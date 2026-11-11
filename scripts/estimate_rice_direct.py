"""Direct model for rice, FIRST LOOK (unconstrained lags, no constrained lag profile yet).
PROVISIONAL results: first-look (free-lag) specification on the 16 regions of methodology
v5, kept as the benchmark that v5 asks for; the recommended specification is
scripts/estimate_direct_rice.py. The direct model uses RONI, DMI and the hazard controls,
not the ERA5 weather, so the ERA5 cropland weights and island coverage do not affect it.

For each ecosystem (irrigated, rainfed palay), region r, quarter t:
  E[Q_rt] = exp( a_{r,q} + d_{r,q} * t
                 + sum_{k=0..4} sum_{s in dry,wet} 1[season(t)=s] *
                     ( b+_{k,s} RONI+_{t-k} + b-_{k,s} RONI-_{t-k} + c_{k,s} DMI_{t-k} )
                 + typhoon_t + typhoon_{t-1} + flood_t + flood_{t-1}
                 + earthquake_t + eruption_t + pinatubo1991_t )
a_{r,q}: region x quarter effects; d_{r,q}: region x quarter trends; season = harvest
season of quarter t (dry: Q1-Q2, wet: Q3-Q4); RONI+ = max(RONI,0), RONI- = min(RONI,0).
Main: Poisson pseudo-ML (PPML). Check: OLS on log production (zero quarters dropped).
Driscoll-Kraay standard errors throughout. Sample 1987Q1-2025Q4.

Typhoon control (main): exposure by PAGASA category, i.e. the rice-weighted share of the
region with winds of at least tropical-storm / typhoon / super-typhoon strength, current
and previous quarter (Alper's reply, Oct 2026: exposure, not damage, as in Eq. 2).
Robustness: the Emanuel damage index instead, and no hazard controls at all
(outputs/tables/rice_direct_control_compare.csv). Geophysical markers (v5 Eq. 4, X_rq):
earthquake in the quarter (eq), eruption with VEI >= 3 (eruption), Pinatubo 1991.
Measurement breaks come from estimation.setup (none for palay).

Run:  python scripts/estimate_rice_direct.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from climate.indices import lags, quarterly  # noqa: E402
from estimation.panel import fit, linear_combination  # noqa: E402
from estimation.setup import break_dummies  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
K = 4
SEASONS = {1: "dry", 2: "dry", 3: "wet", 4: "wet"}
TY_CATS = ["ty_share_ts", "ty_share_ty", "ty_share_sty"]
FLOOD = ["flood_share", "flood_share_lag1"]
GEO = ["eq", "eruption", "pinatubo_1991"]
CONTROL_SETS = {
    "category": TY_CATS + [f"{c}_lag1" for c in TY_CATS] + FLOOD + GEO,  # main
    "damage_index": ["damage_index", "damage_index_lag1"] + FLOOD + GEO,
    "none": [],
}
STATUS = "provisional"
CONTROLS = CONTROL_SETS["category"]
TY_COLS = sorted({c for v in CONTROL_SETS.values() for c in v} - set(FLOOD) - set(GEO))
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"),
            "2023-24": ("2023Q2", "2024Q4")}
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"


def climate_terms():
    roni = lags(quarterly("roni"), K, split_sign=True)
    dmi = lags(quarterly("dmi"), K, split_sign=False)
    c = roni.join(dmi)
    c.index = c.index.astype(str)
    return c


def build(ecosystem):
    p = pd.read_csv(PROC / "rice_region_quarter.csv")
    p = p[p.ecosystem == ecosystem].copy()
    ty = pd.read_csv(PROC / "typhoon_region_quarter.csv")
    fl = pd.read_csv(PROC / "flood_region_quarter.csv")
    keys = ["ecosystem", "region_code", "period"]
    p = (p.merge(ty[keys + TY_COLS], on=keys)
          .merge(fl[keys + ["flood_share", "flood_share_lag1"]], on=keys))
    geo = pd.read_csv(PROC / "geophysical_region_quarter.csv")
    p = p.merge(geo[["region_code", "period"] + GEO], on=["region_code", "period"], how="left")
    p[GEO] = p[GEO].fillna(0)
    c = climate_terms()
    p = p.merge(c, left_on="period", right_index=True)
    per = pd.PeriodIndex(p.period, freq="Q")
    p["q"] = per.quarter
    p["season"] = p.q.map(SEASONS)
    p["t"] = (per.year + (per.quarter - 1) / 4 - 2006) / 10  # decades, centred
    return p.reset_index(drop=True), list(c.columns)


def design(p, clim_cols, controls=CONTROLS):
    rq = p.region_code + "_q" + p.q.astype(str)
    fe = pd.get_dummies(rq, prefix="fe", dtype=float)
    tr = fe.mul(p.t, axis=0).add_prefix("tr_")
    clim = {}
    for s in ("dry", "wet"):
        d = (p.season == s).astype(float)
        for c in clim_cols:
            clim[f"{c}_{s}"] = p[c] * d
    X = pd.concat([pd.DataFrame(clim), p[controls], break_dummies(p, "palay"), fe, tr], axis=1)
    return X


def cumulative(res, sign, season):
    names = [f"roni_{sign}_l{k}_{season}" for k in range(K + 1)]
    return linear_combination(res, {n: 1.0 for n in names})


def implied_losses(p, res, label):
    """National El Nino loss share per quarter: counterfactual without the El Nino part."""
    out = []
    for s in ("dry", "wet"):
        m = p.season == s
        ep = sum(res["params"][f"roni_pos_l{k}_{s}"] * p.loc[m, f"roni_pos_l{k}"]
                 for k in range(K + 1))
        out.append(pd.DataFrame({"period": p.loc[m, "period"], "actual": p.loc[m, "production_t"],
                                 "cf": p.loc[m, "production_t"] / np.exp(ep)}))
    d = pd.concat(out)
    return d.groupby("period")[["actual", "cf"]].sum().assign(model=label)


def sample(p, model):
    """PPML: drop region x quarter cells that are always zero (no harvest that quarter).
    OLS on logs: drop zero quarters."""
    if model == "ppml":
        cell = p.region_code + p.q.astype(str)
        d = p[p.groupby(cell).production_t.transform("sum") > 0]
        return d, d.production_t / 1000
    d = p[p.production_t > 0]
    return d, np.log(d.production_t)


def estimate(d, y, clim_cols, model, controls=CONTROLS):
    X = design(d, clim_cols, controls)
    X = X.loc[:, X.abs().sum() > 0]
    return fit(y, X, d.period, model), X


def compare_controls():
    """El Nino / La Nina cumulative effects under each set of typhoon/flood controls."""
    rows = []
    for eco in ("irrigated", "rainfed"):
        p, clim_cols = build(eco)
        for model in ("ppml", "ols"):
            d, y = sample(p, model)
            for name, controls in CONTROL_SETS.items():
                r, _ = estimate(d, y, clim_cols, model, controls)
                for s in ("dry", "wet"):
                    for sign, term in (("pos", "El Nino"), ("neg", "La Nina")):
                        est, se = cumulative(r, sign, s)
                        rows.append(dict(ecosystem=eco, model=model, season=s, term=term,
                                         controls=name, est=est, se=se))
    t = pd.DataFrame(rows)
    t.assign(status=STATUS).round(4).to_csv(TAB / "rice_direct_control_compare.csv", index=False)
    print("\nEl Nino / La Nina, sum of lags 0-4, by control set:")
    print(t.pivot_table(index=["ecosystem", "model", "term", "season"], columns="controls",
                        values="est")[list(CONTROL_SETS)].round(3).to_string())


def main():
    rows, losses, profiles, ac = [], [], [], []
    for eco in ("irrigated", "rainfed"):
        p, clim_cols = build(eco)
        for model in ("ppml", "ols"):
            d, y = sample(p, model)
            r, X = estimate(d, y, clim_cols, model)
            tag = f"{eco}, {'Poisson' if model == 'ppml' else 'log OLS'}"
            print(f"{tag}: n={len(d)}, converged={r['converged']}")
            for s in ("dry", "wet"):
                for sign in ("pos", "neg"):
                    est, se = cumulative(r, sign, s)
                    rows.append(dict(ecosystem=eco, model=model, season=s,
                                     term="El Nino (sum of lags 0-4)" if sign == "pos"
                                     else "La Nina (sum of lags 0-4)", est=est, se=se))
                est, se = linear_combination(r, {f"dmi_l{k}_{s}": 1.0 for k in range(K + 1)})
                rows.append(dict(ecosystem=eco, model=model, season=s,
                                 term="DMI (sum of lags 0-4)", est=est, se=se))
                for k in range(K + 1):
                    n = f"roni_pos_l{k}_{s}"
                    profiles.append(dict(ecosystem=eco, model=model, season=s, lag=k,
                                         est=r["params"][n], se=r["se"][X.columns.get_loc(n)]))
            for c in CONTROLS:
                rows.append(dict(ecosystem=eco, model=model, season="all", term=c,
                                 est=r["params"][c], se=r["se"][X.columns.get_loc(c)]))
            # residual autocorrelation (within region-ecosystem, quarter to quarter)
            e = pd.DataFrame({"g": d.region_code.values, "per": d.period.values,
                              "e": r["resid"].values}).sort_values(["g", "per"])
            e["e1"] = e.groupby("g").e.shift(1)
            ac.append(dict(ecosystem=eco, model=model, ar1=round(e.e.corr(e.e1), 3),
                           ar4=round(e.e.corr(e.groupby("g").e.shift(4)), 3)))
            if model == "ppml":
                losses.append(implied_losses(d, r, eco))

    tab = pd.DataFrame(rows)
    tab["t"] = tab.est / tab.se
    tab["pct_effect_of_+1C"] = (np.exp(tab.est) - 1) * 100
    tab.assign(status=STATUS).round(4).to_csv(TAB / "rice_direct_first_look.csv", index=False)
    prof = pd.DataFrame(profiles)
    prof.assign(status=STATUS).round(4).to_csv(TAB / "rice_direct_lag_profile.csv", index=False)

    pd.set_option("display.width", 200, "display.max_rows", 100)
    show = tab[tab.term.str.startswith(("El", "La", "DMI"))].pivot_table(
        index=["ecosystem", "term", "season"], columns="model", values=["est", "t"])
    print("\nCumulative effects (log points per +1 C index, held 5 quarters):")
    print(show.round(3).to_string())
    print("\nControls:")
    print(tab[tab.season == "all"].pivot_table(index=["ecosystem", "term"], columns="model",
                                                 values=["est", "t"]).round(3).to_string())
    print("\nResidual autocorrelation:", pd.DataFrame(ac).to_string(index=False))

    # implied national El Nino loss (Poisson, both ecosystems), by quarter and year
    L = pd.concat(losses).groupby("period")[["actual", "cf"]].sum()
    L["loss_pct"] = (1 - L.actual / L.cf) * 100
    L.index = pd.PeriodIndex(L.index, freq="Q")
    yr = L.groupby(L.index.year)[["actual", "cf"]].sum()
    yr["implied_loss_pct"] = (1 - yr.actual / yr.cf) * 100
    yr["actual_change_pct"] = yr.actual.pct_change() * 100
    L.assign(status=STATUS).round(2).to_csv(TAB / "rice_direct_implied_losses.csv")
    print("\nImplied national El Nino loss, Poisson (% of production without El Nino):")
    for ep, (a, b) in EPISODES.items():
        print(f"  {ep}: " + ", ".join(f"{q}: {v:.1f}%" for q, v in
                                      L.loc[a:b, "loss_pct"].items()))
    print("\nYears:", yr.loc[[1997, 1998, 2015, 2016, 2023, 2024],
                             ["implied_loss_pct", "actual_change_pct"]].round(1).to_string())

    # figure: El Nino lag coefficients by ecosystem and season (Poisson)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True, constrained_layout=True)
    for ax, eco in zip(axes, ("irrigated", "rainfed")):
        for j, (s, col) in enumerate((("dry", ORANGE), ("wet", BLUE))):
            e = prof[(prof.ecosystem == eco) & (prof.model == "ppml") & (prof.season == s)]
            x = e.lag + (j - 0.5) * 0.18
            ax.errorbar(x, e.est, yerr=1.96 * e.se, fmt="o", ms=5, color=col, capsize=3,
                        lw=1.2, label=f"{s}-season harvest (Q{'1–Q2' if s == 'dry' else '3–Q4'})")
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_title(f"{eco.capitalize()} palay", fontsize=10, color=INK, loc="left")
        ax.set_xticks(range(K + 1))
        ax.set_xlabel("lag of RONI (quarters)", fontsize=8, color=MUTED)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=8, colors=MUTED)
        ax.grid(axis="y", color="#d9d8d4", lw=0.5)
    axes[0].set_ylabel("effect of +1 °C El Niño on log production", fontsize=8, color=MUTED)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("PROVISIONAL. Direct model, first look, 16 regions: El Niño lag coefficients "
                 "(Poisson, 95% Driscoll–Kraay)",
                 fontsize=10, color=INK)
    fig.savefig(FIG / "rice_direct_lag_profile.png", dpi=150, facecolor="white")
    plt.close(fig)

    compare_controls()


if __name__ == "__main__":
    main()
