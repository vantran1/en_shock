"""Specification tests and episode validation for the v5 direct approach, palay.
PROVISIONAL. Diagnostics for choosing the specification, not the deliverable.

1. Specification tests (v5 Section 3.2: "Several choices are still being tested on the
   palay data"): each variant changes one choice of the base specification of Eq. (4)
   (src/estimation/direct.py, Spec), for irrigated and rainfed palay, Poisson and log-LS:
     base            Eq. 4: lags 1-4, one RONI effect, regional effects, regional trends
     split           El Nino and La Nina with separate effects
     season          effects shifted in wet-season harvest quarters (Q3-Q4)
     trend_rq        trends by region and quarter of year
     trend_spline    smooth regional trends (natural cubic spline, 3 df)
     lags_0_4        lags 0-4 (current quarter included)
     lags_1_6        lags 1-6
     pool_island     effects pooled by island group (Luzon, Visayas, Mindanao)
     pool_national   one national effect
   Fit is compared with an information criterion that charges for extra parameters:
   BIC = n ln(RSS/n) + k ln n (log-LS) and deviance + k ln n (Poisson, a quasi-BIC).
2. Validation (v5 Section 3.6): each strong El Nino episode (1997Q2-1998Q4, 2015Q2-2016Q4,
   2023Q2-2024Q4) is left out in turn, the model is re-estimated without it (timing
   parameters included) and the predicted loss is compared with the observed one, both
   against the model's neutral path (RONI = DMI = 0, controls as observed), summed over
   regions and the episode's quarters (Poisson):
     observed loss  = 1 - sum(actual) / sum(neutral prediction)
     predicted loss = 1 - sum(prediction with the observed RONI and DMI) / sum(neutral).

Run:  python scripts/compare_direct_v5_rice.py      (about 10 minutes on 8 cores)
Writes outputs/tables/direct_v5_rice_spec_comparison.csv, direct_v5_rice_validation.csv,
outputs/direct_v5_rice_specs.md
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import sys  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import estimate_direct_v5_rice as m  # noqa: E402
from estimation.direct import (Spec, base_design, climate_design, estimate,  # noqa: E402
                               is_climate, national_effect)
from estimation.setup import break_dummies  # noqa: E402

TAB, OUT = ROOT / "outputs/tables", ROOT / "outputs/direct_v5_rice_specs.md"
SPECS = [Spec("base"), Spec("split", split=True), Spec("season", season=True),
         Spec("trend_rq", trend="region_quarter"), Spec("trend_spline", trend="region_spline"),
         Spec("lags_0_4", K=5, first_lag=0), Spec("lags_1_6", K=6),
         Spec("pool_island", pooling="island"), Spec("pool_national", pooling="national")]
SPEC_OF = {s.name: s for s in SPECS}
EPISODES = m.EPISODES
WORKERS = 8


def prepare(eco, model, spec):
    p = m.build(eco)
    d, y = m.sample(p, model)
    LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
    LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
    base = base_design(d, m.CONTROLS, break_dummies(d, "palay"), spec.trend)
    return d, y, LR, LD, base


def episode_losses(d, X_full, b, holdout_mask=None):
    """Observed and predicted losses per episode, against the model's neutral path."""
    Xv = X_full.reindex(columns=b.index, fill_value=0.0)
    eta = Xv.to_numpy(float) @ b.to_numpy()
    clim = [c for c in b.index if is_climate(c)]
    eta0 = eta - Xv[clim].to_numpy(float) @ b[clim].to_numpy()
    mu, mu0 = np.exp(eta), np.exp(eta0)
    act = (d.production_t / 1000).to_numpy()
    out = {}
    for ep, (a, z) in EPISODES.items():
        w = d.period.between(a, z).to_numpy()
        out[ep] = (1 - act[w].sum() / mu0[w].sum(), 1 - mu[w].sum() / mu0[w].sum())
    return out


def run(job):
    eco, model, name, holdout = job
    spec = SPEC_OF[name]
    d, y, LR, LD, base = prepare(eco, model, spec)
    if holdout is None:
        r = estimate(d, y, LR, LD, base, model, spec)
        w = m.weights(eco)
        row = dict(ecosystem=eco, model=model, spec=name, n=len(d), k=r["k"], loss=r["loss"],
                   theta_R=r["theta_R"], theta_D=r["theta_D"], theta_on_grid_edge=r["on_grid_edge"])
        row["ic"] = (len(d) * np.log(r["loss"] / len(d)) if model == "ols" else r["loss"]) \
            + r["k"] * np.log(len(d))
        for idx in (("RP", "RN") if spec.split else ("R",)) + ("D",):
            est, se = national_effect(r["fit"], r["X"], w, idx, spec)
            row[f"B_{idx}"], row[f"t_{idx}"] = est, est / se
            if spec.season:
                est, se = national_effect(r["fit"], r["X"], w, idx, spec, wet=True)
                row[f"B_{idx}_wet"], row[f"t_{idx}_wet"] = est, est / se
        if model == "ppml":
            for ep, (obs, pred) in episode_losses(d, r["X"], r["fit"]["params"]).items():
                row[f"in_sample_{ep}_observed"], row[f"in_sample_{ep}_predicted"] = obs, pred
        return "spec", row
    a, z = EPISODES[holdout]
    tr = ~d.period.between(a, z).to_numpy()
    dt = d[tr].reset_index(drop=True)
    r = estimate(dt, y[tr].reset_index(drop=True), LR[tr], LD[tr], base[tr].reset_index(drop=True),
                 model, spec)
    X_full = pd.concat([climate_design(d, LR, LD, r["theta_R"], r["theta_D"], spec), base], axis=1)
    obs, pred = episode_losses(d, X_full, r["fit"]["params"])[holdout]
    return "val", dict(ecosystem=eco, model=model, spec=name, episode=holdout,
                       theta_R=r["theta_R"], theta_D=r["theta_D"],
                       observed_loss_pct=obs * 100, predicted_loss_pct=pred * 100)


def md(df, fmt="{:.3f}"):
    def cell(v):
        return "" if isinstance(v, float) and np.isnan(v) else (fmt.format(v) if isinstance(v, float) else str(v))
    return "\n".join(["| " + " | ".join(map(str, df.columns)) + " |",
                      "|" + "|".join("---" for _ in df.columns) + "|"] +
                     ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)])


def main():
    jobs = [(e, mod, s.name, None) for e in ("irrigated", "rainfed") for mod in ("ppml", "ols")
            for s in SPECS]
    jobs += [(e, "ppml", s.name, ep) for e in ("irrigated", "rainfed") for s in SPECS
             for ep in EPISODES]
    with ProcessPoolExecutor(WORKERS) as ex:
        results = list(ex.map(run, jobs))
    spec = pd.DataFrame([r for k, r in results if k == "spec"])
    val = pd.DataFrame([r for k, r in results if k == "val"])
    base_ic = spec[spec.spec == "base"].set_index(["ecosystem", "model"]).ic
    spec["ic_minus_base"] = spec.ic - spec.set_index(["ecosystem", "model"]).index.map(base_ic)
    spec.assign(status=m.STATUS).round(4).to_csv(TAB / "direct_v5_rice_spec_comparison.csv", index=False)
    val["error_pts"] = val.predicted_loss_pct - val.observed_loss_pct
    val.assign(status=m.STATUS).round(3).to_csv(TAB / "direct_v5_rice_validation.csv", index=False)

    order = [s.name for s in SPECS]
    pd.set_option("display.width", 250, "display.max_columns", 40)
    eff = spec.copy()
    eff["El Nino effect"] = eff.B_RP.fillna(eff.B_R) if "B_RP" in eff else eff.B_R
    eff["t"] = eff.t_RP.fillna(eff.t_R) if "t_RP" in eff else eff.t_R
    cols = ["ecosystem", "model", "spec", "k", "ic_minus_base", "theta_R", "theta_D",
            "El Nino effect", "t"] + [c for c in ("B_RN", "t_RN", "B_R_wet", "t_R_wet") if c in eff]
    tab = eff[cols].assign(spec=pd.Categorical(eff.spec, order)).sort_values(["ecosystem", "model", "spec"])
    vt = val.pivot_table(index=["ecosystem", "spec"], columns="episode",
                         values=["observed_loss_pct", "predicted_loss_pct"]).round(1)
    vt.columns = [f"{'obs' if a.startswith('obs') else 'pred'} {b}" for a, b in vt.columns]
    vt = vt[[f"{k} {ep}" for ep in EPISODES for k in ("obs", "pred")]]
    mae = val.groupby(["ecosystem", "spec"]).error_pts.apply(lambda s: s.abs().mean()).rename("mean abs error (pts)")
    vt = vt.join(mae.round(2)).reset_index()
    vt["spec"] = pd.Categorical(vt.spec, order)
    vt = vt.sort_values(["ecosystem", "spec"])
    print(tab.round(3).to_string(index=False))
    print(vt.to_string(index=False))

    s = ["# v5 direct approach for palay: specification tests and validation (PROVISIONAL)\n",
         "Built by `scripts/compare_direct_v5_rice.py`. Each variant changes one choice of the "
         "base specification (v5 Eq. 4). `ic_minus_base` < 0 means a better fit after charging "
         "for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = "
         "production-weighted national total effect of a sustained +1 °C RONI (log points; "
         "the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on "
         "RONI- means La Niña raises production).\n",
         "## Specification tests\n", md(tab.astype({"spec": str})), "",
         "## Leave-one-episode-out validation (Poisson)\n",
         "Loss in % of the model's neutral path over the episode's quarters, all regions; "
         "obs = observed, pred = predicted by the model estimated without the episode.\n",
         md(vt.astype({"spec": str}), "{:.1f}")]
    OUT.write_text("\n".join(s))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
