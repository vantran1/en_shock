#!/usr/bin/env python3
"""SST predictors beyond the RONI: does more of the ocean help Stage 1? A stand-alone check, like the DMI
analysis; it does not change the fit or any pipeline output.

Step 1, indices. Four SST indices added to the RONI, one at a time, and the first three together:
  emi   El Nino Modoki index (Ashok et al. 2007): A - 0.5 B - 0.5 C, with A = 165E-140W, 10S-10N;
        B = 110W-70W, 15S-5N; C = 125E-145E, 10S-20N. Tells central-Pacific El Ninos from eastern ones.
  iob   Indian Ocean basin, 40E-100E, 20S-20N: the Indian Ocean warming that follows an El Nino.
  psea  Philippine Sea, 125E-150E, 5N-20N, as the mean of the three months BEFORE the target month only:
        local SST in the target month partly reflects the local weather, which would flatter the skill.
        (This box is our choice, not a published index.)
  tna   Tropical North Atlantic, 57.5W-15W, 5.5N-23.5N (Enfield et al. 1999).
  Every index is built from ERSSTv5 anomalies (1991-2020 climatology) minus the tropical-mean anomaly
  (20S-20N), like the RONI, so the warming trend cannot enter as a predictor. emi, iob and tna are centred
  3-month means used at every lag of a lag set, like the DMI; psea is one extra column in every lag set.

Step 2, field CCA. The predictors are the leading EOFs of the SST map itself: the tropical Indo-Pacific,
  30S-30N, 40E-80W, relative anomalies as above, centred 3-month means, the maps of the lags of a lag set side
  by side, area weighted (sqrt cos lat). The EOFs are recomputed from the training years of every fold, and the
  number of SST EOFs (Mx, 2-15) is chosen with the lag set, My and Mc. A second run masks the waters around the
  Philippines (110E-135E, 0-25N): skill that appears only with them is the weather feeding back onto the
  local SST, not predictability.

Each menu is compared with the RONI alone (the main run), everything else the fit's own: predictands,
transforms, trend, EOF-CCA, lag sets, (My, Mc) grid, leave-5-years-out CV, and the nested CV of step 3 (5-year
July-June blocks held out, the configuration chosen again on the remaining years). Skill on the 16 regions
(cropland weights) and the 17 regions (population weights). The paired test is that of the DMI analysis: for
every held-out year, the squared error of the nested hindcast (standardised anomaly) with the RONI alone minus
that with the menu, averaged over the months and regions of a group; a moving-block bootstrap over years
(5-year blocks) gives a 90 % interval for the reduction of the MSE.

The SST file (about 160 MB, not in the repository):
  mkdir -p data/inputs/sst
  curl -L -o data/inputs/sst/ersst.v5.sst.mnmean.nc https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc

  python analysis/sst_predictors.py                     # both steps, all variables and months (about an hour on 2 cores)
  python analysis/sst_predictors.py --steps 1           # indices only
  python analysis/sst_predictors.py --vars P --months 1 2 3
  python analysis/sst_predictors.py --figure-only       # redraw the figure from the saved tables
Writes outputs/analysis/sst/*.csv, summary.txt and sst_summary.png.
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import pathlib
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import engine as E  # noqa: E402
from stage1 import fit as F  # noqa: E402
from stage1 import indices as I  # noqa: E402

WSETS = ["r16_cropland", "r17_population"]
QUARTER = {m: f"Q{(m - 1) // 3 + 1}" for m in range(1, 13)}
QNAME = {"Q1": "JFM", "Q2": "AMJ", "Q3": "JAS", "Q4": "OND"}
BASE = "roni"
# index menus: (indices used at every lag of a lag set, whether the psea column is added)
INDEX_MENUS = {
    "roni": (("roni",), False),
    "roni_emi": (("roni", "emi"), False),
    "roni_iob": (("roni", "iob"), False),
    "roni_psea": (("roni",), True),
    "roni_tna": (("roni", "tna"), False),
    "roni_emi_iob_psea": (("roni", "emi", "iob"), True),
}
FIELD_MENUS = {"field": False, "field_masked": True}      # menu -> waters around the Philippines masked
LABEL = {"roni": "RONI alone", "roni_emi": "RONI + EMI", "roni_iob": "RONI + IOB", "roni_psea": "RONI + Philippine Sea",
         "roni_tna": "RONI + TNA", "roni_emi_iob_psea": "RONI + EMI + IOB + Phil. Sea",
         "field": "SST field (EOFs)", "field_masked": "SST field, Philippine waters masked"}

# boxes: (lat south, lat north, lon west, lon east), longitudes in degrees east 0-360
BOX = {
    "trop": (-20, 20, 0, 360),
    "emi_a": (-10, 10, 165, 220), "emi_b": (-15, 5, 250, 290), "emi_c": (-10, 20, 125, 145),
    "iob": (-20, 20, 40, 100),
    "psea": (5, 20, 125, 150),
    "tna": (5.5, 23.5, 302.5, 345),
    "nino34": (-5, 5, 190, 240),
    "dmi_w": (-10, 10, 50, 70), "dmi_e": (-10, 0, 90, 110),
}
FIELD_DOMAIN = (-30, 30, 40, 280)
FIELD_MASK = (0, 25, 110, 135)

D: F.Data = None          # set in main, shared with the worker processes by fork
IDX: pd.DataFrame = None  # monthly predictor table (roni from CPC and the SST indices) on D.P's index
GRAM: dict = None         # (month, lag set, masked) -> Gram matrix of the field rows, years FIRST_YEAR..
FIRST_YEAR = None
MX_GRID: list = None
STEPS: tuple = None


# ------------------------------------------------------------------ SST indices and field
def in_box(lat, lon, b):
    s, n, w, e = b
    return (lat >= s) & (lat <= n), (lon >= w) & (lon <= e)


class SST:
    """ERSSTv5 relative anomalies: the anomaly (1991-2020 monthly climatology) minus the tropical-mean anomaly."""

    def __init__(self, path: pathlib.Path, clim=(1991, 2020), start="1940-01-01"):
        import xarray as xr
        with xr.open_dataset(path) as ds:
            sst = ds["sst"].sel(time=slice(start, None)).sortby("lat").load()
        ref = sst.sel(time=slice(f"{clim[0]}-01-01", f"{clim[1]}-12-01"))
        anom = sst.groupby("time.month") - ref.groupby("time.month").mean("time")
        self.time = pd.DatetimeIndex(anom["time"].values)
        self.lat = anom["lat"].values.astype(float)
        self.lon = anom["lon"].values.astype(float)
        A = anom.values.astype(float)                      # (time, lat, lon), NaN over land
        self.ocean = np.isfinite(A).all(0)                 # ocean in every month
        A = np.where(self.ocean[None], A, np.nan)
        self.coslat = np.cos(np.deg2rad(self.lat))
        self.trop = self.box_mean(A, BOX["trop"])
        self.rel = A - self.trop[:, None, None]
        self.last = f"{self.time.max():%Y-%m}"

    def box_mean(self, A, b) -> np.ndarray:
        la, lo = in_box(self.lat, self.lon, b)
        sub = A[:, la][:, :, lo]
        w = np.broadcast_to(self.coslat[la][:, None], sub.shape[1:]) * np.isfinite(sub[0])
        return np.nansum(sub * w, axis=(1, 2)) / w.sum()

    def series(self, b, relative=True) -> pd.Series:
        A = self.rel if relative else self.rel + self.trop[:, None, None]
        return pd.Series(self.box_mean(A, b), index=self.time)

    def field(self, domain, mask=None):
        """Centred 3-month means of the relative anomalies at the ocean points of `domain` (minus `mask`),
        times sqrt(cos lat): (time x points), so that F F' is the area-weighted covariance up to centring."""
        la, lo = in_box(self.lat, self.lon, domain)
        LA, LO = np.meshgrid(self.lat, self.lon, indexing="ij")
        keep = la[:, None] & lo[None, :] & self.ocean
        if mask is not None:
            mla, mlo = in_box(self.lat, self.lon, mask)
            keep &= ~(mla[:, None] & mlo[None, :])
        X = self.rel[:, keep] * np.sqrt(np.cos(np.deg2rad(LA[keep])))[None, :]
        Xs = np.full_like(X, np.nan)
        Xs[1:-1] = (X[:-2] + X[1:-1] + X[2:]) / 3
        return pd.DataFrame(Xs, index=self.time), dict(n_points=int(keep.sum()), lat=LA[keep], lon=LO[keep])


def smooth3(s: pd.Series) -> pd.Series:
    return s.rolling(3, center=True, min_periods=3).mean()


def build_indices(sst: SST, P: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The SST indices on the monthly index of the predictor table, and checks against the published series."""
    r = {k: sst.series(BOX[k]) for k in ("emi_a", "emi_b", "emi_c", "iob", "psea", "tna", "nino34", "dmi_w", "dmi_e")}
    raw = pd.DataFrame({
        "emi": r["emi_a"] - 0.5 * r["emi_b"] - 0.5 * r["emi_c"],
        "iob": r["iob"], "tna": r["tna"], "psea": r["psea"],
        "roni_ersst": r["nino34"],
        "dmi_ersst": sst.series(BOX["dmi_w"], False) - sst.series(BOX["dmi_e"], False),
    })
    sm = raw.apply(smooth3)
    out = pd.DataFrame(index=P.index)
    out["roni"] = P["roni"]
    for k in ("emi", "iob", "tna"):
        out[k] = sm[k].reindex(P.index)
    # psea: mean of the three months before the month of the row (t-3 .. t-1), never the month itself
    out["psea"] = raw["psea"].rolling(3, min_periods=3).mean().shift(1).reindex(P.index)
    out["roni_ersst"] = sm["roni_ersst"].reindex(P.index)
    out["dmi_ersst"] = sm["dmi_ersst"].reindex(P.index)
    out["dmi_psl"] = P["dmi"]
    return out, raw


def index_checks(IX: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
    s = IX[(IX.index.year >= y0) & (IX.index.year <= y1)]
    rows = []
    for a, b, what in (("roni_ersst", "roni", "RONI rebuilt from ERSSTv5 vs CPC RONI (both centred 3-month means)"),
                       ("dmi_ersst", "dmi_psl", "DMI rebuilt from ERSSTv5 vs PSL DMI from HadISST (both centred 3-month means)")):
        ok = s[[a, b]].dropna()
        rows.append(dict(check=what, n_months=len(ok), r=ok[a].corr(ok[b])))
    return pd.DataFrame(rows)


def index_correlations(IX: pd.DataFrame, y0: int, y1: int) -> pd.DataFrame:
    """Correlation of each index with the RONI (quarterly means), and with each other over the year."""
    s = IX[(IX.index.year >= y0) & (IX.index.year <= y1)][["roni", "emi", "iob", "psea", "tna"]]
    q = s.groupby([s.index.year, s.index.quarter]).mean()
    rows = []
    for qn in range(1, 5):
        x = q.xs(qn, level=1)
        for k in ("emi", "iob", "psea", "tna"):
            r = x["roni"].corr(x[k])
            rows.append(dict(quarter=f"Q{qn}", months=QNAME[f"Q{qn}"], index=k, r_with_roni=r, vif=1 / (1 - r ** 2)))
    for k in ("emi", "iob", "psea", "tna"):
        r = s["roni"].corr(s[k])
        rows.append(dict(quarter="year", months="all months", index=k, r_with_roni=r, vif=1 / (1 - r ** 2)))
    return pd.DataFrame(rows)


def build_grams(sst: SST, lag_sets: dict, y0: int, y1: int):
    """Gram matrices F F' of the field rows for every target month and lag set (the lags' maps side by side
    add up), years y0..y1, unmasked and masked; and the variance explained by the leading EOFs."""
    grams, eofs, info = {}, [], {}
    lags = sorted({L for v in lag_sets.values() for L in v})
    years = np.arange(y0, y1 + 1)
    for masked in (False, True):
        Fd, inf = sst.field(FIELD_DOMAIN, FIELD_MASK if masked else None)
        info[masked] = inf
        for m in range(1, 13):
            KL = {}
            for L in lags:
                t = pd.DatetimeIndex([pd.Timestamp(y, m, 1) - pd.DateOffset(months=L) for y in years])
                X = Fd.reindex(t).to_numpy()
                if not np.isfinite(X).all():
                    raise SystemExit(f"the SST file does not cover month {m} lag {L} for {y0}-{y1} (it ends {sst.last})")
                KL[L] = X @ X.T
            for ls, lv in lag_sets.items():
                K = sum(KL[L] for L in lv)
                grams[(m, ls, masked)] = K
                if ls == next(iter(lag_sets)):
                    Kc = K - K.mean(0)[None] - K.mean(1)[:, None] + K.mean()
                    w = np.clip(np.linalg.eigvalsh(Kc)[::-1], 0, None)
                    eofs.append(dict(masked=masked, month=m, lagset=ls, **{f"eof{j + 1}": w[j] / w.sum() for j in range(15)}))
    return grams, pd.DataFrame(eofs), info


def field_pcs(K: np.ndarray, tr, te, kmax: int):
    """Standardised leading PCs of the field in the training rows `tr`, and the rows `te` projected on the same
    EOFs: the EOF analysis of the centred training field in its n x n (kernel) form, which gives the same PCs as
    an SVD of the field itself. Returns (n_tr x k) and (n_te x k), each column with sd 1 in the training rows."""
    tr = np.flatnonzero(tr)
    te = np.flatnonzero(te)
    Ktt = K[np.ix_(tr, tr)]
    rm = Ktt.mean(1)
    gm = rm.mean()
    w, V = np.linalg.eigh(Ktt - rm[:, None] - rm[None, :] + gm)
    w, V = w[::-1][:kmax], V[:, ::-1][:, :kmax]
    sq = np.sqrt(len(tr) - 1)
    Kx = K[np.ix_(te, tr)]
    kc = Kx - Kx.mean(1, keepdims=True) - rm[None, :] + gm
    return V * sq, kc @ V / w * sq


# ------------------------------------------------------------------ cross-validation with every menu
def index_design(month: int, lags, menu: str) -> pd.DataFrame:
    preds, psea = INDEX_MENUS[menu]
    X = I.design(IDX, month, lags, preds)
    if psea:
        cur = IDX.index[IDX.index.month == month]
        X["psea_prev3"] = IDX.loc[cur, "psea"].to_numpy()
    return X


def candidates(var: str, month: int, years: np.ndarray):
    yi = years.astype(int)
    idx, fld, menus = {}, {}, {}
    index_menus = [m for m in INDEX_MENUS if m == BASE or 1 in STEPS]
    for mn in index_menus:
        menus[mn] = []
        for ls, lags in D.lag_sets.items():
            X = index_design(month, lags, mn).reindex(yi).to_numpy()
            if not np.isfinite(X).all():
                raise SystemExit(f"{mn} {ls}: missing index values for {var} month {month}")
            idx[f"{mn} | {ls}"] = X
            menus[mn].append(f"{mn} | {ls}")
    if 2 in STEPS:
        pos = yi - FIRST_YEAR
        for mn, masked in FIELD_MENUS.items():
            menus[mn] = []
            for ls in D.lag_sets:
                fld[f"{mn} | {ls}"] = GRAM[(month, ls, masked)][np.ix_(pos, pos)]
                menus[mn] += [f"{mn} | {ls} | Mx={k}" for k in MX_GRID]
    return idx, fld, menus


def cv_all(Y, kind, years, idx: dict, fld: dict, S: dict):
    """Leave-`cv_window`-out CV of every configuration of every candidate predictor set, as E.cv_run:
    index sets (n x p matrices) and fields (n x n Gram matrices, Mx SST EOFs taken in each fold)."""
    n, q = Y.shape
    half = S["cv_window"] // 2
    my_grid, mc_grid = S["my_grid"], S["mc_grid"]
    sizes = {k: X.shape[1] for k, X in idx.items()}
    sizes.update({f"{k} | Mx={mx}": mx for k in fld for mx in MX_GRID})
    grid = E.config_grid(sizes, my_grid, mc_grid)
    obs = np.empty((n, q))
    pred = {g: np.empty((n, q)) for g in grid}
    preps = []
    kmax = max(MX_GRID) if fld else 0
    for k in range(n):
        tr = np.abs(years - years[k]) > half
        tk = years[k:k + 1]
        sq = np.sqrt(tr.sum() - 1)
        pb, Ys = E.prep_y(Y[tr], years[tr], [kind] * q)
        obs[k] = pb.standardize(Y[k:k + 1], tk)[0]
        preps.append([pb])
        U, Sv, Vt = E.svd_top(Ys, max(my_grid))
        for ls, X in idx.items():
            pxx, Xs = E.prep_x(X[tr], years[tr], S.get("detrend_predictors", False))
            W = E.whiten(Xs)
            E.predict_all(Xs @ W / sq, pxx.standardize(X[k:k + 1], tk)[0] @ W, U, Sv, Vt, sq, X.shape[1], pred, k, ls,
                          my_grid, mc_grid)
        for ls, K in fld.items():
            te = np.zeros(n, bool)
            te[k] = True
            Xtr, Xte = field_pcs(K, tr, te, kmax)
            for mx in MX_GRID:          # standardised PCs are already white: W = I
                E.predict_all(Xtr[:, :mx] / sq, Xte[0, :mx], U, Sv, Vt, sq, mx, pred, k, f"{ls} | Mx={mx}",
                              my_grid, mc_grid)
    return dict(grid=grid, obs=obs, pred=pred, preps=preps, sizes=[q], years=years)


def cv_scores(cv: dict) -> dict:
    """E.select's scores (mean CV Spearman over the cells of every configuration), with the observations
    ranked once instead of once per configuration: the same arithmetic as E.col_spearman."""
    ro = stats.rankdata(cv["obs"], axis=0)
    ro -= ro.mean(0)
    o2 = (ro ** 2).sum(0)
    out = {}
    with np.errstate(invalid="ignore", divide="ignore"):
        for g, p in cv["pred"].items():
            rp = stats.rankdata(p, axis=0)
            rp -= rp.mean(0)
            out[g] = float(np.nanmean((rp * ro).sum(0) / np.sqrt((rp ** 2).sum(0) * o2)))
    return out


def best_in(scores: dict, menu) -> tuple:
    menu = set(menu)
    sub = {g: s for g, s in scores.items() if g[0] in menu}
    return max(sub, key=sub.get)


def fit_predict(g, idx, fld, years, tr, te, Ys, detrend):
    """Fit configuration g on the training rows and predict the test rows (standardised cell anomalies)."""
    cand, My, Mc = g
    if cand in idx:
        X = idx[cand]
        pxx, Xs = E.prep_x(X[tr], years[tr], detrend)
        G, _ = E.cca_operator(Xs, Ys, My, Mc)
        return pxx.standardize(X[te], years[te]) @ G.T
    base, mx = cand.rsplit(" | Mx=", 1)
    Xtr, Xte = field_pcs(fld[base], tr, te, int(mx))
    G, _ = E.cca_operator(Xtr, Ys, My, Mc)
    return Xte @ G.T


def describe(g) -> dict:
    parts = g[0].split(" | ")
    return dict(lagset=parts[1], Mx=int(parts[2][3:]) if len(parts) > 2 else np.nan, My=g[1], Mc=g[2])


def run_one(task):
    var, month = task
    t0 = time.time()
    kind = C.PREDICTANDS[var][3]
    years, Y, _ = D.month_data(var, month)
    n, q = Y.shape
    S = D.S
    idx, fld, M = candidates(var, month, years)
    aggs = {ws: D.aggregator(ws, var, month) for ws in WSETS}
    Yr = {ws: a(Y) for ws, a in aggs.items()}

    # plain CV: the configuration of each menu chosen on all years
    cv = cv_all(Y, kind, years, idx, fld, S)
    scores = cv_scores(cv)
    plain, plain_cfg = {}, {}
    for mn, menu in M.items():
        g = best_in(scores, menu)
        plain_cfg[mn] = g
        phys = E.cv_physical(cv, g, 0)
        plain[mn] = {ws: F.regional_cv(Yr[ws], aggs[ws](phys), years, kind, S["cv_window"]) for ws in WSETS}
    del cv

    # nested CV: the July-June blocks of step 3; one inner CV serves every menu
    obs = {ws: np.empty(Yr[ws].shape) for ws in WSETS}
    pred = {mn: {ws: np.empty(Yr[ws].shape) for ws in WSETS} for mn in M}
    choices = []
    nb = F.nested_settings(D.cfg)
    for te in F.nested_blocks(years, month, nb["first_year"], nb["block_len"], nb["start_month"]):
        tr = ~te
        icv = cv_all(Y[tr], kind, years[tr], {k: x[tr] for k, x in idx.items()},
                     {k: K[np.ix_(tr, tr)] for k, K in fld.items()}, S)
        isc = cv_scores(icv)
        del icv
        py, Ys = E.prep_y(Y[tr], years[tr], [kind] * q)
        rprep = {}
        for ws in WSETS:
            pr, _ = E.prep_y(Yr[ws][tr], years[tr], [kind] * Yr[ws].shape[1])
            rprep[ws] = pr
            obs[ws][te] = pr.standardize(Yr[ws][te], years[te])
        for mn, menu in M.items():
            g = best_in(isc, menu)
            choices.append(dict(var=var, month=month, menu=mn, block=f"{int(years[te][0])}-{int(years[te][-1])}",
                                **describe(g)))
            f = fit_predict(g, idx, fld, years, tr, te, Ys, S["detrend_predictors"])
            phys = py.to_physical(f, years[te])
            for ws in WSETS:
                pred[mn][ws][te] = rprep[ws].standardize(aggs[ws](phys), years[te])
    print(f"  {var:7s} month {month:2d}: {time.time() - t0:6.1f} s", flush=True)
    return dict(var=var, month=month, years=years.astype(int), obs=obs, pred=pred, plain=plain,
                plain_cfg={mn: describe(g) for mn, g in plain_cfg.items()}, choices=choices)


# ------------------------------------------------------------------ skill tables
def boot_index(n: int, B: int, block: int, rng) -> np.ndarray:
    """B moving-block resamples of n years (B x n positions)."""
    starts = np.arange(n - block + 1)
    k = int(np.ceil(n / block))
    return (rng.choice(starts, (B, k))[:, :, None] + np.arange(block)).reshape(B, -1)[:, :n]


def skill_tables(res: list, menus: list, B: int, seed: int):
    rng = np.random.default_rng(seed)
    region_rows, long = [], []
    for r in res:
        var, m = r["var"], r["month"]
        for ws in WSETS:
            regions, codes = D.regions(ws)
            o = r["obs"][ws]
            rho = {mn: E.col_spearman(r["pred"][mn][ws], o) for mn in menus}
            rho_p = {mn: E.col_spearman(r["plain"][mn][ws][1], r["plain"][mn][ws][0]) for mn in menus}
            for j, code in enumerate(codes):
                row = dict(weights=ws, var=var, month=m, quarter=QUARTER[m], code=code, region=regions[j],
                           n_years=len(r["years"]))
                for mn in menus:
                    row[f"rho_nested_{mn}"] = rho[mn][j]
                    row[f"mse_nested_{mn}"] = float(np.mean((r["pred"][mn][ws][:, j] - o[:, j]) ** 2))
                    row[f"rho_plain_{mn}"] = rho_p[mn][j]
                region_rows.append(row)
            long.append(pd.DataFrame({
                "weights": ws, "var": var, "month": m, "quarter": QUARTER[m],
                "year": np.repeat(r["years"], len(codes)), "code": np.tile(codes, len(r["years"])),
                **{f"e2_{mn}": ((r["pred"][mn][ws] - o) ** 2).reshape(-1) for mn in menus}}))
    R = pd.DataFrame(region_rows)
    L = pd.concat(long, ignore_index=True)
    others = [mn for mn in menus if mn != BASE]
    boots = {}

    def summarise(keys):
        rows = []
        for k, g in R.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            sel = np.ones(len(L), bool)
            for kk, vv in zip(keys, k):
                sel &= (L[kk] == vv).to_numpy()
            y = L[sel].groupby("year")[[f"e2_{mn}" for mn in menus]].mean()
            n = len(y)
            if n not in boots:
                boots[n] = boot_index(n, B, 5, rng)
            ix = boots[n]
            base = y[f"e2_{BASE}"].to_numpy()
            for mn in others:
                row = dict(zip(keys, k))
                row.update(menu=mn, label=LABEL[mn], rho_nested_roni=g[f"rho_nested_{BASE}"].mean(),
                           rho_nested=g[f"rho_nested_{mn}"].mean())
                row["d_rho_nested"] = row["rho_nested"] - row["rho_nested_roni"]
                row["pct_region_months_better"] = 100 * (g[f"rho_nested_{mn}"] > g[f"rho_nested_{BASE}"]).mean()
                row["rho_plain_roni"] = g[f"rho_plain_{BASE}"].mean()
                row["rho_plain"] = g[f"rho_plain_{mn}"].mean()
                d = base - y[f"e2_{mn}"].to_numpy()
                row["mse_reduction_pct"] = 100 * d.mean() / base.mean()
                bs = 100 * d[ix].mean(1) / base[ix].mean(1)
                row["mse_reduction_p05"], row["mse_reduction_p95"] = np.quantile(bs, [0.05, 0.95])
                row["verdict"] = ("better" if row["mse_reduction_p05"] > 0 else
                                  "worse" if row["mse_reduction_p95"] < 0 else "no clear change")
                rows.append(row)
        return pd.DataFrame(rows)

    by_vq = summarise(["weights", "var", "quarter"])
    by_v = summarise(["weights", "var"])
    by_v["quarter"] = "year"
    by_rq = summarise(["weights", "code", "quarter"])
    by_m = summarise(["weights"])
    by_m["var"], by_m["quarter"] = "all", "year"
    summary = pd.concat([by_vq, by_v, by_m], ignore_index=True)
    summary["menu"] = pd.Categorical(summary["menu"], others)
    summary = summary.sort_values(["weights", "menu", "var", "quarter"]).reset_index(drop=True)
    summary["menu"] = summary["menu"].astype(str)
    return R, summary, by_rq


# ------------------------------------------------------------------ figure
def figure(out: pathlib.Path, ws: str = "r16_cropland"):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    INK, INK2, SURF = "#0b0b0b", "#52514e", "#fcfcfb"
    DIV = LinearSegmentedColormap.from_list("div", ["#b8322f", "#e34948", "#f0efec", "#2a78d6", "#1a4f99"])
    ORDER = ["P", "SPEI3", "SM_RZ", "SM_DEEP", "RO", "E", "PET", "T", "VPD", "RS"]
    LONG = {"P": "rainfall", "SPEI3": "SPEI-3", "SM_RZ": "root-zone soil moisture", "SM_DEEP": "deep soil moisture",
            "RO": "runoff", "E": "evaporation", "PET": "potential evaporation", "T": "temperature",
            "VPD": "vapour pressure deficit", "RS": "solar radiation", "all": "all variables"}
    SHORT = {"roni_emi": "+EMI", "roni_iob": "+IOB", "roni_psea": "+Phil.\nSea", "roni_tna": "+TNA",
             "roni_emi_iob_psea": "+EMI\n+IOB\n+P.Sea", "field": "SST\nfield", "field_masked": "SST field,\nPhil.\nmasked"}
    ONE = {"roni_emi": "+EMI", "roni_iob": "+IOB", "roni_psea": "+Phil. Sea", "roni_tna": "+TNA",
           "roni_emi_iob_psea": "+EMI +IOB +P. Sea", "field": "SST field", "field_masked": "SST field, Phil. masked"}
    GRID, BLUE, ORANGE = "#e4e3df", "#2a78d6", "#eb6834"
    S = pd.read_csv(out / "skill_summary.csv")
    S = S[S["weights"] == ws]
    menus = [m for m in SHORT if m in set(S["menu"])]
    plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 9.5, "axes.titleweight": "bold",
                         "axes.titlelocation": "left", "figure.facecolor": SURF, "axes.facecolor": SURF})
    fields = [m for m in ("field", "field_masked") if m in menus]
    fig = plt.figure(figsize=(15.5 if fields else 12.5, 5.4))
    gs = fig.add_gridspec(1, 3 if fields else 2, width_ratios=[1.3, 0.75, 0.8][:3 if fields else 2], wspace=0.5)

    def heat(ax, M, H, rows, cols, rlab, clab, lim):
        ax.imshow(M, cmap=DIV, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
        for i in range(len(rows)):
            for j in range(len(cols)):
                v, h = M[i, j], H[i, j]
                if not np.isfinite(v):
                    continue
                mark = "*" if h in ("better", "worse") else ""
                ax.text(j, i, f"{v:+.1f}{mark}", ha="center", va="center", fontsize=7.3,
                        color="white" if abs(v) > 0.6 * lim else INK, fontweight="bold" if mark else "normal")
        ax.set_xticks(range(len(cols)), clab)
        ax.set_yticks(range(len(rows)), rlab)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)

    # a: year-round, every variable and menu
    yr = S[S["quarter"] == "year"]
    vs = [v for v in ORDER if v in set(yr["var"])] + ["all"]
    M = yr.pivot(index="var", columns="menu", values="mse_reduction_pct").reindex(index=vs, columns=menus)
    H = yr.pivot(index="var", columns="menu", values="verdict").reindex(index=vs, columns=menus)
    lim = max(4.0, float(np.nanmax(np.abs(M.values))))
    ax = fig.add_subplot(gs[0])
    heat(ax, M.values, H.values, vs, menus, [LONG[v] for v in vs], [SHORT[m] for m in menus], lim)
    ax.axhline(len(vs) - 1.5, color=INK2, lw=0.8)
    if "field" in menus:
        ax.axvline(menus.index("field") - 0.5, color=INK2, lw=0.8)
    ax.set_title("a  Change in hindcast error against the RONI alone,\n    all months, MSE reduction %")
    ax.text(0, -0.2, "Nested cross-validation, 16 regions (cropland). Blue = smaller error than the RONI alone,\n"
            "red = larger; * = 90 % block-bootstrap interval excludes 0.", transform=ax.transAxes, fontsize=7,
            color=INK2, va="top")

    # b: rank correlation, RONI alone against the field
    if fields:
        ax = fig.add_subplot(gs[1])
        y = np.arange(len(vs))
        base = yr.groupby("var")["rho_nested_roni"].first().reindex(vs)
        ax.scatter(base, y, s=58, facecolor=SURF, edgecolor=INK, lw=1.5, zorder=3, label="RONI alone")
        for z, (mn, c, mk) in enumerate((("field", BLUE, "o"), ("field_masked", ORANGE, "D"))):
            if mn in fields:
                r = yr[yr["menu"] == mn].set_index("var")["rho_nested"].reindex(vs)
                ax.scatter(r, y, s=30 if mk == "o" else 24, color=c, marker=mk, zorder=4 + z, edgecolor=SURF, lw=0.8,
                           label=ONE[mn])
                ax.hlines(y, np.minimum(base, r), np.maximum(base, r), color=GRID, lw=2, zorder=1)
        ax.set_yticks(y, [LONG[v] for v in vs])
        ax.set_ylim(len(vs) - 0.5, -0.5)
        ax.axhline(len(vs) - 1.5, color=INK2, lw=0.8)
        ax.set_xlabel("mean Spearman correlation, nested CV")
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(0, -0.13), ncol=1)
        ax.set_title("b  The SST field ranks the years better\n    (higher = better)")

    # c: rainfall by quarter
    p = S[(S["var"] == "P") & (S["quarter"] != "year")]
    qs = ["Q1", "Q2", "Q3", "Q4"]
    M = p.pivot(index="menu", columns="quarter", values="mse_reduction_pct").reindex(index=menus, columns=qs)
    H = p.pivot(index="menu", columns="quarter", values="verdict").reindex(index=menus, columns=qs)
    lim = max(4.0, float(np.nanmax(np.abs(M.values))))
    ax = fig.add_subplot(gs[-1])
    heat(ax, M.values, H.values, menus, qs, [ONE[m] for m in menus], [QNAME[q] for q in qs], lim)
    ax.set_title(f"{'c' if fields else 'b'}  Rainfall by season, MSE reduction %")
    ax.text(0, -0.2, "Same test, rainfall only, months of each quarter.", transform=ax.transAxes, fontsize=7,
            color=INK2, va="top")
    f = out / "sst_summary.png"
    fig.savefig(f, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {f}")


# ------------------------------------------------------------------ main
def main():
    global D, IDX, GRAM, FIRST_YEAR, MX_GRID, STEPS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--sst", help="ERSSTv5 monthly file (default data/inputs/sst/ersst.v5.sst.mnmean.nc)")
    ap.add_argument("--steps", nargs="*", type=int, default=[1, 2], choices=[1, 2])
    ap.add_argument("--vars", nargs="*")
    ap.add_argument("--months", nargs="*", type=int)
    ap.add_argument("--mx", nargs="*", type=int, default=list(range(2, 16)), help="numbers of SST EOFs to try (2-15)")
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count()))
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--figure-only", action="store_true")
    a = ap.parse_args()
    cfg = C.load(a.config)
    cfg["model"]["predictors"] = ["roni"]          # the baseline is the main run, whatever the config says
    out = C.out(cfg, "analysis", "sst", "x").parent
    out.mkdir(parents=True, exist_ok=True)
    if a.figure_only:
        figure(out)
        return
    STEPS, MX_GRID = tuple(sorted(set(a.steps))), sorted(set(a.mx))
    sst_path = pathlib.Path(a.sst) if a.sst else cfg["_root"] / "data" / "inputs" / "sst" / "ersst.v5.sst.mnmean.nc"
    if not sst_path.exists():
        raise SystemExit(f"{sst_path} is missing; download it with\n  mkdir -p {sst_path.parent}\n  curl -L -o {sst_path} "
                         "https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc")
    D, variables, extra = F.load_data(cfg, refresh_indices=False, with_hourly=True)
    y0, y1 = cfg["period"]["train"]
    FIRST_YEAR = y0
    with C.Timer("SST indices and fields"):
        sst = SST(sst_path, tuple(cfg["period"]["clim"]))
        IDX, raw = build_indices(sst, D.P)
        GRAM, eofs, finfo = build_grams(sst, D.lag_sets, y0, y1)
    print(f"ERSSTv5 to {sst.last}; RONI to {extra['index_info']['roni_last']}; field {finfo[False]['n_points']} ocean points "
          f"({finfo[True]['n_points']} with the Philippine waters masked)")
    lines = [f"SST predictors beyond the RONI (ERSSTv5 to {sst.last}; nested CV, July-June 5-year blocks)"]

    IX = IDX[["roni", "emi", "iob", "psea", "tna", "roni_ersst", "dmi_ersst", "dmi_psl"]]
    IX.rename_axis("date").to_csv(out / "indices_monthly.csv", float_format="%.4f")
    chk = index_checks(IX, y0, y1)
    chk.to_csv(out / "index_checks.csv", index=False)
    cr = index_correlations(IX, y0, y1)
    cr.to_csv(out / "index_correlation_with_roni.csv", index=False)
    eofs.to_csv(out / "sst_eof_variance.csv", index=False)
    lines.append("Checks of the index construction\n" + chk.round(3).to_string(index=False))
    lines.append("Correlation of each index with the RONI (quarterly means, 1950-2025)\n"
                 + cr.pivot(index="months", columns="index", values="r_with_roni")
                 .reindex(["JFM", "AMJ", "JAS", "OND", "all months"]).round(2).to_string())
    ev = eofs.groupby("masked")[[f"eof{j}" for j in range(1, 6)]].mean()
    ev.index = ["field", "field, Philippine waters masked"]
    lines.append("Variance of the SST field explained by its leading EOFs (sync, mean over target months, 1950-2025)\n"
                 + ev.round(3).to_string())

    variables = [v for v in (a.vars or variables) if v in variables]
    months = a.months or list(range(1, 13))
    tasks = [(v, m) for v in variables for m in months]
    menus = [m for m in INDEX_MENUS if m == BASE or 1 in STEPS] + (list(FIELD_MENUS) if 2 in STEPS else [])
    print(f"{len(tasks)} variable-months, {len(menus)} menus ({', '.join(menus)}), Mx {MX_GRID}, {a.workers} workers")
    t0 = time.time()
    if a.workers > 1:
        with mp.get_context("fork").Pool(a.workers) as pool:
            res = pool.map(run_one, tasks, chunksize=1)
    else:
        res = [run_one(t) for t in tasks]
    print(f"cross-validation in {(time.time() - t0) / 60:.1f} min")
    R, SUM, RQ = skill_tables(res, menus, a.boot, cfg["model"].get("seed", 42))
    R.to_csv(out / "skill_regions.csv", index=False)
    SUM.to_csv(out / "skill_summary.csv", index=False)
    RQ.to_csv(out / "skill_by_region_quarter.csv", index=False)
    ch = pd.DataFrame([c for r in res for c in r["choices"]])
    ch.to_csv(out / "nested_choices.csv", index=False)
    pc = pd.DataFrame([dict(var=r["var"], month=r["month"], menu=mn, **g) for r in res for mn, g in r["plain_cfg"].items()])
    pc.to_csv(out / "plain_choices.csv", index=False)

    s = SUM[SUM["weights"] == WSETS[0]]
    cell = s.assign(cell=s["mse_reduction_pct"].map("{:+.1f}".format)
                    + s["verdict"].map({"better": " [+]", "worse": " [-]", "no clear change": ""}))
    yr = cell[cell["quarter"] == "year"].pivot(index="var", columns="menu", values="cell")
    lines.append(f"MSE reduction against the RONI alone (%, nested CV, all months, {WSETS[0]}; > 0 = smaller error; "
                 "[+] / [-] = 90 % interval above / below 0)\n"
                 + yr.reindex(columns=[m for m in menus if m != BASE]).to_string())
    pq = cell[(cell["var"] == "P") & (cell["quarter"] != "year")].pivot(index="menu", columns="quarter", values="cell")
    lines.append("Rainfall by quarter, MSE reduction against the RONI alone (%)\n"
                 + pq.reindex([m for m in menus if m != BASE]).to_string())
    rho = s[s["quarter"] == "year"].pivot(index="var", columns="menu", values="rho_nested")
    rho.insert(0, BASE, s[s["quarter"] == "year"].groupby("var")["rho_nested_roni"].first())
    lines.append("Mean nested Spearman rho over regions and months\n" + rho.round(3).to_string())
    if 2 in STEPS:
        f = ch[ch["menu"].isin(list(FIELD_MENUS))]
        lines.append("Number of SST EOFs chosen in the outer folds (share of folds, %)\n"
                     + (100 * f.groupby("menu")["Mx"].value_counts(normalize=True).unstack(fill_value=0)).round(0)
                     .to_string())
    txt = "\n\n".join(lines)
    (out / "summary.txt").write_text(txt + "\n")
    print("\n" + txt + f"\n\nwrote {out}")
    figure(out)


if __name__ == "__main__":
    main()
