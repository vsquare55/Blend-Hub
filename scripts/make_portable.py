#!/usr/bin/env python3
"""
Build a self-contained, portable package of the Deck Manager:  dist/DealDeck_Studio_Portable_<date>.zip

The zip contains the tool, the current base deck + Excel registry AND a private copy of the Python runtime
(only the libraries the tool needs), so it runs on any Windows 10/11 64-bit PC with nothing installed,
no admin rights and no internet.  Unzip anywhere, double-click START_HERE.bat.

Run again (MAKE_PORTABLE.bat) whenever the base deck / registry changed and you want to hand out a fresh copy.
"""
from __future__ import annotations

import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = "DealDeck Studio"
KEEP_SITE = {"pptx", "openpyxl", "et_xmlfile", "lxml", "PIL", "xlsxwriter", "typing_extensions.py"}
SKIP_LIB = {"test", "idlelib", "turtledemo", "ensurepip", "lib2to3", "__pycache__", "site-packages", "tkinter_demos"}
PROJECT_FILES = ["START_HERE.bat", "REPLACE_BASE.bat", "SYNC_FROM_PPTX.bat", "_python.bat", "CREATE_DESKTOP_SHORTCUT.bat",
                 "README.md", "HOW_TO_TAG_IN_PPTX.txt", "config.json", "requirements.txt", "projects_registry.xlsx"]

README_PORTABLE = """DEALDECK STUDIO - PORTABLE COPY
===========================================

1. Unzip this folder anywhere (Desktop, USB stick, shared drive). Do not run it from inside the zip.
2. Double-click START_HERE.bat.
3. Choose EPC or Investor -> client name -> projects -> Generate. Decks appear in the 'output' folder.

Needs: Windows 10/11 (64-bit). Does NOT need: Python, internet, admin rights or PowerPoint to BUILD decks
(PowerPoint is only needed to open / edit them).

Other buttons:  REPLACE_BASE.bat (swap the base deck) | SYNC_FROM_PPTX.bat (health report)
Inside the app: "Manage projects" to add / edit / delete / retire / reorder projects and to undo changes.

IMPORTANT: this package contains your confidential base deck and project registry. Share it only with people
who may see all of it, and keep ONE person as owner of base\\EPC_Partnership_Base.pptx and projects_registry.xlsx.
Changes made in a copy do not flow back to the original - hand the edited base deck to the owner.
"""


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except PermissionError:
        sys.exit(f"Cannot read {path.name} - it is open in PowerPoint/Excel. Save, close it and run again.")


def main() -> int:
    py = Path(sys.base_prefix)
    if not (py / "python.exe").exists():
        sys.exit(f"python.exe not found in {py}")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"DealDeck_Studio_Portable_{datetime.now():%Y%m%d}.zip"
    tmp = out.with_suffix(".building")
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        def add(path: Path, arc: str, data: bytes | None = None):
            nonlocal n
            z.writestr(f"{TOP}/{arc}", data if data is not None else _read(path))
            n += 1

        for f in PROJECT_FILES:
            if (ROOT / f).exists():
                add(ROOT / f, f)
        for f in sorted((ROOT / "scripts").glob("*.py")):
            add(f, f"scripts/{f.name}")
        for f in sorted((ROOT / "scripts" / "hubweb").glob("*")):
            add(f, f"scripts/hubweb/{f.name}")
        for f in sorted((ROOT / "assets").glob("*")):
            add(f, f"assets/{f.name}")
        base = ROOT / "base" / "EPC_Partnership_Base.pptx"
        if not base.exists():
            sys.exit("No base deck to package: base/EPC_Partnership_Base.pptx")
        add(base, "base/EPC_Partnership_Base.pptx")
        for d in ("output", "presets", "backups"):
            z.writestr(f"{TOP}/{d}/.keep", b"")
        z.writestr(f"{TOP}/READ_ME_FIRST.txt", README_PORTABLE.encode("utf-8"))

        # ---- private Python runtime
        for f in ("python.exe", "pythonw.exe", "python3.dll", "python314.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
            if (py / f).exists():
                add(py / f, f"runtime/{f}")
        for f in sorted(py.glob("python3*.dll")):
            if f.name not in ("python3.dll", "python314.dll"):
                add(f, f"runtime/{f.name}")
        for sub in ("DLLs", "tcl"):
            for r, ds, fs in os.walk(py / sub):
                ds[:] = [d for d in ds if d != "__pycache__" and not d.startswith("tcl8.6/tzdata")]
                for f in fs:
                    p = Path(r) / f
                    add(p, f"runtime/{p.relative_to(py).as_posix()}")
        lib = py / "Lib"
        for r, ds, fs in os.walk(lib):
            rel = Path(r).relative_to(lib)
            ds[:] = [d for d in ds if d not in SKIP_LIB or (rel.parts == () and d == "site-packages")]
            if rel.parts[:1] == ("site-packages",):
                continue
            for f in fs:
                if f.endswith((".pyc", ".pyo")):
                    continue
                p = Path(r) / f
                add(p, f"runtime/Lib/{p.relative_to(lib).as_posix()}")
        sp = lib / "site-packages"
        for item in sorted(sp.iterdir()):
            nm = item.name
            if nm in KEEP_SITE or any(nm.startswith(k.split(".")[0] + "-") and nm.endswith(".dist-info") for k in KEEP_SITE):
                if item.is_dir():
                    for r, ds, fs in os.walk(item):
                        ds[:] = [d for d in ds if d != "__pycache__"]
                        for f in fs:
                            if not f.endswith((".pyc", ".pyo")):
                                p = Path(r) / f
                                add(p, f"runtime/Lib/site-packages/{p.relative_to(sp).as_posix()}")
                else:
                    add(item, f"runtime/Lib/site-packages/{nm}")
    os.replace(tmp, out)
    print(f"Built {out}\n  {n} files, {out.stat().st_size / 1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
