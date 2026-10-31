#!/usr/bin/env python3
"""Blend Hub - accounts, passwords, sessions and roles (multi-user).

Kept deliberately apart from the business data:
  * users live in their own file  data/auth.db  (never touched by backups / Excel export / undo)
  * sessions are signed cookies   (secret in data/secret.key) - nothing to store server-side

Three roles, most powerful first:
  master  - everything, including managing who can log in and the destructive / deck actions
  editor  - add and change deals, comments, needs, actions; generate decks
  viewer  - read everything, print / export; no changes
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUTH_DB = DATA / "auth.db"
SECRET_PATH = DATA / "secret.key"

ROLES = ("master", "editor", "viewer")
ROLE_LABEL = {"master": "Master (full control)", "editor": "Editor (can change deals)", "viewer": "Viewer (read only)"}
SESSION_HOURS = 12
PBKDF2_ITERS = 240_000

_COOKIE = "hub_sess"


class AuthError(Exception):
    pass


# --------------------------------------------------------------------------- storage
def _connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    c = sqlite3.connect(AUTH_DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
             username TEXT PRIMARY KEY,
             name     TEXT DEFAULT '',
             role     TEXT DEFAULT 'viewer',
             pwhash   TEXT DEFAULT '',
             salt     TEXT DEFAULT '',
             iters    INTEGER DEFAULT 0,
             active   INTEGER DEFAULT 1,
             must_change INTEGER DEFAULT 0,
             created  TEXT DEFAULT '',
             created_by TEXT DEFAULT '',
             last_login TEXT DEFAULT '')"""
    )
    c.commit()
    return c


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def _norm(username: str) -> str:
    return (username or "").strip().lower()


# --------------------------------------------------------------------------- passwords
def hash_pw(password: str, salt: Optional[str] = None, iters: int = PBKDF2_ITERS) -> tuple[str, str, int]:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), bytes.fromhex(salt), iters)
    return dk.hex(), salt, iters


def _verify(password: str, row: sqlite3.Row) -> bool:
    if not row or not row["pwhash"]:
        return False
    calc, _, _ = hash_pw(password, row["salt"], int(row["iters"] or PBKDF2_ITERS))
    return hmac.compare_digest(calc, row["pwhash"])


# --------------------------------------------------------------------------- user management
def list_users() -> list[dict]:
    c = _connect()
    try:
        rows = c.execute(
            "SELECT username, name, role, active, must_change, created, created_by, last_login FROM users ORDER BY role, username"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def get_user(username: str) -> Optional[dict]:
    c = _connect()
    try:
        r = c.execute("SELECT * FROM users WHERE username=?", (_norm(username),)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def count_masters(active_only: bool = True) -> int:
    c = _connect()
    try:
        q = "SELECT COUNT(*) FROM users WHERE role='master'" + (" AND active=1" if active_only else "")
        return c.execute(q).fetchone()[0]
    finally:
        c.close()


def add_user(username: str, name: str, role: str, password: str, by: str = "", must_change: bool = True) -> None:
    u = _norm(username)
    if not u or not u.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise AuthError("Username must be letters/numbers (dots, dashes and underscores allowed).")
    if role not in ROLES:
        raise AuthError("Unknown role.")
    if not password or len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    c = _connect()
    try:
        if c.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
            raise AuthError(f"User '{u}' already exists.")
        h, salt, iters = hash_pw(password)
        c.execute(
            "INSERT INTO users(username,name,role,pwhash,salt,iters,active,must_change,created,created_by) VALUES(?,?,?,?,?,?,1,?,?,?)",
            (u, name.strip() or u, role, h, salt, iters, 1 if must_change else 0, _now(), by or ""),
        )
        c.commit()
    finally:
        c.close()


def update_user(username: str, by: str = "", *, name=None, role=None, active=None) -> None:
    u = _norm(username)
    c = _connect()
    try:
        row = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if not row:
            raise AuthError("No such user.")
        # Never let the last active master be demoted or disabled - you would lock everyone out.
        going_dark = (role is not None and role != "master") or (active == 0 or active is False)
        if row["role"] == "master" and going_dark and count_masters(active_only=True) <= 1:
            raise AuthError("This is the only master account - add another master before changing this one.")
        sets, vals = [], []
        if name is not None:
            sets.append("name=?"); vals.append(name.strip())
        if role is not None:
            if role not in ROLES:
                raise AuthError("Unknown role.")
            sets.append("role=?"); vals.append(role)
        if active is not None:
            sets.append("active=?"); vals.append(1 if active else 0)
        if sets:
            vals.append(u)
            c.execute("UPDATE users SET " + ", ".join(sets) + " WHERE username=?", vals)
            c.commit()
    finally:
        c.close()


def set_password(username: str, password: str, must_change: bool = False) -> None:
    if not password or len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    u = _norm(username)
    h, salt, iters = hash_pw(password)
    c = _connect()
    try:
        if not c.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
            raise AuthError("No such user.")
        c.execute("UPDATE users SET pwhash=?, salt=?, iters=?, must_change=? WHERE username=?",
                  (h, salt, iters, 1 if must_change else 0, u))
        c.commit()
    finally:
        c.close()


def delete_user(username: str) -> None:
    u = _norm(username)
    c = _connect()
    try:
        row = c.execute("SELECT role FROM users WHERE username=?", (u,)).fetchone()
        if not row:
            return
        if row["role"] == "master" and count_masters(active_only=False) <= 1:
            raise AuthError("Cannot delete the only master account.")
        c.execute("DELETE FROM users WHERE username=?", (u,))
        c.commit()
    finally:
        c.close()


def check_login(username: str, password: str) -> Optional[dict]:
    """Return the user dict on a correct password for an active account, else None."""
    c = _connect()
    try:
        r = c.execute("SELECT * FROM users WHERE username=?", (_norm(username),)).fetchone()
        if not r or not r["active"] or not _verify(password, r):
            return None
        c.execute("UPDATE users SET last_login=? WHERE username=?", (_now(), r["username"]))
        c.commit()
        return {"username": r["username"], "name": r["name"], "role": r["role"], "must_change": bool(r["must_change"])}
    finally:
        c.close()


# --------------------------------------------------------------------------- sessions (signed cookie, no server store)
def _secret() -> bytes:
    DATA.mkdir(exist_ok=True)
    if not SECRET_PATH.exists():
        SECRET_PATH.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(SECRET_PATH, 0o600)
        except OSError:
            pass
    return SECRET_PATH.read_bytes()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user: dict, hours: int = SESSION_HOURS) -> str:
    payload = {"u": user["username"], "r": user["role"], "n": user.get("name", ""), "exp": int(time.time()) + hours * 3600}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token: str) -> Optional[dict]:
    try:
        body, sig = (token or "").split(".", 1)
        good = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(_unb64(body))
        if int(payload.get("exp", 0)) < time.time():
            return None
        return {"username": payload["u"], "role": payload["r"], "name": payload.get("n", "")}
    except Exception:
        return None


def cookie_name() -> str:
    return _COOKIE


# --------------------------------------------------------------------------- bootstrap
def bootstrap() -> Optional[dict]:
    """Make sure at least one master exists. If none, create one and return its credentials (to print once)."""
    _connect().close()  # ensure the table exists
    if count_masters(active_only=False) > 0:
        return None
    username = _norm(os.environ.get("HUB_ADMIN_USER") or "admin")
    password = os.environ.get("HUB_ADMIN_PASS") or secrets.token_urlsafe(9)
    # If the chosen name is somehow taken by a non-master, fall back.
    if get_user(username):
        username = f"admin{secrets.token_hex(2)}"
    add_user(username, name="Administrator", role="master", password=password, by="system", must_change=True)
    return {"username": username, "password": password}


if __name__ == "__main__":  # tiny CLI: python hubauth.py add <user> <role> <password>
    import sys
    if len(sys.argv) >= 5 and sys.argv[1] == "add":
        add_user(sys.argv[2], sys.argv[2], sys.argv[3], sys.argv[4], by="cli", must_change=False)
        print("added", sys.argv[2])
    else:
        for u in list_users():
            print(f"{u['username']:20} {u['role']:8} {'active' if u['active'] else 'disabled'}  {u['name']}")
