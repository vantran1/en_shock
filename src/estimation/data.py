"""Estimation data for the direct models, one function per crop series (shared by rice and
corn, and later VR and PF).

Series: 'irrigated', 'rainfed' (palay, data/processed/rice_region_quarter.csv), 'corn',
'corn_white', 'corn_yellow' (data/processed/crop_region_quarter.csv), 16 regions,
1987Q1-2025Q4; and the calorie indices of vegetables and root crops ('vr', 'vr_noroot') and
perennial fruits ('pf', 'pf_nobanana', 'pf_nocavendish'), 2010Q1-2025Q4, whose
"production" is the calorie energy of the index's crops (billion kcal; the index is this
energy divided by a fixed base, so the proportional effects are the same). Controls (by region, quarter and the same series' production weights):
typhoon exposure by PAGASA category (current and previous quarter), flood share (current
and previous), earthquake, eruption (VEI >= 3), Pinatubo 1991.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from climate.indices import quarterly
from estimation.direct import lag_matrix

PROC = Path(__file__).resolve().parents[2] / "data" / "processed"
TY = ["ty_share_ts", "ty_share_ty", "ty_share_sty"]
CONTROLS = TY + [f"{c}_lag1" for c in TY] + ["flood_share", "flood_share_lag1",
                                              "eq", "eruption", "pinatubo_1991"]
GROUP = {"irrigated": "palay", "rainfed": "palay", "corn": "corn", "corn_white": "corn",
         "corn_yellow": "corn", "vr": "vr", "vr_noroot": "vr", "pf": "pf", "pf_nobanana": "pf",
         "pf_nocavendish": "pf"}
LAST = "2025Q4"
WEIGHT_YEARS = (2016, 2025)
CHECKS = {"kanlaon": {"eruption": "eruption_check_kanlaon2024"}}


def production(series: str) -> pd.DataFrame:
    """region_code, period ('YYYYQn'), production_t for a series, 1987Q1-2025Q4 (VR and PF:
    calorie energy, 2010Q1-2025Q4)."""
    if GROUP[series] == "palay":
        p = pd.read_csv(PROC / "rice_region_quarter.csv")
        p = p[p.ecosystem == series][["region_code", "period", "production_t"]]
    else:
        variable = "energy_bkcal" if GROUP[series] in ("vr", "pf") else "production_t"
        p = pd.read_csv(PROC / "crop_region_quarter.csv")
        p = p[(p.series == series) & (p.variable == variable)]
        p = p.rename(columns={"value": "production_t"})[["region_code", "period", "production_t"]]
    return p[p.period <= LAST].reset_index(drop=True)


def build(series: str, replace: dict | None = None) -> pd.DataFrame:
    """Production with the controls, quarter of the year q and time t (decades from 2006).
    replace: {control: column to use instead}, e.g. CHECKS['kanlaon']."""
    p = production(series)
    key = "ecosystem"
    ty = pd.read_csv(PROC / "typhoon_region_quarter.csv")
    fl = pd.read_csv(PROC / "flood_region_quarter.csv")
    geo = pd.read_csv(PROC / "geophysical_region_quarter.csv")
    ty = ty[ty[key] == series][["region_code", "period"] + TY + [f"{c}_lag1" for c in TY]]
    fl = fl[fl[key] == series][["region_code", "period", "flood_share", "flood_share_lag1"]]
    p = (p.merge(ty, on=["region_code", "period"], validate="1:1")
          .merge(fl, on=["region_code", "period"], validate="1:1")
          .merge(geo, on=["region_code", "period"], how="left", validate="1:1"))
    for new, old in (replace or {}).items():
        p[new] = p[old]
    p[["eq", "eruption", "pinatubo_1991"]] = p[["eq", "eruption", "pinatubo_1991"]].fillna(0)
    per = pd.PeriodIndex(p.period, freq="Q")
    p["q"] = per.quarter
    p["t"] = (per.year + (per.quarter - 1) / 4 - 2006) / 10  # decades, centred
    return p.sort_values(["region_code", "period"]).reset_index(drop=True)


def index_lags(name: str, periods, K: int = 4, first_lag: int = 1) -> np.ndarray:
    q = quarterly(name)
    q.index = q.index.astype(str)
    lm = lag_matrix(q, K, first_lag).reindex(periods)
    if lm.isna().any().any():
        raise ValueError(f"{name}: missing lagged values")
    return lm.to_numpy(float)


# PPML outcome units: thousand t (palay, corn), billion kcal (VR, PF). The estimates do not
# depend on the units, but the deviance (and so the quasi-BIC deviance + k ln n used to
# compare specifications) does; these units put all crops on a similar scale (tens to
# hundreds per region and quarter).
PPML_SCALE = {"palay": 1000, "corn": 1000, "vr": 1, "pf": 1}


def sample(p: pd.DataFrame, model: str, group: str = "palay"):
    """PPML: drop region x quarter cells that are always zero; log-LS: drop zero quarters.
    Returns the sample and y (PPML: production / PPML_SCALE[group]; log-LS: log production)."""
    if model == "ppml":
        cell = p.region_code + p.q.astype(str)
        d = p[p.groupby(cell).production_t.transform("sum") > 0]
        return d.reset_index(drop=True), (d.production_t / PPML_SCALE[group]).reset_index(drop=True)
    d = p[p.production_t > 0].reset_index(drop=True)
    return d, np.log(d.production_t)


def weights(series: str) -> pd.Series:
    """Regions' shares of the series' production, 2016-2025."""
    p = production(series)
    p = p[p.period.str[:4].astype(int).between(*WEIGHT_YEARS)]
    w = p.groupby("region_code").production_t.sum()
    return w / w.sum()
