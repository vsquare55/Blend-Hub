#!/usr/bin/env python3
"""Refresh projects_registry.xlsx from every base deck and report any problems."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deckcore as core  # noqa: E402

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        core.sync(verbose=True)
    except core.DeckError as exc:
        print("\n*** PROBLEM ***\n" + str(exc))
        sys.exit(1)
