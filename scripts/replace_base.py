#!/usr/bin/env python3
"""
Replace a base deck safely.   replace_base.py [--audience EPC] [new_deck.pptx]
 - checks the new deck has tagged project slides BEFORE touching anything
 - archives the current base to base/_archive
 - re-syncs the Excel registry (your Names / Categories / Versions are kept)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deckcore as core  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--audience", "-a")
    args = ap.parse_args()
    try:
        names = core.audience_names()
        aud = args.audience
        if not aud:
            print("Which base deck are you replacing?")
            for i, n in enumerate(names, 1):
                print(f"  {i}. {core.audience_cfg(n)['label']}  ({n})")
            c = input("Choose: ").strip()
            aud = names[int(c) - 1] if c.isdigit() and 1 <= int(c) <= len(names) else c
        f = (args.file or "").strip().strip('"')
        if not f:
            try:
                import tkinter as tk
                from tkinter import filedialog
                r = tk.Tk()
                r.withdraw()
                r.attributes("-topmost", True)
                f = filedialog.askopenfilename(title=f"Choose the new {aud} base deck", filetypes=[("PowerPoint", "*.pptx")])
                r.destroy()
            except Exception:
                f = input("Path to the new .pptx (you can drag the file here): ").strip().strip('"')
        if not f:
            print("Cancelled.")
            return 1
        core.replace_base(aud, f)
        return 0
    except core.DeckError as exc:
        print("\n*** NOT REPLACED - nothing was changed ***\n" + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
