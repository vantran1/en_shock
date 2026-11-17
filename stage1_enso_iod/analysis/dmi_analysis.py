#!/usr/bin/env python3
"""DMI analysis: what does the Indian Ocean Dipole add to the RONI in Stage 1? A stand-alone check; it does
not change the fit. Three questions:

1. Skill. Does RONI + DMI predict the weather better than RONI alone?
   The fit (RONI and DMI in each of the four lag sets) is compared with the same four lag sets holding the
   RONI only, with everything else the fit's own: predictands, transforms, trend, EOF-CCA, (My, Mc) grid,
   leave-5-years-out CV and the nested CV of step 3 (5-year July-June blocks held out, the configuration chosen
   again on the remaining years). A third menu offers both kinds of lag set, so the CV itself decides whether
   to keep the DMI. Skill on the 16 regions (cropland weights) and the 17 regions (population weights).
   The paired test: for every held-out year, the squared error of the nested hindcast (standardised anomaly)
   with the RONI only minus that with RONI + DMI, averaged over the months and regions of a group; a
   moving-block bootstrap over years (5-year blocks) gives a 90 % interval for the reduction of the MSE.

2. Sign. Holding the RONI fixed, does a positive IOD make the Philippines wetter or drier, and when?
   (a) observed: each region's quarterly anomaly regressed on the quarterly mean RONI and DMI and a linear
       trend, 1950-2025; the DMI coefficient per +1 SD of the DMI in that quarter, with its OLS interval.
       A second specification uses the DMI of the previous quarter, with the RONI of both quarters.
   (b) the Stage 1 models: the regional response to a DMI held at +1 SD in every lag of the model, RONI at 0,
       in today's climate (t*), minus the response to 0 (the neutral path of the simulation).

3. Correlation of RONI and DMI by quarter and calendar month (1950-2025 and a recent window), with the variance
   inflation factor 1 / (1 - r^2), the lead-lag correlations and each index's persistence from one quarter to
   the next; and the years in which the two indices disagree (positive IOD without El Nino and the reverse),
   which are the only years that separate their effects.

  python analysis/dmi_analysis.py                      # all variables and months, about 20 minutes on 2 cores
  python analysis/dmi_analysis.py --vars P SPEI3 --months 9 10 11
Writes outputs/analysis/dmi/*.csv and summary.txt.
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
MENUS = ("roni_dmi", "roni", "free")
QUARTER = {m: f"Q{(m - 1) // 3 + 1}" for m in range(1, 13)}
QNAME = {"Q1": "JFM", "Q2": "AMJ", "Q3": "JAS", "Q4": "OND"}
END_OF_QUARTER = ("SPEI3",)              # 3-month accumulations: the quarter is the value of its last month
WET_VARS = ("P", "SPEI3", "SM_RZ", "SM_DEEP", "RO", "E")
D: F.Data = None                         # set in main, shared with the worker processes by fork


# ------------------------------------------------------------------ 1. skill
def month_inputs(var: str, month: int):
    """The fit's data for one target month, with each lag set also in a RONI-only version."""
    years, Y, X = D.month_data(var, month)
    out = {}
    for ls, lags in D.lag_sets.items():
        names = I.x_names(lags)
        roni = [i for i, nm in enumerate(names) if nm.startswith("roni")]
        out[ls] = X[ls]
        out[f"{ls} | RONI only"] = X[ls][:, roni]
    return years, Y, out


def menus():
    both = list(D.lag_sets)
    roni = [f"{ls} | RONI only" for ls in D.lag_sets]
    return {"roni_dmi": both, "roni": roni, "free": both + roni}


def best_in(scores: dict, menu) -> tuple:
    sub = {g: s for g, s in scores.items() if g[0] in menu}
    return max(sub, key=sub.get)


def run_one(task):
    var, month = task
    t0 = time.time()
    kind = C.PREDICTANDS[var][3]
    years, Y, X = month_inputs(var, month)
    n, q = Y.shape
    S = D.S
    M = menus()
    aggs = {ws: D.aggregator(ws, var, month) for ws in WSETS}
    Yr = {ws: a(Y) for ws, a in aggs.items()}

    # plain CV (configuration chosen on all years, as in the fit)
    cv = E.cv_run([Y], [kind], X, years, S)
    _, _, scores = E.select(cv)
    plain, plain_cfg = {}, {}
    for mn, menu in M.items():
        g = best_in(scores, menu)
        plain_cfg[mn] = g
        phys = E.cv_physical(cv, g, 0)
        plain[mn] = {ws: F.regional_cv(Yr[ws], aggs[ws](phys), years, kind, S["cv_window"]) for ws in WSETS}

    # nested CV: the calendar blocks of step 3; one inner CV serves the three menus
    obs = {ws: np.empty(Yr[ws].shape) for ws in WSETS}
    pred = {mn: {ws: np.empty(Yr[ws].shape) for ws in WSETS} for mn in M}
    choices = []
    nb = F.nested_settings(D.cfg)
    for te in F.nested_blocks(years, month, nb["first_year"], nb["block_len"], nb["start_month"]):
        tr = ~te
        icv = E.cv_run([Y[tr]], [kind], {k: x[tr] for k, x in X.items()}, years[tr], S)
        _, _, isc = E.select(icv)
        py, Ys = E.prep_y(Y[tr], years[tr], [kind] * q)
        rprep = {}
        for ws in WSETS:
            pr, _ = E.prep_y(Yr[ws][tr], years[tr], [kind] * Yr[ws].shape[1])
            rprep[ws] = pr
            obs[ws][te] = pr.standardize(Yr[ws][te], years[te])
        for mn, menu in M.items():
            ls, My, Mc = best_in(isc, menu)
            choices.append(dict(var=var, month=month, menu=mn, block=f"{int(years[te][0])}-{int(years[te][-1])}",
                                lagset=ls.split(" | ")[0], uses_dmi=" | RONI only" not in ls, My=My, Mc=Mc))
            pxx, Xs = E.prep_x(X[ls][tr], years[tr], S["detrend_predictors"])
            G, _ = E.cca_operator(Xs, Ys, My, Mc)
            phys = py.to_physical(pxx.standardize(X[ls][te], years[te]) @ G.T, years[te])
            for ws in WSETS:
                pred[mn][ws][te] = rprep[ws].standardize(aggs[ws](phys), years[te])
    print(f"  {var:7s} month {month:2d}: {time.time() - t0:5.1f} s", flush=True)
    return dict(var=var, month=month, years=years.astype(int), obs=obs, pred=pred, plain=plain,
                plain_cfg=plain_cfg, choices=choices)


def block_bootstrap(d: np.ndarray, base: np.ndarray, B: int, block: int, rng) -> tuple[float, float]:
    """90 % interval of 100 * mean(d) / mean(base) with moving blocks of years."""
    n = len(d)
    starts = np.arange(n - block + 1)
    k = int(np.ceil(n / block))
    out = np.empty(B)
    for b in range(B):
        idx = (rng.choice(starts, k)[:, None] + np.arange(block)).ravel()[:n]
        out[b] = 100 * d[idx].mean() / base[idx].mean()
    return tuple(np.quantile(out, [0.05, 0.95]))


def skill_tables(res: list, cfg: dict, B: int, seed: int):
    rng = np.random.default_rng(seed)
    region_rows, long = [], []
    for r in res:
        var, m = r["var"], r["month"]
        for ws in WSETS:
            regions, codes = D.regions(ws)
            o = r["obs"][ws]
            rho = {mn: E.col_spearman(r["pred"][mn][ws], o) for mn in MENUS}
            rho_p = {mn: E.col_spearman(r["plain"][mn][ws][1], r["plain"][mn][ws][0]) for mn in MENUS}
            for j, code in enumerate(codes):
                row = dict(weights=ws, var=var, month=m, quarter=QUARTER[m], code=code, region=regions[j],
                           n_years=len(r["years"]))
                for mn in MENUS:
                    row[f"rho_nested_{mn}"] = rho[mn][j]
                    row[f"mse_nested_{mn}"] = float(np.mean((r["pred"][mn][ws][:, j] - o[:, j]) ** 2))
                    row[f"rho_plain_{mn}"] = rho_p[mn][j]
                row["d_rho_nested"] = row["rho_nested_roni_dmi"] - row["rho_nested_roni"]
                region_rows.append(row)
            e2 = {mn: (r["pred"][mn][ws] - o) ** 2 for mn in MENUS}
            long.append(pd.DataFrame({
                "weights": ws, "var": var, "month": m, "quarter": QUARTER[m],
                "year": np.repeat(r["years"], len(codes)), "code": np.tile(codes, len(r["years"])),
                **{f"e2_{mn}": e2[mn].reshape(-1) for mn in MENUS}}))
    R = pd.DataFrame(region_rows)
    L = pd.concat(long, ignore_index=True)

    def summarise(keys):
        rows = []
        for k, g in R.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            row = dict(zip(keys, k))
            for mn in MENUS:
                row[f"rho_nested_{mn}"] = g[f"rho_nested_{mn}"].mean()
            row["d_rho_nested"] = row["rho_nested_roni_dmi"] - row["rho_nested_roni"]
            row["pct_region_months_better_with_dmi"] = 100 * (g["d_rho_nested"] > 0).mean()
            row["rho_plain_roni_dmi"] = g["rho_plain_roni_dmi"].mean()
            row["rho_plain_roni"] = g["rho_plain_roni"].mean()
            sel = np.ones(len(L), bool)
            for kk, vv in zip(keys, k):
                sel &= (L[kk] == vv).to_numpy()
            y = L[sel].groupby("year")[["e2_roni", "e2_roni_dmi", "e2_free"]].mean()
            d = (y["e2_roni"] - y["e2_roni_dmi"]).to_numpy()
            row["mse_reduction_pct"] = 100 * d.mean() / y["e2_roni"].mean()
            lo, hi = block_bootstrap(d, y["e2_roni"].to_numpy(), B, 5, rng)
            row["mse_reduction_p05"], row["mse_reduction_p95"] = lo, hi
            row["dmi_helps"] = "yes" if lo > 0 else ("worse" if hi < 0 else "no")
            df = (y["e2_roni"] - y["e2_free"]).to_numpy()
            row["mse_reduction_free_pct"] = 100 * df.mean() / y["e2_roni"].mean()
            rows.append(row)
        return pd.DataFrame(rows)

    by_vq = summarise(["weights", "var", "quarter"])
    by_v = summarise(["weights", "var"])
    by_v["quarter"] = "year"
    by_rq = summarise(["weights", "code", "quarter"])
    summary = pd.concat([by_vq, by_v], ignore_index=True).sort_values(["weights", "var", "quarter"])
    return R, summary, by_rq


# ------------------------------------------------------------------ 2. sign of the DMI effect
def regional_monthly(var: str, ws: str) -> pd.DataFrame:
    Fv = D.fields[var]
    y0, y1 = D.cfg["period"]["train"]
    Fv = Fv[(Fv.index.year >= y0) & (Fv.index.year <= y1)]
    _, codes = D.regions(ws)
    out = np.full((len(Fv), len(codes)), np.nan)
    for m in range(1, 13):
        i = np.where(Fv.index.month == m)[0]
        out[i] = D.aggregator(ws, var, m)(Fv.values[i])
    return pd.DataFrame(out, index=Fv.index, columns=codes)


def quarterly(df: pd.DataFrame, last: bool) -> pd.DataFrame:
    """Quarterly values (index (year, quarter)): the mean of the three months, or the last month's value."""
    g = df.groupby([df.index.year, df.index.quarter])
    q = g.last() if last else g.mean().where(g.count() == 3)
    q.index = q.index.set_names(["year", "q"])
    return q


def ols(y, X):
    """OLS with an intercept: coefficients, standard errors, residual degrees of freedom."""
    ok = np.isfinite(y) & np.isfinite(X).all(1)
    y, X = y[ok], np.column_stack([np.ones(ok.sum()), X[ok]])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    dof = len(y) - X.shape[1]
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (e @ e) / dof)
    return beta[1:], se[1:], dof


def national_weights(ws: str) -> np.ndarray:
    rs, kind = ws.split("_", 1)
    p = D.weights["pieces"][rs]
    _, codes = D.regions(ws)
    tot = p["pieces"].groupby("ridx")[kind].sum()
    code_of = dict(zip(range(len(p["regions"])), p["regions"]["code"]))
    w = pd.Series(tot.to_numpy(), index=[code_of[i] for i in tot.index]).reindex(codes).fillna(0).to_numpy()
    return w / w.sum()


def sign_tables(variables: list[str], models: dict, recent: int):
    y0, y1 = D.cfg["period"]["train"]
    P = D.P[(D.P.index.year >= y0 - 1) & (D.P.index.year <= y1)]
    Q = quarterly(P, last=False)
    Qprev = Q.shift(1)
    c0, c1 = D.cfg["period"]["clim"]
    t_star = D.cfg["period"]["t_star"]
    rows, mrows = [], []
    for ws in WSETS:
        regions, codes = D.regions(ws)
        wn = national_weights(ws)
        for v in variables:
            M = regional_monthly(v, ws)
            M["PH"] = M[codes].to_numpy() @ wn
            Y = quarterly(M, last=v in END_OF_QUARTER)
            clim = Y[(Y.index.get_level_values("year") >= c0) & (Y.index.get_level_values("year") <= c1)].groupby(level="q").mean()
            for qn in range(1, 5):
                yq = Y.xs(qn, level="q")
                xq = Q.xs(qn, level="q").reindex(yq.index)
                xp = Qprev.xs(qn, level="q").reindex(yq.index)
                for period, first in (("1950-2025", y0), (f"{recent}-2025", recent)):
                    keep = yq.index >= first
                    t = (yq.index[keep].to_numpy(float) - 2000.0)
                    sd = xq.loc[keep, ["roni", "dmi"]].std()
                    sdp = xp.loc[keep, "dmi"].std()
                    XA = np.column_stack([xq.loc[keep, "roni"], xq.loc[keep, "dmi"], t])
                    XB = np.column_stack([xq.loc[keep, "roni"], xp.loc[keep, "roni"], xp.loc[keep, "dmi"], t])
                    for code in list(codes) + ["PH"]:
                        if period != "1950-2025" and code != "PH":
                            continue
                        y = yq.loc[keep, code].to_numpy(float)
                        bA, sA, dA = ols(y, XA)
                        bB, sB, dB = ols(y, XB)
                        cl = float(clim.loc[qn, code])
                        row = dict(weights=ws, var=v, quarter=f"Q{qn}", months=QNAME[f"Q{qn}"], code=code,
                                   region="Philippines" if code == "PH" else regions[list(codes).index(code)],
                                   period=period, n_years=int(np.isfinite(y).sum()), sd_dmi=sd["dmi"], sd_roni=sd["roni"],
                                   dmi_per_sd=bA[1] * sd["dmi"], dmi_per_sd_lo=(bA[1] - 1.645 * sA[1]) * sd["dmi"],
                                   dmi_per_sd_hi=(bA[1] + 1.645 * sA[1]) * sd["dmi"],
                                   dmi_p=2 * stats.t.sf(abs(bA[1] / sA[1]), dA),
                                   roni_per_sd=bA[0] * sd["roni"], roni_p=2 * stats.t.sf(abs(bA[0] / sA[0]), dA),
                                   prevq_dmi_per_sd=bB[2] * sdp, prevq_dmi_p=2 * stats.t.sf(abs(bB[2] / sB[2]), dB),
                                   clim_mean=cl)
                        if v in ("P", "RO", "E"):
                            for k in ("dmi_per_sd", "dmi_per_sd_lo", "dmi_per_sd_hi", "roni_per_sd", "prevq_dmi_per_sd"):
                                row[f"{k}_pct"] = 100 * row[k] / cl
                        rows.append(row)
            # the Stage 1 models' own response to the DMI, RONI at 0, in today's climate
            agg_m = {}
            for m in range(1, 13):
                if (v, m) not in models:
                    continue
                mdl = models[(v, m)]
                names = mdl.x_names()
                dmi = np.array([nm.startswith("dmi") for nm in names])
                x0 = np.zeros(len(names))
                xp_ = np.where(dmi, mdl.prepx.s, 0.0)
                agg = D.aggregator(ws, v, m)
                r0 = agg(mdl.physical(x0, t_star))[0]
                r1 = agg(mdl.physical(xp_, t_star))[0]
                agg_m[m] = np.append(r1 - r0, (r1 - r0) @ wn)
            for qn in range(1, 5):
                ms = [m for m in range(3 * qn - 2, 3 * qn + 1) if m in agg_m]
                if not ms:
                    continue
                dq = agg_m[ms[-1]] if v in END_OF_QUARTER else np.mean([agg_m[m] for m in ms], axis=0)
                for j, code in enumerate(list(codes) + ["PH"]):
                    r = dict(weights=ws, var=v, quarter=f"Q{qn}", code=code, model_dmi_per_sd=dq[j])
                    if v in ("P", "RO", "E"):
                        cl = float(Y.xs(qn, level="q")[code].loc[c0:c1].mean())
                        r["model_dmi_per_sd_pct"] = 100 * dq[j] / cl
                    mrows.append(r)
    S = pd.DataFrame(rows)
    Mr = pd.DataFrame(mrows)
    S = S.merge(Mr, on=["weights", "var", "quarter", "code"], how="left")
    return S


# ------------------------------------------------------------------ 3. correlation
def nancorr(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def correlation_tables(recent: int):
    y0, y1 = D.cfg["period"]["train"]
    P = D.P[(D.P.index.year >= y0 - 1) & (D.P.index.year <= y1)].dropna()
    Q = quarterly(P, last=False).dropna()
    rows = []

    def corr_row(kind, label, a, b, extra=None):
        a, b = np.asarray(a, float), np.asarray(b, float)
        ok = np.isfinite(a) & np.isfinite(b)
        r = np.corrcoef(a[ok], b[ok])[0, 1]
        z, se = np.arctanh(r), 1 / np.sqrt(ok.sum() - 3)
        out = dict(kind=kind, season=label, n=int(ok.sum()), r=r, r_p05=np.tanh(z - 1.645 * se),
                   r_p95=np.tanh(z + 1.645 * se), vif=1 / (1 - r ** 2))
        out.update(extra or {})
        return out

    for period, first in (("1950-2025", y0), (f"{recent}-2025", recent)):
        Qp = Q[Q.index.get_level_values("year") >= first]
        prev = Q.shift(1).reindex(Qp.index)
        nxt = Q.shift(-1).reindex(Qp.index)
        for qn in range(1, 5):
            sel = Qp.index.get_level_values("q") == qn
            a, b = Qp.loc[sel, "roni"], Qp.loc[sel, "dmi"]
            extra = dict(sd_roni=a.std(), sd_dmi=b.std(),
                         r_dmi_with_prev_roni=nancorr(b, prev.loc[sel, "roni"]),
                         r_dmi_with_next_roni=nancorr(b, nxt.loc[sel, "roni"]),
                         persistence_roni=nancorr(a, prev.loc[sel, "roni"]),
                         persistence_dmi=nancorr(b, prev.loc[sel, "dmi"]))
            rows.append(dict(period=period, **corr_row("quarter", f"Q{qn} {QNAME[f'Q{qn}']}", a, b, extra)))
        Pm = P[P.index.year >= first]
        for m in range(1, 13):
            s = Pm[Pm.index.month == m]
            rows.append(dict(period=period, **corr_row("month", pd.Timestamp(2000, m, 1).strftime("%b"), s["roni"], s["dmi"],
                                                       dict(sd_roni=s["roni"].std(), sd_dmi=s["dmi"].std()))))
    Cr = pd.DataFrame(rows)
    # years that separate the two indices: |anomaly| of one large, the other small
    ev = []
    for qn in range(1, 5):
        s = Q.xs(qn, level="q")
        sd = s.std()
        for yr, x in s.iterrows():
            pos_iod, nino, nina, neg_iod = x["dmi"] >= sd["dmi"], x["roni"] >= 0.5, x["roni"] <= -0.5, x["dmi"] <= -sd["dmi"]
            if pos_iod and not nino:
                ev.append(dict(quarter=f"Q{qn}", year=yr, kind="positive IOD without El Nino", roni=x["roni"], dmi=x["dmi"]))
            elif nino and x["dmi"] <= 0.25 * sd["dmi"]:
                ev.append(dict(quarter=f"Q{qn}", year=yr, kind="El Nino without positive IOD", roni=x["roni"], dmi=x["dmi"]))
            elif neg_iod and not nina:
                ev.append(dict(quarter=f"Q{qn}", year=yr, kind="negative IOD without La Nina", roni=x["roni"], dmi=x["dmi"]))
    return Cr, pd.DataFrame(ev)


# ------------------------------------------------------------------ main
def main():
    global D
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--vars", nargs="*")
    ap.add_argument("--months", nargs="*", type=int)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count()))
    ap.add_argument("--recent", type=int, default=1990, help="first year of the recent window (default 1990)")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--skip-skill", action="store_true", help="only parts 2 and 3 (seconds)")
    a = ap.parse_args()
    cfg = C.load(a.config)
    cfg["model"]["predictors"] = ["roni", "dmi"]      # the analysis builds both menus itself, whatever the main run uses
    D, variables, extra = F.load_data(cfg, refresh_indices=False, with_hourly=True)
    print(f"indices: RONI to {extra['index_info']['roni_last']}, DMI to {extra['index_info']['dmi_raw_last']}")
    variables = [v for v in (a.vars or variables) if v in variables]
    months = a.months or list(range(1, 13))
    out = C.out(cfg, "analysis", "dmi", "x").parent
    out.mkdir(parents=True, exist_ok=True)
    lines = []

    # 3. correlation
    Cr, ev = correlation_tables(a.recent)
    Cr.to_csv(out / "correlation_roni_dmi.csv", index=False)
    ev.to_csv(out / "years_that_separate_roni_and_dmi.csv", index=False)
    q = Cr[Cr["kind"] == "quarter"].pivot(index="season", columns="period", values="r")
    lines.append("3. Correlation of RONI and DMI (quarterly means)\n" + q.round(2).to_string())

    # 2. sign
    mcfg = C.load(a.config, "roni_dmi") if "roni_dmi" in (cfg.get("variants") or {}) else cfg
    models = C.load_pickle(C.work(mcfg, "models.pkl"), "scripts/03_fit_stage1.py --variant roni_dmi")
    C.check_models(mcfg, models)
    S = sign_tables(variables, models, a.recent)
    S.to_csv(out / "dmi_effect_holding_roni.csv", index=False)
    ph = S[(S["code"] == "PH") & (S["period"] == "1950-2025") & (S["weights"] == WSETS[0])]
    show = ph.assign(sig=np.where(ph["dmi_p"] < 0.1, "*", "")).set_index(["var", "quarter"])
    cols = [c for c in ("dmi_per_sd", "dmi_per_sd_pct", "dmi_p", "roni_per_sd", "prevq_dmi_per_sd", "prevq_dmi_p",
                        "model_dmi_per_sd") if c in show]
    lines.append(f"2. DMI effect holding RONI, national ({WSETS[0]}), per +1 SD of DMI, 1950-2025\n"
                 + show[cols].round(3).to_string())

    # 1. skill
    if not a.skip_skill:
        tasks = [(v, m) for v in variables for m in months]
        print(f"{len(tasks)} variable-months, 3 menus, {a.workers} workers")
        t0 = time.time()
        if a.workers > 1:
            with mp.get_context("fork").Pool(a.workers) as pool:
                res = pool.map(run_one, tasks, chunksize=1)
        else:
            res = [run_one(t) for t in tasks]
        R, SUM, RQ = skill_tables(res, cfg, a.boot, cfg["model"].get("seed", 42))
        R.to_csv(out / "skill_regions.csv", index=False)
        SUM.to_csv(out / "skill_summary.csv", index=False)
        RQ.to_csv(out / "skill_by_region_quarter.csv", index=False)
        ch = pd.DataFrame([c for r in res for c in r["choices"]])
        ch.to_csv(out / "nested_choices.csv", index=False)
        pc = pd.DataFrame([dict(var=r["var"], month=r["month"], menu=mn, lagset=g[0], My=g[1], Mc=g[2])
                           for r in res for mn, g in r["plain_cfg"].items()])
        pc.to_csv(out / "plain_choices.csv", index=False)
        print(f"skill part in {(time.time() - t0) / 60:.1f} min")
    elif (out / "skill_summary.csv").exists():
        SUM, ch = pd.read_csv(out / "skill_summary.csv"), pd.read_csv(out / "nested_choices.csv")
    else:
        SUM = None
    if SUM is not None:
        s = SUM[(SUM["weights"] == WSETS[0])]
        lines.append(f"1. MSE reduction from adding the DMI (%, nested CV, {WSETS[0]}; > 0 = DMI helps; "
                     "[+] / [-] = 90 % interval above / below 0)\n"
                     + (s.assign(cell=s["mse_reduction_pct"].map("{:+.1f}".format)
                                 + s["dmi_helps"].map({"yes": " [+]", "worse": " [-]", "no": ""}))
                        .pivot(index="var", columns="quarter", values="cell").to_string()))
        r = s[s["quarter"] == "year"].set_index("var")[["rho_nested_roni", "rho_nested_roni_dmi", "rho_nested_free"]]
        lines.append("   mean nested Spearman rho over regions and months\n" + r.round(3).to_string())
        f = ch[ch["menu"] == "free"]
        lines.append(f"   free menu: the DMI is kept in {100 * f['uses_dmi'].mean():.0f} % of the outer folds")
    txt = "\n\n".join(lines)
    (out / "summary.txt").write_text(txt + "\n")
    print("\n" + txt + f"\n\nwrote {out}")


if __name__ == "__main__":
    main()
