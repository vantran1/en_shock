#!/usr/bin/env python3
"""Is the response of the Philippine weather to ENSO non-linear enough to matter? A stand-alone check, like the
DMI and SST analyses; it does not change the fit or any pipeline output.

Part 1, skill. Four non-linear models against the RONI alone (the main run), with everything else the fit's
own: predictands, transforms, trend, lag sets, leave-5-years-out CV and the nested CV of step 3 (5-year
July-June blocks held out, the configuration chosen again on the remaining years):
  roni_asym    EOF-CCA on the El Nino and La Nina parts of the RONI, max(RONI, 0) and min(RONI, 0), at every
               lag of a lag set: a different response to El Nino and to La Nina
  roni_quad    EOF-CCA on RONI and RONI^2 at every lag: strong events act more than in proportion
  analog_roni  the k past years closest in RONI (the lags of a lag set, standardised): the mean of their
               weather; no linearity at all. k (3-30) is chosen with the lag set
  analog_sst   the k past years with the closest SST map: tropical Indo-Pacific (30S-30N, 40E-80W), the
               waters around the Philippines masked (110E-135E, 0-25N), relative anomalies, centred 3-month
               means, the lags of a lag set side by side; distance in the space of its leading Mx EOFs,
               recomputed in each fold. Mx (2-12) and k (3-30) are chosen with the lag set
  The analogue forecast is the mean standardised anomaly of the k years at every cell, put back in physical
  units with the fold's transform and trend. The linear SST-field CCA of analysis/sst_predictors.py is the
  linear benchmark for analog_sst; its results against the same baseline are shown next to these.
  Skill and the paired block-bootstrap test of the MSE are those of the DMI and SST analyses.

Part 2, shape. Holding a linear trend, the observed quarterly response (national mean and every region) to
the El Nino side of the RONI (slope per unit for RONI > 0) and to the La Nina side (slope per unit for
RONI < 0), with the test of equal slopes; the RONI is the quarterly mean of the same quarter.

Needs the ERSSTv5 file of analysis/sst_predictors.py (data/inputs/sst/ersst.v5.sst.mnmean.nc).

  python analysis/nonlinear_test.py                    # all variables and months (about 15 minutes on 2 cores)
  python analysis/nonlinear_test.py --vars P --months 10 11 12
  python analysis/nonlinear_test.py --figure-only
Writes outputs/analysis/nonlinear/*.csv, summary.txt and nonlinear_summary.png.
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

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from stage1 import config as C  # noqa: E402
from stage1 import engine as E  # noqa: E402
from stage1 import fit as F  # noqa: E402
from stage1 import indices as I  # noqa: E402
import dmi_analysis as DA  # noqa: E402
import sst_predictors as SP  # noqa: E402

WSETS = ["r16_cropland", "r17_population"]
QUARTER = {m: f"Q{(m - 1) // 3 + 1}" for m in range(1, 13)}
QNAME = {"Q1": "JFM", "Q2": "AMJ", "Q3": "JAS", "Q4": "OND"}
BASE = "roni"
LINEAR_MENUS = {"roni": ("roni",), "roni_asym": ("roni_pos", "roni_neg"), "roni_quad": ("roni", "roni_sq")}
ANALOG_MENUS = ("analog_roni", "analog_sst")
K_GRID = [3, 5, 8, 12, 20, 30]
AMX_GRID = [2, 3, 4, 6, 8, 12]
LABEL = {"roni": "RONI alone", "roni_asym": "El Nino and La Nina parts", "roni_quad": "RONI + RONI squared",
         "analog_roni": "Analogues in RONI", "analog_sst": "Analogues in the SST map (Phil. masked)",
         "field": "Linear SST field (SST analysis)", "field_masked": "Linear SST field, Phil. masked (SST analysis)"}

D: F.Data = None
PX: pd.DataFrame = None     # predictor table: roni and its non-linear transforms
GRAM: dict = None           # (month, lag set, masked) -> Gram matrix of the SST field rows, years FIRST_YEAR..
FIRST_YEAR = None


# ------------------------------------------------------------------ predictors
def predictor_table(P: pd.DataFrame) -> pd.DataFrame:
    r = P["roni"]
    return pd.DataFrame({"roni": r, "roni_pos": r.clip(lower=0), "roni_neg": r.clip(upper=0), "roni_sq": r ** 2},
                        index=P.index)


def field_scores(K: np.ndarray, tr, te, kmax: int):
    """Leading PC scores (not standardised: the distance between two years is that between their maps, cut to
    the leading EOFs) of the training rows and of the test rows projected on the same EOFs, from the Gram matrix."""
    tr, te = np.flatnonzero(tr), np.flatnonzero(te)
    Ktt = K[np.ix_(tr, tr)]
    rm = Ktt.mean(1)
    gm = rm.mean()
    w, V = np.linalg.eigh(Ktt - rm[:, None] - rm[None, :] + gm)
    w, V = np.clip(w[::-1][:kmax], 1e-12, None), V[:, ::-1][:, :kmax]
    Kx = K[np.ix_(te, tr)]
    kc = Kx - Kx.mean(1, keepdims=True) - rm[None, :] + gm
    s = np.sqrt(w)
    return V * s, kc @ V / s


def analog_mean(Ys, d, ks):
    """Mean of the training rows of Ys at the k smallest distances, for every k (ties: the earlier year)."""
    order = np.argsort(d, kind="stable")
    return {k: Ys[order[:k]].mean(0) for k in ks}


def parse(name: str):
    parts = name.split(" | ")
    base = " | ".join(p for p in parts if "=" not in p)
    par = dict(p.split("=") for p in parts if "=" in p)
    return base, {k: int(v) for k, v in par.items()}


def candidates(var: str, month: int, years: np.ndarray):
    yi = years.astype(int)
    lin, anx, anf, menus = {}, {}, {}, {}
    for mn, preds in LINEAR_MENUS.items():
        menus[mn] = []
        for ls, lags in D.lag_sets.items():
            lin[f"{mn} | {ls}"] = I.design(PX, month, lags, preds).reindex(yi).to_numpy()
            menus[mn].append(f"{mn} | {ls}")
    menus["analog_roni"] = []
    for ls, lags in D.lag_sets.items():
        anx[f"analog_roni | {ls}"] = I.design(PX, month, lags, ("roni",)).reindex(yi).to_numpy()
        menus["analog_roni"] += [f"analog_roni | {ls} | k={k}" for k in K_GRID]
    pos = yi - FIRST_YEAR
    menus["analog_sst"] = []
    for ls in D.lag_sets:
        anf[f"analog_sst | {ls}"] = GRAM[(month, ls, True)][np.ix_(pos, pos)]
        menus["analog_sst"] += [f"analog_sst | {ls} | Mx={m} | k={k}" for m in AMX_GRID for k in K_GRID]
    for X in list(lin.values()) + list(anx.values()):
        if not np.isfinite(X).all():
            raise SystemExit(f"missing RONI values for {var} month {month}")
    return lin, anx, anf, menus


# ------------------------------------------------------------------ cross-validation
def cv_all(Y, kind, years, lin, anx, anf, S):
    """Leave-`cv_window`-out CV of every configuration, as E.cv_run: EOF-CCA on the linear candidates,
    analogues in index space and in SST-EOF space (keys (name, 0, 0))."""
    n, q = Y.shape
    half = S["cv_window"] // 2
    my_grid, mc_grid = S["my_grid"], S["mc_grid"]
    grid = E.config_grid({k: X.shape[1] for k, X in lin.items()}, my_grid, mc_grid)
    grid += [(f"{c} | k={k}", 0, 0) for c in anx for k in K_GRID]
    grid += [(f"{c} | Mx={m} | k={k}", 0, 0) for c in anf for m in AMX_GRID for k in K_GRID]
    obs = np.empty((n, q))
    pred = {g: np.empty((n, q)) for g in grid}
    preps = []
    for k in range(n):
        tr = np.abs(years - years[k]) > half
        te = np.zeros(n, bool)
        te[k] = True
        tk = years[k:k + 1]
        sq = np.sqrt(tr.sum() - 1)
        pb, Ys = E.prep_y(Y[tr], years[tr], [kind] * q)
        obs[k] = pb.standardize(Y[k:k + 1], tk)[0]
        preps.append([pb])
        U, Sv, Vt = E.svd_top(Ys, max(my_grid))
        for ls, X in lin.items():
            pxx, Xs = E.prep_x(X[tr], years[tr], S.get("detrend_predictors", False))
            W = E.whiten(Xs)
            E.predict_all(Xs @ W / sq, pxx.standardize(X[k:k + 1], tk)[0] @ W, U, Sv, Vt, sq, X.shape[1], pred, k, ls,
                          my_grid, mc_grid)
        for c, X in anx.items():
            pxx, Xs = E.prep_x(X[tr], years[tr], S.get("detrend_predictors", False))
            xt = pxx.standardize(X[k:k + 1], tk)[0]
            for kk, p in analog_mean(Ys, ((Xs - xt) ** 2).sum(1), K_GRID).items():
                pred[(f"{c} | k={kk}", 0, 0)][k] = p
        for c, K in anf.items():
            Ptr, Pte = field_scores(K, tr, te, max(AMX_GRID))
            for m in AMX_GRID:
                for kk, p in analog_mean(Ys, ((Ptr[:, :m] - Pte[0, :m]) ** 2).sum(1), K_GRID).items():
                    pred[(f"{c} | Mx={m} | k={kk}", 0, 0)][k] = p
    return dict(grid=grid, obs=obs, pred=pred, preps=preps, sizes=[q], years=years)


def fit_predict(g, lin, anx, anf, years, tr, te, Ys, detrend):
    name, My, Mc = g
    if name in lin:
        X = lin[name]
        pxx, Xs = E.prep_x(X[tr], years[tr], detrend)
        G, _ = E.cca_operator(Xs, Ys, My, Mc)
        return pxx.standardize(X[te], years[te]) @ G.T
    base, par = parse(name)
    if base in anx:
        X = anx[base]
        pxx, Xs = E.prep_x(X[tr], years[tr], detrend)
        A, B = Xs, pxx.standardize(X[te], years[te])
    else:
        A, B = field_scores(anf[base], tr, te, par["Mx"])
    return np.stack([analog_mean(Ys, ((A - b) ** 2).sum(1), [par["k"]])[par["k"]] for b in B])


def describe(g) -> dict:
    base, par = parse(g[0])
    analog = base.startswith("analog")
    return dict(lagset=base.split(" | ")[1], Mx=par.get("Mx", np.nan), k=par.get("k", np.nan),
                My=np.nan if analog else g[1], Mc=np.nan if analog else g[2])


def run_one(task):
    var, month = task
    t0 = time.time()
    kind = C.PREDICTANDS[var][3]
    years, Y, _ = D.month_data(var, month)
    q = Y.shape[1]
    S = D.S
    lin, anx, anf, M = candidates(var, month, years)
    aggs = {ws: D.aggregator(ws, var, month) for ws in WSETS}
    Yr = {ws: a(Y) for ws, a in aggs.items()}

    cv = cv_all(Y, kind, years, lin, anx, anf, S)
    scores = SP.cv_scores(cv)
    plain, plain_cfg = {}, {}
    for mn, menu in M.items():
        g = SP.best_in(scores, menu)
        plain_cfg[mn] = describe(g)
        phys = E.cv_physical(cv, g, 0)
        plain[mn] = {ws: F.regional_cv(Yr[ws], aggs[ws](phys), years, kind, S["cv_window"]) for ws in WSETS}
    del cv

    obs = {ws: np.empty(Yr[ws].shape) for ws in WSETS}
    pred = {mn: {ws: np.empty(Yr[ws].shape) for ws in WSETS} for mn in M}
    choices = []
    nb = F.nested_settings(D.cfg)
    for te in F.nested_blocks(years, month, nb["first_year"], nb["block_len"], nb["start_month"]):
        tr = ~te
        icv = cv_all(Y[tr], kind, years[tr], {k: x[tr] for k, x in lin.items()}, {k: x[tr] for k, x in anx.items()},
                     {k: K[np.ix_(tr, tr)] for k, K in anf.items()}, S)
        isc = SP.cv_scores(icv)
        del icv
        py, Ys = E.prep_y(Y[tr], years[tr], [kind] * q)
        rprep = {}
        for ws in WSETS:
            pr, _ = E.prep_y(Yr[ws][tr], years[tr], [kind] * Yr[ws].shape[1])
            rprep[ws] = pr
            obs[ws][te] = pr.standardize(Yr[ws][te], years[te])
        for mn, menu in M.items():
            g = SP.best_in(isc, menu)
            choices.append(dict(var=var, month=month, menu=mn, block=f"{int(years[te][0])}-{int(years[te][-1])}",
                                **describe(g)))
            f = fit_predict(g, lin, anx, anf, years, tr, te, Ys, S["detrend_predictors"])
            phys = py.to_physical(f, years[te])
            for ws in WSETS:
                pred[mn][ws][te] = rprep[ws].standardize(aggs[ws](phys), years[te])
    print(f"  {var:7s} month {month:2d}: {time.time() - t0:6.1f} s", flush=True)
    return dict(var=var, month=month, years=years.astype(int), obs=obs, pred=pred, plain=plain, plain_cfg=plain_cfg,
                choices=choices)


# ------------------------------------------------------------------ part 1 tables (as in the SST analysis)
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
                boots[n] = SP.boot_index(n, B, 5, rng)
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


# ------------------------------------------------------------------ part 2: El Nino against La Nina
def ols_cov(y, X):
    ok = np.isfinite(y) & np.isfinite(X).all(1)
    y, X = y[ok], np.column_stack([np.ones(ok.sum()), X[ok]])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    dof = len(y) - X.shape[1]
    V = np.linalg.inv(X.T @ X) * (e @ e) / dof
    return beta[1:], V[1:, 1:], dof


def asymmetry_table(variables: list[str]) -> pd.DataFrame:
    """Quarterly anomaly on max(RONI, 0), min(RONI, 0) and a linear trend, 1950-2025: the slope per unit of RONI
    on each side, and the test of equal slopes (a linear response)."""
    DA.D = D
    y0, y1 = D.cfg["period"]["train"]
    c0, c1 = D.cfg["period"]["clim"]
    P = D.P[(D.P.index.year >= y0) & (D.P.index.year <= y1)]
    Q = DA.quarterly(P[["roni"]], last=False)
    rows = []
    for ws in WSETS:
        regions, codes = D.regions(ws)
        wn = DA.national_weights(ws)
        for v in variables:
            M = DA.regional_monthly(v, ws)
            M["PH"] = M[codes].to_numpy() @ wn
            Yq = DA.quarterly(M, last=v in DA.END_OF_QUARTER)
            yrs = Yq.index.get_level_values("year")
            clim = Yq[(yrs >= c0) & (yrs <= c1)].groupby(level="q").mean()
            for qn in range(1, 5):
                yq = Yq.xs(qn, level="q")
                r = Q.xs(qn, level="q").reindex(yq.index)["roni"].to_numpy(float)
                X = np.column_stack([np.clip(r, 0, None), np.clip(r, None, 0), yq.index.to_numpy(float) - 2000.0])
                for code in list(codes) + ["PH"]:
                    b, V, dof = ols_cov(yq[code].to_numpy(float), X)
                    se_d = np.sqrt(V[0, 0] + V[1, 1] - 2 * V[0, 1])
                    t90 = stats.t.ppf(0.95, dof)
                    row = dict(weights=ws, var=v, quarter=f"Q{qn}", months=QNAME[f"Q{qn}"], code=code,
                               region="Philippines" if code == "PH" else regions[list(codes).index(code)],
                               n_el_nino=int((r > 0).sum()), n_la_nina=int((r < 0).sum()),
                               slope_el_nino=b[0], slope_el_nino_lo=b[0] - t90 * np.sqrt(V[0, 0]),
                               slope_el_nino_hi=b[0] + t90 * np.sqrt(V[0, 0]),
                               slope_la_nina=b[1], slope_la_nina_lo=b[1] - t90 * np.sqrt(V[1, 1]),
                               slope_la_nina_hi=b[1] + t90 * np.sqrt(V[1, 1]),
                               p_equal_slopes=2 * stats.t.sf(abs((b[0] - b[1]) / se_d), dof),
                               clim_mean=float(clim.loc[qn, code]))
                    if v in ("P", "RO", "E"):
                        for k in ("slope_el_nino", "slope_el_nino_lo", "slope_el_nino_hi", "slope_la_nina",
                                  "slope_la_nina_lo", "slope_la_nina_hi"):
                            row[f"{k}_pct"] = 100 * row[k] / row["clim_mean"]
                    rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ figure
def figure(out: pathlib.Path, ws: str = "r16_cropland"):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    RED, BLUE = "#e34948", "#2a78d6"
    DIV = LinearSegmentedColormap.from_list("div", ["#b8322f", "#e34948", "#f0efec", "#2a78d6", "#1a4f99"])
    ORDER = ["P", "SPEI3", "SM_RZ", "SM_DEEP", "RO", "E", "PET", "T", "VPD", "RS"]
    LONG = {"P": "rainfall", "SPEI3": "SPEI-3", "SM_RZ": "root-zone soil moisture", "SM_DEEP": "deep soil moisture",
            "RO": "runoff", "E": "evaporation", "PET": "potential evaporation", "T": "temperature",
            "VPD": "vapour pressure deficit", "RS": "solar radiation", "all": "all variables"}
    SHORT = {"roni_asym": "El Niño /\nLa Niña\nparts", "roni_quad": "RONI\n+ RONI²", "analog_roni": "Analogues\nin RONI",
             "analog_sst": "Analogues\nin SST map", "field": "SST field", "field_masked": "SST field,\nPhil.\nmasked"}
    S = pd.read_csv(out / "skill_summary.csv")
    S = S[S["weights"] == ws]
    sst = out.parent / "sst" / "skill_summary.csv"
    if sst.exists():
        T = pd.read_csv(sst)
        S = pd.concat([S, T[(T["weights"] == ws) & T["menu"].isin(["field", "field_masked"])]], ignore_index=True)
    A = pd.read_csv(out / "asymmetry_el_nino_la_nina.csv")
    menus = [m for m in SHORT if m in set(S["menu"])]
    plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 9.5, "axes.titleweight": "bold",
                         "axes.titlelocation": "left", "figure.facecolor": SURF, "axes.facecolor": SURF})
    fig = plt.figure(figsize=(13, 5.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1], wspace=0.35)

    ax = fig.add_subplot(gs[0])
    yr = S[S["quarter"] == "year"]
    vs = [v for v in ORDER if v in set(yr["var"])] + ["all"]
    M = yr.pivot(index="var", columns="menu", values="mse_reduction_pct").reindex(index=vs, columns=menus)
    H = yr.pivot(index="var", columns="menu", values="verdict").reindex(index=vs, columns=menus)
    lim = max(4.0, float(np.nanmax(np.abs(M.values))))
    ax.imshow(M.values, cmap=DIV, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for i in range(len(vs)):
        for j in range(len(menus)):
            v, h = M.values[i, j], H.values[i, j]
            if not np.isfinite(v):
                continue
            mark = "*" if h in ("better", "worse") else ""
            ax.text(j, i, f"{v:+.1f}{mark}", ha="center", va="center", fontsize=7.3,
                    color="white" if abs(v) > 0.6 * lim else INK, fontweight="bold" if mark else "normal")
    ax.set_xticks(range(len(menus)), [SHORT[m] for m in menus])
    ax.set_yticks(range(len(vs)), [LONG[v] for v in vs])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.axhline(len(vs) - 1.5, color=INK2, lw=0.8)
    if "field" in menus:
        x = menus.index("field") - 0.5
        ax.axvline(x, color=INK2, lw=0.8)
        ax.text(x + 0.1, -0.75, "linear, for reference", fontsize=7, color=INK2, va="bottom")
    ax.set_title("a  Non-linear models against the RONI alone,\n    all months, MSE reduction %", pad=14)
    ax.text(0, -0.2, "Nested cross-validation, 16 regions (cropland). Blue = smaller error than the RONI alone,\n"
            "red = larger; * = 90 % block-bootstrap interval excludes 0.", transform=ax.transAxes, fontsize=7,
            color=INK2, va="top")

    ax = fig.add_subplot(gs[1])
    a = A[(A["weights"] == ws) & (A["code"] == "PH") & (A["var"] == "P")].set_index("quarter")
    qs = ["Q1", "Q2", "Q3", "Q4"]
    x = np.arange(4)
    for off, side, c, lab in ((-0.13, "el_nino", RED, "El Niño side (RONI > 0)"), (0.13, "la_nina", BLUE, "La Niña side (RONI < 0)")):
        s = a.loc[qs, f"slope_{side}_pct"]
        lo, hi = a.loc[qs, f"slope_{side}_lo_pct"], a.loc[qs, f"slope_{side}_hi_pct"]
        ax.errorbar(x + off, s, yerr=[s - lo, hi - s], fmt="o", ms=7, color=c, ecolor=c, elinewidth=2, capsize=0,
                    label=lab, mec=SURF, mew=0.8)
    for i, qq in enumerate(qs):
        top = max(a.loc[qq, "slope_el_nino_hi_pct"], a.loc[qq, "slope_la_nina_hi_pct"])
        ax.annotate(f"p={a.loc[qq, 'p_equal_slopes']:.2f}", (x[i], top), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=7, color=INK2)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, [QNAME[q] for q in qs])
    ax.set_ylabel("national rainfall change per unit of RONI, % of mean")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(0, -0.1), ncol=2)
    ax.set_title("b  Is the rainfall response to El Niño and La Niña\n    the same per unit of RONI?", pad=14)
    ax.text(0, -0.2, "Observed, 1950–2025, quarterly means, linear trend held; bars = 90 % intervals. Below 0 on both\n"
            "sides = drier with El Niño and wetter with La Niña; equal slopes = a linear response (p tests this).",
            transform=ax.transAxes, fontsize=7, color=INK2, va="top")
    f = out / "nonlinear_summary.png"
    fig.savefig(f, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {f}")


# ------------------------------------------------------------------ main
def main():
    global D, PX, GRAM, FIRST_YEAR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--sst", help="ERSSTv5 monthly file (default data/inputs/sst/ersst.v5.sst.mnmean.nc)")
    ap.add_argument("--vars", nargs="*")
    ap.add_argument("--months", nargs="*", type=int)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count()))
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--figure-only", action="store_true")
    a = ap.parse_args()
    cfg = C.load(a.config)
    cfg["model"]["predictors"] = ["roni"]
    out = C.out(cfg, "analysis", "nonlinear", "x").parent
    out.mkdir(parents=True, exist_ok=True)
    if a.figure_only:
        figure(out)
        return
    sst_path = pathlib.Path(a.sst) if a.sst else cfg["_root"] / "data" / "inputs" / "sst" / "ersst.v5.sst.mnmean.nc"
    if not sst_path.exists():
        raise SystemExit(f"{sst_path} is missing: see analysis/sst_predictors.py for the download")
    D, variables, extra = F.load_data(cfg, refresh_indices=False, with_hourly=True)
    y0, y1 = cfg["period"]["train"]
    FIRST_YEAR = y0
    PX = predictor_table(D.P)
    with C.Timer("SST fields"):
        GRAM, _, finfo = SP.build_grams(SP.SST(sst_path, tuple(cfg["period"]["clim"])), D.lag_sets, y0, y1)
    print(f"RONI to {extra['index_info']['roni_last']}; SST map {finfo[True]['n_points']} ocean points (Philippine waters masked)")
    variables = [v for v in (a.vars or variables) if v in variables]
    lines = ["Non-linear responses to ENSO (nested CV, July-June 5-year blocks; baseline: the RONI alone, linear)"]

    # part 2 first (seconds)
    A = asymmetry_table(variables)
    A.to_csv(out / "asymmetry_el_nino_la_nina.csv", index=False)
    ph = A[(A["weights"] == WSETS[0]) & (A["code"] == "PH")].copy()
    cols = ["slope_el_nino", "slope_la_nina", "p_equal_slopes"]
    lines.append(f"Observed response per unit of RONI on each side, national ({WSETS[0]}), quarterly, 1950-2025;\n"
                 "p = test of equal slopes (small p = an asymmetric, non-linear response)\n"
                 + ph.set_index(["var", "months"])[cols].round(3).to_string())
    pr = ph[ph["var"] == "P"].set_index("months")[["slope_el_nino_pct", "slope_la_nina_pct", "p_equal_slopes"]]
    lines.append("   rainfall, % of the quarter's mean per unit of RONI\n" + pr.round(2).to_string())
    reg = A[(A["code"] != "PH") & (A["weights"] == WSETS[0])]
    lines.append(f"   region-quarter-variable slopes that differ at p < 0.1: {100 * (reg['p_equal_slopes'] < 0.1).mean():.0f} % "
                 f"of {len(reg)} (10 % expected by chance)")

    # part 1
    months = a.months or list(range(1, 13))
    tasks = [(v, m) for v in variables for m in months]
    menus = list(LINEAR_MENUS) + list(ANALOG_MENUS)
    print(f"{len(tasks)} variable-months, {len(menus)} menus ({', '.join(menus)}), {a.workers} workers")
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
    pd.DataFrame([dict(var=r["var"], month=r["month"], menu=mn, **g) for r in res for mn, g in r["plain_cfg"].items()]
                 ).to_csv(out / "plain_choices.csv", index=False)

    s = SUM[SUM["weights"] == WSETS[0]]
    cell = s.assign(cell=s["mse_reduction_pct"].map("{:+.1f}".format)
                    + s["verdict"].map({"better": " [+]", "worse": " [-]", "no clear change": ""}))
    others = [m for m in menus if m != BASE]
    lines.append(f"MSE reduction against the RONI alone (%, nested CV, all months, {WSETS[0]}; > 0 = smaller error; "
                 "[+] / [-] = 90 % interval above / below 0)\n"
                 + cell[cell["quarter"] == "year"].pivot(index="var", columns="menu", values="cell")
                 .reindex(columns=others).to_string())
    lines.append("By quarter, all variables pooled\n"
                 + (s[s["quarter"] != "year"].groupby(["menu", "quarter"])["mse_reduction_pct"].mean().unstack()
                    .reindex(others).round(1).to_string()))
    lines.append("Rainfall by quarter, MSE reduction against the RONI alone (%)\n"
                 + cell[(cell["var"] == "P") & (cell["quarter"] != "year")].pivot(index="menu", columns="quarter", values="cell")
                 .reindex(others).to_string())
    rho = s[s["quarter"] == "year"].pivot(index="var", columns="menu", values="rho_nested").reindex(columns=others)
    rho.insert(0, BASE, s[s["quarter"] == "year"].groupby("var")["rho_nested_roni"].first())
    lines.append("Mean nested Spearman rho over regions and months\n" + rho.round(3).to_string())
    sst = out.parent / "sst" / "skill_summary.csv"
    if sst.exists():
        T = pd.read_csv(sst)
        T = T[(T["weights"] == WSETS[0]) & (T["var"] == "all") & T["menu"].isin(["field", "field_masked"])]
        lines.append("For reference, the linear SST-field CCA (analysis/sst_predictors.py), same baseline, all variables\n"
                     + T[["menu", "rho_nested", "mse_reduction_pct", "mse_reduction_p05", "mse_reduction_p95"]]
                     .round(3).to_string(index=False))
    an = ch[ch["menu"].isin(list(ANALOG_MENUS))]
    lines.append("Analogues: number of years averaged (k) chosen in the outer folds, share %\n"
                 + (100 * an.groupby("menu")["k"].value_counts(normalize=True).unstack(fill_value=0)).round(0).to_string())
    txt = "\n\n".join(lines)
    (out / "summary.txt").write_text(txt + "\n")
    print("\n" + txt + f"\n\nwrote {out}")
    figure(out)


if __name__ == "__main__":
    main()
