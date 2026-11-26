"""Stage 2 features from observed weather: Van's Stage-1 variables (`<var>_obs`, ERA5-Land,
16 regions, cropland weights, 349 cells; hindcast of dev_Van f6ddf65, 25 Nov 2026, with the daily
variables) summarised over each crop's growing window
(methodology v5 Section 3.4; estimation.stage2.window_features).

Series and calendars: irrigated and rainfed palay take their own RiceAtlas windows
(data/processed/rice_growing_window.csv); corn takes the GGCMI rainfed calendar
(data/processed/corn_growing_window.csv; PSA does not split corn by water supply).
Vegetables and root crops (VR) and perennial fruits (PF) have no crop calendar; v5 Section 3.4 sets
"longer" fixed windows for them. Chosen (Ginevra, 26 Nov 2026): VR 6 months (the harvest quarter and
the one before), PF 12 months (the harvest quarter and the three before: perennials respond to water
over a whole year), the same in every region and quarter, all months with weight 1.

Variables: the 11 monthly ones (T, VPD, P, SM_RZ, SM_DEEP, PET, E, SPEI3, CWB3, RS, RO) and the 12
daily ones of v5 Table 2 computed from hourly ERA5 (mean daily max and min temperature, afternoon
VPD, extreme degree-days and hot days above 30, 32 and 35 degC, dry days, longest dry spell,
heavy-rain days). Features: window means of each variable (weighted by the share of the quarter's
harvest in the field each month) and extremes over the months with at least half of it in the
field (hottest month T_max, TMAX_max, VPD_max; driest P_min, SM_RZ_min, SPEI3_min; longest dry
spell LDRY_max). The monthly variables are identical to the earlier hindcast (18fe296), so the
monthly features do not change.

Run:  python scripts/build_stage2_features.py
Writes data/processed/stage2_features.csv   series x region x harvest quarter, 1987Q1-2025Q4
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from estimation.stage2 import FEATURES, observed_weather, window_features  # noqa: E402

HIST = ROOT / "data/reference/van/f6ddf65/agriculture/hist_fitted_16regions.csv"
PROC = ROOT / "data/processed"
FIRST, LAST = "1987Q1", "2025Q4"


FIXED_WINDOW_MONTHS = {"vr": 6, "pf": 12}


def fixed_window(months: int, regions) -> pd.DataFrame:
    """Window of the last `months` months up to the end of the harvest quarter (lags 0..months-1),
    weight 1, every region and quarter."""
    return pd.DataFrame([(r, q, lag, 1.0) for r in regions for q in range(1, 5) for lag in range(months)],
                        columns=["region_code", "quarter", "lag", "weight"])


def calendars() -> dict[str, pd.DataFrame]:
    rice = pd.read_csv(PROC / "rice_growing_window.csv")
    corn = pd.read_csv(PROC / "corn_growing_window.csv")
    regions = sorted(rice.region_code.unique())
    return {"irrigated": rice[rice.ecosystem == "irrigated"],
            "rainfed": rice[rice.ecosystem == "rainfed"],
            "corn": corn[corn.calendar == "rainfed"],
            **{s_: fixed_window(m, regions) for s_, m in FIXED_WINDOW_MONTHS.items()}}


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
