"""Corn growing windows by region and harvest quarter, for the Stage 2 weather features (as
scripts/build_rice_calendar.py for rice).

Source: GGCMI Phase 3 crop calendar, maize (Jägermeyr et al. 2021, Nature Food 2:873-885; Zenodo
doi:10.5281/zenodo.5062513, v1.01): planting and maturity day on a 0.5 degree grid, rainfed and
irrigated. For the Philippines the data come from SAGE (Sacks et al. 2010), Dimou et al. (2018),
MIRCA2000 and Iizumi et al. (2019). The calendar has ONE season per cell, mostly the wet-season crop
(planted around May, harvested July-August); the dry-season crop is largely missing.

Steps
1. Each ERA5 cell of the 16 regions (Van's cropland weights, data/reference/van/cropland_weights)
   takes the calendar of the nearest GGCMI cell with data (ties: lowest index).
2. Harvest quarter of the GGCMI season: the quarter holding the maturity month. Window from the
   planting month to the maturity month (agriculture.calendar.window), matched_by = 'ggcmi'.
3. Other quarters (no GGCMI season harvested): a standard cycle of the same length as the cell's
   GGCMI season, harvested in the middle month of the quarter, matched_by = 'standard_cycle'.
4. Regional window: cells weighted by their share of the region's cropland (w_cropland). The weight
   of a month is the share of the region's cropland whose crop was in the field that month.
   lag = months before the last month of the harvest quarter (0 = last month).
Rainfed is the main calendar (PSA does not split corn by water supply, and most corn is rainfed);
irrigated is written alongside as a check.

Run:  python scripts/build_corn_calendar.py
Writes
- data/processed/corn_calendar_cell.csv        ERA5 cell: GGCMI cell used, planting / maturity month
- data/processed/corn_growing_window.csv       calendar x region x harvest quarter x lag: weight, matched_by
- outputs/tables/corn_calendar_coverage.csv    share of PSA corn production per quarter covered by GGCMI
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

from agriculture.calendar import month_of, window  # noqa: E402
from agriculture.psa_openstat import read_palay_corn  # noqa: E402
from agriculture.regions import REGION_OF_PROVINCE  # noqa: E402

GGCMI = ROOT / "data/agriculture/ggcmi/mai_{}_ggcmi_crop_calendar_phase3_v1.01.nc4"
WEIGHTS = ROOT / "data/reference/van/cropland_weights/cropland_weights_16regions.csv"
PROC, TAB = ROOT / "data/processed", ROOT / "outputs/tables"
WEIGHT_YEARS = (2016, 2025)
CALENDARS = {"rainfed": "rf", "irrigated": "ir"}
SOURCES = {1: "MIRCA2000", 2: "SAGE", 3: "Iizumi et al. 2019", 5: "Dimou et al. 2018"}


def cell_calendar(cells: pd.DataFrame, code: str) -> pd.DataFrame:
    """Planting and maturity month of the nearest GGCMI cell with data, for each ERA5 cell."""
    with xr.open_dataset(str(GGCMI).format(code), decode_times=False) as ds:
        g = ds.sel(lat=slice(23, 3), lon=slice(114, 129))[["planting_day", "maturity_day", "data_source_used"]]
        g = g.to_dataframe().dropna().reset_index()
    out = []
    for _, c in cells.iterrows():
        d = np.hypot(g.lat - c.lat, (g.lon - c.lon) * np.cos(np.radians(c.lat)))
        n = g.loc[d.idxmin()]  # idxmin returns the first minimum: lowest index on ties
        out.append({"cell": c.cell, "ggcmi_lat": n.lat, "ggcmi_lon": n.lon,
                    "distance_deg": round(float(d.min()), 3),
                    "plant_month": month_of(n.planting_day), "maturity_month": month_of(n.maturity_day),
                    "source": SOURCES.get(int(n.data_source_used), str(int(n.data_source_used)))})
    return pd.DataFrame(out)


def cell_window(plant: int, maturity: int, q: int):
    """Lags of the window for the crop harvested in quarter q, and how it was set."""
    if (maturity - 1) // 3 + 1 == q:
        return window(plant, maturity, q), "ggcmi"
    length = (maturity - plant) % 12
    return [1 + k for k in range(length + 1)], "standard_cycle"  # harvest in the middle month (lag 1)


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    w = pd.read_csv(WEIGHTS)
    w = w[w.w_cropland > 0][["cell", "lat", "lon", "code", "w_cropland"]].rename(columns={"code": "region_code"})
    cells = w.drop_duplicates("cell")[["cell", "lat", "lon"]]

    cal_rows, win_rows = [], []
    for name, code in CALENDARS.items():
        cal = cell_calendar(cells, code).assign(calendar=name)
        cal_rows.append(cal)
        cw = w.merge(cal, on="cell")
        for q in range(1, 5):
            for _, c in cw.iterrows():
                lags, how = cell_window(c.plant_month, c.maturity_month, q)
                for lag in lags:
                    win_rows.append((name, c.region_code, q, lag, c.w_cropland, how))
    cal = pd.concat(cal_rows)
    cal.to_csv(PROC / "corn_calendar_cell.csv", index=False)

    win = pd.DataFrame(win_rows, columns=["calendar", "region_code", "quarter", "lag", "w", "matched_by"])
    share_std = (win[win.matched_by == "standard_cycle"].drop_duplicates(["calendar", "region_code", "quarter", "w"])
                 .groupby(["calendar", "region_code", "quarter"]).w.sum())
    grid = pd.MultiIndex.from_product([list(CALENDARS), sorted(w.region_code.unique()), range(1, 5), range(12)],
                                      names=["calendar", "region_code", "quarter", "lag"])
    out = win.groupby(["calendar", "region_code", "quarter", "lag"]).w.sum().rename("weight").reindex(grid, fill_value=0.0)
    out = out.reset_index()
    out["calendar_month"] = (3 * out.quarter - out.lag - 1) % 12 + 1
    out["weight"] = out.weight.round(4)
    out = out.merge(share_std.rename("share_standard_cycle").round(4).reset_index(),
                    on=["calendar", "region_code", "quarter"], how="left").fillna({"share_standard_cycle": 0.0})
    out.to_csv(PROC / "corn_growing_window.csv", index=False)

    # coverage: PSA corn production per quarter whose window comes from GGCMI rather than the standard cycle
    d = read_palay_corn()
    d = d[(d.level == "province") & (d.crop == "Corn") & d.period.dt.year.between(*WEIGHT_YEARS)]
    prod = (d.assign(region_code=d.geo.map(REGION_OF_PROVINCE), quarter=d.period.dt.quarter)
            .groupby(["region_code", "quarter"]).production_t.sum().rename("p").reset_index())
    rows = []
    for name in CALENDARS:
        s = share_std.loc[name].rename("std").reset_index()
        m = prod.merge(s, on=["region_code", "quarter"], how="left").fillna({"std": 0.0})
        for q in range(1, 5):
            mq = m[m.quarter == q]
            rows.append({"calendar": name, "quarter": q, "share_of_annual_production": mq.p.sum() / prod.p.sum(),
                         "share_from_ggcmi": (mq.p * (1 - mq["std"])).sum() / mq.p.sum()})
    cov = pd.DataFrame(rows).round(3)
    cov.to_csv(TAB / "corn_calendar_coverage.csv", index=False)

    rf = cal[cal.calendar == "rainfed"]
    print(f"{rf.cell.nunique()} ERA5 cells; nearest GGCMI cell up to {rf.distance_deg.max():.2f} deg away")
    print("rainfed planting -> maturity month:",
          rf.groupby(["plant_month", "maturity_month"]).size().sort_values(ascending=False).head(6).to_dict())
    print("sources:", rf.source.value_counts().to_dict())
    print("irrigated differs from rainfed in",
          int((cal[cal.calendar == "irrigated"].set_index("cell")[["plant_month", "maturity_month"]]
               != rf.set_index("cell")[["plant_month", "maturity_month"]]).any(axis=1).sum()), "cells")
    print(cov.to_string(index=False))


if __name__ == "__main__":
    main()
