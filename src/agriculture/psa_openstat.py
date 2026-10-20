"""Reader for PSA OpenSTAT palay/corn tables (CSV export, "Ecosystem/Croptype x Geolocation").

- 2E4EVCP0: Volume of Production in Metric Tons -> data/agriculture/palay_and_corn_volume.csv
- 2E4EAHC0: Area Harvested in Hectares         -> data/agriculture/palay_and_corn_area.csv

Layout (both files): a title line, then a header with one column per quarter, semester
and year, 1987-2026; '..' = not available. One block of rows per crop (Irrigated Palay,
Rainfed Palay, Palay, White Corn, Yellow Corn, Corn). Inside a block: 'PHILIPPINES',
then each region ('..NAME') followed by its provinces ('....Name'). Names may carry
footnote markers ('Sulu c/'), whose text is not in the CSV export.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
FILES = {
    "production_t": DATA / "agriculture" / "palay_and_corn_volume.csv",
    "area_ha": DATA / "agriculture" / "palay_and_corn_area.csv",
}
FOOTNOTE = r"\s*([a-z])/$"


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
    return long.drop(columns="col")


def read_palay_corn() -> pd.DataFrame:
    """Production and area side by side. Fails if the two files' rows do not line up."""
    prod = read_openstat(FILES["production_t"], "production_t")
    area = read_openstat(FILES["area_ha"], "area_ha")
    keys = ["crop", "level", "region_published", "geo", "footnote", "row", "period"]
    out = prod.merge(area, on=keys, how="outer", validate="1:1", indicator=True)
    if (out["_merge"] != "both").any():
        raise ValueError("volume and area files have different row layouts")
    return out.drop(columns="_merge").sort_values(["row", "period"]).reset_index(drop=True)
