"""Shocks of the direct approach, methodology v5 Section 3.5.

For a climate-mode path x^S (quarterly RONI and DMI over the quarters of the scenario,
zero = neutral before and after), with the exposure controls at "no event" in both runs:

  S_{c,r,q} = 1 - y_{c,r,q}(x^S) / y_{c,r,q}(x^0)                                  (12)
            = 1 - exp( climate terms of region r in quarter q under x^S )          (13)

(region, seasonal, trend and control terms cancel). The climate terms are those of the
estimated specification (estimation.direct.climate_design): blended lags of RONI (split
into El Nino and La Nina parts if the specification does so) and DMI, regional effects,
the wet-season shift by the quarter of the year of q, and, if the effects changed over
time, the effect for today's conditions (after the break).

National and crop aggregation with shares of neutral production (x^0, controls at no
event, trend at today's climate t* = the last full year of data):

  S_{c,q} = sum_r w_{c,r,q} S_{c,r,q},  w_{c,r,q} = y_{c,r,q}(x^0) / sum_r' y_{c,r',q}(x^0)  (13a)

and, for palay, irrigated and rainfed combined with their neutral production shares.
Seasonal scaling for DEFINE-PH, whose quarters carry a quarter of annual output each:

  S^D_{c,q} = S_{c,q} * 4 y_{c,q}(x^0) / sum_{q' in year(q)} y_{c,q'}(x^0)             (13b)

Shocks are delivered for every quarter of the path and the K quarters after it.
"""
import numpy as np
import pandas as pd

from estimation.direct import Spec, climate_design, is_climate

T_STAR_YEAR = 2025  # today's climate: last full year of data (the spline trend is not
                    # evaluated beyond the data)


def scenario_quarters(path: pd.DataFrame, K: int) -> pd.PeriodIndex:
    """Quarters of the path and the K quarters after it. path: index pd.Period('Q'),
    columns roni, dmi."""
    return pd.period_range(path.index.min(), path.index.max() + K, freq="Q")


def scenario_frame(path: pd.DataFrame, regions, K: int, first_lag: int = 1):
    """Rows region x scenario quarter, with the lagged path values (zero outside the
    path). Rows carry `period` set to today's year with the scenario quarter's quarter of
    the year, so that the season shift applies and the effect after a break is today's."""
    qs = scenario_quarters(path, K)
    full = path.reindex(pd.period_range(qs.min() - (first_lag + K), qs.max(), freq="Q")).fillna(0.0)
    lagsR = np.array([[full.roni.get(q - j, 0.0) for j in range(first_lag, first_lag + K)] for q in qs])
    lagsD = np.array([[full.dmi.get(q - j, 0.0) for j in range(first_lag, first_lag + K)] for q in qs])
    rows = pd.DataFrame([(r, q) for q in qs for r in regions], columns=["region_code", "scenario_q"])
    rows["q"] = rows.scenario_q.dt.quarter
    rows["period"] = [f"{T_STAR_YEAR}Q{k}" for k in rows.q]
    pos = {q: i for i, q in enumerate(qs)}
    idx = rows.scenario_q.map(pos).to_numpy()
    return rows, lagsR[idx], lagsD[idx]


def regional_shocks(params: pd.Series, spec: Spec, theta_R: float, theta_D: float,
                    path: pd.DataFrame, regions, K: int) -> pd.DataFrame:
    """Eq. (13): S by region and scenario quarter."""
    rows, LR, LD = scenario_frame(path, regions, K, spec.first_lag)
    C = climate_design(rows, LR, LD, theta_R, theta_D, spec)
    cols = [c for c in C.columns if c in params.index]
    rows["S"] = 1 - np.exp(C[cols].to_numpy(float) @ params[cols].to_numpy())
    return rows[["region_code", "scenario_q", "q", "S"]]


def neutral_production(params: pd.Series, X: pd.DataFrame, d: pd.DataFrame,
                       controls: list[str], year: int = T_STAR_YEAR) -> pd.Series:
    """y(x^0) by region and quarter of the year in `year`: the model's prediction with the
    climate terms at zero and the exposure controls at "no event" (break dummies, which
    describe today's level, are kept)."""
    m = (d["period"].astype(str).str[:4].astype(int) == year).to_numpy()
    Xv = X.loc[m, params.index].copy()
    Xv[[c for c in Xv.columns if is_climate(c) or c in controls]] = 0.0
    y0 = np.exp(Xv.to_numpy(float) @ params.to_numpy())
    return pd.Series(y0, index=pd.MultiIndex.from_arrays([d.loc[m, "region_code"].values,
                                                          d.loc[m, "q"].values],
                                                         names=["region_code", "q"]))


def aggregate(reg: pd.DataFrame, y0: pd.Series) -> pd.DataFrame:
    """Eq. (13a): national S by scenario quarter, with neutral production shares; also
    returns the national neutral production of the quarter (y0_q)."""
    r = reg.merge(y0.rename("y0").reset_index(), on=["region_code", "q"], how="left")
    r["y0"] = r["y0"].fillna(0.0)  # region-quarters with no production
    g = r.groupby(["scenario_q", "q"])
    out = pd.DataFrame({"S": g.apply(lambda x: (x.S * x.y0).sum() / x.y0.sum()),
                        "y0_q": g.y0.sum()}).reset_index()
    return out


def seasonal_scaling(nat: pd.DataFrame, y0_by_q: pd.Series) -> pd.Series:
    """Eq. (13b): S^D = S * 4 * y0_q / sum of y0 over the four quarters of the year."""
    share = y0_by_q / y0_by_q.sum()
    return nat["S"] * 4 * nat["q"].map(share).to_numpy()


def combine(parts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine crops (e.g. irrigated and rainfed palay) with their neutral production
    shares in each quarter: S = sum_c y0_{c,q} S_{c,q} / sum_c y0_{c,q}."""
    a = pd.concat([p.assign(crop=c) for c, p in parts.items()])
    g = a.groupby(["scenario_q", "q"])
    return pd.DataFrame({"S": g.apply(lambda x: (x.S * x.y0_q).sum() / x.y0_q.sum()),
                         "y0_q": g.y0_q.sum()}).reset_index()
