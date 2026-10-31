#!/usr/bin/env python3
"""Shared sorting / filtering for the project lists (main window and Manage projects)."""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple

ALL = "(all)"
NO_SOURCE = "(no source)"
HINT = "Click a heading to sort (click again to reverse). Click a second heading to sort WITHIN the first, e.g. Sector, then Country."


def _blank(v) -> bool:
    return str(v).strip() == "" or str(v).strip().upper() == "TBD"


def toggle_sort(keys: List[Tuple[str, bool]], col: str, cap: int = 3) -> List[Tuple[str, bool]]:
    """keys = [(column, reverse)], most important first. Clicking the primary column flips it; any other column
    becomes the new primary and the old primary becomes the tie-breaker."""
    if keys and keys[0][0] == col:
        return [(col, not keys[0][1])] + keys[1:]
    return [(col, False)] + [k for k in keys if k[0] != col][: cap - 1]


def sort_items(items: list, keys: List[Tuple[str, bool]], getter: Callable) -> list:
    """Stable multi-key sort; empty / 'TBD' values always sink to the bottom whichever way you sort."""
    out = list(items)
    for col, rev in reversed(keys):
        full = [x for x in out if not _blank(getter(x, col))]
        blank = [x for x in out if _blank(getter(x, col))]
        full.sort(key=lambda x: str(getter(x, col)).lower(), reverse=rev)
        out = full + blank
    return out


def heading_text(title: str, keys: List[Tuple[str, bool]], col: str) -> str:
    for rank, (c, rev) in enumerate(keys, 1):
        if c == col:
            return f"{title} {'▼' if rev else '▲'}" + (f"{rank}" if len(keys) > 1 else "")
    return title


def matches(p: dict, sector: str, country: str, category: str, text: str, sources: Optional[Iterable[str]] = None,
            models: Optional[Iterable[str]] = None) -> bool:
    """sources: a set of source names (lower/upper case ignored); NO_SOURCE selects projects with no source recorded."""
    if sector not in ("", ALL) and (p.get("sector") or "") != sector:
        return False
    if country not in ("", ALL) and (p.get("country") or "") != country:
        return False
    if category not in ("", ALL) and (p.get("category") or "") != category:
        return False
    if models:
        import modelnames
        if not ({m.lower() for m in modelnames.parts(p.get("model"))} & {m.lower() for m in models}):
            return False
    if sources:
        want = {s.lower() for s in sources}
        have = {s.lower() for s in (p.get("sources") or [])}
        ok = bool(have & want) or (NO_SOURCE.lower() in want and not have)
        if not ok:
            return False
    t = text.strip().lower()
    if t:
        hay = " ".join(str(p.get(k, "")) for k in ("name", "unnamed_name", "id", "country", "sector", "region", "model", "source")).lower()
        if t not in hay:
            return False
    return True


def distinct(projects: list, field: str) -> List[str]:
    return sorted({(p.get(field) or "").strip() for p in projects if not _blank(p.get(field) or "")}, key=str.lower)


def distinct_sources(projects: list) -> List[str]:
    """Every individual source named on any project (a project can have several)."""
    seen = {}
    for p in projects:
        for s in p.get("sources") or []:
            seen.setdefault(s.lower(), s)
    return sorted(seen.values(), key=str.lower)


def describe(sector, country, category, source_sel, text, sort_keys, names) -> List[str]:
    """Lines for the top of a printout: which filters and which sort order are in force."""
    f = []
    if sector not in ("", ALL):
        f.append(f"Sector: {sector}")
    if country not in ("", ALL):
        f.append(f"Country: {country}")
    if category not in ("", ALL):
        f.append(f"Category: {category}")
    if source_sel:
        f.append("Source: " + ", ".join(source_sel))
    if text.strip():
        f.append(f"Search: '{text.strip()}'")
    lines = ["Filters: " + (" \u00b7 ".join(f) if f else "none (all projects)")]
    if sort_keys:
        lines.append("Sorted by " + ", then ".join(f"{names.get(c, c)} {'\u25bc' if rev else '\u25b2'}" for c, rev in sort_keys))
    else:
        lines.append("In deck order")
    return lines


def source_label(selected: Iterable[str]) -> str:
    sel = list(selected)
    if not sel:
        return ALL
    return sel[0] if len(sel) == 1 else f"{len(sel)} sources selected"
