#!/usr/bin/env python3
"""Lag analysis: would RONI and DMI lagged by up to six months predict the weather better than the lag sets the
fit uses now (sync, sync+lag1)? A stand-alone check; it does not change the fit.

The predictor matrices are built here (RONI and DMI shifted by 0-6 months); everything else is the fit's own
machinery: the same predictands, transforms, leave-5-years-out cross-validation, EOF-CCA and (My, Mc) grid.
All lag sets are compared on the same years (1951-2025, so that lag 6 exists for every target month).

Two comparisons, for every variable and target month:

  plain   each lag set on its own, with its best (My, Mc) chosen by the fit's rule (mean CV Spearman over the
          cells). Shows which lags carry signal. With 12 (My, Mc) choices per lag set the scores are a little
          optimistic, but equally so for every lag set.
  nested  the honest test of changing the menu: outer 5-year blocks are held out, the configuration is chosen
          on the remaining years from a menu of lag sets, and the held-out years are predicted. A longer menu
          only helps if its extra choices beat the cost of choosing among more options.
          Menus: current = {sync, sync+lag1}; cumulative = {sync, sync+lag1, ..., sync+lag1..6};
          sync+one lag = {sync, sync+lag k for k = 1..6}; seasonal = {sync, sync+lag1, sync+lag3, sync+lag6}
          (lags 3 and 6 are the previous non-overlapping 3-month seasons); all = every lag set below.

Skill: mean Spearman over the ERA5 cells (the selection criterion), over the 16 regions with cropland weights
(agriculture) and over the 17 regions with population weights (electricity and labour).

  python analysis/lag_analysis.py                      # all variables and months, about 30-60 minutes
  python analysis/lag_analysis.py --vars T P --months 1 4
Writes outputs/analysis/lags/{plain,nested,nested_choices}.csv.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import engine as E  # noqa: E402
from stage1 import fit as F  # noqa: E402

LAGSETS = {
    "sync": (0,), "sync+lag1": (0, 1), "sync+lag1-2": (0, 1, 2), "sync+lag1-3": (0, 1, 2, 3),
    "sync+lag1-4": (0, 1, 2, 3, 4), "sync+lag1-5": (0, 1, 2, 3, 4, 5), "sync+lag1-6": (0, 1, 2, 3, 4, 5, 6),
    "lag1": (1,), "lag2": (2,), "lag3": (3,), "lag4": (4,), "lag5": (5,), "lag6": (6,),
    "sync+lag2": (0, 2), "sync+lag3": (0, 3), "sync+lag4": (0, 4), "sync+lag5": (0, 5), "sync+lag6": (0, 6),
    "sync+lag3+lag6": (0, 3, 6),
}
MENUS = {
    "current": ["sync", "sync+lag1"],
    "cumulative": ["sync", "sync+lag1", "sync+lag1-2", "sync+lag1-3", "sync+lag1-4", "sync+lag1-5", "sync+lag1-6"],
    "sync+one lag": ["sync", "sync+lag1", "sync+lag2", "sync+lag3", "sync+lag4", "sync+lag5", "sync+lag6"],
    "seasonal": ["sync", "sync+lag1", "sync+lag3", "sync+lag6"],
    "all": list(LAGSETS),
}
WSETS = ["r16_cropland", "r17_population"]
FIRST_YEAR = 1951
D: F.Data = None          # set in main, shared with the worker processes by fork


def design(P: pd.DataFrame, month: int, lags) -> pd.DataFrame:
    cur = P.index[P.index.month == month]
    blocks = [P.shift(L).loc[cur].add_suffix("" if L == 0 else f"_lag{L}") for L in lags]
    return pd.concat(blocks, axis=1).set_axis(cur.year, axis=0)


def month_inputs(var: str, month: int):
    years, Y, _ = D.month_data(var, month)
    keep = years >= FIRST_YEAR
    years, Y = years[keep], Y[keep]
    X = {ls: design(D.P, month, lags).reindex(years.astype(int)).to_numpy() for ls, lags in LAGSETS.items()}
    ok = np.all([np.isfinite(x).all(1) for x in X.values()], axis=0)
    return years[ok], Y[ok], {ls: x[ok] for ls, x in X.items()}


def mean_rho(pred, obs):
    return float(np.nanmean(E.col_spearman(pred, obs)))


def best_in(scores: dict, menu) -> tuple:
    sub = {g: s for g, s in scores.items() if g[0] in menu}
    return max(sub, key=sub.get)


def run_one(task):
    var, month = task
    t0 = time.time()
    kind = C.PREDICTANDS[var][3]
    years, Y, X = month_inputs(var, month)
    n = len(years)
    aggs = {ws: D.aggregator(ws, var, month) for ws in WSETS}
    Yr = {ws: a(Y) for ws, a in aggs.items()}
    S = D.S

    # plain CV: every lag set, its best (My, Mc)
    cv = E.cv_run([Y], [kind], X, years, S)
    _, _, scores = E.select(cv)
    plain = []
    for ls in LAGSETS:
        g = best_in(scores, [ls])
        row = dict(var=var, month=month, lagset=ls, n_lags=len(LAGSETS[ls]), My=g[1], Mc=g[2], n_years=n,
                   cells_rho=scores[g])
        phys = E.cv_physical(cv, g, 0)
        for ws in WSETS:
            o, p = F.regional_cv(Yr[ws], aggs[ws](phys), years, kind, S["cv_window"])
            row[f"{ws}_rho"] = mean_rho(p, o)
        plain.append(row)

    # nested CV: outer 5-year blocks, one inner CV serves the three menus
    cell = {m: np.empty_like(Y, dtype=float) for m in MENUS}
    cell_obs = np.empty_like(Y, dtype=float)
    reg = {m: {ws: np.empty(Yr[ws].shape) for ws in WSETS} for m in MENUS}
    reg_obs = {ws: np.empty(Yr[ws].shape) for ws in WSETS}
    choices = []
    for start in range(0, n, 5):
        te = np.zeros(n, bool)
        te[start:start + 5] = True
        tr = ~te
        icv = E.cv_run([Y[tr]], [kind], {k: x[tr] for k, x in X.items()}, years[tr], S)
        _, _, isc = E.select(icv)
        py, Ys = E.prep_y(Y[tr], years[tr], [kind] * Y.shape[1])
        cell_obs[te] = py.standardize(Y[te], years[te])
        rprep = {}
        for ws in WSETS:
            pr, _ = E.prep_y(Yr[ws][tr], years[tr], [kind] * Yr[ws].shape[1])
            rprep[ws] = pr
            reg_obs[ws][te] = pr.standardize(Yr[ws][te], years[te])
        for m, menu in MENUS.items():
            ls, My, Mc = best_in(isc, menu)
            choices.append(dict(var=var, month=month, menu=m, block_start=int(years[start]), lagset=ls, My=My, Mc=Mc))
            pxx, Xs = E.prep_x(X[ls][tr], years[tr], S["detrend_predictors"])
            G, _ = E.cca_operator(Xs, Ys, My, Mc)
            f = pxx.standardize(X[ls][te], years[te]) @ G.T
            cell[m][te] = f
            phys = py.to_physical(f, years[te])
            for ws in WSETS:
                reg[m][ws][te] = rprep[ws].standardize(aggs[ws](phys), years[te])
    nested = []
    for m in MENUS:
        row = dict(var=var, month=month, menu=m, n_years=n, cells_rho=mean_rho(cell[m], cell_obs))
        for ws in WSETS:
            row[f"{ws}_rho"] = mean_rho(reg[m][ws], reg_obs[ws])
        nested.append(row)
    print(f"  {var:7s} month {month:2d}: {time.time() - t0:5.1f} s", flush=True)
    return plain, nested, choices


def main():
    global D
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--vars", nargs="*")
    ap.add_argument("--months", nargs="*", type=int)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count()))
    a = ap.parse_args()
    cfg = C.load(a.config)
    D, variables, extra = F.load_data(cfg, refresh_indices=False, with_hourly=True)
    print(f"indices: RONI to {extra['index_info']['roni_last']}, DMI to {extra['index_info']['dmi_raw_last']}")
    variables = [v for v in (a.vars or variables) if v in variables]
    months = a.months or list(range(1, 13))
    tasks = [(v, m) for v in variables for m in months]
    print(f"{len(tasks)} variable-months x {len(LAGSETS)} lag sets, {a.workers} workers")
    t0 = time.time()
    if a.workers > 1:
        with mp.get_context("fork").Pool(a.workers) as pool:
            res = pool.map(run_one, tasks, chunksize=1)
    else:
        res = [run_one(t) for t in tasks]
    out = C.out(cfg, "analysis", "lags", "plain.csv").parent
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([r for p, _, _ in res for r in p]).to_csv(out / "plain.csv", index=False)
    pd.DataFrame([r for _, n, _ in res for r in n]).to_csv(out / "nested.csv", index=False)
    pd.DataFrame([r for *_, c in res for r in c]).to_csv(out / "nested_choices.csv", index=False)
    print(f"done in {(time.time() - t0) / 60:.1f} min; wrote {out}")


if __name__ == "__main__":
    main()
