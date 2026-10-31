#!/usr/bin/env python3
"""Blend Hub - data layer.

Transactions (every project in the BIP file + the deck), counterparties (EPCs, investors, banks / lenders, ECAs, insurers),
the mapping between them, a readiness checklist, comments + actions + reviews per transaction, geography / bosses,
and a full activity log with per-field undo.

OneDrive: one SQLite file (journal mode DELETE, no WAL), ONE editor at a time (edit lock with a heartbeat), automatic backups.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = DATA / "hub.db"
LOCK_PATH = DATA / "hub.lock"
BACKUPS = DATA / "backups"

# ----------------------------------------------------------------------------- vocabulary (one place, used by the UI too)
STATUSES = ["Tie-up done", "P1", "P2", "Preliminary", "On hold"]  # INTERNAL review status
CLIENT_TYPES = ["Government", "SOE", "Private", "To confirm"]
PROCUREMENT = ["Tender", "Negotiated", "Both", "To confirm"]
EXT_CATEGORIES = ["BIP", "Active", "Hold", "Closed"]  # what outside parties see (kept for the decks)
PARTY_TYPES = ["EPC", "Investor", "Bank / Lender", "ECA", "Insurer"]
LINK_STATUS = ["Identified", "Shortlisted", "To be approached", "Approached", "In discussion", "Term sheet received", "Appointed", "Dropped"]
SHORTLISTED_UP = LINK_STATUS[1:7]
CHECK_STATES = ["Yes", "In progress", "No", "N.A."]
CHECK_GROUPS = [["Information & studies", ["Information package received", "Pre-feasibility / APS", "FSR (feasibility study)", "Technical documents", "ESIA / permits", "Land available",
                                           "Financial model available", "Owner financials received"]],
                ["Agreements & guarantees", ["EPC contract signed", "Concession agreement", "Offtake agreement", "Government guarantee", "MoU with owner"]],
                ["Submissions", ["Project proposal submitted", "LoI / EoI submitted"]]]
CHECK_ITEMS = [i for _, g in CHECK_GROUPS for i in g]
USD_PER_EUR = 1.15  # the same rate the figures already in the Hub were converted with
MEETING = ["Not held", "To be scheduled", "Requested", "Scheduled", "Held"]
MEETING_KINDS = ["To be scheduled", "Requested", "Scheduled", "Held", "Cancelled"]
SUB_DEFAULT = {"JT": "Sunil", "RB": "Karan", "SS": "Heena"}  # the sub-owner who works for each owner (used when a sub-owner is not chosen)
LOI_RESPONSE = ["", "Awaiting", "Accepted", "Negotiating", "Rejected"]
INFO_STATE = ["Not requested", "Requested", "Partial", "Received"]
MODEL_STATE = ["Not available", "In progress", "Available"]
REVIEW_OUTCOME = ["Pending", "Proceed", "Customise", "Hold", "Drop"]
YESNO = ["No", "Yes"]
COMMENT_KINDS = ["", "Management"]
LEADS = ["RB", "JT", "SS"]
MODELS = ["EPC", "EPC+F", "PPP - Annuity", "PPP - DBFOT", "PPP - DBFM", "PPP - BOT", "IPP", "Financing only", "Supply", "Partnership", "N/D"]  # N/D = not decided
_MODEL_FIX = {"BOT": "PPP - BOT", "DBFM": "PPP - DBFM", "DBFOT": "PPP - DBFOT", "Project-EPCF": "EPC+F", "Finance": "Financing only", "": "N/D"}
PRIORITIES = ["High", "Medium", "Low"]
PMS = "Vishnu & Vijayraj"
NO_NAMES = {"": "", "mp": "Mohsin Patel", "j": "Japhet"}  # source spellings fixed once, everywhere

SCHEMA = """
CREATE TABLE IF NOT EXISTS txn (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, name TEXT, country TEXT DEFAULT '', sector TEXT DEFAULT '',
  structure TEXT DEFAULT '', value TEXT DEFAULT '', client_type TEXT DEFAULT 'To confirm', status TEXT DEFAULT 'Preliminary',
  ext_category TEXT DEFAULT 'BIP', procurement TEXT DEFAULT 'To confirm', lead TEXT DEFAULT '', introduced TEXT DEFAULT '',
  counterparty TEXT DEFAULT '', summary TEXT DEFAULT '', next_steps TEXT DEFAULT '', deck_key TEXT DEFAULT '', reason TEXT DEFAULT '',
  active INTEGER DEFAULT 1, origin TEXT DEFAULT '', created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS party (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT COLLATE NOCASE, type TEXT, country TEXT DEFAULT '', notes TEXT DEFAULT '',
  active INTEGER DEFAULT 1, UNIQUE(name, type));
CREATE TABLE IF NOT EXISTS link (
  txn_id INTEGER, party_id INTEGER, status TEXT DEFAULT 'Identified', remark TEXT DEFAULT '', updated TEXT, by TEXT DEFAULT '',
  PRIMARY KEY (txn_id, party_id));
CREATE TABLE IF NOT EXISTS need (txn_id INTEGER, type TEXT, state TEXT DEFAULT 'Needed', PRIMARY KEY (txn_id, type));
CREATE TABLE IF NOT EXISTS chk (txn_id INTEGER, item TEXT, state TEXT DEFAULT '', remark TEXT DEFAULT '', updated TEXT, PRIMARY KEY (txn_id, item));
CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, by TEXT, txn_id INTEGER, what TEXT, detail TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS access (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, country TEXT DEFAULT '', ministry TEXT DEFAULT '', contact TEXT DEFAULT '', notes TEXT DEFAULT '', created TEXT, by TEXT DEFAULT '', deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS comment (id INTEGER PRIMARY KEY AUTOINCREMENT, txn_id INTEGER, ts TEXT, day TEXT, by TEXT, text TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS action (id INTEGER PRIMARY KEY AUTOINCREMENT, txn_id INTEGER, text TEXT, owner TEXT DEFAULT '', due TEXT DEFAULT '',
  done INTEGER DEFAULT 0, done_ts TEXT DEFAULT '', created TEXT, by TEXT DEFAULT '', deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS meeting (id INTEGER PRIMARY KEY AUTOINCREMENT, txn_id INTEGER, day TEXT DEFAULT '', who TEXT DEFAULT '', status TEXT DEFAULT 'Held',
  notes TEXT DEFAULT '', by TEXT DEFAULT '', created TEXT, deleted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS geo (country TEXT PRIMARY KEY, lead TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS imp (txn_id INTEGER, field TEXT, val TEXT, PRIMARY KEY (txn_id, field));
"""
MIGRATE = {  # column additions to tables created by older versions
    "action": [("auto", "TEXT DEFAULT ''")],
    "txn": [("deleted", "INTEGER DEFAULT 0"), ("last_reviewed", "TEXT DEFAULT ''"), ("next_review", "TEXT DEFAULT ''"),
            ("priority", "TEXT DEFAULT 'Medium'"), ("sub_lead", "TEXT DEFAULT ''"),
            ("meeting_status", "TEXT DEFAULT 'Not held'"), ("meeting_with", "TEXT DEFAULT ''"), ("meeting_date", "TEXT DEFAULT ''"), ("meeting_notes", "TEXT DEFAULT ''"),
            ("value_orig", "TEXT DEFAULT ''"), ("loi_sent", "TEXT DEFAULT 'No'"), ("loi_date", "TEXT DEFAULT ''"), ("loi_response", "TEXT DEFAULT ''"), ("loi_notes", "TEXT DEFAULT ''"),
            ("info_status", "TEXT DEFAULT 'Not requested'"), ("info_notes", "TEXT DEFAULT ''"),
            ("fm_status", "TEXT DEFAULT 'Not available'"), ("fm_notes", "TEXT DEFAULT ''"),
            ("ofin_status", "TEXT DEFAULT 'Not requested'"), ("ofin_notes", "TEXT DEFAULT ''"),
            ("received_date", "TEXT DEFAULT ''"), ("data_date", "TEXT DEFAULT ''"), ("review_date", "TEXT DEFAULT ''"),
            ("review_outcome", "TEXT DEFAULT 'Pending'"), ("review_notes", "TEXT DEFAULT ''")],
    "comment": [("kind", "TEXT DEFAULT ''")],
    "log": [("field", "TEXT DEFAULT ''"), ("oldv", "TEXT DEFAULT ''"), ("newv", "TEXT DEFAULT ''")],
}

_mutex = threading.Lock()


class HubError(Exception):
    pass


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=DELETE")
    c.executescript(SCHEMA)
    for tbl, cols in MIGRATE.items():
        have = {r[1] for r in c.execute(f"PRAGMA table_info({tbl})")}
        for name, decl in cols:
            if name not in have:
                c.execute(f"ALTER TABLE {tbl} ADD COLUMN {name} {decl}")
    _ensure_journal(c)
    if not c.execute("SELECT 1 FROM geo LIMIT 1").fetchone():
        _seed_geo(c)
    _normalize(c)
    _sync_loi(c)
    c.commit()
    return c


def value_to_eur(v):
    """Whatever was typed ('USD 120-180 Mn', '2BN', '75 MN EURO') -> a number in EUR million, or None. No currency = EUR."""
    t = str(v if v is not None else "").strip()
    if not t or not re.search(r"\d", t):
        return None
    if re.fullmatch(r"[\d.]+", t):
        n = float(t)
        return n / 1e6 if n >= 1e5 else n
    unit = 1000 if re.search(r"\d\s*bn\b|billion|\bbn\b", t, re.I) else 1
    fx = 1 / USD_PER_EUR if re.search(r"usd|\$|us\s*dollar", t, re.I) and not re.search(r"eur", t, re.I) else 1
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    rg = re.search(r"(\d[\d.]*)\s*[\u2013-]\s*(\d[\d.]*)", t)
    try:
        n = (float(rg.group(1)) + float(rg.group(2))) / 2 if rg else (float(nums[0]) + float(nums[1]) if "+" in t and len(nums) > 1 else float(nums[0]))
    except (ValueError, IndexError):
        return None
    return n * unit * fx


def _num(n) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def find_date(text) -> str:
    """22.06.26 / 22/06/2026 / 'June 2026' (-> the 1st of that month) -> YYYY-MM-DD, else ''."""
    t = str(text or "")
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(20\d\d)\b", t, re.I)
    if m:
        return f"{int(m.group(2)):04d}-{_MONTHS[m.group(1).lower()[:3]]:02d}-01"
    return ""


def _normalize(c):
    """Idempotent tidy-ups: one name for the LoI/EoI item, values as plain EUR numbers (the original text is kept), parked = On hold."""
    try:
        c.execute("UPDATE link SET status='Term sheet received' WHERE status='LOI / Term sheet'")
        for t in c.execute("SELECT id, meeting_status, meeting_with, meeting_date, meeting_notes FROM txn WHERE meeting_status IN ('Requested','Scheduled','Held') AND id NOT IN (SELECT txn_id FROM meeting)").fetchall():
            c.execute("INSERT INTO meeting(txn_id,day,who,status,notes,by,created) VALUES(?,?,?,?,?,?,?)", (t["id"], t["meeting_date"] or "", t["meeting_with"] or "", t["meeting_status"], t["meeting_notes"] or "", "Migrated", now()))
        c.execute("UPDATE OR IGNORE chk SET item='LoI / EoI submitted' WHERE item='EOI submitted'")
        c.execute("DELETE FROM chk WHERE item='EOI submitted'")
        for r in c.execute("SELECT t.id, k.remark FROM txn t JOIN chk k ON k.txn_id=t.id AND k.item='LoI / EoI submitted' WHERE k.state='Yes' AND t.loi_date=''").fetchall():
            d = find_date(r["remark"])
            if d:
                c.execute("UPDATE txn SET loi_date=? WHERE id=?", (d, r["id"]))
        for r in c.execute("SELECT id, value FROM txn").fetchall():
            v = (r["value"] or "").strip()
            if v and re.fullmatch(r"\d+\.\d{3,}", v) and float(v) < 1e5:
                c.execute("UPDATE txn SET value=? WHERE id=?", (_num(float(v)), r["id"]))
            elif v and (not re.fullmatch(r"\d+(\.\d+)?", v) or float(v) >= 1e5):
                n = value_to_eur(v)
                c.execute("UPDATE txn SET value=?, value_orig=CASE WHEN value_orig='' THEN ? ELSE value_orig END WHERE id=?", ("" if n is None else _num(n), v, r["id"]))
        c.execute("UPDATE txn SET meeting_status='Not held' WHERE meeting_status='Not started'")
        c.execute("UPDATE meeting SET status='Not held' WHERE status='Not started'")
        c.execute("UPDATE action SET owner=COALESCE(NULLIF((SELECT sub_lead FROM txn WHERE txn.id=action.txn_id),''),(SELECT lead FROM txn WHERE txn.id=action.txn_id),'') WHERE auto!='' AND owner=''")
        for old, new in _MODEL_FIX.items():
            c.execute("UPDATE txn SET structure=? WHERE structure=?", (new, old))
        c.execute("UPDATE txn SET active=0 WHERE status='On hold' AND active=1")
        c.execute("UPDATE txn SET active=1 WHERE status!='On hold' AND active=0")
    except sqlite3.Error:
        pass


def _sync_loi(c):
    """'LoI / EoI submitted' (Readiness) and 'LOI sent' (Tracker) are one fact - keep them identical."""
    try:
        for r in c.execute("SELECT t.id, k.remark FROM txn t JOIN chk k ON k.txn_id=t.id AND k.item='LoI / EoI submitted' WHERE k.state='Yes' AND t.loi_sent!='Yes'").fetchall():
            rem = r["remark"] or ""
            c.execute("UPDATE txn SET loi_sent='Yes', loi_response=CASE WHEN loi_response='' THEN ? ELSE loi_response END, loi_notes=CASE WHEN loi_notes='' THEN ? ELSE loi_notes END WHERE id=?",
                      ("Accepted" if "accept" in rem.lower() else "Awaiting", rem, r["id"]))
        c.execute("INSERT OR IGNORE INTO chk(txn_id,item,state,remark,updated) SELECT id,'LoI / EoI submitted','Yes','',? FROM txn WHERE loi_sent='Yes'", (now(),))
    except sqlite3.Error:
        pass


def _seed_geo(c):
    """Owner per country: the distribution already kept in the Desk, else the original RB / JT / SS split."""
    rows = []
    try:
        import tracker as T
        rows = [(g["country"], g["lead"]) for g in T.geo_list()]
    except Exception:
        pass
    c.executemany("INSERT OR IGNORE INTO geo(country, lead) VALUES(?,?)", rows)


# ----------------------------------------------------------------------------- edit lock (one writer on OneDrive)
class Lock:
    """data/hub.lock = who is editing; refreshed every 20 s. Older than 90 s = abandoned (crash / laptop closed)."""
    STALE = 90

    def __init__(self, user: str):
        self.user, self.host, self.mine = user, socket.gethostname(), False
        self.holder, self._stop = "", False

    def _read(self) -> Optional[dict]:
        try:
            return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write(self):
        DATA.mkdir(exist_ok=True)
        LOCK_PATH.write_text(json.dumps({"user": self.user, "host": self.host, "ts": time.time(), "pid": os.getpid()}), encoding="utf-8")

    def try_acquire(self, force: bool = False) -> bool:
        cur = self._read()
        fresh = bool(cur) and (time.time() - cur.get("ts", 0)) < self.STALE
        mine_already = bool(cur) and cur.get("host") == self.host and cur.get("pid") == os.getpid()
        if force or not cur or not fresh or mine_already:
            self._write()
            self.mine, self.holder = True, self.user
        else:
            self.mine, self.holder = False, f"{cur.get('user', '?')} ({cur.get('host', '?')})"
        return self.mine

    def start(self):
        self.try_acquire()

        def beat():
            while not self._stop:
                time.sleep(20)
                try:
                    self.try_acquire() if not self.mine else self._write()
                except Exception:
                    pass
        threading.Thread(target=beat, daemon=True).start()

    def release(self):
        self._stop = True
        cur = self._read()
        if self.mine and cur and cur.get("pid") == os.getpid():
            try:
                LOCK_PATH.unlink()
            except OSError:
                pass


# ----------------------------------------------------------------------------- backups
def backup(keep: int = 30, every_hours: float = 6, force: bool = False) -> Optional[Path]:
    if not DB_PATH.exists():
        return None
    BACKUPS.mkdir(exist_ok=True)
    files = sorted(BACKUPS.glob("hub_*.db"))
    if not force and files and time.time() - files[-1].stat().st_mtime < every_hours * 3600:
        return None
    dst = BACKUPS / f"hub_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(DB_PATH, dst)
    for old in sorted(BACKUPS.glob("hub_*.db"))[:-keep]:
        old.unlink()
    return dst


# ----------------------------------------------------------------------------- reading
LOW = ("Preliminary", "On hold")  # what the hide switches keep out of every screen, print and report


def hide_set(hide) -> tuple:
    """hide: True / "1" = both, "P" = Preliminary, "H" = On hold, "PH" = both, False / "" = nothing -> the statuses to keep out."""
    if hide is True or hide == "1":
        return LOW
    h = str(hide or "").upper()
    return tuple(s for k, s in (("P", "Preliminary"), ("H", "On hold")) if k in h)


FIN_ONLY = "Financing only"  # model of a pure financing deal


def _hidden_ids(c, hide, txns) -> set:
    """Transactions kept out by the hide letters: P preliminary, H on hold, F pure financing deals, N EPC marked 'not needed'."""
    h = str(hide or "").upper() if hide not in (True, "1") else "PH"
    nn = {r[0] for r in c.execute("SELECT txn_id FROM need WHERE type='EPC' AND state='Not needed'")} if "N" in h else set()
    out = hide_set(h)
    return {t["id"] for t in txns if t["status"] in out or ("F" in h and t["structure"] == FIN_ONLY) or t["id"] in nn}


def snapshot(hide="") -> dict:
    out = hide_set(hide)
    hide_letters = hide
    hide = bool(str(hide_letters or "").strip()) and hide_letters is not False
    c = connect()
    try:
        rows = lambda q, a=(): [dict(r) for r in c.execute(q, a)]
        last = {r["txn_id"]: r["ts"] for r in c.execute("SELECT txn_id, MAX(ts) ts FROM log WHERE txn_id IS NOT NULL GROUP BY txn_id")}
        txns = rows("SELECT * FROM txn WHERE deleted=0 ORDER BY country, name")
        for t in txns:
            t["last_activity"] = last.get(t["id"], t.get("updated") or "")
        if hide:
            gone = _hidden_ids(c, hide_letters, txns)
            txns = [t for t in txns if t["id"] not in gone]
        keep = {t["id"] for t in txns}
        mine = (lambda r: r["txn_id"] in keep) if hide else (lambda r: True)
        parties = rows("SELECT * FROM party WHERE active=1 ORDER BY type, name")
        links = [l for l in rows("SELECT txn_id, party_id, status, remark, updated, by FROM link") if mine(l)]
        if hide:  # a counterparty that is only mapped to hidden transactions is hidden too
            used = {l["party_id"] for l in links}
            anywhere = {r[0] for r in c.execute("SELECT DISTINCT party_id FROM link")}
            parties = [p for p in parties if p["id"] in used or p["id"] not in anywhere]
        undo = _undo_candidate(c)
        return {
            "txns": txns,
            "hidden": hide,
            "trash": [t for t in rows("SELECT id, name, country, status FROM txn WHERE deleted=1 ORDER BY name") if t["status"] not in out],
            "parties": parties,
            "links": links,
            "needs": [r for r in rows("SELECT txn_id, type, state FROM need") if mine(r)],
            "chk": [r for r in rows("SELECT txn_id, item, state, remark FROM chk") if mine(r)],
            "comments": [r for r in rows("SELECT id, txn_id, ts, day, by, text, kind FROM comment WHERE deleted=0 ORDER BY day DESC, id DESC") if mine(r)],
            "undo": undo, "redo": _redo_candidate(c),
            "actions": [r for r in rows("SELECT id, txn_id, text, owner, due, done, done_ts, created, by, auto FROM action WHERE deleted=0 ORDER BY done, due='' , due, id") if mine(r)],
            "meetings": [r for r in rows("SELECT id, txn_id, day, who, status, notes, by FROM meeting WHERE deleted=0 ORDER BY day='' , day DESC, id DESC") if mine(r)],
            "geo": rows("SELECT country, lead FROM geo ORDER BY country"),
            "access": rows("SELECT id, source, country, ministry, contact, notes, created, by FROM access WHERE deleted=0 ORDER BY source, country, ministry"),
            "rev": int((c.execute("SELECT v FROM meta WHERE k='rev'").fetchone() or ["0"])[0]),
            "pms": PMS,
            "enums": {"statuses": [x for x in STATUSES if x not in out], "all_statuses": STATUSES, "models": MODELS, "client_types": CLIENT_TYPES, "procurement": PROCUREMENT, "ext": EXT_CATEGORIES,
                      "party_types": PARTY_TYPES, "link_status": LINK_STATUS, "shortlisted_up": SHORTLISTED_UP, "check_states": CHECK_STATES,
                      "check_items": CHECK_ITEMS, "check_groups": CHECK_GROUPS, "leads": LEADS, "priorities": PRIORITIES,
                      "meeting": MEETING, "meeting_kinds": MEETING_KINDS, "loi_response": LOI_RESPONSE, "info_state": INFO_STATE, "model_state": MODEL_STATE, "review_outcome": REVIEW_OUTCOME},
        }
    finally:
        c.close()


def history(txn_id: int, limit: int = 120) -> List[dict]:
    c = connect()
    try:
        return [dict(r) for r in c.execute("SELECT id, ts, by, what, detail, field, oldv, newv FROM log WHERE txn_id=? ORDER BY id DESC LIMIT ?", (txn_id, limit))]
    finally:
        c.close()


def _hide_sql(hide) -> str:
    h = str(hide or "").upper() if hide not in (True, "1") else "PH"
    cond = []
    if hide_set(h):
        cond.append("t.status NOT IN (%s)" % ",".join("'%s'" % s for s in hide_set(h)))
    if "F" in h:
        cond.append("t.structure!='%s'" % FIN_ONLY)
    if "N" in h:
        cond.append("NOT EXISTS (SELECT 1 FROM need n WHERE n.txn_id=t.id AND n.type='EPC' AND n.state='Not needed')")
    return "AND (t.id IS NULL OR (" + " AND ".join(cond) + ")) " if cond else ""


def recent_changes(days: int = 7, limit: int = 300, hide="") -> List[dict]:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c = connect()
    try:
        return [dict(r) for r in c.execute("SELECT l.ts, l.by, l.what, l.detail, l.txn_id, t.name FROM log l LEFT JOIN txn t ON t.id=l.txn_id "
                                           "WHERE l.ts>=? " + _hide_sql(hide) + "ORDER BY l.id DESC LIMIT ?", (since, limit))]
    finally:
        c.close()


# ----------------------------------------------------------------------------- writing helpers
def _bump(c):
    c.execute("INSERT INTO meta(k,v) VALUES('rev','1') ON CONFLICT(k) DO UPDATE SET v=CAST(v AS INTEGER)+1")


def _log(c, by, txn_id, what, detail="", field="", old="", new=""):
    if not _OPINFO.get("what") and not what.startswith("Undone"):
        _OPINFO.update(by=by or "", what=what, detail=detail or "", txn=txn_id)
    c.execute("INSERT INTO log(ts,by,txn_id,what,detail,field,oldv,newv) VALUES(?,?,?,?,?,?,?,?)",
              (now(), by or "", txn_id, what, detail[:600], field, str(old)[:4000], str(new)[:4000]))


# ----------------------------------------------------------------------------- undo / redo: every change is one "operation"; SQLite triggers copy the old rows into the journal
JTABLES = {"txn": ["id"], "party": ["id"], "link": ["txn_id", "party_id"], "need": ["txn_id", "type"], "chk": ["txn_id", "item"],
           "comment": ["id"], "action": ["id"], "meeting": ["id"], "geo": ["country"], "access": ["id"]}
_OPINFO: dict = {}


def _ensure_journal(c):
    c.executescript("""CREATE TABLE IF NOT EXISTS op (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, by TEXT DEFAULT '', what TEXT DEFAULT '', detail TEXT DEFAULT '', txn_id INTEGER,
                       kind TEXT DEFAULT 'do', ref INTEGER DEFAULT 0, undone INTEGER DEFAULT 0, n INTEGER DEFAULT 0);
                       CREATE TABLE IF NOT EXISTS jr (id INTEGER PRIMARY KEY AUTOINCREMENT, op INTEGER, tbl TEXT, kind TEXT, pk TEXT, old TEXT);
                       CREATE INDEX IF NOT EXISTS jr_op ON jr(op);""")
    cols = {t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")] for t in JTABLES}
    sig = json.dumps(cols, sort_keys=True)
    r = c.execute("SELECT v FROM meta WHERE k='jsig'").fetchone()
    if r and r[0] == sig:
        return
    for t in JTABLES:
        for k in "iud":
            c.execute(f"DROP TRIGGER IF EXISTS j_{t}_{k}")
    on = "WHEN COALESCE((SELECT v FROM meta WHERE k='op'),'')<>''"
    opid = "(SELECT CAST(v AS INTEGER) FROM meta WHERE k='op')"
    for t, pk in JTABLES.items():
        pn = lambda src: "json_object(" + ",".join(f"'{k}',{src}.{k}" for k in pk) + ")"
        allc = "json_object(" + ",".join(f"'{k}',OLD.{k}" for k in cols[t]) + ")"
        c.execute(f"CREATE TRIGGER j_{t}_i AFTER INSERT ON {t} {on} BEGIN INSERT INTO jr(op,tbl,kind,pk,old) VALUES({opid},'{t}','I',{pn('NEW')},NULL); END")
        c.execute(f"CREATE TRIGGER j_{t}_u AFTER UPDATE ON {t} {on} BEGIN INSERT INTO jr(op,tbl,kind,pk,old) VALUES({opid},'{t}','U',{pn('OLD')},{allc}); END")
        c.execute(f"CREATE TRIGGER j_{t}_d AFTER DELETE ON {t} {on} BEGIN INSERT INTO jr(op,tbl,kind,pk,old) VALUES({opid},'{t}','D',{pn('OLD')},{allc}); END")
    c.execute("INSERT INTO meta(k,v) VALUES('jsig',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (sig,))
    c.commit()


def _revert(c, opid: int):
    """Put every row an operation touched back to what it was (newest change first)."""
    for r in c.execute("SELECT * FROM jr WHERE op=? ORDER BY id DESC", (opid,)).fetchall():
        t, pk = r["tbl"], json.loads(r["pk"])
        where = " AND ".join(f"{k}=?" for k in pk)
        if r["kind"] == "I":
            c.execute(f"DELETE FROM {t} WHERE {where}", list(pk.values()))
        elif r["kind"] == "U":
            old = json.loads(r["old"])
            c.execute(f"UPDATE {t} SET " + ",".join(f"{k}=?" for k in old) + f" WHERE {where}", list(old.values()) + list(pk.values()))
        else:
            old = json.loads(r["old"])
            c.execute(f"INSERT OR REPLACE INTO {t}({','.join(old)}) VALUES({','.join('?' * len(old))})", list(old.values()))


def _tx(fn, kind: str = "do", journal: bool = True):
    """Run fn(c) under the write mutex in one SQLite transaction (= one undoable operation), bump the revision, commit."""
    with _mutex:
        c = connect()
        try:
            opid = 0
            _OPINFO.clear()
            if journal:
                opid = c.execute("INSERT INTO op(ts,kind) VALUES(?,?)", (now(), kind)).lastrowid
                c.execute("INSERT INTO meta(k,v) VALUES('op',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(opid),))
            r = fn(c)
            if journal:
                c.execute("UPDATE meta SET v='' WHERE k='op'")
                n = c.execute("SELECT COUNT(*) FROM jr WHERE op=?", (opid,)).fetchone()[0]
                if not n:
                    c.execute("DELETE FROM op WHERE id=?", (opid,))
                else:
                    i = _OPINFO
                    c.execute("UPDATE op SET by=?, what=?, detail=?, txn_id=?, ref=?, n=? WHERE id=?", (i.get("by", ""), i.get("what", "Change"), str(i.get("detail", ""))[:300], i.get("txn"), i.get("ref", 0), n, opid))
                    if kind == "do":
                        c.execute("UPDATE op SET undone=1 WHERE kind='undo' AND undone=0")  # a new change ends the redo chain
                    c.execute("DELETE FROM jr WHERE op<=?", (opid - 600,))
                    c.execute("DELETE FROM op WHERE id<=?", (opid - 600,))
            _bump(c)
            c.commit()
            return r
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


TXN_FIELDS = ["name", "country", "sector", "structure", "value", "client_type", "status", "ext_category", "procurement", "lead", "introduced",
              "sub_lead", "counterparty", "summary", "next_steps", "deck_key", "reason", "active", "priority", "next_review",
              "meeting_status", "meeting_with", "meeting_date", "meeting_notes", "loi_sent", "loi_date", "loi_response", "loi_notes", "info_status", "info_notes",
              "fm_status", "fm_notes", "ofin_status", "ofin_notes", "received_date", "data_date", "review_date", "review_outcome", "review_notes"]
_ENUM = {"status": STATUSES, "client_type": CLIENT_TYPES, "procurement": PROCUREMENT, "ext_category": EXT_CATEGORIES, "priority": PRIORITIES,
         "meeting_status": MEETING, "loi_sent": YESNO, "loi_response": LOI_RESPONSE, "info_status": INFO_STATE, "fm_status": MODEL_STATE,
         "ofin_status": INFO_STATE, "review_outcome": REVIEW_OUTCOME}


def _clean_fields(fields: dict) -> dict:
    clean = {k: fields[k] for k in TXN_FIELDS if k in fields}
    for k, allowed in _ENUM.items():
        if k in clean and clean[k] not in allowed:
            raise HubError(f"{k.replace('_', ' ').title()} must be one of: {', '.join(allowed)}.")
    if "lead" in clean and clean["lead"] not in [""] + LEADS:
        raise HubError("Owner must be RB, JT or SS.")
    if "active" in clean:
        clean["active"] = 1 if clean["active"] in (1, True, "1", "true") else 0
    if "introduced" in clean:
        clean["introduced"] = fix_sources(clean["introduced"])
    if "value" in clean:
        v = str(clean["value"] if clean["value"] is not None else "").strip().replace(",", "")
        if not v:
            clean["value"] = ""
        else:
            try:
                n = float(v)
            except ValueError:
                raise HubError("Indicative value must be a number in EUR million (e.g. 250) - no text.")
            if n < 0:
                raise HubError("Indicative value cannot be negative.")
            clean["value"] = _num(n)
    return clean


def _couple(clean: dict, old_status=None) -> dict:
    """'On hold' and 'parked' are one thing: the status drives the pipeline flag, so a transaction never stays greyed out by itself."""
    if "status" in clean and "active" not in clean:
        clean["active"] = 0 if clean["status"] == "On hold" else 1
    elif "active" in clean and "status" not in clean and old_status is not None:
        if clean["active"] == 0 and old_status != "On hold":
            clean["status"] = "On hold"
        elif clean["active"] == 1 and old_status == "On hold":
            clean["status"] = "Preliminary"
    return clean


def fix_sources(text) -> str:
    """'MP / J' -> 'Mohsin Patel / Japhet': one spelling per source, no duplicates."""
    import re
    out, seen = [], set()
    for p in re.split(r"\s*[/;\n]\s*", str(text or "")):
        p = " ".join(p.split())
        p = NO_NAMES.get(p.lower(), p)
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return " / ".join(out)


# ----------------------------------------------------------------------------- transactions
def _sub_follow(clean: dict, old=None):
    """A sub-owner is filled in from the owner (JT - Sunil, RB - Karan, SS - Heena) when it is empty or was just that owner's default."""
    if "sub_lead" in clean or "lead" not in clean:
        return clean
    cur_sub = (old["sub_lead"] or "") if old is not None else ""
    if cur_sub == "" or (old is not None and cur_sub == SUB_DEFAULT.get(old["lead"] or "")):
        clean["sub_lead"] = SUB_DEFAULT.get(clean["lead"], "")
    return clean


def txn_save(by: str, fields: dict, txn_id: Optional[int] = None) -> int:
    def run(c):
        clean = _couple(_clean_fields(fields))
        tid = txn_id
        if tid is None:
            if not str(clean.get("name", "")).strip():
                raise HubError("A transaction needs a name.")
            clean.setdefault("received_date", today())
            _sub_follow(clean)
            cols = ["key", "created", "updated", "origin"] + list(clean)
            vals = [f"manual-{int(time.time() * 1000)}", now(), now(), "Added in Hub"] + list(clean.values())
            tid = c.execute(f"INSERT INTO txn({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals).lastrowid
            _log(c, by, tid, "Transaction added", clean.get("name", ""))
            return tid
        old = c.execute("SELECT * FROM txn WHERE id=?", (tid,)).fetchone()
        if not old:
            raise HubError("Transaction not found.")
        clean = _sub_follow(_couple(clean, old["status"]), old)
        changed = {k: v for k, v in clean.items() if str(old[k] if old[k] is not None else "") != str(v)}
        if changed:
            c.execute("UPDATE txn SET " + ", ".join(f"{k}=?" for k in changed) + ", updated=? WHERE id=?", list(changed.values()) + [now(), tid])
            if "status" in changed or "active" in changed:
                _auto(c, tid)
            if "loi_sent" in changed:
                if changed["loi_sent"] == "Yes":
                    c.execute("INSERT INTO chk(txn_id,item,state,remark,updated) VALUES(?,?,?,?,?) ON CONFLICT(txn_id,item) DO UPDATE SET state='Yes', updated=excluded.updated", (tid, "LoI / EoI submitted", "Yes", "", now()))
                else:
                    c.execute("UPDATE chk SET state='No', updated=? WHERE txn_id=? AND item='LoI / EoI submitted' AND state='Yes'", (now(), tid))
            for k, v in changed.items():
                _log(c, by, tid, f"Changed {k.replace('_', ' ')}", f"{(str(old[k] or '-'))[:80]} -> {(str(v) or '-')[:80]}", k, old[k] if old[k] is not None else "", v)
        return tid
    return _tx(run)


VOCAB = {"sector": False, "country": False, "structure": True, "counterparty": False, "introduced": True}  # field -> holds several values joined by " / "


def _vocab_merge_c(c, by, field, froms, to) -> int:
    to = " ".join(str(to or "").split())
    fl = {" ".join(str(x).split()).lower() for x in froms if str(x).strip()}
    n = 0
    for r in c.execute(f"SELECT id, {field} AS v FROM txn WHERE deleted=0").fetchall():
        cur = r["v"] or ""
        if VOCAB[field]:
            parts = [p.strip() for p in re.split(r"(?<!\bN)\s*/\s*", cur) if p.strip()]
            if not any(p.lower() in fl for p in parts):
                continue
            new = []
            for p in parts:
                q = to if p.lower() in fl else p
                if q and q.lower() not in [x.lower() for x in new]:
                    new.append(q)
            nv = " / ".join(new)
            if field == "introduced":
                nv = fix_sources(nv)
        else:
            if cur.strip().lower() not in fl:
                continue
            nv = to
        if nv != cur:
            c.execute(f"UPDATE txn SET {field}=?, updated=? WHERE id=?", (nv, now(), r["id"]))
            _log(c, by, r["id"], f"Changed {field}", f"{cur[:80] or '-'} -> {nv[:80] or '-'} (merged)", field, cur, nv)
            n += 1
    return n


def vocab_merge(by: str, field: str, froms: List[str], to: str) -> int:
    """Fold several spellings of one value (sector, country, model, client, source) into one - in every transaction. Empty 'to' clears them."""
    if field not in VOCAB:
        raise HubError("This list cannot be merged.")
    if not [x for x in froms if str(x).strip()]:
        raise HubError("Tick the values to merge first.")
    return _tx(lambda c: _vocab_merge_c(c, by, field, froms, to))


def txn_bulk(by: str, ids: List[int], fields: dict) -> int:
    def run(c):
        clean = _clean_fields(fields)
        if not clean:
            return 0
        n = 0
        for tid in ids:
            old = c.execute("SELECT * FROM txn WHERE id=?", (tid,)).fetchone()
            if not old:
                continue
            ch = {k: v for k, v in _sub_follow(_couple(dict(clean), old["status"]), old).items() if str(old[k] if old[k] is not None else "") != str(v)}
            if ch:
                c.execute("UPDATE txn SET " + ", ".join(f"{k}=?" for k in ch) + ", updated=? WHERE id=?", list(ch.values()) + [now(), tid])
                for k, v in ch.items():
                    _log(c, by, tid, f"Changed {k.replace('_', ' ')}", f"{str(old[k] or '-')[:80]} -> {str(v)[:80]} (bulk)", k, old[k] if old[k] is not None else "", v)
                n += 1
        return n
    return _tx(run)


def txn_trash(by: str, ids: List[int], deleted: bool = True):
    def run(c):
        for tid in ids:
            c.execute("UPDATE txn SET deleted=?, updated=? WHERE id=?", (1 if deleted else 0, now(), tid))
            _log(c, by, tid, "Moved to trash" if deleted else "Restored from trash")
    _tx(run)


def txn_duplicate(by: str, tid: int) -> int:
    def run(c):
        o = c.execute("SELECT * FROM txn WHERE id=?", (tid,)).fetchone()
        if not o:
            raise HubError("Transaction not found.")
        cols = [k for k in TXN_FIELDS if k not in ("next_review",)]
        vals = [(o[k] + " (copy)") if k == "name" else o[k] for k in cols]
        new = c.execute(f"INSERT INTO txn(key,created,updated,origin,{','.join(cols)}) VALUES(?,?,?,?,{','.join('?' * len(cols))})",
                        [f"manual-{int(time.time() * 1000)}", now(), now(), "Duplicated in Hub"] + vals).lastrowid
        for r in c.execute("SELECT * FROM link WHERE txn_id=?", (tid,)).fetchall():
            c.execute("INSERT INTO link(txn_id,party_id,status,remark,updated,by) VALUES(?,?,?,?,?,?)", (new, r["party_id"], r["status"], r["remark"], now(), by))
        _log(c, by, new, "Transaction duplicated", f"from #{tid}")
        return new
    return _tx(run)


def undo_log(by: str, log_id: int):
    """Put one changed field back to what it was before."""
    def run(c):
        r = c.execute("SELECT * FROM log WHERE id=?", (log_id,)).fetchone()
        if not r or not r["field"] or r["field"] not in TXN_FIELDS:
            raise HubError("This entry cannot be undone.")
        cur = c.execute(f"SELECT {r['field']} FROM txn WHERE id=?", (r["txn_id"],)).fetchone()
        c.execute(f"UPDATE txn SET {r['field']}=?, updated=? WHERE id=?", (r["oldv"], now(), r["txn_id"]))
        _log(c, by, r["txn_id"], f"Undone: {r['field'].replace('_', ' ')}", f"{str(cur[0] or '-')[:80]} -> {r['oldv'][:80] or '-'}", r["field"], cur[0] or "", r["oldv"])
    _tx(run)


def _op_info(c, r):
    if not r:
        return None
    t = c.execute("SELECT name FROM txn WHERE id=?", (r["txn_id"],)).fetchone() if r["txn_id"] else None
    d = r["detail"] or ""
    return {"id": r["id"], "what": r["what"], "detail": (f"{r['n']} changes" if r["n"] > 1 else "") + (" · " if r["n"] > 1 and d else "") + d, "by": r["by"], "ts": r["ts"], "txn": t["name"] if t else ""}


def _undo_candidate(c):
    """The newest operation that has not been undone yet."""
    return _op_info(c, c.execute("SELECT * FROM op WHERE kind IN ('do','redo') AND undone=0 ORDER BY id DESC LIMIT 1").fetchone())


def _redo_candidate(c):
    r = c.execute("SELECT * FROM op WHERE kind='undo' AND undone=0 ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return None
    return _op_info(c, c.execute("SELECT * FROM op WHERE id=?", (r["ref"],)).fetchone())


def undo_last(by: str) -> dict:
    """Reverse the whole last change (every row it touched - a bulk edit, a mapping, an action, a comment ... not just one field)."""
    def run(c):
        t = c.execute("SELECT * FROM op WHERE kind IN ('do','redo') AND undone=0 ORDER BY id DESC LIMIT 1").fetchone()
        if not t:
            raise HubError("Nothing to undo.")
        info = _op_info(c, t)
        _revert(c, t["id"])
        c.execute("UPDATE op SET undone=1 WHERE id=?", (t["id"],))
        _OPINFO.update(by=by or "", what="Undo: " + t["what"], detail=t["detail"] or "", txn=t["txn_id"], ref=t["id"])
        c.execute("INSERT INTO log(ts,by,txn_id,what,detail) VALUES(?,?,?,?,?)", (now(), by or "", t["txn_id"], "Undone: " + t["what"], f"{t['n']} change(s) reversed"))
        return info
    return _tx(run, kind="undo")


def redo_last(by: str) -> dict:
    """Put back what the last Undo took away."""
    def run(c):
        u = c.execute("SELECT * FROM op WHERE kind='undo' AND undone=0 ORDER BY id DESC LIMIT 1").fetchone()
        if not u:
            raise HubError("Nothing to redo.")
        o = c.execute("SELECT * FROM op WHERE id=?", (u["ref"],)).fetchone()
        info = _op_info(c, o)
        _revert(c, u["id"])
        c.execute("UPDATE op SET undone=1 WHERE id=?", (u["id"],))
        _OPINFO.update(by=by or "", what=(o["what"] if o else "Change"), detail=(o["detail"] if o else ""), txn=(o["txn_id"] if o else None))
        c.execute("INSERT INTO log(ts,by,txn_id,what,detail) VALUES(?,?,?,?,?)", (now(), by or "", o["txn_id"] if o else None, "Redone: " + (o["what"] if o else ""), ""))
        return info
    return _tx(run, kind="redo")


# ----------------------------------------------------------------------------- counterparties
def party_get_or_create(c, name: str, ptype: str) -> int:
    name = " ".join(str(name).split())
    if ptype not in PARTY_TYPES:
        raise HubError("Counterparty type must be one of " + ", ".join(PARTY_TYPES))
    if not name:
        raise HubError("Counterparty needs a name.")
    r = c.execute("SELECT id FROM party WHERE name=? COLLATE NOCASE AND type=?", (name, ptype)).fetchone()
    if r:
        c.execute("UPDATE party SET active=1 WHERE id=?", (r[0],))
        return r[0]
    return c.execute("INSERT INTO party(name,type) VALUES(?,?)", (name, ptype)).lastrowid


def party_new(by: str, name: str, ptype: str, country: str = "") -> int:
    def run(c):
        pid = party_get_or_create(c, name, ptype)
        if country:
            c.execute("UPDATE party SET country=? WHERE id=? AND country=''", (country, pid))
        return pid
    return _tx(run)


def link_set(by: str, txn_id: int, party_id: Optional[int] = None, name: str = "", ptype: str = "", status: str = "Identified",
             remark: Optional[str] = None) -> int:
    if status not in LINK_STATUS:
        raise HubError("Unknown status " + status)

    def run(c):
        pid = party_id if party_id is not None else party_get_or_create(c, name, ptype)
        return _link(c, by, txn_id, pid, status, remark)
    return _tx(run)


def _link(c, by, txn_id, pid, status, remark=None):
    if True:
        p = c.execute("SELECT name, type FROM party WHERE id=?", (pid,)).fetchone()
        old = c.execute("SELECT status, remark FROM link WHERE txn_id=? AND party_id=?", (txn_id, pid)).fetchone()
        rem = remark if remark is not None else (old["remark"] if old else "")
        c.execute("INSERT INTO link(txn_id,party_id,status,remark,updated,by) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(txn_id,party_id) DO UPDATE SET status=excluded.status, remark=excluded.remark, updated=excluded.updated, by=excluded.by",
                  (txn_id, pid, status, rem, now(), by or ""))
        if not old:
            _log(c, by, txn_id, f"{p['type']} mapped", f"{p['name']} -> {status}")
        elif old["status"] != status:
            _log(c, by, txn_id, f"{p['type']} status", f"{p['name']}: {old['status']} -> {status}")
        elif (old["remark"] or "") != rem:
            _log(c, by, txn_id, f"{p['type']} remark", f"{p['name']}: {rem}")
        c.execute("UPDATE txn SET updated=? WHERE id=?", (now(), txn_id))
        _auto(c, txn_id)
        return pid


def link_bulk(by: str, party_ids: List[int], txn_ids: List[int], action: str, status: str = "Shortlisted") -> int:
    """Many counterparties x many transactions at once: map them, change their mapping status, or take them off."""
    if action in ("add", "status") and status not in LINK_STATUS:
        raise HubError("Unknown status " + status)
    if action not in ("add", "status", "remove"):
        raise HubError("Unknown bulk action.")

    def run(c):
        n = 0
        for tid in txn_ids:
            for pid in party_ids:
                have = c.execute("SELECT 1 FROM link WHERE txn_id=? AND party_id=?", (tid, pid)).fetchone()
                if action == "remove":
                    if have:
                        p = c.execute("SELECT name, type FROM party WHERE id=?", (pid,)).fetchone()
                        c.execute("DELETE FROM link WHERE txn_id=? AND party_id=?", (tid, pid))
                        _log(c, by, tid, f"{p['type']} removed", f"{p['name']} (bulk)")
                        n += 1
                elif action == "add" or have:
                    _link(c, by, tid, pid, status)
                    n += 1
        return n
    return _tx(run)


def link_del(by: str, txn_id: int, party_id: int):
    def run(c):
        p = c.execute("SELECT name, type FROM party WHERE id=?", (party_id,)).fetchone()
        c.execute("DELETE FROM link WHERE txn_id=? AND party_id=?", (txn_id, party_id))
        _log(c, by, txn_id, f"{p['type'] if p else 'Counterparty'} removed", p["name"] if p else "")
        _auto(c, txn_id)
    _tx(run)


def need_set(by: str, txn_id: int, ptype: str, state: str):
    if state not in ("Needed", "Not needed"):
        raise HubError("State must be Needed or Not needed.")

    def run(c):
        c.execute("INSERT INTO need(txn_id,type,state) VALUES(?,?,?) ON CONFLICT(txn_id,type) DO UPDATE SET state=excluded.state", (txn_id, ptype, state))
        _log(c, by, txn_id, f"{ptype}: {state.lower()}")
        _auto(c, txn_id)
    _tx(run)


def _auto(c, tid):
    """Things that are 'in progress' always have a task: open one automatically, close it when the thing is done."""
    t = c.execute("SELECT * FROM txn WHERE id=? AND deleted=0", (tid,)).fetchone()
    want = {}
    if t and t["active"]:
        for r in c.execute("SELECT item FROM chk WHERE txn_id=? AND state='In progress'", (tid,)):
            want["chk:" + r["item"]] = f"{r['item']} - in progress: follow up and close it"
        ls = c.execute("SELECT l.status FROM link l JOIN party p ON p.id=l.party_id WHERE l.txn_id=? AND p.type='EPC'", (tid,)).fetchall()
        sts = {x["status"] for x in ls}
        nn = c.execute("SELECT 1 FROM need WHERE txn_id=? AND type='EPC' AND state='Not needed'", (tid,)).fetchone()
        if not nn and not (sts & {"Appointed", "Shortlisted", "Term sheet received"}):
            if sts & {"To be approached", "Approached", "In discussion"}:
                want["epc"] = "EPC - discussions in progress: close the shortlist"
            elif t["status"] in ("Tie-up done", "P1", "P2"):
                want["epc"] = "EPC - find and shortlist an EPC"
        for r in c.execute("SELECT l.party_id, l.updated, p.name, p.type FROM link l JOIN party p ON p.id=l.party_id WHERE l.txn_id=? AND l.status='To be approached'", (tid,)):
            want[f"appr:{r['party_id']}:{r['updated']}"] = f"Approach {r['name']} ({r['type']}) - marked 'to be approached'"
        for r in c.execute("SELECT id, who FROM meeting WHERE txn_id=? AND deleted=0 AND status='To be scheduled'", (tid,)):
            want[f"msched:{r['id']}"] = f"Schedule a meeting with {r['who'] or 'the ministry / owner'}"
        m = c.execute("SELECT status FROM meeting WHERE txn_id=? AND deleted=0 AND status NOT IN ('Cancelled','To be scheduled') ORDER BY day='' , day DESC, id DESC", (tid,)).fetchall()
        if m and not any(x["status"] == "Held" for x in m) and m[0]["status"] in ("Requested", "Scheduled"):
            want["meeting"] = "Meeting with ministry / owner - requested / scheduled: hold it and record the outcome"
    rows = c.execute("SELECT id, auto, done FROM action WHERE txn_id=? AND auto!='' AND deleted=0", (tid,)).fetchall()
    seen = {r["auto"] for r in rows}
    due = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    for k, text in want.items():
        if k not in seen:
            c.execute("INSERT INTO action(txn_id,text,owner,due,created,by,auto) VALUES(?,?,?,?,?,?,?)", (tid, text, (t["sub_lead"] or t["lead"] or "") if t else "", due, now(), "Auto", k))
            _log(c, "Auto", tid, "Action added (automatic)", text)
    for r in rows:
        if not r["done"] and r["auto"] not in want:
            c.execute("UPDATE action SET done=1, done_ts=? WHERE id=?", (now(), r["id"]))
            _log(c, "Auto", tid, "Action done (automatic)", r["auto"])


def auto_all():
    def run(c):
        for r in c.execute("SELECT id FROM txn WHERE deleted=0").fetchall():
            _auto(c, r["id"])
    _tx(run)


# ----------------------------------------------------------------------------- meetings (many per transaction; the overview shows the latest)
def _sync_meeting(c, tid):
    ms = c.execute("SELECT * FROM meeting WHERE txn_id=? AND deleted=0 AND status!='Cancelled' ORDER BY day='' , day DESC, id DESC", (tid,)).fetchall()
    held = [m for m in ms if m["status"] == "Held"]
    pick = held[0] if held else (ms[0] if ms else None)
    if pick:
        c.execute("UPDATE txn SET meeting_status=?, meeting_with=?, meeting_date=?, meeting_notes=? WHERE id=?", (pick["status"], pick["who"], pick["day"], pick["notes"], tid))
    else:
        c.execute("UPDATE txn SET meeting_status='Not held', meeting_with='', meeting_date='', meeting_notes='' WHERE id=?", (tid,))
    _auto(c, tid)


def _meeting_add(c, by, txn_id, day, who, status, notes):
    if status not in MEETING_KINDS:
        raise HubError("Meeting status must be one of: " + ", ".join(MEETING_KINDS))
    mid = c.execute("INSERT INTO meeting(txn_id,day,who,status,notes,by,created) VALUES(?,?,?,?,?,?,?)", (txn_id, day or "", " ".join(str(who or "").split()), status, notes or "", by or "", now())).lastrowid
    _log(c, by, txn_id, f"Meeting {status.lower()}", f"{day or 'no date'} · {who or '-'}" + (f" · {str(notes)[:120]}" if notes else ""))
    _sync_meeting(c, txn_id)
    return mid


def meeting_add(by: str, txn_id: int, day: str = "", who: str = "", status: str = "Held", notes: str = "") -> int:
    return _tx(lambda c: _meeting_add(c, by, txn_id, day, who, status, notes))


def meeting_update(by: str, mid: int, fields: dict):
    def run(c):
        r = c.execute("SELECT * FROM meeting WHERE id=?", (mid,)).fetchone()
        if not r:
            raise HubError("Meeting not found.")
        sets = {k: fields[k] for k in ("day", "who", "status", "notes") if k in fields}
        if sets.get("status") and sets["status"] not in MEETING_KINDS:
            raise HubError("Meeting status must be one of: " + ", ".join(MEETING_KINDS))
        if "deleted" in fields:
            sets["deleted"] = 1 if fields["deleted"] else 0
        if sets:
            c.execute("UPDATE meeting SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [mid])
            _log(c, by, r["txn_id"], "Meeting removed" if sets.get("deleted") else "Meeting updated", ", ".join(f"{k}: {v}" for k, v in sets.items() if k != "deleted")[:200])
            _sync_meeting(c, r["txn_id"])
    _tx(run)


def meeting_latest_set(by: str, txn_id: int, fields: dict):
    """Edit the meeting the overview shows (the latest held one); the first edit on a transaction without meetings creates it."""
    def run(c):
        ms = c.execute("SELECT * FROM meeting WHERE txn_id=? AND deleted=0 AND status!='Cancelled' ORDER BY day='' , day DESC, id DESC", (txn_id,)).fetchall()
        held = [m for m in ms if m["status"] == "Held"]
        pick = held[0] if held else (ms[0] if ms else None)
        f = {k: fields[k] for k in ("day", "who", "status", "notes") if k in fields}
        if f.get("status") == "Not held":
            f.pop("status")
        if not pick:
            st = f.get("status") or "Held"
            day = f.get("day") or (today() if st == "Held" else "")
            _meeting_add(c, by, txn_id, day, f.get("who", ""), st, f.get("notes", ""))
            return
        if f.get("status") == "Held" and not (f.get("day") or pick["day"]):
            f["day"] = today()
        if f:
            c.execute("UPDATE meeting SET " + ", ".join(f"{k}=?" for k in f) + " WHERE id=?", list(f.values()) + [pick["id"]])
            _log(c, by, txn_id, "Meeting updated", ", ".join(f"{k}: {v}" for k, v in f.items())[:200])
            _sync_meeting(c, txn_id)
    _tx(run)


# ----------------------------------------------------------------------------- look-alike names (capital letters, spaces, punctuation)
def _ckey(x) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(x or "").lower())


def _best_spelling(counts: dict) -> str:
    def score(v):
        return (counts[v], 1 if (v != v.lower() and v != v.upper()) else 0, -len(v))
    return max(counts, key=score)


def _vocab_values(c, field):
    cnt = {}
    for r in c.execute(f"SELECT {field} AS v FROM txn WHERE deleted=0").fetchall():
        vals = [p.strip() for p in re.split(r"(?<!\bN)\s*/\s*", r["v"] or "") if p.strip()] if VOCAB[field] else ([" ".join((r["v"] or "").split())] if (r["v"] or "").strip() else [])
        for v in vals:
            cnt[v] = cnt.get(v, 0) + 1
    return cnt


def vocab_suggest(field: str) -> List[dict]:
    """Groups of values that only differ by capitals / spaces / punctuation: [{keep, others:[...]}]."""
    if field not in VOCAB:
        raise HubError("This list cannot be checked.")
    c = connect()
    try:
        cnt = _vocab_values(c, field)
    finally:
        c.close()
    groups = {}
    for v in cnt:
        groups.setdefault(_ckey(v), {})[v] = cnt[v]
    return [{"keep": _best_spelling(g), "others": [v for v in g if v != _best_spelling(g)]} for g in groups.values() if len(g) > 1]


def vocab_dedupe(by: str, field: str) -> int:
    def run(c):
        cnt = _vocab_values(c, field)
        groups = {}
        for v in cnt:
            groups.setdefault(_ckey(v), {})[v] = cnt[v]
        n = 0
        for g in groups.values():
            if len(g) > 1:
                keep = _best_spelling(g)
                n += _vocab_merge_c(c, by, field, [v for v in g if v != keep], keep)
        return n
    return _tx(run)


def party_dedupe(by: str, ptype: str = "") -> int:
    """Same company typed with different capitals ('Tanescoo' / 'TANESCOO'): keep the one with most mappings, fold the others in."""
    def run(c):
        n = 0
        groups = {}
        for p in c.execute("SELECT id, name, type FROM party WHERE active=1" + (" AND type=?" if ptype else ""), (ptype,) if ptype else ()).fetchall():
            groups.setdefault((p["type"], _ckey(p["name"])), []).append(p)
        for g in groups.values():
            if len(g) < 2:
                continue
            nl = {p["id"]: c.execute("SELECT COUNT(*) FROM link WHERE party_id=?", (p["id"],)).fetchone()[0] for p in g}
            names = {p["name"]: nl[p["id"]] for p in g}
            keep_name = _best_spelling({k: max(v, 1) for k, v in names.items()})
            keep = next(p for p in g if p["name"] == keep_name)
            for p in g:
                if p["id"] != keep["id"]:
                    _merge(c, keep["id"], p["id"])
                    n += 1
        if n:
            _log(c, by, None, f"{n} look-alike counterparties merged", ptype or "all types")
        return n
    return _tx(run)


def chk_set(by: str, txn_id: int, item: str, state: str, remark: Optional[str] = None):
    if state not in CHECK_STATES + [""]:
        raise HubError("Unknown checklist state.")

    def run(c):
        old = c.execute("SELECT state, remark FROM chk WHERE txn_id=? AND item=?", (txn_id, item)).fetchone()
        rem = remark if remark is not None else (old["remark"] if old else "")
        c.execute("INSERT INTO chk(txn_id,item,state,remark,updated) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(txn_id,item) DO UPDATE SET state=excluded.state, remark=excluded.remark, updated=excluded.updated",
                  (txn_id, item, state, rem, now()))
        if item == "LoI / EoI submitted":
            c.execute("UPDATE txn SET loi_sent=? WHERE id=?", ("Yes" if state == "Yes" else "No", txn_id))
            if state == "Yes":
                c.execute("UPDATE txn SET loi_response=CASE WHEN loi_response='' THEN ? ELSE loi_response END WHERE id=?", ("Accepted" if "accept" in rem.lower() else "Awaiting", txn_id))
        if not old or old["state"] != state:
            _log(c, by, txn_id, f"Checklist: {item}", f"{(old['state'] if old else '') or '-'} -> {state or '-'}")
        elif (old["remark"] or "") != rem:
            _log(c, by, txn_id, f"Checklist note: {item}", rem)
        _auto(c, txn_id)
    _tx(run)


def chk_del(by: str, txn_id: int, item: str):
    """Remove a project-specific readiness item (the standard items stay - mark those N.A. instead)."""
    if item in CHECK_ITEMS:
        raise HubError("This is a standard readiness item - mark it N.A. if it does not apply to this project.")

    def run(c):
        c.execute("DELETE FROM chk WHERE txn_id=? AND item=?", (txn_id, item))
        _log(c, by, txn_id, "Readiness item removed", item)
        _auto(c, txn_id)
    _tx(run)


def chk_bulk(by: str, txn_ids: List[int], item: str, state: str) -> int:
    """One readiness item set to one state on many transactions."""
    if item not in CHECK_ITEMS:
        raise HubError("Unknown readiness item.")
    for tid in txn_ids:
        chk_set(by, tid, item, state)
    return len(txn_ids)


def party_save(by: str, party_id: int, fields: dict):
    def run(c):
        sets = {k: fields[k] for k in ("name", "country", "notes", "active") if k in fields}
        if sets:
            c.execute("UPDATE party SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [party_id])
    _tx(run)


def _merge(c, keep_id, drop_id):
    for r in c.execute("SELECT * FROM link WHERE party_id=?", (drop_id,)).fetchall():
        if c.execute("SELECT 1 FROM link WHERE txn_id=? AND party_id=?", (r["txn_id"], keep_id)).fetchone():
            c.execute("DELETE FROM link WHERE txn_id=? AND party_id=?", (r["txn_id"], drop_id))
        else:
            c.execute("UPDATE link SET party_id=? WHERE txn_id=? AND party_id=?", (keep_id, r["txn_id"], drop_id))
    c.execute("DELETE FROM party WHERE id=?", (drop_id,))


def party_merge(by: str, keep_id: int, drop_id: int):
    """Two spellings of the same counterparty: move every mapping to 'keep' and remove 'drop'."""
    _tx(lambda c: _merge(c, keep_id, drop_id))


def party_bulk_add(by: str, ptype: str, rows: List[dict]) -> dict:
    """Paste a list: new names are added, names that already exist are skipped (and reported)."""
    if ptype not in PARTY_TYPES:
        raise HubError("Counterparty type must be one of " + ", ".join(PARTY_TYPES))

    def run(c):
        added, skipped = [], []
        seen = set()
        for r in rows:
            name = " ".join(str(r.get("name", "")).split())
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            country = " ".join(str(r.get("country", "")).split())
            ex = c.execute("SELECT id, active FROM party WHERE name=? COLLATE NOCASE AND type=?", (name, ptype)).fetchone()
            if ex and ex["active"]:
                skipped.append(name)
                continue
            if ex:
                c.execute("UPDATE party SET active=1 WHERE id=?", (ex["id"],))
                pid = ex["id"]
            else:
                pid = c.execute("INSERT INTO party(name,type) VALUES(?,?)", (name, ptype)).lastrowid
            if country:
                c.execute("UPDATE party SET country=? WHERE id=?", (country, pid))
            added.append(name)
        if added:
            _log(c, by, None, f"{ptype}: {len(added)} counterparties added (bulk)", ", ".join(added)[:500])
        return {"added": added, "skipped": skipped}
    return _tx(run)


def party_bulk(by: str, ids: List[int], action: str, value: str = "") -> dict:
    """delete | country | type | merge (into the party whose id is in value)."""
    def run(c):
        n = 0
        if action == "delete":
            for pid in ids:
                c.execute("DELETE FROM link WHERE party_id=?", (pid,))
                c.execute("UPDATE party SET active=0 WHERE id=?", (pid,))
                n += 1
            _log(c, by, None, f"{n} counterparties deleted (bulk)")
        elif action == "country":
            for pid in ids:
                c.execute("UPDATE party SET country=? WHERE id=?", (str(value).strip(), pid))
                n += 1
        elif action == "type":
            if value not in PARTY_TYPES:
                raise HubError("Unknown counterparty type.")
            for pid in ids:
                p = c.execute("SELECT name, type FROM party WHERE id=?", (pid,)).fetchone()
                if not p or p["type"] == value:
                    continue
                ex = c.execute("SELECT id FROM party WHERE name=? AND type=?", (p["name"], value)).fetchone()
                if ex:
                    _merge(c, ex["id"], pid)
                else:
                    c.execute("UPDATE party SET type=? WHERE id=?", (value, pid))
                n += 1
        elif action == "merge":
            keep = int(value)
            for pid in ids:
                if pid != keep:
                    _merge(c, keep, pid)
                    n += 1
            _log(c, by, None, f"{n} counterparties merged (bulk)")
        else:
            raise HubError("Unknown bulk action.")
        return {"n": n}
    return _tx(run)


def party_bulk_edit(by: str, edits: List[dict]) -> int:
    def run(c):
        n = 0
        for e in edits:
            sets = {k: " ".join(str(e[k]).split()) for k in ("name", "country") if k in e}
            if "name" in sets and not sets["name"]:
                raise HubError("A counterparty needs a name.")
            if sets:
                cur = c.execute("SELECT type FROM party WHERE id=?", (e["id"],)).fetchone()
                if "name" in sets and cur and c.execute("SELECT 1 FROM party WHERE name=? AND type=? AND id<>? AND active=1", (sets["name"], cur["type"], e["id"])).fetchone():
                    raise HubError(f"“{sets['name']}” already exists - use Merge to combine two counterparties.")
                c.execute("UPDATE party SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [e["id"]])
                n += 1
        if n:
            _log(c, by, None, f"{n} counterparties edited (bulk)")
        return n
    return _tx(run)


def party_delete(by: str, party_id: int):
    """Hide a counterparty (and its mappings) - e.g. junk picked up from the file."""
    def run(c):
        c.execute("DELETE FROM link WHERE party_id=?", (party_id,))
        c.execute("UPDATE party SET active=0 WHERE id=?", (party_id,))
    _tx(run)


# ----------------------------------------------------------------------------- discussion: comments, actions, reviews
def comment_add(by: str, txn_id: int, text: str, day: str = "", kind: str = "") -> int:
    if not text.strip():
        raise HubError("Write the comment first.")
    if kind not in COMMENT_KINDS:
        raise HubError("Unknown comment type.")

    def run(c):
        cid = c.execute("INSERT INTO comment(txn_id,ts,day,by,text,kind) VALUES(?,?,?,?,?,?)", (txn_id, now(), day or today(), by or "", text.strip(), kind)).lastrowid
        _log(c, by, txn_id, "Management comment" if kind else "Comment", text.strip()[:200])
        c.execute("UPDATE txn SET updated=? WHERE id=?", (now(), txn_id))
        return cid
    return _tx(run)


def comment_edit(by: str, cid: int, text: str = None, deleted: bool = False):
    def run(c):
        r = c.execute("SELECT txn_id, text FROM comment WHERE id=?", (cid,)).fetchone()
        if not r:
            raise HubError("Comment not found.")
        if deleted:
            c.execute("UPDATE comment SET deleted=1 WHERE id=?", (cid,))
            _log(c, by, r["txn_id"], "Comment deleted", r["text"][:200])
        elif text is not None and text.strip() != r["text"]:
            c.execute("UPDATE comment SET text=? WHERE id=?", (text.strip(), cid))
            _log(c, by, r["txn_id"], "Comment edited", f"{r['text'][:100]} -> {text.strip()[:100]}")
    _tx(run)


def action_add(by: str, txn_id: int, text: str, owner: str = "", due: str = "") -> int:
    if not text.strip():
        raise HubError("Write the action first.")

    def run(c):
        aid = c.execute("INSERT INTO action(txn_id,text,owner,due,created,by) VALUES(?,?,?,?,?,?)", (txn_id, text.strip(), owner, due, now(), by or "")).lastrowid
        _log(c, by, txn_id, "Action added", f"{text.strip()[:150]}" + (f" (owner {owner})" if owner else "") + (f" due {due}" if due else ""))
        return aid
    return _tx(run)


def action_bulk(by: str, txn_ids: List[int], text: str, owner: str = "", due: str = "") -> int:
    """The same task on many transactions at once. owner '__sub' = each transaction's own sub-owner (falls back to its owner)."""
    if not text.strip():
        raise HubError("Write the task first.")

    def run(c):
        n = 0
        for tid in txn_ids:
            t = c.execute("SELECT sub_lead, lead FROM txn WHERE id=? AND deleted=0", (tid,)).fetchone()
            if not t:
                continue
            ow = (t["sub_lead"] or t["lead"] or "") if owner == "__sub" else owner
            c.execute("INSERT INTO action(txn_id,text,owner,due,created,by) VALUES(?,?,?,?,?,?)", (tid, text.strip(), ow, due, now(), by or ""))
            _log(c, by, tid, "Action added", text.strip()[:150] + (f" (owner {ow})" if ow else "") + (f" due {due}" if due else "") + " (bulk)")
            n += 1
        return n
    return _tx(run)


def access_save(by: str, aid: Optional[int], fields: dict) -> int:
    """A source's connection: which country / ministry / department it can open a door to."""
    f = {k: " ".join(str(fields[k]).split()) if k != "notes" else str(fields[k]).strip() for k in ("source", "country", "ministry", "contact", "notes") if k in fields}

    def run(c):
        if aid is None:
            if not f.get("source"):
                raise HubError("Which source is this connection for?")
            if not (f.get("country") or f.get("ministry")):
                raise HubError("Write the country and / or the ministry or department.")
            cols = list(f) + ["created", "by"]
            i = c.execute(f"INSERT INTO access({','.join(cols)}) VALUES({','.join('?' * len(cols))})", list(f.values()) + [now(), by or ""]).lastrowid
            _log(c, by, None, "Source connection added", f"{f.get('source')}: {f.get('country', '')} {f.get('ministry', '')}".strip())
            return i
        if f:
            c.execute("UPDATE access SET " + ", ".join(f"{k}=?" for k in f) + " WHERE id=?", list(f.values()) + [aid])
            _log(c, by, None, "Source connection updated", ", ".join(f"{k}: {v}" for k, v in f.items())[:200])
        return aid
    return _tx(run)


def access_del(by: str, aid: int):
    def run(c):
        r = c.execute("SELECT source, country, ministry FROM access WHERE id=?", (aid,)).fetchone()
        c.execute("UPDATE access SET deleted=1 WHERE id=?", (aid,))
        if r:
            _log(c, by, None, "Source connection removed", f"{r['source']}: {r['country']} {r['ministry']}".strip())
    _tx(run)


def action_update(by: str, aid: int, fields: dict):
    def run(c):
        r = c.execute("SELECT * FROM action WHERE id=?", (aid,)).fetchone()
        if not r:
            raise HubError("Action not found.")
        sets = {k: fields[k] for k in ("text", "owner", "due", "done", "deleted") if k in fields}
        if "done" in sets:
            sets["done"] = 1 if sets["done"] in (1, True, "1") else 0
            sets["done_ts"] = now() if sets["done"] else ""
        if sets:
            c.execute("UPDATE action SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?", list(sets.values()) + [aid])
            what = "Action done" if sets.get("done") else "Action reopened" if "done" in sets else "Action deleted" if sets.get("deleted") else "Action updated"
            _log(c, by, r["txn_id"], what, r["text"][:150])
    _tx(run)


def review_mark(by: str, txn_id: int, next_days: int = 7):
    def run(c):
        nxt = (datetime.now() + timedelta(days=next_days)).strftime("%Y-%m-%d")
        c.execute("UPDATE txn SET last_reviewed=?, next_review=?, updated=? WHERE id=?", (today(), nxt, now(), txn_id))
        _log(c, by, txn_id, "Reviewed", f"next review {nxt}")
    _tx(run)


# ----------------------------------------------------------------------------- geography / bosses / sources
def geo_set(by: str, country: str, lead: str, apply_to_txns: bool = True) -> int:
    if lead not in [""] + LEADS:
        raise HubError("Owner must be RB, JT or SS.")

    def run(c):
        c.execute("INSERT INTO geo(country,lead) VALUES(?,?) ON CONFLICT(country) DO UPDATE SET lead=excluded.lead", (country, lead))
        n = 0
        if apply_to_txns:
            for r in c.execute("SELECT id, lead FROM txn WHERE lower(country)=lower(?) AND deleted=0", (country,)).fetchall():
                if r["lead"] != lead:
                    c.execute("UPDATE txn SET lead=? WHERE id=?", (lead, r["id"]))
                    _log(c, by, r["id"], "Changed lead", f"{r['lead'] or '-'} -> {lead or '-'} (country {country})", "lead", r["lead"], lead)
                    n += 1
        return n
    return _tx(run)


def source_rename(by: str, old: str, new: str) -> int:
    """Rename one source on every transaction (e.g. 'MP' -> 'Mohsin Patel'); merges if the new name already exists."""
    def run(c):
        n = 0
        for r in c.execute("SELECT id, introduced FROM txn WHERE introduced!='' AND deleted=0").fetchall():
            parts = [p.strip() for p in r["introduced"].replace(";", "/").split("/") if p.strip()]
            if any(p.lower() == old.lower() for p in parts):
                nv = fix_sources(" / ".join(new if p.lower() == old.lower() else p for p in parts))
                c.execute("UPDATE txn SET introduced=? WHERE id=?", (nv, r["id"]))
                _log(c, by, r["id"], "Source renamed", f"{old} -> {new}", "introduced", r["introduced"], nv)
                n += 1
        return n
    return _tx(run)
