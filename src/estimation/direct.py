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

Standard errors: Driscoll-Kraay (estimation.panel), conditional on the selected timing
parameters; v5 computes the confidence intervals of the shocks by a block bootstrap over
years that re-estimates the timing parameters in each replication (to be added with the
shocks).
"""
from math import comb

import numpy as np
import pandas as pd
import statsmodels.api as sm

from estimation.panel import fit

THETA_GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)


def binomial_weights(theta: float, K: int) -> np.ndarray:
    j = np.arange(1, K + 1)
    return np.array([comb(K - 1, i - 1) for i in j]) * theta ** (K - j) * (1 - theta) ** (j - 1)


def lag_matrix(index_q: pd.Series, K: int) -> pd.DataFrame:
    """Columns lag1..lagK of a quarterly index (index: 'YYYYQn' strings)."""
    return pd.DataFrame({f"lag{j}": index_q.shift(j) for j in range(1, K + 1)}, index=index_q.index)


def blended(lags: np.ndarray, theta: float) -> np.ndarray:
    """z_q(theta) = sum_j w_j(theta) x_{q-j}; lags: n x K array aligned with the panel."""
    return lags @ binomial_weights(theta, lags.shape[1])


def base_design(p: pd.DataFrame, controls: list[str], extra: pd.DataFrame | None = None) -> pd.DataFrame:
    """Everything except the climate terms: region x quarter effects, region trends,
    controls (and extra columns such as break dummies). p needs region_code, q, t."""
    rq = p["region_code"] + "_q" + p["q"].astype(str)
    fe = pd.get_dummies(rq, prefix="fe", dtype=float)
    reg = pd.get_dummies(p["region_code"], prefix="tr", dtype=float).mul(p["t"].values, axis=0)
    parts = [fe, reg, p[controls]]
    if extra is not None and extra.shape[1]:
        parts.append(extra)
    return pd.concat(parts, axis=1)


def climate_design(p: pd.DataFrame, zR: np.ndarray, zD: np.ndarray) -> pd.DataFrame:
    """Blended RONI and DMI interacted with region dummies: columns BR_<r>, BD_<r>."""
    d = pd.get_dummies(p["region_code"], dtype=float)
    return pd.concat([d.mul(zR, axis=0).add_prefix("BR_"), d.mul(zD, axis=0).add_prefix("BD_")],
                     axis=1)


def _loss(y: np.ndarray, X: np.ndarray, model: str) -> float:
    if model == "ppml":
        return float(sm.GLM(y, X, family=sm.families.Poisson()).fit(maxiter=200, tol=1e-10).deviance)
    return float(sm.OLS(y, X).fit().ssr)


def profile(p, y, lagsR, lagsD, base, model, grid=THETA_GRID) -> pd.DataFrame:
    """Loss L(theta^R, theta^D) over the grid (Eq. 6), same sample throughout."""
    B = base.to_numpy(float)
    rows = []
    for tR in grid:
        zR = blended(lagsR, tR)
        for tD in grid:
            C = climate_design(p, zR, blended(lagsD, tD)).to_numpy(float)
            rows.append((tR, tD, _loss(y, np.hstack([C, B]), model)))
    return pd.DataFrame(rows, columns=["theta_R", "theta_D", "loss"])


def estimate(p, y, lagsR, lagsD, base, model, grid=THETA_GRID) -> dict:
    """Profile the timing parameters, then fit Eq. (4) at the best pair with
    Driscoll-Kraay standard errors. Returns the fit (estimation.panel.fit), the design,
    the profile table and the selected thetas."""
    prof = profile(p, y, lagsR, lagsD, base, model, grid)
    best = prof.loc[prof["loss"].idxmin()]
    tR, tD = float(best.theta_R), float(best.theta_D)
    X = pd.concat([climate_design(p, blended(lagsR, tR), blended(lagsD, tD)), base], axis=1)
    X = X.loc[:, X.abs().sum() > 0]
    res = fit(y, X, p["period"], model)
    return {"fit": res, "X": X, "profile": prof, "theta_R": tR, "theta_D": tD,
            "on_grid_edge": tR in (grid[0], grid[-1]) or tD in (grid[0], grid[-1])}
