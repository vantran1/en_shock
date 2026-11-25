"""Stage 2 (weather -> production), methodology v5 Section 3.4: the hinge regression of
Eq. (11) against gradient boosting, compared out of sample. PROVISIONAL.

What it does
1. Panel: production by region and quarter (estimation.data.build, as the direct approach;
   1987Q1-2025Q4, 16 regions) for irrigated palay, rainfed palay and corn, with the window
   features of data/processed/stage2_features.csv (scripts/build_stage2_features.py).
2. Models (all Poisson pseudo-ML on production in levels, with region x quarter-of-year
   effects, smooth regional trends, the exposure controls of the direct approach and, for
   corn, the Region VI measurement-break dummy):
   - base:            no weather (the reference for out-of-sample skill)
   - linear:          window means of T, VPD, P, SM_RZ, linear (Eq. 11 with delta = 0)
   - hinge:           the same with a hinge on each (Eq. 11; thresholds chosen by fit on the
                      5th, 10th, ..., 95th percentiles of the training sample)
   - hinge_sm_t:      parsimonious: hinges on T and SM_RZ only (the four means are strongly
                      correlated, so their separate effects are poorly identified)
   - hinge_extremes:  linear means plus hinges on the hottest month (T_max) and the driest
                      root-zone soil moisture (SM_RZ_min)
   Daily variables (v5 Table 2, from hourly ERA5; Van, 25 Nov 2026):
   - hinge_sm_tmax:   hinges on the mean daily maximum temperature (TMAX) and SM_RZ
   - hinge_sm_edd30:  hinges on extreme degree-days above 30 degC (EDD30) and SM_RZ
   - hinge_ldry_tmax: hinges on the longest dry spell (LDRY) and TMAX
   - gbm4:            gradient boosting on the four monthly window means
   - gbm_all:         gradient boosting on the 16 monthly features (11 window means + 5 extremes)
   - gbm_daily:       gradient boosting on all 30 features (monthly and daily)
   Today's response (the weather effects changed from 2000, item 4):
   - hinge_sm_t_post2000: hinge_sm_t with every weather term shifting from 2000 (thresholds
                      common); the shock uses the post-2000 response
   - gbm_daily_post2000:  gbm_daily with a post-2000 indicator as a feature, so the trees can
                      let the response differ after 2000; the shock sets it to 1
   Boosting: monotonic constraints and backfitting with the non-weather terms
   (estimation.stage2.fit_gbm).
3. Out-of-sample comparison (v5: "the model that predicts better on years left out of the
   estimation is kept"): two sets of folds, each re-estimating everything (thresholds,
   trends with knots on the training years, boosting) without the held-out quarters:
   - 5-year blocks (1987-1991, ..., 2022-2025);
   - the three strong El Nino episodes (1997Q2-1998Q4, 2015Q2-2016Q4, 2023Q2-2024Q4).
   Skill = 1 - deviance(model) / deviance(base) on the held-out quarters (positive: the
   weather improves the prediction). For the episodes, the national production anomaly
   observed (actual / base - 1) is compared with the predicted one (model / base - 1).
4. Full sample: coefficients of the linear and hinge models with Driscoll-Kraay standard
   errors (conditional on the thresholds), and the 2000-break test: do the weather effects
   of the parsimonious hinge model (hinge_sm_t) change from 2000 (as the direct rice effect does)? Wald test (DK) on
   the post-2000 shifts, thresholds held at their full-sample values.
5. Response curves: production relative to the median weather as one feature moves over
   its observed range (hinge: exact; boosting: partial dependence, other features as
   observed).

Diagnostics, not the deliverable: the shocks come from chaining these models with Van's
Stage-1 simulations (next step). VR and PF not included yet.

Run:  python scripts/estimate_stage2.py [--workers 8]
Writes outputs/tables/stage2_{cv_skill,cv_episodes,coefficients,break2000,response}.csv,
outputs/stage2_comparison.md, outputs/figures/stage2_{episodes,response}.png
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import argparse  # noqa: E402
import sys  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from estimation.data import CONTROLS, GROUP, build, sample  # noqa: E402
from estimation.panel import fit as dk_fit  # noqa: E402
from estimation.setup import break_dummies  # noqa: E402
from estimation.stage2 import (FEATURES, FEATURES_MONTHLY, Stage2Spec, fit_base,  # noqa: E402
                               fit_gbm, fit_hinge, poisson_deviance, predict_gbm, predict_hinge)
from validate_strict import rcs  # noqa: E402

PROC, TAB, FIG, OUT = (ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures",
                       ROOT / "outputs")
SERIES = ["irrigated", "rainfed", "corn"]
MAIN4 = ("T", "VPD", "P", "SM_RZ")
SPECS = {"linear": Stage2Spec("linear", linear=MAIN4),
         "hinge": Stage2Spec("hinge", hinge=MAIN4),
         "hinge_sm_t": Stage2Spec("hinge_sm_t", hinge=("T", "SM_RZ")),
         "hinge_extremes": Stage2Spec("hinge_extremes", linear=MAIN4, hinge=("T_max", "SM_RZ_min")),
         "hinge_sm_tmax": Stage2Spec("hinge_sm_tmax", hinge=("TMAX", "SM_RZ")),
         "hinge_sm_edd30": Stage2Spec("hinge_sm_edd30", hinge=("EDD30", "SM_RZ")),
         "hinge_ldry_tmax": Stage2Spec("hinge_ldry_tmax", hinge=("LDRY", "TMAX")),
         "hinge_sm_t_post2000": Stage2Spec("hinge_sm_t_post2000", hinge=("T", "SM_RZ"), post=2000)}
BREAK_MODEL = "hinge_sm_t"  # the regression whose effects are tested for a change from 2000
GBMS = {"gbm4": list(MAIN4), "gbm_all": FEATURES_MONTHLY, "gbm_daily": FEATURES,
        "gbm_daily_post2000": FEATURES + ["post2000"]}
RESPONSE_FEATURES = list(MAIN4) + ["TMAX", "EDD30", "LDRY"]
FIG_MODELS = ["hinge_sm_t", "hinge_sm_t_post2000", "hinge_sm_edd30", "gbm_all", "gbm_daily",
              "gbm_daily_post2000"]
MODELS = ["base"] + list(SPECS) + list(GBMS)
BLOCKS = {f"{a}-{min(a + 4, 2025)}": (f"{a}Q1", f"{min(a + 4, 2025)}Q4") for a in range(1987, 2026, 5)}
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"),
            "2023-24": ("2023Q2", "2024Q4")}
STATUS = "provisional; diagnostic (stage 2 model choice), monthly and daily weather"
BLUE, ORANGE, NAVY, GREEN, INK, MUTED, GRID = ("#2a78d6", "#eb6834", "#0d366b", "#3a9a5b",
                                              "#0b0b0b", "#52514e", "#d9d8d4")
COLOR = {"linear": MUTED, "hinge": BLUE, "hinge_sm_t": "#8a5cc2", "hinge_extremes": NAVY, "gbm4": ORANGE,
         "gbm_all": GREEN, "hinge_sm_tmax": "#c2185b", "hinge_sm_edd30": BLUE,
         "hinge_ldry_tmax": "#7a6a00", "hinge_sm_t_post2000": NAVY, "gbm_daily": ORANGE,
         "gbm_daily_post2000": "#b34700"}


def panel(series: str):
    """Estimation sample (PPML) with the features; y in PPML units."""
    p = build(series)
    f = pd.read_csv(PROC / "stage2_features.csv")
    f = f[f.series == series].drop(columns="series")
    p = p.merge(f, on=["region_code", "period"], how="left", validate="1:1")
    assert not p[FEATURES].isna().any().any()
    d, y = sample(p, "ppml", GROUP[series])
    d["post2000"] = (d.period.str[:4].astype(int) >= 2000).astype(float)
    return d, y.to_numpy(float)


def base_design(d: pd.DataFrame, train: np.ndarray, series: str) -> pd.DataFrame:
    """Region x quarter effects, regional restricted cubic spline trends with knots on the
    training rows, controls, the corn break dummy."""
    fe = pd.get_dummies(d.region_code + "_q" + d.q.astype(str), prefix="fe", dtype=float)
    reg = pd.get_dummies(d.region_code, dtype=float)
    t = d.t.to_numpy(float)
    B = rcs(t, np.quantile(t[train], [0.05, 0.35, 0.65, 0.95]))
    tr = pd.concat([reg.mul(B[:, j], axis=0).add_prefix(f"tr{j}_") for j in range(B.shape[1])], axis=1)
    parts = [fe, tr, d[CONTROLS]]
    if GROUP[series] == "corn":
        parts.append(break_dummies(d, "corn"))
    return pd.concat(parts, axis=1)


def held_mask(d, a, z):
    per = pd.PeriodIndex(d.period, freq="Q")
    return np.asarray((per >= pd.Period(a, "Q")) & (per <= pd.Period(z, "Q")))


def predict(model, d, y, base, train):
    """Fit `model` on the training rows; predictions for all rows."""
    if model == "base":
        p = fit_base(y, base, train)
        return np.exp(base[p.index].to_numpy(float) @ p.to_numpy()), {}
    if model in SPECS:
        r = fit_hinge(d, y, base, SPECS[model], train)
        return predict_hinge(r, d, base, SPECS[model]), r["thresholds"]
    r = fit_gbm(d, y, base, GBMS[model], train)
    return predict_gbm(r, d, base), {}


def run_fold(job):
    series, kind, fold, a, z = job
    d, y = panel(series)
    held = held_mask(d, a, z)
    train = ~held
    base = base_design(d, train, series)
    preds, thr = {}, {}
    for model in MODELS:
        preds[model], thr[model] = predict(model, d, y, base, train)
    skill = [{"series": series, "fold_type": kind, "fold": fold, "model": mdl, "n_held": int(held.sum()),
              "deviance": poisson_deviance(y[held], preds[mdl][held]),
              "thresholds": "; ".join(f"{k}={v:.3g}" for k, v in thr[mdl].items())} for mdl in MODELS]
    ep = []
    if kind == "episode":
        h = d.loc[held, ["period"]].assign(actual=y[held], **{m_: preds[m_][held] for m_ in MODELS})
        g = h.groupby("period").sum().reset_index()
        ep = g.assign(series=series, episode=fold).to_dict("records")
    print(f"{series:9s} {kind:7s} {fold}: done", flush=True)
    return skill, ep


def full_sample(series):
    """Coefficients (DK), break test, response curves."""
    d, y = panel(series)
    train = np.ones(len(d), bool)
    base = base_design(d, train, series)
    yser = pd.Series(y)
    coef, brk, resp = [], [], []
    fits = {}
    for name, spec in SPECS.items():
        r = fit_hinge(d, y, base, spec, train)
        res = dk_fit(yser, r["X"], d.period, "ppml")
        se = pd.Series(res["se"], index=r["X"].columns)
        for c in r["X"].columns:
            if c[:2] in ("W_", "H_"):
                v = c[2:]
                coef.append({"series": series, "model": name, "term": c, "est": res["params"][c],
                             "se": se[c], "threshold": r["thresholds"].get(v, np.nan) if c[0] == "H" else np.nan,
                             "on_grid_edge": r["on_grid_edge"].get(v, False) if c[0] == "H" else False})
        fits[name] = r
        if name == BREAK_MODEL:
            spec_p = Stage2Spec(f"{name}_post2000", hinge=spec.hinge, post=2000, thresholds=r["thresholds"])
            rp = fit_hinge(d, y, base, spec_p, train)
            resp_ = dk_fit(yser, rp["X"], d.period, "ppml")
            cols = [c for c in rp["X"].columns if c.startswith("P_")]
            b = resp_["params"][cols].to_numpy()
            V = resp_["cov"].loc[cols, cols].to_numpy()
            wald = float(b @ np.linalg.pinv(V) @ b)
            brk.append({"series": series, "test": "weather effects (linear + hinge) shift from 2000",
                        "wald": wald, "df": len(cols), "p_value": float(stats.chi2.sf(wald, len(cols))),
                        "deviance_no_break": r["deviance"], "deviance_break": rp["deviance"]})
            sep = pd.Series(resp_["se"], index=rp["X"].columns)
            for c in cols:
                coef.append({"series": series, "model": f"{name}_post2000", "term": c,
                             "est": resp_["params"][c], "se": sep[c], "threshold": np.nan,
                             "on_grid_edge": False})
    gb = {name: fit_gbm(d, y, base, feats, train) for name, feats in GBMS.items()}
    # response curves, 5th-95th percentile of each feature; post-2000 models at today's response
    def today(dd):
        dd["post2000"] = 1.0
        dd["period"] = "2020Q1"
        return dd

    for v in RESPONSE_FEATURES:
        grid = np.quantile(d[v], np.linspace(0.05, 0.95, 19))
        med = float(np.median(d[v]))
        for name in ("linear", "hinge", "hinge_sm_t", "hinge_sm_t_post2000", "hinge_sm_tmax",
                     "hinge_sm_edd30", "hinge_ldry_tmax"):
            r, spec = fits[name], SPECS[name]
            if v not in spec.linear + spec.hinge:
                continue
            dd = today(d.copy())
            dd[v] = med
            ref = predict_hinge(r, dd, base, spec, weather_only=True)
            for gv in grid:
                dd[v] = gv
                resp.append({"series": series, "model": name, "feature": v, "value": gv,
                             "rel": float(np.mean(predict_hinge(r, dd, base, spec, weather_only=True) / ref))})
        for name, r in gb.items():
            if v not in r["features"]:
                continue
            dd = today(d.copy())
            dd[v] = med
            ref = predict_gbm(r, dd, base, weather_only=True).mean()
            for gv in grid:
                dd[v] = gv
                resp.append({"series": series, "model": name, "feature": v, "value": gv,
                             "rel": float(predict_gbm(r, dd, base, weather_only=True).mean() / ref)})
    print(f"{series}: full sample done", flush=True)
    return coef, brk, resp


def md(df, fmt="{:.3f}"):
    def cell(v):
        return fmt.format(v) if isinstance(v, (float, np.floating)) and not pd.isna(v) else str(v)
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main(workers=8):
    jobs = ([(s, "block", k, a, z) for s in SERIES for k, (a, z) in BLOCKS.items()]
            + [(s, "episode", k, a, z) for s in SERIES for k, (a, z) in EPISODES.items()])
    with ProcessPoolExecutor(workers) as ex:
        folds = list(ex.map(run_fold, jobs))
        full = list(ex.map(full_sample, SERIES))
    skill = pd.DataFrame([r for f in folds for r in f[0]])
    ep = pd.DataFrame([r for f in folds for r in f[1]])
    coef = pd.DataFrame([r for f in full for r in f[0]])
    brk = pd.DataFrame([r for f in full for r in f[1]])
    resp = pd.DataFrame([r for f in full for r in f[2]])
    for df, name in ((skill, "cv_skill"), (ep, "cv_episodes"), (coef, "coefficients"),
                     (brk, "break2000"), (resp, "response")):
        df.assign(status=STATUS).round(5).to_csv(TAB / f"stage2_{name}.csv", index=False)

    # summaries
    sk = skill.pivot_table(index=["series", "fold_type", "model"], values="deviance", aggfunc="sum").reset_index()
    b = sk[sk.model == "base"].set_index(["series", "fold_type"]).deviance
    sk["skill_pct"] = (1 - sk.deviance / sk.set_index(["series", "fold_type"]).index.map(b)) * 100
    skill_tab = sk[sk.model != "base"].pivot_table(index=["series", "model"], columns="fold_type",
                                                   values="skill_pct").reset_index()
    by_fold = skill.copy()
    bf = by_fold[by_fold.model == "base"].set_index(["series", "fold"]).deviance
    by_fold["skill_pct"] = (1 - by_fold.deviance / by_fold.set_index(["series", "fold"]).index.map(bf)) * 100
    wins = (by_fold[by_fold.model != "base"].loc[lambda x: x.groupby(["series", "fold"]).skill_pct.idxmax()]
            .groupby(["series", "model"]).size().rename("folds_best").reset_index())
    e = ep.groupby(["series", "episode"])[["actual"] + MODELS].sum()
    etab = pd.DataFrame({"observed_%": (e.actual / e.base - 1) * 100,
                         **{f"{m_}_%": (e[m_] / e.base - 1) * 100 for m_ in MODELS[1:]}}).reset_index()

    s = ["# Stage 2: hinge regression vs gradient boosting (PROVISIONAL)\n",
         "Diagnostic for the choice of the stage 2 model (methodology v5 Section 3.4). Monthly weather "
         "only (Van's `_obs`, 349 cells, cropland weights), window means over the crop calendars. "
         "Poisson pseudo-ML, region x quarter effects, regional spline trends, exposure controls.\n",
         "## Out-of-sample skill (% of the base model's deviance removed; held-out quarters, all folds)\n",
         md(skill_tab, "{:.1f}"), "\n## Folds in which each model predicts best\n", md(wins),
         "\n## Episodes held out: national production anomaly against the base model (%), whole window\n",
         md(etab, "{:.1f}"), "\n## Thresholds and coefficients, full sample (DK s.e.)\n",
         md(coef.assign(t=coef.est / coef.se)[["series", "model", "term", "est", "se", "t", "threshold"]], "{:.3f}"),
         f"\n## Do the weather effects change from 2000? ({BREAK_MODEL}, Wald test, DK)\n", md(brk, "{:.3f}")]
    (OUT / "stage2_comparison.md").write_text("\n".join(s) + "\n")
    print("\n".join(s))
    figures(ep, resp)


def figures(ep, resp):
    # episodes: national quarterly anomaly vs base, observed and predicted
    fig, axes = plt.subplots(len(SERIES), len(EPISODES), figsize=(13, 9), constrained_layout=True,
                             sharey="row")
    for i, s_ in enumerate(SERIES):
        for j, k in enumerate(EPISODES):
            ax = axes[i, j]
            e = ep[(ep.series == s_) & (ep.episode == k)].sort_values("period")
            x = np.arange(len(e))
            ax.axhline(0, color=MUTED, lw=0.8)
            ax.plot(x, (e.actual / e.base - 1) * 100, color=INK, lw=2, marker="o", ms=3, label="observed")
            for m_ in FIG_MODELS:
                ax.plot(x, (e[m_] / e.base - 1) * 100, color=COLOR[m_], lw=1.2, label=m_)
            ax.set_xticks(x, e.period.str[2:], fontsize=7, rotation=45)
            ax.tick_params(labelsize=7, colors=MUTED)
            ax.grid(axis="y", color=GRID, lw=0.5)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            if i == 0:
                ax.set_title(f"{k} held out", fontsize=9, color=INK, loc="left")
            if j == 0:
                ax.set_ylabel(f"{s_}: % vs model without weather", fontsize=8, color=MUTED)
    axes[0, 0].legend(frameon=False, fontsize=7)
    fig.suptitle("PROVISIONAL. Stage 2 out of sample: national production in each episode, observed and "
                 "predicted from observed weather", fontsize=10, color=INK, x=0.01, ha="left")
    fig.savefig(FIG / "stage2_episodes.png", dpi=150, facecolor="white")
    plt.close(fig)
    # response curves
    feats = list(dict.fromkeys(resp.feature))
    fig, axes = plt.subplots(len(SERIES), len(feats), figsize=(18, 8.5), constrained_layout=True,
                             sharey="row")
    unit = {"T": "°C", "VPD": "kPa", "P": "mm/month", "SM_RZ": "m³/m³", "TMAX": "°C",
            "EDD30": "°C·day/month", "LDRY": "days"}
    for i, s_ in enumerate(SERIES):
        for j, v in enumerate(feats):
            ax = axes[i, j]
            for m_ in ("hinge_sm_t", "hinge_sm_t_post2000", "hinge_sm_tmax", "hinge_sm_edd30",
                       "hinge_ldry_tmax", "gbm_all", "gbm_daily", "gbm_daily_post2000"):
                r = resp[(resp.series == s_) & (resp.feature == v) & (resp.model == m_)]
                ax.plot(r.value, (r.rel - 1) * 100, color=COLOR[m_], lw=1.4, label=m_)
            ax.axhline(0, color=MUTED, lw=0.8)
            ax.tick_params(labelsize=7, colors=MUTED)
            ax.grid(color=GRID, lw=0.5)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            if i == len(SERIES) - 1:
                ax.set_xlabel(f"window mean {v} ({unit[v]})", fontsize=8, color=MUTED)
            if j == 0:
                ax.set_ylabel(f"{s_}: % vs median weather", fontsize=8, color=MUTED)
    handles = {}
    for ax in axes.ravel():
        for h, lab in zip(*ax.get_legend_handles_labels()):
            handles.setdefault(lab, h)
    fig.legend(handles.values(), handles.keys(), loc="lower center", ncol=len(handles), frameon=False,
               fontsize=8, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("PROVISIONAL. Stage 2 response of production to each window-mean weather variable "
                 "(5th–95th percentile of the data), full sample; post-2000 models at today's response",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.savefig(FIG / "stage2_response.png", dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    main(ap.parse_args().workers)
