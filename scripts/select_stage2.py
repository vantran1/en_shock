"""Stage 2 model choice by nested cross-validation (methodology v5 Section 3.4: "the model that
predicts better on years left out of the estimation is kept"). PROVISIONAL; a diagnostic.

Why nested: scripts/estimate_stage2.py compares 12 models on the same held-out folds that are then
used to pick the best one, so the winner's score is optimistic, and some candidates (the post-2000
versions) were added after looking at full-sample results. Here the candidate list is fixed in
advance and the choice itself is made inside each fold, on the training years only, so the
held-out score measures the whole procedure (choice + estimation).

Candidates (fixed, 25 Nov 2026): 3 models x 4 options for the change in the weather response
(from 2000, 2005, 2010, or none; as the break year of the strict validation of the direct
approach, scripts/validate_strict.py):
- reg:          hinge regression on window-mean temperature and root-zone soil moisture (v5 Eq. 11),
                every weather term shifting from the break year;
- gbm_compact:  gradient boosting on 9 features chosen in advance, one per mechanism: mean, daily
                maximum and night-time temperature (T, TMAX, TMIN), heat above 30 degC (EDD30),
                root-zone soil moisture, mean and driest month (SM_RZ, SM_RZ_min), rainfall (P),
                longest dry spell (LDRY), runoff as a proxy for irrigation water (RO);
- gbm_full:     gradient boosting on all 30 features.
Boosting gets an indicator for the years from the break as an extra feature.

Procedure, for each series (irrigated, rainfed, corn) and each outer fold (eight 5-year blocks;
the three episodes 1997Q2-1998Q4, 2015Q2-2016Q4, 2023Q2-2024Q4):
1. inner cross-validation on the training years: leave out each 5-year block in turn (its
   training quarters), fit every candidate on the rest (thresholds and trends re-chosen), sum the
   Poisson deviance on the left-out quarters;
2. choose the candidate with the lowest inner deviance, refit it on all training years, predict
   the held-out quarters. Nested skill = 1 - deviance(chosen) / deviance(no weather).
Every candidate's own outer score is kept too (as in estimate_stage2.py, for reference).
Final choice for the chain: step 1 on all years (inner folds = the eight blocks).

Grouped importance (boosting, break 2000, outer folds): the rise in held-out deviance when the
features of one mechanism are shuffled together across the held-out rows (5 repeats). Large =
the model relies on it out of sample.

Run:  python scripts/select_stage2.py [--workers 8]   (about an hour; run detached)
Writes outputs/tables/stage2_nested_{folds,configs,final,importance}.csv, outputs/stage2_nested.md
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from estimate_stage2 import BLOCKS, EPISODES, SERIES, base_design, held_mask, md, panel  # noqa: E402
from estimation.stage2 import (FEATURES, Stage2Spec, fit_base, fit_gbm, fit_hinge,  # noqa: E402
                               poisson_deviance, predict_gbm, predict_hinge)

TAB, OUT = ROOT / "outputs/tables", ROOT / "outputs"
COMPACT = ["T", "TMAX", "TMIN", "EDD30", "SM_RZ", "SM_RZ_min", "P", "LDRY", "RO"]
BREAKS = [2000, 2005, 2010, None]
MODELS = ["reg", "gbm_compact", "gbm_full"]
CONFIGS = [(m, b) for m in MODELS for b in BREAKS]
GROUPS = {  # mechanism -> features (all 30 features belong to one group)
    "heat": ["T", "TMAX", "T_max", "TMAX_max", "EDD30", "EDD32", "EDD", "NHOT30", "NHOT32", "NHOT", "PET"],
    "night heat": ["TMIN"],
    "air dryness (VPD)": ["VPD", "VPDMAX", "VPD_max"],
    "rainfall": ["P", "P_min", "NDRY", "N50"],
    "dry spells": ["LDRY", "LDRY_max"],
    "soil water": ["SM_RZ", "SM_DEEP", "SM_RZ_min", "SPEI3", "SPEI3_min", "CWB3", "E"],
    "runoff (irrigation water)": ["RO"],
    "radiation": ["RS"],
}
assert sorted(sum(GROUPS.values(), [])) == sorted(FEATURES)
REPEATS = 5
STATUS = "provisional; diagnostic (nested choice of the stage 2 model)"


def name(cfg):
    m, b = cfg
    return f"{m}, {'no change' if b is None else f'from {b}'}"


def with_post(d):
    for b in BREAKS:
        if b is not None:
            d[f"post{b}"] = (d.period.str[:4].astype(int) >= b).astype(float)
    return d


def fit_config(cfg, d, y, train, series):
    """Fit on the training rows; returns (predict function on any rows, fit object)."""
    m, b = cfg
    base = base_design(d, train, series)
    if m == "reg":
        spec = Stage2Spec(f"reg_{b}", hinge=("T", "SM_RZ"), post=b)
        r = fit_hinge(d, y, base, spec, train)
        return (lambda dd: predict_hinge(r, dd, base.loc[dd.index], spec)), r
    feats = (COMPACT if m == "gbm_compact" else FEATURES) + ([f"post{b}"] if b is not None else [])
    r = fit_gbm(d, y, base, feats, train)
    return (lambda dd: predict_gbm(r, dd, base.loc[dd.index])), r


def base_predict(d, y, train, series):
    base = base_design(d, train, series)
    p = fit_base(y, base, train)
    return np.exp(base[p.index].to_numpy(float) @ p.to_numpy())


def inner_choice(d, y, train, series):
    """Inner CV on the training rows: deviance of every config summed over the 5-year blocks."""
    dev = {cfg: 0.0 for cfg in CONFIGS}
    for a, z in BLOCKS.values():
        inner_held = held_mask(d, a, z) & train
        if inner_held.sum() == 0:
            continue
        inner_train = train & ~inner_held
        for cfg in CONFIGS:
            pred, _ = fit_config(cfg, d, y, inner_train, series)
            dev[cfg] += poisson_deviance(y[inner_held], pred(d.loc[inner_held]))
    best = min(dev, key=dev.get)
    return best, dev


def importance(fit_obj, d, y, held, base_pred_fn, rng):
    """Rise in held-out deviance when a group of features is shuffled across the held-out rows."""
    dh = d.loc[held].copy()
    ref = poisson_deviance(y[held], base_pred_fn(dh))
    out = {}
    for g, feats in GROUPS.items():
        feats = [f for f in feats if f in fit_obj["features"]]
        if not feats:
            continue
        rises = []
        for _ in range(REPEATS):
            dp = dh.copy()
            perm = rng.permutation(len(dp))
            dp[feats] = dp[feats].to_numpy()[perm]
            rises.append(poisson_deviance(y[held], base_pred_fn(dp)) - ref)
        out[g] = float(np.mean(rises)) / ref * 100
    return out


def run(job):
    series, kind, fold, a, z = job
    d, y = panel(series)
    d = with_post(d)
    rng = np.random.default_rng(0)
    if kind == "final":
        best, dev = inner_choice(d, y, np.ones(len(d), bool), series)
        print(f"{series} final: {name(best)}", flush=True)
        return {"final": [{"series": series, "config": name(c), "inner_deviance": v, "chosen": c == best}
                          for c, v in dev.items()]}
    held = held_mask(d, a, z)
    train = ~held
    best, dev = inner_choice(d, y, train, series)
    mu0 = base_predict(d, y, train, series)
    rows, imp, ep = [], [], []
    for cfg in CONFIGS:
        pred, r = fit_config(cfg, d, y, train, series)
        mu = pred(d.loc[held])
        rows.append({"series": series, "fold_type": kind, "fold": fold, "config": name(cfg),
                     "model": cfg[0], "break": cfg[1] or "none", "chosen": cfg == best,
                     "inner_deviance": dev[cfg], "outer_deviance": poisson_deviance(y[held], mu),
                     "base_deviance": poisson_deviance(y[held], mu0[held])})
        if cfg == best and kind == "episode":
            g = (d.loc[held, ["period"]].assign(actual=y[held], base=mu0[held], chosen=mu)
                 .groupby("period").sum().reset_index())
            ep = g.assign(series=series, episode=fold, config=name(cfg)).to_dict("records")
        if cfg[0] != "reg" and cfg[1] == 2000:
            for grp, v in importance(r, d, y, held, pred, rng).items():
                imp.append({"series": series, "fold_type": kind, "fold": fold, "model": cfg[0],
                            "group": grp, "deviance_rise_pct": v})
    print(f"{series:9s} {kind:7s} {fold}: chose {name(best)}", flush=True)
    return {"rows": rows, "imp": imp, "ep": ep}


def main(workers=8):
    jobs = ([(s, "block", k, a, z) for s in SERIES for k, (a, z) in BLOCKS.items()]
            + [(s, "episode", k, a, z) for s in SERIES for k, (a, z) in EPISODES.items()]
            + [(s, "final", "all", None, None) for s in SERIES])
    with ProcessPoolExecutor(workers) as ex:
        res = list(ex.map(run, jobs))
    rows = pd.DataFrame([r for x in res for r in x.get("rows", [])])
    imp = pd.DataFrame([r for x in res for r in x.get("imp", [])])
    ep = pd.DataFrame([r for x in res for r in x.get("ep", [])])
    final = pd.DataFrame([r for x in res for r in x.get("final", [])])
    for df, nm in ((rows, "configs"), (imp, "importance"), (final, "final"), (ep, "episodes")):
        df.assign(status=STATUS).round(5).to_csv(TAB / f"stage2_nested_{nm}.csv", index=False)

    ch = rows[rows.chosen]
    folds = ch[["series", "fold_type", "fold", "config"]]
    folds.to_csv(TAB / "stage2_nested_folds.csv", index=False)
    nested = (ch.groupby(["series", "fold_type"])[["outer_deviance", "base_deviance"]].sum()
              .assign(skill_pct=lambda x: (1 - x.outer_deviance / x.base_deviance) * 100)
              .skill_pct.unstack().reset_index())
    each = (rows.groupby(["series", "fold_type", "config"])[["outer_deviance", "base_deviance"]].sum()
            .assign(skill_pct=lambda x: (1 - x.outer_deviance / x.base_deviance) * 100)
            .skill_pct.unstack("fold_type").reset_index())
    freq = folds.groupby(["series", "config"]).size().rename("folds_chosen").reset_index()
    fin = final[final.chosen][["series", "config"]]
    imp_t = (imp.groupby(["series", "model", "group"]).deviance_rise_pct.agg(["mean", "min", "max"])
             .round(1).reset_index().sort_values(["series", "model", "mean"], ascending=[True, True, False]))
    e = ep.groupby(["series", "episode"])[["actual", "base", "chosen"]].sum()
    etab = pd.DataFrame({"observed_%": (e.actual / e.base - 1) * 100,
                         "chosen_%": (e.chosen / e.base - 1) * 100}).reset_index()
    s = ["# Stage 2: nested choice of the model (PROVISIONAL)\n",
         "Candidates fixed in advance: regression (T, SM_RZ hinges), compact boosting (9 features), full "
         "boosting (30 features), each with the weather response changing from 2000, 2005, 2010 or not at "
         "all. In every outer fold the candidate is chosen by inner cross-validation on the training years "
         "only. See scripts/select_stage2.py.\n",
         "## Nested out-of-sample skill (% of the no-weather deviance removed; the whole procedure)\n",
         md(nested, "{:.1f}"), "\n## Choice for the chain (inner CV on all years)\n", md(fin),
         "\n## How often each candidate is chosen in the outer folds (of 11 per series)\n", md(freq),
         "\n## Each candidate's own outer skill (for reference; not nested)\n", md(each, "{:.1f}"),
         "\n## Episodes held out, chosen model: national production vs no-weather model (%)\n",
         md(etab, "{:.1f}"),
         "\n## Grouped importance (boosting, change from 2000): rise in held-out deviance when a "
         "mechanism's features are shuffled, % (mean, min, max over the 11 outer folds)\n", md(imp_t, "{:.1f}")]
    (OUT / "stage2_nested.md").write_text("\n".join(s) + "\n")
    print("\n".join(s))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    main(ap.parse_args().workers)
