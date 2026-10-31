# -*- coding: utf-8 -*-
"""
Content for the projects added to the EPC base deck (Table 3 'New' items).

Source: the pipeline / hold spreadsheets only. Deliberately NOT carried onto slides:
partner / EPC / bank / lender / sponsor names, status notes, scores, assessments, internal remarks.

Text tokens:  {{named text|unnamed text}}  ->  one or the other depending on the slide version.
Every named-side token is automatically checked to be ABSENT from the unnamed slide.

Per project:
  key, section, country, model, hold, title, sub,
  A = (head, sub, [(lead, text) ...], chip, highlight)
  B = (head, sub, [(lead, text) ...], chip, highlight)
  steps = [(line1, line2) x4], strip = label, footer, value (optional), placeholder (bool)
"""

REGION = {
    "Guinea": "West Africa", "Burkina Faso": "West Africa", "Benin": "West Africa", "Sierra Leone": "West Africa",
    "Liberia": "West Africa", "Niger": "West Africa", "Togo": "West Africa",
    "Cameroon": "Central Africa", "Gabon": "Central Africa", "Chad": "Central Africa",
    "Tanzania": "East Africa", "Madagascar": "East Africa", "Botswana": "Southern Africa",
}


def N(c):  # country token
    return "{{%s|%s}}" % (c, REGION[c])


# Order of insertion: (after_key, [projects in deck order])
EPCF_AFTER, PPP_AFTER, EPC_AFTER = "roc_floating", "drc_rural", "tanzania_geo"

P = []


def add(**kw):
    P.append(kw)


# ============================================================================ EPC+F section
add(key="guinea_grid", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — Grid Modernisation & Expansion (5 contracts)",
    sub="Phase 1 modernisation and Phase 2 new build · EPC + Finance with 100% debt · framework agreements signed",
    A=("PHASE 1 — MODERNISATION", "Upgrade of the existing 60/110 kV network", [
        ("{{Manéah–Libraport–Kaloum 60/110 kV|60/110 kV network upgrade}}:", " modernisation, 24 months"),
        ("{{Garafiri 110 kV|110 kV upgrade (1)}}:", " modernisation, 8 months"),
        ("{{Samou–Manéah 110 kV|110 kV upgrade (2)}}:", " modernisation, 14 months")],
       "3 CONTRACTS · 8–24 MONTHS", "Phase 1: three modernisation contracts"),
    B=("PHASE 2 — NEW BUILD", "New substations and 225 kV lines", [
        ("{{Fandjé|New}} substation + 225 kV line:", " 24 months"),
        ("{{Dubréka|New}} substation + 225 kV line:", " 24 months"),
        ("Structure:", " EPC + Finance, 100% debt")],
       "EPC + FINANCE · 100% DEBT", "2 new substations with 225 kV lines"),
    steps=[("5 contracts", "Across two phases"), ("3 contracts", "Phase 1 modernisation"),
           ("2 contracts", "Phase 2 new 225 kV build"), ("8–24 months", "Execution per contract")],
    strip="PROGRAMME SNAPSHOT  —  GRID MODERNISATION & EXPANSION",
    footer=N("Guinea") + " — Power transmission · EPC+F · Framework agreements signed · Opportunity summary",
    value="Indicative value: USD ~362 Mn (5 contracts)")

add(key="burkina_bassinko", section="EPCF", country="Burkina Faso", model="EPC+F",
    title=N("Burkina Faso") + " — {{Bassinko |}}Hospital under EPC+F Model",
    sub="Healthcare infrastructure · EOI accepted by the Government · project data being collected",
    A=("PROJECT OVERVIEW", "Asset and delivery model", [
        ("Asset:", "  hospital facility{{ (Bassinko)|}}"),
        ("Sector:", "  healthcare infrastructure"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "HEALTHCARE · EPC+F", "Hospital project under EPC+F"),
    B=("STAGE & NEXT STEPS", "Where the project stands", [
        ("Expression of interest:", "  submitted and accepted by the Government"),
        ("Requirements:", "  project requirements being collected"),
        ("Next:", "  tripartite agreement and technical data")],
       "EOI ACCEPTED", "EOI accepted — data collection under way"),
    steps=[("Healthcare", "Hospital project"), ("EPC+F", "Delivery model"),
           ("EOI accepted", "By the Government"), ("Data collection", "Next stage")],
    strip="PROJECT SNAPSHOT  —  HOSPITAL",
    footer=N("Burkina Faso") + " — Healthcare · EPC+F · Opportunity summary")

add(key="guinea_health", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — National Health Programme (31 Hospitals)",
    sub="Renovation and extension of 31 hospitals across 8 regions · financed in clustered tranches",
    A=("PROGRAMME SCOPE", "National hospital renovation programme", [
        ("Scope:", "  renovation / extension of 31 hospitals"),
        ("Coverage:", "  8 regions across the country"),
        ("Focus:", "  {{Ntag Hospital|one priority hospital}} (scope narrowed from the full list)")],
       "31 HOSPITALS · 8 REGIONS", "National programme, tranche-based"),
    B=("FINANCING & STAGE", "Clustered delivery", [
        ("Structure:", "  hospitals clustered 4–5 per financing tranche"),
        ("Stage:", "  information pending"),
        ("Awaited:", "  project identification document from the Ministry of Health")],
       "4–5 HOSPITALS PER TRANCHE", "Tranche-based financing"),
    steps=[("31 hospitals", "In the programme"), ("8 regions", "Nationwide coverage"),
           ("4–5 per tranche", "Financing clusters"), ("PID awaited", "From the Ministry of Health")],
    strip="PROGRAMME SNAPSHOT  —  NATIONAL HEALTH PROGRAMME",
    footer=N("Guinea") + " — Healthcare · EPC+F · Opportunity summary",
    value="Indicative value: EUR >150–200 Mn (estimate)")

add(key="liberia_hospital", section="EPCF", country="Liberia", model="EPC+F",
    title=N("Liberia") + " — {{John F. Kennedy |}}Hospital Reconstruction",
    sub="Reconstruction and upgrade of an existing hospital · EPC+F · survey completed",
    A=("PROJECT OVERVIEW", "Asset and scope", [
        ("Asset:", "  {{John F. Kennedy Hospital|existing hospital}}"),
        ("Scope:", "  reconstruction and upgrade"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "RECONSTRUCTION · EPC+F", "Hospital reconstruction and upgrade"),
    B=("STAGE & NEXT STEPS", "Where the project stands", [
        ("Survey:", "  completed; survey report received"),
        ("Next:", "  approach to the Ministry of Health"),
        ("Financing route:", "  to be established")],
       "SURVEY COMPLETED", "Survey report available"),
    steps=[("Healthcare", "Hospital reconstruction"), ("EPC+F", "Delivery model"),
           ("Survey done", "Report received"), ("Ministry of Health", "Next engagement")],
    strip="PROJECT SNAPSHOT  —  HOSPITAL RECONSTRUCTION",
    footer=N("Liberia") + " — Healthcare · EPC+F · Opportunity summary")

add(key="burkina_solar100", section="EPCF", country="Burkina Faso", model="EPC+F",
    title=N("Burkina Faso") + " — 100 MW Solar Power Plant under EPC+F",
    sub="Utility-scale solar PV · offtake by {{SONABEL, the national utility|the national utility}}",
    A=("PROJECT OVERVIEW", "Asset and offtaker", [
        ("Capacity:", "  100 MW solar power plant"),
        ("Offtaker:", "  {{SONABEL (national utility)|the national utility}}"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "100 MW SOLAR PV", "100 MW · utility-scale solar"),
    B=("STAGE & NEXT STEPS", "Where the project stands", [
        ("Stage:", "  initial — expression of interest submitted"),
        ("Value:", "  to be confirmed"),
        ("Next:", "  project documents and financing structure")],
       "INITIAL STAGE", "Early-stage solar opportunity"),
    steps=[("100 MW", "Installed capacity"), ("Solar PV", "Technology"),
           ("EPC+F", "Delivery model"), ("Initial", "Development stage")],
    strip="PROJECT SNAPSHOT  —  100 MW SOLAR",
    footer=N("Burkina Faso") + " — Solar power · EPC+F · Opportunity summary")

add(key="cameroon_camtel", section="EPCF", country="Cameroon", model="EPC+F",
    title=N("Cameroon") + " — {{CAMTEL|Telecom Operator}} Mobile Network Expansion",
    sub="2G / 3G / 4G coverage expansion · financing required in three lots · Indian EPC sought",
    A=("THE REQUIREMENT", "{{CAMTEL — state telecom operator|State telecom operator}}", [
        ("Scope:", "  expand 2G / 3G / 4G coverage to regional capitals, counties and university towns"),
        ("Background:", "  programme planned for completion by 2023, left incomplete"),
        ("EPC:", "  Indian EPC required; 75% of supplies (by value) from India"),
        ("Documents:", "  brief note available")],
       "2G · 3G · 4G EXPANSION", "Planned for 2023, left incomplete"),
    B=("FINANCING REQUIRED", "In three lots · about USD 330 Mn in total", [
        ("Lot 1:", "  USD 95 Mn (finalised)"),
        ("Lot 2:", "  USD 152.76 Mn"),
        ("Lot 3:", "  USD 82.24 Mn"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "3 LOTS · USD 330 Mn", "Lot 1 finalised"),
    steps=[("3 lots", "USD 95 / 152.76 / 82.24 Mn"), ("USD 330 Mn", "Total financing"), ("Indian EPC", "75% Indian supplies"),
           ("2G / 3G / 4G", "Network expansion")],
    strip="PROGRAMME SNAPSHOT",
    footer=N("Cameroon") + " — Telecom · EPC+F · Opportunity summary")

add(key="cameroon_sodecoton", section="EPCF", country="Cameroon", model="EPC+F",
    title=N("Cameroon") + " — {{SODECOTON|Cotton Company}} Ginning-Plant Expansion",
    sub="Expansion and modernisation of cotton ginning plants · EPC+F with State guarantee",
    A=("THE REQUIREMENT", "{{11 factories · ~2,500 staff · 85% of revenue from exported fibre|State cotton company}}", [
        ("Requirement:", "  expand 2 plants; replace outdated equipment (~90% of base)"),
        ("Capacity:", "  {{260,000 t (2026E) vs ~400,000 t at peak|below its historic peak}}"),
        ("Counterparty:", "  {{SODECOTON, supervised by the Ministry of Agriculture|state cotton company}}")],
       "EXPAND 2 PLANTS · RENEW EQUIPMENT", "Modernisation and capacity expansion"),
    B=("PROGRAMME & STRUCTURE", "EPC+F · State-guaranteed", [
        ("Programme:", "  3 phases of 200,000 t, 2027–2030 (indicative), to 600,000 t"),
        ("Structure:", "  EPC+F; loan repaid by {{SODECOTON|the company}} under State guarantee"),
        ("Security:", "  sovereign guarantee + collection account over export receipts"),
        ("Asked of EPC:", "  advance guarantee up to 20%, performance 5%, retention 5%")],
       "3 PHASES · 600,000 t BY 2030", "EPC+F with sovereign guarantee"),
    steps=[("2 plants", "Expansion"), ("3 phases", "200,000 t each, 2027–2030"), ("EPC+F", "Sovereign guarantee"),
           ("APG 20% · PPG 5%", "Retention 5%")],
    strip="PROGRAMME SNAPSHOT",
    footer=N("Cameroon") + " — Cotton ginning · EPC+F · Opportunity summary",
    value="Indicative value: EUR 190–230 Mn")

add(key="cameroon_camwater", section="PPP", country="Cameroon", model="", placeholder=True,
    title=N("Cameroon") + " — {{CAMWATER |}}Water Treatment Plant (WTP)",
    sub="EUR 80 Mn project · as of now, details to be added",
    A=("PROJECT SCOPE", "{{CAMWATER — state water utility|State water utility}}", [
        ("Project:", "  water treatment plant (WTP)"), ("Size:", "  EUR 80 Mn"), ("Details:", "  to be added")],
       "EUR 80 Mn · WTP", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"), ("Stage:", "  to be confirmed"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("EUR 80 Mn", "Project size"), ("WTP", "Water treatment plant"), ("TBC", "Structure"), ("TBC", "Stage")],
    strip="PROJECT SNAPSHOT  —  AS OF NOW",
    footer="DRAFT — " + N("Cameroon") + " — Water · Details to be added")

add(key="cameroon_socadel_gas", section="PPP", country="Cameroon", model="", placeholder=True,
    title=N("Cameroon") + " — {{SOCADEL |}}250 MW Gas-Fired Power Plant",
    sub="DRAFT — project details to be added",
    A=("PROJECT SCOPE", "To be confirmed", [
        ("Power:", "  250 MW gas-fired power plant"), ("Counterparty:", "  {{SOCADEL|to be confirmed}}"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"), ("Stage:", "  to be confirmed"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("250 MW", "Gas-fired power plant"), ("TBC", "Structure"), ("TBC", "Stage")],
    strip="PROJECT SNAPSHOT  —  DRAFT",
    footer="DRAFT — " + N("Cameroon") + " — Gas power · Details to be added")

add(key="chad_streetlights", section="PPP", country="Chad", model="",
    title=N("Chad") + " — Solar Street Lighting (7,800 Lights)",
    sub="Solar street lights in two cities · 208 km of roads · MoU signed with the Ministry",
    A=("PROJECT SCOPE", "Installation and maintenance of solar street lights", [
        ("Project:", "  7,800 solar street lights in total"),
        ("Counterparty:", "  {{Ministry of Water and Energy|line ministry}}"),
        ("MoU:", "  signed Feb 2025 for five priority cities"),
        ("This phase:", "  {{Moundou and Abéché|two cities}}, 208 km of roads")],
       "7,800 LIGHTS · 208 km", "Two cities, 208 km of roads"),
    B=("SCOPE BY CITY", "Two cities · USD 8.5 Mn and USD 15.16 Mn", [
        ("{{Moundou|City 1}}:", "  2,847 lights · 73.8 km · USD 8.5 Mn"),
        ("{{Abéché|City 2}}:", "  4,953 lights · 134.5 km · USD 15.16 Mn"),
        ("Lights:", "  Thermos 100 W on main arterials; Atlas 60 W on secondary roads and residential areas"),
        ("Promoter:", "  private promoter with a technical partner")],
       "THERMOS 100 W + ATLAS 60 W", "Main arterials + residential roads"),
    steps=[("7,800", "Solar street lights"), ("208 km", "Road length"), ("2 cities", "Two-city scope")],
    strip="PROJECT SNAPSHOT",
    footer=N("Chad") + " — Solar street lighting · Opportunity summary",
    value="Indicative value: USD 23.74 Mn")

add(key="guinea_roads_wave1", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — {{Simandou 2040 |National }}Roads Programme (Wave 1)",
    sub="17 national roads · about 2,200 km · PPP / EPC+F delivery",
    A=("PROGRAMME SCOPE", "Wave 1 of the national roads programme", [
        ("Roads:", "  17 national roads"),
        ("Length:", "  approximately 2,200 km"),
        ("Programme:", "  {{Simandou 2040|national 2040 infrastructure programme}}, Wave 1")],
       "17 ROADS · ~2,200 KM", "Wave 1 — 17 national roads"),
    B=("STRUCTURE & STAGE", "Delivery model and status", [
        ("Structure:", "  PPP / EPC+F"),
        ("Stage:", "  information pending — road list received"),
        ("Awaited:", "  road-level technical documents")],
       "PPP / EPC+F", "Large road programme, documents awaited"),
    steps=[("17 roads", "In Wave 1"), ("~2,200 km", "Total length"),
           ("PPP / EPC+F", "Delivery model"), ("Documents", "Awaited")],
    strip="PROGRAMME SNAPSHOT  —  ROADS WAVE 1",
    footer=N("Guinea") + " — Roads · PPP / EPC+F · Opportunity summary",
    value="Indicative value: USD 2.5–3.0 Bn")

add(key="guinea_urban_leads", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — {{Simandou 2040 |}}Urban & Infrastructure Leads",
    sub="City development, business district, expressway, irrigation and telecom modernisation leads",
    A=("URBAN & TRANSPORT LEADS", "Pitch-stage opportunities", [
        ("New city:", "  {{Kansonyah city development|new city development}}"),
        ("Business district:", "  {{Camayenne CBD|central business district}}"),
        ("Expressway:", "  {{TACON|national}} expressway, 90 km")],
       "3 URBAN / TRANSPORT LEADS", "City, CBD and 90 km expressway"),
    B=("AGRICULTURE & TELECOM LEADS", "Pitch-stage opportunities", [
        ("Irrigation:", "  irrigated plains of 101,958 ha"),
        ("Telecom:", "  {{MTN Guinea|mobile network}} modernisation"),
        ("Stage:", "  teasers only — no costing, documents or MOUs")],
       "5 LEADS IN TOTAL", "Teaser-stage programme"),
    steps=[("5 leads", "In the programme"), ("90 km", "Expressway"),
           ("101,958 ha", "Irrigated plains"), ("Teaser stage", "Documents to follow")],
    strip="PROGRAMME SNAPSHOT  —  URBAN & INFRASTRUCTURE LEADS",
    footer=N("Guinea") + " — Mixed infrastructure · EPC+F · Opportunity summary",
    value="Indicative value: EUR ~490 Mn (city); USD 100–200 Mn (others)")

add(key="benin_rail_education", section="EPCF", country="Benin", model="EPC+F",
    title=N("Benin") + " — Railway Projects and Education Project",
    sub="Two railway projects and one education project · documents awaited",
    A=("RAILWAY PROJECTS", "Two projects of the same size", [
        ("Scope:", "  2 railway projects"),
        ("Size:", "  two projects of equal size"),
        ("Stage:", "  documents awaited from the project introducer")],
       "2 RAILWAY PROJECTS", "Two railway projects"),
    B=("EDUCATION PROJECT", "Education infrastructure", [
        ("Scope:", "  education infrastructure project"),
        ("Structure:", "  EPC + Finance (EPC+F)"),
        ("Stage:", "  information pending")],
       "EPC+F · EDUCATION", "Education infrastructure project"),
    steps=[("3 projects", "2 rail + 1 education"), ("Rail", "2 projects"),
           ("Education", "1 project"), ("Documents", "Awaited")],
    strip="PROGRAMME SNAPSHOT  —  RAIL & EDUCATION",
    footer=N("Benin") + " — Rail and education · EPC+F · Opportunity summary",
    value="Indicative value: USD 60 Mn (rail)")

add(key="guinea_lng", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — LNG Import Terminal & Gas-Fired Power",
    sub="LNG terminal of 100,000+ cbm with regasification and jetty, plus gas-fired power generation",
    A=("LNG IMPORT TERMINAL", "Storage, regasification and jetty", [
        ("Storage:", "  100,000+ cbm LNG storage"),
        ("Facilities:", "  regasification unit and jetty"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "100,000+ CBM LNG", "LNG terminal with regasification"),
    B=("GAS-FIRED POWER & STAGE", "Power plant and development status", [
        ("Power:", "  gas-fired power plant linked to the terminal"),
        ("Stage:", "  P2 — structuring"),
        ("Next:", "  financing term sheet and project documents")],
       "P2 · STRUCTURING", "Large-scale LNG-to-power project"),
    steps=[("100,000+ cbm", "LNG storage"), ("Regas + jetty", "Terminal facilities"),
           ("Gas power", "Generation"), ("P2", "Structuring stage")],
    strip="PROJECT SNAPSHOT  —  LNG TERMINAL & POWER",
    footer=N("Guinea") + " — Oil & gas and power · EPC+F · Opportunity summary",
    value="Indicative value: USD ~500 Mn+")

add(key="guinea_hydro_solar_tx", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — Hydro, Solar and Transmission Pipeline",
    sub="Large hydro dam, 200 MW solar IPP, 800 km transmission line and a national observatory",
    A=("GENERATION", "Hydro and solar", [
        ("Hydro:", "  large hydro dam"),
        ("Solar:", "  200 MW solar IPP"),
        ("Stage:", "  P2 — early discussions, no studies yet")],
       "HYDRO + 200 MW SOLAR", "Large hydro and 200 MW solar"),
    B=("TRANSMISSION & OBSERVATORY", "Grid and monitoring", [
        ("Transmission:", "  800 km transmission line"),
        ("Observatory:", "  national observatory (scope to be defined)"),
        ("Documents:", "  none available yet")],
       "800 KM TRANSMISSION", "800 km line and observatory"),
    steps=[("4 components", "Hydro · solar · line · observatory"), ("200 MW", "Solar IPP"),
           ("800 km", "Transmission line"), ("P2", "Early stage")],
    strip="PIPELINE SNAPSHOT  —  HYDRO, SOLAR & TRANSMISSION",
    footer=N("Guinea") + " — Power and hydro · EPC+F · Opportunity summary",
    value="Indicative value: dam EUR 500 Mn+; solar USD 200–250 Mn; line USD 300–500 Mn")

add(key="guinea_wte", section="EPCF", country="Guinea", model="EPC+F",
    title=N("Guinea") + " — Waste-to-Energy Plant (1,000–1,200 TPD)",
    sub="Integrated municipal solid waste and waste-to-energy plant",
    A=("PROJECT OVERVIEW", "Asset and capacity", [
        ("Asset:", "  integrated municipal solid waste (MSW) and waste-to-energy plant"),
        ("Capacity:", "  1,000–1,200 tonnes per day (TPD)"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "1,000–1,200 TPD", "Integrated MSW and waste-to-energy"),
    B=("STAGE & NEXT STEPS", "Where the project stands", [
        ("Stage:", "  information pending"),
        ("Partners:", "  technology and waste-treatment partners introduced"),
        ("Next:", "  site visit to a reference plant")],
       "INFORMATION PENDING", "Early stage, partners identified"),
    steps=[("1,000–1,200", "Tonnes per day"), ("MSW + WtE", "Integrated plant"),
           ("EPC+F", "Delivery model"), ("Early", "Partners identified")],
    strip="PROJECT SNAPSHOT  —  WASTE-TO-ENERGY",
    footer=N("Guinea") + " — Waste-to-energy · EPC+F · Opportunity summary")

add(key="sierra_leone_moh", section="EPCF", country="Sierra Leone", model="EPC+F",
    title=N("Sierra Leone") + " — Ministry of Health Programme (9+ projects)",
    sub="Hospitals, cancer centre, emergency services, pharma and health-sector infrastructure",
    A=("HOSPITALS & SERVICES", "Core healthcare infrastructure", [
        ("Hospitals:", "  5 multi-specialty and 3 tertiary hospitals"),
        ("Specialist care:", "  cancer centre"),
        ("Emergency:", "  emergency medical services")],
       "9+ PROJECTS", "Hospitals, cancer centre and EMS"),
    B=("SUPPORTING INFRASTRUCTURE", "Pharma, public health and digital", [
        ("Pharma:", "  warehousing and manufacturing"),
        ("Public health:", "  agency HQ, diagnostics, training, Ministry HQ"),
        ("Stage:", "  pre-feasibility; EOI accepted by the Government")],
       "PRE-FEASIBILITY", "EOI accepted — documentation is the gap"),
    steps=[("9+ projects", "In the programme"), ("8 hospitals", "5 multi-specialty + 3 tertiary"),
           ("Telemedicine", "Pharma · diagnostics"), ("EOI accepted", "Pre-feasibility stage")],
    strip="PROGRAMME SNAPSHOT  —  MINISTRY OF HEALTH PROGRAMME",
    footer=N("Sierra Leone") + " — Healthcare · EPC+F · Opportunity summary",
    value="Indicative value: USD 330 Mn (stated items)")

add(key="gabon_water3", section="EPCF", country="Gabon", model="EPC+F",
    title=N("Gabon") + " — Three Water Projects",
    sub="Three water supply projects · studies to be received",
    A=("WATER SUPPLY PROJECTS", "Three projects in the programme", [
        ("Project 1:", "  {{Mbomo (Libreville)|capital-area project}} — phase 1 about 80% complete"),
        ("Project 2:", "  {{Akanda|second project}} — 5,000 m³/day capacity"),
        ("Project 3:", "  {{Franceville|third project}}")],
       "3 WATER PROJECTS", "Three water supply projects"),
    B=("STAGE & NEXT STEPS", "Where the programme stands", [
        ("Stage:", "  information pending"),
        ("Studies:", "  to be received"),
        ("Next:", "  studies and project documents")],
       "STUDIES AWAITED", "Information pending since first contact"),
    steps=[("3 projects", "Water supply"), ("80%", "Phase 1 progress, project 1"),
           ("5,000 m³/day", "Project 2 capacity"), ("Studies", "To be received")],
    strip="PROGRAMME SNAPSHOT  —  WATER PROJECTS",
    footer=N("Gabon") + " — Water · EPC+F · Opportunity summary",
    value="Indicative value: EUR 211 Mn (3 projects)")

add(key="madagascar_education", section="EPCF", country="Madagascar", model="EPC+F",
    title=N("Madagascar") + " — Education Development Project",
    sub="School infrastructure and kits · 36-month duration",
    A=("PROJECT OVERVIEW", "Scope", [
        ("Scope:", "  school infrastructure and school kits"),
        ("Sector:", "  education"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "EDUCATION · EPC+F", "School infrastructure programme"),
    B=("DURATION & STAGE", "Timeline and status", [
        ("Duration:", "  36 months"),
        ("Stage:", "  information pending"),
        ("Next:", "  project details awaited")],
       "36 MONTHS", "36-month programme"),
    steps=[("Education", "School infrastructure"), ("School kits", "Included in scope"),
           ("36 months", "Project duration"), ("Info pending", "Details awaited")],
    strip="PROJECT SNAPSHOT  —  EDUCATION",
    footer=N("Madagascar") + " — Education · EPC+F · Opportunity summary")

add(key="gabon_libreville_grid", section="EPCF", country="Gabon", model="EPC+F", hold=True,
    title=N("Gabon") + " — {{Greater Libreville |Capital-Area }}Grid Reinforcement",
    sub="New source substations, underground lines and rehabilitation · on hold",
    A=("PROJECT SCOPE", "Grid reinforcement and stabilisation", [
        ("New substations:", "  new source substations"),
        ("Network:", "  underground lines"),
        ("Rehabilitation:", "  rehabilitation of the existing network")],
       "GRID REINFORCEMENT", "Reinforcement and stabilisation"),
    B=("STAGE & PRIORITY", "Status", [
        ("Priority:", "  named as a government priority"),
        ("Stage:", "  on hold"),
        ("Studies:", "  to be received")],
       "ON HOLD", "Government priority — studies awaited"),
    steps=[("Substations", "New source stations"), ("Underground", "Lines"),
           ("Rehabilitation", "Existing network"), ("On hold", "Studies awaited")],
    strip="PROJECT SNAPSHOT  —  GRID REINFORCEMENT",
    footer=N("Gabon") + " — Power distribution · EPC+F · Opportunity summary",
    value="Indicative value: EUR 136.48 Mn")

add(key="gabon_grid8", section="EPCF", country="Gabon", model="EPC+F", hold=True,
    title=N("Gabon") + " — Eight Grid & Energy Projects",
    sub="Transmission, interconnection, solar, storage and street lighting · studies available, to be received",
    A=("GRID & TRANSMISSION", "Lines and interconnection", [
        ("Lines:", "  {{Oyem–Mitzic line|regional line}}; {{Mayumba–Tchibanga|regional}} 225 kV"),
        ("Interconnection:", "  {{C2M|regional}} interconnection; {{Ntoum–Cocobeach|regional line}}"),
        ("Waste-to-energy:", "  waste-to-energy plant")],
       "GRID · 225 KV · WTE", "Grid, interconnection and WtE"),
    B=("GENERATION, STORAGE & LIGHTING", "Solar, storage and street lighting", [
        ("Solar:", "  {{Makokou|regional}} 7 MW solar plant"),
        ("Storage:", "  5 storage plants"),
        ("Lighting:", "  50,000 solar streetlights")],
       "7 MW SOLAR · 5 STORAGE", "Solar, storage and streetlights"),
    steps=[("8 projects", "Grid and energy"), ("225 kV", "Transmission"),
           ("5 storage plants", "Plus 7 MW solar"), ("50,000", "Solar streetlights")],
    strip="PROGRAMME SNAPSHOT  —  EIGHT GRID & ENERGY PROJECTS",
    footer=N("Gabon") + " — Grid and energy · EPC+F · Opportunity summary",
    value="Indicative value: EUR ~383 Mn (8 projects)")

add(key="gabon_roads_airport", section="EPCF", country="Gabon", model="EPC+F", placeholder=True,
    title=N("Gabon") + " — Four Road Projects and an Airport Runway",
    sub="DRAFT — project details to be added",
    A=("PROJECT SCOPE", "To be confirmed", [
        ("Roads:", "  four road projects"),
        ("Airport:", "  airport runway"),
        ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"),
        ("Stage:", "  to be confirmed"),
        ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("4 roads", "Road projects"), ("1 runway", "Airport"), ("TBC", "Structure"), ("TBC", "Stage")],
    strip="PROJECT SNAPSHOT  —  DRAFT",
    footer="DRAFT — " + N("Gabon") + " — Roads and airport · Details to be added")

add(key="guinea_port", section="EPCF", country="Guinea", model="EPC+F", hold=True,
    title=N("Guinea") + " — Port De-Congestion & Fisheries Port",
    sub="{{Conakry port|Capital port}} upgrade and a fisheries port with processing zone · on hold",
    A=("PORT DE-CONGESTION", "Upgrade of the main port", [
        ("Scope:", "  {{Conakry port|capital port}} upgrade and de-congestion"),
        ("Stage:", "  on hold"),
        ("Details:", "  to be confirmed")],
       "PORT UPGRADE", "Port de-congestion project"),
    B=("FISHERIES PORT", "Fisheries port and processing zone", [
        ("Scope:", "  fisheries port with cold storage"),
        ("Zone:", "  fisheries processing zone"),
        ("Stage:", "  on hold, no information")],
       "FISHERIES + COLD STORAGE", "Fisheries port and processing zone"),
    steps=[("2 projects", "Port + fisheries"), ("Port upgrade", "De-congestion"),
           ("Cold storage", "Fisheries port"), ("On hold", "Current status")],
    strip="PROJECT SNAPSHOT  —  PORT & FISHERIES",
    footer=N("Guinea") + " — Ports · EPC+F · Opportunity summary",
    value="Indicative value: USD 100–200 Mn (port)")

add(key="burkina_fertiliser", section="EPCF", country="Burkina Faso", model="EPC+F", placeholder=True,
    title=N("Burkina Faso") + " — Fertiliser Plant & Agriculture Warehouse",
    sub="DRAFT — project details to be added",
    A=("PROJECT SCOPE", "To be confirmed", [
        ("Plant:", "  fertiliser plant"), ("Storage:", "  agriculture warehouse"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"), ("Stage:", "  to be confirmed"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("Fertiliser", "Plant"), ("Warehouse", "Agriculture storage"), ("TBC", "Structure"), ("TBC", "Stage")],
    strip="PROJECT SNAPSHOT  —  DRAFT",
    footer="DRAFT — " + N("Burkina Faso") + " — Agriculture · Details to be added")

add(key="burkina_gas_hfo", section="EPCF", country="Burkina Faso", model="EPC+F", placeholder=True,
    title=N("Burkina Faso") + " — 200 km Gas Pipeline and 100 MW HFO Plant",
    sub="DRAFT — project details to be added",
    A=("PROJECT SCOPE", "To be confirmed", [
        ("Pipeline:", "  200 km gas pipeline"), ("Power:", "  100 MW HFO plant"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"), ("Stage:", "  to be confirmed"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("200 km", "Gas pipeline"), ("100 MW", "HFO plant"), ("TBC", "Structure"), ("TBC", "Stage")],
    strip="PROJECT SNAPSHOT  —  DRAFT",
    footer="DRAFT — " + N("Burkina Faso") + " — Gas and power · Details to be added")

add(key="niger_tanks", section="EPCF", country="Niger", model="EPC+F", placeholder=True,
    title=N("Niger") + " — Six Fuel Tank Farms",
    sub="DRAFT — project details to be added",
    A=("PROJECT SCOPE", "To be confirmed", [
        ("Facilities:", "  six fuel tank farms"), ("Sector:", "  oil and gas storage"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"), ("Stage:", "  to be confirmed"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("6 tank farms", "Fuel storage"), ("TBC", "Capacity"), ("TBC", "Structure"), ("TBC", "Stage")],
    strip="PROJECT SNAPSHOT  —  DRAFT",
    footer="DRAFT — " + N("Niger") + " — Fuel storage · Details to be added")

add(key="botswana_ghanzi_solar", section="EPCF", country="Botswana", model="EPC+F", hold=True,
    title=N("Botswana") + " — 15 MW Solar Plant{{, Ghanzi|}}",
    sub="Utility-scale solar PV · EPC+F · on hold",
    A=("PROJECT OVERVIEW", "Asset and structure", [
        ("Capacity:", "  15 MW solar plant"),
        ("Location:", "  {{Ghanzi|regional site}}"),
        ("Structure:", "  EPC + Finance (EPC+F)")],
       "15 MW SOLAR PV", "15 MW solar plant"),
    B=("STAGE", "Where the project stands", [
        ("Stage:", "  on hold"),
        ("Value:", "  to be confirmed"),
        ("Details:", "  to be confirmed")],
       "ON HOLD", "On hold"),
    steps=[("15 MW", "Installed capacity"), ("Solar PV", "Technology"),
           ("EPC+F", "Delivery model"), ("On hold", "Current status")],
    strip="PROJECT SNAPSHOT  —  15 MW SOLAR",
    footer=N("Botswana") + " — Solar power · EPC+F · Opportunity summary")

# ============================================================================ PPP-annuity section
add(key="gabon_floating_solar", section="PPP", country="Gabon", model="PPP Annuity",
    title=N("Gabon") + " — 38.4 MW Floating Solar + 40 MW BESS",
    sub="Turnkey EPC · five floating solar sites within 4 km · evacuation point 400 m away",
    A=("PROJECT SCOPE", "Floating solar and storage", [
        ("Floating solar:", "  38.4 MW across 5 sites within a 4 km radius"),
        ("Storage:", "  40 MW battery energy storage (BESS)"),
        ("Grid:", "  evacuation point 400 m from the site")],
       "38.4 MW + 40 MW BESS", "5 floating solar sites + BESS"),
    B=("COMMERCIAL TERMS & STAGE", "Payment and development status", [
        ("Payment:", "  30% advance, 70% against milestones"),
        ("Financing:", "  bank finances the project company (SPV)"),
        ("Stage:", "  key studies done; PPA signed by the SPV")],
       "TURNKEY EPC · SPV FINANCED", "Key studies done, PPA signed by the SPV"),
    steps=[("38.4 MW", "Floating solar, 5 sites"), ("40 MW", "BESS"),
           ("30 / 70", "Advance / milestones"), ("PPA signed", "By the SPV")],
    strip="PROJECT SNAPSHOT  —  FLOATING SOLAR + BESS",
    footer=N("Gabon") + " — Solar and storage · PPP Annuity · Opportunity summary")

add(key="sierra_leone_hospitals", section="PPP", country="Sierra Leone", model="PPP Annuity",
    title=N("Sierra Leone") + " — VIP Hospital and Two Primary Care Hospitals",
    sub="1 × 100-bed hospital and 2 × 50-bed primary care hospitals · secured government payment obligations",
    A=("PROJECT SCOPE", "Three hospitals", [
        ("VIP hospital:", "  100 beds{{ (Freetown)|}}"),
        ("Primary care:", "  2 hospitals of 50 beds each"),
        ("Total:", "  200 beds across 3 facilities")],
       "100 + 50 + 50 BEDS", "Three hospitals, 200 beds"),
    B=("STRUCTURE & STAGE", "PPP structure and status", [
        ("Structure:", "  PPP / EPCF-annuity with secured government payment obligations"),
        ("Proposed split:", "  50:50 structure"),
        ("Stage:", "  P2 — pre-feasibility; concept note available")],
       "PPP · ANNUITY · P2", "Secured payment obligations"),
    steps=[("3 hospitals", "1 VIP + 2 primary care"), ("200 beds", "Total capacity"),
           ("PPP annuity", "Payment structure"), ("P2", "Pre-feasibility")],
    strip="PROJECT SNAPSHOT  —  HOSPITALS",
    footer=N("Sierra Leone") + " — Healthcare · PPP Annuity · Opportunity summary",
    value="Indicative value: USD 50 Mn (35 + 15)")

add(key="cameroon_roads", section="PPP", country="Cameroon", model="PPP Annuity",
    title=N("Cameroon") + " — Road Infrastructure (83 projects, 3 cities)",
    sub="About 110 km of urban roads across three cities · feasibility study submitted",
    A=("URBAN ROAD PROGRAMME", "83 projects in three cities", [
        ("City 1:", "  {{Douala|first city}} — 37.3 km (27 projects)"),
        ("City 2:", "  {{Yaoundé|second city}} — 53.7 km (52 projects, incl. a ~36 km corridor)"),
        ("City 3:", "  {{Maroua|third city}} — 19.0 km (4 projects)")],
       "~110 KM · 83 PROJECTS", "Three-city urban road programme"),
    B=("STAGE & NEXT STEPS", "Where the programme stands", [
        ("Feasibility:", "  study submitted (March 2025)"),
        ("Stage:", "  awaiting funding decision"),
        ("Engagement:", "  Ministry and Presidency met; LOI submitted")],
       "FEASIBILITY SUBMITTED", "Awaiting funding decision"),
    steps=[("83 projects", "Across 3 cities"), ("~110 km", "Total road length"),
           ("Feasibility", "Study submitted"), ("Funding", "Decision awaited")],
    strip="PROGRAMME SNAPSHOT  —  URBAN ROADS",
    footer=N("Cameroon") + " — Roads · PPP Annuity · Opportunity summary",
    value="Indicative value: USD ~1,239 Mn")

add(key="benin_solar", section="PPP", country="Benin", model="PPP Annuity",
    title=N("Benin") + " — 25 MW Solar + 5 MW BESS",
    sub="Solar PV with battery storage · BOT · long-term PPA with agreed tariff",
    A=("PROJECT OVERVIEW", "Asset and structure", [
        ("Solar:", "  25 MW solar PV plant"),
        ("Storage:", "  5 MW battery energy storage (BESS)"),
        ("Structure:", "  BOT (build–operate–transfer)")],
       "25 MW SOLAR + 5 MW BESS", "25 MW solar with 5 MW BESS"),
    B=("TARIFF & PPA", "Commercial terms", [
        ("PPA term:", "  45 years"),
        ("Tariff:", "  USD 6.8 cents per kWh"),
        ("Stage:", "  initial — EPC offers awaited")],
       "45-YEAR PPA · 6.8 c/kWh", "Tariff and PPA tenor agreed"),
    steps=[("25 MW", "Solar PV"), ("5 MW", "BESS"), ("45 years", "PPA term"), ("6.8 c/kWh", "Agreed tariff")],
    strip="PROJECT SNAPSHOT  —  25 MW SOLAR + BESS",
    footer=N("Benin") + " — Solar and storage · BOT · Opportunity summary",
    value="Indicative value: USD 19 Mn")

add(key="tanzania_gold_mine", section="PPP", country="Tanzania", model="PPP Annuity",
    title=N("Tanzania") + " — {{Kiabakari |}}Gold Mine",
    sub="Active open-pit producing gold asset · licence valid to October 2028",
    A=("ASSET OVERVIEW", "Producing asset", [
        ("Asset:", "  active open-pit gold mine in production"),
        ("Location:", "  {{Mara region, 30–40 km south of Musoma|regional mining area}}"),
        ("Licence:", "  valid to October 2028")],
       "OPEN-PIT · PRODUCING", "Producing open-pit gold asset"),
    B=("STAGE & NEXT STEPS", "Where the project stands", [
        ("Stage:", "  information pending"),
        ("Next:", "  teaser to be prepared"),
        ("To confirm:", "  owner, reserves and licence details")],
       "INFORMATION PENDING", "Owner and reserves to be confirmed"),
    steps=[("Open-pit", "Gold mine"), ("Producing", "Active operation"),
           ("Oct 2028", "Licence validity"), ("Teaser", "Next step")],
    strip="PROJECT SNAPSHOT  —  GOLD MINE",
    footer=N("Tanzania") + " — Mining · Opportunity summary")

add(key="togo_solar50", section="PPP", country="Togo", model="PPP Annuity",
    title=N("Togo") + " — 50 MW Solar Power Plant",
    sub="Utility-scale solar PV · LOI submitted",
    A=("PROJECT OVERVIEW", "Asset", [
        ("Capacity:", "  50 MW solar PV plant"),
        ("Technology:", "  solar photovoltaic"),
        ("Stage:", "  LOI submitted")],
       "50 MW SOLAR PV", "50 MW solar power plant"),
    B=("STAGE & NEXT STEPS", "Where the project stands", [
        ("LOI:", "  submitted"),
        ("Value:", "  to be confirmed"),
        ("Next:", "  further project details")],
       "LOI SUBMITTED", "LOI in, details to follow"),
    steps=[("50 MW", "Installed capacity"), ("Solar PV", "Technology"),
           ("LOI", "Submitted"), ("Details", "To follow")],
    strip="PROJECT SNAPSHOT  —  50 MW SOLAR",
    footer=N("Togo") + " — Solar power · PPP · Opportunity summary")

add(key="burkina_hfo4", section="PPP", country="Burkina Faso", model="PPP Annuity",
    title=N("Burkina Faso") + " — HFO Power Plants (4 sites)",
    sub="Four HFO plants of 25–40 MW · PPP · pre-feasibility available",
    A=("PLANT PORTFOLIO", "Four HFO sites", [
        ("Site 1:", "  {{40 MW — Dedougou|40 MW}}"),
        ("Site 2:", "  {{25 MW — Manga|25 MW}}"),
        ("Sites 3 and 4:", "  {{25 MW each — Banfora and Gaoua|25 MW each}}")],
       "4 SITES · 115 MW", "Four HFO plants, 115 MW in total"),
    B=("STRUCTURE & STAGE", "PPP structure and status", [
        ("Structure:", "  PPP"),
        ("Pre-feasibility:", "  available"),
        ("Stage:", "  initial; partnership agreements pending")],
       "PPP · INITIAL STAGE", "Pre-feasibility available"),
    steps=[("4 sites", "HFO plants"), ("115 MW", "Total capacity"),
           ("PPP", "Delivery model"), ("Initial", "Development stage")],
    strip="PORTFOLIO SNAPSHOT  —  HFO PLANTS",
    footer=N("Burkina Faso") + " — HFO power generation · PPP · Opportunity summary")

add(key="togo_ccgt_lng", section="PPP", country="Togo", model="PPP Annuity",
    title=N("Togo") + " — 500 MW CCGT + LNG Regasification Platform",
    sub="500 MW combined-cycle plant with gas pipeline and 330 kV link · 25-year concession",
    A=("POWER PLANT", "500 MW combined-cycle gas turbine", [
        ("Capacity:", "  500 MW CCGT (about 4,200 GWh per year)"),
        ("Gas supply:", "  30 km gas pipeline"),
        ("Grid:", "  330 kV connection")],
       "500 MW CCGT", "500 MW combined-cycle plant"),
    B=("LNG & CONCESSION", "Gas supply and contract model", [
        ("LNG:", "  regasification platform to diversify gas supply"),
        ("Concession:", "  25 years"),
        ("Stage:", "  initial; details awaited")],
       "25-YEAR CONCESSION", "CCGT with LNG regasification"),
    steps=[("500 MW", "CCGT"), ("30 km", "Gas pipeline"), ("330 kV", "Grid link"), ("25 years", "Concession")],
    strip="PROJECT SNAPSHOT  —  500 MW CCGT + LNG",
    footer=N("Togo") + " — Gas-fired power and LNG · PPP · Opportunity summary",
    value="Indicative value: USD 550 Mn (CCGT); LNG to be confirmed")

add(key="cameroon_power", section="PPP", country="Cameroon", model="PPP Annuity",
    title=N("Cameroon") + " — Power Pipeline (CCGT, Barge, Solar + BESS)",
    sub="Two 150 MW gas plants and a 200 MWp solar + 100 MW BESS project · timelines 2026–2029",
    A=("GAS-FIRED POWER", "Two 150 MW plants", [
        ("CCGT:", "  150 MW, {{Far North|northern region}}"),
        ("Barge CCGT:", "  150 MW, {{Douala|coastal city}}; injects into the 90 kV network"),
        ("Timeline:", "  barge plant 2026 Q2 to 2027")],
       "2 × 150 MW GAS-FIRED", "300 MW of gas-fired generation"),
    B=("SOLAR + BESS", "Solar and storage", [
        ("Solar:", "  200 MWp solar PV"),
        ("Storage:", "  100 MW BESS"),
        ("Timeline:", "  2027–2029, {{centre region|central region}}")],
       "200 MWp + 100 MW BESS", "Solar and storage 2027–2029"),
    steps=[("3 projects", "Power pipeline"), ("300 MW", "Gas-fired"),
           ("200 MWp", "Solar PV"), ("100 MW", "BESS")],
    strip="PIPELINE SNAPSHOT  —  POWER",
    footer=N("Cameroon") + " — Power generation · PPP · Opportunity summary")

add(key="botswana_pipeline", section="PPP", country="Botswana", model="PPP Annuity",
    title=N("Botswana") + " — Solar, Transmission and Mining Pipeline",
    sub="Large solar programmes, unawarded transmission lines and mining opportunities",
    A=("SOLAR PROGRAMMES", "{{BPC solar — national utility|National utility solar}}", [
        ("Solar:", "  200 MW and 30 + 500 MW programmes"),
        ("Offtaker:", "  {{Botswana Power Corporation|national utility}}"),
        ("Stage:", "  initial")],
       "200 MW · 30 + 500 MW SOLAR", "Large solar programmes"),
    B=("TRANSMISSION & MINING", "Further opportunities", [
        ("Transmission:", "  unawarded transmission lines"),
        ("Mining:", "  gold and copper"),
        ("Stage:", "  information pending")],
       "TRANSMISSION + MINING", "Pipeline of further opportunities"),
    steps=[("Solar", "200 MW; 30 + 500 MW"), ("Transmission", "Unawarded lines"),
           ("Mining", "Gold and copper"), ("Initial", "Development stage")],
    strip="PIPELINE SNAPSHOT  —  SOLAR, TRANSMISSION & MINING",
    footer=N("Botswana") + " — Energy and mining · PPP · Opportunity summary")

add(key="tanzania_gold4", section="PPP", country="Tanzania", model="PPP Annuity", hold=True,
    title=N("Tanzania") + " — Four Gold Mining Projects",
    sub="Develop and finance four exploration-stage gold licences · on hold",
    A=("PROJECT PORTFOLIO", "Four gold licences", [
        ("Projects:", "  four gold projects"),
        ("Licences:", "  exploration stage"),
        ("Scope:", "  develop and finance")],
       "4 GOLD PROJECTS", "Four exploration-stage gold projects"),
    B=("STAGE", "Where the portfolio stands", [
        ("Stage:", "  moved to hold"),
        ("Status:", "  awaiting feedback from the project introducer"),
        ("Value:", "  to be confirmed")],
       "ON HOLD", "On hold — no feedback"),
    steps=[("4 projects", "Gold mining"), ("Exploration", "Licence stage"),
           ("Develop + finance", "Scope"), ("On hold", "Current status")],
    strip="PORTFOLIO SNAPSHOT  —  GOLD MINING",
    footer=N("Tanzania") + " — Mining · Opportunity summary")

add(key="tanzania_gas1000", section="PPP", country="Tanzania", model="PPP Annuity", hold=True,
    title=N("Tanzania") + " — 1,000 MW Gas-to-Power",
    sub="Large thermal power opportunity · on hold",
    A=("PROJECT OVERVIEW", "Asset", [
        ("Capacity:", "  1,000 MW gas-to-power"),
        ("Sector:", "  thermal power generation"),
        ("Details:", "  location and further details not yet available")],
       "1,000 MW GAS-TO-POWER", "1,000 MW thermal power"),
    B=("STAGE", "Where the project stands", [
        ("Stage:", "  on hold"),
        ("Developers:", "  several developer / EPC groups have shown interest"),
        ("Next:", "  location and project details")],
       "ON HOLD", "On hold — details awaited"),
    steps=[("1,000 MW", "Gas-to-power"), ("Thermal", "Technology"),
           ("TBC", "Location"), ("On hold", "Current status")],
    strip="PROJECT SNAPSHOT  —  1,000 MW GAS-TO-POWER",
    footer=N("Tanzania") + " — Gas-fired power · Opportunity summary")

add(key="tanzania_bahi_dodoma", section="PPP", country="Tanzania", model="PPP Annuity", hold=True,
    title=N("Tanzania") + " — {{Bahi–Dodoma |}}Water Pipeline (110 km)",
    sub="110 km pipeline linked to a dam and 128,000 m³/day water treatment plant under construction",
    A=("PROJECT SCOPE", "Pipeline and linked works", [
        ("Pipeline:", "  110 km"),
        ("Dam:", "  {{AfDB-funded|multilateral-funded}} dam under construction"),
        ("Treatment:", "  128,000 m³/day water treatment plant under construction")],
       "110 KM PIPELINE", "110 km water pipeline"),
    B=("STAGE", "Where the project stands", [
        ("Stage:", "  asked to hold; information pending"),
        ("Studies:", "  feasibility study and land acquisition under way"),
        ("Outlook:", "  could become a priority after the feasibility study")],
       "ON HOLD", "On hold — feasibility under way"),
    steps=[("110 km", "Pipeline"), ("128,000 m³/day", "Treatment plant"),
           ("Dam", "Under construction"), ("On hold", "Feasibility under way")],
    strip="PROJECT SNAPSHOT  —  WATER PIPELINE",
    footer=N("Tanzania") + " — Water · Opportunity summary",
    value="Indicative value: USD 150 Mn")

add(key="tanzania_wind100", section="PPP", country="Tanzania", model="PPP Annuity", hold=True,
    title=N("Tanzania") + " — 100 MW Wind IPP",
    sub="Independent power producer wind project · data room available · on hold",
    A=("PROJECT OVERVIEW", "Asset and model", [
        ("Capacity:", "  100 MW wind"),
        ("Model:", "  independent power producer (IPP)"),
        ("Data room:", "  received")],
       "100 MW WIND IPP", "100 MW wind power"),
    B=("STAGE", "Where the project stands", [
        ("Stage:", "  on hold"),
        ("Data room:", "  available"),
        ("Value:", "  to be confirmed")],
       "ON HOLD", "On hold"),
    steps=[("100 MW", "Wind capacity"), ("IPP", "Delivery model"),
           ("Data room", "Received"), ("On hold", "Current status")],
    strip="PROJECT SNAPSHOT  —  100 MW WIND",
    footer=N("Tanzania") + " — Wind power · IPP · Opportunity summary")

# ============================================================================ EPC section
add(key="tanzania_tx_hospital_solar", section="EPC", country="Tanzania", model="EPC",
    title=N("Tanzania") + " — Transmission Line, Hospital and Small Solar Leads",
    sub="Early leads: a transmission line, a hospital and a 100–200 MW small solar portfolio",
    A=("TRANSMISSION & HOSPITAL", "Early leads", [
        ("Transmission:", "  transmission line project"),
        ("Hospital:", "  hospital project"),
        ("Stage:", "  information pending")],
       "2 EARLY LEADS", "Transmission line and hospital"),
    B=("SMALL SOLAR PORTFOLIO", "Aggregation opportunity", [
        ("Portfolio:", "  100–200 MW of small solar projects"),
        ("Approach:", "  aggregation of existing small-project holders"),
        ("Data:", "  awaited")],
       "100–200 MW SOLAR", "Small solar aggregation"),
    steps=[("3 leads", "Early stage"), ("Transmission", "Line project"),
           ("Hospital", "Healthcare"), ("100–200 MW", "Small solar")],
    strip="LEADS SNAPSHOT  —  TRANSMISSION, HOSPITAL & SOLAR",
    footer=N("Tanzania") + " — Mixed leads · EPC · Opportunity summary")

add(key="tanzania_port_leads", section="EPC", country="Tanzania", model="EPC", placeholder=True,
    title=N("Tanzania") + " — Port, Metering, Housing, Streetlight and Rail Leads",
    sub="DRAFT — project details to be added",
    A=("LEADS", "To be confirmed", [
        ("Port:", "  port project"), ("Utilities:", "  metering and streetlight projects"),
        ("Other:", "  housing and rail projects")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    B=("STRUCTURE & STAGE", "To be confirmed", [
        ("Structure:", "  to be confirmed"), ("Stage:", "  to be confirmed"), ("Details:", "  to be added")],
       "DETAILS TO BE ADDED", "Draft slide — details to follow"),
    steps=[("Port", "Lead"), ("Metering · streetlight", "Leads"), ("Housing · rail", "Leads"), ("TBC", "Stage")],
    strip="LEADS SNAPSHOT  —  DRAFT",
    footer="DRAFT — " + N("Tanzania") + " — Mixed leads · Details to be added")

AFTER = {"EPCF": EPCF_AFTER, "PPP": PPP_AFTER, "EPC": EPC_AFTER}
