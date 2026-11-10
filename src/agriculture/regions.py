"""Fixed province -> region mapping used by every PSA series (palay, corn, VR, PF) and by
the hazard controls: the 16 agricultural regions of methodology v5 (Table 1).

v5: "Regions follow the structure that applied before the creation of the Negros Island
Region in 2024, with Negros Occidental, Negros Oriental and Siquijor kept in Western and
Central Visayas; the data for these provinces after 2024 are added back to the two
regions. The National Capital Region ... is excluded. Sulu, separated from BARMM in 2024,
and Cotabato City, which joined BARMM in 2019, are kept in BARMM for all years."

Region codes and labels are those of Van's boundary file (scripts/make_regions.py,
data/boundaries/phl_16_regions.gpkg), so production, weather and controls share one key.

Eight Cluster Areas (63 barangays of the Province of Cotabato, Region XII, that joined
BARMM): PSA includes them in the BARMM total from 2023Q1 but in no province row. To keep
both regions on their pre-2023 boundaries, the residual BARMM total minus the sum of the
provinces listed under BARMM is added to Region XII from 2023Q1 (agriculture.rebuild).

PSA table notes (palay/corn release of 2026-07-29; same footnotes in the VR/PF tables):
  a/ Negros Occidental: still part of Western Visayas prior to 2024
  b/ Negros Oriental, Siquijor: still part of Central Visayas prior to 2024
  c/ Sulu: still part of BARMM prior to 2026; realigned to Region IX by EO 91
  d/ BARMM: 2026 data exclude Sulu
Province names are as in PSA OpenSTAT, without footnote markers; the VR/PF tables spell some
differently from the palay/corn tables (e.g. "City of Bacolod", "Cotabato", "Maguindanao"),
so both spellings are listed.
"""
import re

import pandas as pd

REGIONS = {  # code (as in Van's boundary file) -> PSA label, in PSA order
    "CAR": "CORDILLERA ADMINISTRATIVE REGION (CAR)",
    "R01": "REGION I (ILOCOS REGION)",
    "R02": "REGION II (CAGAYAN VALLEY)",
    "R03": "REGION III (CENTRAL LUZON)",
    "R04A": "REGION IV-A (CALABARZON)",
    "MIMAROPA": "MIMAROPA REGION",
    "R05": "REGION V (BICOL REGION)",
    "R06": "REGION VI (WESTERN VISAYAS)",
    "R07": "REGION VII (CENTRAL VISAYAS)",
    "R08": "REGION VIII (EASTERN VISAYAS)",
    "R09": "REGION IX (ZAMBOANGA PENINSULA)",
    "R10": "REGION X (NORTHERN MINDANAO)",
    "R11": "REGION XI (DAVAO REGION)",
    "R12": "REGION XII (SOCCSKSARGEN)",
    "R13": "REGION XIII (CARAGA)",
    "BARMM": "BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO (BARMM)",
}
CODE_OF_LABEL = {v: k for k, v in REGIONS.items()}
# published region rows that are not one of the 16 (only used to read PSA tables)
PUBLISHED_ONLY = {"NEGROS ISLAND REGION": "NIR", "NEGROS ISLAND REGION (NIR)": "NIR"}
# label variants seen in PSA tables (fruit table writes BARMM without the acronym)
LABEL_ALIASES = {"BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO": "BARMM"}

PROVINCE_REGION = {
    "CAR": ["Abra", "Apayao", "Benguet", "Ifugao", "Kalinga", "Mountain Province"],
    "R01": ["Ilocos Norte", "Ilocos Sur", "La Union", "Pangasinan"],
    "R02": ["Batanes", "Cagayan", "Isabela", "Nueva Vizcaya", "Quirino"],
    "R03": ["Aurora", "Bataan", "Bulacan", "Nueva Ecija", "Pampanga", "Tarlac", "Zambales"],
    "R04A": ["Batangas", "Cavite", "Laguna", "Quezon", "Rizal"],
    "MIMAROPA": ["Marinduque", "Occidental Mindoro", "Oriental Mindoro", "Palawan",
                 "Romblon", "Puerto Princesa City",
                 "City of Puerto Princesa"],
    "R05": ["Albay", "Camarines Norte", "Camarines Sur", "Catanduanes", "Masbate", "Sorsogon"],
    "R06": ["Aklan", "Antique", "Capiz", "Guimaras", "Iloilo", "Negros Occidental",
            "Bacolod City", "City of Bacolod"],
    "R07": ["Bohol", "Cebu", "Negros Oriental", "Siquijor"],
    "R08": ["Biliran", "Eastern Samar", "Leyte", "Northern Samar", "Samar", "Southern Leyte"],
    "R09": ["Zamboanga del Norte", "Zamboanga del Sur", "Zamboanga Sibugay", "Zamboanga City",
            "City of Zamboanga"],
    "R10": ["Bukidnon", "Camiguin", "Lanao del Norte", "Misamis Occidental", "Misamis Oriental"],
    "R11": ["Davao de Oro (Compostela Valley)", "Davao de Oro", "Davao del Norte", "Davao del Sur",
            "Davao Occidental", "Davao Oriental", "City of Davao"],
    "R12": ["Cotabato (North Cotabato)", "Cotabato", "Sarangani", "South Cotabato", "Sultan Kudarat"],
    "R13": ["Agusan del Norte", "Agusan del Sur", "Dinagat Islands", "Surigao del Norte",
            "Surigao del Sur", "Butuan City", "City of Butuan"],
    "BARMM": ["Basilan", "Lanao del Sur", "Maguindanao", "Maguindanao del Norte", "Maguindanao del Sur",
              "Sulu", "Tawi-tawi"],
}
REGION_OF_PROVINCE = {p: r for r, ps in PROVINCE_REGION.items() for p in ps}

# Every unit whose region or name changed. 'In PSA table' was checked against the
# 1987-2026 palay/corn release and the 2010-2026 VR/PF releases.
BOUNDARY_CHANGES = pd.DataFrame([
    ("Negros Occidental", "VI -> NIR", "2024 (RA 12000)",
     "under VI to 2023Q4, under NIR from 2024Q1", "R06, all years"),
    ("Negros Oriental", "VII -> NIR", "2024 (RA 12000)",
     "under VII to 2023Q4, under NIR from 2024Q1", "R07, all years"),
    ("Siquijor", "VII -> NIR", "2024 (RA 12000)",
     "under VII to 2023Q4, under NIR from 2024Q1", "R07, all years"),
    ("Bacolod City", "split out of Negros Occidental", "-",
     "separate row from 2026Q1 only", "R06"),
    ("Sulu", "BARMM -> IX", "Executive Order No. 91 (PSA note c/)",
     "under BARMM to 2025Q4, under IX from 2026Q1", "BARMM, all years"),
    ("Eight Cluster Areas", "63 barangays of the Province of Cotabato (XII) -> BARMM", "2019",
     "in the BARMM total from 2023Q1, in no province row (PSA note)",
     "BARMM total - BARMM provinces, added to R12 from 2023Q1"),
    ("Cotabato City", "XII -> BARMM", "2019 (RA 11054)", "no separate row",
     "BARMM (v5); in Van's boundaries too"),
    ("Maguindanao", "split into del Norte and del Sur (both BARMM)", "2022 (RA 11550)",
     "del Norte from 2024Q1; before, all Maguindanao in the 'del Sur' row",
     "no regional effect"),
    ("Compostela Valley", "renamed Davao de Oro (XI)", "2019", "one row", "no regional effect"),
    ("Davao Occidental", "created from Davao del Sur (XI)", "2013", "back-cast",
     "no regional effect"),
    ("Dinagat Islands", "created from Surigao del Norte (XIII)", "2006", "back-cast",
     "no regional effect"),
    ("Zamboanga Sibugay", "created from Zamboanga del Sur (IX)", "2001", "back-cast",
     "no regional effect"),
    ("Apayao", "created from Kalinga-Apayao (CAR)", "1995", "back-cast", "no regional effect"),
    ("Biliran / Guimaras / Sarangani", "created from Leyte / Iloilo / South Cotabato",
     "1992", "back-cast", "no regional effect"),
    ("Caraga; 2001 Mindanao regrouping; Region IV split (IV-A, MIMAROPA); Aurora IV -> III",
     "regional reorganisations", "1995 / 2001 / 2002",
     "back-cast: provinces listed under current regions from 1987", "none needed"),
    ("Puerto Princesa City / Butuan City", "split out of Palawan / Agusan del Norte", "-",
     "separate rows from 2026Q1 only, same region", "no regional effect"),
], columns=["unit", "change", "when", "in PSA table", "treatment"])

_FOOTNOTE = re.compile(r"\s*\d+/$")


def clean_label(label: str) -> str:
    """PSA region label without numeric footnote markers ('... (BARMM) 1/' -> '... (BARMM)')."""
    return _FOOTNOTE.sub("", str(label).strip()).strip()


def code_of_published(labels: pd.Series) -> pd.Series:
    """Code of a published region row: one of the 16, or 'NIR'. Fails on unknown labels."""
    lab = labels.map(clean_label)
    out = lab.map(CODE_OF_LABEL).fillna(lab.map(LABEL_ALIASES)).fillna(lab.map(PUBLISHED_ONLY))
    unknown = sorted(lab[out.isna() & labels.notna()].unique())
    if unknown:
        raise KeyError(f"unknown PSA region labels: {unknown}")
    return out


def assign_region(provinces: pd.Series) -> pd.Series:
    """Fixed region code for each province; fails on names not in the mapping, so a new
    PSA release with renamed or new provinces cannot be silently mis-assigned."""
    out = provinces.map(REGION_OF_PROVINCE)
    unknown = sorted(provinces[out.isna()].unique())
    if unknown:
        raise KeyError(f"provinces missing from PROVINCE_REGION: {unknown}")
    return out


def mapping_table() -> pd.DataFrame:
    return pd.DataFrame([(p, r, REGIONS[r]) for r, ps in PROVINCE_REGION.items() for p in ps],
                        columns=["province", "region_code", "region"])
