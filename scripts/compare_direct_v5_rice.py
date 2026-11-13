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

VR and PF (--crop vr|pf, calorie indices from 2010): only the 2015-16 and 2023-24 episodes
are in the data. Set 'vrpf' compares, on top of v5 as written, the rice/corn candidate
(split + season + spline) with the choices that matter most for a short sample: linear
instead of spline trends, effects pooled by island group or nationally, lags 1-6 (v5: up
to six for PF), and no season shift.

Sets of specifications (--set):
  one_change  the list above (default; outputs without suffix)
  vrpf, vrpf_national  VR and PF (see above)
  candidate   the combination suggested by the one-change tests: Poisson-relevant choices
              El Nino / La Nina split + season shift + spline trends + regional effects,
              and the same with the RONI effects shifting from 2000, 2005 or 2010 on
              (effect_break: has the El Nino effect changed over time?)

Run:  python scripts/compare_direct_v5_rice.py [--crop rice|corn] [--set SET] [--break-start YYYYQn]
      (corn: total corn; --break-start sets the Region VI break dummy, estimation.setup)
      (about 10 minutes on 8 cores per set)
Writes outputs/tables/direct_v5_<crop>_spec_comparison[_<set>].csv,
direct_v5_<crop>_validation[_<set>].csv, outputs/direct_v5_<crop>_specs[_<set>].md
"""
import argparse
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

import estimate_direct as m  # noqa: E402
from estimation.direct import (Spec, base_design, climate_design, estimate,  # noqa: E402
                               is_climate, national_effect)
from estimation.setup import break_dummies  # noqa: E402

TAB = ROOT / "outputs/tables"
ONE_CHANGE = [Spec("base"), Spec("split", split=True), Spec("season", season=True),
         Spec("trend_rq", trend="region_quarter"), Spec("trend_spline", trend="region_spline"),
         Spec("lags_0_4", K=5, first_lag=0), Spec("lags_1_6", K=6),
         Spec("pool_island", pooling="island"), Spec("pool_national", pooling="national")]
_CAND = dict(split=True, season=True, trend="region_spline")
CANDIDATE = [Spec("candidate", **_CAND)] + [Spec(f"candidate_break{y}", effect_break=y, **_CAND)
                                            for y in (2000, 2005, 2010)]
DECLINE = [Spec("step_2000", effect_break=2000, **_CAND),
           Spec("gradual_linear", effect_trend=True, **_CAND)]
SUMMARY = [Spec("base"), Spec("candidate", **_CAND), Spec("step_2000", effect_break=2000, **_CAND),
           Spec("gradual_linear", effect_trend=True, **_CAND)]
# with and without the DMI, on each crop's recommended specification
DMI_SETS = {"rice": [Spec("recommended", effect_break=2000, **_CAND),
                     Spec("recommended_no_dmi", effect_break=2000, dmi=False, **_CAND)],
            "corn": [Spec("recommended_corn", **_CAND),
                     Spec("recommended_corn_no_dmi", dmi=False, **_CAND)],
            "vr": [Spec("recommended_vrpf", trend="region_spline", pooling="national"),
                   Spec("recommended_vrpf_no_dmi", trend="region_spline", pooling="national", dmi=False)]}
DMI_SETS["pf"] = DMI_SETS["vr"]
BREAK_YEARS = [Spec("no_break", **_CAND)] + [Spec(f"step_{y}", effect_break=y, **_CAND)
                                              for y in (2000, 2005, 2010)]
VRPF = [Spec("base"), Spec("candidate", **_CAND),
        Spec("candidate_linear_trend", split=True, season=True),
        Spec("candidate_no_season", split=True, trend="region_spline"),
        Spec("candidate_island", pooling="island", **_CAND),
        Spec("candidate_national", pooling="national", **_CAND),
        Spec("candidate_lags_1_6", K=6, **_CAND),
        Spec("candidate_island_lags_1_6", K=6, pooling="island", **_CAND)]
# VR / PF, second round: smooth trends + one national effect (best in both rounds), with one
# choice changed at a time
_NAT = dict(trend="region_spline", pooling="national")
VRPF_NATIONAL = [Spec("base"), Spec("spline_national", **_NAT),
                 Spec("spline_national_split", split=True, **_NAT),
                 Spec("spline_national_season", season=True, **_NAT),
                 Spec("spline_national_lags_1_6", K=6, **_NAT),
                 Spec("spline_island", trend="region_spline", pooling="island"),
                 Spec("spline_region", trend="region_spline")]
SETS = {"one_change": ONE_CHANGE, "candidate": CANDIDATE, "decline": DECLINE, "summary": SUMMARY,
        "dmi": None, "breaks": BREAK_YEARS, "vrpf": VRPF, "vrpf_national": VRPF_NATIONAL}
TEST_SERIES = {"rice": ["irrigated", "rainfed"], "corn": ["corn"], "vr": ["vr"], "pf": ["pf"]}
T_1995 = (1995 - 2006) / 10  # t of 1995 in the panel's time variable
SPEC_OF = {s.name: s for v in list(SETS.values()) + list(DMI_SETS.values()) if v for s in v}
EPISODES = m.EPISODES
WORKERS = 8


def prepare(eco, model, spec, break_start=None):
    p = m.build(eco)
    d, y = m.sample(p, model, m.GROUP[eco])
    LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
    LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
    base = base_design(d, m.CONTROLS, break_dummies(d, m.GROUP[eco], start=break_start), spec.trend)
    return d, y, LR, LD, base


def episode_losses(d, X_full, b, episodes=EPISODES, scale=1000):
    """Observed and predicted losses per episode, against the model's neutral path."""
    Xv = X_full.reindex(columns=b.index, fill_value=0.0)
    eta = Xv.to_numpy(float) @ b.to_numpy()
    clim = [c for c in b.index if is_climate(c)]
    eta0 = eta - Xv[clim].to_numpy(float) @ b[clim].to_numpy()
    mu, mu0 = np.exp(eta), np.exp(eta0)
    act = (d.production_t / scale).to_numpy()
    out = {}
    for ep, (a, z) in episodes.items():
        w = d.period.between(a, z).to_numpy()
        out[ep] = (1 - act[w].sum() / mu0[w].sum(), 1 - mu[w].sum() / mu0[w].sum())
    return out


def run(job):
    eco, model, name, holdout, break_start = job
    spec = SPEC_OF[name]
    d, y, LR, LD, base = prepare(eco, model, spec, break_start)
    if holdout is None:
        r = estimate(d, y, LR, LD, base, model, spec)
        w = m.weights(eco)
        row = dict(ecosystem=eco, model=model, spec=name, n=len(d), k=r["k"], loss=r["loss"],
                   theta_R=r["theta_R"], theta_D=r["theta_D"], theta_on_grid_edge=r["on_grid_edge"])
        row["ic"] = (len(d) * np.log(r["loss"] / len(d)) if model == "ols" else r["loss"]) \
            + r["k"] * np.log(len(d))
        for idx in (("RP", "RN") if spec.split else ("R",)) + (("D",) if spec.dmi else ()):
            est, se = national_effect(r["fit"], r["X"], w, idx, spec)
            row[f"B_{idx}"], row[f"t_{idx}"] = est, est / se
            if spec.season:
                est, se = national_effect(r["fit"], r["X"], w, idx, spec, wet=True)
                row[f"B_{idx}_wet"], row[f"t_{idx}_wet"] = est, est / se
            if idx != "D" and (spec.effect_break is not None or spec.effect_trend):
                base_est = row[f"B_{idx}"]  # dry-season effect (est is reused above for wet)
                if spec.effect_trend:
                    today = base_est
                    e95, _ = national_effect(r["fit"], r["X"], w, idx, spec, dt=T_1995 - spec.t_today)
                else:
                    today, _ = national_effect(r["fit"], r["X"], w, idx, spec, post=True)
                    e95 = base_est
                row[f"B_{idx}_today"], row[f"B_{idx}_1995"] = today, e95
                c = f"S{idx}_trend"
                if c in r["X"].columns:
                    sh = r["fit"]["params"][c]
                    row[f"change_per_decade_{idx}"] = sh
                    row[f"t_change_per_decade_{idx}"] = sh / r["fit"]["se"][r["X"].columns.get_loc(c)]
            if spec.effect_break is not None and idx != "D":
                est, se = national_effect(r["fit"], r["X"], w, idx, spec, post=True)
                row[f"B_{idx}_post"], row[f"t_{idx}_post"] = est, est / se
                c = f"S{idx}_post"
                if c in r["X"].columns:
                    sh = r["fit"]["params"][c]
                    row[f"shift_{idx}_post"] = sh
                    row[f"t_shift_{idx}_post"] = sh / r["fit"]["se"][r["X"].columns.get_loc(c)]
        if model == "ppml":
            for ep, (obs, pred) in episode_losses(d, r["X"], r["fit"]["params"], m.episodes_for(eco),
                                                  m.PPML_SCALE[m.GROUP[eco]]).items():
                row[f"in_sample_{ep}_observed"], row[f"in_sample_{ep}_predicted"] = obs, pred
        return "spec", row
    a, z = EPISODES[holdout]
    tr = ~d.period.between(a, z).to_numpy()
    dt = d[tr].reset_index(drop=True)
    r = estimate(dt, y[tr].reset_index(drop=True), LR[tr], LD[tr], base[tr].reset_index(drop=True),
                 model, spec)
    X_full = pd.concat([climate_design(d, LR, LD, r["theta_R"], r["theta_D"], spec), base], axis=1)
    obs, pred = episode_losses(d, X_full, r["fit"]["params"], EPISODES,
                               m.PPML_SCALE[m.GROUP[eco]])[holdout]
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="one_change", choices=list(SETS))
    ap.add_argument("--crop", default="rice", choices=list(TEST_SERIES))
    ap.add_argument("--break-start", help="start of the measurement-break dummy (corn), e.g. 2023Q3")
    ap.add_argument("--report-only", action="store_true",
                    help="rewrite the markdown report from the saved tables")
    args = ap.parse_args()
    SPECS = SETS[args.set] or DMI_SETS[args.crop]
    suffix = "" if args.set == "one_change" else f"_{args.set}"
    crop = args.crop
    OUT = ROOT / f"outputs/direct_v5_{crop}_specs{suffix}.md"
    first = SPECS[0].name
    series = TEST_SERIES[crop]
    bs = args.break_start
    jobs = [(e, mod, s.name, None, bs) for e in series for mod in ("ppml", "ols") for s in SPECS]
    jobs += [(e, "ppml", s.name, ep, bs) for e in series for s in SPECS for ep in m.episodes_for(e)]
    if not args.report_only:
        with ProcessPoolExecutor(WORKERS) as ex:
            results = list(ex.map(run, jobs))
        spec = pd.DataFrame([r for k, r in results if k == "spec"])
        val = pd.DataFrame([r for k, r in results if k == "val"])
        base_ic = spec[spec.spec == first].set_index(["ecosystem", "model"]).ic
        spec["ic_minus_base"] = spec.ic - spec.set_index(["ecosystem", "model"]).index.map(base_ic)
        spec.assign(status=m.STATUS).round(4).to_csv(
            TAB / f"direct_v5_{crop}_spec_comparison{suffix}.csv", index=False)
        val["error_pts"] = val.predicted_loss_pct - val.observed_loss_pct
        val.assign(status=m.STATUS).round(3).to_csv(TAB / f"direct_v5_{crop}_validation{suffix}.csv",
                                                    index=False)
    spec = pd.read_csv(TAB / f"direct_v5_{crop}_spec_comparison{suffix}.csv")
    val = pd.read_csv(TAB / f"direct_v5_{crop}_validation{suffix}.csv")

    order = [s.name for s in SPECS]
    pd.set_option("display.width", 250, "display.max_columns", 40)
    eff = spec.copy()
    nan = pd.Series(np.nan, index=eff.index)
    eff["El Nino effect"] = eff.get("B_RP", nan).fillna(eff.get("B_R", nan))
    eff["t"] = eff.get("t_RP", nan).fillna(eff.get("t_R", nan))
    cols = ["ecosystem", "model", "spec", "k", "ic_minus_base", "theta_R", "theta_D",
            "El Nino effect", "t"] + [c for c in ("B_RN", "t_RN", "B_R_wet", "t_R_wet", "B_RP_wet",
                                                  "t_RP_wet", "B_RP_post", "t_RP_post",
                                                  "shift_RP_post", "t_shift_RP_post",
                                                  "shift_RN_post", "t_shift_RN_post",
                                                  "B_RP_today", "B_RP_1995",
                                                  "change_per_decade_RP", "t_change_per_decade_RP")
                         if c in eff]
    tab = eff[cols].assign(spec=pd.Categorical(eff.spec, order)).sort_values(["ecosystem", "model", "spec"])
    vt = val.pivot_table(index=["ecosystem", "spec"], columns="episode",
                         values=["observed_loss_pct", "predicted_loss_pct"]).round(1)
    vt.columns = [f"{'obs' if a.startswith('obs') else 'pred'} {b}" for a, b in vt.columns]
    vt = vt[[f"{k} {ep}" for ep in EPISODES if ep in set(val.episode) for k in ("obs", "pred")]]
    mae = val.groupby(["ecosystem", "spec"]).error_pts.apply(lambda s: s.abs().mean()).rename("mean abs error (pts)")
    vt = vt.join(mae.round(2)).reset_index()
    vt["spec"] = pd.Categorical(vt.spec, order)
    vt = vt.sort_values(["ecosystem", "spec"])
    print(tab.round(3).to_string(index=False))
    print(vt.to_string(index=False))

    s = [f"# v5 direct approach for {'palay' if crop == 'rice' else crop}: specification tests "
         "and validation (PROVISIONAL)\n",
         f"Built by `scripts/compare_direct_v5_rice.py --crop {crop} --set {args.set}"
         + (f" --break-start {bs}" if bs else "") + "`. "
         + ("Each variant changes one choice of the base specification (v5 Eq. 4). "
            if args.set == "one_change" else
            "Step versus gradual change of the El Niño effect, both on the candidate (El Niño / "
            "La Niña split + season shift + spline trends + regional effects): step_2000 = "
            "effects shift from 2000; gradual_linear = effects change linearly over time "
            "(B_RP = today's effect, change_per_decade_RP its rate of change). B_RP_today and "
            "B_RP_1995 compare the two (dry-season harvest). "
            if args.set == "decline" else
            "Summary set: v5 as written (base), the candidate (El Niño / La Niña split + season shift "
            "+ spline trends), and the candidate with the effect changing in a step in 2000 or "
            "gradually (B_RP_today / B_RP_1995 compare them). "
            if args.set == "summary" else
            "With and without the DMI, on the crop's recommended specification (the DMI moves "
            "together with RONI when El Niño builds and its timing is poorly identified). "
            if args.set == "dmi" else
            "Break year of the El Niño effect on the full sample: no break versus a step in 2000, "
            "2005 or 2010 (candidate specification otherwise; B_RP = effect before the break, "
            "B_RP_today = from the break on, shift_RP_post = the change). "
            if args.set == "breaks" else
            "VR / PF set: v5 as written, the rice/corn candidate (El Niño / La Niña split + season "
            "shift + spline trends + regional effects) and the candidate with one choice changed "
            "(linear trends, no season shift, effects pooled by island group or nationally, lags "
            "1-6). Calorie index from 2010; only the 2015-16 and 2023-24 episodes are in the data. "
            if args.set == "vrpf" else
            "VR / PF, second round: smooth regional trends with one national effect (best in the "
            "first round), and with one choice changed (El Niño / La Niña split, season shift, "
            "lags 1-6, effects by island group or by region). "
            if args.set == "vrpf_national" else
            "Candidate = El Niño / La Niña split + season shift + spline trends + regional effects; "
            "the break variants let the El Niño and La Niña effects shift from 2000, 2005 or 2010 on "
            "(B_RP = El Niño effect in dry-season harvest quarters before the break; B_RP_post after; "
            "shift_RP_post = the change, with its t). ")
         + f"`ic_minus_base` (relative to `{first}`) < 0 means a better fit after charging "
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
