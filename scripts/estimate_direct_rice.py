"""Direct approach for irrigated and rainfed palay: RECOMMENDED specification.
PROVISIONAL results.

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

Run:  python scripts/estimate_direct_rice.py
Writes outputs/tables/direct_rice_{coefficients,national_effects,timing,profile,
implied_losses}.csv and outputs/figures/direct_rice_effects.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agriculture.regions import REGIONS  # noqa: E402
from climate.indices import quarterly  # noqa: E402
from estimation.direct import (Spec, base_design, binomial_weights, estimate,  # noqa: E402
                               is_climate, is_roni, lag_matrix, national_effect)
from estimation.setup import break_dummies  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
K = 4
# differs from v5 (log B1-B3); recommended because the data support it
RECOMMENDED = Spec("recommended", split=True, season=True, trend="region_spline", effect_break=2000)
SPEC_NOTE = "recommended; differs from methodology v5 (change log B1-B3)"
TY = ["ty_share_ts", "ty_share_ty", "ty_share_sty"]
CONTROLS = TY + [f"{c}_lag1" for c in TY] + ["flood_share", "flood_share_lag1",
                                              "eq", "eruption", "pinatubo_1991"]
WEIGHT_YEARS = (2016, 2025)
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"),
            "2023-24": ("2023Q2", "2024Q4")}
STATUS = "provisional"
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#d9d8d4"
INDEX_NAME = {"RP": "El Nino (RONI+)", "RN": "La Nina (RONI-)", "D": "DMI"}


def build(ecosystem):
    p = pd.read_csv(PROC / "rice_region_quarter.csv")
    p = p[p.ecosystem == ecosystem].copy()
    keys = ["ecosystem", "region_code", "period"]
    ty = pd.read_csv(PROC / "typhoon_region_quarter.csv")
    fl = pd.read_csv(PROC / "flood_region_quarter.csv")
    geo = pd.read_csv(PROC / "geophysical_region_quarter.csv")
    p = (p.merge(ty[keys + TY + [f"{c}_lag1" for c in TY]], on=keys)
          .merge(fl[keys + ["flood_share", "flood_share_lag1"]], on=keys)
          .merge(geo, on=["region_code", "period"], how="left"))
    p[["eq", "eruption", "pinatubo_1991"]] = p[["eq", "eruption", "pinatubo_1991"]].fillna(0)
    per = pd.PeriodIndex(p.period, freq="Q")
    p["q"] = per.quarter
    p["t"] = (per.year + (per.quarter - 1) / 4 - 2006) / 10  # decades, centred
    return p.reset_index(drop=True)


def index_lags(name, periods, K=K, first_lag=1):
    q = quarterly(name)
    q.index = q.index.astype(str)
    lm = lag_matrix(q, K, first_lag).reindex(periods)
    if lm.isna().any().any():
        raise ValueError(f"{name}: missing lagged values")
    return lm.to_numpy(float)


def sample(p, model):
    if model == "ppml":
        cell = p.region_code + p.q.astype(str)
        d = p[p.groupby(cell).production_t.transform("sum") > 0]
        return d.reset_index(drop=True), (d.production_t / 1000).reset_index(drop=True)
    d = p[p.production_t > 0].reset_index(drop=True)
    return d, np.log(d.production_t)


def weights(ecosystem):
    p = pd.read_csv(PROC / "rice_region_quarter.csv")
    p = p[(p.ecosystem == ecosystem) & p.period.str[:4].astype(int).between(*WEIGHT_YEARS)]
    w = p.groupby("region_code").production_t.sum()
    return w / w.sum()


def implied_losses(d, X, b):
    clim = [c for c in X.columns if is_climate(c)]
    roni = [c for c in clim if is_roni(c)]
    eR = X[roni].to_numpy(float) @ b[roni].to_numpy()
    eA = X[clim].to_numpy(float) @ b[clim].to_numpy()
    a = d.production_t.to_numpy()
    out = pd.DataFrame({"period": d.period, "actual": a, "neutral_roni": a / np.exp(eR),
                        "neutral_roni_dmi": a / np.exp(eA)})
    return out.groupby("period").sum()


def main(spec=RECOMMENDED):
    coef_rows, nat_rows, timing_rows, losses, profiles = [], [], [], [], []
    for eco in ("irrigated", "rainfed"):
        p = build(eco)
        w = weights(eco)
        for model in ("ppml", "ols"):
            d, y = sample(p, model)
            lagsR, lagsD = index_lags("roni", d.period), index_lags("dmi", d.period)
            base = base_design(d, CONTROLS, break_dummies(d, "palay"), spec.trend)
            r = estimate(d, y, lagsR, lagsD, base, model, spec)
            res, X = r["fit"], r["X"]
            se = pd.Series(res["se"], index=X.columns)
            tag = dict(ecosystem=eco, model=model)
            print(f"{eco:9s} {model}: n={len(d)}, theta_R={r['theta_R']:.2f}, "
                  f"theta_D={r['theta_D']:.2f}, edge={r['on_grid_edge']}, converged={res['converged']}")
            profiles.append(r["profile"].assign(**tag))
            wR, wD = binomial_weights(r["theta_R"], K), binomial_weights(r["theta_D"], K)
            timing_rows.append({**tag, "n": len(d), "k": r["k"], "theta_R": r["theta_R"],
                                "theta_D": r["theta_D"], "loss": r["loss"],
                                "theta_on_grid_edge": r["on_grid_edge"],
                                **{f"wR_lag{j + 1}": wR[j] for j in range(K)},
                                **{f"wD_lag{j + 1}": wD[j] for j in range(K)}})
            for c in X.columns:
                if is_climate(c) or c in CONTROLS:
                    kind = "climate" if is_climate(c) else "control"
                    coef_rows.append({**tag, "kind": kind, "term": c, "est": res["params"][c],
                                      "se": se[c]})
            for idx in ("RP", "RN", "D"):
                for wet in (False, True):
                    for post in ((False, True) if idx != "D" else (False,)):
                        est, s = national_effect(res, X, w, idx, spec, wet=wet, post=post)
                        nat_rows.append({**tag, "index": INDEX_NAME[idx],
                                         "harvest_season": "wet (Q3-Q4)" if wet else "dry (Q1-Q2)",
                                         "period": ("from 2000" if post else "before 2000")
                                         if idx != "D" else "all",
                                         "est": est, "se": s})
            if model == "ppml":
                losses.append(implied_losses(d, X, res["params"]).assign(ecosystem=eco))

    coef = pd.DataFrame(coef_rows)
    coef["t"] = coef.est / coef.se
    coef.assign(spec=spec.name, spec_note=SPEC_NOTE, status=STATUS).round(4).to_csv(TAB / "direct_rice_coefficients.csv",
                                                               index=False)
    nat = pd.DataFrame(nat_rows)
    nat["t"] = nat.est / nat.se
    nat["pct_effect_of_+1"] = (np.exp(nat.est) - 1) * 100
    nat.assign(spec=spec.name, spec_note=SPEC_NOTE, status=STATUS).round(4).to_csv(TAB / "direct_rice_national_effects.csv",
                                                              index=False)
    timing = pd.DataFrame(timing_rows)
    timing.assign(spec=spec.name, spec_note=SPEC_NOTE, status=STATUS).round(4).to_csv(TAB / "direct_rice_timing.csv",
                                                                 index=False)
    pd.concat(profiles).round(4).to_csv(TAB / "direct_rice_profile.csv", index=False)

    L = pd.concat(losses).groupby(level=0)[["actual", "neutral_roni", "neutral_roni_dmi"]].sum()
    L["loss_roni_pct"] = (1 - L.actual / L.neutral_roni) * 100
    L["loss_roni_dmi_pct"] = (1 - L.actual / L.neutral_roni_dmi) * 100
    L.index = pd.PeriodIndex(L.index, freq="Q")
    L.assign(spec=spec.name, spec_note=SPEC_NOTE, status=STATUS).round(2).to_csv(TAB / "direct_rice_implied_losses.csv")
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
    print("\nImplied national loss, Poisson, both ecosystems (% of neutral production):")
    for ep, (a, b) in EPISODES.items():
        print(f"  {ep}: " + ", ".join(f"{q}: {v:.1f}%" for q, v in L.loc[a:b, "loss_roni_dmi_pct"].items()))
    print("\nYears:\n", yr.loc[[1997, 1998, 2015, 2016, 2023, 2024],
                               ["implied_loss_roni_pct", "implied_loss_roni_dmi_pct",
                                "actual_change_pct"]].round(1).to_string())

    # figure: regional El Nino effect (dry-season harvest, from 2000 = regional B + shift)
    reg = coef[(coef.model == "ppml") & coef.term.str.startswith("BRP_")].copy()
    reg["region_code"] = reg.term.str[4:]
    fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
    for j, (eco, col) in enumerate((("irrigated", BLUE), ("rainfed", ORANGE))):
        e = reg[reg.ecosystem == eco].set_index("region_code").reindex(list(REGIONS))
        x = np.arange(len(REGIONS)) + (j - 0.5) * 0.25
        ax.errorbar(x, e.est, yerr=1.96 * e.se, fmt="o", ms=5, color=col, capsize=2.5, lw=1.1,
                    label=f"{eco} palay, before 2000")
        for per, ls in (("before 2000", "--"), ("from 2000", ":")):
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
    ax.legend(frameon=False, fontsize=8,
              title="lines: national, dashed before 2000, dotted from 2000", title_fontsize=7)
    ax.set_title("PROVISIONAL. Recommended specification, differs from v5 (El Niño / La Niña split, "
                 "spline trends, change from 2000):\nEl Niño effect by region, dry-season harvest, "
                 "Poisson, 95% Driscoll–Kraay", fontsize=10, color=INK, loc="left")
    fig.savefig(FIG / "direct_rice_effects.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
