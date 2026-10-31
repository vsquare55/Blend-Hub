# -*- coding: utf-8 -*-
"""
Source / origination of each project in the base deck, read from 'BIP - Captive Projects.xlsx'
(column 'Partner Who Introduced' / 'Name of Local Partner' / 'Developer & Local Partner' / 'Sponsor', plus notes).

RULES USED
 * Only a person / minister / partner who actually INTRODUCED or ORIGINATED the project is recorded.
 * Counterparties (ministries, utilities, SOEs) are NOT sources, and neither is your internal team (RM / ESF / Innovus names).
 * Where the workbook says nothing, the source is left BLANK (an uncertain match is mentioned in 'Source Notes' only).
 * Several sources are separated by ' / '.
"""

# key -> (source(s), evidence / notes)
SEED = {
    # ---- Togo (sheet TOGO, 'Partner Who Introduced' = Anil (RAMCO); local partner list: Anil Vora - Ramco)
    "togo_161kv": ("Anil Vora (RAMCO)", "Sheet TOGO, 'Partner Who Introduced': Anil (RAMCO). Counterparty: Ministry of Energy & Mineral Resources."),
    "togo_bess": ("Anil Vora (RAMCO)", "Sheet TOGO, 'Partner Who Introduced': Anil (RAMCO)."),
    "togo_gas": ("Anil Vora (RAMCO)", "Sheet TOGO, 'Partner Who Introduced': Anil (RAMCO)."),
    "togo_ccgt_lng": ("Anil Vora (RAMCO)", "Sheet TOGO, 500 MW CCGT and LNG Regasification rows: Anil (RAMCO)."),
    # ---- Cameroon
    "cameroon_airports": ("Nexus Capital", "Sheet CAMEROON: Kribi / Bertoua / Tiko airports introduced by Nexus Capital (counterparty CCAA). "
                                           "Matched to this 3-airport project - please confirm."),
    "cameroon_solar_500": ("Hamadama", "Sheet CAMEROON, SOCADEL 500 MW Solar: introduced by Hamadama."),
    "cameroon_refinery": ("Hamadama", "Sheet CAMEROON, SONARA Refinery Rehabilitation: introduced by Hamadama."),
    "cameroon_camtel": ("Steve / Hamadama", "Sheet CAMEROON: CAMTEL programme introduced by Steve; SODECOTON introduced by Hamadama."),
    "cameroon_power": ("Hamadama", "Sheet CAMEROON: 150 MW CCGT (Far North), barge CCGT (Douala) and Solar + BESS introduced by Hamadama."),
    "cameroon_roads": ("KT&Co", "Sheet 'Cameroon Road 3 Cities': sponsor KT&CO.; sponsor has already met the Ministry and the Presidency."),
    # ---- Gabon (sheet GABON, 'Partner Who Introduced')
    "gabon_water3": ("Virgil", "Sheet GABON: Mbomo, Akanda and Franceville water projects introduced by Virgil (son of the Minister of Energy)."),
    "gabon_libreville_grid": ("Virgil", "Sheet GABON: Greater Libreville grid strengthening introduced by Virgil; he confirmed it is a Government priority."),
    "gabon_grid8": ("Virgil", "Sheet GABON: the eight grid / energy items introduced by Virgil (floating solar by Arm, connected by Virgil)."),
    "gabon_floating_solar": ("Arm", "Sheet GABON, 40 MW Floating Solar: introduced by Arm - 'connected by Virgil'."),
    "gabon_roads_airport": ("Walter / Yann", "Sheet GABON: 4 road projects 'expected from Yann' and airport runway; introduced by Walter / Yann."),
    # ---- Guinea (sheet Guinea / GUINEA CONAKRY 3)
    "guinea_health": ("Minister Sylla", "Sheet Guinea, 'Partner Who Introduced': Sylla Minister (Ministry of Health programme)."),
    "guinea_roads_wave1": ("Roshan (Topaz)", "Sheet Guinea, Simandou 2040 Wave 1 roads: introduced by Roshan (Topaz)."),
    "guinea_port": ("Roshan (Topaz)", "Sheet Guinea, Port De-Congestion and Fisheries Port: introduced by Roshan (Topaz)."),
    "guinea_wte": ("Roshan (Topaz)", "Sheet Guinea, Waste to Energy: introduced by Roshan (Topaz)."),
    "guinea_lng": ("Bashir Kamara (MAHH)", "Sheet Guinea: hydrocarbon / LNG terminals introduced by Bachir; notes: Bashir Kamara (MAHH) is personally driving this."),
    "guinea_hydro_solar_tx": ("Topaz Group", "Sheet GUINEA CONAKRY 3: dam, 200 MW solar, 800 km line and observatory led by Topaz (developer advocate)."),
    "guinea_urban_leads": ("Hamere Consultant", "Sheet Guinea: TACON expressway, Kansonyah city and Camayenne CBD introduced by Hamere Consultant."),
    # ---- Burkina Faso (sheet Burkina Faso 'Name of Local Partner' / JT - BURKINA FASO 'Developer & Local Partner')
    "burkina_storage": ("Oscar Daga (DK Group)", "Sheet Burkina Faso: 100,000 m3 hydrocarbon depot (SONABHY) - local partner Oscar Daga (DK Groupe)."),
    "burkina_bassinko": ("Oscar Daga (DK Group) / Ahmed Fofana", "Corrected by user: source is Oscar Daga (DK Group) together with Ahmed Fofana."),
    "burkina_fertiliser": ("Oscar Daga (DK Group)", "Sheet JT - BURKINA FASO: fertiliser blending plant and agriculture warehouse (SOBIMAP) - DK Group."),
    "burkina_gas_hfo": ("Oscar Daga (DK Group) / Ahmed Fofana", "Sheet JT - BURKINA FASO: 200 km gas pipeline - DK Group; 100 MW HFO plant (Bobo) - Ahmed Fofana."),
    "burkina_hfo": ("Souleymen Ildo (Ildo Oil)", "Sheets Burkina Faso / JT - BURKINA FASO: 50 MW HFO plant - local partner Souleymen Ildo (Ildo Oil)."),
    "burkina_hfo4": ("Oscar Daga (DK Group) / Ahmed Fofana", "Corrected by user: source is Oscar Daga (DK Group) together with Ahmed Fofana."),
    "burkina_solar100": ("Souleymen Ildo (Ildo Oil)", "Sheet JT - BURKINA FASO: 100 MW solar - developer & local partner 'Varaha + Ildo Oil'."),
    # ---- Benin / Liberia / Sierra Leone
    "benin_rail_education": ("CDCB (Edmond) / Planet One", "Sheet BENIN: railway projects introduced by CDCB - Edmond; education project introduced by Planet One."),
    "benin_solar": ("Zener Group (Zeneer)", "Sheet BENIN: 25 MW solar + 5 MW BESS introduced by Zeneer (Zener Group)."),
    "liberia_hospital": ("Anatole", "Sheet OTHERS_: John F Kennedy Hospital - local partner Anatole (Cameroon Consulate in Togo, introduced by Ferdinand); survey report from UHG."),
    "sierra_leone_moh": ("UHG", "Sheets SIERRA LEONE / JT - SIERRA LEONE: Ministry of Health programme items - local partner UHG."),
    "sierra_leone_hospitals": ("UHG", "Sheet SIERRA LEONE, 'Partner Who Introduced': UHG - EPC partner."),
    # ---- Tanzania (sheet TANZANIA / Tanzania - JT, 'Partner Who Introduced')
    "tanzania_solar_100": ("Boma / Renata", "Sheet TANZANIA, 100 MW Solar (TANESCO): introduced by Boma / Renata."),
    "tanzania_wind100": ("Renata", "Sheet TANZANIA, 100 MW Wind: introduced by Renata."),
    "tanzania_gas1000": ("Japhet", "Sheet TANZANIA, Gas to Power (1000 MW): introduced by Japhet."),
    "tanzania_geo": ("Japhet", "Sheet TANZANIA, 60 MW / 70 MW Kiejo-Mbaka Geothermal: introduced by Japhet."),
    "tanzania_gold_mine": ("Mohsin Patel", "Sheet TANZANIA, Kiabakari Gold Mine: introduced by Mohsin Patel."),
    "tanzania_gold4": ("Boma", "Sheet TANZANIA, Nyankuru-Nyangoto / Misungwi / Iseni-Lwamgasa / 6PML gold projects: introduced by BOMA."),
    "tanzania_roads": ("Mohsin Patel / Juma (PPP Unit)", "Sheet TANZANIA: Ministry of Works road corridors introduced by Mohsin Patel; two roads also by Juma (PPP Unit)."),
    "tanzania_wtp": ("Mohsin Patel", "Sheet TANZANIA, Ruvu Water Treatment Plant Expansion: introduced by Mohsin Patel."),
    "tanzania_rufiji": ("Mohsin Patel", "Sheet TANZANIA, Rufiji-Dar-Lindi Water Pipeline: introduced by Mohsin Patel."),
    "tanzania_bahi_dodoma": ("Mohsin Patel", "Sheet TANZANIA, Bahi-Dodoma Pipeline: introduced by Mohsin Patel."),
    "icc_convention": ("Boma", "Sheet TANZANIA, International Convention Centre (Zanzibar): introduced by BOMA."),
    "tanzania_tx_hospital_solar": ("Abdul", "Sheet TANZANIA: transmission line introduced by Abdul."),
    "tanzania_port_leads": ("Delina / Boma / Mohsin Patel", "Sheet TANZANIA: streetlight, housing, Zanzibar port - Delina; smart meters - Boma / Delina; railway - Mohsin Patel."),
    # ---- DRC
    "drc_rural": ("Michael", "Sheet DRC: all five rural-development projects introduced by Michael (Ministry of Rural Development countersigned the EOI)."),
}

# deliberately blank (nothing, or nothing certain, in the workbook) - a hint is stored where there is a candidate
BLANK_HINTS = {
    "botswana_airports": "NOT ASSIGNED - possible match: 'Commercialisation of Airports' (Botswana Development Corporation) introduced by Oteng. Confirm before using.",
}

# who the sources are (only what the notes actually say)
INFO = {
    "Anil Vora (RAMCO)": ("Local partner in Togo (RAMCO); brought the energy and mining projects from the Ministry of Energy & Mineral Resources.", "Local partner", "Togo"),
    "Nexus Capital": ("Local partner in Cameroon; introduced the airport projects (CCAA) and the Kribi hydrocarbon terminal.", "Local partner", "Cameroon"),
    "Hamadama": ("Local partner in Cameroon; introduced SONARA, SOCADEL, SODECOTON and the power projects; he approves the EOIs.", "Local partner", "Cameroon"),
    "Steve": ("Local partner in Cameroon; introduced CAMTEL and the MINEPAT adviser projects.", "Local partner", "Cameroon"),
    "KT&Co": ("Sponsor of the Cameroon 3-city road programme; has already met the Ministry and the Presidency.", "Developer", "Cameroon"),
    "Virgil": ("Son of the Minister of Energy (Gabon); brought the water, grid and energy projects and says they are Government priorities.", "Minister / Government", "Gabon"),
    "Arm": ("Connected through Virgil; contact for the Gabon floating-solar project.", "Developer", "Gabon"),
    "Walter": ("Local partner in Gabon; works with Yann on the education, road and airport projects (Presidency / ministries).", "Local partner", "Gabon"),
    "Yann": ("Local partner in Gabon; confirmed the Presidency is keen on the education project and advised focusing on the roads and education ministries.", "Local partner", "Gabon"),
    "Minister Sylla": ("Minister, Republic of Guinea; introduced the National Health Infrastructure Programme (31 hospitals).", "Minister / Government", "Guinea"),
    "Roshan (Topaz)": ("Topaz Group contact; introduced the Simandou 2040 roads, port, fisheries and waste-to-energy projects.", "Developer", "Guinea"),
    "Bashir Kamara (MAHH)": ("Official at MAHH (Guinea ministry); personally driving the LNG terminal and oil-terminal projects.", "Minister / Government", "Guinea"),
    "Topaz Group": ("Developer / promoter behind Guinea's P2 pipeline (hydro, solar, transmission, observatory).", "Developer", "Guinea"),
    "Hamere Consultant": ("Design / technical advisor (HAMERE SARL) for the TACON expressway, Kansonyah city and Camayenne CBD.", "Adviser / Consultant", "Guinea"),
    "Oscar Daga (DK Group)": ("Local partner in Burkina Faso (DK Groupe); several of his projects are on the Presidency office's priority list.", "Local partner", "Burkina Faso"),
    "Souleymen Ildo (Ildo Oil)": ("Local partner in Burkina Faso (Ildo Oil / Ildo Business); HFO power plants and fuel supply.", "Local partner", "Burkina Faso"),
    "Ahmed Fofana": ("Local partner in Burkina Faso (listed in the local-partner list).", "Local partner", "Burkina Faso"),
    "CDCB (Edmond)": ("Contact at CDC Bank (Benin); introduced the two railway projects and further CDC projects.", "Bank / Financier", "Benin"),
    "Planet One": ("EPC partner; introduced the Benin education project.", "EPC partner", ""),
    "Zener Group (Zeneer)": ("Developer; Benin solar + BESS project (also involved in Burkina HFO sites).", "Developer", "Benin"),
    "Anatole": ("Cameroon Consulate in Togo (introduced by Ferdinand); local partner for the Liberia JFK Hospital.", "Local partner", "Liberia"),
    "UHG": ("Hospital EPC / developer partner (with Infra.Health); introduced the Sierra Leone hospital projects.", "EPC partner", "Sierra Leone"),
    "Boma": ("Introduced the Tanzania gold projects, the Zanzibar convention centre and solar opportunities.", "", "Tanzania"),
    "Mohsin Patel": ("Introduced most of Tanzania's Government projects (roads, water, ministries, Kiabakari gold, railway).", "", "Tanzania"),
    "Juma (PPP Unit)": ("Official of Tanzania's PPP Unit; identified the Ministry of Works' priority road projects.", "Minister / Government", "Tanzania"),
    "Japhet": ("Introduced the Tanzania geothermal and gas-to-power projects; relays documents to the Ministry.", "", "Tanzania"),
    "Renata": ("Contact for Tanzanian power projects (100 MW wind, solar); asks for a PCN instead of an LOI.", "", "Tanzania"),
    "Delina": ("Introduced Tanzania's streetlight, housing, Zanzibar port and smart-meter projects.", "", "Tanzania"),
    "Abdul": ("Introduced the Tanzania transmission line and fertiliser / railway leads; RGS meets him directly.", "", "Tanzania"),
    "Michael": ("Introducer of the DRC rural-development (PADER) programme; the Ministry of Rural Development countersigned the EOI.", "", "DRC"),
}
