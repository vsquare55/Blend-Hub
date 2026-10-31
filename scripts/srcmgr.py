#!/usr/bin/env python3
"""Managing the sources (originators) of projects: seed, edit, rename / merge, set per project, report."""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import deckcore as core
import sourcesheet as ss
from projmgr import _edit_registry

DeckError = core.DeckError


# --------------------------------------------------------------------------- the Sources sheet
def _edit_sources(fn) -> None:
    wb = core._open_registry()
    if ss.SHEET not in wb.sheetnames:
        raise DeckError("The registry has no 'Sources' sheet yet - start the app once so it is created.")
    ws = wb[ss.SHEET]
    hdr = {core._s(c.value): i + 1 for i, c in enumerate(ws[1]) if c.value}
    fn(wb, ws, hdr)
    try:
        core._backup_registry()
        tmp = core.REGISTRY_XLSX.with_suffix(".tmp.xlsx")
        wb.save(tmp)
        os.replace(tmp, core.REGISTRY_XLSX)
    except PermissionError:
        core._rm(core.REGISTRY_XLSX.with_suffix(".tmp.xlsx"))
        raise DeckError("projects_registry.xlsx is open in Excel. Close it and try again.")


def _find_row(ws, hdr, name: str) -> Optional[int]:
    for r in range(2, ws.max_row + 1):
        if core._s(ws.cell(r, hdr["Source"]).value).lower() == name.strip().lower():
            return r
    return None


def update_source_info(name: str, role: Optional[str] = None, type: Optional[str] = None, country: Optional[str] = None) -> bool:
    """Change ONLY the given attributes of a source (None = leave as it is)."""
    name = " ".join(name.split())
    if not name:
        raise DeckError("A source needs a name.")

    def fn(wb, ws, hdr):
        r = _find_row(ws, hdr, name)
        if r is None:
            ws.append([None] * len(hdr))
            r = ws.max_row
            ws.cell(r, hdr["Source"]).value = name
        for col, val in (("Role / Description", role), ("Type", type), ("Country", country)):
            if val is not None:
                ws.cell(r, hdr[col]).value = val

    _edit_sources(fn)
    return True


def rename_source(old: str, new: str) -> int:
    """Rename a source everywhere (all projects). If `new` already exists the two are MERGED. Returns projects touched."""
    old, new = " ".join(old.split()), " ".join(new.split())
    if not old or not new:
        raise DeckError("Both names are needed.")
    touched = [0]
    cfg = core.load_config()
    sheets = sorted({cfg["audiences"][core.primary(a)]["sheet"][:31] for a in cfg["audiences"]})

    wb = core._open_registry()
    for sh in sheets:
        if sh not in wb.sheetnames:
            continue
        ws = wb[sh]
        hdr = {core._s(c.value): i + 1 for i, c in enumerate(ws[1]) if c.value}
        col = hdr.get("Source / Origination")
        if not col:
            continue
        for r in range(2, ws.max_row + 1):
            toks = ss.split_sources(ws.cell(r, col).value)
            if any(t.lower() == old.lower() for t in toks):
                toks = [new if t.lower() == old.lower() else t for t in toks]
                ws.cell(r, col).value = ss.join_sources(ss.split_sources(ss.join_sources(toks)))
                touched[0] += 1
    if ss.SHEET in wb.sheetnames:
        ws = wb[ss.SHEET]
        hdr = {core._s(c.value): i + 1 for i, c in enumerate(ws[1]) if c.value}
        ro, rn = _find_row(ws, hdr, old), _find_row(ws, hdr, new)
        if ro and rn and ro != rn:  # merge: keep the new one's details, borrow the old one's where blank
            for c in ("Role / Description", "Type", "Country"):
                if not core._s(ws.cell(rn, hdr[c]).value) and core._s(ws.cell(ro, hdr[c]).value):
                    ws.cell(rn, hdr[c]).value = ws.cell(ro, hdr[c]).value
            ws.delete_rows(ro)
        elif ro:
            ws.cell(ro, hdr["Source"]).value = new
    try:
        core._backup_registry()
        tmp = core.REGISTRY_XLSX.with_suffix(".tmp.xlsx")
        wb.save(tmp)
        os.replace(tmp, core.REGISTRY_XLSX)
    except PermissionError:
        core._rm(core.REGISTRY_XLSX.with_suffix(".tmp.xlsx"))
        raise DeckError("projects_registry.xlsx is open in Excel. Close it and try again.")
    core.sync(verbose=False)
    return touched[0]


def set_project_sources(audience: str, keys: List[str], sources: List[str], mode: str = "replace") -> int:
    """mode: replace (set exactly these) | add (add to what is there) | remove (take these off)."""
    keys = [core.norm_id(k) for k in keys]
    n = [0]

    def fn(ws, hdr, rows):
        col = hdr["Source / Origination"]
        for k in keys:
            r = rows.get(k)
            if not r:
                continue
            cur = ss.split_sources(ws.cell(r, col).value)
            if mode == "replace":
                new = ss.split_sources(ss.join_sources(sources))
            elif mode == "add":
                new = ss.split_sources(ss.join_sources(cur + sources))
            else:
                drop = {s.lower() for s in sources}
                new = [t for t in cur if t.lower() not in drop]
            ws.cell(r, col).value = ss.join_sources(new)
            n[0] += 1

    _edit_registry(audience, fn)
    core.sync([core.primary(audience)], verbose=False)
    return n[0]


# --------------------------------------------------------------------------- one-time import of what the workbook says
def apply_seed(audience: str = "EPC", overwrite: bool = False) -> dict:
    """Fill Source / Source Notes from source_seed.py (only where blank, unless overwrite) and the source roles."""
    import source_seed as sd
    audience = core.primary(audience)
    done = {"filled": 0, "kept": 0}

    def fn(ws, hdr, rows):
        sc, nc = hdr["Source / Origination"], hdr["Source Notes"]
        for key, (src, note) in sd.SEED.items():
            r = rows.get(key)
            if not r:
                continue
            if core._s(ws.cell(r, sc).value) and not overwrite:
                done["kept"] += 1
                continue
            ws.cell(r, sc).value = src
            ws.cell(r, nc).value = note
            done["filled"] += 1
        for key, hint in sd.BLANK_HINTS.items():
            r = rows.get(key)
            if r and not core._s(ws.cell(r, nc).value):
                ws.cell(r, nc).value = hint

    _edit_registry(audience, fn)
    core.sync([audience], verbose=False)  # creates one row per source in the Sources sheet

    def info(wb, ws, hdr):
        for name, (role, typ, country) in sd.INFO.items():
            r = _find_row(ws, hdr, name)
            if r is None:
                continue
            for col, val in (("Role / Description", role), ("Type", typ), ("Country", country)):
                if val and (overwrite or not core._s(ws.cell(r, hdr[col]).value)):
                    ws.cell(r, hdr[col]).value = val

    _edit_sources(info)
    core.sync([audience], verbose=False)
    return done


# --------------------------------------------------------------------------- analysis / report
def breakdown(projects: List[dict], info: List[dict]) -> List[dict]:
    """One row per source: projects, category split, countries, sectors (live, non-retired projects)."""
    by = defaultdict(list)
    for p in projects:
        toks = p.get("sources") or []
        for t in toks:
            by[t.lower()].append(p)
    meta = {s["name"].lower(): s for s in info}
    names = {t.lower(): t for p in projects for t in (p.get("sources") or [])}
    rows = []
    for key in sorted(set(by) | set(meta), key=lambda k: (-len(by.get(k, [])), k)):
        ps = by.get(key, [])
        m = meta.get(key, {})
        cats = Counter(p["category"] for p in ps)
        rows.append({
            "name": m.get("name") or names.get(key, key), "role": m.get("role", ""), "type": m.get("type", ""),
            "country": m.get("country", ""), "count": len(ps),
            "cats": {c: cats.get(c, 0) for c in core.CATEGORY_ORDER},
            "countries": sorted({p["country"] for p in ps if p["country"] and p["country"].upper() != "TBD"}),
            "sectors": sorted({p["sector"] for p in ps}),
            "projects": [p["name"] for p in ps], "ids": [p["id"] for p in ps],
        })
    return rows


def export_summary(audience: str) -> Path:
    """Excel report for informed decisions: by source, project-by-source list, and projects with no source."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    data = core.load_projects(audience)
    rows = breakdown(data["projects"], data.get("sources_info", []))
    wb = Workbook()
    ws = wb.active
    ws.title = "By source"
    ws.append(["Source", "Role / Description", "Type", "Country", "Projects", "Closed", "Active", "BIP", "Hold", "Countries", "Sectors", "Projects (names)"])
    for r in rows:
        ws.append([r["name"], r["role"], r["type"], r["country"], r["count"], r["cats"]["Closed"], r["cats"]["Active"], r["cats"]["BIP"],
                   r["cats"]["Hold"], ", ".join(r["countries"]), ", ".join(r["sectors"]), "; ".join(r["projects"])])
    ws2 = wb.create_sheet("Projects by source")
    ws2.append(["Source", "Sr. No.", "Project", "Country", "Sector", "Category", "Default version"])
    for r in rows:
        for pid in r["ids"]:
            p = next(x for x in data["projects"] if x["id"] == pid)
            ws2.append([r["name"], p["sr"], p["name"], p["country"], p["sector"], p["category"], p["version"]])
    ws3 = wb.create_sheet("No source recorded")
    ws3.append(["Sr. No.", "Project", "Country", "Sector", "Category", "Source Notes"])
    for p in data["projects"]:
        if not p["sources"]:
            ws3.append([p["sr"], p["name"], p["country"], p["sector"], p["category"], p["source_notes"]])
    for sheet, widths in ((ws, (30, 60, 22, 14, 9, 8, 8, 8, 8, 34, 34, 90)), (ws2, (30, 8, 60, 14, 22, 10, 14)), (ws3, (8, 60, 14, 22, 10, 80))):
        for c in sheet[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1B3A5F")
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for i, w in enumerate(widths):
            sheet.column_dimensions[chr(65 + i)].width = w
        sheet.freeze_panes = "A2"
    core.OUTPUT_DIR.mkdir(exist_ok=True)
    out = core.OUTPUT_DIR / f"Source_Summary_{datetime.now():%Y%m%d_%H%M}.xlsx"
    wb.save(out)
    return out
