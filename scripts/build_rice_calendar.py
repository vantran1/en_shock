"""Rice growing windows by region and harvest quarter, for the Stage 2 weather features (two-stage
approach: weather in the months the crop is in the field -> production in the harvest quarter).

Source: RiceAtlas (Laborte et al. 2017, Scientific Data 4:170074; Harvard Dataverse
doi:10.7910/DVN/JE6R48), RiceCalendar_v1: planting and harvest dates (start, peak, end; day of
year) for up to three seasons per province, one fixed calendar (no year-to-year change, no
irrigated / rainfed split). Read from the attribute table inside the zip; the shapes are not used.

Steps
1. Province calendars: the Philippine rows of RiceAtlas, matched to the PSA provinces of the 16
   regions (agriculture.regions). Name differences are in ALIASES; provinces with no RiceAtlas row
   take the calendar in FALLBACK (Davao Occidental, split from Davao del Sur in 2013). Provinces
   with neither are left out and their share of production is reported (Batanes, Tawi-tawi).
2. Season of each harvest quarter: for each province and quarter, the season whose harvest window
   (harvest start to harvest end) overlaps the quarter most. If no season is harvested in the
   quarter, the season with the nearest harvest peak (matched_by = 'nearest'): that quarter's PSA
   production is not explained by the calendar, and its share is reported.
3. Growing window: from the planting peak to the harvest peak of that season, as months. The
   harvest peak is moved into the harvest quarter when it falls outside it (the crop harvested in
   the quarter cannot have been harvested before or after it), keeping the season's length.
4. Regional window: each province weighted by its mean PSA production in that quarter (2016-2025,
   as the shock weights), separately for irrigated, rainfed and total palay. The weight of a month
   is the share of the region's production in that quarter whose crop was in the field that month.
   lag = months before the last month of the harvest quarter (0 = last month of the quarter).

Run:  python scripts/build_rice_calendar.py
Writes
- data/processed/rice_calendar_province.csv        RiceAtlas calendar per PSA province and season
                                                   (months of planting / harvest start, peak, end)
- data/processed/rice_season_by_quarter.csv        province x ecosystem x quarter: season used, window,
                                                   match type, production weight
- data/processed/rice_growing_window.csv           ecosystem x region x harvest quarter x lag: weight
- outputs/tables/rice_calendar_coverage.csv        production share not covered / matched by 'nearest'
"""
import sys
import struct
import zipfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agriculture.psa_openstat import read_palay_corn  # noqa: E402
from agriculture.regions import REGION_OF_PROVINCE  # noqa: E402

ATLAS = ROOT / "data/agriculture/riceatlas/RiceCalendar_v1.zip"
PROC, TAB = ROOT / "data/processed", ROOT / "outputs/tables"
WEIGHT_YEARS = (2016, 2025)
ECOSYSTEMS = {"Irrigated Palay": "irrigated", "Rainfed Palay": "rainfed", "Palay": "total"}

# RiceAtlas name -> PSA province name(s)
ALIASES = {
    "Compostela Valley": ["Davao de Oro (Compostela Valley)"],
    "North Cotabato": ["Cotabato (North Cotabato)"],
    "Davao City": ["City of Davao"],
    "Western Samar": ["Samar"],
    "Dinagat Island": ["Dinagat Islands"],
    "Maguindanao": ["Maguindanao del Norte", "Maguindanao del Sur"],
    "General Santos City": [],  # no PSA row: its rice is in South Cotabato
}
# PSA province with no RiceAtlas row -> RiceAtlas province whose calendar it takes
FALLBACK = {"Davao Occidental": "Davao del Sur"}
FIELDS = ["PLANT_ST", "PLANT_PK", "PLANT_END", "HARV_ST", "HARV_PK", "HARV_END"]


def read_dbf(raw: bytes) -> pd.DataFrame:
    """dBase III table (the .dbf of a shapefile), all fields as text."""
    n, header_len, rec_len = struct.unpack("<IHH", raw[4:12])
    fields, pos = [], 32
    while raw[pos] != 0x0D:
        fields.append((raw[pos:pos + 11].split(b"\0")[0].decode(), raw[pos + 16]))
        pos += 32
    rows = []
    for i in range(n):
        rec, p, row = raw[header_len + i * rec_len: header_len + (i + 1) * rec_len], 1, []
        for _, length in fields:
            row.append(rec[p:p + length].decode("latin1").strip())
            p += length
        rows.append(row)
    return pd.DataFrame(rows, columns=[f for f, _ in fields])


def month_of(doy) -> int:
    """Calendar month (1-12) of a day of year (non-leap year)."""
    return (date(2001, 1, 1) + timedelta(days=int(doy) - 1)).month


def province_calendar() -> pd.DataFrame:
    with zipfile.ZipFile(ATLAS) as z:
        atlas = read_dbf(z.read("RiceCalendar_v1.dbf"))
    atlas = atlas[atlas.ISO == "PHL"]
    rows = []
    for _, a in atlas.iterrows():
        for psa in ALIASES.get(a.SUB_REGION, [a.SUB_REGION]):
            for k in (1, 2, 3):
                if float(a[f"HARV_PK{k}"] or 0) <= 0:
                    continue
                rows.append({"province": psa, "riceatlas_name": a.SUB_REGION, "season": k,
                             "season_name": a[f"NAME{k}"], "num_crop": int(a.NUM_CROP),
                             **{f.lower() + "_month": month_of(float(a[f"{f}{k}"])) for f in FIELDS}})
    cal = pd.DataFrame(rows)
    for psa, src in FALLBACK.items():
        cal = pd.concat([cal, cal[cal.province == src].assign(province=psa, riceatlas_name=f"{src} (fallback)")])
    unknown = sorted(set(cal.province) - set(REGION_OF_PROVINCE))
    if unknown:
        raise KeyError(f"RiceAtlas names not matched to a PSA province: {unknown}")
    cal.insert(1, "region_code", cal.province.map(REGION_OF_PROVINCE))
    return cal.sort_values(["region_code", "province", "season"]).reset_index(drop=True)


def harvest_months(s) -> set:
    """Calendar months from harvest start to harvest end (wrapping over the year)."""
    return {(s.harv_st_month - 1 + i) % 12 + 1 for i in range((s.harv_end_month - s.harv_st_month) % 12 + 1)}


def window(s, q: int) -> list:
    """Months (as offsets from the last month of quarter q, 0 = last month) of the growing window
    of season s for the crop harvested in quarter q."""
    q_end = 3 * q
    length = (s.harv_pk_month - s.plant_pk_month) % 12
    harvest = q_end - ((q_end - s.harv_pk_month) % 12)  # harvest peak at or before the quarter end
    if harvest - q_end <= -6:  # nearer to the next cycle
        harvest += 12
    harvest = min(max(harvest, q_end - 2), q_end)  # moved into the harvest quarter
    return [q_end - m for m in range(harvest - length, harvest + 1)]


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    cal = province_calendar()
    cal.to_csv(PROC / "rice_calendar_province.csv", index=False)

    d = read_palay_corn()
    d = d[(d.level == "province") & d.crop.isin(ECOSYSTEMS) & d.period.dt.year.between(*WEIGHT_YEARS)]
    d = d.assign(ecosystem=d.crop.map(ECOSYSTEMS), quarter=d.period.dt.quarter,
                 region_code=d.geo.map(REGION_OF_PROVINCE))
    w = (d.groupby(["ecosystem", "region_code", "geo", "quarter"]).production_t.sum()
         / (WEIGHT_YEARS[1] - WEIGHT_YEARS[0] + 1)).rename("production_t").reset_index()
    w = w[w.production_t > 0].rename(columns={"geo": "province"})

    seasons, missing = [], []
    for _, r in w.iterrows():
        c = cal[cal.province == r.province]
        if c.empty:
            missing.append(r)
            continue
        q_months = {3 * r.quarter - 2, 3 * r.quarter - 1, 3 * r.quarter}
        overlap = c.apply(lambda s: len(harvest_months(s) & q_months), axis=1)
        if overlap.max() > 0:
            s, how = c.loc[overlap.idxmax()], "overlap"
        else:
            dist = c.harv_pk_month.map(lambda m: min((m - 3 * r.quarter + 1) % 12, (3 * r.quarter - 1 - m) % 12))
            s, how = c.loc[dist.idxmin()], "nearest"
        lags = window(s, r.quarter)
        seasons.append({**r, "season": s.season, "season_name": s.season_name, "matched_by": how,
                        "plant_pk_month": s.plant_pk_month, "harv_pk_month": s.harv_pk_month,
                        "lag_first": max(lags), "lag_last": min(lags), "lags": lags})
    seasons = pd.DataFrame(seasons)
    seasons["share"] = seasons.production_t / seasons.groupby(["ecosystem", "region_code", "quarter"]).production_t.transform("sum")
    seasons.drop(columns="lags").to_csv(PROC / "rice_season_by_quarter.csv", index=False)

    win = seasons.explode("lags").rename(columns={"lags": "lag"})
    win = (win.groupby(["ecosystem", "region_code", "quarter", "lag"]).share.sum().rename("weight")
           .reindex(pd.MultiIndex.from_product([sorted(win.ecosystem.unique()), sorted(win.region_code.unique()),
                                                range(1, 5), range(12)],
                                               names=["ecosystem", "region_code", "quarter", "lag"]), fill_value=0.0)
           .reset_index())
    win = win[win.set_index(["ecosystem", "region_code", "quarter"]).index.isin(
        seasons.set_index(["ecosystem", "region_code", "quarter"]).index)]
    win["calendar_month"] = (3 * win.quarter - win.lag - 1) % 12 + 1
    win["weight"] = win.weight.round(4)
    win.to_csv(PROC / "rice_growing_window.csv", index=False)

    # coverage: production with no calendar, and production matched to the 'nearest' season
    total = w.groupby("ecosystem").production_t.sum()
    miss = pd.DataFrame(missing)
    cov = pd.DataFrame({
        "production_t_per_year": total,
        "share_no_calendar": (miss.groupby("ecosystem").production_t.sum() / total if len(miss) else 0.0),
        "share_matched_nearest": seasons[seasons.matched_by == "nearest"].groupby("ecosystem").production_t.sum() / total,
    }).fillna(0.0).round(4)
    cov["provinces_no_calendar"] = (miss.groupby("ecosystem").province.apply(lambda s: ", ".join(sorted(set(s))))
                                    if len(miss) else "")
    cov.to_csv(TAB / "rice_calendar_coverage.csv")

    print(f"RiceAtlas: {cal.riceatlas_name.nunique()} calendars -> {cal.province.nunique()} PSA provinces, "
          f"{cal.region_code.nunique()} regions")
    print(cov.to_string())
    main_win = win[(win.ecosystem == "total") & (win.weight >= 0.5)]
    span = main_win.groupby(["region_code", "quarter"]).lag.agg(["max", "min"])
    print("\nTotal palay: months with weight >= 0.5 (lag first-last, 0 = last month of harvest quarter)")
    print(span.unstack("quarter").to_string())


if __name__ == "__main__":
    main()
