"""Direct approach of methodology v5, Eqs. (4)-(6), for any crop series.

  ln y_{c,r,q} = alpha_{c,r} + sum_{j=1..K} [ B^R_{c,r} w_j(theta^R) RONI_{q-j}
                                             + B^D_{c,r} w_j(theta^D) DMI_{q-j} ]
                 + gamma' X_{r,q} + s_{c,r,qtr(q)} + tau_{c,r} q + e                 (4)

  w_j(theta) = C(K-1, j-1) theta^(K-j) (1-theta)^(j-1),  j = 1..K,  sum_j w_j = 1   (5)
  (theta near 1: weight on the first lag; near 0: on the last)

  (theta^R, theta^D) = argmin over Theta x Theta of L(theta^R, theta^D),
  Theta = {0.05, 0.10, ..., 0.95}                                                   (6)

with L the residual sum of squares (log-linear least squares) or the deviance (Poisson
pseudo-maximum likelihood, production in levels). For given timing parameters, (4) is
linear in the rest once the lagged indices are blended with the weights (5): the blended
regressor z_q(theta) = sum_j w_j(theta) x_{q-j} enters interacted with region dummies, so
the total effects B_{c,r} differ by region and the timing is common to all regions.
alpha_r + s_{r,qtr} = region x quarter-of-year effects; tau_r = one linear trend per region.
Lag coefficients: beta_{r,j} = B_r w_j(theta).

The choices v5 lists as still being tested are switches of `Spec` (defaults = Eq. 4):
- split:   El Nino and La Nina with separate total effects (RONI+ = max(RONI, 0) and
           RONI- = min(RONI, 0), lag by lag; same timing parameter);
- season:  effects differ in wet-season harvest quarters (Q3-Q4): a common shift of each
           total effect in those quarters;
- trend:   'region' (Eq. 4), 'region_quarter' (one trend per region and quarter of year),
           'region_spline' (smooth trend per region: centred natural cubic spline, 3 df);
- lags:    K lags starting at first_lag (v5: 1..4 for palay, corn, VR; up to 6 for PF;
           first_lag = 0 includes the current quarter);
- pooling: total effects by 'region' (Eq. 4), by island group ('island': Luzon, Visayas,
           Mindanao) or one 'national' effect.
Not on v5's list, suggested by the episode validation (1997-98 large losses, 2015-16 none):
- effect_break: the RONI effects (El Nino and La Nina) shift from this year on, by a
           common amount in all regions (test of whether the effect changed over time);
- dmi:     False leaves the DMI out (RONI only). Tested because DMI and RONI move together
           in the quarters when El Nino builds (correlation 0.46 in Q3, 0.62 in Q4, 1987-2025)
           and the DMI timing is poorly identified.
- effect_trend: the RONI effects change linearly over time instead (gradual decline), by
           a common rate in all regions; time is centred on today (t_today), so the total
           effects B are today's effects. t is the panel's time variable (decades from
           2006), so t_today = 1.9 is 2025.

Climate columns are named B<idx>_<group> (total effects), S<idx>_wet (season shift) and
S<idx>_post (shift after effect_break), S<idx>_trend (change per decade, effect_trend), with
idx R (RONI), RP / RN (El Nino / La Nina) or D (DMI).

Standard errors: Driscoll-Kraay (estimation.panel), conditional on the selected timing
parameters; v5 computes the confidence intervals of the shocks by a block bootstrap over
years that re-estimates the timing parameters in each replication (to be added with the
shocks).
"""
from dataclasses import dataclass
from math import comb

import numpy as np
import pandas as pd
import statsmodels.api as sm
from patsy import dmatrix

from estimation.panel import fit

THETA_GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)
ISLAND = {"CAR": "Luzon", "R01": "Luzon", "R02": "Luzon", "R03": "Luzon", "R04A": "Luzon",
          "MIMAROPA": "Luzon", "R05": "Luzon", "R06": "Visayas", "R07": "Visayas",
          "R08": "Visayas", "R09": "Mindanao", "R10": "Mindanao", "R11": "Mindanao",
          "R12": "Mindanao", "R13": "Mindanao", "BARMM": "Mindanao"}
WET_QUARTERS = (3, 4)


@dataclass(frozen=True)
class Spec:
    name: str = "base"
    K: int = 4
    first_lag: int = 1
    split: bool = False
    season: bool = False
    trend: str = "region"
    pooling: str = "region"
    effect_break: int | None = None
    effect_trend: bool = False
    t_today: float = 1.9
    dmi: bool = True


def binomial_weights(theta: float, K: int) -> np.ndarray:
    j = np.arange(1, K + 1)
    return np.array([comb(K - 1, i - 1) for i in j]) * theta ** (K - j) * (1 - theta) ** (j - 1)


def lag_matrix(index_q: pd.Series, K: int, first_lag: int = 1) -> pd.DataFrame:
    """Columns lag<first>..lag<first+K-1> of a quarterly index (index: 'YYYYQn' strings)."""
    return pd.DataFrame({f"lag{j}": index_q.shift(j) for j in range(first_lag, first_lag + K)},
                        index=index_q.index)


def blended(lags: np.ndarray, theta: float) -> np.ndarray:
    """z_q(theta) = sum_j w_j(theta) x_{q-j}; lags: n x K array aligned with the panel."""
    return lags @ binomial_weights(theta, lags.shape[1])


def groups(p: pd.DataFrame, pooling: str) -> pd.Series:
    if pooling == "region":
        return p["region_code"]
    if pooling == "island":
        return p["region_code"].map(ISLAND)
    if pooling == "national":
        return pd.Series("all", index=p.index)
    raise ValueError(pooling)


def base_design(p: pd.DataFrame, controls: list[str], extra: pd.DataFrame | None = None,
                trend: str = "region") -> pd.DataFrame:
    """Everything except the climate terms: region x quarter effects, trends, controls
    (and extra columns such as break dummies). p needs region_code, q, t."""
    rq = p["region_code"] + "_q" + p["q"].astype(str)
    fe = pd.get_dummies(rq, prefix="fe", dtype=float)
    if trend == "region":
        tr = pd.get_dummies(p["region_code"], prefix="tr", dtype=float).mul(p["t"].values, axis=0)
    elif trend == "region_quarter":
        tr = fe.mul(p["t"].values, axis=0).add_prefix("tr_")
    elif trend == "region_spline":
        basis = np.asarray(dmatrix("cr(t, df=3, constraints='center') - 1", {"t": p["t"].values}))
        reg = pd.get_dummies(p["region_code"], dtype=float)
        tr = pd.concat([reg.mul(basis[:, k], axis=0).add_prefix(f"tr{k}_")
                        for k in range(basis.shape[1])], axis=1)
    else:
        raise ValueError(trend)
    parts = [fe, tr, p[controls]]
    if extra is not None and extra.shape[1]:
        parts.append(extra)
    return pd.concat(parts, axis=1)


def climate_design(p: pd.DataFrame, lagsR: np.ndarray, lagsD: np.ndarray, tR: float, tD: float,
                   spec: Spec = Spec()) -> pd.DataFrame:
    """Blended indices interacted with the pooling groups (+ the season shift)."""
    if spec.split:
        terms = {"RP": blended(np.clip(lagsR, 0, None), tR),
                 "RN": blended(np.clip(lagsR, None, 0), tR)}
    else:
        terms = {"R": blended(lagsR, tR)}
    if spec.dmi:
        terms["D"] = blended(lagsD, tD)
    g = pd.get_dummies(groups(p, spec.pooling), dtype=float)
    parts = [g.mul(z, axis=0).add_prefix(f"B{k}_") for k, z in terms.items()]
    if spec.season:
        wet = p["q"].isin(WET_QUARTERS).to_numpy(float)
        parts.append(pd.DataFrame({f"S{k}_wet": z * wet for k, z in terms.items()}, index=p.index))
    if spec.effect_break is not None:
        post = np.asarray(pd.PeriodIndex(p["period"].astype(str), freq="Q").year
                          >= spec.effect_break, dtype=float)
        parts.append(pd.DataFrame({f"S{k}_post": z * post for k, z in terms.items()
                                   if k.startswith("R")}, index=p.index))
    if spec.effect_trend:
        dt = p["t"].to_numpy(float) - spec.t_today
        parts.append(pd.DataFrame({f"S{k}_trend": z * dt for k, z in terms.items()
                                   if k.startswith("R")}, index=p.index))
    return pd.concat(parts, axis=1)


def is_climate(col: str) -> bool:
    return col[:2] in ("BR", "BD", "SR", "SD")


def is_roni(col: str) -> bool:
    return col[:2] in ("BR", "SR")


def _loss(y: np.ndarray, X: np.ndarray, model: str) -> float:
    if model == "ppml":
        return float(sm.GLM(y, X, family=sm.families.Poisson()).fit(maxiter=200, tol=1e-10).deviance)
    return float(sm.OLS(y, X).fit().ssr)


def profile(p, y, lagsR, lagsD, base, model, spec=Spec(), grid=THETA_GRID) -> pd.DataFrame:
    """Loss L(theta^R, theta^D) over the grid (Eq. 6), same sample throughout."""
    B = base.to_numpy(float)
    yv = np.asarray(y, float)
    rows = []
    for tR in grid:
        for tD in (grid if spec.dmi else grid[:1]):  # no DMI: theta_D irrelevant
            C = climate_design(p, lagsR, lagsD, tR, tD, spec).to_numpy(float)
            rows.append((tR, tD, _loss(yv, np.hstack([C, B]), model)))
    return pd.DataFrame(rows, columns=["theta_R", "theta_D", "loss"])


def estimate(p, y, lagsR, lagsD, base, model, spec=Spec(), grid=THETA_GRID) -> dict:
    """Profile the timing parameters, then fit Eq. (4) at the best pair with
    Driscoll-Kraay standard errors. Returns the fit (estimation.panel.fit), the design,
    the profile table and the selected thetas."""
    prof = profile(p, y, lagsR, lagsD, base, model, spec, grid)
    best = prof.loc[prof["loss"].idxmin()]
    tR, tD = float(best.theta_R), float(best.theta_D)
    X = pd.concat([climate_design(p, lagsR, lagsD, tR, tD, spec), base], axis=1)
    X = X.loc[:, X.abs().sum() > 0]
    res = fit(y, X, p["period"], model)
    edge = tR in (grid[0], grid[-1]) or (spec.dmi and tD in (grid[0], grid[-1]))
    return {"fit": res, "X": X, "profile": prof, "theta_R": tR,
            "theta_D": tD if spec.dmi else float("nan"),
            "loss": float(best.loss), "k": X.shape[1], "on_grid_edge": edge}


def national_effect(res: dict, X: pd.DataFrame, weights: pd.Series, idx: str,
                    spec: Spec = Spec(), wet: bool = False, post: bool = False,
                    dt: float | None = None):
    """Production-weighted national total effect of index idx ('R', 'RP', 'RN', 'D'),
    with its Driscoll-Kraay s.e.; wet=True adds the wet-season shift, post=True the shift
    after effect_break; dt (decades from today) evaluates an effect_trend specification at
    another date."""
    from estimation.panel import linear_combination
    g = weights.groupby(weights.index.map(lambda r: groups(
        pd.DataFrame({"region_code": [r]}), spec.pooling).iloc[0])).sum()
    w = {f"B{idx}_{k}": v for k, v in g.items() if f"B{idx}_{k}" in X.columns}
    if wet and f"S{idx}_wet" in X.columns:
        w[f"S{idx}_wet"] = 1.0
    if post and f"S{idx}_post" in X.columns:
        w[f"S{idx}_post"] = 1.0
    if dt is not None and f"S{idx}_trend" in X.columns:
        w[f"S{idx}_trend"] = dt
    return linear_combination(res, w)
