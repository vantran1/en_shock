"""Panel estimators shared by the direct models: Poisson pseudo-ML (PPML) and OLS on
logs, with Driscoll-Kraay standard errors.

Driscoll-Kraay: scores are summed over regions within each quarter (the climate index
is common to all regions, so regions are not independent), then a Bartlett-weighted
Newey-West sum over quarters allows autocorrelation up to `bandwidth` quarters.
V = H^-1 Omega H^-1, with H the Hessian (PPML: sum mu x x'; OLS: X'X).
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm


def driscoll_kraay(scores: np.ndarray, time: np.ndarray, hessian: np.ndarray,
                   bandwidth: int | None = None) -> np.ndarray:
    t_codes, _ = pd.factorize(time, sort=True)
    T = t_codes.max() + 1
    S = np.zeros((T, scores.shape[1]))
    np.add.at(S, t_codes, scores)
    L = bandwidth if bandwidth is not None else int(np.floor(4 * (T / 100) ** (2 / 9)))
    omega = S.T @ S
    for lag in range(1, L + 1):
        g = S[lag:].T @ S[:-lag]
        omega += (1 - lag / (L + 1)) * (g + g.T)
    h_inv = np.linalg.pinv(hessian)
    return h_inv @ omega @ h_inv


def fit(y: pd.Series, X: pd.DataFrame, time: pd.Series, model: str = "ppml",
        bandwidth: int | None = None) -> dict:
    """model: 'ppml' (y in levels, >= 0) or 'ols' (y already in logs)."""
    Xv, yv = X.to_numpy(float), y.to_numpy(float)
    if model == "ppml":
        res = sm.GLM(yv, Xv, family=sm.families.Poisson()).fit(maxiter=200, tol=1e-10)
        mu = res.fittedvalues
        scores = Xv * (yv - mu)[:, None]
        hess = (Xv * mu[:, None]).T @ Xv
        resid = (yv - mu) / np.sqrt(mu)  # Pearson residuals
    elif model == "ols":
        res = sm.OLS(yv, Xv).fit()
        e = res.resid
        scores = Xv * e[:, None]
        hess = Xv.T @ Xv
        resid = e
    else:
        raise ValueError(model)
    V = driscoll_kraay(scores, time.to_numpy(), hess, bandwidth)
    params = pd.Series(res.params, index=X.columns)
    cov = pd.DataFrame(V, index=X.columns, columns=X.columns)
    return {"params": params, "cov": cov, "se": np.sqrt(np.clip(np.diag(V), 0, None)),
            "resid": pd.Series(resid, index=y.index), "converged": getattr(res, "converged", True)}


def linear_combination(fit_res: dict, weights: dict) -> tuple[float, float]:
    """Estimate and DK s.e. of sum_j w_j * beta_j."""
    g = pd.Series(0.0, index=fit_res["params"].index)
    for k, w in weights.items():
        g[k] = w
    est = float(g @ fit_res["params"])
    se = float(np.sqrt(max(g @ fit_res["cov"] @ g, 0)))
    return est, se
