#!/usr/bin/env python3
"""
EPC / Investor Deck Manager - core engine.

One engine, many audiences (EPC, Investor, ...). Each audience has its own base
deck in base/ and its own sheet in projects_registry.xlsx.

Everything the generator needs about the SLIDES is read fresh from the base deck
(speaker-notes tags), so the Excel file can never go stale or break a build.
Excel only stores the things a human curates: names, default category, default
version (Named/Unnamed), model, country, notes ...

Notes tags on a project slide (speaker notes):
    ID: togo_161kv_named          <- "_named" / "_unnamed" suffix = which version this slide is
    ID: togo_161kv_unnamed           (same project key "togo_161kv" -> ONE project, two versions)
    ID: icc_convention            <- no suffix = one slide used for both versions
    CATEGORY: Active              <- optional first-time default (Closed | Active | BIP | Hold)
    NAME: Pretty name             <- optional first-time default for the index name
    TYPE: divider|boilerplate|closing|skip   <- optional, for slides WITHOUT an ID
    VARIANT: named|unnamed        <- optional, instead of the _named/_unnamed suffix
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from sectors import infer_sector
import sourcesheet
import modelnames

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
REGISTRY_XLSX = ROOT / "projects_registry.xlsx"
OUTPUT_DIR = ROOT / "output"
BACKUP_DIR = ROOT / "backups"
PRESET_DIR = ROOT / "presets"
ARCHIVE_DIR = ROOT / "base" / "_archive"

CATEGORY_ORDER = ["Closed", "Active", "BIP", "Hold"]
CATS = {"closed": "Closed", "active": "Active", "bip": "BIP", "hold": "Hold"}
VERSIONS = ["Named", "Unnamed"]

DEFAULT_SENSITIVE = [
    "Togo", "Cameroon", "Guinea", "Burkina Faso", "Burkina", "Tanzania", "Botswana", "DRC", "Congo",
    "Conakry", "Lomé", "Douala", "Yaoundé", "Ouagadougou", "Gaborone", "Kinshasa", "Brazzaville",
    "Dar es Salaam", "Dodoma", "Rufiji", "TANESCO", "DAWASA", "TGDC", "Ngozi", "Kiejo-Mbaka",
    "Zambia", "Kenya", "Uganda", "Ghana", "Nigeria", "Senegal", "Mali", "Niger", "Chad", "Gabon", "Rwanda",
    "Mozambique", "Namibia", "Angola", "Ethiopia", "Ivory Coast", "Côte d'Ivoire", "Sierra Leone",
    "Liberia", "Zimbabwe", "Malawi", "Benin", "Mauritania", "Madagascar", "Sudan", "Egypt", "Morocco",
    "Algeria", "Tunisia", "Libya",
]

DEFAULT_CONFIG = {
    "audiences": {
        "EPC": {
            "label": "EPC contractor",
            "base": "base/EPC_Partnership_Base.pptx",
            "sheet": "EPC Registry",
            "file_tag": "EPC_Partnership",
        },
        "Investor": {
            "label": "Investor",
            "base": "base/Investor_Partnership_Base.pptx",
            "sheet": "Investor Registry",
            "file_tag": "Investor_Partnership",
            "seed_category_from_legacy_excel": True,
        },
    },
    "client_placeholders": ["Omatapalo"],
    "footer": "BLEND FINANCE  ·  STRICTLY PRIVATE & CONFIDENTIAL",
    "sensitive_terms": DEFAULT_SENSITIVE,
    "backups_to_keep": 15,
    "doc_title": "Partnership Opportunities – {client}",  # file 'Title' property of generated decks
    "doc_author": "",  # blank = keep the base deck's author
}


def os_open(path, reveal: bool = False) -> None:
    """Open a file / folder with the system default (Windows, macOS, Linux); reveal=True shows it in Explorer / Finder."""
    import subprocess
    p = str(path)
    if sys.platform.startswith("win"):
        if reveal:
            subprocess.Popen(["explorer", "/select,", p])
        else:
            os.startfile(p)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", p] if reveal else ["open", p])
    else:
        subprocess.Popen(["xdg-open", str(Path(p).parent if reveal else p)])


BROWSER_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "/Applications/Chromium.app/Contents/MacOS/Chromium",
    str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/microsoft-edge"]


def find_chromium():
    """Edge / Chrome / Brave / Chromium (needed for PDFs and the app-style window) on Windows, macOS or Linux."""
    for b in BROWSER_PATHS:
        if os.path.exists(b):
            return b
    for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        w = shutil.which(name)
        if w:
            return w
    return None


class DeckError(Exception):
    """A problem the user can understand and fix (shown as a plain message)."""


class NeedsConfirm(DeckError):
    """The change is allowed but unusual - the caller should ask the user and call again with confirm_multi=True."""


# --------------------------------------------------------------------------- config
def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(user.get("audiences"), dict) and user["audiences"]:
                cfg["audiences"] = user["audiences"]
            for k in ("client_placeholders", "footer", "sensitive_terms", "backups_to_keep", "doc_title", "doc_author"):
                if k in user:
                    cfg[k] = user[k]
        except Exception as exc:  # corrupt config must never block the user
            print(f"  [warn] config.json unreadable ({exc}); using defaults")
    else:
        try:
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    for name, a in cfg["audiences"].items():
        src = a.get("same_as")
        if src and src in cfg["audiences"] and src != name:  # share another audience's deck + registry sheet
            a["base"], a["sheet"] = cfg["audiences"][src].get("base"), cfg["audiences"][src].get("sheet")
        a.setdefault("label", name)
        a.setdefault("sheet", f"{name} Registry")
        a.setdefault("file_tag", f"{name}_Partnership")
        a.setdefault("base", f"base/{name}_Partnership_Base.pptx")
    return cfg


def primary(audience: str) -> str:
    """The audience that owns the base deck / registry sheet (itself unless configured 'same_as')."""
    auds = load_config()["audiences"]
    src = auds.get(audience, {}).get("same_as")
    return src if src in auds else audience


def audience_cfg(audience: str) -> dict:
    cfg = load_config()
    if audience not in cfg["audiences"]:
        raise DeckError(f"Unknown audience '{audience}'. Available: {', '.join(cfg['audiences'])}")
    return cfg["audiences"][audience]


def base_path(audience: str) -> Path:
    return ROOT / audience_cfg(audience)["base"]


def audience_names() -> List[str]:
    return list(load_config()["audiences"].keys())


# --------------------------------------------------------------------------- small helpers
def norm_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def safe_filename(s: str) -> str:
    out = "".join(c if (c.isalnum() or c in "-_ ") else "_" for c in s).strip().replace(" ", "_")
    return out[:80] or "Client"


def norm_category(v) -> Optional[str]:
    return CATS.get(str(v or "").strip().lower())


def norm_version(v) -> Optional[str]:
    s = str(v or "").strip().lower()
    if not s:
        return None
    if s.startswith(("un", "no", "anon", "blind", "hidden")):
        return "Unnamed"
    if s.startswith(("name", "reveal", "show")):
        return "Named"
    return None


def norm_include(v) -> bool:
    return str(v or "").strip().upper() in ("YES", "Y", "1", "TRUE", "X")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def clip(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# --------------------------------------------------------------------------- scanning a base deck
ID_RE = re.compile(r"\bID\s*:[ \t]*([^\r\n\x0b|]+)", re.I)
CAT_RE = re.compile(r"\bCATEGORY\s*:[ \t]*([^\r\n\x0b|]+)", re.I)
NAME_RE = re.compile(r"\bNAME\s*:[ \t]*([^\r\n\x0b|]+)", re.I)
TYPE_RE = re.compile(r"\bTYPE\s*:\s*(divider|boilerplate|closing|skip)", re.I)
VARIANT_RE = re.compile(r"\bVARIANT\s*:\s*(named|unnamed)", re.I)
STATUS_RE = re.compile(r"\bSTATUS\s*:\s*retired", re.I)  # retired = hidden from the app, never put in a deck, never deleted
SUFFIX_RE = re.compile(r"^(.*?)_(unnamed|nonamed|noname|named)$")


def _notes(slide) -> str:
    try:
        if not slide.has_notes_slide:
            return ""
        tf = slide.notes_slide.notes_text_frame
        return tf.text if tf is not None else ""
    except Exception:
        return ""


def _title(slide) -> str:
    for sh in slide.shapes:
        try:
            if sh.has_text_frame and sh.text_frame.text.strip():
                return " ".join(sh.text_frame.text.strip().splitlines()[0].split())[:90]
        except Exception:
            continue
    return ""


def _has_value_shape(slide) -> bool:
    from pptx.oxml.ns import qn
    return any((e.get("name") or "").upper().startswith("VALUE") for e in slide._element.iter(qn("p:cNvPr")))


def _strip_value_shapes(slide) -> int:
    """Remove every shape whose name starts with VALUE (the optional 'Indicative value' box)."""
    from pptx.oxml.ns import qn
    n = 0
    for c in list(slide._element.iter(qn("p:cNvPr"))):
        if (c.get("name") or "").upper().startswith("VALUE"):
            node = c.getparent().getparent()  # cNvPr -> nvSpPr -> sp
            if node.getparent() is not None:
                node.getparent().remove(node)
                n += 1
    return n


def _slide_text(slide) -> str:
    from pptx.oxml.ns import qn
    parts = [t.text or "" for t in slide._element.iter(qn("a:t"))]
    parts += [e.get("descr", "") for e in slide._element.iter() if e.get("descr")]
    return " \n".join(parts)


def _open_presentation(path: Path):
    from pptx import Presentation
    if not path.exists():
        raise DeckError(f"Base deck not found:\n{path}")
    try:
        return Presentation(str(path))
    except PermissionError:
        raise DeckError(f"Cannot read the base deck (is it locked?):\n{path}\nClose it in PowerPoint and try again.")
    except Exception as exc:
        raise DeckError(f"The base deck could not be opened ({exc}).\n{path}\n"
                        f"Open it in PowerPoint and re-save it, then try again.")


def scan_base(path: Path, sensitive: Optional[List[str]] = None) -> dict:
    """Read a base deck and classify every slide. Never modifies anything."""
    prs = _open_presentation(path)
    slides = []
    for i, s in enumerate(prs.slides, 1):
        n = _notes(s)
        idm, cm, nm, tm, vm = (ID_RE.search(n), CAT_RE.search(n), NAME_RE.search(n),
                               TYPE_RE.search(n), VARIANT_RE.search(n))
        key = variant = None
        if idm:
            raw = norm_id(idm.group(1))
            sm = SUFFIX_RE.match(raw)
            if vm:
                variant = vm.group(1).lower()
                key = sm.group(1) if sm else raw
            elif sm:
                key = sm.group(1)
                variant = "named" if sm.group(2) == "named" else "unnamed"
            else:
                key, variant = raw, "single"
        slides.append({
            "num": i, "title": _title(s), "key": key, "variant": variant,
            "category_raw": cm.group(1).strip() if cm else None,
            "name": nm.group(1).strip() if nm else None,
            "type": tm.group(1).lower() if tm else None,
            "text": _slide_text(s), "has_value": _has_value_shape(s), "retired": bool(STATUS_RE.search(n)),
        })

    tagged = [s["num"] for s in slides if s["key"]]
    first, last = (min(tagged), max(tagged)) if tagged else (0, 0)
    boiler, dividers, closing, warnings = [], [], [], []
    projects: Dict[str, dict] = {}

    for s in slides:
        n = s["num"]
        if s["key"]:
            s["role"] = "Project"
            p = projects.setdefault(s["key"], {
                "key": s["key"], "slides": {"named": [], "unnamed": [], "single": []},
                "titles": {"named": "", "unnamed": "", "single": ""}, "category": None,
                "name_tag": None, "first": n, "retired": False})
            p["retired"] = p["retired"] or s["retired"]
            p["slides"][s["variant"]].append(n)
            p["titles"][s["variant"]] = p["titles"][s["variant"]] or s["title"]
            if s["category_raw"] and not p["category"]:
                c = norm_category(s["category_raw"])
                if c:
                    p["category"] = c
                else:
                    warnings.append(f"Slide {n} ({s['key']}): unknown CATEGORY '{s['category_raw']}' "
                                    f"(use Closed, Active, BIP or Hold) - ignored.")
            p["name_tag"] = p["name_tag"] or s["name"]
            continue
        role = s["type"]
        if role is None:
            if n < first:
                role = "divider" if "project opportunities" in s["title"].lower() else "boilerplate"
            elif n > last:
                role = "closing"
            else:
                role = "divider"
                if "project opportunities" not in s["title"].lower():
                    warnings.append(f"Slide {n} ('{clip(s['title'], 40)}') has no ID in its notes - treated as a "
                                    f"section divider and left out of generated decks. Add 'ID: ...' if it is a project.")
        s["role"] = {"divider": "Old divider (dropped)", "skip": "Old divider (dropped)",
                     "boilerplate": "Boilerplate", "closing": "Closing"}[role]
        {"boilerplate": boiler, "closing": closing}.get(role, dividers).append(n)

    for p in projects.values():
        for v in p["slides"]:
            p["slides"][v].sort()
        sl = p["slides"]
        if sl["single"] and (sl["named"] or sl["unnamed"]):
            warnings.append(f"'{p['key']}' mixes a no-suffix ID with _named/_unnamed IDs - the no-suffix slide(s) "
                            f"{sl['single']} will be used for BOTH versions. Check this is intended.")
        for v in ("named", "unnamed", "single"):
            nums = sl[v]
            if nums and nums[-1] - nums[0] + 1 != len(nums):
                warnings.append(f"'{p['key']}' ({v}) is on non-adjacent slides {nums} - if these are different "
                                f"projects, give each its own ID.")
            titles = [next(x["title"] for x in slides if x["num"] == k) for k in nums]
            if len(nums) > 1 and len(set(titles)) < len(titles):
                warnings.append(f"'{p['key']}' ({v}) covers slides {nums} with identical titles - if you copied "
                                f"a slide to make a NEW project, change the ID in its notes.")
        if not (sl["named"] or sl["single"]):
            warnings.append(f"'{p['key']}' has only an UNNAMED slide - choosing 'Named' will use the unnamed slide.")
        if not (sl["unnamed"] or sl["single"]):
            warnings.append(f"'{p['key']}' has only a NAMED slide - it will be SKIPPED in any deck where 'Unnamed' "
                            f"is chosen. (If one slide suits both, remove the '_named' suffix from its ID.)")
    if not tagged:
        warnings.append("No 'ID: ...' notes found on any slide - nothing can be selected. See HOW_TO_TAG_IN_PPTX.txt.")

    # slides that look like a forgotten tag: untagged slides sitting among the projects, or several 'closing' slides
    extra_closing = list(closing) if len(closing) > 1 else []  # normally exactly one closing slide
    if extra_closing:
        warnings.append(f"Slides {extra_closing} come after the last project and are treated as CLOSING slides "
                        f"(shown in EVERY deck). If they are new projects, tag them (app: 'Tag new slides').")
    suspect = sorted(set(extra_closing) | {s["num"] for s in slides if s["role"] == "Old divider (dropped)"
                                           and not s["key"] and "project opportunities" not in s["title"].lower()})

    return {
        "path": str(path), "slides": slides, "boilerplate": boiler, "dividers": set(dividers), "closing": closing,
        "projects": sorted(projects.values(), key=lambda p: p["first"]), "warnings": warnings,
        "n_slides": len(slides), "suspect": suspect,
    }


def find_leaks(text: str, terms: List[str]) -> List[str]:
    hits = []
    for t in terms:
        t = _s(t)
        if len(t) < 3 or t.upper() == "TBD":
            continue
        if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, re.I):
            hits.append(t)
    return hits


def project_leaks(scan: dict, proj_slides_unnamed: List[int], country: str, cfg: dict) -> List[str]:
    terms = list(cfg.get("sensitive_terms", []))
    for part in re.split(r"[/,;]", country or ""):
        if part.strip():
            terms.append(part.strip())
    by_num = {s["num"]: s for s in scan["slides"]}
    found = []
    for n in proj_slides_unnamed:
        for h in find_leaks(by_num[n]["text"], terms):
            if h.lower() not in [f.lower() for f in found]:
                found.append(h)
    return found


# --------------------------------------------------------------------------- registry (Excel)
HEADERS = ["Sr. No.", "Include", "ID", "Project Name", "Unnamed Name", "Category", "Version", "Model", "Country",
           "Sector", "Source / Origination", "Region (Unnamed)", "Currency Note", "Value (EUR Mn)", "Named Slides",
           "Unnamed Slides", "Common Slides", "Sort Order", "Notes", "Source Notes"]
SOURCE_HEADERS = ["Sr. No.", "Source", "Role / Description", "Type", "Country", "Projects", "Project list"]
SOURCE_TYPES = ["Minister / Government", "Local partner", "Developer", "Adviser / Consultant", "Bank / Financier",
                "EPC partner", "Other"]
SLIDE_COLS = ("Named Slides", "Unnamed Slides", "Common Slides")


def _fmt_slides(lst: List[int]) -> str:
    return ",".join(str(x) for x in lst)


def _read_sheet(wb, name: str) -> Tuple[List[str], List[dict]]:
    if name not in wb.sheetnames:
        return [], []
    ws = wb[name]
    headers = [_s(c.value) for c in ws[1]]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        d = {headers[i]: ("" if v is None else v) for i, v in enumerate(r) if i < len(headers) and headers[i]}
        if _s(d.get("ID")):
            rows.append(d)
    return headers, rows


def _open_registry():
    from openpyxl import load_workbook, Workbook
    if REGISTRY_XLSX.exists():
        try:
            return load_workbook(REGISTRY_XLSX)
        except PermissionError:
            raise DeckError("Cannot read projects_registry.xlsx - close it in Excel and try again.")
        except Exception as exc:
            raise DeckError(f"projects_registry.xlsx is damaged or not a valid Excel file ({exc}).\n"
                            f"Restore a copy from the 'backups' folder.")
    return Workbook()


def _old_registry_seed(wb) -> Dict[str, dict]:
    """Rows of the pre-audience registry ('Projects Registry') used once to carry data over."""
    if "Projects Registry" not in wb.sheetnames:
        return {}
    _, rows = _read_sheet(wb, "Projects Registry")
    seed = {}
    for r in rows:
        seed[norm_id(r["ID"])] = {
            "Project Name": _s(r.get("Project Name")), "Category": norm_category(r.get("Category")),
            "Model": _s(r.get("Model")), "Country": _s(r.get("Country")),
            "Currency Note": _s(r.get("Currency Note")), "Value (EUR Mn)": r.get("Value (EUR Mn)", ""),
            "Notes": _s(r.get("Notes")),
        }
    return seed


def merge_registry(scan: dict, existing: List[dict], seed: Optional[Dict[str, dict]] = None,
                   seed_category_wins: bool = False) -> Tuple[List[dict], dict]:
    """
    Combine what the base deck says with what the Excel rows say.
    Human-curated Excel values are never overwritten; slide numbers always refresh.
    Returns (rows in sort order, report).
    """
    seed = seed or {}
    rep = {"added": [], "removed": [], "moved": [], "repaired": []}
    by_key = {}
    for r in existing:
        k = norm_id(r["ID"])
        r["ID"] = k
        if k in by_key:
            rep["repaired"].append(f"duplicate registry row for '{k}' ignored")
            continue
        by_key[k] = r
    deck = {p["key"]: p for p in scan["projects"]}

    for k, r in by_key.items():
        if k in deck:
            p = deck[k]
            new = (_fmt_slides(p["slides"]["named"]), _fmt_slides(p["slides"]["unnamed"]), _fmt_slides(p["slides"]["single"]))
            old = tuple(_s(r.get(c)).replace(" ", "") for c in SLIDE_COLS)
            if old != new and any(old):
                rep["moved"].append((k, old, new))
            for c, v in zip(SLIDE_COLS, new):
                r[c] = v
            # repair invalid user values instead of crashing later
            cat = norm_category(r.get("Category"))
            if not cat:
                cat = p["category"] or "BIP"
                rep["repaired"].append(f"{k}: invalid Category '{r.get('Category')}' -> {cat}")
            r["Category"] = cat
            ver = norm_version(r.get("Version"))
            if not ver:
                if _s(r.get("Version")):
                    rep["repaired"].append(f"{k}: invalid Version '{r.get('Version')}' -> Named")
                ver = "Named"
            r["Version"] = ver
            r["Include"] = "YES" if norm_include(r.get("Include")) else "NO"
            marker = "not in base deck (slide removed)"
            if marker in _s(r.get("Notes")):  # its slides are back (or the mark was stale): re-activate, keep its details
                note = _s(r["Notes"]).replace(" | " + marker, "").replace(marker, "").strip(" |")
                r["Notes"] = note
                if not any(old):  # it had been switched off only because the slides were missing
                    r["Include"] = "YES"
                    rep.setdefault("restored", []).append(k)
            if not _s(r.get("Project Name")):
                r["Project Name"] = p["name_tag"] or p["titles"]["named"] or p["titles"]["single"] or p["titles"]["unnamed"] or k
            if not _s(r.get("Unnamed Name")) and p["titles"]["unnamed"]:
                r["Unnamed Name"] = p["titles"]["unnamed"]
            if not _s(r.get("Sector")):  # first-time classification only; whatever you type afterwards is kept
                r["Sector"] = infer_sector(k, _s(r.get("Project Name")), _s(r.get("Unnamed Name")))
        else:
            if _s(r.get("Named Slides")) or _s(r.get("Unnamed Slides")) or _s(r.get("Common Slides")) or norm_include(r.get("Include")):
                r["Include"] = "NO"
                for c in SLIDE_COLS:
                    r[c] = ""
                note = _s(r.get("Notes"))
                if "not in base deck" not in note:
                    r["Notes"] = (note + " | " if note else "") + "not in base deck (slide removed)"
                rep["removed"].append(k)

    def sort_val(r):
        try:
            return int(float(r.get("Sort Order")))
        except (TypeError, ValueError):
            return 10 ** 6
    ordered = sorted(by_key.values(), key=sort_val)

    prev: Optional[str] = None
    for p in scan["projects"]:
        k = p["key"]
        if k not in by_key:
            sd = seed.get(k, {})
            sl = p["slides"]
            cat = None
            if seed_category_wins:
                cat = sd.get("Category")
            cat = cat or p["category"] or sd.get("Category") or "BIP"
            row = {h: "" for h in HEADERS}
            row.update({
                "Include": "YES", "ID": k,
                "Project Name": sd.get("Project Name") or p["name_tag"] or p["titles"]["named"] or p["titles"]["single"] or p["titles"]["unnamed"] or k,
                "Unnamed Name": p["titles"]["unnamed"], "Category": cat,
                "Sector": infer_sector(k, sd.get("Project Name") or p["titles"]["named"] or p["titles"]["single"], p["titles"]["unnamed"]),
                "Version": "Named" if (sl["named"] or sl["single"]) else "Unnamed",
                "Model": sd.get("Model", ""), "Country": sd.get("Country", ""), "Currency Note": sd.get("Currency Note", ""),
                "Value (EUR Mn)": sd.get("Value (EUR Mn)", ""),
                "Named Slides": _fmt_slides(sl["named"]), "Unnamed Slides": _fmt_slides(sl["unnamed"]),
                "Common Slides": _fmt_slides(sl["single"]),
                "Notes": sd.get("Notes") or "NEW - check name / model / country / region",
            })
            pos = 0
            if prev is not None and prev in by_key:
                pos = next(i for i, r in enumerate(ordered) if r["ID"] == prev) + 1
            ordered.insert(pos, row)
            by_key[k] = row
            rep["added"].append(k)
        prev = k
    for i, r in enumerate(ordered):
        r["Sort Order"] = (i + 1) * 10
    n = 0
    for r in ordered:  # proper Sr. No.: 1, 2, 3 ... in deck order for live projects; blank for projects no longer in the deck
        if r["ID"] in deck:
            n += 1
            r["Sr. No."] = n
        else:
            r["Sr. No."] = ""
    return ordered, rep


def _style_and_write_sheet(ws, headers: List[str], rows: List[dict]) -> None:
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.formatting import ConditionalFormattingList
    ws.delete_rows(1, ws.max_row + 1)
    ws.data_validations.dataValidation = []
    ws.conditional_formatting = ConditionalFormattingList()
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    hdr_fill = PatternFill("solid", fgColor="1B3A5F")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF", name="Calibri")
        c.fill = hdr_fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
    widths = {"Sr. No.": 7, "Source / Origination": 30, "Source Notes": 50, "Include": 9, "ID": 24, "Project Name": 46, "Unnamed Name": 46, "Category": 11, "Version": 11, "Model": 14,
              "Sector": 22, "Country": 15, "Region (Unnamed)": 18, "Currency Note": 28, "Value (EUR Mn)": 12, "Named Slides": 12,
              "Unnamed Slides": 13, "Common Slides": 13, "Sort Order": 10, "Notes": 44}
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(h, 16)
    ws.freeze_panes = "E2"
    last = max(len(rows) + 1, 2) + 40  # leave room for rows the user types in by hand
    col = {h: get_column_letter(i) for i, h in enumerate(headers, 1)}
    for hname, opts in (("Include", "YES,NO"), ("Category", ",".join(CATEGORY_ORDER)), ("Version", "Named,Unnamed")):
        dv = DataValidation(type="list", formula1=f'"{opts}"', allow_blank=False, showErrorMessage=True)
        ws.add_data_validation(dv)
        dv.add(f"{col[hname]}2:{col[hname]}{last}")
    fills = {"Closed": "C8E6C9", "Active": "BBDEFB", "BIP": "FFF59D", "Hold": "FFCDD2"}
    for cat, colr in fills.items():
        ws.conditional_formatting.add(f"{col['Category']}2:{col['Category']}{last}",
                                      CellIsRule(operator="equal", formula=[f'"{cat}"'], fill=PatternFill("solid", bgColor=colr, fgColor=colr)))
    for cname in SLIDE_COLS:
        for c in ws[col[cname]][1:]:
            c.font = Font(color="808080")


def _write_slide_map(wb, name: str, scan: dict) -> None:
    from openpyxl.styles import Font, PatternFill
    if name in wb.sheetnames:
        del wb[name]
    ws = wb.create_sheet(name[:31])
    ws.append(["Slide #", "Role", "Project ID", "Version", "Title"])
    for s in scan["slides"]:
        ws.append([s["num"], s["role"], s["key"] or "", s["variant"] or "", s["title"]])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1B3A5F")
    for letter, w in zip("ABCDE", (9, 22, 28, 11, 80)):
        ws.column_dimensions[letter].width = w
    ws.freeze_panes = "A2"


INSTRUCTIONS = [
    ("EPC / INVESTOR DECK MANAGER", ""),
    ("", ""),
    ("WHAT THIS FILE IS", "One sheet per audience (EPC Registry, Investor Registry). It holds the defaults you curate: names, category, version, include."),
    ("", "Slide numbers are refreshed automatically from the base deck every time - do not edit the grey slide columns."),
    ("", ""),
    ("COLUMNS YOU CAN EDIT", ""),
    ("Include", "YES = ticked by default in the selection window. You can still change everything per client in the window."),
    ("Category", "Closed / Active / BIP / Hold. Default category; changeable per client in the window."),
    ("Version", "Named / Unnamed. Default; changeable per client. Only ONE version of a project is ever put in a deck."),
    ("Project Name / Unnamed Name", "Names printed on the auto-generated Project Index. Unnamed Name must NOT reveal the country/client."),
    ("Region (Unnamed)", "Shown in the index instead of Country when the Unnamed version is used, e.g. 'West Africa'."),
    ("Source / Origination", "Who brought the project: a person, minister, partner or influential contact. Several: separate with  /  (e.g. Walter / Yann)."),
    ("", "Leave blank when unknown. Roles and types of each source are kept in the 'Sources' sheet. Sources NEVER appear in generated decks."),
    ("Source Notes", "Where the source information came from, or a candidate you have not confirmed."),
    ("Sr. No.", "Serial number in deck order - renumbered automatically, do not type it."),
    ("", ""),
    ("TAGGING SLIDES IN THE BASE DECK (speaker notes)", ""),
    ("ID: togo_161kv_named", "The named slide of project 'togo_161kv'."),
    ("ID: togo_161kv_unnamed", "The unnamed slide of the SAME project (same key before the suffix)."),
    ("ID: icc_convention", "No suffix = one slide that is used for both versions."),
    ("CATEGORY: Active", "Optional. Only used the first time a project is seen; this sheet wins afterwards."),
    ("", ""),
    ("REPLACING A BASE DECK", "Double-click REPLACE_BASE.bat (or use the button in the app). The old deck is archived automatically."),
    ("", "Or simply overwrite the file in the base folder - everything re-syncs on the next run."),
    ("", ""),
    ("SAFETY", "Every change to this file is backed up to the 'backups' folder first. If Excel has the file open the tool still works (it just skips saving)."),
]


def _write_instructions(wb) -> None:
    from openpyxl.styles import Font
    if "Instructions" in wb.sheetnames:
        del wb["Instructions"]
    ws = wb.create_sheet("Instructions", 0)
    for a, b in INSTRUCTIONS:
        ws.append([a, b])
    ws["A1"].font = Font(bold=True, size=14)
    for r in ws.iter_rows(min_col=1, max_col=1):
        if r[0].value and (r[0].value.isupper() or r[0].value.startswith(("COLUMNS", "TAGGING"))):
            r[0].font = Font(bold=True)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 120


def _backup_registry() -> Optional[Path]:
    if not REGISTRY_XLSX.exists():
        return None
    BACKUP_DIR.mkdir(exist_ok=True)
    dst = BACKUP_DIR / f"projects_registry_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    shutil.copy2(REGISTRY_XLSX, dst)
    keep = int(load_config().get("backups_to_keep", 15))
    olds = sorted(BACKUP_DIR.glob("projects_registry_*.xlsx"))
    for o in olds[:-keep] if keep > 0 else []:
        try:
            o.unlink()
        except Exception:
            pass
    return dst


def _normalised(rows: List[dict], headers: List[str]) -> List[List[str]]:
    return [[_s(r.get(h)) for h in headers] for r in rows]


def sync(audiences: Optional[List[str]] = None, verbose: bool = True, write: bool = True) -> dict:
    """
    Scan every audience's base deck, merge with the registry, and (if write) save the registry.
    Returns {audience: {"scan","rows","report"}, "_saved": bool, "_notes": [...]}.
    Never raises because Excel is open - it just skips the save and says so.
    """
    cfg = load_config()
    names = list(dict.fromkeys(primary(n) for n in (audiences or list(cfg["audiences"].keys()))))
    wb = _open_registry()
    fresh = REGISTRY_XLSX.exists() is False
    legacy = _old_registry_seed(wb)
    out: dict = {"_notes": []}
    changed = False
    existing_sources = sourcesheet.read(wb)
    known_sources = {s["name"].lower(): s["name"] for s in existing_sources}

    for aud in names:
        a = cfg["audiences"][aud]
        bp = ROOT / a["base"]
        if not bp.exists():
            out["_notes"].append(f"[{aud}] base deck missing: {bp}  (skipped)")
            continue
        scan = scan_base(bp, cfg.get("sensitive_terms"))
        sheet = a["sheet"][:31]
        headers_old, rows_old = _read_sheet(wb, sheet)
        seeded = not rows_old and bool(legacy)
        old_snapshot = [dict(r) for r in rows_old]  # merge_registry edits rows in place - compare against a copy
        rows, rep = merge_registry(scan, rows_old, legacy if seeded else None,
                                   seed_category_wins=(seeded and bool(a.get("seed_category_from_legacy_excel"))))
        for r in rows:  # one spelling per source everywhere (the one in the Sources sheet)
            r["Source / Origination"] = sourcesheet.canon(r.get("Source / Origination"), known_sources)
        extra = [h for h in headers_old if h and h not in HEADERS]
        headers = HEADERS + extra
        if sheet not in wb.sheetnames or _normalised(rows, headers) != _normalised(old_snapshot, headers) or \
                [h for h in headers_old if h] != headers:
            changed = True
            if sheet in wb.sheetnames:
                ws = wb[sheet]
            else:
                ws = wb.create_sheet(sheet)
            _style_and_write_sheet(ws, headers, rows)
        _write_slide_map(wb, f"Slide Map - {aud}", scan)
        out[aud] = {"scan": scan, "rows": rows, "report": rep, "seeded": seeded}

    live = [r for aud_ in names if aud_ in out for r in out[aud_]["rows"] if str(r.get("Sr. No.", "")) != ""]
    src_rows, src_changed = sourcesheet.build(existing_sources, live)
    out["_sources"] = src_rows

    if write:
        if src_changed or sourcesheet.SHEET not in wb.sheetnames:
            sourcesheet.write(wb, src_rows)
            changed = True
        if audiences is None:  # full sync only: legacy sheets have been migrated into every audience
            for junk in ("Projects Registry", "Slide Map (Base)", "Sheet"):
                if junk in wb.sheetnames and all(cfg["audiences"][n]["sheet"][:31] in wb.sheetnames for n in names
                                                 if (ROOT / cfg["audiences"][n]["base"]).exists()):
                    del wb[junk]
        if "Category Legend" in wb.sheetnames:
            del wb["Category Legend"]
        _write_instructions(wb)
        # keep sheet order tidy: Instructions, registries, slide maps
        order = ["Instructions"] + [cfg["audiences"][n]["sheet"][:31] for n in names] + [sourcesheet.SHEET] + \
                [f"Slide Map - {n}" for n in names]
        for stale in [w for w in wb.sheetnames if w not in order and (w.endswith(" Registry") or w.startswith("Slide Map - "))]:
            del wb[stale]  # sheets of audiences that now share another audience's deck
            changed = True
        wb._sheets = [wb[n] for n in order if n in wb.sheetnames] + [w for w in wb._sheets if w.title not in order]
        wb.active = 1 if len(wb.sheetnames) > 1 else 0
        saved = False
        if changed or fresh:
            try:
                if REGISTRY_XLSX.exists():
                    _backup_registry()
                tmp = REGISTRY_XLSX.with_suffix(".tmp.xlsx")
                wb.save(tmp)
                os.replace(tmp, REGISTRY_XLSX)
                saved = True
            except PermissionError:
                out["_notes"].append("projects_registry.xlsx is open in Excel - changes NOT saved this time "
                                     "(the app still works from the base deck). Close Excel to save.")
                try:
                    tmp.unlink()
                except Exception:
                    pass
            except Exception as exc:
                out["_notes"].append(f"Could not save projects_registry.xlsx ({exc}); continuing without saving.")
        out["_saved"] = saved
    if verbose:
        for aud in names:
            if aud not in out:
                continue
            sc, rep = out[aud]["scan"], out[aud]["report"]
            print(f"[{aud}] {len(sc['projects'])} projects, {sc['n_slides']} slides in {Path(sc['path']).name}")
            print(f"   boilerplate: {sc['boilerplate']}  closing: {sc['closing']}  dividers dropped: {sorted(sc['dividers'])}")
            for k in rep["added"]:
                print(f"   + NEW      {k}")
            for k, o, n in rep["moved"]:
                print(f"   ~ slides   {k}: {o} -> {n}")
            for k in rep["removed"]:
                print(f"   - REMOVED  {k} (Include set to NO)")
            for r in rep["repaired"]:
                print(f"   ~ repaired {r}")
            for w in sc["warnings"]:
                print(f"   ! {w}")
        for n in out["_notes"]:
            print("  *", n)
    return out


# --------------------------------------------------------------------------- loading projects for the UI / generator
def load_projects(audience: str, do_sync: bool = True, include_retired: bool = False) -> dict:
    """
    Returns {"projects": [...], "scan": scan, "notes": [...], "warnings": [...]}.
    Each project: id, name, unnamed_name, category, version, include, model, country, region, currency_note,
                  notes, slides{named,unnamed,single}, has_named, has_unnamed, leaks[], sort
    """
    cfg = load_config()
    if audience not in cfg["audiences"]:
        raise DeckError(f"Unknown audience '{audience}'.")
    res = sync([audience] if not do_sync else None, verbose=False, write=do_sync)
    audience = primary(audience)
    if audience not in res:
        raise DeckError(f"No base deck for '{audience}'.\nExpected: {ROOT / cfg['audiences'][audience]['base']}\n"
                        f"Use 'Replace base deck' to add one.")
    scan, rows = res[audience]["scan"], res[audience]["rows"]
    deck = {p["key"]: p for p in scan["projects"]}
    projects = []
    for r in rows:
        k = r["ID"]
        if k not in deck or (deck[k]["retired"] and not include_retired):
            continue
        sl = deck[k]["slides"]
        un_slides = sl["unnamed"] or sl["single"]
        projects.append({
            "id": k, "name": _s(r["Project Name"]) or k,
            "unnamed_name": _s(r.get("Unnamed Name")) or _s(r["Project Name"]) or k,
            "category": r["Category"], "version": r["Version"], "include": norm_include(r["Include"]),
            "model": modelnames.norm(_s(r.get("Model"))), "country": _s(r.get("Country")), "sector": _s(r.get("Sector")) or "Mixed / Other",
            "sr": r.get("Sr. No.", ""), "source": _s(r.get("Source / Origination")),
            "sources": sourcesheet.split_sources(r.get("Source / Origination")), "source_notes": _s(r.get("Source Notes")),
            "region": _s(r.get("Region (Unnamed)")),
            "currency_note": _s(r.get("Currency Note")), "notes": _s(r.get("Notes")),
            "slides": sl, "has_named": bool(sl["named"] or sl["single"]), "has_unnamed": bool(sl["unnamed"] or sl["single"]),
            "leaks": project_leaks(scan, un_slides, _s(r.get("Country")), cfg) if sl["unnamed"] else [],
            "sort": int(r.get("Sort Order") or 0), "retired": deck[k]["retired"],
            "has_value": any(s["has_value"] for s in scan["slides"]
                             if s["key"] == k and s["variant"] in ("named", "unnamed", "single")),
        })
    projects.sort(key=lambda p: p["sort"])
    warnings = list(scan["warnings"])
    for p in projects:
        if p["leaks"]:
            warnings.append(f"UNNAMED slide of '{p['id']}' contains: {', '.join(p['leaks'])}  - check it before sending.")
    return {"projects": projects, "scan": scan, "notes": res["_notes"], "warnings": warnings,
            "sources_info": res.get("_sources", []),
            "report": res[audience]["report"], "saved": res.get("_saved", False)}


def default_selection(projects: List[dict]) -> List[dict]:
    return [{"id": p["id"], "category": p["category"], "version": p["version"]} for p in projects if p["include"]]


# --------------------------------------------------------------------------- saving defaults / presets
def save_defaults(audience: str, selections: List[dict], all_ids: List[str]) -> bool:
    """Write Include / Category / Version back into the registry sheet. Returns False if Excel is locked."""
    a = audience_cfg(audience)
    wb = _open_registry()
    sheet = a["sheet"][:31]
    if sheet not in wb.sheetnames:
        return False
    ws = wb[sheet]
    headers = [_s(c.value) for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(headers) if h}
    chosen = {s["id"]: s for s in selections}
    for r in range(2, ws.max_row + 1):
        pid = norm_id(ws.cell(r, col["ID"]).value or "")
        if pid not in all_ids:
            continue
        s = chosen.get(pid)
        ws.cell(r, col["Include"]).value = "YES" if s else "NO"
        if s:
            ws.cell(r, col["Category"]).value = s["category"]
            ws.cell(r, col["Version"]).value = s["version"]
    try:
        _backup_registry()
        tmp = REGISTRY_XLSX.with_suffix(".tmp.xlsx")
        wb.save(tmp)
        os.replace(tmp, REGISTRY_XLSX)
        return True
    except PermissionError:
        _rm(REGISTRY_XLSX.with_suffix(".tmp.xlsx"))
        return False


def _preset_path(audience: str, client: Optional[str]) -> Path:
    return PRESET_DIR / (f"{safe_filename(audience)}__{safe_filename(client)}.json" if client else f"{safe_filename(audience)}__LAST.json")


def save_preset(audience: str, client: str, selections: List[dict]) -> None:
    try:
        PRESET_DIR.mkdir(exist_ok=True)
        data = json.dumps({"audience": audience, "client": client, "saved": datetime.now().isoformat(timespec="seconds"),
                           "selections": selections}, indent=2, ensure_ascii=False)
        _preset_path(audience, None).write_text(data, encoding="utf-8")
        if client:
            _preset_path(audience, client).write_text(data, encoding="utf-8")
    except Exception:
        pass  # presets are a convenience; never fail a build over them


def load_preset(audience: str, client: Optional[str]) -> Optional[dict]:
    p = _preset_path(audience, client)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------- building slides (python-pptx)
def _fonts():
    from pptx.dml.color import RGBColor
    return {
        "NAVY": RGBColor(0x1B, 0x3A, 0x5F), "DARK": RGBColor(0x2C, 0x3E, 0x50), "WHITE": RGBColor(0xFF, 0xFF, 0xFF),
        "GREY": RGBColor(0x78, 0x90, 0x9C), "LIGHT": RGBColor(0xB0, 0xBE, 0xC5),
        "COLORS": {"Closed": RGBColor(0x2E, 0x7D, 0x32), "Active": RGBColor(0x15, 0x65, 0xC0),
                   "BIP": RGBColor(0xF9, 0xA8, 0x25), "Hold": RGBColor(0xC6, 0x28, 0x28)},
    }


CATEGORY_SUBTITLES = {
    "Closed": "Financial Closure done by us  ·  Debt arranged & closed  ·  EPC delivery underway",
    "Active": "Live pipeline  ·  Studies complete  ·  Negotiation / structuring in progress",
    "BIP": "Business In Pipeline  ·  Early-stage  ·  Concept & proposal stage",
    "Hold": "Temporarily paused  ·  Pending funding, politics or client decision",
}


def _blank_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    for shape in list(slide.shapes):
        shape._element.getparent().remove(shape._element)
    return slide


def _text(slide, x, y, w, h, text, size, color, bold=False, wrap=True):
    from pptx.util import Inches, Pt
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.text = text
    p.font.size, p.font.color.rgb, p.font.bold, p.font.name = Pt(size), color, bold, "Calibri"
    return tb


def add_category_divider(prs, category: str, count: int, footer: str) -> None:
    from pptx.util import Inches, Pt
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    F = _fonts()
    slide = _blank_slide(prs)
    sw, sh = prs.slide_width, prs.slide_height
    colr = F["COLORS"].get(category, F["NAVY"])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, sw, sh)
    bg.fill.solid(); bg.fill.fore_color.rgb = F["NAVY"]; bg.line.fill.background()
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, sw, Inches(0.12))
    bar.fill.solid(); bar.fill.fore_color.rgb = colr; bar.line.fill.background()
    _text(slide, 0.8, 2.4, 11.7, 0.4, "TRANSACTION CATEGORY", 12, F["GREY"], True)
    _text(slide, 0.8, 2.85, 11.7, 1.0, "BIP — Business In Pipeline" if category == "BIP" else f"{category} Transactions", 40, F["WHITE"], True)
    _text(slide, 0.8, 3.95, 11.7, 0.5, CATEGORY_SUBTITLES.get(category, ""), 16, F["LIGHT"])
    badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.0), Inches(2.4), Inches(0.55))
    badge.fill.solid(); badge.fill.fore_color.rgb = colr; badge.line.fill.background()
    try:
        badge.adjustments[0] = 0.15
    except Exception:
        pass
    p = badge.text_frame.paragraphs[0]
    p.text = f"{count} project{'s' if count != 1 else ''}"
    p.font.size, p.font.color.rgb, p.font.bold, p.font.name = Pt(14), F["WHITE"], True, "Calibri"
    p.alignment = PP_ALIGN.CENTER
    _text(slide, 0.8, 6.9, 11.7, 0.3, footer, 10, F["GREY"])


def add_index_slides(prs, items: List[dict], client: str, footer: str) -> None:
    """Project index. Flows into columns and extra slides as needed - nothing is ever cut off."""
    from pptx.util import Inches, Pt
    from pptx.enum.shapes import MSO_SHAPE
    F = _fonts()
    ROW_H, HEAD_H, TOP, BOTTOM, N_COLS = 0.42, 0.5, 1.2, 6.95, 3
    col_w = 12.3 / N_COLS
    by_cat = {c: [] for c in CATEGORY_ORDER}
    for it in items:
        by_cat[it["category"]].append(it)

    # flatten into blocks: ("head", cat, n, cont) / ("row", item, idx)
    blocks = []
    for cat in CATEGORY_ORDER:
        for i, it in enumerate(by_cat[cat], 1):
            blocks.append(("row", cat, it, i))
    pages: List[List[Tuple[int, float, tuple]]] = [[]]
    col, y = 0, TOP
    last_cat_in_col = None

    def new_col():
        nonlocal col, y, last_cat_in_col
        col += 1
        y = TOP
        last_cat_in_col = None
        if col >= N_COLS:
            pages.append([])
            col = 0

    one_per_col = sum(1 for c in CATEGORY_ORDER if by_cat[c]) <= N_COLS
    for kind, cat, it, idx in blocks:
        if one_per_col and last_cat_in_col is not None and last_cat_in_col != cat:
            new_col()  # each category gets its own column
        need = ROW_H + (HEAD_H if last_cat_in_col != cat else 0)
        if y + need > BOTTOM:
            new_col()
            need = ROW_H + HEAD_H
        if last_cat_in_col != cat:
            pages[-1].append((col, y, ("head", cat, len(by_cat[cat]), idx > 1)))
            y += HEAD_H
            last_cat_in_col = cat
        pages[-1].append((col, y, ("row", cat, it, idx)))
        y += ROW_H

    total = len(items)
    for pg_no, page in enumerate(pages, 1):
        if not page:
            continue
        slide = _blank_slide(prs)
        sw = prs.slide_width
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, sw, Inches(0.9))
        bar.fill.solid(); bar.fill.fore_color.rgb = F["NAVY"]; bar.line.fill.background()
        suffix = f"  ({pg_no}/{len([p for p in pages if p])})" if len([p for p in pages if p]) > 1 else ""
        _text(slide, 0.5, 0.18, 10, 0.5, "PROJECT INDEX" + suffix, 22, F["WHITE"], True)
        _text(slide, 0.5, 0.55, 12, 0.3, f"Prepared for  {client}  ·  {total} opportunit{'ies' if total != 1 else 'y'}", 11, F["LIGHT"])
        for c, yy, blk in page:
            x = 0.5 + c * col_w
            if blk[0] == "head":
                _, cat, n, cont = blk
                pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(yy), Inches(min(col_w - 0.3, 3.0)), Inches(0.36))
                pill.fill.solid(); pill.fill.fore_color.rgb = F["COLORS"][cat]; pill.line.fill.background()
                try:
                    pill.adjustments[0] = 0.2
                except Exception:
                    pass
                p = pill.text_frame.paragraphs[0]
                p.text = f"  {cat.upper()}  ({n})" + ("  – cont." if cont else "")
                p.font.size, p.font.color.rgb, p.font.bold, p.font.name = Pt(11), F["WHITE"], True, "Calibri"
            else:
                _, cat, it, idx = blk
                tb = slide.shapes.add_textbox(Inches(x), Inches(yy), Inches(col_w - 0.25), Inches(ROW_H - 0.05))
                tf = tb.text_frame
                tf.word_wrap = True
                tf.margin_top = tf.margin_bottom = 0
                p = tf.paragraphs[0]
                p.text = f"{idx}.  {clip(it['display_name'], 120)}"
                p.font.size, p.font.color.rgb, p.font.bold, p.font.name = Pt(10), F["DARK"], True, "Calibri"
        _text(slide, 0.5, 7.1, 12, 0.25, footer, 9, F["LIGHT"])



def _replace_in_paragraph(p_el, rx, repl) -> int:
    from pptx.oxml.ns import qn
    runs = [t for t in p_el.iter(qn("a:t"))]
    if not runs:
        return 0
    joined = "".join(t.text or "" for t in runs)
    if not rx.search(joined):
        return 0
    n = 0
    for t in runs:  # normal case: placeholder sits inside one run (keeps all formatting)
        if t.text and rx.search(t.text):
            t.text = rx.sub(repl, t.text)
            n += 1
    if rx.search("".join(t.text or "" for t in runs)):  # placeholder was split across runs
        joined = "".join(t.text or "" for t in runs)
        runs[0].text = rx.sub(repl, joined)
        for t in runs[1:]:
            t.text = ""
        n += 1
    return n


def replace_client_name(prs, client: str, placeholders: List[str]) -> int:
    from pptx.oxml.ns import qn
    phs = [p for p in placeholders if p]
    if not phs:
        return 0
    rx = re.compile("|".join(re.escape(p) for p in phs), re.I)

    def repl(m):
        return client.upper() if (m.group(0).isupper() and len(m.group(0)) > 1) else client
    count = 0
    for slide in prs.slides:
        for p_el in slide._element.iter(qn("a:p")):
            count += _replace_in_paragraph(p_el, rx, repl)
    cp = prs.core_properties
    for attr in ("title", "subject", "keywords", "comments", "category"):
        try:
            v = getattr(cp, attr)
            if v and rx.search(v):
                setattr(cp, attr, rx.sub(repl, v))
        except Exception:
            pass
    return count


def _strip_sections(prs) -> None:
    """Sections / custom shows point at slide ids we remove - drop them or PowerPoint asks to 'repair'."""
    from pptx.oxml.ns import qn
    root = prs.part._element
    for ext in list(root.iter(qn("p:ext"))):
        if any("sectionLst" in c.tag for c in ext):
            ext.getparent().remove(ext)
    for el in list(root.iter(qn("p:custShowLst"))):
        el.getparent().remove(el)


# --------------------------------------------------------------------------- the generator
def generate(audience: str, client: str, selections: List[dict], log: Callable[[str], None] = print,
             output_dir: Optional[Path] = None, remember: bool = True) -> dict:
    """
    selections: [{"id","category","version"}]  (version: Named | Unnamed)
    Returns {"path","warnings","manifest","n_slides"}.   Raises DeckError for anything the user must fix.
    """
    from pptx import Presentation
    from pptx.oxml.ns import qn

    cfg = load_config()
    client = " ".join(_s(client).split()) or "Client"
    data = load_projects(audience, include_retired=True)
    projects = {p["id"]: p for p in data["projects"]}
    scan = data["scan"]
    warnings: List[str] = []

    items, seen = [], set()
    for s in selections:
        pid = norm_id(s.get("id", ""))
        if pid in seen:
            warnings.append(f"'{pid}' was selected twice - used once.")
            continue
        seen.add(pid)
        p = projects.get(pid)
        if p and p.get("retired"):
            warnings.append(f"'{p['name']}' is RETIRED - skipped.")
            continue
        if not p:
            warnings.append(f"'{pid}' is not in the {audience} base deck - skipped.")
            continue
        cat = norm_category(s.get("category")) or p["category"]
        want = norm_version(s.get("version")) or p["version"]
        sl = p["slides"]
        if want == "Unnamed":
            slides, used = (sl["unnamed"] or sl["single"]), "Unnamed"
            if not slides:
                warnings.append(f"SKIPPED '{p['name']}': Unnamed requested but it has no unnamed slide "
                                f"(sending the named slide would reveal it).")
                continue
        else:
            slides, used = (sl["named"] or sl["single"]), "Named"
            if not slides:
                slides, used = sl["unnamed"], "Unnamed"
                warnings.append(f"'{p['name']}' has no named slide - the unnamed one was used.")
        if used == "Unnamed" and p["leaks"]:
            warnings.append(f"CHECK '{p['name']}' (unnamed slide): still contains {', '.join(p['leaks'])}")
        unnamed_used = used == "Unnamed" and bool(sl["unnamed"])
        region = p["region"]
        meta_loc = (region or "") if unnamed_used else p["country"]
        items.append({
            "id": pid, "category": cat, "version": used, "slides": slides, "proj": p,
            "show_value": bool(s.get("show_value", False)),
            "display_name": p["unnamed_name"] if unnamed_used else p["name"],
            "meta": [m for m in (meta_loc, p["model"], p["currency_note"]) if m and m.strip().upper() != "TBD"],
            "sort": p["sort"],
        })
    if not items:
        raise DeckError("No projects selected (or none could be used).\n" + "\n".join(warnings))
    items.sort(key=lambda it: (CATEGORY_ORDER.index(it["category"]), it["sort"]))

    bp = base_path(audience)
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = audience_cfg(audience)["file_tag"]
    final = out_dir / f"{safe_filename(client)}_{tag}.pptx"
    tmp = out_dir / f".building_{os.getpid()}_{int(time.time())}.pptx"

    log(f"\nBuilding {audience} deck for: {client}")
    log(f"Projects: {len(items)}")
    try:
        shutil.copy2(bp, tmp)
    except PermissionError:
        raise DeckError(f"The base deck is locked:\n{bp}\nClose it in PowerPoint and try again.")

    try:
        prs = Presentation(str(tmp))
        n_orig = len(prs.slides)
        if n_orig != scan["n_slides"]:
            raise DeckError("The base deck changed while it was being read. Please run again.")
        sld = prs.slides._sldIdLst
        orig_rid = {i + 1: sld[i].get(qn("r:id")) for i in range(n_orig)}

        by_cat = {c: [it for it in items if it["category"] == c] for c in CATEGORY_ORDER}
        footer = cfg.get("footer", "")

        before = set(el.get(qn("r:id")) for el in sld)
        add_index_slides(prs, items, client, footer)
        sld = prs.slides._sldIdLst
        index_rids = [el.get(qn("r:id")) for el in sld if el.get(qn("r:id")) not in before]
        div_rid = {}
        for cat in CATEGORY_ORDER:
            if by_cat[cat]:
                add_category_divider(prs, cat, len(by_cat[cat]), footer)
                div_rid[cat] = list(prs.slides._sldIdLst)[-1].get(qn("r:id"))
        sld = prs.slides._sldIdLst
        rid_el = {el.get(qn("r:id")): el for el in sld}

        order: List[str] = []
        order += [orig_rid[n] for n in scan["boilerplate"] if n in orig_rid]
        order += index_rids
        used_slides = []
        for cat in CATEGORY_ORDER:
            if cat in div_rid:
                order.append(div_rid[cat])
                for it in by_cat[cat]:
                    for n in it["slides"]:
                        if n in orig_rid and n not in used_slides:
                            order.append(orig_rid[n])
                            used_slides.append(n)
        order += [orig_rid[n] for n in scan["closing"] if n in orig_rid]

        seen_r, ordered = set(), []
        for r in order:
            if r in rid_el and r not in seen_r:
                ordered.append(r)
                seen_r.add(r)
        for el in list(sld):
            sld.remove(el)
        for r in ordered:
            sld.append(rid_el[r])
        for r in rid_el:
            if r not in seen_r:
                try:
                    prs.part.drop_rel(r)
                except Exception:
                    pass
        _strip_sections(prs)
        n_val = 0
        for it in items:
            if not it["show_value"]:
                for n_ in it["slides"]:
                    if n_ in orig_rid:
                        n_val += _strip_value_shapes(prs.part.related_part(orig_rid[n_]).slide)
        if n_val:
            log(f"  indicative value hidden on {n_val} slide(s)")

        n = replace_client_name(prs, client, cfg.get("client_placeholders", []))
        log(f"  client name set in {n} text run(s)")
        if n == 0:
            warnings.append(f"The client placeholder ({', '.join(cfg.get('client_placeholders', []))}) was not found in the "
                            f"deck, so the client name only appears on the Project Index.")
        for slide in prs.slides:  # tags must never reach a recipient
            if slide.has_notes_slide:
                try:
                    tf = slide.notes_slide.notes_text_frame
                    if tf is not None:
                        tf.text = ""
                except Exception:
                    pass
        clean_metadata(prs, client, len(ordered), cfg)
        prs.save(str(tmp))

        # ---- verify the file we just wrote, before it replaces anything
        chk = Presentation(str(tmp))
        expected = len(ordered)
        if len(chk.slides) != expected:
            raise DeckError(f"Self-check failed: expected {expected} slides, file has {len(chk.slides)}.")
        for w in source_name_hits(chk, data.get("sources_info", [])):
            warnings.append(w)
        leftovers = [i for i, s in enumerate(chk.slides, 1) if s.has_notes_slide and _notes(s).strip()]
        if leftovers:
            raise DeckError(f"Self-check failed: speaker notes still present on slides {leftovers}.")
        if len(used_slides) != len(set(used_slides)):
            raise DeckError("Self-check failed: a slide was used twice.")

        try:
            os.replace(tmp, final)
        except PermissionError:
            alt = out_dir / f"{safe_filename(client)}_{tag}_{datetime.now():%H%M%S}.pptx"
            os.replace(tmp, alt)
            warnings.append(f"'{final.name}' is open in PowerPoint, so the deck was saved as '{alt.name}' instead.")
            final = alt
    except DeckError:
        _rm(tmp)
        raise
    except Exception as exc:
        _rm(tmp)
        raise DeckError(f"Unexpected problem while building the deck: {exc}")

    manifest = []
    for cat in CATEGORY_ORDER:
        if by_cat[cat]:
            manifest.append(f"{cat} ({len(by_cat[cat])})")
            for it in by_cat[cat]:
                manifest.append(f"    - {it['display_name']}  [{it['version']}{', value shown' if it['show_value'] else ''}]  slides {','.join(map(str, it['slides']))}")
    for line in manifest:
        log("  " + line)
    for w in warnings:
        log("  ! " + w)
    log(f"\nOK -> {final}\n   {expected} slides")
    if remember:
        save_preset(audience, client, [{"id": it["id"], "category": it["category"], "version": it["version"], "show_value": it["show_value"]} for it in items])
    return {"path": str(final), "warnings": warnings, "manifest": manifest, "n_slides": expected}


def source_name_hits(prs, sources_info: List[dict]) -> List[str]:
    """Sources are internal: warn if any source name (or the bracketed company, e.g. RAMCO) appears on a slide of a deck."""
    terms: Dict[str, str] = {}
    for s in sources_info:
        name = s.get("name", "")
        base = re.sub(r"\s*\(.*?\)", "", name).strip()
        inner = re.findall(r"\((.*?)\)", name)
        for t in [base] + inner:
            t = t.strip()
            if len(t) >= 3:
                terms.setdefault(t, name)
    hits: Dict[str, List[int]] = {}
    for i, slide in enumerate(prs.slides, 1):
        text = _slide_text(slide)
        for t in terms:
            flags = 0 if len(t) <= 4 else re.I  # short names are matched case-sensitively (e.g. 'Arm' vs the word 'arm')
            if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, flags):
                hits.setdefault(t, []).append(i)
    return [f"SOURCE NAME '{t}' appears on slide(s) {', '.join(map(str, sl[:6]))} of this deck - sources are internal, remove it before sending."
            for t, sl in hits.items()]


def _rm(p: Path) -> None:
    try:
        p.unlink()
    except Exception:
        pass


# --------------------------------------------------------------------------- replacing a base deck
def replace_base(audience: str, new_file: str, log: Callable[[str], None] = print) -> dict:
    """Validate a new deck, archive the current base, install the new one, re-sync Excel."""
    src = Path(new_file).expanduser()
    dst = base_path(audience)
    if not src.exists():
        raise DeckError(f"File not found:\n{src}")
    if src.suffix.lower() != ".pptx":
        raise DeckError("Please choose a .pptx file (save .ppt / .potx as .pptx first).")
    try:
        if dst.exists() and src.resolve() == dst.resolve():
            raise DeckError("That is already the active base deck.")
    except OSError:
        pass
    scan = scan_base(src)
    if not scan["projects"]:
        raise DeckError("This deck has no tagged project slides, so nothing could be selected from it.\n"
                        "Put 'ID: some_project_named' / 'ID: some_project_unnamed' in each project slide's speaker notes\n"
                        "(see HOW_TO_TAG_IN_PPTX.txt), then try again.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    archived = None
    if dst.exists():
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archived = ARCHIVE_DIR / f"{dst.stem}_{datetime.now():%Y%m%d_%H%M%S}.pptx"
        shutil.copy2(dst, archived)
    tmp = dst.with_suffix(".incoming.pptx")
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    except PermissionError:
        _rm(tmp)
        raise DeckError(f"The current base deck is locked (open in PowerPoint?):\n{dst}\nClose it and try again.")
    res = sync([audience], verbose=False)
    rep = res[primary(audience)]["report"]
    log(f"Base deck for {audience} replaced ({len(scan['projects'])} projects, {scan['n_slides']} slides).")
    if archived:
        log(f"Previous version archived: {archived.name}")
    for k in rep["added"]:
        log(f"  + new project   {k}")
    for k in rep["removed"]:
        log(f"  - removed       {k}")
    for w in scan["warnings"]:
        log(f"  ! {w}")
    return {"scan": scan, "report": rep, "archived": str(archived) if archived else None, "warnings": scan["warnings"]}


# --------------------------------------------------------------------------- removing projects from a base deck
def remove_projects(audience: str, keys: List[str], log: Callable[[str], None] = print) -> dict:
    """Delete every slide of the given project keys from the base deck (old deck archived, registry rows removed)."""
    from pptx.oxml.ns import qn
    audience = primary(audience)
    dst = base_path(audience)
    keys = [norm_id(k) for k in keys]
    scan = scan_base(dst)
    known = {p["key"]: p for p in scan["projects"]}
    missing = [k for k in keys if k not in known]
    if missing:
        raise DeckError(f"Not in the base deck: {', '.join(missing)}")
    nums = sorted({n for k in keys for v in known[k]["slides"].values() for n in v})
    prs = _open_presentation(dst)
    lst = prs.slides._sldIdLst
    before = len(lst)
    for n in sorted(nums, reverse=True):
        el = lst[n - 1]
        prs.part.drop_rel(el.get(qn("r:id")))
        lst.remove(el)
    _strip_sections(prs)
    tmp = dst.with_suffix(".removing.pptx")
    try:
        prs.save(str(tmp))
        chk = _open_presentation(tmp)
        if len(chk.slides) != before - len(nums):
            raise DeckError("Self-check failed after removing slides; the base deck was not changed.")
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archived = ARCHIVE_DIR / f"{dst.stem}_{datetime.now():%Y%m%d_%H%M%S}_before_removing_{'_'.join(keys)[:40]}.pptx"
        shutil.copy2(dst, archived)
        os.replace(tmp, dst)
    except PermissionError:
        _rm(tmp)
        raise DeckError(f"The base deck is locked (open in PowerPoint?):\n{dst}\nClose it and try again.")
    except DeckError:
        _rm(tmp)
        raise
    sync([audience], verbose=False)
    wb = _open_registry()
    ws = wb[audience_cfg(audience)["sheet"][:31]]
    idcol = [_s(c.value) for c in ws[1]].index("ID") + 1
    for r in range(ws.max_row, 1, -1):
        if norm_id(ws.cell(r, idcol).value or "") in keys:
            ws.delete_rows(r)
    try:
        _backup_registry()
        t2 = REGISTRY_XLSX.with_suffix(".tmp.xlsx")
        wb.save(t2)
        os.replace(t2, REGISTRY_XLSX)
    except PermissionError:
        _rm(REGISTRY_XLSX.with_suffix(".tmp.xlsx"))
        log("  (registry row left in Excel marked 'not in base deck' - Excel was open)")
    log(f"Removed {', '.join(keys)} (slides {nums}). Base now {before - len(nums)} slides. Previous deck archived: {archived.name}")
    return {"removed_slides": nums, "archived": str(archived)}


# --------------------------------------------------------------------------- hidden file data of generated decks
def clean_metadata(prs, client: str, n_slides: int, cfg: dict) -> None:
    """Remove everything in the file that still describes the BASE deck (title, preview thumbnail, stale counts)."""
    cp = prs.core_properties
    cp.title = (cfg.get("doc_title") or "Partnership Opportunities").replace("{client}", client)
    cp.subject = ""
    cp.comments = ""
    cp.keywords = ""
    cp.category = ""
    if cfg.get("doc_author"):
        cp.author = cfg["doc_author"]
    cp.last_modified_by = cp.author or ""
    cp.revision = 1
    pkg = prs.part.package
    for rid, rel in list(pkg._rels.items()):  # preview thumbnail = picture of the base deck's title slide
        if rel.reltype.endswith("/thumbnail"):
            pkg._rels.pop(rid)
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
           '<TotalTime>0</TotalTime><Application>Microsoft Office PowerPoint</Application>'
           '<PresentationFormat>Widescreen</PresentationFormat><Slides>%d</Slides><Notes>0</Notes>'
           '<HiddenSlides>0</HiddenSlides></Properties>' % n_slides)
    for part in pkg.iter_parts():
        if str(part.partname) == "/docProps/app.xml":
            part._blob = app.encode("utf-8")


# --------------------------------------------------------------------------- keeping the app in step with the base deck
def base_state(audience: str):
    """(mtime_ns, size) of the base deck - the app polls this to notice that you saved / replaced it."""
    try:
        st = base_path(audience).stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def base_readable(audience: str) -> bool:
    """False while PowerPoint (or OneDrive) still holds the file."""
    try:
        with open(base_path(audience), "rb") as f:
            f.read(4)
        return True
    except OSError:
        return False


def suggest_key(title: str) -> str:
    t = re.sub(r"^[^—–-]{0,30}[—–-]\s*", "", title) if re.match(r"^[^—–-]{0,30}[—–-]", title) else title
    return norm_id(t)[:36].strip("_")


def untagged_slides(audience: str) -> List[dict]:
    """Slides with no 'ID:' in their notes (what the 'Tag new slides' window lists)."""
    scan = scan_base(base_path(primary(audience)))
    return [{"num": s["num"], "title": s["title"], "role": s["role"], "suspect": s["num"] in scan["suspect"],
             "key_hint": suggest_key(s["title"])} for s in scan["slides"] if not s["key"]]


def set_slide_notes(prs, slide, text: str, append: bool = True) -> None:
    """Write notes text; works even when the notes master has no body placeholder (borrows a tagged slide's structure)."""
    import copy as _copy
    from pptx.oxml.ns import qn
    ns = slide.notes_slide
    if ns.notes_text_frame is None:
        donor = next((s for s in prs.slides if s.has_notes_slide and s.notes_slide.notes_text_frame is not None), None)
        if donor is None:
            raise DeckError("This deck has no usable speaker-notes layout; add a note to any slide in PowerPoint once, then retry.")
        keep = (qn("p:nvGrpSpPr"), qn("p:grpSpPr"))
        dst, src = ns.shapes._spTree, donor.notes_slide.shapes._spTree
        for ch in list(dst):
            if ch.tag not in keep:
                dst.remove(ch)
        for ch in src:
            if ch.tag not in keep:
                dst.append(_copy.deepcopy(ch))
        ns.notes_text_frame.text = ""
    tf = ns.notes_text_frame
    # drop any existing tag lines (ID / CATEGORY / NAME / TYPE / VARIANT) so a re-tag REPLACES instead of stacking
    keep_lines = [ln for ln in re.split(r"[\n\x0b]", tf.text)
                  if ln.strip() and not any(rx.search(ln) for rx in (ID_RE, CAT_RE, NAME_RE, TYPE_RE, VARIANT_RE))]
    old = "\n".join(keep_lines) if append else ""
    tf.text = "\n".join(x for x in (old, text) if x)


def all_slides(audience: str) -> List[dict]:
    """Every slide with its current tag, for the tag editor."""
    scan = scan_base(base_path(primary(audience)))
    out = []
    for s in scan["slides"]:
        cat = norm_category(s["category_raw"]) if s["category_raw"] else None
        out.append({"num": s["num"], "title": s["title"], "role": s["role"], "key": s["key"] or "",
                    "variant": s["variant"] or "", "category": cat or "", "name": s["name"] or "",
                    "tagged": bool(s["key"]) or s["type"] == "skip", "suspect": s["num"] in scan["suspect"],
                    "key_hint": suggest_key(s["title"])})
    return out


def _apply_tag_choices(audience: str, assignments: List[dict]) -> None:
    """A category / index name typed in the tag editor is an explicit choice: copy it into the registry as well
    (otherwise the registry's older value would keep winning)."""
    todo = [a for a in assignments if (a.get("variant") or "") in ("named", "unnamed", "single")
            and (norm_category(a.get("category")) or _s(a.get("name")))]
    if not todo:
        return
    try:
        wb = _open_registry()
        ws = wb[audience_cfg(audience)["sheet"][:31]]
        hdr = {_s(c.value): i + 1 for i, c in enumerate(ws[1])}
        rows = {norm_id(ws.cell(r, hdr["ID"]).value or ""): r for r in range(2, ws.max_row + 1)}
        for a in todo:
            r = rows.get(norm_id(a["key"]))
            if not r:
                continue
            if norm_category(a.get("category")):
                ws.cell(r, hdr["Category"]).value = norm_category(a["category"])
            if _s(a.get("name")):
                col = "Unnamed Name" if a["variant"] == "unnamed" else "Project Name"
                ws.cell(r, hdr[col]).value = _s(a["name"])
        _backup_registry()
        tmp = REGISTRY_XLSX.with_suffix(".tmp.xlsx")
        wb.save(tmp)
        os.replace(tmp, REGISTRY_XLSX)
    except PermissionError:
        _rm(REGISTRY_XLSX.with_suffix(".tmp.xlsx"))  # Excel open: the tag is saved in the deck; registry value unchanged


def _verify_tags(path: Path, assignments: List[dict]) -> None:
    chk = scan_base(path)
    for a in assignments:
        n, variant = int(a["num"]), (a.get("variant") or "").lower()
        s = chk["slides"][n - 1]
        if variant == "ignore":
            ok = s["type"] == "skip"
        elif variant == "remove":
            ok = not s["key"] and s["type"] is None
        else:
            ok = s["key"] == norm_id(a["key"]) and s["variant"] == variant
        if not ok:
            raise DeckError(f"Self-check failed on slide {n}; the base deck was not changed.")


def tag_slides(audience: str, assignments: List[dict], log: Callable[[str], None] = print,
               confirm_multi: bool = False) -> dict:
    """
    Write ID tags into the base deck's notes (old deck archived first).
    assignments: [{"num": 12, "key": "...", "variant": "named|unnamed|single|ignore|remove",
                   "category": "Active" | "-" (clear) , "name": "..."}]
    Every field is OPTIONAL: anything left out (None / blank) keeps the slide's CURRENT value, so changing
    one attribute never touches the others.  Raises NeedsConfirm when the change would put several slides
    on the same project version (unless confirm_multi=True).
    """
    audience = primary(audience)
    dst = base_path(audience)
    if not assignments:
        raise DeckError("Nothing to tag.")
    scan = scan_base(dst)
    by_num = {s["num"]: s for s in scan["slides"]}
    lines: Dict[int, str] = {}
    resolved: List[dict] = []
    final: Dict[int, tuple] = {s["num"]: (s["key"], s["variant"]) for s in scan["slides"] if s["key"]}
    for a in assignments:
        n, variant = int(a["num"]), (a.get("variant") or "").lower()
        if n not in by_num:
            raise DeckError(f"Slide {n} does not exist in the base deck any more - reload the list.")
        cur = by_num[n]
        if variant == "ignore":
            lines[n] = "TYPE: skip"
            final.pop(n, None)
            resolved.append({"num": n, "variant": "ignore"})
            continue
        if variant == "remove":
            lines[n] = ""
            final.pop(n, None)
            resolved.append({"num": n, "variant": "remove"})
            continue
        variant = variant or cur["variant"] or ""
        if variant not in ("named", "unnamed", "single"):
            raise DeckError(f"Slide {n}: choose its version (Named / Unnamed / Same slide for both).")
        key = norm_id(a.get("key") or "") or (cur["key"] or "")
        if not key or SUFFIX_RE.match(key):
            raise DeckError(f"Slide {n}: enter a project key without '_named'/'_unnamed' (e.g. kenya_solar_50mw).")
        if a.get("category") == "-":
            cat = None
        else:
            cat = norm_category(a.get("category")) or (norm_category(cur["category_raw"]) if cur["category_raw"] else None)
        name = _s(a.get("name")) or (cur["name"] or "")
        tag = f"ID: {key}" + ("" if variant == "single" else f"_{variant}")
        if cat:
            tag += chr(10) + f"CATEGORY: {cat}"
        if name:
            tag += chr(10) + f"NAME: {name}"
        lines[n] = tag
        final[n] = (key, variant)
        resolved.append({"num": n, "key": key, "variant": variant, "category": norm_category(a.get("category")),
                         "name": _s(a.get("name"))})
    before = {}
    for s in scan["slides"]:
        if s["key"]:
            before[(s["key"], s["variant"])] = before.get((s["key"], s["variant"]), 0) + 1
    after = {}
    for k_v in final.values():
        after[k_v] = after.get(k_v, 0) + 1
    multi = [(k, v, c) for (k, v), c in after.items() if v in ("named", "unnamed") and c > 1 and c > before.get((k, v), 0)]
    if multi and not confirm_multi:
        txt = "; ".join(f"'{k}' ({v}) would be on {c} slides" for k, v, c in multi[:5])
        raise NeedsConfirm("This puts several slides on the same project version: " + txt + ". "
                           "That is only right for a project that really has several slides per version.")
    assignments = resolved
    prs = _open_presentation(dst)
    slides = list(prs.slides)
    for n, text in lines.items():
        set_slide_notes(prs, slides[n - 1], text)
    tmp = dst.with_suffix(".tagging.pptx")
    try:
        prs.save(str(tmp))
        _verify_tags(tmp, assignments)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archived = ARCHIVE_DIR / f"{dst.stem}_{datetime.now():%Y%m%d_%H%M%S}_before_tagging.pptx"
        shutil.copy2(dst, archived)
        os.replace(tmp, dst)
    except PermissionError:
        _rm(tmp)
        raise DeckError(f"The base deck is locked (open in PowerPoint?):\n{dst}\nSave and close it, then try again.")
    except DeckError:
        _rm(tmp)
        raise
    _verify_tags(dst, assignments)  # re-read the FINAL file: the tags really are in the .pptx
    for old in sorted(ARCHIVE_DIR.glob(dst.stem + "_*_before_tagging.pptx"))[:-20]:
        _rm(old)  # keep only the 20 newest tagging backups
    res = sync([audience], verbose=False)
    _apply_tag_choices(audience, assignments)
    log(f"Tagged {len(lines)} slide(s). Previous deck archived: {archived.name}")
    return {"tagged": sorted(lines), "archived": str(archived), "report": res[audience]["report"],
            "warnings": res[audience]["scan"]["warnings"]}
