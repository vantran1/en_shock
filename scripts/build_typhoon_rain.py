"""Typhoon rainfall control by region and quarter, 1987-2025 (src/hazards/typhoon_rain.py).

Requested by Alper (27 Nov 2026) as an alternative to dropping the Luzon quarters of late 2015
(write-up section 2.6): rain that falls while a tropical cyclone centre is within 500 km
(IBTrACS), from ERA5 total precipitation on the 0.25 deg grid of Van's Stage 1, cropland-weighted
over the 349 kept cells. PROVISIONAL.

Input: a folder of ERA5 NetCDF files with hourly or daily 'tp' (m) covering 1986Q4-2025 (the
previous quarter of 1987Q1 is needed for the lag), area at least 4-22N, 116-127.5E. Not in git.

Run:  python scripts/build_typhoon_rain.py --precip-dir <folder> [--radius-km 500]
Writes data/processed/typhoon_rain_region_quarter.csv   region x quarter: tp_mm, tc_rain_mm, tc_days,
                                                         tc_rain_share, each with _lag1
       outputs/tables/typhoon_rain_checks.csv           sanity checks (share of annual rain from
                                                         cyclones by region; top region-quarters)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from hazards.typhoon_rain import RADIUS_KM, build  # noqa: E402

PROC, TAB = ROOT / "data/processed", ROOT / "outputs/tables"


def checks(r: pd.DataFrame) -> pd.DataFrame:
    y = r[r.period.str[:4].astype(int).between(1987, 2025)]
    share = (y.groupby("region_code")[["tc_rain_mm", "tp_mm"]].sum()
             .assign(value=lambda d: d.tc_rain_mm / d.tp_mm * 100)[["value"]]
             .assign(check="share of 1987-2025 rain from cyclones (%)").reset_index())
    top = (y.nlargest(15, "tc_rain_mm")[["region_code", "period", "tc_rain_mm"]]
           .rename(columns={"tc_rain_mm": "value"}).assign(check="largest typhoon rain (mm)"))
    return pd.concat([share, top], ignore_index=True)


def main(precip_dir: str, radius_km: float):
    files = sorted(Path(precip_dir).expanduser().glob("*.nc"))
    if not files:
        raise FileNotFoundError(f"no .nc files in {precip_dir}")
    r, _ = build(files, radius_km)
    r = r[r.period >= "1987Q1"]
    if r[["tc_rain_mm_lag1"]].isna().any().any():
        print("warning: missing previous quarter for", r[r.tc_rain_mm_lag1.isna()].period.unique()[:5],
              "(the files should start in 1986Q4)")
    r.assign(radius_km=radius_km, status="provisional").round(4).to_csv(
        PROC / "typhoon_rain_region_quarter.csv", index=False)
    c = checks(r)
    c.round(2).to_csv(TAB / "typhoon_rain_checks.csv", index=False)
    pd.set_option("display.width", 200)
    print(c.round(1).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--precip-dir", required=True)
    ap.add_argument("--radius-km", type=float, default=RADIUS_KM)
    a = ap.parse_args()
    main(a.precip_dir, a.radius_km)
