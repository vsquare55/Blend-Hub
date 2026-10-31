#!/usr/bin/env python3
"""Sector list + automatic first-time classification of a project from its name (you can change it any time)."""
from __future__ import annotations

import re

SECTORS = ["Power", "Oil & Gas", "Water", "Transport", "Health", "Education", "Agriculture & Rural", "Mining",
           "Telecom", "Urban & Infrastructure", "Mixed / Other"]

# projects that mention several sectors in their name: decided by hand
OVERRIDES = {
    "benin_rail_education": "Mixed / Other",
    "tanzania_tx_hospital_solar": "Mixed / Other",
    "tanzania_port_leads": "Mixed / Other",
    "botswana_pipeline": "Mixed / Other",
    "burkina_gas_hfo": "Mixed / Other",
    "guinea_urban_leads": "Urban & Infrastructure",
    "cameroon_camtel": "Telecom",
}

# first matching rule wins (order matters)
RULES = [
    ("Health", r"hospital|health|clinic|medical"),
    ("Education", r"school|education|college|polytechnic|university"),
    ("Mining", r"\bgold\b|mining|\bmine\b|phosphate|copper"),
    ("Telecom", r"telecom|camtel|mobile network"),
    ("Oil & Gas", r"hydrocarbon|storage depot|oil depot|floating oil|tank farm|fuel tank|refinery|lng import|oil terminal|petroleum|gas pipeline"),
    ("Power", r"ccgt|solar|\bwind\b|\bhfo\b|\bbess\b|battery|geothermal|transmission|\bgrid\b|substation|hydro|"
              r"power plant|modular gas|gas-to-power|waste-to-energy|energy storage|power pipeline|\bkv\b"),
    ("Water", r"water|\bwtp\b|river"),
    ("Transport", r"\broads?\b|airport|runway|\bport\b|\brail|railway|expressway|highway"),
    ("Agriculture & Rural", r"agricult|fertili|rural|irrigat|cotton"),
    ("Urban & Infrastructure", r"convention|urban|\bcity\b|housing|real estate"),
]


def infer_sector(key: str, *texts: str) -> str:
    if key in OVERRIDES:
        return OVERRIDES[key]
    blob = " ".join(t for t in texts if t).lower()
    for sector, rx in RULES:
        if re.search(rx, blob):
            return sector
    return "Mixed / Other"
