#!/bin/bash
# Blend Hub - macOS launcher (double-click in Finder). First time only: see MAC_SETUP.txt.
cd "$(dirname "$0")" || exit 1
. ./_python.sh || { echo; read -r -p " Press Enter to close"; exit 1; }
echo
echo " Blend Hub is starting - it opens in its own window."
echo " Keep THIS window open while you work (closing it stops the Hub)."
echo
"$PYEXE" -X utf8 scripts/hubserver.py
status=$?
if [ $status -ne 0 ]; then echo; echo " Something went wrong - see the message above."; read -r -p " Press Enter to close"; fi
