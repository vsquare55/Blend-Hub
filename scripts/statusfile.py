#!/usr/bin/env python3
"""
Internal status from a team-maintained Excel file (optional; only when you upload it).

Reads any workbook that looks like the 'BIP - Captive Projects' file: every visible sheet that has a header row with a project-name column
is read (country pipeline sheets, 'ADVANCE PROJECTS' with its stakeholder blocks, 'Burkina Faso' ...). Columns are recognised by their
heading, not their position, so the team can add / move columns. Each Desk project is matched to the file's rows by name + country
(fuzzy: 'confident' or 'possible'); a project that is not in the file - not even partly - simply shows 'no data'.
Nothing here ever goes into a deck.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import deckcore as core
import tracker as T

# --------------------------------------------------------------------------- column recognition
# field -> regex on the normalised heading; first rule that matches wins
RULES = [
    ("name", r"^(project name|name of project|project title|projects?)$"),
    ("country", r"^country$"),
    ("sector", r"^sector$"),
    ("summary", r"^project summary$"),
    ("counterparty", r"counterparty|project owner|state-owned"),
    ("introduced", r"partner who introduced|name of local partner|introduced by"),
    ("stage", r"^project stage$"),
    ("class", r"^type$"),
    ("status", r"^status$"),
    ("epc", r"epc mapping"),
    ("next", r"next steps|action plan"),
    ("value", r"indicative project value|est\. project value|project cost|project value"),
    ("structure", r"structure"),
    ("info", r"information available|summary of available|documents received"),
    ("eoi", r"^eoi status$"),
    ("eoi_fb", r"^eoi feedback$"),
    ("mou", r"status of mou"),
    ("proposal", r"status of submission of project proposal"),
    ("proposal_fb", r"feedback on project proposal"),
    ("initiated", r"date initiated"),
    ("rm", r"responsible rm|innovus/blend rm|^rm$"),
    ("remarks", r"remarks"),
    ("priority", r"^priority$"),
    # roll-up block of the ADVANCE sheet
    ("stakeholders", r"stakeholders engaged"),
    ("agr_signed", r"agreements signed"),
    ("agr_pending", r"agreements pending"),
    ("agr_status", r"overall agreement status"),
    ("updated", r"last updated"),
]
MULTI = {"rm", "remarks", "info"}
LABELS = {"stage": "Project stage", "class": "Class", "status": "Status", "structure": "Structure", "value": "Indicative value",
          "counterparty": "Counterparty / owner", "introduced": "Introduced by / local partner", "epc": "EPC mapping",
          "eoi": "EOI status", "eoi_fb": "EOI feedback", "mou": "MOU with owner", "proposal": "Proposal submitted",
          "proposal_fb": "Proposal feedback", "initiated": "Date initiated", "rm": "Responsible RMs", "info": "Information available",
          "summary": "Summary", "remarks": "Remarks", "priority": "Priority", "sector": "Sector", "stakeholders": "Stakeholders engaged",
          "agr_signed": "Agreements signed", "agr_pending": "Agreements pending", "agr_status": "Overall agreement status",
          "updated": "Last updated in file"}
SHOW_ORDER = ["stage", "class", "status", "priority", "structure", "value", "counterparty", "introduced", "epc", "eoi", "eoi_fb", "mou", "proposal",
              "proposal_fb", "initiated", "agr_status", "agr_signed", "agr_pending", "stakeholders", "updated", "rm", "info", "summary", "remarks"]
WATCH = ["stage", "class", "status", "next", "epc", "structure", "value", "agr_status", "eoi", "mou", "proposal"]  # what counts as 'changed'
EMPTY = {"", "none", "n.a.", "n.a", "na", "n/a", "-", "--", "nil", "#ref!", "0"}
JUNK_PARTY = re.compile(r"^(tbc|tbd|pending|none|n\.?a\.?|not yet identified|to be (decided|confirmed)|-+)\b", re.I)
PARTY_FIELDS = [("name", r"^name ?/ ?entity$|^name$"), ("status", r"agreement status|financing status|^status$"),
                ("notes", r"^notes?$"), ("commission", r"commission amount|commission type"), ("date", r"agreement date")]
BANK_WORDS = re.compile(r"\b(?:[A-Z][\w'’&.-]*\s){0,3}(?:Bank|Banque|Eximbank|Kredit|Kommunalkredit|Finance Corporation)\b|"
                        r"\b(?:BGFI|KUKE|EIFO|SACE|EBID|BNIG|AFREXIMBANK|Afreximbank|AfDB|BOAD|BADEA|IsDB|Euler Hermes|Atradius|UKEF|Bpifrance|"
                        r"Coface|DFI|ECA|IFC|Proparco|FMO|DEG|OPEC Fund|Frontera Capital)\b")
KIND = [(r"bank|lender", "Bank / lender"), (r"investor", "Investor"), (r"local partner|investee", "Local partner"), (r"epc", "EPC contractor"),
        (r"consultant", "Consultant")]


def clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        v = int(v)
    s = str(v).replace("\r", "").strip()
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return "" if s.lower() in EMPTY else s


def head_norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\n", " ")).strip().lower()


def map_headers(row) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for i, v in enumerate(row):
        h = head_norm(v)
        if not h:
            continue
        for field, pat in RULES:
            if re.search(pat, h):
                out[i] = field
                break
    return out


def role_label(g: str) -> str:
    g = re.sub(r"(?i)investorfor", "INVESTOR FOR", g)
    g = g.title() if g.isupper() or g.islower() else g
    g = re.sub(r"Epc", "EPC", g)
    return re.sub(r"\s+", " ", g).strip()


def kind_of(group: str) -> str:
    for pat, k in KIND:
        if re.search(pat, group, re.I):
            return k
    return "Partner"


# --------------------------------------------------------------------------- parsing
def parse_workbook(path: Path, include_hidden: bool = False) -> dict:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    rows: List[dict] = []
    sheets_used, sheets_skipped = [], []
    for ws in wb.worksheets:
        name = ws.title.strip()
        if ws.sheet_state != "visible" and not include_hidden:
            sheets_skipped.append(f"{name} (hidden)")
            continue
        grid = [list(r) for r in ws.iter_rows(min_row=1, max_row=1500, max_col=70, values_only=True)]
        hdr_i, hmap = None, {}
        for i, row in enumerate(grid[:12]):
            m = map_headers(row)
            if "name" in m.values() and len(m) >= 3:
                hdr_i, hmap = i, m
                break
        if hdr_i is None:
            sheets_skipped.append(f"{name} (no project table)")
            continue
        header = grid[hdr_i]
        # stakeholder groups: the row above the header carries a label over each block (forward-filled)
        groups: Dict[int, str] = {}
        if hdr_i > 0:
            above, cur = grid[hdr_i - 1], ""
            for i in range(len(header)):
                if i < len(above) and clean(above[i]):
                    cur = clean(above[i])
                groups[i] = cur
        party_cols: Dict[str, Dict[str, int]] = {}
        for i, v in enumerate(header):
            g = groups.get(i, "")
            h = head_norm(v)
            if not g or not h or i in hmap and hmap[i] in ("name", "country", "sector"):
                continue
            if re.search(r"project information", g, re.I):
                continue
            for f, pat in PARTY_FIELDS:
                if re.search(pat, h):
                    party_cols.setdefault(g, {}).setdefault(f, i)
                    break
        party_cols = {g: c for g, c in party_cols.items() if "name" in c}
        grouped_cols = {i for c in party_cols.values() for i in c.values()}
        sheet_country = core_country(name)
        used = 0
        for ri in range(hdr_i + 1, len(grid)):
            row = grid[ri]
            cols = {f: [] for f in MULTI}
            fields: Dict[str, object] = {}
            for i, f in hmap.items():
                if i >= len(row) or i in grouped_cols:
                    continue
                val = clean(row[i])
                if not val:
                    continue
                if f in MULTI:
                    cols[f].append((head_norm(header[i]) if f != "info" else "", val))
                elif f not in fields:
                    fields[f] = val
            nm = fields.pop("name", "")
            if not nm or len(nm) < 3 or re.fullmatch(r"project name", nm, re.I):
                continue
            for f, lst in cols.items():
                if lst:
                    fields[f] = lst
            country = fields.pop("country", "") or sheet_country
            if not [k for k in fields if k not in ("sector",)]:
                continue  # a section heading or a stray cell, not a project
            parties: List[dict] = []
            for g, c in party_cols.items():
                nm_p = clean(row[c["name"]]) if c["name"] < len(row) else ""
                if not nm_p or JUNK_PARTY.match(nm_p):
                    continue
                p = {"role": role_label(g), "kind": kind_of(g), "name": nm_p}
                for f in ("status", "notes", "commission", "date"):
                    if f in c and c[f] < len(row) and clean(row[c[f]]):
                        p[f] = clean(row[c[f]])
                parties.append(p)
            if fields.get("epc") and not JUNK_PARTY.match(str(fields["epc"])) and not any(p["kind"] == "EPC contractor" for p in parties):
                parties.append({"role": "EPC mapping", "kind": "EPC contractor", "name": str(fields["epc"])})
            if fields.get("introduced") and not JUNK_PARTY.match(str(fields["introduced"])):
                parties.append({"role": "Introduced by / local partner", "kind": "Local partner", "name": str(fields["introduced"])})
            text = " ".join(str(v) if not isinstance(v, list) else " ".join(t for _, t in v)
                            for k, v in fields.items() if k in ("info", "next", "status", "remarks", "structure", "summary", "eoi_fb", "proposal_fb"))
            banks = []
            for m in BANK_WORDS.finditer(text):
                b = m.group(0).strip()
                if b and b not in banks and not re.fullmatch(r"(?i)the bank|bank", b):
                    banks.append(b)
            rows.append({"sheet": name, "row": ri + 1, "country": country, "name": nm.replace("\n", " ").strip(), "fields": fields,
                         "parties": parties, "banks": banks[:8]})
            used += 1
        sheets_used.append(f"{name} ({used})")
    wb.close()
    return {"rows": rows, "sheets_used": sheets_used, "sheets_skipped": sheets_skipped}


def core_country(sheet: str) -> str:
    s = re.sub(r"\s+", " ", sheet.replace("_", " ")).strip()
    s = re.sub(r"^jt\s*-\s*", "", s, flags=re.I)
    c = T.canonical(s.title() if s.isupper() else s)
    return T.ALIASES.get(c.lower(), c) if c.lower() not in ("advance projects", "others", "investment opportunity") else ""


# --------------------------------------------------------------------------- matching
STOP = {"project", "projects", "the", "of", "in", "and", "for", "a", "an", "to", "at", "on", "de", "du", "des", "la", "le", "les", "et",
        "plant", "power", "new", "phase", "construction", "development", "establishment", "building", "program", "programme", "scheme",
        "under", "with", "from", "by", "expansion", "opportunity", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "several", "various", "other", "others", "programmes", "contracts", "sites", "site", "pipeline", "modernisation", "modernization"}
_COUNTRY_WORDS = {w for v in T.GEO_SEED.values() for c in v for w in re.findall(r"[a-z]+", c.lower())} | \
                 {w for k in T.ALIASES for w in re.findall(r"[a-z]+", k)} | {"conakry", "zanzibar", "niger", "congo", "roc", "car", "drc", "ivc"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("\u00b3", "3")
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)  # 30,000 -> 30000
    s = re.sub(r"(\d+)\s*(?:cu\.?\s?m|m3|cum|cubic metres?)\b", r"\1m3", s)
    s = re.sub(r"(\d+)\s*(mwh|mwp|mw|kv|km|mn|mva|kwp|ha|mt|t)\b", r"\1\2", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _stem(t: str) -> str:
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("ing") and len(t) > 5:
        return t[:-3]
    if t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
        return t[:-1]
    return t


def _tokens(s: str) -> List[str]:
    out = []
    for t in _norm(s).split():
        if t in STOP or t in _COUNTRY_WORDS or (len(t) < 2 and not t.isdigit()):
            continue
        m = re.fullmatch(r"([0-9]+)[a-z]{1,3}", t)
        out.append(m.group(1) if m else _stem(t))
    return out


def _prep(s: str):
    t = _tokens(s)
    return t, set(t), " ".join(t)


def _score(a: str, b: str) -> float:
    return _score_p(_prep(a), _prep(b))


def _score_p(pa, pb) -> float:
    ta, A, ja = pa
    tb, B, jb = pb
    if not ta or not tb:
        return 0.0
    inter = len(A & B)
    contain = inter / min(len(A), len(B))
    jacc = inter / len(A | B)
    ratio = SequenceMatcher(None, ja, jb).ratio()
    s = 0.5 * contain + 0.2 * jacc + 0.3 * ratio
    na = {t for t in A if re.search(r"\d", t)}
    nb = {t for t in B if re.search(r"\d", t)}
    if na and nb:
        s += 0.08 if na & nb else -0.15
    return max(0.0, min(1.0, s))


HIGH, PARTIAL = 0.72, 0.52


def _ccountry(c: str) -> str:
    return T.canonical((c or "").strip()).lower()


def match_projects(projects: List[dict], rows: List[dict], links: Optional[Dict[str, dict]] = None) -> Dict[str, dict]:
    """key -> {'rows': [{'row':..., 'score':..}], 'conf': 'high'|'possible'|'linked'} ; projects without a match are absent."""
    links = links or {}
    out: Dict[str, dict] = {}
    rowp = [(r, _prep(r["name"]), _ccountry(r["country"])) for r in rows]
    for p in projects:
        k = p["id"]
        lk = links.get(k)
        if lk is not None:
            if not lk["norm"]:
                continue  # user said: no data for this project
            hit = [r for r in rows if _norm(r["name"]) == lk["norm"] and (not lk["country"] or _ccountry(r["country"]) == _ccountry(lk["country"]))]
            if hit:
                out[k] = {"rows": [{"row": r, "score": 1.0} for r in hit[:3]], "conf": "linked"}
                continue
        pc = _ccountry(p.get("country", ""))
        cand: List[Tuple[float, dict]] = []
        pn, pid = _prep(p["name"]), _prep(k.replace("_", " "))
        for r, rp, rc in rowp:
            s = max(_score_p(pn, rp), 0.9 * _score_p(pid, rp))
            if pc and rc and pc != rc:
                s *= 0.35
            elif not pc or not rc:
                s *= 0.93
            if s >= PARTIAL:
                cand.append((s, r))
        if not cand:
            continue
        cand.sort(key=lambda t: -t[0])
        best = cand[0][0]
        keep = [(s, r) for s, r in cand if s >= best - 0.12][:6]
        out[k] = {"rows": [{"row": r, "score": round(s, 3)} for s, r in keep], "conf": "high" if best >= HIGH else "possible"}
    return out


SHEET_RANK = {"ADVANCE PROJECTS": 0, "Investment Opportunity": 3, "OTHERS_": 3}


def group_rows(m: dict) -> List[dict]:
    """The matched rows, with the same project listed on several sheets merged: [{'main': match, 'also': [match,...]}].
    Main = the richest source (ADVANCE sheet > country sheet > other sheets)."""
    groups: Dict[Tuple[str, str], List[dict]] = {}
    for x in m["rows"]:
        r = x["row"]
        groups.setdefault((_norm(r["name"]), _ccountry(r["country"])), []).append(x)
    out = []
    for g in groups.values():
        g.sort(key=lambda x: (SHEET_RANK.get(x["row"]["sheet"], 1), -len(x["row"]["parties"])))
        out.append({"main": g[0], "also": g[1:]})
    out.sort(key=lambda d: (SHEET_RANK.get(d["main"]["row"]["sheet"], 1), -d["main"]["score"]))
    return out


# --------------------------------------------------------------------------- import (store + diff + log)
def _snap(m: Optional[dict]) -> Dict[str, str]:
    if not m:
        return {}
    best = max(m["rows"], key=lambda x: len(x["row"]["parties"]) * 3 + len(x["row"]["fields"]))["row"]
    d = {}
    for f in WATCH:
        v = best["fields"].get(f)
        d[f] = " ".join(t for _, t in v) if isinstance(v, list) else str(v or "")
    return d


def import_file(path: Path, projects: List[dict], include_hidden: bool = False) -> dict:
    parsed = parse_workbook(path, include_hidden)
    rows = parsed["rows"]
    if not rows:
        raise core.DeckError("No project table was found in that file. It should have a heading row with a 'Project Name' column "
                             "(and ideally Country, Project Stage, Next Steps ...).")
    links = T.ext_links()
    old_rows = T.ext_rows()
    old = match_projects(projects, old_rows, links) if old_rows else {}
    new = match_projects(projects, rows, links)
    changed, appeared, gone = [], [], []
    for k in set(old) | set(new):
        a, b = _snap(old.get(k)), _snap(new.get(k))
        if k in new and k not in old and old_rows:
            appeared.append(k)
            T.log_event(k, "Appeared in status file", note=f"{new[k]['conf']} match: {new[k]['rows'][0]['row']['sheet']} row {new[k]['rows'][0]['row']['row']}")
        elif k in old and k not in new:
            gone.append(k)
            T.log_event(k, "No longer in status file")
        elif k in new and old_rows:
            diffs = []
            for f in WATCH:
                if (a.get(f, "").strip().lower() != b.get(f, "").strip().lower()):
                    short = f in ("stage", "class", "status", "epc", "structure", "value", "agr_status", "eoi", "mou", "proposal") and max(len(a.get(f, "")), len(b.get(f, ""))) < 60
                    diffs.append(f"{LABELS.get(f, 'Next steps' if f == 'next' else f)}: {a.get(f) or '-'} → {b.get(f) or '-'}" if short
                                 else f"{LABELS.get(f, 'Next steps' if f == 'next' else f)} updated")
            if diffs:
                changed.append(k)
                T.log_event(k, "Status updated from file", note="; ".join(diffs)[:600])
    summary = {"sheets_used": parsed["sheets_used"], "sheets_skipped": parsed["sheets_skipped"], "n_rows": len(rows),
               "matched": len(new), "high": sum(1 for m in new.values() if m["conf"] in ("high", "linked")),
               "possible": sum(1 for m in new.values() if m["conf"] == "possible"), "n_projects": len(projects),
               "changed": changed, "appeared": appeared, "gone": gone, "first": not old_rows}
    bid = T.ext_save(str(path), path.name, path.stat().st_mtime, summary, rows)
    T.log_event("", "Status file imported", note=f"{path.name}: {len(rows)} rows, {len(new)} of {len(projects)} projects matched, {len(changed)} changed")
    summary["batch"] = bid
    return summary


def current_matches(projects: List[dict]) -> Dict[str, dict]:
    rows = T.ext_rows()
    return match_projects(projects, rows, T.ext_links()) if rows else {}


def unmatched_rows(projects: List[dict]) -> List[dict]:
    rows = T.ext_rows()
    m = match_projects(projects, rows, T.ext_links())
    used = {(x["row"]["sheet"], x["row"]["row"]) for v in m.values() for x in v["rows"]}
    return [r for r in rows if (r["sheet"], r["row"]) not in used]


def next_steps_text(row: dict) -> str:
    v = row["fields"].get("next")
    return v if isinstance(v, str) else ""


def field_text(v) -> str:
    return "\n".join((f"{lbl.title()}: " if lbl and len(v) > 1 else "") + t for lbl, t in v) if isinstance(v, list) else str(v)


def norm_name(s: str) -> str:
    return _norm(s)
