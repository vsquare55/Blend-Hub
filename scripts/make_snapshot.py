"""One self-contained HTML file with the whole Hub (same screens as the live Hub, read-only): opens by double-click in any browser, no Python, works offline,
on a Mac too. Data = what the Hub holds right now; make a new file whenever the data has changed."""
from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

import hubdb as H

WEB = Path(__file__).parent / "hubweb"
SHIM = r"""<script>
(function () {
  const SNAP = JSON.parse(document.getElementById("snapdata").textContent);
  try { if (!localStorage.getItem("hubUser")) localStorage.setItem("hubUser", "Guest"); } catch (e) {}
  const jr = (o, s) => new Response(JSON.stringify(o), {status: s || 200, headers: {"Content-Type": "application/json"}});
  function view(hide) {
    const h = (hide === "1" ? "PH" : hide || "").toUpperCase(), out = [];
    if (h.includes("P")) out.push("Preliminary"); if (h.includes("H")) out.push("On hold");
    if (!h) return SNAP;
    const nn = new Set(SNAP.needs.filter(n => n.type === "EPC" && n.state === "Not needed").map(n => n.txn_id));
    const gone = new Set(SNAP.txns.filter(t => out.includes(t.status) || (h.includes("F") && t.structure === "Financing only") || (h.includes("N") && nn.has(t.id))).map(t => t.id));
    const txns = SNAP.txns.filter(t => !gone.has(t.id)), keep = new Set(txns.map(t => t.id)), mine = r => keep.has(r.txn_id);
    const links = SNAP.links.filter(mine), used = new Set(links.map(l => l.party_id)), anywhere = new Set(SNAP.links.map(l => l.party_id));
    return Object.assign({}, SNAP, {txns, hidden: true, links, parties: SNAP.parties.filter(p => used.has(p.id) || !anywhere.has(p.id)), needs: SNAP.needs.filter(mine), chk: SNAP.chk.filter(mine),
      comments: SNAP.comments.filter(mine), actions: SNAP.actions.filter(mine), meetings: SNAP.meetings.filter(mine), trash: SNAP.trash.filter(t => !out.includes(t.status)), undo: null,
      enums: Object.assign({}, SNAP.enums, {statuses: SNAP.enums.statuses.filter(s => !out.includes(s))})});
  }
  const real = window.fetch.bind(window);
  window.fetch = async (u, o) => {
    u = String(u); const p = u.split("?")[0];
    if (p === "/api/all") return jr(Object.assign({}, view(o && o.headers && o.headers["X-Hide"] || ""), {lock: {mine: false, holder: "snapshot", user: "Guest"}, default_user: "Guest"}));
    if (p === "/api/rev") return jr({rev: SNAP.rev, lock: {mine: false, holder: "snapshot", user: "Guest"}, ver: "snap"});
    if (p === "/api/history") { const id = new URLSearchParams(u.split("?")[1]).get("txn"); return jr(SNAP.hist[id] || []); }
    if (p === "/api/backups" || p === "/api/changes") return jr([]);
    if (p === "/api/print/cols") return jr({});
    return jr({error: "This is a read-only copy for viewing. Changes, printing and exports are done in the live Hub."}, 400);
  };
})();
</script>"""
BANNER_OLD = '<div class="banner"><div>🔒 <b>${esc(lock.holder)}</b> is editing right now - you can read everything but not change it.</div><button class="btn sm" data-act="take">Take over editing</button></div>'


def build(dest: Path) -> Path:
    snap = H.snapshot("")
    snap["hist"] = {t["id"]: H.history(t["id"], 60) for t in snap["txns"]}
    stamp = datetime.now().strftime("%d %b %Y %H:%M")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert BANNER_OLD in html, "banner text changed - update make_snapshot.py"
    html = html.replace(BANNER_OLD, f'<div class="banner"><div>📷 <b>Snapshot of {stamp}</b> - a read-only copy of the Blend Hub: browse, filter, sort and open everything; changes, printing and exports are done in the live Hub.</div></div>')
    logo = "data:image/png;base64," + base64.b64encode((WEB / "logo.png").read_bytes()).decode()
    html = html.replace('href="logo.png"', f'href="{logo}"').replace('src="logo.png"', f'src="{logo}"')
    data = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("<script>", f'<script id="snapdata" type="application/json">{data}</script>\n{SHIM}\n<script>', 1)
    i = html.rindex("</script>") + len("</script>")  # after the app's own script: Print / PDF buttons use the browser's print dialog (Save as PDF there)
    html = html[:i] + '\n<script>printCentre = async function () { toast("In the print window choose \\u201cSave as PDF\\u201d (or a printer). The filters you applied are printed at the top."); setTimeout(() => window.print(), 600); };</script>' + html[i:]
    html = html.replace("<title>", f"<title>Snapshot {stamp} - ", 1) if "<title>" in html else html
    dest.write_text(html, encoding="utf-8")
    return dest


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else H.ROOT / f"Blend_Hub_Snapshot_{datetime.now():%Y-%m-%d}.html"
    print("Written:", build(out), f"({out.stat().st_size // 1024} KB)")
