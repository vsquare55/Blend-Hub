#!/usr/bin/env python3
"""
Project Desk - the INTERNAL layer of DealDeck Studio (never goes into a deck).

For every project it keeps: who leads the geography (RB / JT / SS), what is needed (investor, EPC, ...), the bosses' comments
from each discussion, action items, and a complete change log (what was added / changed / deleted, by whom, when).
Nothing is ever really deleted here: removed items are flagged and stay in the log.

Storage: data/desk.db (SQLite, one file, no server). Backed up automatically once a day to data/backups/.
"""
from __future__ import annotations

import getpass
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import deckcore as core

DATA_DIR = core.ROOT / "data"
DB_PATH = DATA_DIR / "desk.db"
KEEP_DAILY_BACKUPS = 30

STAGES = ["To discuss", "In discussion", "Awaiting info", "Partner search", "Partner matched", "On hold", "Closed"]
PRIORITIES = ["High", "Medium", "Low"]
KINDS = ["Investor", "EPC", "Developer / Sponsor", "Lender / DFI", "Other"]
REQ_STATUS = ["Open", "Searching", "In talks", "Matched", "Not needed"]
CLOSED_REQ = ("Matched", "Not needed")
LEADS = ["RB", "JT", "SS"]
PMS = "Vishnu & Vijayraj"

# Geography distribution between the three leads (from the distribution sheet)
GEO_SEED = {
    "RB": ["Tanzania", "Central African Republic", "Madagascar", "Sierra Leone", "Mauritania", "Zambia", "Republic of Congo"],
    "JT": ["Cameroon", "Gabon", "Chad", "Benin", "Togo", "Ghana", "Angola", "Zimbabwe", "Liberia"],
    "SS": ["Cote d'Ivoire", "Burkina Faso", "DRC", "Guinea", "Botswana", "Namibia", "Uganda", "Rwanda"],
}
TEAM_SEED = {"RB": ["Karan", "Smruti"], "JT": ["Sunil", "Neelkand"], "SS": ["Heena", "Shivang"]}
ALIASES = {"zanzibar": "Tanzania", "car": "Central African Republic", "congo (roc)": "Republic of Congo", "roc": "Republic of Congo",
           "congo": "Republic of Congo", "congo-brazzaville": "Republic of Congo", "ivc": "Cote d'Ivoire", "ivory coast": "Cote d'Ivoire",
           "côte d'ivoire": "Cote d'Ivoire", "cote d’ivoire": "Cote d'Ivoire", "bostwana": "Botswana", "rawanda": "Rwanda",
           "democratic republic of congo": "DRC", "drc congo": "DRC", "burkina": "Burkina Faso"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS geo (country TEXT PRIMARY KEY, lead TEXT);
CREATE TABLE IF NOT EXISTS team (lead TEXT, member TEXT);
CREATE TABLE IF NOT EXISTS proj (key TEXT PRIMARY KEY, lead TEXT DEFAULT '', pm TEXT DEFAULT '', stage TEXT DEFAULT 'To discuss',
    priority TEXT DEFAULT 'Medium', summary TEXT DEFAULT '', updated TEXT);
CREATE TABLE IF NOT EXISTS req (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, kind TEXT, detail TEXT, status TEXT DEFAULT 'Open',
    created TEXT, updated TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS cmt (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, by TEXT, day TEXT, text TEXT, ts TEXT,
    edited TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS act (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, text TEXT, owner TEXT, due TEXT, done INTEGER DEFAULT 0,
    created TEXT, done_ts TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT, key TEXT, action TEXT, field TEXT,
    old TEXT, new TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, first_seen TEXT, in_deck INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS ext_batch (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT, path TEXT, fname TEXT, mtime REAL, summary TEXT);
CREATE TABLE IF NOT EXISTS ext_row (id INTEGER PRIMARY KEY AUTOINCREMENT, batch INTEGER, sheet TEXT, rownum INTEGER, country TEXT, name TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS ext_link (key TEXT PRIMARY KEY, norm TEXT, country TEXT);
CREATE INDEX IF NOT EXISTS ix_extrow ON ext_row(batch);
CREATE INDEX IF NOT EXISTS ix_req ON req(key); CREATE INDEX IF NOT EXISTS ix_cmt ON cmt(key);
CREATE INDEX IF NOT EXISTS ix_act ON act(key); CREATE INDEX IF NOT EXISTS ix_log ON log(key, ts);
"""
_ready = False


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- connection
def _daily_backup() -> None:
    if not DB_PATH.exists():
        return
    bdir = DATA_DIR / "backups"
    bdir.mkdir(exist_ok=True)
    dst = bdir / f"desk_{datetime.now():%Y%m%d}.db"
    if not dst.exists():
        try:
            src = sqlite3.connect(DB_PATH)
            out = sqlite3.connect(dst)
            src.backup(out)
            out.close()
            src.close()
        except Exception:
            return
        for old in sorted(bdir.glob("desk_*.db"))[:-KEEP_DAILY_BACKUPS]:
            try:
                old.unlink()
            except OSError:
                pass


@contextmanager
def db():
    global _ready
    DATA_DIR.mkdir(exist_ok=True)
    if not _ready:
        _daily_backup()
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=DELETE")  # one plain file: safest on OneDrive
    try:
        if not _ready:
            c.executescript(SCHEMA)
            if "next_review" not in {r[1] for r in c.execute("PRAGMA table_info(proj)")}:
                c.execute("ALTER TABLE proj ADD COLUMN next_review TEXT DEFAULT ''")
            _seed(c)
            _ready = True
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _seed(c) -> None:
    if c.execute("SELECT COUNT(*) FROM geo").fetchone()[0] == 0:
        for lead, countries in GEO_SEED.items():
            for k in countries:
                c.execute("INSERT OR IGNORE INTO geo VALUES (?,?)", (k, lead))
        for lead, ms in TEAM_SEED.items():
            for m in ms:
                c.execute("INSERT INTO team VALUES (?,?)", (lead, m))
        c.execute("INSERT INTO log (ts,user,key,action,note) VALUES (?,?,?,?,?)",
                  (now(), get_user(c), "", "Desk created", "Geography distribution loaded: RB / JT / SS"))


def get_user(c=None) -> str:
    def q(cc):
        r = cc.execute("SELECT v FROM meta WHERE k='user'").fetchone()
        return r[0] if r else ""
    try:
        if c is not None:
            v = q(c)
        else:
            with db() as cc:
                v = q(cc)
    except Exception:
        v = ""
    return v or getpass.getuser()


def set_user(name: str) -> None:
    with db() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES ('user',?)", (name.strip(),))


def user_is_set() -> bool:
    with db() as c:
        return bool(c.execute("SELECT 1 FROM meta WHERE k='user'").fetchone())


# --------------------------------------------------------------------------- log
def _log(c, key: str, action: str, field: str = "", old="", new="", note: str = "") -> None:
    c.execute("INSERT INTO log (ts,user,key,action,field,old,new,note) VALUES (?,?,?,?,?,?,?,?)",
              (now(), get_user(c), key or "", action, field, "" if old is None else str(old), "" if new is None else str(new), note))


def log_event(key: str, action: str, field: str = "", old="", new="", note: str = "") -> None:
    """Best-effort entry point used by the deck operations (never raises)."""
    try:
        with db() as c:
            _log(c, key, action, field, old, new, note)
    except Exception:
        pass


def history(key: Optional[str] = None, limit: int = 1000, text: str = "") -> List[dict]:
    with db() as c:
        q, a = "SELECT * FROM log", []
        w = []
        if key:
            w.append("key=?")
            a.append(key)
        if text:
            w.append("(action||' '||field||' '||old||' '||new||' '||note||' '||key||' '||user) LIKE ?")
            a.append(f"%{text}%")
        if w:
            q += " WHERE " + " AND ".join(w)
        q += " ORDER BY id DESC LIMIT ?"
        a.append(limit)
        return [dict(r) for r in c.execute(q, a)]


# --------------------------------------------------------------------------- geography
def canonical(country: str) -> str:
    k = (country or "").strip()
    return ALIASES.get(k.lower(), k)


def lead_for_country(country: str, c=None) -> str:
    cn = canonical(country)
    if not cn:
        return ""
    def q(cc):
        r = cc.execute("SELECT lead FROM geo WHERE lower(country)=lower(?)", (cn,)).fetchone()
        return r[0] if r else ""
    if c is not None:
        return q(c)
    with db() as cc:
        return q(cc)


def geo_list() -> List[dict]:
    with db() as c:
        return [dict(r) for r in c.execute("SELECT country, lead FROM geo ORDER BY lead, country")]


def team() -> Dict[str, List[str]]:
    with db() as c:
        out: Dict[str, List[str]] = {}
        for r in c.execute("SELECT lead, member FROM team ORDER BY rowid"):
            out.setdefault(r["lead"], []).append(r["member"])
        return out


def set_geo(country: str, lead: str) -> None:
    """Assign a country to a lead ('' removes the assignment)."""
    cn = canonical(country)
    if not cn:
        raise core.DeckError("Enter a country.")
    if lead and lead not in LEADS:
        raise core.DeckError("Lead must be RB, JT or SS.")
    with db() as c:
        old = lead_for_country(cn, c)
        if lead:
            c.execute("INSERT OR REPLACE INTO geo VALUES (?,?)", (cn, lead))
        else:
            c.execute("DELETE FROM geo WHERE lower(country)=lower(?)", (cn,))
        if old != lead:
            _log(c, "", "Geography changed", cn, old or "(none)", lead or "(none)")


# --------------------------------------------------------------------------- per-project record
def get_proj(key: str, country: str = "") -> dict:
    with db() as c:
        r = c.execute("SELECT * FROM proj WHERE key=?", (key,)).fetchone()
        d = dict(r) if r else {"key": key, "lead": "", "pm": "", "stage": "To discuss", "priority": "Medium", "summary": "", "updated": "", "next_review": ""}
        d["geo_lead"] = lead_for_country(country, c)
        d["lead_eff"] = d["lead"] or d["geo_lead"]
        d["pm_eff"] = d["pm"] or PMS
        return d


def set_proj(key: str, **fields) -> int:
    """Change internal fields (lead, pm, stage, priority, summary). Logs every real change; returns how many changed."""
    allowed = {"lead", "pm", "stage", "priority", "summary", "next_review"}
    bad = set(fields) - allowed
    if bad:
        raise core.DeckError("Unknown field: " + ", ".join(sorted(bad)))
    if fields.get("lead") and fields["lead"] not in LEADS:
        raise core.DeckError("Lead must be RB, JT or SS.")
    if (fields.get("next_review") or "").strip():
        try:
            datetime.strptime(fields["next_review"].strip(), "%Y-%m-%d")
        except ValueError:
            raise core.DeckError("Write the date as YYYY-MM-DD, e.g. 2026-11-03 (or leave it empty).")
    n = 0
    with db() as c:
        r = c.execute("SELECT * FROM proj WHERE key=?", (key,)).fetchone()
        if not r:
            c.execute("INSERT INTO proj (key, updated) VALUES (?,?)", (key, now()))
            r = c.execute("SELECT * FROM proj WHERE key=?", (key,)).fetchone()
        for f, v in fields.items():
            v = (v or "").strip()
            if (r[f] or "") != v:
                c.execute(f"UPDATE proj SET {f}=?, updated=? WHERE key=?", (v, now(), key))
                _log(c, key, "Updated", f, r[f] or "", v)
                n += 1
    return n


# --------------------------------------------------------------------------- requirements / comments / actions
def _list(table: str, key: str, include_deleted=False) -> List[dict]:
    with db() as c:
        q = f"SELECT * FROM {table} WHERE key=?" + ("" if include_deleted else " AND deleted=0") + " ORDER BY id DESC"
        return [dict(r) for r in c.execute(q, (key,))]


def reqs(key: str) -> List[dict]:
    return _list("req", key)


def comments(key: str) -> List[dict]:
    return sorted(_list("cmt", key), key=lambda r: (r["day"] or "", r["id"]), reverse=True)


def actions(key: str) -> List[dict]:
    return sorted(_list("act", key), key=lambda r: (r["done"], r["due"] or "9999", -r["id"]))


def add_req(key: str, kind: str, detail: str = "", status: str = "Open") -> int:
    if not (kind or "").strip():
        raise core.DeckError("Choose what is needed (Investor, EPC, ...).")
    with db() as c:
        cur = c.execute("INSERT INTO req (key,kind,detail,status,created,updated) VALUES (?,?,?,?,?,?)",
                        (key, kind.strip(), (detail or "").strip(), status, now(), now()))
        _log(c, key, "Requirement added", kind, "", status, detail)
        return cur.lastrowid


def update_req(rid: int, **f) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM req WHERE id=?", (rid,)).fetchone()
        if not r:
            return
        for k, v in f.items():
            if k in ("kind", "detail", "status") and (r[k] or "") != (v or "").strip():
                c.execute(f"UPDATE req SET {k}=?, updated=? WHERE id=?", ((v or "").strip(), now(), rid))
                _log(c, r["key"], "Requirement changed", f"{r['kind']}: {k}", r[k] or "", (v or "").strip())


def delete_req(rid: int) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM req WHERE id=?", (rid,)).fetchone()
        if r and not r["deleted"]:
            c.execute("UPDATE req SET deleted=1, updated=? WHERE id=?", (now(), rid))
            _log(c, r["key"], "Requirement deleted", r["kind"], r["detail"], "", "was " + (r["status"] or ""))


def add_comment(key: str, by: str, text: str, day: str = "") -> int:
    if not (text or "").strip():
        raise core.DeckError("Type the comment first.")
    with db() as c:
        cur = c.execute("INSERT INTO cmt (key,by,day,text,ts) VALUES (?,?,?,?,?)", (key, by.strip(), day or today(), text.strip(), now()))
        _log(c, key, "Comment added", by, "", text.strip()[:300], day or today())
        return cur.lastrowid


def update_comment(cid: int, text: str, by: Optional[str] = None) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM cmt WHERE id=?", (cid,)).fetchone()
        if r and (r["text"] != text.strip() or (by is not None and by != r["by"])):
            c.execute("UPDATE cmt SET text=?, by=?, edited=? WHERE id=?", (text.strip(), by if by is not None else r["by"], now(), cid))
            _log(c, r["key"], "Comment edited", r["by"], r["text"][:300], text.strip()[:300])


def delete_comment(cid: int) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM cmt WHERE id=?", (cid,)).fetchone()
        if r and not r["deleted"]:
            c.execute("UPDATE cmt SET deleted=1 WHERE id=?", (cid,))
            _log(c, r["key"], "Comment deleted", r["by"], r["text"][:300], "")


def add_action(key: str, text: str, owner: str = "", due: str = "") -> int:
    if not (text or "").strip():
        raise core.DeckError("Type the action first.")
    with db() as c:
        cur = c.execute("INSERT INTO act (key,text,owner,due,created) VALUES (?,?,?,?,?)", (key, text.strip(), owner.strip(), due.strip(), now()))
        _log(c, key, "Action added", owner, "", text.strip(), due)
        return cur.lastrowid


def set_action_done(aid: int, done: bool) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM act WHERE id=?", (aid,)).fetchone()
        if r and bool(r["done"]) != done:
            c.execute("UPDATE act SET done=?, done_ts=? WHERE id=?", (1 if done else 0, now() if done else None, aid))
            _log(c, r["key"], "Action done" if done else "Action reopened", r["owner"], "", r["text"])


def update_action(aid: int, **f) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM act WHERE id=?", (aid,)).fetchone()
        if not r:
            return
        for k, v in f.items():
            if k in ("text", "owner", "due") and (r[k] or "") != (v or "").strip():
                c.execute(f"UPDATE act SET {k}=? WHERE id=?", ((v or "").strip(), aid))
                _log(c, r["key"], "Action changed", k, r[k] or "", (v or "").strip())


def delete_action(aid: int) -> None:
    with db() as c:
        r = c.execute("SELECT * FROM act WHERE id=?", (aid,)).fetchone()
        if r and not r["deleted"]:
            c.execute("UPDATE act SET deleted=1 WHERE id=?", (aid,))
            _log(c, r["key"], "Action deleted", r["owner"], r["text"], "")


# --------------------------------------------------------------------------- overview for the list
def overview() -> Dict[str, dict]:
    """key -> {needs: 'Investor, EPC', open_reqs, open_actions, overdue, last_comment, last_activity, stage, priority, lead, pm}."""
    out: Dict[str, dict] = {}
    with db() as c:
        for r in c.execute("SELECT * FROM proj"):
            out[r["key"]] = {"stage": r["stage"], "priority": r["priority"], "lead": r["lead"], "pm": r["pm"], "summary": r["summary"],
                             "next_review": r["next_review"] or ""}
        def slot(k):
            return out.setdefault(k, {"stage": "To discuss", "priority": "Medium", "lead": "", "pm": "", "summary": "", "next_review": ""})
        needs: Dict[str, List[str]] = {}
        for r in c.execute("SELECT key, kind, status FROM req WHERE deleted=0 ORDER BY id"):
            s = slot(r["key"])
            s["n_reqs"] = s.get("n_reqs", 0) + 1
            if r["status"] not in CLOSED_REQ:
                s["open_reqs"] = s.get("open_reqs", 0) + 1
                needs.setdefault(r["key"], [])
                if r["kind"] not in needs[r["key"]]:
                    needs[r["key"]].append(r["kind"])
        for k, v in needs.items():
            out[k]["needs"] = ", ".join(v)
        td = today()
        td7 = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        for r in c.execute("SELECT key, due FROM act WHERE deleted=0 AND done=0"):
            s = slot(r["key"])
            s["open_actions"] = s.get("open_actions", 0) + 1
            if r["due"] and td <= r["due"] <= td7:
                s["due7"] = s.get("due7", 0) + 1
            if r["due"] and r["due"] < td:
                s["overdue"] = s.get("overdue", 0) + 1
        for r in c.execute("SELECT key, by, day, text FROM cmt WHERE deleted=0 ORDER BY day, id"):
            s = slot(r["key"])
            s["last_comment"] = f"{r['day']} {r['by']}: {r['text']}"
            s["n_cmts"] = s.get("n_cmts", 0) + 1
        for r in c.execute("SELECT key, MAX(ts) t FROM log WHERE key<>'' AND action NOT IN ('Project appeared in the deck','Project back in the deck','Project no longer in the deck') GROUP BY key"):
            slot(r["key"])["last_activity"] = r["t"]
    for s in out.values():
        s.setdefault("needs", "")
        s.setdefault("open_reqs", 0)
        s.setdefault("open_actions", 0)
        s.setdefault("overdue", 0)
        s.setdefault("due7", 0)
        s.setdefault("n_cmts", 0)
        s.setdefault("n_reqs", 0)
        s.setdefault("last_comment", "")
        s.setdefault("last_activity", "")
    return out


# --------------------------------------------------------------------------- keep the desk in step with the deck
def note_deck(projects: Iterable[dict]) -> List[str]:
    """Compare the projects now in the base deck with those seen before; log new / vanished ones. Returns messages."""
    msgs: List[str] = []
    cur = {p["id"]: p for p in projects}
    with db() as c:
        seen = {r["key"]: r["in_deck"] for r in c.execute("SELECT key, in_deck FROM seen")}
        first = not seen
        for k, p in cur.items():
            if k not in seen:
                c.execute("INSERT INTO seen VALUES (?,?,1)", (k, now()))
                if not first:
                    _log(c, k, "Project appeared in the deck", note=p.get("name", ""))
                    msgs.append(f"{p.get('name', k)} appeared in the deck")
            elif not seen[k]:
                c.execute("UPDATE seen SET in_deck=1 WHERE key=?", (k,))
                _log(c, k, "Project back in the deck", note=p.get("name", ""))
        for k, v in seen.items():
            if v and k not in cur:
                c.execute("UPDATE seen SET in_deck=0 WHERE key=?", (k,))
                _log(c, k, "Project no longer in the deck", note="removed from the base deck (its desk notes are kept)")
                msgs.append(f"{k} is no longer in the deck")
        if first and cur:
            _log(c, "", "Desk linked to deck", note=f"{len(cur)} projects found in the base deck")
    return msgs


def rename_key(old: str, new: str) -> None:
    with db() as c:
        for t in ("proj", "req", "cmt", "act", "seen"):
            if t in ("proj", "seen"):
                if c.execute(f"SELECT 1 FROM {t} WHERE key=?", (new,)).fetchone():
                    c.execute(f"DELETE FROM {t} WHERE key=?", (new,))
            c.execute(f"UPDATE {t} SET key=? WHERE key=?", (new, old))
        c.execute("UPDATE log SET key=? WHERE key=?", (new, old))
        _log(c, new, "Key renamed", "key", old, new)


# --------------------------------------------------------------------------- Excel
def _rows_for_export(projects: List[dict], scoped: bool = False, since: str = "") -> dict:
    ov = overview()
    names = {p["id"]: p for p in projects}
    ks = set(names)
    inscope = (lambda k: k in ks) if scoped else (lambda k: True)
    def pn(k):
        return names[k]["name"] if k in names else f"{k} (not in deck)"
    summary = []
    for p in projects:
        o = ov.get(p["id"], {})
        pr = get_proj(p["id"], p.get("country", ""))
        summary.append([p.get("sr", ""), p["name"], p.get("country", ""), p.get("sector", ""), p.get("category", ""), pr["lead_eff"] or "unassigned",
                        pr["pm_eff"], o.get("stage", "To discuss"), o.get("priority", "Medium"), o.get("needs", ""), o.get("open_reqs", 0),
                        o.get("open_actions", 0), o.get("overdue", 0), o.get("summary", ""), o.get("last_comment", ""), o.get("last_activity", "")])
    with db() as c:
        rq = [[pn(r["key"]), r["kind"], r["detail"], r["status"], r["created"], r["updated"], "deleted" if r["deleted"] else ""]
              for r in c.execute("SELECT * FROM req ORDER BY key, id") if inscope(r["key"])]
        cm = [[pn(r["key"]), r["day"], r["by"], r["text"], r["ts"], r["edited"] or "", "deleted" if r["deleted"] else ""]
              for r in c.execute("SELECT * FROM cmt ORDER BY key, day, id") if inscope(r["key"])]
        ac = [[pn(r["key"]), r["text"], r["owner"], r["due"], "Done" if r["done"] else "Open", r["created"], r["done_ts"] or "",
               "deleted" if r["deleted"] else ""] for r in c.execute("SELECT * FROM act ORDER BY key, id") if inscope(r["key"])]
        lg = [[r["ts"], r["user"], pn(r["key"]) if r["key"] else "", r["action"], r["field"], r["old"], r["new"], r["note"]]
              for r in c.execute("SELECT * FROM log ORDER BY id DESC") if (not scoped or r["key"] in ks)]
        gg = [[r["country"], r["lead"]] for r in c.execute("SELECT country, lead FROM geo ORDER BY lead, country")]
    extra = {}
    if since:
        ch = [[h["ts"], h["user"], pn(h["key"]) if h["key"] else "", h["action"], h["field"], h["old"], h["new"], h["note"]]
              for h in changes_since(since, list(ks) if scoped else None)]
        extra["Desk - Changes since " + since[5:]] = (["When", "Who", "Project", "What", "Field", "Old", "New", "Note"], ch)
    return {**extra,
        "Desk - Summary": (["Sr.", "Project", "Country", "Sector", "Category", "Lead", "Project managers", "Stage", "Priority", "Needs (open)",
                            "Open requirements", "Open actions", "Overdue", "Internal summary", "Last comment", "Last activity"], summary),
        "Desk - Requirements": (["Project", "Needed", "Detail", "Status", "Added", "Updated", "Removed"], rq),
        "Desk - Comments": (["Project", "Discussion date", "By", "Comment", "Logged", "Edited", "Removed"], cm),
        "Desk - Actions": (["Project", "Action", "Owner", "Due", "Status", "Added", "Done on", "Removed"], ac),
        "Desk - Change log": (["When", "Who", "Project", "What", "Field", "Old", "New", "Note"], lg),
        "Desk - Geography": (["Country", "Lead"], gg),
    }


def write_sheets(wb, projects: List[dict], scoped: bool = False, since: str = "") -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    for name, (hdr, rows) in _rows_for_export(projects, scoped, since).items():
        if name in wb.sheetnames:
            del wb[name]
        ws = wb.create_sheet(name)
        ws.append(hdr)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1B3A5F")
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for r in rows:
            ws.append(r)
        for i, h in enumerate(hdr, 1):
            L = ws.cell(1, i).column_letter
            wide = max([len(str(h))] + [min(len(str(r[i - 1] or "")), 70) for r in rows[:300]]) if rows else len(str(h))
            ws.column_dimensions[L].width = max(10, min(wide + 2, 72))
            for cell in ws[L][1:]:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = "1:1"


def export_workbook(path: Path, projects: List[dict], scoped: bool = False, since: str = "") -> Path:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    write_sheets(wb, projects, scoped, since)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def mirror_to_registry(projects: List[dict]) -> Path:
    """Write the Desk sheets into projects_registry.xlsx (after a backup). Fails politely if Excel has the file open."""
    from openpyxl import load_workbook
    p = core.REGISTRY_XLSX
    if not p.exists():
        raise core.DeckError("The registry Excel file was not found.")
    try:
        wb = load_workbook(p)
    except PermissionError:
        raise core.DeckError("Close projects_registry.xlsx in Excel first, then try again.")
    core.BACKUP_DIR.mkdir(exist_ok=True)
    shutil.copy2(p, core.BACKUP_DIR / f"projects_registry_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    write_sheets(wb, projects)
    try:
        wb.save(p)
    except PermissionError:
        raise core.DeckError("Close projects_registry.xlsx in Excel first, then try again.")
    return p


# --------------------------------------------------------------------------- hooks: every deck operation lands in the log
def install_hooks(pm) -> None:
    """Wrap the project-manager operations so that add / delete / modify are logged automatically."""
    import functools

    def snap(keys=None):
        try:
            return {p["id"]: p for p in core.load_projects("EPC")["projects"]}
        except Exception:
            return {}

    def wrap(name, before, after):
        fn = getattr(pm, name)
        if getattr(fn, "_desk_hooked", False):
            return

        @functools.wraps(fn)
        def w(*a, **k):
            ctx = before(*a, **k) if before else None
            res = fn(*a, **k)
            try:
                after(ctx, res, *a, **k)
            except Exception:
                pass
            return res
        w._desk_hooked = True
        setattr(pm, name, w)

    def keys_of(a, k, pos=1):
        v = k.get("keys", a[pos] if len(a) > pos else [])
        return [core.norm_id(x) for x in v]

    wrap("delete_projects", lambda *a, **k: snap(),
         lambda s, r, *a, **k: [log_event(x, "Slides deleted from deck",
                                          note=(", ".join(k.get("versions") or (a[2] if len(a) > 2 and a[2] else [])) or "all versions")
                                          + (" - project removed from the deck" if x in r.get("projects_gone", []) else ""))
                                for x in keys_of(a, k)])
    wrap("set_retired", None,
         lambda s, r, *a, **k: [log_event(x, "Retired (hidden)" if (k.get("retired", a[2] if len(a) > 2 else False)) else "Restored (unhidden)")
                                for x in keys_of(a, k)])

    def pre_update(*a, **k):
        return snap()

    def post_update(s, r, *a, **k):
        ch = k.get("changes", a[2] if len(a) > 2 else {})
        for x in keys_of(a, k):
            old = s.get(x, {})
            for f, v in ch.items():
                o = old.get(f, "")
                if f == "include":
                    o = "YES" if old.get("include") else "NO"
                if str(o or "") != str(v or ""):
                    log_event(x, "Deck attribute changed", f, o, v)
    wrap("update_fields", pre_update, post_update)

    def post_rename(s, r, *a, **k):
        old, new = core.norm_id(a[1]), core.norm_id(a[2])
        rename_key(old, new)
    wrap("rename_project", None, post_rename)
    wrap("duplicate_project", None, lambda s, r, *a, **k: log_event(core.norm_id(a[2]), "Project created as a copy", note="copied from " + core.norm_id(a[1])))
    wrap("add_project", None, lambda s, r, *a, **k: log_event(r.get("key", ""), "Project added to the deck",
                                                              note="slides: " + str(k.get("versions", a[2] if len(a) > 2 else "both"))))
    wrap("refresh_project_slides", None, lambda s, r, *a, **k: log_event(a[1]["key"], "Slide content updated", note="slides " + str(r.get("slides"))))
    wrap("restore_backup", None, lambda s, r, *a, **k: log_event("", "Deck restored from backup", note=str(a[1] if len(a) > 1 else "")))
    wrap("move_projects", None, lambda s, r, *a, **k: [log_event(x, "Moved in deck order", note=str(a[2] if len(a) > 2 else k.get("where", "")))
                                                       for x in keys_of(a, k)] if r.get("moved") else None)


def snapshot(projects: List[dict]) -> Optional[Path]:
    """Safety copy of EVERYTHING as a plain Excel file (data/Desk_snapshot.xlsx). Best effort, never raises."""
    try:
        return export_workbook(DATA_DIR / "Desk_snapshot.xlsx", projects)
    except Exception:
        return None


# --------------------------------------------------------------------------- review helpers (daily / weekly use)
def mark_reviewed(key: str, days: int = 7, note: str = "") -> str:
    """'I went through this project today': logged, and the next review is set `days` ahead. Returns the next-review date."""
    nxt = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    with db() as c:
        if not c.execute("SELECT 1 FROM proj WHERE key=?", (key,)).fetchone():
            c.execute("INSERT INTO proj (key, updated) VALUES (?,?)", (key, now()))
        c.execute("UPDATE proj SET next_review=?, updated=? WHERE key=?", (nxt, now(), key))
        _log(c, key, "Reviewed", note=(note + "  " if note else "") + f"next review {nxt}")
    return nxt


def changes_since(since: str, keys: Optional[List[str]] = None) -> List[dict]:
    """Log rows from the start of day `since` (YYYY-MM-DD) onwards, oldest first; optionally only for the given project keys."""
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM log WHERE ts>=? ORDER BY id", (since + " 00:00:00",))]
    if keys is not None:
        ks = set(keys)
        rows = [r for r in rows if r["key"] in ks]
    return rows


def all_actions(keys: Optional[List[str]] = None, owner: str = "", include_done: bool = False) -> List[dict]:
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM act WHERE deleted=0" + ("" if include_done else " AND done=0") + " ORDER BY id")]
    if keys is not None:
        ks = set(keys)
        rows = [r for r in rows if r["key"] in ks]
    if owner:
        rows = [r for r in rows if (r["owner"] or "").lower() == owner.lower()]
    return sorted(rows, key=lambda r: (r["done"], r["due"] or "9999-99-99", r["id"]))


def deleted_items(key: str) -> List[dict]:
    out = []
    with db() as c:
        for r in c.execute("SELECT id, kind, detail, status, updated FROM req WHERE key=? AND deleted=1", (key,)):
            out.append({"type": "req", "id": r["id"], "text": f"Need - {r['kind']}: {r['detail']}", "when": r["updated"] or ""})
        for r in c.execute("SELECT id, by, day, text, ts FROM cmt WHERE key=? AND deleted=1", (key,)):
            out.append({"type": "cmt", "id": r["id"], "text": f"Comment ({r['day']}, {r['by']}): {r['text']}", "when": r["ts"] or ""})
        for r in c.execute("SELECT id, text, owner, due, created FROM act WHERE key=? AND deleted=1", (key,)):
            out.append({"type": "act", "id": r["id"], "text": f"Action ({r['owner']}, due {r['due']}): {r['text']}", "when": r["created"] or ""})
    return out


def restore_item(kind: str, item_id: int) -> None:
    table = {"req": "req", "cmt": "cmt", "act": "act"}[kind]
    with db() as c:
        r = c.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        if r and r["deleted"]:
            c.execute(f"UPDATE {table} SET deleted=0 WHERE id=?", (item_id,))
            what = {"req": "need", "cmt": "comment", "act": "action"}[kind]
            _log(c, r["key"], "Restored deleted " + what, note=str(r["detail"] if kind == "req" else r["text"])[:200])


def ui_get() -> dict:
    import json
    try:
        with db() as c:
            r = c.execute("SELECT v FROM meta WHERE k='ui'").fetchone()
        return json.loads(r[0]) if r else {}
    except Exception:
        return {}


def ui_set(d: dict) -> None:
    import json
    try:
        with db() as c:
            c.execute("INSERT OR REPLACE INTO meta VALUES ('ui',?)", (json.dumps(d),))
    except Exception:
        pass


# --------------------------------------------------------------------------- imported internal status (from the team's Excel file)
def ext_save(path: str, fname: str, mtime: float, summary: dict, rows: List[dict]) -> int:
    import json
    with db() as c:
        cur = c.execute("INSERT INTO ext_batch (ts,user,path,fname,mtime,summary) VALUES (?,?,?,?,?,?)",
                        (now(), get_user(c), path, fname, mtime, json.dumps(summary)))
        bid = cur.lastrowid
        c.executemany("INSERT INTO ext_row (batch,sheet,rownum,country,name,data) VALUES (?,?,?,?,?,?)",
                      [(bid, r["sheet"], r["row"], r["country"], r["name"],
                        json.dumps({"fields": r["fields"], "parties": r["parties"], "banks": r["banks"]})) for r in rows])
        for old in [r[0] for r in c.execute("SELECT id FROM ext_batch ORDER BY id DESC LIMIT -1 OFFSET 5")]:
            c.execute("DELETE FROM ext_row WHERE batch=?", (old,))
            c.execute("DELETE FROM ext_batch WHERE id=?", (old,))
        return bid


def ext_batch() -> Optional[dict]:
    """The latest import (path, file name, when, summary) or None when no status file has been loaded."""
    import json
    with db() as c:
        r = c.execute("SELECT * FROM ext_batch ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return None
    d = dict(r)
    d["summary"] = json.loads(d["summary"] or "{}")
    return d


def ext_rows() -> List[dict]:
    import json
    b = ext_batch()
    if not b:
        return []
    with db() as c:
        out = []
        for r in c.execute("SELECT * FROM ext_row WHERE batch=? ORDER BY id", (b["id"],)):
            d = json.loads(r["data"])
            out.append({"sheet": r["sheet"], "row": r["rownum"], "country": r["country"], "name": r["name"],
                        "fields": d["fields"], "parties": d["parties"], "banks": d["banks"]})
        return out


def ext_links() -> Dict[str, dict]:
    with db() as c:
        return {r["key"]: {"norm": r["norm"], "country": r["country"]} for r in c.execute("SELECT * FROM ext_link")}


def ext_set_link(key: str, norm: Optional[str], country: str = "") -> None:
    """norm=None removes the manual link; norm='' means 'this project has no data in the file'."""
    with db() as c:
        if norm is None:
            c.execute("DELETE FROM ext_link WHERE key=?", (key,))
            _log(c, key, "Status link reset")
        else:
            c.execute("INSERT OR REPLACE INTO ext_link VALUES (?,?,?)", (key, norm, country))
            _log(c, key, "Status link set" if norm else "Marked: no data in status file", note=norm)


def ext_clear() -> None:
    with db() as c:
        c.execute("DELETE FROM ext_row")
        c.execute("DELETE FROM ext_batch")
        _log(c, "", "Status data removed", note="the imported status file data was cleared")
