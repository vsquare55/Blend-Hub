"""One self-contained, EDITABLE HTML file with the whole Hub (same screens as the live Hub). The data lives in the browser (saved automatically); 'Save as Excel' / 'Open Excel'
use the same workbook as the live Hub, so the two stay in step through Excel. Works by double-click on a Mac or any PC - no Python, no install, no internet."""
from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

import hubdb as H

HERE = Path(__file__).parent
WEB = HERE / "hubweb"
STYLE = """<style>
#editbar{position:fixed;right:14px;bottom:12px;z-index:90;display:flex;gap:8px;align-items:center;background:#1B2F5B;color:#fff;border-radius:99px;padding:6px 8px 6px 14px;box-shadow:0 6px 24px #0004;font-size:12.5px}
#editbar b{font-weight:700}#editbar span{background:#fff;border-radius:99px;padding:2px 10px;font-weight:650;font-size:12px}
#editbar button{border:0;border-radius:99px;padding:6px 12px;font-weight:650;cursor:pointer;background:#F4A21E;color:#1B2F5B}#editbar button#eb_open{background:#fff}#editbar button#eb_reset{background:transparent;color:#fff;border:1px solid #ffffff66}
@media print{#editbar{display:none!important}}
@media (max-width:900px){#editbar{left:8px;right:8px;flex-wrap:wrap;border-radius:14px}}
</style>"""


def raw_tables() -> dict:
    c = H.connect()
    try:
        out = {}
        for tb in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]:
            info = list(c.execute(f"PRAGMA table_info({tb})"))
            cols = [r[1] for r in info]
            out[tb] = {"cols": cols, "types": {r[1]: ("INT" if "INT" in (r[2] or "").upper() else "TEXT") for r in info}, "defaults": {r[1]: r[4] for r in info},
                       "rows": [[(None if v is None else v) for v in row] for row in c.execute(f"SELECT * FROM {tb}")]}
        return out
    finally:
        c.close()


def build(dest: Path) -> Path:
    snap = H.snapshot("")
    boot = {"id": datetime.now().strftime("%Y%m%d%H%M%S"), "tables": raw_tables(), "enums": snap["enums"], "pms": snap["pms"], "txn_fields": H.TXN_FIELDS,
            "enum_checks": H._ENUM, "meeting_kinds": H.MEETING_KINDS, "party_types": H.PARTY_TYPES}
    html = (WEB / "index.html").read_text(encoding="utf-8")
    logo = "data:image/png;base64," + base64.b64encode((WEB / "logo.png").read_bytes()).decode()
    html = html.replace('href="logo.png"', f'href="{logo}"').replace('src="logo.png"', f'src="{logo}"')
    data = json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")
    lib = (HERE / "vendor" / "xlsx.full.min.js").read_text(encoding="utf-8").replace("</script>", "<\\/script>")
    engine = (HERE / "editable_engine.js").read_text(encoding="utf-8")
    inject = f'<script id="hubdata" type="application/json">{data}</script>\n<script>{lib}</script>\n<script>{engine}</script>\n<script>'
    html = html.replace("<script>", inject, 1)
    html = html.replace("</head>", STYLE + "\n</head>", 1)
    stamp = datetime.now().strftime("%d %b %Y %H:%M")
    html = html.replace("<title>", f"<title>Editable {stamp} - ", 1) if "<title>" in html else html
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else H.ROOT / "Editable HTML" / "Blend_Hub_Editable.html"
    print("Written:", build(out), f"({out.stat().st_size // 1024} KB)")
