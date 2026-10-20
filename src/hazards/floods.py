"""Flood occurrence by province and quarter, from EM-DAT (CRED, public.emdat.be).

Events kept (to match the flood CAT model: river and surface flooding from all rain
sources, including typhoon rain; storm surge excluded):
- Disaster Type = Flood, all subtypes except Coastal flood;
- Disaster Type = Storm with 'Flood' among Associated Types (typhoon-rain flooding).

Location -> provinces, in order of preference:
1. 'Admin Units' (GAUL): adm2 = provinces, adm1 = regions (expanded on the boundaries of
   their time, e.g. Western Visayas before 2024 includes Negros Occidental);
2. 'GADM Admin Units': province from the gid_1 prefix;
3. 'Location' free text: province / region / island names, typos matched fuzzily.
Events naming only 'Luzon', 'Visayas' or 'Mindanao' cannot be placed and are listed.
Units are the boundary polygons of hazards.typhoon (Maguindanao as one unit).
"""
import difflib
import json
import re
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "hazards" / "emdat"

PROVINCES = [
    "Abra", "Agusan del Norte", "Agusan del Sur", "Aklan", "Albay", "Antique", "Apayao",
    "Aurora", "Basilan", "Bataan", "Batanes", "Batangas", "Benguet", "Biliran", "Bohol",
    "Bukidnon", "Bulacan", "Cagayan", "Camarines Norte", "Camarines Sur", "Camiguin", "Capiz",
    "Catanduanes", "Cavite", "Cebu", "Compostela Valley", "Cotabato", "Davao Occidental",
    "Davao Oriental", "Davao del Norte", "Davao del Sur", "Dinagat Islands", "Eastern Samar",
    "Guimaras", "Ifugao", "Ilocos Norte", "Ilocos Sur", "Iloilo", "Isabela", "Kalinga",
    "La Union", "Laguna", "Lanao del Norte", "Lanao del Sur", "Leyte", "Maguindanao",
    "Marinduque", "Masbate", "Misamis Occidental", "Misamis Oriental", "Mountain Province",
    "Negros Occidental", "Negros Oriental", "Northern Samar", "Nueva Ecija", "Nueva Vizcaya",
    "Occidental Mindoro", "Oriental Mindoro", "Palawan", "Pampanga", "Pangasinan", "Quezon",
    "Quirino", "Rizal", "Romblon", "Samar", "Sarangani", "Siquijor", "Sorsogon",
    "South Cotabato", "Southern Leyte", "Sultan Kudarat", "Sulu", "Surigao del Norte",
    "Surigao del Sur", "Tarlac", "Tawi-Tawi", "Zambales", "Zamboanga Sibugay",
    "Zamboanga del Norte", "Zamboanga del Sur",
]
ALIASES = {  # lower-case variant -> list of province units
    "mindoro occidental": ["Occidental Mindoro"], "mindoro oriental": ["Oriental Mindoro"],
    "north cotabato": ["Cotabato"], "compostela": ["Compostela Valley"],
    "davao de oro": ["Compostela Valley"], "dinagat": ["Dinagat Islands"],
    "saranggani": ["Sarangani"], "shariff kabunsuan": ["Maguindanao"],
    "maguindanao del sur": ["Maguindanao"], "maguindanao del norte": ["Maguindanao"],
    "maguidanao del sur": ["Maguindanao"],
    "kalinga apayao": ["Kalinga", "Apayao"], "kalinga-apayao": ["Kalinga", "Apayao"],
    "kalin-aapayo": ["Kalinga", "Apayao"], "northern leyte": ["Leyte"],
    "western samar": ["Samar"], "mt. province": ["Mountain Province"],
    "lanao del sud": ["Lanao del Sur"], "arora": ["Aurora"], "barangas": ["Batangas"],
    "davao city": ["Davao del Sur"], "zamboanga city": ["Zamboanga del Sur"],
    "cagayan de oro": ["Misamis Oriental"], "gingoog": ["Misamis Oriental"],
    "bacolod city": ["Negros Occidental"], "manukan": ["Zamboanga del Norte"],
    "bacungan": ["Zamboanga del Norte"],
    "sorgoson": ["Sorsogon"], "iligan": ["Lanao del Norte"], "kauswagan": ["Lanao del Norte"],
    "linamon": ["Lanao del Norte"], "tubod": ["Lanao del Norte"],
    "bago": ["Negros Occidental"], "la cariota": ["Negros Occidental"],
    "laoag city": ["Ilocos Norte"], "tangag": ["Surigao del Sur"], "marawi": ["Lanao del Sur"],
    "agusan": ["Agusan del Norte", "Agusan del Sur"],
    "surigao": ["Surigao del Norte", "Surigao del Sur"],
    "panay": ["Aklan", "Antique", "Capiz", "Iloilo"], "panays islands": ["Aklan", "Antique", "Capiz", "Iloilo"],
    "negros": ["Negros Occidental", "Negros Oriental"],
    "floridablanca": ["Pampanga"], "concepcion": ["Tarlac"], "abuyog town": ["Leyte"],
    "valencia": ["Bukidnon"],
}
NO_RICE = {"metropolitan manila", "metro manila", "metro manilla", "manila", "manilla",
           "national capital region", "ncr", "national capital region (ncr)"}
VAGUE = {"luzon", "luzon isl", "luzon islands", "luzon island", "luzon province", "visayas",
         "mindanao", "mindanao island", "mindanao islands", "mindanao province",
         "muslim mindanao", "northern mindanao"}
# Assumption (flagged in the report): 'Northern Luzon' = Ilocos, Cagayan Valley and CAR.
NORTHERN_LUZON = {"northern luzon", "northern luzon island"}
# Per-event decisions where the text is ambiguous (EM-DAT DisNo -> extra units)
OVERRIDES = {"1994-0594-PHL": ["Negros Occidental"]}  # 'Bacolod' next to Iloilo, Leyte

# regions on the boundaries of the time of the event (EM-DAT/GAUL names and text forms)
REGION_UNITS = {
    "CAR": ["Abra", "Apayao", "Benguet", "Ifugao", "Kalinga", "Mountain Province"],
    "I": ["Ilocos Norte", "Ilocos Sur", "La Union", "Pangasinan"],
    "II": ["Batanes", "Cagayan", "Isabela", "Nueva Vizcaya", "Quirino"],
    "III": ["Aurora", "Bataan", "Bulacan", "Nueva Ecija", "Pampanga", "Tarlac", "Zambales"],
    "IV-A": ["Batangas", "Cavite", "Laguna", "Quezon", "Rizal"],
    "MIMAROPA": ["Marinduque", "Occidental Mindoro", "Oriental Mindoro", "Palawan", "Romblon"],
    "V": ["Albay", "Camarines Norte", "Camarines Sur", "Catanduanes", "Masbate", "Sorsogon"],
    "VI": ["Aklan", "Antique", "Capiz", "Guimaras", "Iloilo", "Negros Occidental"],
    "VII": ["Bohol", "Cebu", "Negros Oriental", "Siquijor"],
    "NIR": ["Negros Occidental", "Negros Oriental", "Siquijor"],
    "VIII": ["Biliran", "Eastern Samar", "Leyte", "Northern Samar", "Samar", "Southern Leyte"],
    "IX": ["Zamboanga del Norte", "Zamboanga del Sur", "Zamboanga Sibugay"],
    "X": ["Bukidnon", "Camiguin", "Lanao del Norte", "Misamis Occidental", "Misamis Oriental"],
    "XI": ["Compostela Valley", "Davao del Norte", "Davao del Sur", "Davao Occidental",
           "Davao Oriental"],
    "XII": ["Cotabato", "Sarangani", "South Cotabato", "Sultan Kudarat"],
    "XIII": ["Agusan del Norte", "Agusan del Sur", "Dinagat Islands", "Surigao del Norte",
             "Surigao del Sur"],
    "ARMM": ["Basilan", "Lanao del Sur", "Maguindanao", "Sulu", "Tawi-Tawi"],
}
REGION_UNITS["IV"] = REGION_UNITS["IV-A"] + REGION_UNITS["MIMAROPA"]
REGION_UNITS["BARMM"] = REGION_UNITS["ARMM"]
REGION_NAMES = {  # lower-case name -> region key
    "cordillera administrative region": "CAR", "car": "CAR", "ilocos": "I",
    "ilocos region": "I", "cagayan valley": "II", "central luzon": "III",
    "calabarzon": "IV-A", "southern tagalog": "IV", "mimaropa": "MIMAROPA", "bicol": "V",
    "bicol region": "V", "western visayas": "VI", "central visayas": "VII",
    "negros island region": "NIR", "negros islands region": "NIR", "eastern visayas": "VIII", "zamboanga peninsula": "IX",
    "zamboanga peninsula region": "IX", "northern mindanao region": "X", "davao": "XI",
    "davao region": "XI", "soccsksargen": "XII", "caraga": "XIII",
    "autonomous region in muslim mindanao": "ARMM", "armm": "ARMM", "barmm": "BARMM",
    "bangsamoro autonomous region": "BARMM",
}
ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "4a": "IV-A", "5": "V", "6": "VI",
         "7": "VII", "8": "VIII", "9": "IX", "10": "X", "11": "XI", "12": "XII", "13": "XIII"}
_LOWER = {p.lower(): p for p in PROVINCES}


def _province(name: str):
    """Province units for a name; [] = a place with no rice (Metro Manila); None = unknown."""
    n = re.sub(r"\s+", " ", name.strip().lower()).strip(" .")
    n = re.sub(r"^(the|towns? of)\s+", "", n)
    cands = (n, re.sub(r"\b(province|provinces|isl|island|islands|city|town|area|areas)$", "", n).strip(" ."))
    for cand in cands:
        if cand in NO_RICE:
            return []
        if cand in _LOWER:
            return [_LOWER[cand]]
        if cand in ALIASES:
            return ALIASES[cand]
    for cand in cands:
        m = difflib.get_close_matches(cand, list(_LOWER) + list(ALIASES), n=1, cutoff=0.85)
        if m:
            return [_LOWER[m[0]]] if m[0] in _LOWER else ALIASES[m[0]]
    return None


def _region(name: str):
    """Region key from a GAUL adm1 name or a text fragment, else None."""
    n = name.strip().lower()
    m = re.search(r"\(([^)]+)\)", n)
    if m and m.group(1).strip() in REGION_NAMES:
        return REGION_NAMES[m.group(1).strip()]
    n = re.sub(r"\bregions?\b", "", re.sub(r"\(.*?\)", "", n)).strip(" .")
    if n in REGION_NAMES:
        return REGION_NAMES[n]
    if n.upper() in REGION_UNITS:
        return n.upper()
    if n in ROMAN:
        return ROMAN[n]
    return None


def _split_top(text: str):
    """Split on , and ; outside brackets; returns (main, [bracket contents]) per item."""
    items, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch in ",;" and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    out = []
    for it in items:
        inner = re.findall(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)", it)
        main = re.sub(r"\(.*\)", "", it).strip()
        out.append((main, inner))
    return out


def _place(frag: str):
    """Units for one fragment: region name, 'Northern Luzon', province; None if unknown."""
    low = frag.lower().strip(" .")
    low = re.sub(r"^(the)\s+", "", low)
    if low in NORTHERN_LUZON:
        return set(REGION_UNITS["I"] + REGION_UNITS["II"] + REGION_UNITS["CAR"])
    if low in VAGUE:
        return None
    r = _region(low)
    if r:
        return set(REGION_UNITS[r])
    p = _province(low)
    return None if p is None else set(p)


def _from_text(text: str):
    """Units named in a free-text Location; also returns fragments it could not place."""
    units, unplaced = set(), []
    t = text.replace(" and ", ", ")
    # 'Regions I, II, III and CAR' / 'Region 3, 1 (Ilocos), 6' : numerals after 'Region(s)'
    pat = r"(?i)regions?\s+([0-9ivx ,\-a]+?)(?=[;(]|$|[a-z]{3,})"
    for m in re.finditer(pat, t):
        for tok in re.split(r"[,\- ]+", m.group(1).lower()):
            key = ROMAN.get(tok.strip()) or (tok.strip().upper() if tok.strip().upper() in REGION_UNITS else None)
            if key:
                units.update(REGION_UNITS[key])
    t = re.sub(pat, ",", t)
    for main, inner in _split_top(t):
        if not main and not inner:
            continue
        if main and re.fullmatch(r"(?i)[0-9ivx\- ]+|regions?", main):
            continue
        got = _place(main) if main else None
        if got is None:
            # bracket only when the main part could not be placed ('Tangag (Surigao del Sur)')
            for txt in inner:
                for sub, _ in _split_top(txt):
                    g = _place(sub)
                    if g:
                        got = (got or set()) | g
        if got is None:
            if main:
                unplaced.append(main)
        else:
            units.update(got)
    return units, unplaced


def load_events() -> pd.DataFrame:
    f = sorted(p for p in DATA.glob("*.xlsx") if not p.name.startswith("~$"))[0]
    d = pd.read_excel(f, sheet_name=0)
    flood = (d["Disaster Type"] == "Flood") & (d["Disaster Subtype"] != "Coastal flood")
    storm_flood = (d["Disaster Type"] == "Storm") & d["Associated Types"].astype(str).str.contains("Flood")
    d = d[flood | storm_flood].copy()
    gadm1 = {}
    for s in d["GADM Admin Units"].dropna():
        for u in json.loads(s):
            if "name_1" in u:
                gadm1[u["gid_1"]] = u["name_1"]
    rows = []
    for _, e in d.iterrows():
        units, unplaced, source = set(), [], ""
        if pd.notna(e["Admin Units"]):
            source = "admin units (GAUL)"
            for u in json.loads(e["Admin Units"]):
                if "adm2_name" in u:
                    p = _province(u["adm2_name"])
                    (units.update(p) if p is not None else unplaced.append(u["adm2_name"]))
                else:
                    r = _region(u["adm1_name"])
                    if r:
                        units.update(REGION_UNITS[r])
                    elif _province(u["adm1_name"]) != []:
                        unplaced.append(u["adm1_name"])
        elif pd.notna(e["GADM Admin Units"]):
            source = "GADM admin units"
            for u in json.loads(e["GADM Admin Units"]):
                gid = u.get("gid_1") or ".".join(u.get("gid_2", "").split(".")[:2]) + "_1"
                p = _province(gadm1.get(gid, ""))
                if p:
                    units.update(p)
        elif pd.notna(e["Location"]):
            source = "location text"
            units, unplaced = _from_text(str(e["Location"]))
        units.update(OVERRIDES.get(e["DisNo."], []))
        start = pd.Period(year=int(e["Start Year"]), month=int(e["Start Month"]), freq="M")
        end_m = e["End Month"] if pd.notna(e["End Month"]) else e["Start Month"]
        end_y = e["End Year"] if pd.notna(e["End Year"]) else e["Start Year"]
        end = max(start, pd.Period(year=int(end_y), month=int(end_m), freq="M"))
        rows.append(dict(DisNo=e["DisNo."], type=e["Disaster Type"], subtype=e["Disaster Subtype"],
                         name=e["Event Name"], start=start, end=end, source=source,
                         units=sorted(units), unplaced="; ".join(unplaced),
                         location=e["Location"]))
    return pd.DataFrame(rows)


def province_quarter(events: pd.DataFrame) -> pd.DataFrame:
    """One row per province x quarter with >= 1 event; quarters spanned start..end."""
    rows = []
    for _, e in events.iterrows():
        for q in pd.period_range(e.start.asfreq("Q"), e.end.asfreq("Q"), freq="Q"):
            for u in e.units:
                rows.append((u, q, e.DisNo))
    x = pd.DataFrame(rows, columns=["polygon", "period", "DisNo"])
    return (x.groupby(["polygon", "period"]).DisNo.nunique().rename("n_events")
             .reset_index())
