#!/usr/bin/env python3
"""Blend Hub - load the BIP workbook (every transaction), the deck projects, and the Madagascar call notes into hub.db.

Safe to run again: existing transactions are never overwritten (only empty fields are filled, new rows are added)."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import deckcore as core
import hubdb as H
import modelnames
import sectors
import statusfile as sf
import tracker as T

ECA_RX = re.compile(r"\b(KUKE|EIFO|SACE|Euler Hermes|UKEF|Atradius|Bpifrance|BPI France|Coface|OeKB|EKF|Sinosure|NEXI|JBIC|US EXIM|EXIM US|"
                    r"Cesce|Eksfin|GIEK|Finnvera|Credendo|EKN)\b", re.I)
BANK_RX = re.compile(r"bank|banque|kredit|capital|finance|fund|eximbank|dbsa|afreximbank|ebid|boad|bidc|\bafc\b|\bifc\b|proparco|fmo|deg\b", re.I)
GOV_RX = re.compile(r"minist|minstr|misitr|\bmin\b|\bmin\.|\bmo[heaw]\b|govt|government|presiden|secretariat|state of|republic|prefecture|municipal|commune|\bpws\b|\bpwd\b|\bdg\b", re.I)
SOE_NAMES = {"tanesco", "dawasa", "sonara", "camtel", "sodecoton", "socadel", "camwater", "scdp", "ccaa", "jirama", "seg", "tpa", "sonabhy",
             "sobimap", "ppa", "spat", "bpc", "botswana power", "onad", "minhas", "zesco", "senelec", "sbee", "ceb", "nawec", "lec", "eneo",
             "sonatrach", "sodeci", "cie", "sonel", "ocp", "rsb", "reg", "ugandan", "uetcl", "kplc", "ketraco", "rea", "tazara", "trc", "pura", "tanroads", "tarura", "temesa", "tcra", "tanroads", "tarura", "temesa", "tcra", "nssf"}
SOE_RX = re.compile(r"\b(" + "|".join(sorted(SOE_NAMES, key=len, reverse=True)) + r")\b|utility|authority|corporation|state[- ]owned|\bsoe\b|national (oil|power|water|railway)|\bport\b", re.I)
PRIVATE_RX = re.compile(r"\b(brands|a2mp|areeba|mtn|sarl|ltd|llc|limited|group|groupe|holding|inc|plc|sasu|sa|gmbh|developer|promoter|private)\b", re.I)
JUNK_RX = re.compile(r"pending|tbc|tbd|process|discuss|needed|^to |^under|^na$|n\.a|none|not yet|identify|finalis|awaited|contractor|appointed|^epc$", re.I)
FACT_RX = {
    "Pre-feasibility / APS": re.compile(r"\b(APS|pre-?feasibility)\b[^.\n]{0,50}(available|prepared|submitted|done|complete|received|shared)|"
                                        r"(available|prepared|submitted|done|complete|received|shared)[^.\n]{0,40}\b(APS|pre-?feasibility)\b", re.I),
    "FSR (feasibility study)": re.compile(r"\b(FSR|feasibility (study|report))\b[^.\n]{0,50}(available|prepared|submitted|done|complete|received|shared)", re.I),
    "Land available": re.compile(r"\bland\b[^.\n]{0,40}(available|allocated|secured|identified|acquired)", re.I),
    "Concession agreement": re.compile(r"concession (agreement|contract)[^.\n]{0,40}(signed|available|in place|received)", re.I),
    "Technical documents": re.compile(r"\b(technical (documents?|studies)|detailed design|BOQ|data room)\b[^.\n]{0,40}(available|shared|received|prepared)", re.I),
}


def clean(s) -> str:
    return " ".join(str(s or "").replace("\xa0", " ").split())


def blankish(v) -> str:
    v = clean(v)
    return "" if v.lower() in ("pending", "tbc", "tbd", "n.a.", "n.a", "na", "n/a", "none", "-", "nil", "no details available yet") else v


def clean_ml(s) -> str:
    return "\n".join(l.strip() for l in str(s or "").replace("\xa0", " ").splitlines() if l.strip())


KNOWN = ["Planet One", "Metito", "Aquaswiss", "SMC", "VSG", "EMS", "Enprode", "Tecmon", "Samcrete", "UHG", "Varaha", "77 Construction", "Omatapalo",
         "Novea Energy", "JIVO Energy", "Delta Gen", "Verteco", "East India Udyog"]
GENERIC = {"dfi", "eca", "epc", "bank", "banks", "lender", "lenders", "investor", "investors", "central bank", "local bank", "e", "tbc", "tbd"}
ALIAS = {"kommunal kredit": "Kommunalkredit", "updated kommunalkredit": "Kommunalkredit", "varah": "Varaha", "varaha infra": "Varaha Infra",
         "infra.heath": "Infra.Health", "infra. health": "Infra.Health", "infra.health": "Infra.Health", "eco bank": "Ecobank",
         "developmnet finance corporation": "Development Finance Corporation", "deltagen": "Delta Gen", "usp": "USP&E", "rieckermann": "Rieckermann",
         "jivo energy": "Jivo Energy", "worldbank": "World Bank"}
BAD_WORD = re.compile(r"refinanc|\bstep\b|^projects?$|^updated$|\bnot\b|\bloi\b|loi's|share|\bother\b|\bproject\b|arrang|solar epcs|\bto\b|\bwill\b|\bwith\b|\bhas\b", re.I)


def _ok_name(p: str) -> bool:
    return bool(p) and 2 < len(p) <= 32 and len(p.split()) <= 4 and not JUNK_RX.search(p) and not BAD_WORD.search(p) and p.lower() not in GENERIC


def split_names(text: str) -> List[str]:
    """Counterparty names out of a free-text cell ('SMC, VSG - prepared EOI', '1. Deltagen / 2. LTL Holdings' ...)."""
    out = []
    for part in re.split(r"[\n/;,+]|\band\b|&", str(text or "")):
        p = clean(re.sub(r"^(finalised|finalized)\s*:?\s*", "", clean(part), flags=re.I))
        p = clean(re.sub(r"^\d+[.)]\s*", "", p))
        p = clean(re.split(r"\s[-–:]\s", p)[0])
        found = [k for k in KNOWN if re.search(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", p, re.I)]
        if len(found) >= 2 and len(p) > 6:
            out.extend(found)
        elif _ok_name(p):
            out.append(p)
    seen, res = set(), []
    for p in (ALIAS.get(x.lower(), x) for x in out):
        if p.lower() not in seen:
            seen.add(p.lower())
            res.append(p)
    return res


def client_type(counterparty: str, name: str = "", introduced: str = "") -> str:
    cp = clean(counterparty)
    if not cp:
        return "To confirm"
    if SOE_RX.search(cp) and not re.search(r"^minist", cp, re.I):
        return "SOE"
    if GOV_RX.search(cp):
        return "Government"
    if PRIVATE_RX.search(cp):
        return "Private"
    return "To confirm"


def derive(f: dict, sheet: str) -> Tuple[str, int, str]:
    """(internal status, active, reason) from the stage / class / EPC mapping / how much we actually know."""
    stage, cls, epc = clean(f.get("stage")).lower(), clean(f.get("class")).upper(), clean(f.get("epc"))
    if "declin" in stage:
        return "On hold", 0, "Declined by the client / counterparty"
    if stage.startswith("hold") or "on hold" in stage:
        return "On hold", 0, "On hold in the BIP file"
    if epc.lower().startswith("finalis"):
        return "Tie-up done", 1, "EPC finalised in the BIP file"
    if cls in ("P1", "P2") or stage in ("p1", "p2"):
        return (cls if cls in ("P1", "P2") else stage.upper()), 1, ""
    if stage in ("advanced",):
        return "P1", 1, "Marked advanced in the BIP file"
    info = clean(sf.field_text(f.get("info", ""))) + clean(sf.field_text(f.get("summary", "")))
    nxt = clean(sf.field_text(f.get("next", "")))
    has_epc = bool(split_names(epc))
    has_val = bool(re.search(r"\d", clean(f.get("value"))))
    if stage in ("information pending", "") and not (has_epc or has_val or len(info) > 60 or len(nxt) > 25):
        return "On hold", 0, "Parked: no information, EPC or value received yet - reopen when data arrives"
    return "Preliminary", 1, ""


def _proc(text: str) -> str:
    t = text.lower()
    neg, ten = "negotiat" in t, bool(re.search(r"tender|bidding|\bbid\b|competitive", t))
    return "Both" if neg and ten else "Negotiated" if neg else "Tender" if ten else "To confirm"


def party_type(kind: str, role: str, name: str) -> Optional[str]:
    k = (kind or "").lower()
    if ECA_RX.search(name):
        return "ECA"
    if k.startswith("epc"):
        return "EPC"
    if k.startswith("investor"):
        return "Investor"
    if k.startswith("bank") or k.startswith("lender"):
        return "Bank / Lender"
    return None


# --------------------------------------------------------------------------- low level helpers (own connection, one commit)
def _party(c, name: str, ptype: str, country: str = "") -> int:
    name = clean(name)
    r = c.execute("SELECT id FROM party WHERE name=? AND type=?", (name, ptype)).fetchone()
    if r:
        return r[0]
    return c.execute("INSERT INTO party(name,type,country) VALUES(?,?,?)", (name, ptype, country)).lastrowid


def _link(c, tid: int, pid: int, status: str, remark: str = "", by: str = "Import"):
    if not c.execute("SELECT 1 FROM link WHERE txn_id=? AND party_id=?", (tid, pid)).fetchone():
        c.execute("INSERT INTO link(txn_id,party_id,status,remark,updated,by) VALUES(?,?,?,?,?,?)", (tid, pid, status, remark, H.now(), by))


def _check(c, tid: int, item: str, state: str, remark: str = ""):
    if not c.execute("SELECT 1 FROM chk WHERE txn_id=? AND item=?", (tid, item)).fetchone():
        c.execute("INSERT INTO chk(txn_id,item,state,remark,updated) VALUES(?,?,?,?,?)", (tid, item, state, remark, H.now()))


TRACKED = ("sector", "structure", "value", "counterparty", "introduced", "summary", "next_steps", "deck_key")


def _snapshot(c, tid: int, vals: dict):
    for f in TRACKED + ("status",):
        if f in vals:
            c.execute("INSERT INTO imp(txn_id,field,val) VALUES(?,?,?) ON CONFLICT(txn_id,field) DO UPDATE SET val=excluded.val", (tid, f, str(vals[f] or "")))


def _refresh(c, tid: int, vals: dict, by: str, stats: dict):
    """Team updated the BIP file: bring the new text in - but never over something a person has edited here."""
    cur = c.execute("SELECT * FROM txn WHERE id=?", (tid,)).fetchone()
    snap = {r["field"]: r["val"] for r in c.execute("SELECT field, val FROM imp WHERE txn_id=?", (tid,))}
    changes = []
    for f in TRACKED:
        new, old = str(vals.get(f) or ""), str(cur[f] or "")
        if not new or new == old:
            continue
        untouched = (old == snap[f]) if f in snap else old == ""
        if untouched:
            c.execute(f"UPDATE txn SET {f}=?, updated=? WHERE id=?", (new, H.now(), tid))
            c.execute("INSERT INTO log(ts,by,txn_id,what,detail,field,oldv,newv) VALUES(?,?,?,?,?,?,?,?)",
                      (H.now(), by, tid, "Updated from file", f"{f.replace('_', ' ')}: {old[:60] or '-'} -> {new[:60]}", f, old, new))
            changes.append(f)
    if "status" in snap and cur["status"] == snap["status"] and vals["status"] != cur["status"]:
        c.execute("UPDATE txn SET status=?, active=?, reason=?, updated=? WHERE id=?", (vals["status"], vals["active"], vals["reason"], H.now(), tid))
        c.execute("INSERT INTO log(ts,by,txn_id,what,detail,field,oldv,newv) VALUES(?,?,?,?,?,?,?,?)",
                  (H.now(), by, tid, "Updated from file", f"status: {cur['status']} -> {vals['status']}", "status", cur["status"], vals["status"]))
        changes.append("status")
    if changes:
        stats["updated"] = stats.get("updated", 0) + 1
    _snapshot(c, tid, vals)


def _backfill_snapshots(c):
    """Transactions imported before refresh existed: what is in the database now counts as 'what the file said', unless a person changed that field."""
    for t in c.execute("SELECT * FROM txn WHERE origin LIKE 'BIP:%' AND id NOT IN (SELECT DISTINCT txn_id FROM imp)").fetchall():
        edited = {r["field"] for r in c.execute("SELECT DISTINCT field FROM log WHERE txn_id=? AND field!='' AND what LIKE 'Changed%'", (t["id"],))}
        for f in TRACKED + ("status",):
            if f not in edited and not (f == "status" and t["origin"].startswith("BIP") and "Madagascar" in (t["origin"] or "")):
                c.execute("INSERT OR IGNORE INTO imp(txn_id,field,val) VALUES(?,?,?)", (t["id"], f, str(t[f] or "")))


def _fill(c, tid: int, **vals):
    """Fill only the empty fields of an existing transaction."""
    cur = c.execute("SELECT * FROM txn WHERE id=?", (tid,)).fetchone()
    sets = {k: v for k, v in vals.items() if v not in ("", None) and not (cur[k] not in ("", None, "To confirm"))}
    if sets:
        c.execute("UPDATE txn SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [tid])


# --------------------------------------------------------------------------- BIP workbook
def group_rows(rows: List[dict]) -> List[dict]:
    """The same project is often listed on several sheets: one transaction per project, best sheet first."""
    groups: List[dict] = []
    for r in sorted(rows, key=lambda r: sf.SHEET_RANK.get(r["sheet"], 1)):
        country = T.canonical(clean(r["country"])).lower()
        prep = sf._prep(r["name"])
        for g in groups:
            if g["country"] == country and sf._score_p(prep, g["prep"]) >= 0.85:
                g["rows"].append(r)
                break
        else:
            groups.append({"country": country, "prep": prep, "rows": [r]})
    return groups


def import_bip(path: Path, by: str = "Import") -> dict:
    parsed = sf.parse_workbook(Path(path))
    rows = parsed["rows"]
    if not rows:
        raise H.HubError("No project table was found in that file.")
    groups = group_rows(rows)
    try:
        deck = core.load_projects("EPC", include_retired=True)["projects"]
    except Exception:
        deck = []  # base deck not present: import the pipeline data anyway (linking to deck slides is optional)
    dm = sf.match_projects(deck, rows)
    row_deck: Dict[Tuple[str, int], str] = {}
    for k, v in dm.items():
        for x in v["rows"]:
            row_deck.setdefault((x["row"]["sheet"], x["row"]["row"]), k)
    deck_src = {p["id"]: p.get("source", "") for p in deck}
    c = H.connect()
    _backfill_snapshots(c)
    geo = {r["country"].lower(): r["lead"] for r in c.execute("SELECT country, lead FROM geo")}
    lead_of = lambda ctry: geo.get(str(ctry).lower()) or T.lead_for_country(ctry) or ""
    stats = {"rows": len(rows), "transactions": len(groups), "added": 0, "existing": 0, "parked": 0, "links": 0, "parties": 0}
    try:
        n_party0 = c.execute("SELECT COUNT(*) FROM party").fetchone()[0]
        for g in groups:
            prim = g["rows"][0]
            f: dict = {}
            for r in g["rows"]:  # primary first; other sheets only fill gaps
                for k, v in r["fields"].items():
                    if k not in f or not clean(sf.field_text(f[k])):
                        f[k] = v
            name = clean(prim["name"])
            country = T.canonical(clean(prim["country"]))
            key = "bip-" + re.sub(r"[^a-z0-9]+", "-", f"{country}-{name}".lower()).strip("-")[:90]
            status, active, reason = derive(f, prim["sheet"])
            summary = clean_ml(sf.field_text(f.get("info", "")) or sf.field_text(f.get("summary", "")))
            nxt = clean_ml(sf.field_text(f.get("next", "")))
            text = summary + "\n" + nxt + "\n" + clean_ml(sf.field_text(f.get("remarks", "")))
            deck_key = next((row_deck[(r["sheet"], r["row"])] for r in g["rows"] if (r["sheet"], r["row"]) in row_deck), "")
            vals = dict(name=name, country=country, sector=clean(f.get("sector")) or sectors.infer_sector(deck_key or name, name),
                        structure=modelnames.norm(blankish(f.get("structure"))), value=blankish(f.get("value")),
                        client_type=client_type(clean(f.get("counterparty"))), status=status, active=active, reason=reason,
                        procurement=_proc(text), lead=lead_of(country), introduced=H.fix_sources(deck_src.get(deck_key) or clean(f.get("introduced"))),
                        counterparty=clean(f.get("counterparty")), summary=summary[:3000], next_steps=nxt[:2500], deck_key=deck_key,
                        ext_category="Hold" if status == "On hold" else "BIP", origin="BIP: " + ", ".join(sorted({r["sheet"] for r in g["rows"]})))
            old = c.execute("SELECT id FROM txn WHERE key=?", (key,)).fetchone()
            if old:
                tid = old[0]
                _fill(c, tid, lead=vals["lead"])
                _refresh(c, tid, vals, by, stats)
                stats["existing"] += 1
            else:
                cols = ["key", "created", "updated"] + list(vals)
                tid = c.execute(f"INSERT INTO txn({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                                [key, H.now(), H.now()] + list(vals.values())).lastrowid
                c.execute("INSERT INTO log(ts,by,txn_id,what,detail) VALUES(?,?,?,?,?)",
                          (H.now(), by, tid, "Imported from BIP file", f"{status}" + (f" - {reason}" if reason else "")))
                _snapshot(c, tid, vals)
                stats["added"] += 1
                stats["parked"] += 0 if active else 1
            # ----- counterparties named in the file
            epc_text = clean_ml(sf.field_text(f.get("epc", "")))
            fin = epc_text.lower().startswith("finalis")
            for nm in split_names(epc_text):
                _link(c, tid, _party(c, nm, "EPC", country), "Appointed" if fin else "Shortlisted", "EPC mapping in the BIP file")
                stats["links"] += 1
            for r in g["rows"]:
                for p in r.get("parties", []):
                    st = "Appointed" if re.search(r"signed", clean(p.get("status")), re.I) and not re.search(r"not|un|pending", clean(p.get("status")), re.I) else "Identified"
                    for nm in split_names(p.get("name")):
                        pt = party_type(p.get("kind", ""), p.get("role", ""), nm)
                        if pt:
                            _link(c, tid, _party(c, nm, pt, country), st, clean(p.get("role")))
                            stats["links"] += 1
                for b in r.get("banks", []):
                    for nm in split_names(b):
                        _link(c, tid, _party(c, nm, "ECA" if ECA_RX.search(nm) else "Bank / Lender", country), "Identified", "Bank named in the BIP file")
                        stats["links"] += 1
            for m in ECA_RX.finditer(text):
                nm = m.group(1).upper() if len(m.group(1)) <= 5 else m.group(1)
                _link(c, tid, _party(c, nm, "ECA"), "Identified", "Mentioned in the BIP notes")
            # ----- readiness checklist from the structured columns (only what the file clearly says)
            if re.search(r"submitted", clean(f.get("eoi")), re.I):
                _check(c, tid, "LoI / EoI submitted", "Yes", clean(f.get("eoi_fb")))
            if re.search(r"sign", clean(f.get("mou")), re.I):
                _check(c, tid, "MoU with owner", "Yes", clean(f.get("mou")))
            if re.search(r"submitted", clean(f.get("proposal")), re.I):
                _check(c, tid, "Project proposal submitted", "Yes", clean(f.get("proposal_fb")))
            for item, rx in FACT_RX.items():
                if rx.search(text):
                    _check(c, tid, item, "Yes", "From the BIP notes - please verify")
        stats["parties"] = c.execute("SELECT COUNT(*) FROM party").fetchone()[0] - n_party0
        # ----- deck projects the workbook did not match: still part of the pipeline
        matched = set(dm)
        for p in deck:
            if p["id"] in matched or c.execute("SELECT 1 FROM txn WHERE deck_key=?", (p["id"],)).fetchone():
                continue
            key = "deck-" + p["id"]
            if c.execute("SELECT 1 FROM txn WHERE key=?", (key,)).fetchone():
                continue
            st = "On hold" if p["category"] == "Hold" else "Preliminary"
            c.execute("INSERT INTO txn(key,name,country,sector,structure,client_type,status,ext_category,lead,introduced,deck_key,active,origin,created,updated,reason) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (key, p["name"], p.get("country", ""), p.get("sector", ""), p.get("model", ""), "To confirm", st, p["category"],
                       T.lead_for_country(p.get("country", "")) or "", p.get("source", ""), p["id"], 0 if st == "On hold" else 1, "Deck", H.now(), H.now(),
                       "On hold in the deck" if st == "On hold" else ""))
            stats["added"] += 1
        H._normalize(c)
        H._bump(c)
        c.commit()
    finally:
        c.close()
    return stats


# --------------------------------------------------------------------------- Madagascar call notes (Stamin / Oman)
MADAGASCAR = [
    dict(hint="Transmission", name="JIRAMA - Transmission & Distribution package (Oman-funded)", sector="Power", structure="EPC", value="USD 1.8 Bn (transmission 1.3 Bn + distribution 0.5 Bn)",
         client_type="SOE", status="P2", counterparty="JIRAMA", procurement="Negotiated",
         summary="Energy partnership with Oman investment funds / capital and JIRAMA, implemented under an EPC + services model. Total USD 1.8 Bn: transmission USD 1.3 Bn, distribution USD 0.5 Bn. Full details (km, substations) already shared.",
         next_steps="Get cash-flow security structure / assignment of industrial cash flows from JIRAMA (meeting next week). Blend LoI already shared.",
         epcs=[("Tecmon", "Shortlisted", "Innovus went on a call with Tecmon - shortlisted")],
         inv=[("Oman Investment Authority", "In discussion", "MoU signed with Madagascar")], bank=[("Oman Development Bank", "In discussion", "Lead financier and PPP participant")],
         chk=[("Technical documents", "Yes", "Km / substation details received"), ("LoI / EoI submitted", "Yes", "Blend LoI shared")]),
    dict(hint="JIRAMA IPP", name="JIRAMA - Solar / IPP list (55 received, 16 shortlisted, 14-75 MW each)", sector="Power", structure="IPP", value="To be confirmed",
         client_type="SOE", status="Preliminary", counterparty="JIRAMA", procurement="To confirm",
         summary="JIRAMA sent a list of 55 projects; 16 shortlisted (14-75 MW each). Some already contracted or identified - Blend can come in as EPC behind the developer or partner an EPC. Tariff and JIRAMA's financial health are the key issues.",
         next_steps="Discuss how JIRAMA can secure us (assignment of industrial cash flows) - meeting next week.",
         epcs=[("77 Construction", "Shortlisted", "Madagascar EPC shortlist (call notes) - project allocation to confirm")]),
    dict(hint="Two additional", name="JIRAMA - two additional transmission lines (can be split)", sector="Power", structure="EPC", value="To be confirmed",
         client_type="SOE", status="Preliminary", counterparty="JIRAMA", summary="JIRAMA offered two more transmission lines; the scope can be split.",
         next_steps="Ask JIRAMA for additional information and the split.", epcs=[("Tecmon", "Shortlisted", "")]),
    dict(hint="Road", name="Roads - Ministry of Public Works (5-6 large projects) / 32-road list", sector="Transport", structure="PPP", value="32 roads ~ USD 6 Bn (9 ready)",
         client_type="Government", status="P2", counterparty="Ministry of Public Works",
         summary="Broader list of 32 road projects, ~USD 6 Bn in total, 9 ready. The Ministry of Public Works gave 5-6 large projects (some with tunnels). Interest expressed; EOI submitted via VSG, VSG LoI given. Feedback expected.",
         next_steps="Await feedback on the EOI; pick one project with a political / tunnel angle.",
         epcs=[("VSG", "Shortlisted", "EOI / LoI given via VSG"), ("Omatapalo", "Shortlisted", "Madagascar EPC shortlist - allocation to confirm")],
         chk=[("LoI / EoI submitted", "Yes", "Via VSG")]),
    dict(hint="Education", name="Education - Ministry of National Education (9 projects, ~USD 90 Mn)", sector="Education", structure="EPC+F", value="USD ~90 Mn",
         client_type="Government", status="P2", counterparty="Ministry of National Education",
         summary="9 projects worth about USD 90 Mn: refurbishment, furniture and supplies. EOI already submitted via VSG.",
         next_steps="Follow-up meeting next week.", epcs=[("VSG", "Shortlisted", "EOI submitted via VSG")], chk=[("LoI / EoI submitted", "Yes", "Via VSG")]),
    dict(hint="Hospital", name="Health - Ministry of Health (small package)", sector="Health", structure="", value="USD 2-3 Mn", client_type="Government", status="Preliminary",
         counterparty="Ministry of Health", summary="Small package of about USD 2-3 Mn. Preference shifted to priority projects that are not yet 'ready'.",
         next_steps="Details already requested; meeting next week."),
    dict(hint="Water", name="Water - Ministry of Water (about USD 13.5 Mn)", sector="Water", structure="EPC+F", value="USD ~13.5 Mn", client_type="Government", status="Preliminary",
         counterparty="Ministry of Water", summary="One project of about USD 13.5 Mn (SMC, EPC-FP structure). More projects requested from the ministry.",
         next_steps="Additional projects requested.", epcs=[("SMC", "Shortlisted", "SMC offer")]),
    dict(hint="Port", name="Toamasina Port - 8-phase terminal development", sector="Transport", structure="PPP", value="To be confirmed", client_type="SOE", status="P2",
         counterparty="Toamasina Port (CEO) / SPAT", procurement="Both",
         summary="Largest port. Terminals / facilities in 8 phases: 2 on a negotiated basis, 6 by bidding. Port CEO open to working together; supplies also discussed. EOI submitted via VSG.",
         next_steps="Settle bidding vs negotiated approach for the phases.", epcs=[("VSG", "Shortlisted", "EOI submitted via VSG")],
         bank=[("AFG Bank", "In discussion", "Ready to fund (noted for 5 projects)")], chk=[("LoI / EoI submitted", "Yes", "Via VSG")]),
    dict(hint=None, name="Gold mining - 2 open-pit projects (~USD 500 Mn)", sector="Mining", structure="PPP", value="USD ~500 Mn", client_type="Private", status="Preliminary",
         counterparty="", summary="Two open-pit gold projects, ~USD 500 Mn, 15-year mine life, 50-100k oz/year each (up to ~200k oz/year combined). Reserve / value details and documents awaited.",
         next_steps="Follow up pending mining documents.", inv=[("Oman Investment Authority", "In discussion", "MoU signed with Madagascar")],
         bank=[("Oman Development Bank", "In discussion", "Lead financier and PPP participant")]),
    dict(hint=None, name="Airport projects", sector="Transport", structure="", value="To be confirmed", client_type="To confirm", status="Preliminary",
         summary="Airport projects are already advancing.", next_steps="Get details."),
    dict(hint=None, name="Oil storage facility (floating storage acceptable)", sector="Oil & Gas", structure="", value="To be confirmed", client_type="To confirm", status="Preliminary",
         summary="The country has no storage of its own and uses private facilities. Long-term plan for a storage facility; floating storage (a ship at the port) is acceptable meanwhile.",
         next_steps="Confirm requirement and capacity."),
]
MADAGASCAR_CONTEXT = ("Country context: under an IMF ECF programme, so borrowing (especially non-concessional) is capped - PPP structures are strongly preferred; "
                      "pure EPC / EPS financing is difficult.")


def import_madagascar(by: str = "Import") -> dict:
    c = H.connect()
    added = merged = 0
    try:
        mada = [dict(r) for r in c.execute("SELECT * FROM txn WHERE lower(country)='madagascar'")]
        for e in MADAGASCAR:
            hit = next((m for m in mada if e["hint"] and e["hint"].lower() in m["name"].lower()), None) if e["hint"] else None
            if not hit:
                hit = next((m for m in mada if m["name"] == e["name"]), None)
            vals = {k: e[k] for k in ("sector", "structure", "value", "client_type", "status", "counterparty", "summary", "next_steps", "procurement") if e.get(k)}
            vals["summary"] = (vals.get("summary", "") + "\n" + MADAGASCAR_CONTEXT).strip()
            if hit:
                tid = hit["id"]
                sets = dict(vals, name=e["name"], active=1, reason="", introduced=hit["introduced"] or "Stamen / Brian", updated=H.now())
                if hit["status"] == "On hold" and e["status"] != "On hold":
                    sets["status"] = e["status"]
                c.execute("UPDATE txn SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [tid])
                c.execute("INSERT INTO log(ts,by,txn_id,what,detail) VALUES(?,?,?,?,?)", (H.now(), by, tid, "Updated from Madagascar call notes", e["name"]))
                merged += 1
            else:
                key = "mada-" + re.sub(r"[^a-z0-9]+", "-", e["name"].lower())[:70]
                if c.execute("SELECT 1 FROM txn WHERE key=?", (key,)).fetchone():
                    continue
                cols = dict(key=key, name=e["name"], country="Madagascar", lead=T.lead_for_country("Madagascar") or "", introduced="Stamen / Brian",
                            origin="Madagascar call notes", created=H.now(), updated=H.now(), active=1, **vals)
                tid = c.execute(f"INSERT INTO txn({','.join(cols)}) VALUES({','.join('?' * len(cols))})", list(cols.values())).lastrowid
                c.execute("INSERT INTO log(ts,by,txn_id,what,detail) VALUES(?,?,?,?,?)", (H.now(), by, tid, "Added from Madagascar call notes", e["name"]))
                added += 1
            for typ, key_ in (("EPC", "epcs"), ("Investor", "inv"), ("Bank / Lender", "bank")):
                for nm, st, rem in e.get(key_, []):
                    pid = _party(c, nm, typ, "Madagascar")
                    c.execute("INSERT INTO link(txn_id,party_id,status,remark,updated,by) VALUES(?,?,?,?,?,?) ON CONFLICT(txn_id,party_id) DO UPDATE SET "
                              "status=excluded.status, remark=excluded.remark, updated=excluded.updated, by=excluded.by", (tid, pid, st, rem, H.now(), by))
            for item, st, rem in e.get("chk", []):
                c.execute("INSERT INTO chk(txn_id,item,state,remark,updated) VALUES(?,?,?,?,?) ON CONFLICT(txn_id,item) DO UPDATE SET state=excluded.state, remark=excluded.remark",
                          (tid, item, st, rem, H.now()))
        H._normalize(c)
        H._bump(c)
        c.commit()
    finally:
        c.close()
    return {"added": added, "merged": merged}


if __name__ == "__main__":
    f = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "BIP - Captive Projects.xlsx"
    print(import_bip(f))
    print(import_madagascar())
