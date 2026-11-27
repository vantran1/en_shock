"""Verification scores of the Stage 1 notebook (WMO-No. 1246 good practice) and probabilistic scores."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def verify(obs: np.ndarray, pred: np.ndarray, columns) -> pd.DataFrame:
    """Per column: Spearman (and p-value), Pearson, 2AFC, ROC areas of the lower and upper thirds, RPSS, MSSS.
    obs and pred are standardised anomalies (years x columns). The p-value is one-sided (alternative: Spearman > 0),
    since only a positive correlation is skill: a hindcast that is anti-correlated with the observations is never
    counted as significant."""
    resid_sd = np.sqrt(((obs - pred) ** 2).mean(0))
    rows = []
    for j, r in enumerate(columns):
        o, f = obs[:, j], pred[:, j]
        if np.nanstd(o) == 0 or np.nanstd(f) == 0:
            rows.append(dict(column=r))
            continue
        rs, ps = stats.spearmanr(f, o, alternative="greater")
        tau = stats.kendalltau(f, o).statistic
        t1, t2 = np.quantile(o, [1 / 3, 2 / 3])
        below, above = o < t1, o > t2

        def auc(ev, s):
            if ev.all() or (~ev).all():
                return np.nan
            return stats.mannwhitneyu(s[ev], s[~ev]).statistic / (ev.sum() * (~ev).sum())

        sd = resid_sd[j] if resid_sd[j] > 0 else 1.0
        pb = stats.norm.cdf((t1 - f) / sd)
        pa = 1 - stats.norm.cdf((t2 - f) / sd)
        cum_f, cum_o = np.c_[pb, 1 - pa], np.c_[below, ~above].astype(float)
        rps = ((cum_f - cum_o) ** 2).sum(1).mean()
        rps_clim = ((np.array([1 / 3, 2 / 3]) - cum_o) ** 2).sum(1).mean()
        rows.append(dict(column=r, spearman=rs, p_value=ps, pearson=np.corrcoef(f, o)[0, 1], two_afc=(1 + tau) / 2,
                         roc_below=auc(below, -f), roc_above=auc(above, f), rpss=1 - rps / rps_clim,
                         msss=1 - ((o - f) ** 2).mean() / (o ** 2).mean()))
    return pd.DataFrame(rows)


def bh_fdr(p, q=0.10) -> np.ndarray:
    """Benjamini-Hochberg: which p-values pass at false-discovery rate q (NaN never passes)."""
    p = np.asarray(p, float)
    out = np.zeros(len(p), bool)
    ok = np.isfinite(p)
    if not ok.any():
        return out
    pv = p[ok]
    order = np.argsort(pv)
    passed = pv[order] <= q * np.arange(1, len(pv) + 1) / len(pv)
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    sub = np.zeros(len(pv), bool)
    sub[order[:k]] = True
    out[np.where(ok)[0]] = sub
    return out


def add_fdr(tbl: pd.DataFrame, q: float, by=("var", "cv")) -> pd.DataFrame:
    """significant = the one-sided p-value of verify() passes Benjamini-Hochberg at FDR q, within each group of `by`
    (for Stage 1: each variable, CV type and weighting, across its region-months)."""
    tbl = tbl.copy()
    tbl["significant"] = False
    for _, idx in tbl.groupby(list(by)).groups.items():
        tbl.loc[idx, "significant"] = bh_fdr(tbl.loc[idx, "p_value"].values, q)
    return tbl


def crps_sample(samp: np.ndarray, obs: np.ndarray) -> np.ndarray:
    """CRPS of an ensemble (m x p) for observations (p,), per column: E|X - y| - 1/2 E|X - X'|."""
    m = samp.shape[0]
    s = np.sort(samp, axis=0)
    t1 = np.abs(s - obs).mean(0)
    w = (2 * np.arange(1, m + 1) - m - 1)[:, None]
    return t1 - (w * s).sum(0) / (m * m)
