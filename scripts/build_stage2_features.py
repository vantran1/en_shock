"""Stage 2 features from observed weather: Van's Stage-1 variables (`<var>_obs`, ERA5-Land,
16 regions, cropland weights, 349 cells) summarised over each crop's growing window
(methodology v5 Section 3.4; estimation.stage2.window_features).

Series and calendars: irrigated and rainfed palay take their own RiceAtlas windows
(data/processed/rice_growing_window.csv); corn takes the GGCMI rainfed calendar
(data/processed/corn_growing_window.csv; PSA does not split corn by water supply).
VR and PF are not built yet (v5: longer, fixed windows; data from 2010).

Monthly variables only (T, VPD, P, SM_RZ, SM_DEEP, PET, E, SPEI3, CWB3, RS, RO): the daily
variables of v5 Table 2 (Tmax/Tmin, extreme degree-days, dry spells, heavy-rain days) are not in
Van's file yet. Features: window means of each variable (weighted by the share of the quarter's
harvest in the field each month) and extremes over the months with at least half of it in the
field (hottest month T_max, VPD_max; driest P_min, SM_RZ_min, SPEI3_min).

Run:  python scripts/build_stage2_features.py
Writes data/processed/stage2_features.csv   series x region x harvest quarter, 1987Q1-2025Q4
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from estimation.stage2 import FEATURES, observed_weather, window_features  # noqa: E402

HIST = ROOT / "data/reference/van/hist_fitted_16regions_roni_18fe296.csv"
PROC = ROOT / "data/processed"
FIRST, LAST = "1987Q1", "2025Q4"


def calendars() -> dict[str, pd.DataFrame]:
    rice = pd.read_csv(PROC / "rice_growing_window.csv")
    corn = pd.read_csv(PROC / "corn_growing_window.csv")
    return {"irrigated": rice[rice.ecosystem == "irrigated"],
            "rainfed": rice[rice.ecosystem == "rainfed"],
            "corn": corn[corn.calendar == "rainfed"]}


def main():
    w = observed_weather(pd.read_csv(HIST))
    out = []
    for series, win in calendars().items():
        f = window_features(w, win)
        f = f[(f.period >= FIRST) & (f.period <= LAST)]
        out.append(f.assign(series=series))
    out = pd.concat(out)[["series", "region_code", "period"] + FEATURES]
    assert not out[FEATURES].isna().any().any()
    out.round(5).to_csv(PROC / "stage2_features.csv", index=False)
    print(out.groupby("series").size(), "\n", out.groupby("series")[["T", "P", "SM_RZ"]].mean().round(3))


if __name__ == "__main__":
    main()
