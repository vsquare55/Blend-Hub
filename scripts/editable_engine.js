/* Blend Hub - editable single-file version. The same screens as the live Hub; the database lives in this browser (saved automatically)
   and moves in and out through the Excel backup workbook (same format as the live Hub: "Restore from Excel" / "Open Excel"). */
(function () {
  const BOOT = JSON.parse(document.getElementById("hubdata").textContent);
  const KEY = "blendhub_editable_" + BOOT.id;
  const MAGIC = "Blend Hub backup v1";
  let DB = null, changes = 0;
  const pad = n => String(n).padStart(2, "0");
  const now = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const today = () => now().slice(0, 10);
  const plusDays = n => { const d = new Date(Date.now() + n * 864e5); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const err = m => { const e = new Error(m); e.hub = true; return e; };
  const jr = (o, s) => new Response(JSON.stringify(o), {status: s || 200, headers: {"Content-Type": "application/json"}});
  const who = () => { try { return localStorage.getItem("hubUser") || "Guest"; } catch (e) { return "Guest"; } };

  /* ---------------------------------------------------------------- the database */
  const toObjs = t => t.rows.map(r => { const o = {}; t.cols.forEach((c, i) => o[c] = r[i]); return o; });
  function fresh() { const d = {}; for (const tb in BOOT.tables) d[tb] = toObjs(BOOT.tables[tb]); return d; }
  function load() {
    try { const s = localStorage.getItem(KEY); if (s) { DB = JSON.parse(s); return; } } catch (e) {}
    DB = fresh();
  }
  function setStatus() {
    const el = document.getElementById("editbar_status"); if (!el) return;
    el.textContent = changes ? `${changes} change${changes > 1 ? "s" : ""} since the last Excel file` : "No changes since the last Excel file";
    el.style.color = changes ? "#B4421F" : "#0E6E73";
  }
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(DB)); try { localStorage.setItem(KEY + "_n", String(changes)); } catch (e) {} }
    catch (e) { const el = document.getElementById("editbar_status"); if (el) el.textContent = "Could not save in the browser - save an Excel file now"; }
    setStatus();
  }
  const meta = (k, v) => { let r = DB.meta.find(x => x.k === k); if (v === undefined) return r ? r.v : ""; if (!r) DB.meta.push(r = {k, v: ""}); r.v = String(v); };
  const nextId = tb => DB[tb].reduce((m, r) => Math.max(m, r.id || 0), 0) + 1;
  function newRow(tb, vals) {
    const t = BOOT.tables[tb], o = {};
    t.cols.forEach((c, i) => { const d = t.defaults[c]; o[c] = d === null || d === undefined ? (t.types[c] === "INT" ? 0 : "") : (t.types[c] === "INT" ? +d : String(d).replace(/^'|'$/g, "")); });
    Object.assign(o, vals); if (t.cols.includes("id") && !o.id) o.id = nextId(tb); DB[tb].push(o); return o;
  }
  function log(by, tid, what, detail, field, oldv, newv) {
    DB.log.push({id: nextId("log"), ts: now(), by: by || "", txn_id: tid, what, detail: String(detail || "").slice(0, 600), field: field || "", oldv: String(oldv ?? "").slice(0, 4000), newv: String(newv ?? "").slice(0, 4000)});
  }
  const touch = tid => { const t = DB.txn.find(x => x.id === tid); if (t) t.updated = now(); };

  /* ---------------------------------------------------------------- rules copied from the live Hub */
  const TXN_FIELDS = BOOT.txn_fields;
  function couple(clean, oldStatus) {
    if ("status" in clean && !("active" in clean)) clean.active = clean.status === "On hold" ? 0 : 1;
    else if ("active" in clean && !("status" in clean) && oldStatus !== undefined) {
      if (clean.active === 0 && oldStatus !== "On hold") clean.status = "On hold"; else if (clean.active === 1 && oldStatus === "On hold") clean.status = "Preliminary";
    }
    return clean;
  }
  function cleanFields(f) {
    const c = {}; TXN_FIELDS.forEach(k => { if (k in f) c[k] = f[k]; });
    for (const [k, allowed] of Object.entries(BOOT.enum_checks)) if (k in c && !allowed.includes(c[k])) throw err(k.replace(/_/g, " ") + " must be one of: " + allowed.join(", ") + ".");
    if ("active" in c) c.active = [1, true, "1", "true"].includes(c.active) ? 1 : 0;
    if ("value" in c) {
      const v = String(c.value ?? "").trim().replace(/,/g, "");
      if (!v) c.value = ""; else { const n = Number(v); if (isNaN(n)) throw err("Indicative value must be a number in EUR million (e.g. 250) - no text."); if (n < 0) throw err("Indicative value cannot be negative."); c.value = String(+n.toFixed(2)); }
    }
    return c;
  }
  function chkSetRaw(by, tid, item, state, remark) {
    let r = DB.chk.find(x => x.txn_id === tid && x.item === item); const old = r ? {state: r.state, remark: r.remark} : null;
    const rem = remark !== undefined && remark !== null ? remark : (old ? old.remark : "");
    if (!r) { r = {txn_id: tid, item, state, remark: rem, updated: now()}; DB.chk.push(r); } else { r.state = state; r.remark = rem; r.updated = now(); }
    if (item === "LoI / EoI submitted") {
      const t = DB.txn.find(x => x.id === tid); if (t) { t.loi_sent = state === "Yes" ? "Yes" : "No"; if (state === "Yes" && !t.loi_response) t.loi_response = /accept/i.test(rem) ? "Accepted" : "Awaiting"; }
    }
    if (!old || old.state !== state) log(by, tid, "Checklist: " + item, `${(old && old.state) || "-"} -> ${state || "-"}`); else if ((old.remark || "") !== rem) log(by, tid, "Checklist note: " + item, rem);
    auto(tid);
  }
  function auto(tid) {
    const t = DB.txn.find(x => x.id === tid && !x.deleted), want = {};
    if (t && t.active) {
      DB.chk.filter(r => r.txn_id === tid && r.state === "In progress").forEach(r => want["chk:" + r.item] = `${r.item} - in progress: follow up and close it`);
      const links = DB.link.filter(l => l.txn_id === tid), pt = id => DB.party.find(p => p.id === id) || {};
      const sts = new Set(links.filter(l => pt(l.party_id).type === "EPC").map(l => l.status));
      const nn = DB.need.some(n => n.txn_id === tid && n.type === "EPC" && n.state === "Not needed");
      if (!nn && !["Appointed", "Shortlisted", "Term sheet received"].some(s => sts.has(s))) {
        if (["To be approached", "Approached", "In discussion"].some(s => sts.has(s))) want.epc = "EPC - discussions in progress: close the shortlist";
        else if (["Tie-up done", "P1", "P2"].includes(t.status)) want.epc = "EPC - find and shortlist an EPC";
      }
      links.filter(l => l.status === "To be approached").forEach(l => { const p = pt(l.party_id); want[`appr:${l.party_id}:${l.updated}`] = `Approach ${p.name} (${p.type}) - marked 'to be approached'`; });
      DB.meeting.filter(m => m.txn_id === tid && !m.deleted && m.status === "To be scheduled").forEach(m => want["msched:" + m.id] = "Schedule a meeting with " + (m.who || "the ministry / owner"));
      const ms = DB.meeting.filter(m => m.txn_id === tid && !m.deleted && !["Cancelled", "To be scheduled"].includes(m.status)).sort(meetOrder);
      if (ms.length && !ms.some(m => m.status === "Held") && ["Requested", "Scheduled"].includes(ms[0].status)) want.meeting = "Meeting with ministry / owner - requested / scheduled: hold it and record the outcome";
    }
    const rows = DB.action.filter(a => a.txn_id === tid && a.auto && !a.deleted), seen = new Set(rows.map(r => r.auto));
    Object.entries(want).forEach(([k, text]) => { if (!seen.has(k)) { newRow("action", {txn_id: tid, text, owner: (t.sub_lead || t.lead || ""), due: plusDays(7), created: now(), by: "Auto", auto: k}); log("Auto", tid, "Action added (automatic)", text); } });
    rows.forEach(r => { if (!r.done && !(r.auto in want)) { r.done = 1; r.done_ts = now(); log("Auto", tid, "Action done (automatic)", r.auto); } });
  }
  const meetOrder = (a, b) => ((a.day === "") - (b.day === "")) || (a.day < b.day ? 1 : a.day > b.day ? -1 : 0) || b.id - a.id;
  function syncMeeting(tid) {
    const ms = DB.meeting.filter(m => m.txn_id === tid && !m.deleted && m.status !== "Cancelled").sort(meetOrder), held = ms.filter(m => m.status === "Held"), pick = held[0] || ms[0], t = DB.txn.find(x => x.id === tid); if (!t) return;
    if (pick) { t.meeting_status = pick.status; t.meeting_with = pick.who; t.meeting_date = pick.day; t.meeting_notes = pick.notes; }
    else { t.meeting_status = "Not held"; t.meeting_with = ""; t.meeting_date = ""; t.meeting_notes = ""; }
    auto(tid);
  }
  function meetingAdd(by, tid, day, who_, status, notes) {
    if (!BOOT.meeting_kinds.includes(status)) throw err("Meeting status must be one of: " + BOOT.meeting_kinds.join(", "));
    const m = newRow("meeting", {txn_id: tid, day: day || "", who: String(who_ || "").split(/\s+/).join(" "), status, notes: notes || "", by: by || "", created: now(), deleted: 0});
    log(by, tid, "Meeting " + status.toLowerCase(), `${day || "no date"} · ${who_ || "-"}` + (notes ? " · " + String(notes).slice(0, 120) : "")); syncMeeting(tid); return m.id;
  }
  function linkRaw(by, tid, pid, status, remark) {
    const p = DB.party.find(x => x.id === pid); if (!p) throw err("Counterparty not found.");
    let l = DB.link.find(x => x.txn_id === tid && x.party_id === pid); const old = l ? {status: l.status, remark: l.remark} : null, rem = remark !== undefined && remark !== null ? remark : (old ? old.remark : "");
    if (!l) DB.link.push(l = {txn_id: tid, party_id: pid, status, remark: rem, updated: now(), by: by || ""}); else Object.assign(l, {status, remark: rem, updated: now(), by: by || ""});
    if (!old) log(by, tid, `${p.type} mapped`, `${p.name} -> ${status}`); else if (old.status !== status) log(by, tid, `${p.type} status`, `${p.name}: ${old.status} -> ${status}`); else if ((old.remark || "") !== rem) log(by, tid, `${p.type} remark`, `${p.name}: ${rem}`);
    touch(tid); auto(tid); return pid;
  }
  function partyGetOrCreate(name, ptype) {
    name = String(name || "").split(/\s+/).filter(Boolean).join(" ");
    if (!BOOT.party_types.includes(ptype)) throw err("Counterparty type must be one of " + BOOT.party_types.join(", "));
    if (!name) throw err("Counterparty needs a name.");
    const r = DB.party.find(p => p.type === ptype && p.name.toLowerCase() === name.toLowerCase()); if (r) { r.active = 1; return r.id; }
    return newRow("party", {name, type: ptype, active: 1}).id;
  }
  const SUBD = {JT: "Sunil", RB: "Karan", SS: "Heena"};
  function subFollow(clean, old) {
    if ("sub_lead" in clean || !("lead" in clean)) return clean;
    const cur = old ? old.sub_lead || "" : ""; if (cur === "" || (old && cur === (SUBD[old.lead || ""] || "\u0000"))) clean.sub_lead = SUBD[clean.lead] || ""; return clean;
  }
  function txnApply(by, tid, fields) {
    const t = DB.txn.find(x => x.id === tid); if (!t) throw err("Transaction not found.");
    const clean = subFollow(couple(cleanFields(fields), t.status), t), changed = {};
    Object.entries(clean).forEach(([k, v]) => { if (String(t[k] ?? "") !== String(v)) changed[k] = v; });
    if (!Object.keys(changed).length) return;
    const old = Object.assign({}, t); Object.assign(t, changed); t.updated = now();
    if ("status" in changed || "active" in changed) auto(tid);
    if ("loi_sent" in changed) {
      if (changed.loi_sent === "Yes") { const c = DB.chk.find(x => x.txn_id === tid && x.item === "LoI / EoI submitted"); if (c) { c.state = "Yes"; c.updated = now(); } else DB.chk.push({txn_id: tid, item: "LoI / EoI submitted", state: "Yes", remark: "", updated: now()}); }
      else { const c = DB.chk.find(x => x.txn_id === tid && x.item === "LoI / EoI submitted" && x.state === "Yes"); if (c) { c.state = "No"; c.updated = now(); } }
    }
    Object.entries(changed).forEach(([k, v]) => log(by, tid, "Changed " + k.replace(/_/g, " "), `${String(old[k] || "-").slice(0, 80)} -> ${String(v || "-").slice(0, 80)}`, k, old[k] ?? "", v));
  }

  /* ---------------------------------------------------------------- the snapshot the screens read */
  function snapshot(hide) {
    const h = (hide === "1" ? "PH" : hide || "").toUpperCase(), out = []; if (h.includes("P")) out.push("Preliminary"); if (h.includes("H")) out.push("On hold");
    const last = {}; DB.log.forEach(l => { if (l.txn_id !== null && l.txn_id !== undefined && l.txn_id !== "" && (!last[l.txn_id] || l.ts > last[l.txn_id])) last[l.txn_id] = l.ts; });
    let txns = DB.txn.filter(t => !t.deleted).sort((a, b) => (a.country || "").localeCompare(b.country || "") || (a.name || "").localeCompare(b.name || "")).map(t => Object.assign({}, t, {last_activity: last[t.id] || t.updated || ""}));
    let gone = new Set();
    if (h) { const nn = new Set(DB.need.filter(n => n.type === "EPC" && n.state === "Not needed").map(n => n.txn_id)); gone = new Set(txns.filter(t => out.includes(t.status) || (h.includes("F") && t.structure === "Financing only") || (h.includes("N") && nn.has(t.id))).map(t => t.id)); txns = txns.filter(t => !gone.has(t.id)); }
    const keep = new Set(txns.map(t => t.id)), mine = r => !h || keep.has(r.txn_id), pick = (o, ks) => { const r = {}; ks.forEach(k => r[k] = o[k]); return r; };
    let parties = DB.party.filter(p => p.active).sort((a, b) => (a.type || "").localeCompare(b.type || "") || (a.name || "").localeCompare(b.name || ""));
    const links = DB.link.filter(mine).map(l => pick(l, ["txn_id", "party_id", "status", "remark", "updated", "by"]));
    if (h) { const used = new Set(links.map(l => l.party_id)), any = new Set(DB.link.map(l => l.party_id)); parties = parties.filter(p => used.has(p.id) || !any.has(p.id)); }
    const rev = +meta("rev") || 0;
    return {
      txns, hidden: !!h, trash: DB.txn.filter(t => t.deleted && !out.includes(t.status)).map(t => pick(t, ["id", "name", "country", "status"])), parties, links,
      needs: DB.need.filter(mine), chk: DB.chk.filter(mine).map(r => pick(r, ["txn_id", "item", "state", "remark"])),
      comments: DB.comment.filter(c => !c.deleted && mine(c)).sort((a, b) => (a.day < b.day ? 1 : a.day > b.day ? -1 : 0) || b.id - a.id).map(c => pick(c, ["id", "txn_id", "ts", "day", "by", "text", "kind"])), undo: null,
      actions: DB.action.filter(a => !a.deleted && mine(a)).sort((a, b) => (a.done - b.done) || ((a.due === "") - (b.due === "")) || (a.due < b.due ? -1 : a.due > b.due ? 1 : 0) || a.id - b.id).map(a => pick(a, ["id", "txn_id", "text", "owner", "due", "done", "done_ts", "created", "by", "auto"])),
      meetings: DB.meeting.filter(m => !m.deleted && mine(m)).sort(meetOrder).map(m => pick(m, ["id", "txn_id", "day", "who", "status", "notes", "by"])),
      geo: DB.geo.slice().sort((a, b) => a.country.localeCompare(b.country)), access: (DB.access || []).filter(a => !a.deleted).sort((a, b) => (a.source || "").localeCompare(b.source || "") || (a.country || "").localeCompare(b.country || "")), rev, pms: BOOT.pms,
      enums: Object.assign({}, BOOT.enums, {statuses: BOOT.enums.all_statuses.filter(s => !out.includes(s))}),
      lock: {mine: true, holder: who(), user: who()}, default_user: who()
    };
  }

  /* ---------------------------------------------------------------- the API the screens call */
  const API = {
    "/api/txn": (by, d) => {
      if (d.id !== undefined && d.id !== null) { txnApply(by, d.id, d.fields || {}); return {ok: true, id: d.id}; }
      const clean = subFollow(couple(cleanFields(d.fields || {})));
      if (!String(clean.name || "").trim()) throw err("A transaction needs a name.");
      if (!("received_date" in clean)) clean.received_date = today();
      const t = newRow("txn", Object.assign({key: "manual-" + Date.now(), created: now(), updated: now(), origin: "Added in Hub", deleted: 0}, clean));
      log(by, t.id, "Transaction added", clean.name); return {ok: true, id: t.id};
    },
    "/api/txn/bulk": (by, d) => { d.ids.forEach(id => { if (DB.txn.find(x => x.id === id)) txnApply(by, id, d.fields); }); return {ok: true, n: d.ids.length}; },
    "/api/txn/trash": (by, d) => { d.ids.forEach(id => { const t = DB.txn.find(x => x.id === id); if (t) { t.deleted = d.deleted === false ? 0 : 1; t.updated = now(); log(by, id, d.deleted === false ? "Restored from trash" : "Moved to trash"); } }); return {ok: true}; },
    "/api/txn/dup": (by, d) => {
      const o = DB.txn.find(x => x.id === d.id); if (!o) throw err("Transaction not found.");
      const n = newRow("txn", Object.assign({}, o, {id: 0, key: "manual-" + Date.now(), created: now(), updated: now(), origin: "Duplicated in Hub", name: o.name + " (copy)"}));
      DB.link.filter(l => l.txn_id === o.id).forEach(l => DB.link.push(Object.assign({}, l, {txn_id: n.id, updated: now(), by}))); log(by, n.id, "Transaction added", n.name); return {ok: true, id: n.id};
    },
    "/api/link": (by, d) => { if (!BOOT.enums.link_status.includes(d.status || "Identified")) throw err("Unknown status " + d.status); const pid = d.party_id !== undefined && d.party_id !== null ? d.party_id : partyGetOrCreate(d.name, d.type); linkRaw(by, d.txn_id, pid, d.status || "Identified", d.remark); return {ok: true, party_id: pid}; },
    "/api/link/del": (by, d) => { const p = DB.party.find(x => x.id === d.party_id); DB.link = DB.link.filter(l => !(l.txn_id === d.txn_id && l.party_id === d.party_id)); log(by, d.txn_id, `${p ? p.type : "Counterparty"} removed`, p ? p.name : ""); auto(d.txn_id); return {ok: true}; },
    "/api/link/bulk": (by, d) => {
      let n = 0;
      d.txn_ids.forEach(tid => d.party_ids.forEach(pid => {
        const have = DB.link.find(l => l.txn_id === tid && l.party_id === pid);
        if (d.action === "remove") { if (have) { const p = DB.party.find(x => x.id === pid); DB.link = DB.link.filter(l => l !== have); log(by, tid, `${p.type} removed`, `${p.name} (bulk)`); n++; } }
        else if (d.action === "add" || have) { linkRaw(by, tid, pid, d.status || "Shortlisted"); n++; }
      }));
      d.txn_ids.forEach(auto); return {ok: true, n};
    },
    "/api/need": (by, d) => { if (!["Needed", "Not needed"].includes(d.state)) throw err("State must be Needed or Not needed."); const r = DB.need.find(n => n.txn_id === d.txn_id && n.type === d.type); if (r) r.state = d.state; else DB.need.push({txn_id: d.txn_id, type: d.type, state: d.state}); log(by, d.txn_id, `${d.type}: ${d.state.toLowerCase()}`); auto(d.txn_id); return {ok: true}; },
    "/api/chk": (by, d) => { if (![...BOOT.enums.check_states, ""].includes(d.state || "")) throw err("Unknown checklist state."); chkSetRaw(by, d.txn_id, d.item, d.state || "", d.remark); return {ok: true}; },
    "/api/chk/del": (by, d) => { if (BOOT.enums.check_items.includes(d.item)) throw err("This is a standard readiness item - mark it N.A. if it does not apply to this project."); DB.chk = DB.chk.filter(r => !(r.txn_id === d.txn_id && r.item === d.item)); log(by, d.txn_id, "Readiness item removed", d.item); auto(d.txn_id); return {ok: true}; },
    "/api/chk/bulk": (by, d) => { d.txn_ids.forEach(id => chkSetRaw(by, id, d.item, d.state || "")); return {ok: true, n: d.txn_ids.length}; },
    "/api/party": (by, d) => { const p = DB.party.find(x => x.id === d.id); if (p) ["name", "country", "notes", "active"].forEach(k => { if (k in (d.fields || {})) p[k] = d.fields[k]; }); return {ok: true}; },
    "/api/comment": (by, d) => {
      if (!String(d.text || "").trim()) throw err("Write the comment first."); if (!["", "Management"].includes(d.kind || "")) throw err("Unknown comment type.");
      const c = newRow("comment", {txn_id: d.txn_id, ts: now(), day: d.day || today(), by: by || "", text: d.text.trim(), kind: d.kind || "", deleted: 0}); log(by, d.txn_id, d.kind ? "Management comment" : "Comment", d.text.trim().slice(0, 200)); touch(d.txn_id); return {ok: true, id: c.id};
    },
    "/api/comment/edit": (by, d) => { const c = DB.comment.find(x => x.id === d.id); if (!c) throw err("Comment not found."); if (d.deleted) { c.deleted = 1; log(by, c.txn_id, "Comment deleted", c.text.slice(0, 200)); } else if (d.text !== undefined && d.text !== null && d.text.trim() !== c.text) { log(by, c.txn_id, "Comment edited", `${c.text.slice(0, 100)} -> ${d.text.trim().slice(0, 100)}`); c.text = d.text.trim(); } return {ok: true}; },
    "/api/action": (by, d) => { if (!String(d.text || "").trim()) throw err("Write the action first."); const a = newRow("action", {txn_id: d.txn_id, text: d.text.trim(), owner: d.owner || "", due: d.due || "", created: now(), by: by || "", done: 0, deleted: 0, auto: ""}); log(by, d.txn_id, "Action added", d.text.trim().slice(0, 150) + (d.owner ? ` (owner ${d.owner})` : "") + (d.due ? ` due ${d.due}` : "")); return {ok: true, id: a.id}; },
    "/api/action/update": (by, d) => {
      const a = DB.action.find(x => x.id === d.id); if (!a) throw err("Action not found."); const f = d.fields || {}, s = {};
      ["text", "owner", "due", "done", "deleted"].forEach(k => { if (k in f) s[k] = f[k]; });
      if ("done" in s) { s.done = [1, true, "1"].includes(s.done) ? 1 : 0; s.done_ts = s.done ? now() : ""; }
      if ("deleted" in s) s.deleted = [1, true, "1"].includes(s.deleted) ? 1 : 0;
      if (Object.keys(s).length) { Object.assign(a, s); log(by, a.txn_id, s.done ? "Action done" : "done" in s ? "Action reopened" : s.deleted ? "Action deleted" : "Action updated", a.text.slice(0, 150)); } return {ok: true};
    },
    "/api/meeting/add": (by, d) => ({ok: true, id: meetingAdd(by, d.txn_id, d.day || "", d.who || "", d.status || "Held", d.notes || "")}),
    "/api/meeting/update": (by, d) => {
      const m = DB.meeting.find(x => x.id === d.id); if (!m) throw err("Meeting not found."); const f = d.fields || {}, s = {};
      ["day", "who", "status", "notes"].forEach(k => { if (k in f) s[k] = f[k]; }); if (s.status && !BOOT.meeting_kinds.includes(s.status)) throw err("Meeting status must be one of: " + BOOT.meeting_kinds.join(", "));
      if ("deleted" in f) s.deleted = f.deleted ? 1 : 0;
      if (Object.keys(s).length) { Object.assign(m, s); log(by, m.txn_id, s.deleted ? "Meeting removed" : "Meeting updated", Object.entries(s).filter(([k]) => k !== "deleted").map(([k, v]) => `${k}: ${v}`).join(", ").slice(0, 200)); syncMeeting(m.txn_id); } return {ok: true};
    },
    "/api/meeting/latest": (by, d) => {
      const tid = d.txn_id, ms = DB.meeting.filter(m => m.txn_id === tid && !m.deleted && m.status !== "Cancelled").sort(meetOrder), held = ms.filter(m => m.status === "Held"), pick = held[0] || ms[0], f = {};
      ["day", "who", "status", "notes"].forEach(k => { if (k in (d.fields || {})) f[k] = d.fields[k]; }); if (f.status === "Not held") delete f.status;
      if (!pick) { const st = f.status || "Held"; meetingAdd(by, tid, f.day || (st === "Held" ? today() : ""), f.who || "", st, f.notes || ""); return {ok: true}; }
      if (f.status === "Held" && !(f.day || pick.day)) f.day = today();
      if (Object.keys(f).length) { Object.assign(pick, f); log(by, tid, "Meeting updated", Object.entries(f).map(([k, v]) => `${k}: ${v}`).join(", ").slice(0, 200)); syncMeeting(tid); } return {ok: true};
    },
    "/api/review": (by, d) => { const t = DB.txn.find(x => x.id === d.txn_id); if (t) { const nxt = plusDays(+d.days || 7); t.last_reviewed = today(); t.next_review = nxt; t.updated = now(); log(by, t.id, "Reviewed", "next review " + nxt); } return {ok: true}; },
    "/api/geo": (by, d) => {
      if (!["", ...BOOT.enums.leads].includes(d.lead || "")) throw err("Owner must be RB, JT or SS."); let g = DB.geo.find(x => x.country === d.country); if (g) g.lead = d.lead || ""; else DB.geo.push({country: d.country, lead: d.lead || ""});
      let n = 0; if (d.apply !== false) DB.txn.filter(t => !t.deleted && (t.country || "").toLowerCase() === d.country.toLowerCase() && t.lead !== (d.lead || "")).forEach(t => { log(by, t.id, "Changed lead", `${t.lead || "-"} -> ${d.lead || "-"} (country ${d.country})`, "lead", t.lead, d.lead || ""); t.lead = d.lead || ""; n++; }); return {ok: true, n};
    },
    "/api/action/bulk": (by, d) => {
      if (!String(d.text || "").trim()) throw err("Write the task first."); let n = 0;
      d.txn_ids.forEach(id => { const t = DB.txn.find(x => x.id === id && !x.deleted); if (!t) return; const ow = d.owner === "__sub" ? (t.sub_lead || t.lead || "") : (d.owner || ""); newRow("action", {txn_id: id, text: d.text.trim(), owner: ow, due: d.due || "", created: now(), by: by || "", done: 0, deleted: 0, auto: ""}); log(by, id, "Action added", d.text.trim().slice(0, 150) + (ow ? ` (owner ${ow})` : "") + " (bulk)"); n++; });
      return {ok: true, n};
    },
    "/api/access": (by, d) => {
      DB.access = DB.access || []; const f = d.fields || {};
      if (d.id === undefined || d.id === null) { if (!f.source) throw err("Which source is this connection for?"); if (!(f.country || f.ministry)) throw err("Write the country and / or the ministry or department."); const a = newRow("access", Object.assign({created: now(), by: by || "", deleted: 0}, f)); return {ok: true, id: a.id}; }
      const a = DB.access.find(x => x.id === d.id); if (a) ["source", "country", "ministry", "contact", "notes"].forEach(k => { if (k in f) a[k] = f[k]; }); return {ok: true, id: d.id};
    },
    "/api/access/del": (by, d) => { const a = (DB.access || []).find(x => x.id === d.id); if (a) a.deleted = 1; return {ok: true}; },
    "/api/lock/take": () => ({ok: true})
  };
  const NO = "This function needs the live Hub (or the Excel file opened there): " ;

  /* ---------------------------------------------------------------- fetch shim */
  window.fetch = async (u, o) => {
    u = String(u); const p = u.split("?")[0], by = (() => { try { return decodeURIComponent((o && o.headers && o.headers["X-User"]) || who()); } catch (e) { return who(); } })();
    if (p === "/api/all") return jr(snapshot(o && o.headers && o.headers["X-Hide"] || ""));
    if (p === "/api/rev") return jr({rev: +meta("rev") || 0, lock: {mine: true, holder: who(), user: who()}, ver: "editable"});
    if (p === "/api/history") { const id = +new URLSearchParams(u.split("?")[1]).get("txn"); return jr(DB.log.filter(l => l.txn_id === id).sort((a, b) => b.id - a.id).slice(0, 120).map(l => ({id: l.id, ts: l.ts, by: l.by, what: l.what, detail: l.detail, field: l.field, oldv: l.oldv, newv: l.newv}))); }
    if (p === "/api/backups" || p === "/api/changes") return jr([]);
    if (p === "/api/print/cols") return jr({});
    const fn = API[p];
    if (fn && o && o.method === "POST") {
      try { const d = JSON.parse(o.body || "{}"); const r = fn(by, d); changes++; meta("rev", (+meta("rev") || 0) + 1); persist(); return jr(r); } catch (e) { return jr({error: e.hub ? e.message : "Could not do that here: " + e.message}, 400); }
    }
    return jr({error: NO + p.replace("/api/", "").replace(/\//g, " ") + ". The screens, filters, editing, mapping, meetings, actions and Excel save / open all work here."}, 400);
  };

  /* ---------------------------------------------------------------- Excel in and out */
  const MAKE_SHEETS = () => {
    const wb = XLSX.utils.book_new(), tb = Object.keys(BOOT.tables).sort(), hidden = [];
    const readable = DB.txn.filter(t => !t.deleted).sort((a, b) => (a.country || "").localeCompare(b.country || "") || (a.name || "").localeCompare(b.name || "")).map((t, i) => ({"#": i + 1, Project: t.name, Country: t.country, Sector: t.sector, Model: t.structure, "Value (EUR mn)": t.value === "" ? "" : +t.value, "Client type": t.client_type, Status: t.status, Priority: t.priority, Owner: t.lead, "Sub-owner": t.sub_lead, Source: t.introduced,
      Meeting: t.meeting_status, "Meeting date": t.meeting_date, "Meeting with": t.meeting_with, "LoI / EoI": t.loi_sent, "Review outcome": t.review_outcome, "Next steps": t.next_steps, Summary: t.summary, "Last updated": t.updated}));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet([{Note: "Blend Hub - made from the editable HTML file on " + now() + ". Readable tab: Transactions. The hidden tabs starting with _ hold the complete database: open this file in the editable HTML (Open Excel) or in the live Hub (Settings & data > Restore from Excel). Do not edit the hidden tabs."}]), "README");
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(readable), "Transactions");
    tb.forEach(name => { const t = BOOT.tables[name]; XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([t.cols].concat(DB[name].map(r => t.cols.map(c => r[c] === undefined ? null : r[c])))), "_" + name); });
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([["magic", "made", "transactions", "tables"], [MAGIC, now(), DB.txn.filter(t => !t.deleted).length, tb.join(",")]]), "_backup_info");
    wb.Workbook = {Sheets: wb.SheetNames.map(n => ({Hidden: n.startsWith("_") ? 1 : 0}))};
    return wb;
  };
  window.hubEditable = {excelBase64: () => XLSX.write(MAKE_SHEETS(), {type: "base64", bookType: "xlsx"}), openExcel: f => openExcel(f)};
  function saveExcel() {
    const wb = MAKE_SHEETS(), name = `Blend_Hub_${today()}_${pad(new Date().getHours())}${pad(new Date().getMinutes())}.xlsx`;
    XLSX.writeFile(wb, name); changes = 0; persist(); alert("Saved: " + name + "\n\nIt is in your Downloads folder. Open it again here with 'Open Excel', or restore it in the live Hub (Settings & data > Restore from Excel).");
  }
  function openExcel(file) {
    const rd = new FileReader();
    rd.onload = () => {
      try {
        const wb = XLSX.read(new Uint8Array(rd.result), {type: "array", cellDates: false}); if (!wb.Sheets["_backup_info"]) throw new Error("This is not a Blend Hub Excel file (the hidden _backup_info tab is missing).");
        const info = XLSX.utils.sheet_to_json(wb.Sheets["_backup_info"], {header: 1})[1]; if (info[0] !== MAGIC) throw new Error("This file was made by a different version.");
        const nd = {}; String(info[3]).split(",").filter(Boolean).forEach(tb => {
          const t = BOOT.tables[tb], ws = wb.Sheets["_" + tb]; if (!t || !ws) return; const rows = XLSX.utils.sheet_to_json(ws, {header: 1, defval: null}), head = rows[0] || [];
          nd[tb] = rows.slice(1).filter(r => r.some(x => x !== null && x !== "")).map(r => { const o = {}; t.cols.forEach(c => { const i = head.indexOf(c); let v = i < 0 ? null : r[i]; if (t.types[c] === "INT") v = v === null || v === "" || isNaN(+v) ? (t.defaults[c] !== null && t.defaults[c] !== undefined ? +t.defaults[c] : 0) : Math.trunc(+v); else v = v === null ? "" : String(v); o[c] = v; }); return o; });
        });
        if (!nd.txn || !nd.txn.length) throw new Error("The file holds no transactions - nothing was changed.");
        for (const tb in BOOT.tables) if (!nd[tb]) nd[tb] = [];
        if (!confirm(`Open this Excel file?\n\n${nd.txn.length} transactions will replace what is in this window now (save an Excel file first if you want to keep the current state).`)) return;
        DB = nd; changes = 0; persist(); location.reload();
      } catch (e) { alert("Could not open the file: " + e.message); }
    };
    rd.readAsArrayBuffer(file);
  }
  function startAgain() { if (confirm("Throw away every change made in this window and go back to the data this file was made with?")) { try { localStorage.removeItem(KEY); } catch (e) {} DB = fresh(); changes = 0; location.reload(); } }

  /* ---------------------------------------------------------------- bar + start */
  load(); try { changes = +localStorage.getItem(KEY + "_n") || 0; } catch (e) {}
  try { if (!localStorage.getItem("hubUser")) localStorage.setItem("hubUser", "Guest"); } catch (e) {}
  window.addEventListener("DOMContentLoaded", () => {
    const bar = document.createElement("div"); bar.id = "editbar"; bar.className = "noprint";
    bar.innerHTML = `<b>Editable copy</b><span id="editbar_status"></span><button id="eb_save" title="Download the whole Hub as an Excel file">⬇ Save as Excel</button><button id="eb_open" title="Load an Excel file made by this page or by the live Hub">⬆ Open Excel</button><button id="eb_reset" title="Forget all changes made here">⟲ Start again</button><input type="file" id="eb_file" accept=".xlsx" style="display:none">`;
    document.body.appendChild(bar); setStatus();
    document.getElementById("eb_save").onclick = saveExcel; document.getElementById("eb_open").onclick = () => document.getElementById("eb_file").click();
    document.getElementById("eb_file").onchange = e => { if (e.target.files[0]) openExcel(e.target.files[0]); }; document.getElementById("eb_reset").onclick = startAgain;
  });
})();
