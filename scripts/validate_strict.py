"""Stricter leave-one-episode-out validation of the direct approach (methodology v5 Section
3.6), saved separately from the earlier validation (compare_direct_v5_rice.py), which is
kept as it is. PROVISIONAL; a diagnostic, not a result.

Stricter in three ways (change log C7):
1. Held-out window = the episode (1997Q2-1998Q4, 2015Q2-2016Q4, 2023Q2-2024Q4) plus the 4
   quarters after it, so that no training quarter has the episode's RONI among its lags
   (1-4). Losses are measured over the episode window, as before.
2. Inside each fold, the break year of the El Nino effect is chosen among 2000, 2005, 2010
   and no break using only the training data (lowest deviance + k ln n), and the timing
   parameters are re-chosen (profile estimation on the 0.05 grid) for each candidate.
3. The trends are set on the training years only: region-specific restricted cubic splines
   (Harrell; knots at the 5/35/65/95% quantiles of the training years; linear beyond the
   outer knots, so they extend to held-out years at the end of the sample). This replaces
   the spline of the main estimation (patsy natural cubic spline, which cannot be evaluated
   outside its knots); flexibility is the same (3 terms per region).

Variants (Poisson): the recommended specification (El Nino / La Nina split, season shift,
spline trends, nested break choice) and v5 as written (one RONI effect, linear regional
trends, no break), each with and without the DMI.
Loss definitions as before: observed = 1 - sum(actual) / sum(neutral prediction);
predicted = 1 - sum(prediction with observed RONI and DMI) / sum(neutral prediction);
neutral = RONI = DMI = 0, controls as observed, from the model estimated without the window.

Run:  python scripts/validate_strict.py --crop rice|corn
Writes outputs/tables/validation_strict_<crop>.csv and outputs/validation_strict_<crop>.md
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import argparse  # noqa: E402
import sys  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

import estimate_direct as m  # noqa: E402
from estimation.direct import Spec, THETA_GRID, climate_design, is_climate, profile  # noqa: E402
from estimation.setup import break_dummies  # noqa: E402

TAB, OUT = ROOT / "outputs/tables", ROOT / "outputs"
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"),
            "2023-24": ("2023Q2", "2024Q4")}
EXTRA_AFTER = 4
BREAKS = [2000, 2005, 2010, None]
SERIES = {"rice": ["irrigated", "rainfed"], "corn": ["corn"]}
REC = Spec("recommended", split=True, season=True, trend="rcs")
V5 = Spec("v5", trend="region")
VARIANTS = {"recommended (nested break)": REC, "recommended, no DMI (nested break)": replace(REC, dmi=False),
            "v5 as written": V5, "v5 as written, no DMI": replace(V5, dmi=False)}


def rcs(t: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """Restricted cubic spline basis (Harrell): t and K-2 nonlinear terms, linear beyond the
    outer knots."""
    k = knots
    K = len(k)
    pos = lambda x: np.clip(x, 0, None) ** 3  # noqa: E731
    cols = [t]
    for j in range(K - 2):
        f = (pos(t - k[j]) - pos(t - k[K - 2]) * (k[K - 1] - k[j]) / (k[K - 1] - k[K - 2])
             + pos(t - k[K - 1]) * (k[K - 2] - k[j]) / (k[K - 1] - k[K - 2]))
        cols.append(f / (k[K - 1] - k[0]) ** 2)
    return np.column_stack(cols)


def base_design(d, train, spec, extra):
    """Region x quarter effects, trends set on the training rows, controls, break dummies."""
    rq = d.region_code + "_q" + d.q.astype(str)
    fe = pd.get_dummies(rq, prefix="fe", dtype=float)
    reg = pd.get_dummies(d.region_code, dtype=float)
    t = d.t.to_numpy(float)
    if spec.trend == "region":
        B = t[:, None]
    else:
        knots = np.quantile(t[train], [0.05, 0.35, 0.65, 0.95])
        B = rcs(t, knots)
    tr = pd.concat([reg.mul(B[:, j], axis=0).add_prefix(f"tr{j}_") for j in range(B.shape[1])], axis=1)
    parts = [fe, tr, d[m.CONTROLS]]
    if extra is not None and extra.shape[1]:
        parts.append(extra)
    return pd.concat(parts, axis=1)


def fit_fold(d, y, LR, LD, base, train, spec):
    """Timing by profile estimation on the training rows, then a Poisson fit; returns params,
    thetas and the information criterion (deviance + k ln n) on the training rows."""
    bt = base.loc[train]
    bt = bt.loc[:, bt.abs().sum() > 0]
    dt = d.loc[train].reset_index(drop=True)
    prof = profile(dt, y[train], LR[train], LD[train], bt.reset_index(drop=True), "ppml", spec, THETA_GRID)
    best = prof.loc[prof.loss.idxmin()]
    tR, tD = float(best.theta_R), float(best.theta_D)
    X = pd.concat([climate_design(d, LR, LD, tR, tD, spec), base], axis=1)
    Xt = X.loc[train]
    Xt = Xt.loc[:, Xt.abs().sum() > 0]
    res = sm.GLM(y[train], Xt.to_numpy(float), family=sm.families.Poisson()).fit(maxiter=200, tol=1e-10)
    ic = res.deviance + Xt.shape[1] * np.log(train.sum())
    return pd.Series(res.params, index=Xt.columns), X, tR, tD, ic


def run(job):
    crop, eco, variant, episode = job
    spec0 = VARIANTS[variant]
    p = m.build(eco)
    d, yser = m.sample(p, "ppml")
    y = yser.to_numpy(float)
    LR, LD = m.index_lags("roni", d.period), m.index_lags("dmi", d.period)
    per = pd.PeriodIndex(d.period, freq="Q")
    a, z = EPISODES[episode]
    held = (per >= pd.Period(a, "Q")) & (per <= pd.Period(z, "Q") + EXTRA_AFTER)
    window = (per >= pd.Period(a, "Q")) & (per <= pd.Period(z, "Q"))
    train = ~np.asarray(held)
    extra = break_dummies(d, m.GROUP[eco])
    base = base_design(d, train, spec0, extra)
    candidates = BREAKS if spec0.name == "recommended" else [None]
    fits = {}
    for b in candidates:
        fits[b] = fit_fold(d, y, LR, LD, base, train, replace(spec0, effect_break=b))
    chosen = min(fits, key=lambda b: fits[b][4])
    params, X, tR, tD, ic = fits[chosen]
    Xv = X.reindex(columns=params.index, fill_value=0.0)
    eta = Xv.to_numpy(float) @ params.to_numpy()
    clim = [c for c in params.index if is_climate(c)]
    eta0 = eta - Xv[clim].to_numpy(float) @ params[clim].to_numpy()
    w = np.asarray(window)
    obs = 1 - y[w].sum() / np.exp(eta0[w]).sum()
    pred = 1 - np.exp(eta[w]).sum() / np.exp(eta0[w]).sum()
    return dict(crop=crop, series=eco, variant=variant, episode=episode,
                chosen_break="none" if chosen is None else str(chosen),
                ic_by_break={("none" if b is None else str(b)): round(f[4] - fits[chosen][4], 1)
                             for b, f in fits.items()} if len(fits) > 1 else "",
                theta_R=tR, theta_D=tD if spec0.dmi else np.nan, n_train=int(train.sum()),
                observed_loss_pct=obs * 100, predicted_loss_pct=pred * 100,
                error_pts=(pred - obs) * 100)


def md(df, fmt="{:.1f}"):
    def cell(v):
        return "" if isinstance(v, float) and np.isnan(v) else (fmt.format(v) if isinstance(v, float) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |",
                      "|" + "|".join("---" for _ in df.columns) + "|"] +
                     ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)])


def report(t, crop):
    s = [f"# Stricter leave-one-episode-out validation: {crop} (PROVISIONAL)\n",
         "Built by `scripts/validate_strict.py`. Held-out window = episode + 4 quarters; break "
         "year chosen inside each fold (2000, 2005, 2010 or none) on the training data; trends "
         "set on the training years (restricted cubic splines). Poisson. Losses in % of the "
         "model's neutral path over the episode window. Error = predicted − observed.\n"]
    for eco in SERIES[crop]:
        e = t[t.series == eco]
        s.append(f"## {eco}\n")
        tab = e[["variant", "episode", "chosen_break", "theta_R", "observed_loss_pct",
                 "predicted_loss_pct", "error_pts"]].sort_values(["variant", "episode"])
        s.append(md(tab))
        s.append("")
        mae = e.groupby("variant").error_pts.apply(lambda x: x.abs().mean()).rename("mean abs error")
        drop = {ep: e[e.episode != ep].groupby("variant").error_pts.apply(lambda x: x.abs().mean())
                for ep in EPISODES}
        summ = pd.concat([mae] + [v.rename(f"without {k}") for k, v in drop.items()], axis=1).reset_index()
        s.append("Mean absolute error, all three episodes and leaving each one out (to see whether a "
                 "single episode drives the comparison):\n")
        s.append(md(summ))
        s.append("")
        picks = e[e.variant.str.startswith("recommended")][["variant", "episode", "chosen_break", "ic_by_break"]]
        s.append("Break year chosen in each fold (information criterion of each candidate relative "
                 "to the chosen one):\n")
        s.append(md(picks))
        s.append("")
    (OUT / f"validation_strict_{crop}.md").write_text("\n".join(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", choices=list(SERIES), default="rice")
    crop = ap.parse_args().crop
    jobs = [(crop, e, v, ep) for e in SERIES[crop] for v in VARIANTS for ep in EPISODES]
    with ProcessPoolExecutor(8) as ex:
        t = pd.DataFrame(list(ex.map(run, jobs)))
    t.assign(ic_by_break=t.ic_by_break.astype(str), status="provisional").round(3).to_csv(
        TAB / f"validation_strict_{crop}.csv", index=False)
    report(t, crop)
    pd.set_option("display.width", 250)
    print(t.drop(columns=["ic_by_break"]).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
