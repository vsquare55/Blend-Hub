#!/usr/bin/env python3
"""
Sources (origination) of projects.

A project's "Source / Origination" is the person / minister / partner / influential contact who brought it in.
Several sources are separated by "/" or ";"  (e.g. "Walter / Yann").  The 'Sources' sheet of the registry lists every source once,
with a role/description, a type and live counts, so the app can filter and report by source.
SOURCES NEVER APPEAR IN GENERATED DECKS - they live only in the registry and the app.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Tuple

SHEET = "Sources"
HEADERS = ["Sr. No.", "Source", "Role / Description", "Type", "Country", "Projects", "Project list"]
TYPES = ["Minister / Government", "Local partner", "Developer", "Adviser / Consultant", "Bank / Financier", "EPC partner", "Other"]
_SPLIT = re.compile(r"\s*[/;\n]\s*")
NO_SOURCE = "(no source)"


def split_sources(text) -> List[str]:
    """'Walter / Yann' -> ['Walter', 'Yann'] (empty parts dropped, duplicates removed, order kept)."""
    out, seen = [], set()
    for t in _SPLIT.split(str(text or "")):
        t = " ".join(t.split())
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def join_sources(items: List[str]) -> str:
    return " / ".join(items)


def canon(text, known: Dict[str, str]) -> str:
    """Use the spelling/case already in the Sources sheet for every source typed in a project row."""
    return join_sources([known.get(t.lower(), t) for t in split_sources(text)])


def read(wb) -> List[dict]:
    if SHEET not in wb.sheetnames:
        return []
    ws = wb[SHEET]
    hdr = [str(c.value or "").strip() for c in ws[1]]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        d = {hdr[i]: ("" if v is None else v) for i, v in enumerate(r) if i < len(hdr) and hdr[i]}
        if str(d.get("Source", "")).strip():
            out.append({"name": str(d["Source"]).strip(), "role": str(d.get("Role / Description", "")).strip(),
                        "type": str(d.get("Type", "")).strip(), "country": str(d.get("Country", "")).strip(),
                        "count": str(d.get("Projects", "")).strip(), "projects": str(d.get("Project list", "")).strip()})
    return out


def build(existing: List[dict], project_rows: List[dict]) -> Tuple[List[dict], bool]:
    """
    Merge the existing Sources sheet with the sources used by live projects.
    Never deletes a source (you may be keeping it for later); only adds and refreshes the counts.
    Returns (rows, changed).
    """
    by_name = {s["name"].lower(): dict(s) for s in existing}
    used: Dict[str, List[dict]] = {}
    for r in project_rows:
        for t in split_sources(r.get("Source / Origination")):
            used.setdefault(t.lower(), []).append(r)
            by_name.setdefault(t.lower(), {"name": t, "role": "", "type": "", "country": ""})
    rows = []
    for key, s in by_name.items():
        prs = used.get(key, [])
        if not s["country"] and prs:  # first-time default: the country most of its projects are in
            cs = Counter(str(p.get("Country", "")).strip() for p in prs if str(p.get("Country", "")).strip().upper() not in ("", "TBD"))
            s["country"] = cs.most_common(1)[0][0] if cs else ""
        names = [str(p.get("Project Name", "")).strip() for p in prs]
        s["count"] = len(prs)
        s["projects"] = "; ".join(n[:60] for n in names[:12]) + (f"; ... (+{len(names) - 12})" if len(names) > 12 else "")
        rows.append(s)
    rows.sort(key=lambda s: (-s["count"], s["name"].lower()))
    old = [(s["name"], s["role"], s["type"], s["country"], str(s.get("count", "")), s.get("projects", "")) for s in existing]
    new = [(s["name"], s["role"], s["type"], s["country"], str(s["count"]), s["projects"]) for s in rows]
    return rows, old != new  # order matters too (sorted by number of projects)


def write(wb, rows: List[dict]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    if SHEET in wb.sheetnames:
        ws = wb[SHEET]
        ws.delete_rows(1, ws.max_row + 1)
        ws.data_validations.dataValidation = []
    else:
        ws = wb.create_sheet(SHEET)
    ws.append(HEADERS)
    for i, s in enumerate(rows, 1):
        ws.append([i, s["name"], s["role"], s["type"], s["country"], s["count"], s["projects"]])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF", name="Calibri")
        c.fill = PatternFill("solid", fgColor="1B3A5F")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for letter, w in zip("ABCDEFG", (7, 30, 60, 24, 16, 10, 90)):
        ws.column_dimensions[letter].width = w
    ws.freeze_panes = "C2"
    dv = DataValidation(type="list", formula1='"' + ",".join(TYPES) + '"', allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv)
    dv.add(f"D2:D{max(len(rows) + 1, 2) + 40}")
    for col in ("F", "G"):
        for c in ws[col][1:]:
            c.font = Font(color="808080")
