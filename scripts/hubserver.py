#!/usr/bin/env python3
"""Blend Hub - local web app. Run it (START_HUB.bat); it opens the Hub in its own window. Nothing is sent over the internet."""
from __future__ import annotations

import getpass
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import hubdb as H

WEB = Path(__file__).resolve().parent / "hubweb"
PORT = 8765
_SRC = [*Path(__file__).resolve().parent.glob("*.py"), WEB / "index.html"]
VER = str(int(max(f.stat().st_mtime for f in _SRC if f.exists())))  # changes whenever the program files change
LOCK: H.Lock = None  # type: ignore


LAST_HIT = time.time()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle_one_request(self):
        global LAST_HIT
        LAST_HIT = time.time()
        super().handle_one_request()

    def log_message(self, *a):  # quiet
        pass

    # ------------------------------------------------------------------ helpers
    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _hide(self) -> str:
        return self.headers.get("X-Hide") or ""

    def _lock_info(self) -> dict:
        return {"mine": LOCK.mine, "holder": LOCK.holder, "user": LOCK.user}

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/api/all":
                d = H.snapshot(self._hide())
                d["lock"] = self._lock_info()
                d["default_user"] = getpass.getuser().replace(".", " ").title()
                return self._json(d)
            if u.path == "/api/rev":
                return self._json({"rev": H.snapshot()["rev"] if False else _rev(), "lock": self._lock_info(), "ver": VER})
            if u.path == "/api/changes":
                return self._json(H.recent_changes(int(q.get("days", ["7"])[0]), hide=self._hide()))
            if u.path == "/api/deck/projects":
                import hubdeck
                return self._json(hubdeck.projects(q.get("aud", ["EPC"])[0]))
            if u.path == "/api/deck/backups":
                import hubdeck
                return self._json(hubdeck.backups(q.get("aud", ["EPC"])[0]))
            if u.path == "/api/deck/preset":
                import hubdeck
                return self._json(hubdeck.preset(q.get("aud", ["EPC"])[0], q.get("client", [""])[0]))
            if u.path == "/api/print/cols":
                import hubprint
                return self._json({k: [[i, l, d] for i, l, d in v] for k, v in hubprint.COLS.items()})
            if u.path == "/api/history":
                return self._json(H.history(int(q.get("txn", ["0"])[0])))
            if u.path in ("/api/xl/new", "/api/xl/get"):  # a real browser download: lands in the browser's Downloads
                import hubxl
                if u.path == "/api/xl/new":
                    f = hubxl.export_workbook(Path(tempfile.mkdtemp()) / "x.xlsx")
                    fname = f"Blend_Hub_full_{time.strftime('%Y%m%d_%H%M')}.xlsx"
                else:
                    f = hubxl.XL_BACKUPS / Path(q.get("name", [""])[0]).name
                    fname = f.name
                    if not f.is_file():
                        return self._send(404, b"not found", "text/plain")
                return self._send(200, f.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", {"Content-Disposition": f'attachment; filename="{fname}"'})
            if u.path == "/api/backups":
                import hubxl
                return self._json([{"name": p.name, "size": p.stat().st_size} for p in sorted(H.BACKUPS.glob("hub_*.db"), reverse=True)] + [{"name": x["name"], "size": 0, "excel": True} for x in hubxl.list_excel_backups()])
            path = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
            f = (WEB / path).resolve()
            if WEB.resolve() not in f.parents and f != WEB.resolve() or not f.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            return self._send(200, f.read_bytes(), ctype)
        except Exception as exc:
            traceback.print_exc()
            return self._json({"error": str(exc)}, 500)

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        raw = self._body()
        if u.path == "/api/shutdown" and self.client_address[0] == "127.0.0.1":  # a newer copy of the Hub asks this one to make way
            self._json({"ok": True})
            if LOCK:
                LOCK.release()
            threading.Timer(0.4, lambda: os._exit(0)).start()
            return
        by = urllib.parse.unquote(self.headers.get("X-User", "")) or LOCK.user
        try:
            if u.path == "/api/lock/take":
                LOCK.try_acquire(force=True)
                return self._json({"ok": True, "lock": self._lock_info()})
            if not LOCK.mine:
                LOCK.try_acquire()
            if not LOCK.mine:
                return self._json({"error": f"{LOCK.holder} is editing right now. You can read everything; to edit, ask them to close the Hub or use 'Take over'."}, 423)
            if u.path == "/api/import":
                name = urllib.parse.parse_qs(u.query).get("name", ["bip.xlsx"])[0]
                tmp = Path(tempfile.mkdtemp()) / (Path(name).name or "bip.xlsx")
                tmp.write_bytes(raw)
                import hubimport
                st = hubimport.import_bip(tmp, by)
                st.update(hubimport.import_madagascar(by))
                return self._json({"ok": True, "stats": st})
            if u.path == "/api/restore_backup":
                import hubxl
                f = hubxl.XL_BACKUPS / Path(json.loads(raw.decode("utf-8") or "{}").get("name", "")).name
                if not f.is_file():
                    raise H.HubError("That backup file is not there.")
                return self._json({"ok": True, "stats": hubxl.restore_workbook(f, by)})
            if u.path == "/api/restore":
                import hubxl
                tmp = Path(tempfile.mkdtemp()) / "restore.xlsx"
                tmp.write_bytes(raw)
                return self._json({"ok": True, "stats": hubxl.restore_workbook(tmp, by)})
            d = json.loads(raw.decode("utf-8") or "{}")
            if u.path == "/api/txn":
                tid = H.txn_save(by, d.get("fields", {}), d.get("id"))
                return self._json({"ok": True, "id": tid})
            if u.path == "/api/link":
                pid = H.link_set(by, d["txn_id"], d.get("party_id"), d.get("name", ""), d.get("type", ""), d.get("status", "Identified"), d.get("remark"))
                return self._json({"ok": True, "party_id": pid})
            if u.path == "/api/link/del":
                H.link_del(by, d["txn_id"], d["party_id"])
                return self._json({"ok": True})
            if u.path == "/api/need":
                H.need_set(by, d["txn_id"], d["type"], d["state"])
                return self._json({"ok": True})
            if u.path == "/api/chk":
                H.chk_set(by, d["txn_id"], d["item"], d.get("state", ""), d.get("remark"))
                return self._json({"ok": True})
            if u.path == "/api/chk/del":
                H.chk_del(by, d["txn_id"], d["item"])
                return self._json({"ok": True})
            if u.path == "/api/chk/bulk":
                return self._json({"ok": True, "n": H.chk_bulk(by, d["txn_ids"], d["item"], d.get("state", ""))})
            if u.path == "/api/party":
                H.party_save(by, d["id"], d.get("fields", {}))
                return self._json({"ok": True})
            if u.path == "/api/txn/bulk":
                return self._json({"ok": True, "n": H.txn_bulk(by, d["ids"], d["fields"])})
            if u.path == "/api/txn/trash":
                H.txn_trash(by, d["ids"], d.get("deleted", True))
                return self._json({"ok": True})
            if u.path == "/api/txn/dup":
                return self._json({"ok": True, "id": H.txn_duplicate(by, d["id"])})
            if u.path == "/api/undo":
                H.undo_log(by, d["log_id"])
                return self._json({"ok": True})
            if u.path == "/api/comment":
                return self._json({"ok": True, "id": H.comment_add(by, d["txn_id"], d.get("text", ""), d.get("day", ""), d.get("kind", ""))})
            if u.path == "/api/meeting/add":
                return self._json({"ok": True, "id": H.meeting_add(by, d["txn_id"], d.get("day", ""), d.get("who", ""), d.get("status", "Held"), d.get("notes", ""))})
            if u.path == "/api/meeting/update":
                H.meeting_update(by, d["id"], d.get("fields", {}))
                return self._json({"ok": True})
            if u.path == "/api/meeting/latest":
                H.meeting_latest_set(by, d["txn_id"], d.get("fields", {}))
                return self._json({"ok": True})
            if u.path == "/api/vocab/suggest":
                return self._json({"ok": True, "groups": H.vocab_suggest(d["field"])})
            if u.path == "/api/vocab/dedupe":
                return self._json({"ok": True, "n": H.vocab_dedupe(by, d["field"])})
            if u.path == "/api/party/dedupe":
                return self._json({"ok": True, "n": H.party_dedupe(by, d.get("type", ""))})
            if u.path == "/api/vocab/merge":
                return self._json({"ok": True, "n": H.vocab_merge(by, d["field"], d.get("froms", []), d.get("to", ""))})
            if u.path == "/api/undo/last":
                return self._json({"ok": True, "undone": H.undo_last(by)})
            if u.path == "/api/redo/last":
                return self._json({"ok": True, "redone": H.redo_last(by)})
            if u.path == "/api/party/bulk_add":
                return self._json({"ok": True, **H.party_bulk_add(by, d["type"], d.get("rows", []))})
            if u.path == "/api/party/bulk":
                return self._json({"ok": True, **H.party_bulk(by, d["ids"], d["action"], d.get("value", ""))})
            if u.path == "/api/party/bulk_edit":
                return self._json({"ok": True, "n": H.party_bulk_edit(by, d.get("edits", []))})
            if u.path == "/api/link/bulk":
                return self._json({"ok": True, "n": H.link_bulk(by, d["party_ids"], d["txn_ids"], d["action"], d.get("status", "Shortlisted"))})
            if u.path == "/api/comment/edit":
                H.comment_edit(by, d["id"], d.get("text"), bool(d.get("deleted")))
                return self._json({"ok": True})
            if u.path == "/api/action":
                return self._json({"ok": True, "id": H.action_add(by, d["txn_id"], d.get("text", ""), d.get("owner", ""), d.get("due", ""))})
            if u.path == "/api/action/bulk":
                return self._json({"ok": True, "n": H.action_bulk(by, d["txn_ids"], d.get("text", ""), d.get("owner", ""), d.get("due", ""))})
            if u.path == "/api/access":
                return self._json({"ok": True, "id": H.access_save(by, d.get("id"), d.get("fields", {}))})
            if u.path == "/api/access/del":
                H.access_del(by, d["id"])
                return self._json({"ok": True})
            if u.path == "/api/action/update":
                H.action_update(by, d["id"], d.get("fields", {}))
                return self._json({"ok": True})
            if u.path == "/api/review":
                H.review_mark(by, d["txn_id"], int(d.get("days", 7)))
                return self._json({"ok": True})
            if u.path == "/api/geo":
                return self._json({"ok": True, "n": H.geo_set(by, d["country"], d.get("lead", ""), d.get("apply", True))})
            if u.path == "/api/source/rename":
                return self._json({"ok": True, "n": H.source_rename(by, d["old"], d["new"])})
            if u.path == "/api/party/delete":
                H.party_delete(by, d["id"])
                return self._json({"ok": True})
            if u.path == "/api/backup":
                import hubxl
                p = H.backup(force=True)
                x = hubxl.excel_backup(force=True)
                return self._json({"ok": True, "file": p.name if p else "", "excel": x.name if x else ""})
            if u.path == "/api/export":
                import hubxl, deckcore
                folder = Path.home() / "Downloads"
                if not folder.is_dir():
                    folder = H.ROOT / "exports"
                dest = folder / f"Blend_Hub_full_{time.strftime('%Y%m%d_%H%M')}.xlsx"
                hubxl.export_workbook(dest)
                deckcore.os_open(dest)
                return self._json({"ok": True, "path": str(dest)})
            if u.path == "/api/deck/open":
                subprocess.Popen([sys.executable, "-X", "utf8", str(H.ROOT / "scripts" / "generate_client_deck.py")], cwd=str(H.ROOT))
                return self._json({"ok": True})
            if u.path == "/api/print":
                import hubprint
                snap = H.snapshot(self._hide())
                kind, opts, fmt = d.get("kind", "register"), d.get("opts", {}), d.get("format", "pdf")
                if fmt == "xlsx":
                    f = hubprint.build_xlsx(kind, snap, d["ids"], opts, Path(tempfile.mkdtemp()) / "Blend.xlsx")
                    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                else:
                    f = hubprint.build_pdf(kind, snap, d["ids"], opts)
                    ctype = "application/pdf"
                if d.get("save"):  # write to the Downloads folder and open it - no browser download / print dialog involved
                    import deckcore
                    folder = Path.home() / "Downloads"
                    if not folder.is_dir():
                        folder = H.ROOT / "exports"
                    folder.mkdir(parents=True, exist_ok=True)
                    dest = folder / f"Blend_{kind}_{time.strftime('%Y%m%d')}{f.suffix}"
                    n = 1
                    while dest.exists():
                        n += 1
                        dest = folder / f"Blend_{kind}_{time.strftime('%Y%m%d')}_{n}{f.suffix}"
                    shutil.copyfile(f, dest)
                    deckcore.os_open(dest)
                    return self._json({"ok": True, "path": str(dest)})
                return self._send(200, f.read_bytes(), ctype, {"Content-Disposition": f'inline; filename="Blend_{kind}_{time.strftime("%Y%m%d")}{f.suffix}"'})
            if u.path == "/api/report":
                import hubreport
                snap = H.snapshot(self._hide())
                opts = d.get("opts", {})
                if d.get("format") == "pdf":
                    f = hubreport.build_pdf(snap, d["ids"], opts)
                    ctype = "application/pdf"
                else:
                    f = hubreport.build_xlsx(snap, d["ids"], opts, Path(tempfile.mkdtemp()) / "Blend_pipeline.xlsx")
                    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                name = f"Blend_pipeline_{time.strftime('%Y%m%d')}{f.suffix}"
                return self._send(200, f.read_bytes(), ctype, {"Content-Disposition": f'attachment; filename="{name}"'})
            if u.path.startswith("/api/deck/") and u.path != "/api/deck/open":
                import hubdeck
                import deckcore
                try:
                    a = d.get("aud", "EPC")
                    if u.path == "/api/deck/generate":
                        return self._json({"ok": True, **hubdeck.generate(a, d.get("client", ""), d["selections"], bool(d.get("save_defaults")), d.get("all_ids"))})
                    if u.path == "/api/deck/update":
                        return self._json({"ok": True, "n": hubdeck.update(a, d["keys"], d["changes"])})
                    if u.path == "/api/deck/rename":
                        hubdeck.rename(a, d["old"], d["new"])
                    elif u.path == "/api/deck/retire":
                        hubdeck.retire(a, d["keys"], bool(d.get("retired", True)))
                    elif u.path == "/api/deck/delete":
                        hubdeck.delete(a, d["keys"])
                    elif u.path == "/api/deck/move":
                        hubdeck.move(a, d["keys"], d["where"])
                    elif u.path == "/api/deck/add":
                        hubdeck.add(a, d["f"])
                    elif u.path == "/api/deck/restore":
                        hubdeck.restore(a, d["file"])
                    elif u.path == "/api/deck/openfile":
                        hubdeck.open_path(d["path"], bool(d.get("reveal")))
                    else:
                        return self._json({"error": "unknown call"}, 404)
                    return self._json({"ok": True})
                except deckcore.DeckError as exc:
                    return self._json({"error": str(exc)}, 400)
            if u.path == "/api/txn/todeck":
                import hubdeck
                return self._json({"ok": True, **hubdeck.from_txns(by, d["ids"], d.get("aud", "EPC"))})
            if u.path == "/api/party/new":
                return self._json({"ok": True, "id": H.party_new(by, d["name"], d["type"], d.get("country", ""))})
            if u.path == "/api/party/merge":
                H.party_merge(by, d["keep"], d["drop"])
                return self._json({"ok": True})
            return self._json({"error": "unknown call"}, 404)
        except H.HubError as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:
            traceback.print_exc()
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def _rev() -> int:
    c = H.connect()
    try:
        r = c.execute("SELECT v FROM meta WHERE k='rev'").fetchone()
        return int(r[0]) if r else 0
    finally:
        c.close()


def open_window(url: str):
    """Edge / Chrome 'app' window (no tabs, no address bar) = looks like a normal desktop program; plain browser as a fallback."""
    import deckcore
    exe = deckcore.find_chromium()
    if exe:
        try:
            profile = Path(tempfile.gettempdir()) / "blend_hub_profile"
            subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1500,920", "--no-first-run"])
            return
        except OSError:
            pass
    webbrowser.open(url)


def already_running():
    """The version of the Hub already answering on this port, or None."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/rev", timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8")).get("ver", "old") if r.status == 200 else None
    except Exception:
        return None


def replace_old_hub() -> bool:
    """A Hub from before the last update is still running (closing its window does not stop it): stop it so the new one starts."""
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/api/shutdown", data=b"{}", method="POST"), timeout=3)
    except Exception:
        pass
    for _ in range(20):
        time.sleep(0.4)
        if already_running() is None:
            return True
    return False


def _excel_loop():
    """Excel copy of everything: at start and then every 6 hours while the Hub is open (kept 30)."""
    import hubxl

    def one():
        try:
            hubxl.excel_backup(every_hours=12)
        except Exception:
            traceback.print_exc()
    threading.Thread(target=one, daemon=True).start()

    def beat():
        while True:
            time.sleep(6 * 3600)
            if LOCK and LOCK.mine:
                one()
    threading.Thread(target=beat, daemon=True).start()


def main():
    global LOCK
    H.DATA.mkdir(exist_ok=True)
    running = already_running()
    if running is not None:
        if running == VER:  # the same Hub is already open on this PC: just show it
            open_window(f"http://127.0.0.1:{PORT}")
            return
        if not replace_old_hub():
            print("An older Hub is still running and could not be stopped. Close its black window (the one titled 'Blend Hub'), then start again.")
            open_window(f"http://127.0.0.1:{PORT}")
            return
    LOCK = H.Lock(getpass.getuser().replace(".", " ").title())
    LOCK.start()
    H.backup()
    _excel_loop()
    c = H.connect()
    empty = c.execute("SELECT COUNT(*) FROM txn").fetchone()[0] == 0
    c.close()
    if empty:
        for cand in (Path.home() / "Downloads" / "BIP - Captive Projects.xlsx", H.ROOT / "BIP - Captive Projects.xlsx"):
            if cand.exists():
                import hubimport
                print("First start: loading", cand)
                hubimport.import_bip(cand)
                hubimport.import_madagascar()
                break
    srv = ThreadingHTTPServer(("0.0.0.0" if os.environ.get("HUB_SHARE") else "127.0.0.1", PORT), Handler)
    print(f"Blend Hub running at http://127.0.0.1:{PORT}  (close this window to stop)")
    if not os.environ.get("HUB_NO_WINDOW"):
        threading.Timer(0.8, lambda: open_window(f"http://127.0.0.1:{PORT}")).start()
    if os.environ.get("HUB_AUTOQUIT"):  # started from the Mac app (no Terminal window): stop when the Hub window has been closed for 3 minutes
        def watch():
            global LAST_HIT
            prev = time.time()
            while True:
                time.sleep(15)
                now = time.time()
                if now - prev > 60:  # the computer was asleep - give the window time to wake up
                    LAST_HIT = now
                prev = now
                if now - LAST_HIT > 180:
                    LOCK.release()
                    os._exit(0)
        threading.Thread(target=watch, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        LOCK.release()


if __name__ == "__main__":
    main()
