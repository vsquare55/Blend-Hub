#!/usr/bin/env python3
"""Blend Hub - the whole Hub as ONE Excel workbook, and the way back.

export_workbook(): a tidy, readable version of the BIP file (INDEX, ALL, one tab per country, counterparties, mappings, readiness,
meetings, actions, comments, change log) + hidden data sheets (_txn, _party, _link ...) that hold every table of the database 1:1.
restore_workbook(): reads those data sheets and rebuilds the whole database from them (a copy of the current database is kept first).
excel_backup(): the automatic Excel copy (data/backups/excel), same rules as the .db backups.
"""
from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import hubdb as H
import hubprint as P

MAGIC = "Blend Hub backup v1"
NAVY, GREY = "16213A", "F1F3F8"
XL_BACKUPS = H.BACKUPS / "excel"
ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LAB = {"Yes": "Yes", "In progress": "In progress", "No": "Not yet", "N.A.": "N.A.", "": ""}


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return ILLEGAL.sub("", v)[:32000]
    return v


def _sheet_name(wb, name: str) -> str:
    base = re.sub(r"[\[\]\*\?/\\:]", " ", " ".join(str(name).split())).strip()[:28] or "Sheet"
    n, i = base, 1
    while n.lower() in {s.title.lower() for s in wb.worksheets}:
        i += 1
        n = f"{base[:25]} {i}"
    return n


def _write(ws, head: List[str], rows: List[list], widths: Optional[dict] = None, wrap: tuple = ()):
    ws.append(head)
    for r in rows:
        ws.append([_cell(x) for x in r])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "C2" if len(head) > 3 else "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(head))}{max(len(rows) + 1, 2)}"
    for i, h in enumerate(head, 1):
        w = (widths or {}).get(h) or min(max(len(str(h)) + 3, 12), 22)
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=c.column_letter in wrap)


# ------------------------------------------------------------------------------------------------ readable sheets
TXN_HEAD = ["#", "Project", "Country", "Sector", "Structure", "Value (EUR mn)", "Client type", "Client", "Status", "Active", "Priority", "Owner", "Sub-owner", "Procurement", "Source",
            "EPCs", "Banks / lenders", "ECAs", "Investors", "Insurers", "Term sheet received (banks)",
            "Meeting", "Meeting date", "Meeting with", "No. of meetings", "LoI / EoI", "LoI / EoI date", "LoI / EoI response", "Information", "Review outcome", "Review date",
            "Received", "Readiness done", "Open actions", "Next steps", "Summary", "Last updated"]
TXN_W = {"Project": 46, "Summary": 70, "Next steps": 55, "EPCs": 36, "Banks / lenders": 34, "ECAs": 24, "Investors": 28, "Insurers": 22, "Client": 28, "Source": 22,
         "Term sheet received (banks)": 30, "Meeting with": 26, "Country": 16, "Sector": 16}


def _names(c, t, ty):
    ls = [l for l in c.ix["L"].get(t["id"], []) if l["p"]["type"] == ty and l["status"] != "Dropped"]
    return "; ".join(l["p"]["name"] + ("" if l["status"] == "Shortlisted" else f" ({l['status']})") for l in ls)


def _term(c, t):
    ls = [l for l in c.ix["L"].get(t["id"], []) if l["p"]["type"] in ("Bank / Lender", "ECA") and l["status"] in ("Term sheet received", "Appointed")]
    return "; ".join(l["p"]["name"] for l in ls)


def _txn_row(c, t, n, nopen):
    ck = c.ix["C"].get(t["id"], {})
    items_all = list(H.CHECK_ITEMS) + [k for k in ck if k not in H.CHECK_ITEMS]
    done = sum(1 for i in items_all if (ck.get(i) or {}).get("state") in ("Yes", "N.A."))
    loi_txt = {"Yes": "Sent", "In progress": "In progress", "N.A.": "Not applicable"}.get(P._chk(c, t, "LoI / EoI submitted") or ("Yes" if t.get("loi_sent") == "Yes" else ""), "Not yet")
    return [n, t["name"], t["country"], t["sector"], t["structure"], t["vn"], t["client_type"], t["counterparty"], t["status"], "Yes" if t["active"] else "On hold", t.get("priority"), t["lead"], t.get("sub_lead") or "",
            t["procurement"], t["introduced"], _names(c, t, "EPC"), _names(c, t, "Bank / Lender"), _names(c, t, "ECA"), _names(c, t, "Investor"), _names(c, t, "Insurer"), _term(c, t),
            t.get("meeting_status"), t.get("meeting_date"), t.get("meeting_with"), len(c.ix["M"].get(t["id"], [])), loi_txt, t.get("loi_date"), t.get("loi_response"), P._info_state(c, t),
            t.get("review_outcome"), t.get("review_date"), t.get("received_date") or (t.get("created") or "")[:10], f"{done}/{len(items_all)}", nopen.get(t["id"], 0),
            t["next_steps"], t["summary"], t.get("updated")]


def _readable(wb, snap: dict):
    ids = [t["id"] for t in snap["txns"]]
    c = P.Ctx(snap, ids, {})
    nopen = {}
    for a in snap["actions"]:
        if not a["done"]:
            nopen[a["txn_id"]] = nopen.get(a["txn_id"], 0) + 1
    ts = sorted(c.ts, key=lambda t: (t["country"].lower(), H.STATUSES.index(t["status"]) if t["status"] in H.STATUSES else 9, t["name"].lower()))
    # --- INDEX
    ws = wb.create_sheet("INDEX")
    by_c = {}
    for t in ts:
        by_c.setdefault(t["country"] or "(no country)", []).append(t)
    rows = []
    for ctry, a in sorted(by_c.items(), key=lambda kv: kv[0].lower()):
        rows.append([ctry, len(a), sum(1 for t in a if t["active"]), sum(1 for t in a if t["status"] == "P1"), sum(1 for t in a if t["status"] == "P2"), sum(1 for t in a if t["status"] == "Tie-up done"),
                     round(sum(t["vn"] or 0 for t in a)), ", ".join(sorted({t["lead"] for t in a if t["lead"]})), ", ".join(sorted({t["sector"] for t in a if t["sector"]}))[:200]])
    rows.append(["TOTAL", len(ts), sum(1 for t in ts if t["active"]), sum(1 for t in ts if t["status"] == "P1"), sum(1 for t in ts if t["status"] == "P2"),
                 sum(1 for t in ts if t["status"] == "Tie-up done"), round(sum(t["vn"] or 0 for t in ts)), "", ""])
    _write(ws, ["Country", "Transactions", "Active", "P1", "P2", "Tie-up done", "Value (EUR mn)", "Owner", "Sectors"], rows, {"Country": 24, "Sectors": 60}, ("Sectors",))
    ws.freeze_panes = "A2"
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    # --- ALL + one tab per country
    ws = wb.create_sheet("ALL")
    _write(ws, TXN_HEAD, [_txn_row(c, t, i + 1, nopen) for i, t in enumerate(ts)], TXN_W, ("Project", "Summary", "Next steps", "EPCs", "Banks / lenders", "Investors"))
    for ctry, a in sorted(by_c.items(), key=lambda kv: kv[0].lower()):
        ws = wb.create_sheet(_sheet_name(wb, ctry.upper()))
        _write(ws, TXN_HEAD, [_txn_row(c, t, i + 1, nopen) for i, t in enumerate(a)], TXN_W, ("Project", "Summary", "Next steps", "EPCs", "Banks / lenders", "Investors"))
    # --- readiness / milestones
    head, rws = P.milestone_rows(c)
    ws = wb.create_sheet("READINESS")
    _write(ws, head, rws, {"Transaction": 46}, ())
    # --- counterparties / mappings
    ws = wb.create_sheet("COUNTERPARTIES")
    cnt = {}
    for l in snap["links"]:
        cnt[l["party_id"]] = cnt.get(l["party_id"], 0) + 1
    _write(ws, ["Name", "Type", "Country", "Transactions", "Notes"], [[p["name"], p["type"], p["country"], cnt.get(p["id"], 0), p["notes"]] for p in sorted(snap["parties"], key=lambda p: (p["type"], p["name"].lower()))],
           {"Name": 36, "Notes": 60}, ("Notes",))
    ws = wb.create_sheet("MAPPINGS")
    pb, tb = {p["id"]: p for p in snap["parties"]}, {t["id"]: t for t in snap["txns"]}
    mp = [[tb[l["txn_id"]]["country"], tb[l["txn_id"]]["name"], pb[l["party_id"]]["type"], pb[l["party_id"]]["name"], l["status"], l.get("remark")] for l in snap["links"] if l["txn_id"] in tb and l["party_id"] in pb]
    _write(ws, ["Country", "Project", "Type", "Counterparty", "Status", "Remark"], sorted(mp, key=lambda r: (r[0].lower(), r[1].lower(), r[2])), {"Project": 46, "Counterparty": 32, "Remark": 50})
    # --- meetings / actions / comments / log
    ws = wb.create_sheet("MEETINGS")
    _write(ws, ["Country", "Project", "Date", "With whom", "Status", "Notes", "By"],
           [[tb[m["txn_id"]]["country"], tb[m["txn_id"]]["name"], m["day"], m["who"], m["status"], m["notes"], m["by"]] for m in sorted(snap.get("meetings", []), key=lambda m: m.get("day") or "", reverse=True) if m["txn_id"] in tb],
           {"Project": 46, "With whom": 28, "Notes": 80}, ("Notes",))
    ws = wb.create_sheet("ACTIONS")
    _write(ws, ["Country", "Project", "Action", "Owner", "Due", "Done", "Automatic"],
           [[tb[a["txn_id"]]["country"], tb[a["txn_id"]]["name"], a["text"], a["owner"], a["due"], "Yes" if a["done"] else "", "Yes" if a.get("auto") else ""] for a in sorted(snap["actions"], key=lambda a: (a["done"], a["due"] or "9999")) if a["txn_id"] in tb],
           {"Project": 46, "Action": 70}, ("Action",))
    ws = wb.create_sheet("COMMENTS")
    _write(ws, ["Country", "Project", "Date", "By", "Comment", "Management"],
           [[tb[m["txn_id"]]["country"], tb[m["txn_id"]]["name"], m["day"], m["by"], m["text"], "Yes" if m.get("kind") else ""] for m in sorted(snap["comments"], key=lambda m: m["day"], reverse=True) if m["txn_id"] in tb],
           {"Project": 46, "Comment": 90}, ("Comment",))


# ------------------------------------------------------------------------------------------------ data sheets (the real backup)
def _tables(c) -> List[str]:
    return [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('op','jr') ORDER BY name")]


def _data(wb, c):
    for tb in _tables(c):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({tb})")]
        ws = wb.create_sheet("_" + tb)
        ws.append(cols)
        for r in c.execute(f"SELECT * FROM {tb}"):
            ws.append([_cell(x) for x in r])
        ws.sheet_state = "hidden"


def export_workbook(dest: Path) -> Path:
    snap = H.snapshot()
    c = H.connect()
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "README"
        n = c.execute("SELECT COUNT(*) FROM txn WHERE deleted=0").fetchone()[0]
        for line in [
            ["Blend Hub - full workbook", ""],
            ["Made", datetime.now().strftime("%d %b %Y %H:%M")],
            ["Transactions", n],
            ["", ""],
            ["INDEX / ALL / country tabs", "Readable version of the pipeline (like the BIP file). Safe to filter, sort, print or share."],
            ["READINESS / COUNTERPARTIES / MAPPINGS / MEETINGS / ACTIONS / COMMENTS", "Same data, one topic per tab."],
            ["Hidden tabs starting with _", "The complete database, table by table. THIS is what 'Restore from Excel' reads. Do not edit, rename or delete them."],
            ["", ""],
            ["Restore", "Hub > Settings & data > Restore from Excel > pick this file. Everything (transactions, counterparties, mappings, readiness, meetings, actions, comments, history) is rebuilt exactly as it was."],
            ["Editing here", "Changes typed into the readable tabs are NOT read back. To change data use the Hub (or the BIP import for the original file)."],
        ]:
            ws.append(line)
        ws["A1"].font = Font(bold=True, size=14)
        ws.column_dimensions["A"].width = 44
        ws.column_dimensions["B"].width = 110
        for r in ws.iter_rows(min_row=1):
            for x in r:
                x.alignment = Alignment(wrap_text=True, vertical="top")
        _readable(wb, snap)
        _data(wb, c)
        wm = wb.create_sheet("_backup_info")
        wm.append(["magic", "made", "transactions", "tables"])
        wm.append([MAGIC, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), n, ",".join(_tables(c))])
        wm.sheet_state = "hidden"
        dest.parent.mkdir(parents=True, exist_ok=True)
        wb.save(dest)
        return dest
    finally:
        c.close()


# ------------------------------------------------------------------------------------------------ automatic Excel backups
def excel_backup(keep: int = 30, every_hours: float = 12, force: bool = False) -> Optional[Path]:
    XL_BACKUPS.mkdir(parents=True, exist_ok=True)
    files = sorted(XL_BACKUPS.glob("Blend_Hub_*.xlsx"))
    if not force and files and time.time() - files[-1].stat().st_mtime < every_hours * 3600:
        return None
    dst = XL_BACKUPS / f"Blend_Hub_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    export_workbook(dst)
    for old in sorted(XL_BACKUPS.glob("Blend_Hub_*.xlsx"))[:-keep]:
        old.unlink()
    return dst


def list_excel_backups() -> List[dict]:
    return [{"name": p.name, "mb": round(p.stat().st_size / 1e6, 1)} for p in sorted(XL_BACKUPS.glob("Blend_Hub_*.xlsx"), reverse=True)]


# ------------------------------------------------------------------------------------------------ restore
def _check_workbook(wb) -> dict:
    names = set(wb.sheetnames)
    if "_backup_info" not in names:
        raise H.HubError("This is not a Blend Hub backup workbook (the hidden _backup_info tab is missing). Use the BIP import for the original BIP file.")
    info = [r for r in wb["_backup_info"].iter_rows(min_row=2, max_row=2, values_only=True)][0]
    if info[0] != MAGIC:
        raise H.HubError("This backup was made by a different version of the Hub.")
    need = {"_txn", "_party", "_link", "_chk", "_meta"}
    if need - names:
        raise H.HubError("The backup is incomplete - missing: " + ", ".join(sorted(need - names)))
    return {"made": info[1], "transactions": info[2], "tables": [t for t in str(info[3]).split(",") if t]}


def restore_workbook(path: Path, by: str = "Restore") -> dict:
    wb = load_workbook(path, read_only=True, data_only=True)
    info = _check_workbook(wb)
    data = {}
    for tb in info["tables"]:
        if "_" + tb not in wb.sheetnames:
            continue
        rows = list(wb["_" + tb].iter_rows(values_only=True))
        if rows:
            data[tb] = (list(rows[0]), [r for r in rows[1:] if any(x not in (None, "") for x in r)])
    wb.close()
    if not data.get("txn") or not data["txn"][1]:
        raise H.HubError("The backup holds no transactions - nothing was changed.")
    H.backup(force=True)  # the current database is kept first

    def run(c):
        counts = {}
        for tb, (cols, rows) in data.items():
            have = {r[1]: (r[2] or "").upper() for r in c.execute(f"PRAGMA table_info({tb})")}
            if not have:
                continue
            use = [(i, k) for i, k in enumerate(cols) if k in have]
            c.execute(f"DELETE FROM {tb}")
            for r in rows:
                vals = []
                for i, k in use:
                    v = r[i] if i < len(r) else None
                    if "INT" in have[k]:
                        v = int(float(v)) if v not in (None, "") else None
                    elif have[k] in ("", "TEXT") or "CHAR" in have[k]:
                        v = "" if v is None else (str(int(v)) if isinstance(v, float) and v == int(v) else str(v))
                    vals.append(v)
                c.execute(f"INSERT OR REPLACE INTO {tb}({','.join(k for _, k in use)}) VALUES({','.join('?' * len(use))})", vals)
            counts[tb] = len(rows)
        c.execute("INSERT INTO log(ts,by,txn_id,what,detail) VALUES(?,?,?,?,?)", (H.now(), by, None, "Restored from Excel backup", f"made {info['made']}, {counts.get('txn', 0)} transactions"))
        return counts
    counts = H._tx(run, journal=False)
    return {"made": info["made"], "counts": counts}
