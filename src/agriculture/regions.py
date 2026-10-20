"""Fixed province -> region mapping: all years on the CURRENT 17 agricultural regions
(the 18 official regions minus NCR, which has no palay/corn rows).

"Current" = Negros Island Region (NIR) as created in 2024, and Sulu in Region IX (PSA
lists it there from 2026Q1, realigned by Executive Order No. 91). Province names are as
in PSA OpenSTAT, without footnote markers. PSA table notes (2026-07-29 release):
  a/ Negros Occidental: still part of Western Visayas prior to 2024
  b/ Negros Oriental, Siquijor: still part of Central Visayas prior to 2024
  c/ Sulu: still part of BARMM prior to 2026; realigned to Region IX by EO 91
  d/ BARMM: 2026 data exclude Sulu
  BARMM total from 2023Q1 includes the Eight Cluster Areas (63 barangays previously
  of the Province of Cotabato), which are in no province row.
"""
import pandas as pd

REGIONS = {  # code -> PSA label, in PSA order
    "CAR": "CORDILLERA ADMINISTRATIVE REGION (CAR)",
    "I": "REGION I (ILOCOS REGION)",
    "II": "REGION II (CAGAYAN VALLEY)",
    "III": "REGION III (CENTRAL LUZON)",
    "IV-A": "REGION IV-A (CALABARZON)",
    "MIMAROPA": "MIMAROPA REGION",
    "V": "REGION V (BICOL REGION)",
    "VI": "REGION VI (WESTERN VISAYAS)",
    "NIR": "NEGROS ISLAND REGION",
    "VII": "REGION VII (CENTRAL VISAYAS)",
    "VIII": "REGION VIII (EASTERN VISAYAS)",
    "IX": "REGION IX (ZAMBOANGA PENINSULA)",
    "X": "REGION X (NORTHERN MINDANAO)",
    "XI": "REGION XI (DAVAO REGION)",
    "XII": "REGION XII (SOCCSKSARGEN)",
    "XIII": "REGION XIII (CARAGA)",
    "BARMM": "BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO (BARMM)",
}
CODE_OF_LABEL = {v: k for k, v in REGIONS.items()}

PROVINCE_REGION = {
    "CAR": ["Abra", "Apayao", "Benguet", "Ifugao", "Kalinga", "Mountain Province"],
    "I": ["Ilocos Norte", "Ilocos Sur", "La Union", "Pangasinan"],
    "II": ["Batanes", "Cagayan", "Isabela", "Nueva Vizcaya", "Quirino"],
    "III": ["Aurora", "Bataan", "Bulacan", "Nueva Ecija", "Pampanga", "Tarlac", "Zambales"],
    "IV-A": ["Batangas", "Cavite", "Laguna", "Quezon", "Rizal"],
    "MIMAROPA": ["Marinduque", "Occidental Mindoro", "Oriental Mindoro", "Palawan",
                 "Romblon", "Puerto Princesa City"],
    "V": ["Albay", "Camarines Norte", "Camarines Sur", "Catanduanes", "Masbate", "Sorsogon"],
    "VI": ["Aklan", "Antique", "Capiz", "Guimaras", "Iloilo"],
    "NIR": ["Negros Occidental", "Bacolod City", "Negros Oriental", "Siquijor"],
    "VII": ["Bohol", "Cebu"],
    "VIII": ["Biliran", "Eastern Samar", "Leyte", "Northern Samar", "Samar", "Southern Leyte"],
    "IX": ["Zamboanga del Norte", "Zamboanga del Sur", "Zamboanga Sibugay", "Zamboanga City",
           "Sulu"],
    "X": ["Bukidnon", "Camiguin", "Lanao del Norte", "Misamis Occidental", "Misamis Oriental"],
    "XI": ["Davao de Oro (Compostela Valley)", "Davao del Norte", "Davao del Sur",
           "Davao Occidental", "Davao Oriental", "City of Davao"],
    "XII": ["Cotabato (North Cotabato)", "Sarangani", "South Cotabato", "Sultan Kudarat"],
    "XIII": ["Agusan del Norte", "Agusan del Sur", "Dinagat Islands", "Surigao del Norte",
             "Surigao del Sur", "Butuan City"],
    "BARMM": ["Basilan", "Lanao del Sur", "Maguindanao del Norte", "Maguindanao del Sur",
              "Tawi-tawi"],
}
REGION_OF_PROVINCE = {p: r for r, ps in PROVINCE_REGION.items() for p in ps}

# Every unit whose region or name changed. 'In PSA table' was checked against the
# 1987-2026 release; legal dates are for reference.
BOUNDARY_CHANGES = pd.DataFrame([
    ("Negros Occidental", "VI -> NIR", "2024 (RA 12000)",
     "under VI to 2023Q4, under NIR from 2024Q1; VI row = 0 in 2025Q1", "NIR, all years"),
    ("Negros Oriental", "VII -> NIR", "2024 (RA 12000)",
     "under VII to 2023Q4, under NIR from 2024Q1; VII row = 0 in 2025Q1", "NIR, all years"),
    ("Siquijor", "VII -> NIR", "2024 (RA 12000)",
     "under VII to 2023Q4, under NIR from 2024Q1; VII row = 0 in 2025Q1", "NIR, all years"),
    ("Bacolod City", "split out of Negros Occidental", "-",
     "separate row from 2026Q1 only", "NIR"),
    ("Sulu", "BARMM -> IX", "Executive Order No. 91 (PSA note c/)",
     "under BARMM to 2025Q4, under IX from 2026Q1", "IX, all years"),
    ("ARMM -> BARMM", "renamed; adds Cotabato City and the Eight Cluster Areas "
     "(63 barangays of the Province of Cotabato)", "2019 (RA 11054)",
     "one BARMM row from 1987; from 2023Q1 the BARMM total includes the Eight Cluster "
     "Areas, which are in no province row (PSA note)",
     "BARMM = sum of its provinces; cluster areas kept apart"),
    ("Maguindanao", "split into del Norte and del Sur (both BARMM)", "2022 (RA 11550)",
     "del Norte from 2024Q1; before, all Maguindanao in the 'del Sur' row",
     "no regional effect"),
    ("Compostela Valley", "renamed Davao de Oro (XI)", "2019", "one row", "no regional effect"),
    ("Davao Occidental", "created from Davao del Sur (XI)", "2013", "back-cast to 1987",
     "no regional effect"),
    ("Dinagat Islands", "created from Surigao del Norte (XIII)", "2006", "back-cast to 1987",
     "no regional effect"),
    ("Zamboanga Sibugay", "created from Zamboanga del Sur (IX)", "2001", "back-cast to 1987",
     "no regional effect"),
    ("Apayao", "created from Kalinga-Apayao (CAR)", "1995", "back-cast to 1987",
     "no regional effect"),
    ("Biliran / Guimaras / Sarangani", "created from Leyte / Iloilo / South Cotabato",
     "1992", "back-cast to 1987", "no regional effect"),
    ("Caraga; 2001 Mindanao regrouping; Region IV split (IV-A, MIMAROPA); Aurora IV -> III",
     "regional reorganisations", "1995 / 2001 / 2002",
     "back-cast: provinces listed under current regions from 1987", "none needed"),
    ("Puerto Princesa City / Butuan City", "split out of Palawan / Agusan del Norte", "-",
     "separate rows from 2026Q1 only, same region", "no regional effect"),
], columns=["unit", "change", "when", "in PSA table", "treatment"])


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
