#!/usr/bin/env python3
"""One spelling per financing / delivery model (EPC, EPC+F, PPP, PPP - Annuity, IPP, BOT, HAM ...).

Several models on one project are joined with ' / ', e.g. 'EPC+F / PPP - Annuity'."""
from __future__ import annotations

import re

WORDS = {
    "epc": "EPC", "turnkey epc": "EPC", "epcf": "EPC+F", "epc+f": "EPC+F", "epc + f": "EPC+F", "epc+finance": "EPC+F",
    "epc + finance": "EPC+F", "epc finance": "EPC+F", "epc+f ": "EPC+F",
    "ppp": "PPP", "ppp model": "PPP", "annuity": "PPP - Annuity", "annuity model": "PPP - Annuity", "ppp annuity": "PPP - Annuity",
    "ppp-annuity": "PPP - Annuity", "ppp - annuity": "PPP - Annuity", "ppp annuty": "PPP - Annuity",
    "ipp": "IPP", "bot": "BOT", "boot": "BOOT", "bto": "BTO", "ham": "HAM", "dbfm": "DBFM", "dbfot": "DBFOT", "dbfomt": "DBFOMT",
    "supply + finance": "Supply + Finance", "trade finance": "Trade Finance", "supply": "Supply", "development": "Development",
}
BLANK = {"", "tbd", "tbc", "n.a.", "n.a", "na", "n/a", "pending", "other", "-"}
ORDER = ["EPC", "EPC+F", "PPP", "PPP - Annuity", "IPP", "BOT", "BOOT", "BTO", "HAM", "DBFM", "DBFOT", "DBFOMT"]


def norm(value) -> str:
    t = str(value or "").strip()
    if t.lower() in BLANK:
        return "" if t.lower() in ("", "-") else t
    out = []
    for part in re.split(r"\s*(?:/|;|,|&|\band\b)\s*", re.sub(r"(?i)^proposed\s+", "", t)):
        k = " ".join(part.lower().split())
        if not k:
            continue
        w = WORDS.get(k) or WORDS.get(k.replace(" ", "")) or (part.strip().upper() if len(part.strip()) <= 6 else part.strip())
        if w not in out:
            out.append(w)
    if "PPP - Annuity" in out and "PPP" in out:
        out.remove("PPP")  # a bare PPP beside an annuity model says nothing more
    out.sort(key=lambda x: ORDER.index(x) if x in ORDER else 99)
    return " / ".join(out)


def parts(value) -> list:
    """['EPC+F', 'PPP - Annuity'] for filtering (each model of a combination is matched on its own)."""
    return [x.strip() for x in norm(value).split(" / ") if x.strip()]
