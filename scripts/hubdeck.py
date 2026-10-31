#!/usr/bin/env python3
"""Blend Hub - the deck generator and project manager behind the 'Decks' page (same engine as the old DealDeck window)."""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import Dict, List

import deckcore as core
import projmgr as pm

_lock = threading.Lock()
AUDIENCES = {"EPC": "EPC contractor", "Investor": "Investor"}


def _aud(a: str) -> str:
    if a not in AUDIENCES:
        raise core.DeckError("Audience must be EPC or Investor.")
    return a


def projects(aud: str) -> dict:
    with _lock:
        data = core.load_projects(_aud(aud), include_retired=True)
    out = []
    for p in data["projects"]:
        out.append({"id": p["id"], "sr": p.get("sr", ""), "name": p["name"], "unnamed_name": p.get("unnamed_name", ""), "category": p["category"],
                    "version": p["version"], "include": bool(p["include"]), "model": p.get("model", ""), "country": p.get("country", ""),
                    "sector": p.get("sector", ""), "source": p.get("source", ""), "retired": bool(p.get("retired")), "has_value": bool(p.get("has_value")),
                    "leaks": p.get("leaks", []), "has_named": bool(p.get("has_named")), "has_unnamed": bool(p.get("has_unnamed")),
                    "region": p.get("region", ""), "slides": p.get("slides", {})})
    return {"projects": out, "warnings": data.get("warnings", []), "categories": core.CATEGORY_ORDER}


def preset(aud: str, client: str) -> dict:
    pre = core.load_preset(_aud(aud), client or None) or core.load_preset(aud, None)
    return {"selections": (pre or {}).get("selections", [])}


def generate(aud: str, client: str, selections: List[dict], save_defaults: bool = False, all_ids: List[str] = None) -> dict:
    client = " ".join(str(client).split())
    if not client:
        raise core.DeckError("Please enter the client / recipient name.")
    if not selections:
        raise core.DeckError("Tick at least one project.")
    with _lock:
        res = core.generate(_aud(aud), client, selections, log=lambda m: None)
        if save_defaults:
            if not core.save_defaults(aud, selections, all_ids or [s["id"] for s in selections]):
                res["warnings"].append("Excel defaults NOT saved (projects_registry.xlsx is open in Excel).")
    return {"path": str(res["path"]), "n_slides": res["n_slides"], "warnings": res["warnings"]}


def update(aud: str, keys: List[str], changes: Dict[str, str]) -> int:
    with _lock:
        return pm.update_fields(_aud(aud), keys, changes)


def rename(aud: str, old: str, new: str):
    with _lock:
        pm.rename_project(_aud(aud), old, new)


def retire(aud: str, keys: List[str], retired: bool):
    with _lock:
        return pm.set_retired(_aud(aud), keys, retired)


def delete(aud: str, keys: List[str]):
    with _lock:
        return pm.delete_projects(_aud(aud), keys, None, log=lambda m: None)


def move(aud: str, keys: List[str], where: str):
    with _lock:
        return pm.move_projects(_aud(aud), keys, where)


def add(aud: str, f: dict) -> dict:
    title = " ".join(str(f.get("title", "")).split())
    if not title:
        raise core.DeckError("The project needs a title.")
    key = core.norm_id(f.get("key") or title)[:40]
    card = {"head": "", "sub": "", "bullets": "", "chip": "", "hl": ""}
    spec = {"key": key, "country": f.get("country", ""), "region": f.get("region", ""), "model": f.get("model", ""), "sector": f.get("sector", ""),
            "source": f.get("source", ""), "category": f.get("category") or None, "hide": [], "title": title, "sub": f.get("sub", ""), "A": dict(card), "B": dict(card),
            "steps": [], "strip": "", "footer": "", "value": f.get("value", "")}
    with _lock:
        return pm.add_project(_aud(aud), spec, f.get("versions", "both"), f.get("after") or None)


def from_txns(by: str, ids: List[int], aud: str = "EPC") -> dict:
    """Put Hub transactions into the base deck: one placeholder slide pair (named + unnamed) each, title + country / sector / model / source filled in.
    The slide body stays empty until the details are added in the deck (nothing from the internal notes is copied - those are never for outsiders)."""
    import hubdb as H
    try:
        from new_projects_data import REGION
    except Exception:
        REGION = {}
    done, skipped, errors = [], [], []
    for tid in ids:
        c = H.connect()
        t = c.execute("SELECT * FROM txn WHERE id=? AND deleted=0", (tid,)).fetchone()
        c.close()
        if not t:
            continue
        if t["deck_key"]:
            skipped.append(t["name"])
            continue
        name = " ".join(t["name"].split())
        title = name if t["country"] and t["country"].lower() in name.lower() else (f"{t['country']} — {name}" if t["country"] else name)
        try:
            key = core.norm_id(title)[:40]
            add(aud, {"title": title, "key": key, "country": t["country"], "region": REGION.get(t["country"], "Africa"), "sector": t["sector"],
                      "model": t["structure"], "source": t["introduced"], "category": "BIP" if t["status"] != "On hold" else "Hold", "versions": "both"})
            H.txn_save(by, {"deck_key": key}, tid)
            done.append(name)
        except core.DeckError as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
    return {"added": done, "skipped": skipped, "errors": errors}


def backups(aud: str) -> List[dict]:
    return [{"file": b["file"], "when": b["when"].strftime("%d %b %Y %H:%M"), "what": b["what"], "mb": round(b["size"] / 1048576, 1)} for b in pm.list_backups(_aud(aud))[:40]]


def restore(aud: str, file: str):
    with _lock:
        pm.restore_backup(_aud(aud), file)


def open_path(path: str, reveal: bool = False):
    p = Path(path)
    if not p.exists() or core.ROOT not in p.resolve().parents:
        raise core.DeckError("That file is not inside the DealDeck folder.")
    core.os_open(p, reveal)
