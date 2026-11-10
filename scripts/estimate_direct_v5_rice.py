"""Direct approach of methodology v5 (Eqs. 4-6) for irrigated and rainfed palay.
PROVISIONAL: base specification of Eq. (4); the choices v5 lists as still being tested
(estimator, season-specific or El Nino / La Nina effects, trend form, lags, pooled vs
regional effects) and the leave-one-episode-out validation (v5 Section 3.6) come next.
The free-lag first look (scripts/estimate_rice_direct.py) is the benchmark v5 asks for.

Specification (src/estimation/direct.py):
- y: quarterly palay production by ecosystem, 16 regions, 1987Q1-2025Q4
  (data/processed/rice_region_quarter.csv);
- RONI and DMI: quarterly means of the monthly values (src/climate/indices.py), lags
  j = 1..4 tied to a binomial profile with one timing parameter each, chosen on the grid
  0.05..0.95 by profile estimation; total effects B^R_r, B^D_r by region;
- region x quarter-of-year effects and one linear trend per region (t in decades);
- controls X_rq: typhoon exposure by PAGASA category (current and previous quarter),
  flood share (current and previous), earthquake, eruption, Pinatubo 1991;
- estimators: Poisson pseudo-ML (levels) and least squares on logs (zero quarters
  dropped); Driscoll-Kraay standard errors conditional on the timing parameters.

National effect: production-weighted mean of the regional B (2016-2025 shares of the
ecosystem's production), as in the aggregation of the regional shocks (v5 Section 3.5).
Implied losses: production relative to a neutral path (RONI = DMI = 0), summed over
regions, for the RONI part and for RONI + DMI.

Run:  python scripts/estimate_direct_v5_rice.py
Writes outputs/tables/direct_v5_rice_*.csv, outputs/figures/direct_v5_rice_effects.png
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
from estimation.direct import binomial_weights, blended, lag_matrix, base_design, estimate  # noqa: E402
from estimation.panel import linear_combination  # noqa: E402
from estimation.setup import break_dummies  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
K = 4
TY = ["ty_share_ts", "ty_share_ty", "ty_share_sty"]
CONTROLS = TY + [f"{c}_lag1" for c in TY] + ["flood_share", "flood_share_lag1",
                                              "eq", "eruption", "pinatubo_1991"]
WEIGHT_YEARS = (2016, 2025)
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"),
            "2023-24": ("2023Q2", "2024Q4")}
STATUS = "provisional"
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#d9d8d4"


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


def index_lags(name, periods):
    q = quarterly(name)
    q.index = q.index.astype(str)
    lm = lag_matrix(q, K).reindex(periods)
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


def implied_losses(d, res, lagsR, lagsD, tR, tD):
    par = res["params"]
    bR = d.region_code.map(lambda r: par.get(f"BR_{r}", 0.0)).to_numpy()
    bD = d.region_code.map(lambda r: par.get(f"BD_{r}", 0.0)).to_numpy()
    eR, eD = bR * blended(lagsR, tR), bD * blended(lagsD, tD)
    a = d.production_t.to_numpy()
    out = pd.DataFrame({"period": d.period, "actual": a, "neutral_roni": a / np.exp(eR),
                        "neutral_roni_dmi": a / np.exp(eR + eD)})
    return out.groupby("period").sum()


def main():
    coef_rows, timing_rows, losses, profiles = [], [], [], []
    for eco in ("irrigated", "rainfed"):
        p = build(eco)
        w = weights(eco)
        for model in ("ppml", "ols"):
            d, y = sample(p, model)
            lagsR, lagsD = index_lags("roni", d.period), index_lags("dmi", d.period)
            base = base_design(d, CONTROLS, break_dummies(d, "palay"))
            r = estimate(d, y, lagsR, lagsD, base, model)
            res, X = r["fit"], r["X"]
            se = pd.Series(res["se"], index=X.columns)
            tag = dict(ecosystem=eco, model=model)
            print(f"{eco:9s} {model}: n={len(d)}, theta_R={r['theta_R']:.2f}, "
                  f"theta_D={r['theta_D']:.2f}, edge={r['on_grid_edge']}, converged={res['converged']}")
            profiles.append(r["profile"].assign(**tag))
            wR, wD = binomial_weights(r["theta_R"], K), binomial_weights(r["theta_D"], K)
            timing_rows.append({**tag, "n": len(d), "theta_R": r["theta_R"], "theta_D": r["theta_D"],
                                "loss": r["profile"].loss.min(), "theta_on_grid_edge": r["on_grid_edge"],
                                **{f"wR_lag{j + 1}": wR[j] for j in range(K)},
                                **{f"wD_lag{j + 1}": wD[j] for j in range(K)}})
            for idx, pre in (("RONI", "BR_"), ("DMI", "BD_")):
                for reg in REGIONS:
                    c = pre + reg
                    if c in X.columns:
                        coef_rows.append({**tag, "term": f"B_{idx}", "region_code": reg,
                                          "est": res["params"][c], "se": se[c]})
                ww = {pre + reg: w.get(reg, 0.0) for reg in REGIONS if pre + reg in X.columns}
                est, s = linear_combination(res, ww)
                coef_rows.append({**tag, "term": f"B_{idx}", "region_code": "national (weighted)",
                                  "est": est, "se": s})
            for c in CONTROLS:
                if c in X.columns:
                    coef_rows.append({**tag, "term": c, "region_code": "all",
                                      "est": res["params"][c], "se": se[c]})
            if model == "ppml":
                losses.append(implied_losses(d, res, lagsR, lagsD, r["theta_R"], r["theta_D"])
                              .assign(ecosystem=eco))

    coef = pd.DataFrame(coef_rows)
    coef["t"] = coef.est / coef.se
    coef["pct_effect_of_+1"] = (np.exp(coef.est) - 1) * 100
    coef.assign(status=STATUS).round(4).to_csv(TAB / "direct_v5_rice_coefficients.csv", index=False)
    timing = pd.DataFrame(timing_rows)
    timing.assign(status=STATUS).round(4).to_csv(TAB / "direct_v5_rice_timing.csv", index=False)
    pd.concat(profiles).round(4).to_csv(TAB / "direct_v5_rice_profile.csv", index=False)

    L = pd.concat(losses).groupby(level=0)[["actual", "neutral_roni", "neutral_roni_dmi"]].sum()
    L["loss_roni_pct"] = (1 - L.actual / L.neutral_roni) * 100
    L["loss_roni_dmi_pct"] = (1 - L.actual / L.neutral_roni_dmi) * 100
    L.index = pd.PeriodIndex(L.index, freq="Q")
    L.assign(status=STATUS).round(2).to_csv(TAB / "direct_v5_rice_implied_losses.csv")
    yr = L.groupby(L.index.year)[["actual", "neutral_roni", "neutral_roni_dmi"]].sum()
    yr["implied_loss_roni_pct"] = (1 - yr.actual / yr.neutral_roni) * 100
    yr["implied_loss_roni_dmi_pct"] = (1 - yr.actual / yr.neutral_roni_dmi) * 100
    yr["actual_change_pct"] = yr.actual.pct_change() * 100

    pd.set_option("display.width", 220, "display.max_rows", 200)
    print("\nTiming:\n", timing.round(3).to_string(index=False))
    nat = coef[coef.region_code == "national (weighted)"]
    print("\nNational total effects (production-weighted B, log points per +1 unit, sustained):")
    print(nat.pivot_table(index=["ecosystem", "term"], columns="model", values=["est", "t"]).round(3).to_string())
    reg = coef[(coef.term == "B_RONI") & (coef.model == "ppml") & (coef.region_code.isin(REGIONS))]
    print("\nRegional B_RONI, Poisson:")
    print(reg.pivot_table(index="region_code", columns="ecosystem", values=["est", "t"]).round(2).to_string())
    print("\nControls:")
    print(coef[coef.region_code == "all"].pivot_table(index=["ecosystem", "term"], columns="model",
                                                      values=["est", "t"]).round(3).to_string())
    print("\nImplied national loss, Poisson, both ecosystems (% of neutral production):")
    for ep, (a, b) in EPISODES.items():
        print(f"  {ep}: " + ", ".join(f"{q}: {v:.1f}%" for q, v in L.loc[a:b, "loss_roni_dmi_pct"].items()))
    print("\nYears:\n", yr.loc[[1997, 1998, 2015, 2016, 2023, 2024],
                               ["implied_loss_roni_pct", "implied_loss_roni_dmi_pct",
                                "actual_change_pct"]].round(1).to_string())

    # figure: regional total effect of RONI, Poisson, with 95% DK intervals
    order = [r for r in REGIONS]
    fig, ax = plt.subplots(figsize=(10, 4.2), constrained_layout=True)
    for j, (eco, col) in enumerate((("irrigated", BLUE), ("rainfed", ORANGE))):
        e = reg[reg.ecosystem == eco].set_index("region_code").reindex(order)
        x = np.arange(len(order)) + (j - 0.5) * 0.25
        ax.errorbar(x, e.est, yerr=1.96 * e.se, fmt="o", ms=5, color=col, capsize=2.5, lw=1.1,
                    label=f"{eco} palay")
        n = nat[(nat.ecosystem == eco) & (nat.model == "ppml") & (nat.term == "B_RONI")].est.iloc[0]
        ax.axhline(n, color=col, lw=0.9, ls="--")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(range(len(order)), order, fontsize=8, rotation=0)
    ax.set_ylabel("B (log points per +1 °C RONI, sustained)", fontsize=8, color=MUTED)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=8, colors=MUTED)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.legend(frameon=False, fontsize=8, title="dashed: national (production-weighted)",
              title_fontsize=7)
    ax.set_title("PROVISIONAL. v5 direct approach (Eq. 4): total effect of RONI by region, "
                 "Poisson, 95% Driscoll–Kraay", fontsize=10, color=INK, loc="left")
    fig.savefig(FIG / "direct_v5_rice_effects.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
