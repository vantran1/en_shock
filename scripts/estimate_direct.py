"""Direct approach, RECOMMENDED specification, for a crop: rice (irrigated and rainfed
palay) or corn (total, white and yellow). PROVISIONAL results.

DIFFERS FROM THE CURRENT METHODOLOGY (v5). The recommended specification is v5,
Eqs. (4)-(6), with the changes the palay data support (tests and episode validation in
scripts/compare_direct_v5_rice.py). Because it fits and predicts the past El Nino
episodes better, we suggest going forward with it; the changes are proposed to Alper
(docs/methodology_change_log.md, B1-B3) and are not in the v5 text:
- El Nino and La Nina with separate total effects (RONI+ = max(RONI, 0), RONI- =
  min(RONI, 0), lag by lag), same timing parameter                         (log B1)
- smooth regional trends (natural cubic spline, 3 df) instead of linear    (log B2)
- the El Nino and La Nina effects shift from 2000 on, by a common amount in all regions;
  the post-2000 effect is the one for today's conditions                   (log B3)
- a common shift of the effects in wet-season harvest quarters (Q3-Q4)
Unchanged from v5: lags 1-4 with a binomial profile and one timing parameter each for
RONI and DMI, chosen on the grid 0.05..0.95 by profile estimation; total effects by
region; region x quarter-of-year effects; controls X_rq (typhoon exposure by PAGASA
category, current and previous quarter; flood share, current and previous; earthquake;
eruption; Pinatubo 1991); Driscoll-Kraay standard errors conditional on the timing.
Main estimator Poisson pseudo-ML (levels); least squares on logs as a check.
The current-methodology version (v5 base, compare_direct_v5_rice.py, spec 'base') and
the free-lag first look (estimate_rice_direct.py) are kept for comparison.

National effects: production-weighted mean of the regional effects (2016-2025 shares of
the ecosystem's production) plus the common shifts, for dry / wet harvest quarters and
before / from 2000. Implied losses: production relative to a neutral path (RONI = DMI = 0),
summed over regions, for the RONI part and for RONI + DMI.

Corn (tests in compare_direct_v5_rice.py --crop corn --set summary): El Nino / La Nina
split, spline trends and the wet-season shift, as for rice, but NO change of the effect
over time: neither a step in 2000 nor a gradual change is supported for corn (largely
rainfed, without rice's irrigation expansion). Corn has the Region VI
measurement break (Negros Occidental, estimation.setup): a level dummy whose start can be
set with --break-start (default: estimation.setup.BREAKS).

Run:  python scripts/estimate_direct.py --crop rice|corn [--check CHECK] [--break-start YYYYQn]
Writes outputs/tables/direct_<crop>_{coefficients,national_effects,timing,profile,
implied_losses}.csv and outputs/figures/direct_<crop>_effects.png. Checks (tables end in
_check_<name>, no figure):
  kanlaon             eruption marker includes Kanlaon Oct 2024 - Mar 2026 in Region VI
  no_vi_corn_2023q3   corn only: Region VI corn dropped from 2023Q3 (no break dummy)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agriculture.regions import REGIONS  # noqa: E402
from climate.indices import quarterly  # noqa: E402
from estimation.data import (CHECKS, CONTROLS, GROUP, PPML_SCALE, build,  # noqa: E402,F401
                             index_lags, sample, weights)
from estimation.direct import (Spec, base_design, binomial_weights, estimate,  # noqa: E402
                               is_climate, is_roni, national_effect)
from estimation.setup import break_dummies  # noqa: E402
from estimation.setup import sample as break_sample  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
K = 4
# differs from v5 (log B1-B3); recommended because the data support it
RECOMMENDED = Spec("recommended", split=True, season=True, trend="region_spline", effect_break=2000)
RECOMMENDED_CORN = Spec("recommended_corn", split=True, season=True, trend="region_spline")
# VR and PF (scripts/compare_direct_v5_rice.py --set vrpf, vrpf_national): v5 Eq. 4 (one
# RONI effect, lags 1-4) with smooth regional trends and one national effect; no El Nino /
# La Nina split, no season shift
RECOMMENDED_VRPF = Spec("recommended_vrpf", trend="region_spline", pooling="national")
RECOMMENDED_BY_CROP = {"rice": RECOMMENDED, "corn": RECOMMENDED_CORN, "vr": RECOMMENDED_VRPF,
                       "pf": RECOMMENDED_VRPF}
SPEC_NOTE = "recommended; differs from methodology v5 (change log B1-B3)"
SPEC_NOTE_BY_CROP = {"rice": SPEC_NOTE,
                     "corn": "recommended; differs from methodology v5 (change log B1-B2; no change "
                             "over time for corn)",
                     "vr": "recommended; differs from methodology v5 (spline trends, change log "
                           "B2; one national effect)",
                     "pf": "recommended; differs from methodology v5 (spline trends, change log "
                           "B2; one national effect)"}
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"),
            "2023-24": ("2023Q2", "2024Q4")}
FIRST_QUARTER = {"vr": "2010Q1", "pf": "2010Q1"}  # by crop group; others from 1987Q1


def episodes_for(series):
    """The strong episodes inside a series' data (VR and PF start in 2010: no 1997-98)."""
    start = FIRST_QUARTER.get(GROUP[series], "1987Q1")
    return {k: v for k, v in EPISODES.items() if v[0] >= start}

STATUS = "provisional"
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#d9d8d4"
INDEX_NAME = {"R": "RONI", "RP": "El Nino (RONI+)", "RN": "La Nina (RONI-)", "D": "DMI"}
CROPS = {"rice": {"series": ["irrigated", "rainfed"], "label": "palay"},
         "corn": {"series": ["corn", "corn_white", "corn_yellow"], "label": "corn"},
         "vr": {"series": ["vr", "vr_noroot"], "label": "VR"},
         "pf": {"series": ["pf", "pf_nobanana", "pf_nocavendish"], "label": "PF"}}
SAMPLE_CHECKS = {"no_vi_corn_2023q3": "end_before_break"}
COLORS = ["#2a78d6", "#eb6834", "#0d366b"]


def implied_losses(d, X, b):
    clim = [c for c in X.columns if is_climate(c)]
    roni = [c for c in clim if is_roni(c)]
    eR = X[roni].to_numpy(float) @ b[roni].to_numpy()
    eA = X[clim].to_numpy(float) @ b[clim].to_numpy()
    a = d.production_t.to_numpy()
    out = pd.DataFrame({"period": d.period, "actual": a, "neutral_roni": a / np.exp(eR),
                        "neutral_roni_dmi": a / np.exp(eA)})
    return out.groupby("period").sum()


def main(crop="rice", spec=None, check=None, break_start=None):
    spec = spec or RECOMMENDED_BY_CROP[crop]
    note = SPEC_NOTE_BY_CROP[crop]
    replace = CHECKS.get(check) if check else None
    sfx = f"_check_{check}" if check else (f"_break{break_start}" if break_start else "")
    coef_rows, nat_rows, timing_rows, losses, profiles = [], [], [], [], []
    for eco in CROPS[crop]["series"]:
        group = GROUP[eco]
        p = build(eco, replace)
        if check in SAMPLE_CHECKS:
            p = break_sample(p, group, SAMPLE_CHECKS[check]).reset_index(drop=True)
        w = weights(eco)
        for model in ("ppml", "ols"):
            d, y = sample(p, model, group)
            lagsR = index_lags("roni", d.period, spec.K, spec.first_lag)
            lagsD = index_lags("dmi", d.period, spec.K, spec.first_lag)
            extra = (break_dummies(d, group, start=break_start) if check not in SAMPLE_CHECKS
                     else None)
            base = base_design(d, CONTROLS, extra, spec.trend)
            r = estimate(d, y, lagsR, lagsD, base, model, spec)
            res, X = r["fit"], r["X"]
            se = pd.Series(res["se"], index=X.columns)
            tag = dict(ecosystem=eco, model=model)
            print(f"{eco:9s} {model}: n={len(d)}, theta_R={r['theta_R']:.2f}, "
                  f"theta_D={r['theta_D']:.2f}, edge={r['on_grid_edge']}, converged={res['converged']}")
            profiles.append(r["profile"].assign(**tag))
            wR, wD = binomial_weights(r["theta_R"], spec.K), binomial_weights(r["theta_D"], spec.K)
            timing_rows.append({**tag, "n": len(d), "k": r["k"], "theta_R": r["theta_R"],
                                "theta_D": r["theta_D"], "loss": r["loss"],
                                "theta_on_grid_edge": r["on_grid_edge"],
                                **{f"wR_lag{j + spec.first_lag}": wR[j] for j in range(spec.K)},
                                **{f"wD_lag{j + spec.first_lag}": wD[j] for j in range(spec.K)}})
            for c in X.columns:
                if is_climate(c) or c in CONTROLS:
                    kind = "climate" if is_climate(c) else "control"
                    coef_rows.append({**tag, "kind": kind, "term": c, "est": res["params"][c],
                                      "se": se[c]})
            yb = spec.effect_break
            for idx in (("RP", "RN") if spec.split else ("R",)) + (("D",) if spec.dmi else ()):
                for wet in ((False, True) if spec.season else (False,)):
                    for post in ((False, True) if idx != "D" and yb else (False,)):
                        est, s_ = national_effect(res, X, w, idx, spec, wet=wet, post=post)
                        nat_rows.append({**tag, "index": INDEX_NAME[idx],
                                         "harvest_season": ("wet (Q3-Q4)" if wet else "dry (Q1-Q2)")
                                         if spec.season else "all",
                                         "period": ((f"from {yb}" if post else f"before {yb}")
                                                    if idx != "D" and yb else "all"),
                                         "est": est, "se": s_})
            for c in X.columns:
                if c.startswith("break_"):
                    coef_rows.append({**tag, "kind": "break", "term": c, "est": res["params"][c],
                                      "se": se[c]})
            if model == "ppml":
                losses.append(implied_losses(d, X, res["params"]).assign(ecosystem=eco))

    coef = pd.DataFrame(coef_rows)
    coef["t"] = coef.est / coef.se
    coef.assign(spec=spec.name, spec_note=note, status=STATUS).round(4).to_csv(TAB / f"direct_{crop}_coefficients{sfx}.csv",
                                                               index=False)
    nat = pd.DataFrame(nat_rows)
    nat["t"] = nat.est / nat.se
    nat["pct_effect_of_+1"] = (np.exp(nat.est) - 1) * 100
    nat.assign(spec=spec.name, spec_note=note, status=STATUS).round(4).to_csv(TAB / f"direct_{crop}_national_effects{sfx}.csv",
                                                              index=False)
    timing = pd.DataFrame(timing_rows)
    timing.assign(spec=spec.name, spec_note=note, status=STATUS).round(4).to_csv(TAB / f"direct_{crop}_timing{sfx}.csv",
                                                                 index=False)
    pd.concat(profiles).round(4).to_csv(TAB / f"direct_{crop}_profile{sfx}.csv", index=False)

    L = pd.concat(losses).groupby(level=0)[["actual", "neutral_roni", "neutral_roni_dmi"]].sum()
    L["loss_roni_pct"] = (1 - L.actual / L.neutral_roni) * 100
    L["loss_roni_dmi_pct"] = (1 - L.actual / L.neutral_roni_dmi) * 100
    L.index = pd.PeriodIndex(L.index, freq="Q")
    L.assign(spec=spec.name, spec_note=note, status=STATUS).round(2).to_csv(TAB / f"direct_{crop}_implied_losses{sfx}.csv")
    yr = L.groupby(L.index.year)[["actual", "neutral_roni", "neutral_roni_dmi"]].sum()
    yr["implied_loss_roni_pct"] = (1 - yr.actual / yr.neutral_roni) * 100
    yr["implied_loss_roni_dmi_pct"] = (1 - yr.actual / yr.neutral_roni_dmi) * 100
    yr["actual_change_pct"] = yr.actual.pct_change() * 100

    pd.set_option("display.width", 220, "display.max_rows", 200)
    print("\nTiming:\n", timing.round(3).to_string(index=False))
    print("\nNational effects, Poisson (log points per +1 unit sustained; % in last column):")
    n = nat[nat.model == "ppml"].pivot_table(index=["ecosystem", "index", "period"],
                                             columns="harvest_season", values=["est", "t"])
    print(n.round(3).to_string())
    print("\nControls, Poisson:")
    print(coef[(coef.kind == "control") & (coef.model == "ppml")]
          .pivot_table(index="term", columns="ecosystem", values=["est", "t"]).round(3).to_string())
    print(f"\nImplied national loss, Poisson, {', '.join(CROPS[crop]['series'])} (% of neutral production):")
    for ep, (a, b) in episodes_for(CROPS[crop]["series"][0]).items():
        print(f"  {ep}: " + ", ".join(f"{q}: {v:.1f}%" for q, v in L.loc[a:b, "loss_roni_dmi_pct"].items()))
    print("\nYears:\n", yr.loc[[y for y in (1997, 1998, 2015, 2016, 2023, 2024) if y in yr.index],
                               ["implied_loss_roni_pct", "implied_loss_roni_dmi_pct",
                                "actual_change_pct"]].round(1).to_string())

    if check or break_start or spec.pooling != "region":
        return  # the figure shows regional effects
    # figure: regional El Nino effect (dry-season harvest, from 2000 = regional B + shift)
    reg = coef[(coef.model == "ppml") & coef.term.str.startswith("BRP_")].copy()
    reg["region_code"] = reg.term.str[4:]
    fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
    series = CROPS[crop]["series"][:2] if crop == "rice" else CROPS[crop]["series"][:1]
    for j, (eco, col) in enumerate(zip(series, COLORS)):
        e = reg[reg.ecosystem == eco].set_index("region_code").reindex(list(REGIONS))
        x = np.arange(len(REGIONS)) + (j - (len(series) - 1) / 2) * 0.25
        ax.errorbar(x, e.est, yerr=1.96 * e.se, fmt="o", ms=5, color=col, capsize=2.5, lw=1.1,
                    label=f"{eco} {CROPS[crop]['label'] if crop == 'rice' else ''}".strip()
                    + (", before 2000" if spec.effect_break else ""))
        periods = list(dict.fromkeys(nat[nat["index"] == INDEX_NAME["RP"]].period))
        for per, ls in zip(periods, ("--", ":")):
            v = nat[(nat.ecosystem == eco) & (nat.model == "ppml") & (nat["index"] == INDEX_NAME["RP"])
                    & (nat.harvest_season == "dry (Q1-Q2)") & (nat.period == per)].est.iloc[0]
            ax.axhline(v, color=col, lw=0.9, ls=ls)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(range(len(REGIONS)), list(REGIONS), fontsize=8)
    ax.set_ylabel("log points per +1 °C El Niño, sustained", fontsize=8, color=MUTED)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=8, colors=MUTED)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.legend(frameon=False, fontsize=8, title_fontsize=7,
              title=("lines: national, dashed before 2000, dotted from 2000" if spec.effect_break
                     else "dashed line: national effect"))
    changes = "El Niño / La Niña split, spline trends" + (", change from 2000" if spec.effect_break else "")
    ax.set_title(f"PROVISIONAL. {crop.capitalize()}, recommended specification, differs from v5 "
                 f"({changes}):\nEl Niño effect by region, dry-season harvest, Poisson, 95% "
                 "Driscoll–Kraay", fontsize=10, color=INK, loc="left")
    fig.savefig(FIG / f"direct_{crop}_effects.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", choices=list(CROPS), default="rice")
    ap.add_argument("--check", choices=list(CHECKS) + list(SAMPLE_CHECKS))
    ap.add_argument("--break-start", help="start of the measurement-break dummy, e.g. 2023Q3")
    a = ap.parse_args()
    main(crop=a.crop, check=a.check, break_start=a.break_start)
