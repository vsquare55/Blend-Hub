#!/bin/bash
# Shared helper for macOS / Linux: finds Python 3, keeps a private environment OUTSIDE OneDrive (~/.blend-hub-env),
# installs python-pptx and openpyxl once, and sets PYEXE. Used by START_HERE.command.
VENV="$HOME/.blend-hub-env"
PYEXE=""
[ -x "$VENV/bin/python" ] && PYEXE="$VENV/bin/python"
if [ -z "$PYEXE" ]; then
  BASE=""
  for c in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    p="$(command -v $c 2>/dev/null)"
    [ -n "$p" ] || continue
    if "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then BASE="$p"; break; fi
  done
  if [ -z "$BASE" ]; then
    echo
    echo " Python 3 was not found on this Mac."
    echo " Install it once from https://www.python.org/downloads/macos/ (the normal installer), then double-click START_HERE.command again."
    return 1 2>/dev/null || exit 1
  fi
  echo " Setting up a private Python environment (one time, about a minute)..."
  "$BASE" -m venv "$VENV" || { echo " Could not create the environment."; return 1 2>/dev/null || exit 1; }
  PYEXE="$VENV/bin/python"
fi
if ! "$PYEXE" -c "import pptx, openpyxl" 2>/dev/null; then
  echo " Installing python-pptx and openpyxl - one time only..."
  "$PYEXE" -m pip install --quiet --upgrade pip python-pptx openpyxl || { echo " Install failed - check your internet connection."; return 1 2>/dev/null || exit 1; }
fi
export PYEXE
