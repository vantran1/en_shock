"""Reader for PSA OpenSTAT crop tables (CSV export, "Crop x Geolocation").

- 2E4EVCP0: palay and corn, volume of production (t)  -> data/agriculture/palay_and_corn_volume.csv
- 2E4EAHC0: palay and corn, area harvested (ha)       -> data/agriculture/palay_and_corn_area.csv
- Vegetables and Root Crops, volume of production (t) -> data/agriculture/psa_veg_root_crops_2010-2026.csv
- Fruit Crops, volume of production (t)               -> data/agriculture/psa_fruit_crops_2010-2026.csv

Layout (all files): a title line, then a header with one column per quarter, semester
and year ("1987 Quarter 1" in the palay/corn tables, "2010 Quarter1" in the VR/PF
tables); '..' = not available. One block of rows per crop. Inside a block: 'PHILIPPINES',
then each region ('..NAME') followed by its provinces ('....Name'). Names may carry
footnote markers: letters for provinces ('Sulu c/'), numbers for regions ('... 1/'),
whose text is not in the CSV export.

Sub-rows ('......Name', VR table): the cities (Davao, Zamboanga, and from 2026 Bacolod,
Butuan, Puerto Princesa) are NOT included in the province above them (region total =
provinces + cities), so they are kept as separate units. Maguindanao del Norte and del
Sur are parts of Maguindanao: in the VR table, from 2025 they are listed under a
'Maguindanao' row that still holds the total; in the fruit table, from 2025 the
'Maguindanao' row is empty ('..') and only the halves have data. So, crop by crop and
quarter by quarter, the halves are dropped wherever the 'Maguindanao' row has a value.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
FILES = {
    "production_t": DATA / "agriculture" / "palay_and_corn_volume.csv",
    "area_ha": DATA / "agriculture" / "palay_and_corn_area.csv",
}
VR_PF_FILES = {
    "VR": DATA / "agriculture" / "psa_veg_root_crops_2010-2026.csv",
    "PF": DATA / "agriculture" / "psa_fruit_crops_2010-2026.csv",
}
FOOTNOTE = r"\s*([a-z0-9]+)/$"


def read_openstat(path: Path, value_name: str) -> pd.DataFrame:
    """Long table: one row per crop x geolocation row x quarter.

    Columns: crop, level ('national'|'region'|'province'), region_published (region the
    row is listed under in this release), geo (name without dots and footnote),
    footnote, row (position in file), period (quarterly pd.Period), value_name.
    Semester and annual columns are dropped: they are sums of the quarters.
    """
    raw = pd.read_csv(path, skiprows=1, na_values=[".."], dtype={0: str, 1: str}).copy()
    raw = raw.rename(columns={raw.columns[0]: "crop", raw.columns[1]: "geo_raw"})
    raw["row"] = np.arange(len(raw))
    raw["level"] = np.select(
        [raw["geo_raw"] == "PHILIPPINES", raw["geo_raw"].str.startswith("....")],
        ["national", "province"], "region")
    name = raw["geo_raw"].str.lstrip(".").str.strip()
    raw["footnote"] = name.str.extract(FOOTNOTE, expand=False)
    raw["geo"] = name.str.replace(FOOTNOTE, "", regex=True)
    # a province belongs to the last region row above it, within its crop block
    raw["region_published"] = raw["geo"].where(raw["level"] == "region")
    raw["region_published"] = raw.groupby("crop")["region_published"].ffill()
    raw.loc[raw["level"] == "national", "region_published"] = np.nan

    qcols = [c for c in raw.columns if "Quarter" in str(c)]
    ids = ["crop", "level", "region_published", "geo", "footnote", "row"]
    long = raw[ids + qcols].melt(id_vars=ids, var_name="col", value_name=value_name)
    long["period"] = pd.PeriodIndex(long["col"].str[:4] + "Q" + long["col"].str[-1], freq="Q")
    long = long.drop(columns="col")
    # Maguindanao del Norte / del Sur: drop where the 'Maguindanao' row has a value
    parent = (long[long["geo"] == "Maguindanao"].dropna(subset=[value_name])
              [["crop", "period"]].assign(parent_has_value=True))
    long = long.merge(parent, on=["crop", "period"], how="left")
    halves = long["geo"].isin(["Maguindanao del Norte", "Maguindanao del Sur"])
    long = long[~(halves & long["parent_has_value"].fillna(False).astype(bool))]
    return long.drop(columns="parent_has_value").reset_index(drop=True)


def read_palay_corn() -> pd.DataFrame:
    """Production and area side by side. Fails if the two files' rows do not line up."""
    prod = read_openstat(FILES["production_t"], "production_t")
    area = read_openstat(FILES["area_ha"], "area_ha")
    keys = ["crop", "level", "region_published", "geo", "footnote", "row", "period"]
    out = prod.merge(area, on=keys, how="outer", validate="1:1", indicator=True)
    if (out["_merge"] != "both").any():
        raise ValueError("volume and area files have different row layouts")
    return out.drop(columns="_merge").sort_values(["row", "period"]).reset_index(drop=True)


def read_vr_pf(crops: dict[str, list[str]]) -> pd.DataFrame:
    """Production of the requested commodities from the VR and PF tables.

    crops: {"VR": [...], "PF": [...]}, names exactly as in the PSA files (so "Mango" does
    not pick up "Mangosteen"). Fails if a name is missing. Adds a column `group`."""
    out = []
    for group, names in crops.items():
        d = read_openstat(VR_PF_FILES[group], "production_t")
        missing = sorted(set(names) - set(d["crop"]))
        if missing:
            raise KeyError(f"{group}: commodities not in the PSA file: {missing}")
        out.append(d[d["crop"].isin(names)].assign(group=group))
    return pd.concat(out, ignore_index=True)
