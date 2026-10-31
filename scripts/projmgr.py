#!/usr/bin/env python3
"""
Project management operations on the base deck + registry (used by the 'Manage projects' window).

Every operation:  backs up the current base deck first (base/_archive), edits a temporary copy, re-opens it to verify,
only then replaces the base deck, and re-syncs the Excel registry.  Nothing is ever changed in place.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import deckcore as core
import build_new_slides as bns
from pptx.oxml.ns import qn

DeckError = core.DeckError
NL = chr(10)
KEEP_ARCHIVES = 40


# --------------------------------------------------------------------------- generic safe edit of the base deck
def _prune_archive(stem: str) -> None:
    rx = re.compile("^" + re.escape(stem) + r"_\d{8}_\d{6}_before_")
    files = sorted(p for p in core.ARCHIVE_DIR.glob(stem + "_*.pptx") if rx.match(p.name))
    for old in files[:-KEEP_ARCHIVES]:
        core._rm(old)


def _edit_deck(audience: str, mutate: Callable, tag: str, verify: Optional[Callable] = None) -> Path:
    audience = core.primary(audience)
    dst = core.base_path(audience)
    prs = core._open_presentation(dst)
    mutate(prs)
    core._strip_sections(prs)
    tmp = dst.with_suffix(".editing.pptx")
    try:
        prs.save(str(tmp))
        chk = core._open_presentation(tmp)
        if verify:
            verify(chk)
        core.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archived = core.ARCHIVE_DIR / f"{dst.stem}_{datetime.now():%Y%m%d_%H%M%S}_before_{tag}.pptx"
        shutil.copy2(dst, archived)
        os.replace(tmp, dst)
    except PermissionError:
        core._rm(tmp)
        raise DeckError("The base deck is locked (open in PowerPoint?):" + NL + str(dst) + NL + "Save and close it, then try again.")
    except DeckError:
        core._rm(tmp)
        raise
    _prune_archive(dst.stem)
    return archived


def _edit_registry(audience: str, fn: Callable) -> None:
    audience = core.primary(audience)
    wb = core._open_registry()
    ws = wb[core.audience_cfg(audience)["sheet"][:31]]
    hdr = {core._s(c.value): i + 1 for i, c in enumerate(ws[1]) if c.value}
    rows = {core.norm_id(ws.cell(r, hdr["ID"]).value or ""): r for r in range(2, ws.max_row + 1) if ws.cell(r, hdr["ID"]).value}
    fn(ws, hdr, rows)
    try:
        core._backup_registry()
        tmp = core.REGISTRY_XLSX.with_suffix(".tmp.xlsx")
        wb.save(tmp)
        os.replace(tmp, core.REGISTRY_XLSX)
    except PermissionError:
        core._rm(core.REGISTRY_XLSX.with_suffix(".tmp.xlsx"))
        raise DeckError("projects_registry.xlsx is open in Excel. Close it and try again (the deck itself was already changed).")


def _scan(audience: str) -> dict:
    return core.scan_base(core.base_path(core.primary(audience)))


def _project_slides(scan: dict, key: str, versions: Optional[List[str]] = None) -> List[int]:
    p = next((x for x in scan["projects"] if x["key"] == key), None)
    if not p:
        raise DeckError(f"Project '{key}' is not in the base deck.")
    vs = versions or ["named", "unnamed", "single"]
    return sorted(n for v in vs for n in p["slides"][v])


# --------------------------------------------------------------------------- delete / retire
def delete_projects(audience: str, keys: List[str], versions: Optional[List[str]] = None, log=print) -> dict:
    """Delete the slides of the given projects (all versions, or only e.g. ['unnamed'])."""
    audience = core.primary(audience)
    keys = [core.norm_id(k) for k in keys]
    scan = _scan(audience)
    nums = sorted({n for k in keys for n in _project_slides(scan, k, versions)})
    if not nums:
        raise DeckError("Nothing to delete: those projects have no slides of that version.")
    total = scan["n_slides"]

    def mutate(prs):
        lst = prs.slides._sldIdLst
        for n in sorted(nums, reverse=True):
            el = lst[n - 1]
            prs.part.drop_rel(el.get(qn("r:id")))
            lst.remove(el)

    def verify(chk):
        if len(chk.slides) != total - len(nums):
            raise DeckError("Self-check failed after deleting slides; the base deck was not changed.")

    archived = _edit_deck(audience, mutate, "deleting_" + "_".join(keys)[:30], verify)
    core.sync([audience], verbose=False)
    gone = [k for k in keys if not any(p["key"] == k for p in _scan(audience)["projects"])]
    if gone:
        def drop(ws, hdr, rows):
            for k in gone:
                if k in rows:
                    ws.delete_rows(rows[k])
                    for kk in list(rows):
                        if rows[kk] > rows[k]:
                            rows[kk] -= 1
        try:
            _edit_registry(audience, drop)
        except DeckError as exc:
            log("  (" + str(exc).split(NL)[0] + ")")
    log(f"Deleted slides {nums}.")
    return {"slides": nums, "archived": str(archived), "projects_gone": gone}


def set_retired(audience: str, keys: List[str], retired: bool) -> dict:
    """Retire (hide from the app, keep the slides) or restore projects. Reversible, nothing is deleted."""
    audience = core.primary(audience)
    keys = [core.norm_id(k) for k in keys]
    scan = _scan(audience)
    nums = sorted({n for k in keys for n in _project_slides(scan, k)})

    def mutate(prs):
        slides = list(prs.slides)
        for n in nums:
            tf = slides[n - 1].notes_slide.notes_text_frame
            if tf is None:
                raise DeckError("Slide " + str(n) + " has no speaker-notes frame to hold its status.")
            lines = [ln for ln in re.split(r"[\n\x0b]", tf.text) if ln.strip() and not core.STATUS_RE.search(ln)]
            if retired:
                lines.append("STATUS: retired")
            tf.text = NL.join(lines)

    archived = _edit_deck(audience, mutate, ("retiring_" if retired else "restoring_") + "_".join(keys)[:30])
    core.sync([audience], verbose=False)
    after = {p["key"]: p for p in _scan(audience)["projects"]}
    bad = [k for k in keys if k in after and after[k]["retired"] != retired]
    if bad:
        raise DeckError("Self-check failed: status did not change for " + ", ".join(bad))
    return {"archived": str(archived), "slides": nums}


# --------------------------------------------------------------------------- bulk attribute edit (registry)
FIELDS = {"category": "Category", "version": "Version", "include": "Include", "country": "Country", "sector": "Sector",
          "region": "Region (Unnamed)", "model": "Model", "currency_note": "Currency Note",
          "name": "Project Name", "unnamed_name": "Unnamed Name",
          "source": "Source / Origination", "source_notes": "Source Notes"}


def update_fields(audience: str, keys: List[str], changes: Dict[str, str]) -> int:
    """Change ONLY the given attributes on the given projects (registry). changes keys: see FIELDS."""
    audience = core.primary(audience)
    keys = [core.norm_id(k) for k in keys]
    vals = {}
    for k, v in changes.items():
        if k not in FIELDS:
            raise DeckError(f"Unknown attribute '{k}'.")
        if k == "category":
            v = core.norm_category(v)
            if not v:
                raise DeckError("Category must be Closed, Active, BIP or Hold.")
        elif k == "version":
            v = core.norm_version(v)
            if not v:
                raise DeckError("Version must be Named or Unnamed.")
        elif k == "include":
            v = "YES" if core.norm_include(v) else "NO"
        elif k == "model":
            import modelnames
            v = modelnames.norm(v)
        elif k == "source":
            import sourcesheet
            v = sourcesheet.join_sources(sourcesheet.split_sources(v))  # tidy: one ' / ' separator, no duplicates
        vals[FIELDS[k]] = v
    if ("Project Name" in vals or "Unnamed Name" in vals) and len(keys) > 1:
        raise DeckError("A project name must be set one project at a time.")
    n = [0]

    def apply(ws, hdr, rows):
        for k in keys:
            r = rows.get(k)
            if not r:
                continue
            for col, v in vals.items():
                ws.cell(r, hdr[col]).value = v
            n[0] += 1

    _edit_registry(audience, apply)
    if "Source / Origination" in vals:
        core.sync([audience], verbose=False)  # adds any new source to the Sources sheet and refreshes its counts
    return n[0]


# --------------------------------------------------------------------------- rename key
def rename_project(audience: str, old: str, new: str) -> None:
    """Change a project's key (tags on all its slides) and carry its Excel details over."""
    audience = core.primary(audience)
    old, new = core.norm_id(old), core.norm_id(new)
    if not new or core.SUFFIX_RE.match(new):
        raise DeckError("Enter a project key without '_named'/'_unnamed' (e.g. kenya_wind_50mw).")
    scan = _scan(audience)
    if any(p["key"] == new for p in scan["projects"]):
        raise DeckError(f"A project called '{new}' already exists.")
    nums = _project_slides(scan, old)
    core.tag_slides(audience, [{"num": n, "key": new} for n in nums], log=lambda m: None, confirm_multi=True)

    def move(ws, hdr, rows):
        ro, rn = rows.get(old), rows.get(new)
        if ro and rn:
            for col, c in hdr.items():
                if col in ("ID", "Named Slides", "Unnamed Slides", "Common Slides", "Sort Order"):
                    continue
                ws.cell(rn, c).value = ws.cell(ro, c).value
            ws.delete_rows(ro)

    try:
        _edit_registry(audience, move)
    except DeckError:
        pass
    core.sync([audience], verbose=False)


# --------------------------------------------------------------------------- reorder
def move_projects(audience: str, keys: List[str], where: str) -> dict:
    """where: up | down | top | bottom.  Reorders the slides in the base deck (this is the order used inside each category)."""
    audience = core.primary(audience)
    keys = [core.norm_id(k) for k in keys]
    scan = _scan(audience)
    seq = [p["key"] for p in scan["projects"]]
    block = {p["key"]: sorted(n for v in p["slides"].values() for n in v) for p in scan["projects"]}
    order = list(range(1, scan["n_slides"] + 1))

    def place(key, before=None, after=None):
        for n in block[key]:
            order.remove(n)
        if before is not None:
            idx = order.index(min(block[before]))
        else:
            idx = order.index(max(block[after])) + 1
        for j, n in enumerate(block[key]):
            order.insert(idx + j, n)

    sel = [k for k in seq if k in keys]
    if where == "up":
        for k in sel:
            i = seq.index(k)
            if i > 0 and seq[i - 1] not in sel:
                place(k, before=seq[i - 1])
                seq[i - 1], seq[i] = seq[i], seq[i - 1]
    elif where == "down":
        for k in reversed(sel):
            i = seq.index(k)
            if i < len(seq) - 1 and seq[i + 1] not in sel:
                place(k, after=seq[i + 1])
                seq[i + 1], seq[i] = seq[i], seq[i + 1]
    elif where == "top":
        first = [k for k in seq if k not in sel][0] if len(sel) < len(seq) else None
        if first:
            for k in sel:
                place(k, before=first)
    elif where == "bottom":
        last = [k for k in seq if k not in sel][-1] if len(sel) < len(seq) else None
        if last:
            for k in reversed(sel):
                place(k, after=last)
    else:
        raise DeckError("where must be up, down, top or bottom")
    if order == list(range(1, scan["n_slides"] + 1)):
        return {"moved": False}

    def mutate(prs):
        lst = prs.slides._sldIdLst
        els = list(lst)
        for e in els:
            lst.remove(e)
        for n in order:
            lst.append(els[n - 1])

    def verify(chk):
        if len(chk.slides) != scan["n_slides"]:
            raise DeckError("Self-check failed after reordering; the base deck was not changed.")

    archived = _edit_deck(audience, mutate, "reordering", verify)
    core.sync([audience], verbose=False)
    new_seq = [p["key"] for p in _scan(audience)["projects"]]

    def renumber(ws, hdr, rows):
        i = 0
        for k in new_seq:
            if k in rows:
                i += 1
                ws.cell(rows[k], hdr["Sort Order"]).value = i * 10
        for k, r in rows.items():
            if k not in new_seq:
                i += 1
                ws.cell(r, hdr["Sort Order"]).value = i * 10

    try:
        _edit_registry(audience, renumber)
    except DeckError:
        pass
    return {"moved": True, "archived": str(archived)}


# --------------------------------------------------------------------------- duplicate an existing project
def duplicate_project(audience: str, key: str, new_key: str, versions: Optional[List[str]] = None) -> dict:
    """Copy a project's slides under a new key (then edit the text in PowerPoint)."""
    audience = core.primary(audience)
    key, new_key = core.norm_id(key), core.norm_id(new_key)
    if not new_key or core.SUFFIX_RE.match(new_key):
        raise DeckError("Enter a new project key without '_named'/'_unnamed'.")
    scan = _scan(audience)
    if any(p["key"] == new_key for p in scan["projects"]):
        raise DeckError(f"A project called '{new_key}' already exists.")
    p = next((x for x in scan["projects"] if x["key"] == key), None)
    if not p:
        raise DeckError(f"Project '{key}' is not in the base deck.")
    want = versions or [v for v in ("named", "unnamed", "single") if p["slides"][v]]
    nums = [(v, n) for v in want for n in p["slides"][v]]
    nums.sort(key=lambda t: t[1])
    last = max(n for _, n in nums)

    def mutate(prs):
        slides = list(prs.slides)
        lst = prs.slides._sldIdLst
        new_els = []
        for v, n in nums:
            src = slides[n - 1]
            for rel in src.part.rels.values():
                if not rel.reltype.endswith(("/image", "/slideLayout", "/notesSlide")):
                    raise DeckError("This project's slides contain charts or embedded objects that cannot be copied automatically. "
                                    "Duplicate them in PowerPoint instead.")
            new = bns.clone_slide(prs, src)
            core.set_slide_notes(prs, new, "ID: " + new_key + ("" if v == "single" else "_" + v), append=False)
            new_els.append(list(prs.slides._sldIdLst)[-1])
        for e in new_els:
            lst.remove(e)
        idx = last  # insert right after the original project's last slide
        for j, e in enumerate(new_els):
            lst.insert(idx + j, e)

    archived = _edit_deck(audience, mutate, "duplicating_" + key[:30])
    core.sync([audience], verbose=False)
    return {"archived": str(archived)}


# --------------------------------------------------------------------------- add a brand-new project from a form
LIMITS = {"title": 62, "sub": 115, "head": 40, "csub": 75, "bullet": 150, "chip": 40, "hl": 58, "step": 32,
          "footer": 110, "value": 80, "strip": 70}
TOKEN = bns.TOKEN


def tokenize(text: str, pairs: List[Tuple[str, str]]) -> str:
    """Wrap every occurrence of a 'hide' word in {{word|replacement}} (outside existing tokens)."""
    pairs = [(w.strip(), r.strip()) for w, r in pairs if w.strip()]
    if not pairs:
        return text
    pairs.sort(key=lambda t: -len(t[0]))
    lookup = {w.lower(): r for w, r in pairs}
    rx = re.compile("(?<!\\w)(" + "|".join(re.escape(w) for w, _ in pairs) + ")(?!\\w)", re.I)
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        out.append(rx.sub(lambda g: "{{" + g.group(1) + "|" + lookup[g.group(1).lower()] + "}}", text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(rx.sub(lambda g: "{{" + g.group(1) + "|" + lookup[g.group(1).lower()] + "}}", text[pos:]))
    return "".join(out)


def parse_bullets(text: str) -> List[Tuple[str, str]]:
    rows = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ":" in ln:
            a, b = ln.split(":", 1)
            rows.append((a.strip() + ":", "  " + b.strip()))
        else:
            rows.append(("", ln))
    return rows


def build_data(spec: dict) -> dict:
    """Form spec -> the dict format of new_projects_data (with {{named|unnamed}} tokens inserted)."""
    pairs = list(spec.get("hide", []))
    if spec.get("country") and spec.get("region"):
        pairs.append((spec["country"], spec["region"]))
    T = lambda t: tokenize(t, pairs)  # noqa: E731

    def card(c):
        return (T(c["head"]), T(c["sub"]), [(T(a), T(b)) for a, b in parse_bullets(c["bullets"])], T(c["chip"]), T(c["hl"]))

    d = {"key": core.norm_id(spec["key"]), "country": spec.get("country", ""), "model": spec.get("model", ""),
         "category": spec.get("category") or "", "title": T(spec["title"]), "sub": T(spec["sub"]),
         "A": card(spec["A"]), "B": card(spec["B"]),
         "steps": [(T(a), T(b)) for a, b in spec["steps"]], "strip": T(spec["strip"]), "footer": T(spec["footer"])}
    if spec.get("value", "").strip():
        d["value"] = T(spec["value"].strip())
    return d


def validate(d: dict, versions: str) -> Tuple[List[str], List[str]]:
    """(errors, warnings). Errors block saving: text that would not fit the template or a leak in an unnamed slide."""
    errs, warns = [], []
    if not d["key"] or core.SUFFIX_RE.match(d["key"]):
        errs.append("Project key is empty or ends with _named/_unnamed.")
    variants = ["named", "unnamed"] if versions == "both" else (["named"] if versions in ("named", "single") else ["unnamed"])
    for v in variants:
        R = lambda t: bns.render(t, v)  # noqa: E731
        checks = [("Title", R(d["title"]), "title"), ("Subtitle", R(d["sub"]), "sub"), ("Strip label", R(d["strip"]), "strip"),
                  ("Footer", R(d["footer"]), "footer")]
        if d.get("value"):
            checks.append(("Indicative value", R(d["value"]), "value"))
        for nm, c in (("Card A", d["A"]), ("Card B", d["B"])):
            checks += [(nm + " heading", R(c[0]), "head"), (nm + " sub-heading", R(c[1]), "csub"),
                       (nm + " chip", R(c[3]), "chip"), (nm + " highlight", R(c[4]), "hl")]
            if len(c[2]) > 4:
                errs.append(nm + ": at most 4 bullets fit.")
            for a, b in c[2]:
                checks.append((nm + " bullet", R(a) + R(b), "bullet"))
        for i, (a, b) in enumerate(d["steps"], 1):
            checks += [(f"Snapshot {i} line 1", R(a), "step"), (f"Snapshot {i} line 2", R(b), "step")]
        for nm, txt, lim in checks:
            if nm == "Title" and not txt.strip():
                errs.append("The title (heading) is required.")  # the ONLY required field
            elif len(txt) > LIMITS[lim]:
                errs.append(f"[{v}] {nm} is too long ({len(txt)} > {LIMITS[lim]} characters): {txt[:40]}...")
    return errs, warns


def add_project(audience: str, spec: dict, versions: str = "both", after_key: Optional[str] = None) -> dict:
    """
    Create the slides of a new project from a form spec and insert them into the base deck.
    versions: 'both' (named + unnamed) | 'named' | 'unnamed' | 'single' (one slide used for both versions)
    """
    d = build_data(spec)
    return add_project_from_data(audience, d, versions, after_key,
                                 {"region": spec.get("region"), "sector": spec.get("sector"), "source": spec.get("source")})


def add_project_from_data(audience: str, d: dict, versions: str = "both", after_key: Optional[str] = None, extras: Optional[dict] = None) -> dict:
    """Same as add_project, from a ready data dict (format of new_projects_data). extras: region, sector, source for the registry."""
    extras = extras or {}
    audience = core.primary(audience)
    errs, _ = validate(d, versions)
    if errs:
        raise DeckError("Fix these first:" + NL + NL.join(" - " + e for e in errs))
    scan = _scan(audience)
    if any(p["key"] == d["key"] for p in scan["projects"]):
        raise DeckError(f"A project called '{d['key']}' already exists - choose another key.")
    if after_key:
        ak = core.norm_id(after_key)
        nums = _project_slides(scan, ak)
        insert_after = max(nums)
    else:
        insert_after = max((n for p in scan["projects"] for v in p["slides"].values() for n in v), default=scan["n_slides"] - 1)
    todo = ["named", "unnamed"] if versions == "both" else [("named" if versions == "single" else versions)]
    leaks = []

    def mutate(prs):
        template = bns.find_template(prs)
        lst = prs.slides._sldIdLst
        new_els = []
        for v in todo:
            s = bns.clone_slide(prs, template)
            bns.fill(s, d, v, template, tag_variant="single" if versions == "single" else None)
            new_els.append(list(prs.slides._sldIdLst)[-1])
            if v == "unnamed" or versions == "single":
                bad = bns.check_no_leak(d, s) if v == "unnamed" else core.find_leaks(core._slide_text(s), core.load_config()["sensitive_terms"] + [d["country"]])
                leaks.extend(bad)
        for e in new_els:
            lst.remove(e)
        for j, e in enumerate(new_els):
            lst.insert(insert_after + j, e)
        if leaks:
            raise DeckError("The unnamed slide still contains identifying words: " + ", ".join(sorted(set(leaks))) +
                            NL + "Add them to 'Words to hide' (or reword) and try again. Nothing was saved.")

    archived = _edit_deck(audience, mutate, "adding_" + d["key"][:30])
    core.sync([audience], verbose=False)
    extra = {}
    if d["country"]:
        extra["Country"] = d["country"]
    if extras.get("region"):
        extra["Region (Unnamed)"] = extras["region"]
    if d["model"]:
        import modelnames
        extra["Model"] = modelnames.norm(d["model"])
    if extras.get("sector"):
        extra["Sector"] = extras["sector"]
    if extras.get("source"):
        import sourcesheet
        extra["Source / Origination"] = sourcesheet.join_sources(sourcesheet.split_sources(extras["source"]))
    if d["category"]:
        extra["Category"] = d["category"]

    def reg(ws, hdr, rows):
        r = rows.get(d["key"])
        if r:
            for col, val in extra.items():
                ws.cell(r, hdr[col]).value = val

    try:
        if extra:
            _edit_registry(audience, reg)
    except DeckError:
        pass
    return {"archived": str(archived), "key": d["key"]}


def refresh_project_slides(audience: str, d: dict) -> dict:
    """Re-fill the EXISTING standard-layout slides of a project (one named + one unnamed, or one for both) from a data
    definition (same format as new_projects_data). Nothing else in the deck changes; the old deck is archived first."""
    audience = core.primary(audience)
    scan = _scan(audience)
    p = next((x for x in scan["projects"] if x["key"] == d["key"]), None)
    if not p:
        raise DeckError(f"Project '{d['key']}' is not in the base deck.")
    jobs = []
    for v in ("named", "unnamed", "single"):
        if len(p["slides"][v]) > 1:
            raise DeckError(f"'{d['key']}' has several {v} slides - refresh only works on single-slide versions.")
        if p["slides"][v]:
            jobs.append((v, p["slides"][v][0]))
    leaks = []

    def mutate(prs):
        template = bns.find_template(prs)
        slides = list(prs.slides)
        for v, n in jobs:
            sl = slides[n - 1]
            names = {sh.name for sh in sl.shapes}
            if not {"Title", "Card head 1", "Bullets 1"} <= names:
                raise DeckError(f"Slide {n} is not in the standard layout, so it cannot be refreshed automatically.")
            bns.fill(sl, d, "named" if v == "single" else v, template, tag_variant="single" if v == "single" else None)
            if v in ("unnamed", "single"):
                leaks.extend(bns.check_no_leak(d, sl))
        if leaks:
            raise DeckError("The unnamed slide would still contain identifying words: " + ", ".join(sorted(set(leaks))) + NL +
                            "Nothing was changed.")

    archived = _edit_deck(audience, mutate, "updating_" + d["key"][:30])
    core.sync([audience], verbose=False)
    return {"archived": str(archived), "slides": [n for _, n in jobs]}


# --------------------------------------------------------------------------- undo
def list_backups(audience: str) -> List[dict]:
    stem = core.base_path(core.primary(audience)).stem
    out = []
    for p in sorted(core.ARCHIVE_DIR.glob(stem + "_*.pptx"), reverse=True):
        m = re.match("^" + re.escape(stem) + r"_(\d{8})_(\d{6})_before_(.*)\.pptx$", p.name)
        if m:
            when = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            out.append({"file": p.name, "when": when, "what": m.group(3).replace("_", " "), "size": p.stat().st_size})
    return out


def restore_backup(audience: str, filename: str) -> None:
    """Put an archived version back as the base deck (the current one is archived first)."""
    audience = core.primary(audience)
    src = core.ARCHIVE_DIR / filename
    if not src.exists():
        raise DeckError("That backup no longer exists.")
    core._open_presentation(src)  # must be a valid deck

    def mutate(prs):
        pass

    dst = core.base_path(audience)
    core.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    keep = core.ARCHIVE_DIR / f"{dst.stem}_{datetime.now():%Y%m%d_%H%M%S}_before_restoring_backup.pptx"
    try:
        shutil.copy2(dst, keep)
        tmp = dst.with_suffix(".restoring.pptx")
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    except PermissionError:
        raise DeckError("The base deck is locked (open in PowerPoint?). Save and close it, then try again.")
    core.sync([audience], verbose=False)


# every add / delete / modify below is written to the Project Desk change log
try:
    import tracker as _tracker
    _tracker.install_hooks(sys.modules[__name__])
except Exception:  # the log must never stop a deck operation
    pass
