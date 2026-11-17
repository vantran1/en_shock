"""EOF -> CCA numerics (Section 3.3 of the methodology), as in the Stage 1 notebooks.

All functions work on plain arrays: rows are years, columns are grid cells (or regions).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import special, stats

T_REF = 2000.0          # reference year of the trend terms: mu + zeta (t - T_REF)


# ------------------------------------------------------------------ transforms T_v (Eq. 10)
def gamma_fit(Y: np.ndarray):
    """Column-wise 2-parameter Gamma MLE (Thom 1958)."""
    Yp = np.clip(Y, 1e-6, None)
    m = Yp.mean(0)
    A = np.maximum(np.log(m) - np.log(Yp).mean(0), 1e-8)
    a = (1 + np.sqrt(1 + 4 * A / 3)) / (4 * A)
    return a, m / a


class Transform:
    """Per-column normal-score transform: identity ('none'), Gamma ('gamma') or empirical ('empirical').

    The empirical transform is for counts with many zeros (dry days, hot days, ...): normal scores of the
    plotting positions k/(n+1), with ties sharing their mean position; its inverse interpolates the training
    quantiles, so simulated values stay inside the range of the training years."""

    def __init__(self, kinds):
        self.kinds = np.asarray(kinds)

    def fit(self, Y):
        self.g = self.kinds == "gamma"
        self.e = self.kinds == "empirical"
        if self.g.any():
            self.ga, self.gs = gamma_fit(Y[:, self.g])
        if self.e.any():
            self.es = np.sort(Y[:, self.e], axis=0)                          # (n, q_e)
        return self

    def _emp_forward(self, V):
        S = self.es
        n = S.shape[0]
        less = (S[None, :, :] < V[:, None, :]).sum(1)
        equal = (S[None, :, :] == V[:, None, :]).sum(1)
        p = (less + 0.5 * equal + 0.5) / (n + 1)
        return special.ndtri(np.clip(p, 0.5 / (n + 1), 1 - 0.5 / (n + 1)))

    def _emp_inverse(self, Z):
        S = self.es
        n = S.shape[0]
        pk = np.arange(1, n + 1) / (n + 1)
        P = special.ndtr(Z)
        out = np.empty_like(P)
        flat_p = P.reshape(-1, P.shape[-1])
        flat_o = out.reshape(-1, P.shape[-1])
        for j in range(S.shape[1]):
            flat_o[:, j] = np.interp(flat_p[:, j], pk, S[:, j])
        return out

    def forward(self, Y):
        Y = np.asarray(Y, dtype=float)
        Z = np.array(Y, dtype=float, copy=True)
        if self.g.any():
            p = special.gammainc(self.ga, np.clip(Y[:, self.g], 1e-6, None) / self.gs)
            Z[:, self.g] = special.ndtri(np.clip(p, 1e-6, 1 - 1e-6))
        if self.e.any():
            Z[:, self.e] = self._emp_forward(Y[:, self.e])
        return Z

    def inverse(self, Z):
        Y = np.array(Z, dtype=float, copy=True)
        if self.g.any():
            Y[..., self.g] = special.gammaincinv(self.ga, special.ndtr(Z[..., self.g])) * self.gs
        if self.e.any():
            Y[..., self.e] = self._emp_inverse(Z[..., self.e])
        return Y


@dataclass
class Prep:
    """Transform, trend and spread of the predictand columns in one training sample."""
    tf: Transform
    mu: np.ndarray
    zeta: np.ndarray
    sigma: np.ndarray

    def standardize(self, Y, t):
        t = np.atleast_1d(np.asarray(t, float))
        return (self.tf.forward(np.atleast_2d(Y)) - self.mu - self.zeta * (t[:, None] - T_REF)) / self.sigma

    def to_physical(self, y_std, t):
        """Eq. 10: W = T^-1(mu + zeta (t - T_REF) + sigma y), with y = y_hat + e."""
        return self.tf.inverse(self.mu + self.zeta * (np.asarray(t, float)[..., None] - T_REF) + self.sigma * y_std)


def prep_y(Y, t, kinds):
    tf = Transform(kinds).fit(Y)
    Yt = tf.forward(Y)
    tc = np.asarray(t, float) - T_REF
    tb = tc.mean()
    zeta = ((tc - tb)[:, None] * (Yt - Yt.mean(0))).sum(0) / ((tc - tb) ** 2).sum()
    mu = Yt.mean(0) - zeta * tb
    resid = Yt - mu - zeta * tc[:, None]
    sigma = resid.std(0, ddof=1)
    sigma = np.where(sigma > 1e-12, sigma, 1.0)          # constant columns (e.g. no hot days ever) stay constant
    return Prep(tf, mu, zeta, sigma), resid / sigma


@dataclass
class PrepX:
    a: np.ndarray
    b: np.ndarray
    s: np.ndarray

    def standardize(self, X, t):
        t = np.atleast_1d(np.asarray(t, float))
        return (np.atleast_2d(X) - self.a - self.b * (t[:, None] - T_REF)) / self.s


def prep_x(X, t, detrend=False):
    tc = np.asarray(t, float) - T_REF
    if detrend:
        tb = tc.mean()
        b = ((tc - tb)[:, None] * (X - X.mean(0))).sum(0) / ((tc - tb) ** 2).sum()
        a = X.mean(0) - b * tb
    else:
        a, b = X.mean(0), np.zeros(X.shape[1])
    R = X - a - b * tc[:, None]
    s = R.std(0, ddof=1)
    return PrepX(a, b, s), R / s


# ------------------------------------------------------------------ EOF -> CCA (Eqs. 8-9)
def whiten(Xs):
    n = Xs.shape[0]
    _, Sx, Vxt = np.linalg.svd(Xs, full_matrices=False)
    return Vxt.T / Sx * np.sqrt(n - 1)


def svd_top(Y, k):
    """Leading k singular triplets of Y (n x p) from the n x n cross-product matrix (same modes as the full SVD)."""
    w, V = np.linalg.eigh(Y @ Y.T)
    w, V = w[::-1][:k], V[:, ::-1][:, :k]
    S = np.sqrt(np.maximum(w, 0))
    S_safe = np.where(S > 1e-12, S, 1.0)
    return V, S, (V.T @ Y) / S_safe[:, None]


def cca_operator(Xs, Ys, My, Mc):
    """EOF -> CCA on standardised data: y_hat = G x_tilde (Eq. 9). Also returns the pieces for diagnostics."""
    n = Xs.shape[0]
    sq = np.sqrt(n - 1)
    U, S, Vt = svd_top(Ys, My)
    Z = sq * U[:, :My]
    Lam = Vt[:My].T * S[:My] / sq
    W = whiten(Xs)
    P, R, Qt = np.linalg.svd((Xs @ W).T @ Z / (n - 1), full_matrices=False)
    A, B, rho = W @ P[:, :Mc], Qt[:Mc].T, R[:Mc]
    G = Lam @ B @ np.diag(rho) @ A.T
    return G, dict(rho=rho, A=A, B=B, Lam=Lam, Z=Z, explained=(S[:My] ** 2) / (Ys ** 2).sum())


def config_grid(px_by_lag: dict, my_grid, mc_grid):
    return [(ls, My, Mc) for ls, px in px_by_lag.items() for My in my_grid for Mc in mc_grid if Mc <= min(px, My)]


def col_spearman(a, b):
    """Spearman correlation per column (NaN for constant columns)."""
    ra, rb = stats.rankdata(a, axis=0), stats.rankdata(b, axis=0)
    ra -= ra.mean(0)
    rb -= rb.mean(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (ra * rb).sum(0) / np.sqrt((ra ** 2).sum(0) * (rb ** 2).sum(0))


def predict_all(Ux, xw, U, S, Vt, sq, px, out, k, ls, my_grid, mc_grid):
    """Every (My, Mc) prediction for one fold and one lag set, from the fold's EOFs."""
    for My in my_grid:
        Lam = Vt[:My].T * S[:My] / sq
        P, R, Qt = np.linalg.svd(Ux.T @ U[:, :My], full_matrices=False)
        proj = P.T @ xw
        for Mc in mc_grid:
            if Mc <= min(px, My):
                out[(ls, My, Mc)][k] = Lam @ (Qt[:Mc].T @ (R[:Mc] * proj[:Mc]))


def cv_run(blocks, kinds, X_by_lag, years, S):
    """Leave-`cv_window`-out cross-validation of the EOF-CCA for every configuration.

    `blocks` is a list of (n x q_b) predictand arrays (one per variable; a single block for the per-variable
    model, all variables for the joint check). Each block is transformed, detrended and standardised in each
    training window; the EOFs are taken of the blocks side by side. Returns the standardised observations and
    predictions of every configuration, and every fold's `Prep` per block (to go back to physical units)."""
    n = len(years)
    sizes = [b.shape[1] for b in blocks]
    Q = sum(sizes)
    half = S["cv_window"] // 2
    my_grid, mc_grid = S["my_grid"], S["mc_grid"]
    grid = config_grid({k: v.shape[1] for k, v in X_by_lag.items()}, my_grid, mc_grid)
    obs = np.empty((n, Q))
    pred = {g: np.empty((n, Q)) for g in grid}
    preps = []
    for k in range(n):
        tr = np.abs(years - years[k]) > half
        tk = years[k:k + 1]
        sq = np.sqrt(tr.sum() - 1)
        fold_preps, Ys_parts, col = [], [], 0
        for b, kind, q in zip(blocks, kinds, sizes):
            pb, Ysb = prep_y(b[tr], years[tr], [kind] * q)
            obs[k, col:col + q] = pb.standardize(b[k:k + 1], tk)[0]
            fold_preps.append(pb)
            Ys_parts.append(Ysb)
            col += q
        preps.append(fold_preps)
        Ys = Ys_parts[0] if len(Ys_parts) == 1 else np.hstack(Ys_parts)
        U, Sv, Vt = svd_top(Ys, max(my_grid))
        for ls, X in X_by_lag.items():
            pxx, Xs = prep_x(X[tr], years[tr], S.get("detrend_predictors", False))
            W = whiten(Xs)
            Ux, xw = Xs @ W / sq, pxx.standardize(X[k:k + 1], tk)[0] @ W
            predict_all(Ux, xw, U, Sv, Vt, sq, X.shape[1], pred, k, ls, my_grid, mc_grid)
    return dict(grid=grid, obs=obs, pred=pred, preps=preps, sizes=sizes, years=years)


def select(cv: dict, cols=None):
    """Configuration with the highest mean CV Spearman correlation (over `cols`, default all columns)."""
    sl = slice(None) if cols is None else cols
    scores = {g: float(np.nanmean(col_spearman(p[:, sl], cv["obs"][:, sl]))) for g, p in cv["pred"].items()}
    best = max(scores, key=scores.get)
    return best, scores[best], scores


def block_slice(cv: dict, b: int) -> slice:
    start = sum(cv["sizes"][:b])
    return slice(start, start + cv["sizes"][b])


def cv_physical(cv: dict, cfg, b: int = 0) -> np.ndarray:
    """CV predictions of block b for configuration cfg, back in physical units (residual zero)."""
    sl = block_slice(cv, b)
    P = cv["pred"][cfg][:, sl]
    return np.stack([cv["preps"][k][b].to_physical(P[k][None, :], cv["years"][k])[0] for k in range(len(cv["years"]))])
