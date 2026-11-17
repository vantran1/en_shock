"""El Nino shocks from the direct approach (methodology v5 Section 3.5) for a crop, with
its recommended specification in scripts/estimate_direct.py (differs from v5: El Nino /
La Nina split, spline trends, wet-season shift; for rice also the effect change from 2000).
PROVISIONAL.

Crops: rice = irrigated and rainfed palay, combined into palay with neutral production
shares; corn = total corn (the corn shock), with white and yellow corn reported
separately and combined (white + yellow) as a consistency check. Corn includes the
Region VI measurement-break dummy (estimation.setup), which describes today's level.
vr / pf = the calorie indices of vegetables and root crops and of perennial fruits (data
from 2010), with the indices without root crops, without banana and without Cavendish
reported as checks (methodology v5 Section 3.2).

Shocks (src/estimation/shocks.py): share of production lost against the neutral path
(RONI = DMI = 0), controls at "no event" in both runs, today's conditions (the effect
after 2000; neutral production at t* = 2025). By region (Eq. 13), national with neutral
production shares (Eq. 13a), palay = irrigated + rainfed with their neutral production
shares, and seasonally scaled for DEFINE-PH (Eq. 13b). Delivered for the quarters of the
path and the 4 quarters after it.

Paths: RONI and DMI of the quarters with RONI >= 0.5 in the three strong episodes
(1997Q2-1998Q1, 2015Q2-2016Q1, 2023Q3-2024Q1), replayed under today's conditions, and a
unit path (RONI +1 for four quarters from Q3, DMI 0) as a sensitivity.

Central estimate: Poisson on the full sample (timing on the 0.05 grid). Range (v5: "the
90 percent confidence interval of the direct approach"): block bootstrap over years
(whole years, all regions, irrigated and rainfed drawn together), re-estimating the
timing parameters on a 0.10 grid in each replication; 5th and 95th percentiles.
Log-LS central shocks are reported as a check.

RONI only since 16 Nov 2026 (estimate_direct.RECOMMENDED_BY_CROP); the paths' DMI is then
not used. --with-dmi: the variant with the DMI (v5 Eq. 4 as written); outputs end in
_with_dmi.

Run:  python scripts/shocks_direct.py --crop rice|corn|vr|pf [--reps 200] [--with-dmi]
Writes outputs/tables/shocks_<crop>.csv (national), shocks_<crop>_regional.csv (central,
by region), shocks_<crop>_bootstrap.csv (draws), shocks_<crop>_episode_totals.csv (total
loss over each scenario, % of a year's production), outputs/figures/shocks_<crop>.png
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import argparse  # noqa: E402
from dataclasses import replace  # noqa: E402
import sys  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

import estimate_direct as m  # noqa: E402
from agriculture.regions import REGIONS  # noqa: E402
from climate.indices import quarterly  # noqa: E402
from estimation.direct import THETA_GRID, base_design, climate_design, profile  # noqa: E402
from estimation.setup import break_dummies  # noqa: E402
from estimation.shocks import (aggregate, combine, neutral_production,  # noqa: E402
                               regional_shocks, seasonal_scaling)

TAB, FIG = ROOT / "outputs/tables", ROOT / "outputs/figures"
CONF = {"rice": {"series": ["irrigated", "rainfed"], "main": "palay",
                 "combine": ("palay", ["irrigated", "rainfed"]), "dashed": ["irrigated", "rainfed"]},
        "corn": {"series": ["corn", "corn_white", "corn_yellow"], "main": "corn",
                 "combine": ("white + yellow", ["corn_white", "corn_yellow"]),
                 "dashed": ["corn_white", "corn_yellow"]},
        "vr": {"series": ["vr", "vr_noroot"], "main": "vr", "combine": None,
               "dashed": ["vr_noroot"]},
        "pf": {"series": ["pf", "pf_nobanana", "pf_nocavendish"], "main": "pf", "combine": None,
               "dashed": ["pf_nobanana", "pf_nocavendish"]}}
DASHED_LABEL = {"corn_white": "white", "corn_yellow": "yellow", "vr_noroot": "VR without root crops",
                "pf_nobanana": "PF without banana", "pf_nocavendish": "PF without Cavendish"}
LABEL = {"rice": "palay", "corn": "corn", "vr": "vegetables and root crops (VR)",
         "pf": "perennial fruits (PF)"}
BOOT_GRID = np.round(np.arange(0.05, 0.951, 0.10), 2)
EPISODE_PATHS = {"1997-98": ("1997Q2", "1998Q1"), "2015-16": ("2015Q2", "2016Q1"),
                 "2023-24": ("2023Q3", "2024Q1")}
WORKERS = 8


def paths():
    idx = pd.DataFrame({"roni": quarterly("roni"), "dmi": quarterly("dmi")})
    out = {name: idx.loc[pd.Period(a, "Q"):pd.Period(b, "Q")] for name, (a, b) in EPISODE_PATHS.items()}
    unit = pd.period_range("2001Q3", periods=4, freq="Q")
    out["unit RONI +1 (4 quarters from Q3)"] = pd.DataFrame({"roni": 1.0, "dmi": 0.0}, index=unit)
    return out


def prepare(eco, spec, model="ppml"):
    p = m.build(eco)
    d, y = m.sample(p, model, m.GROUP[eco])
    LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
    LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
    base = base_design(d, m.CONTROLS, break_dummies(d, m.GROUP[eco]), spec.trend)
    return d, y.to_numpy(float), LR, LD, base


def fit_params(d, y, LR, LD, base, model, grid, spec):
    """Profile the timing on `grid`, then fit; returns params (Series) and thetas.
    Columns that are all zero in the sample (e.g. the Pinatubo marker in a bootstrap draw
    without 1991) are dropped first."""
    base = base.loc[:, base.abs().sum() > 0]
    prof = profile(d, y, LR, LD, base, model, spec, grid)
    best = prof.loc[prof.loss.idxmin()]
    tR, tD = float(best.theta_R), float(best.theta_D)
    X = pd.concat([climate_design(d, LR, LD, tR, tD, spec), base], axis=1)
    X = X.loc[:, X.abs().sum() > 0]
    if model == "ppml":
        res = sm.GLM(y, X.to_numpy(float), family=sm.families.Poisson()).fit(maxiter=200, tol=1e-10)
    else:
        res = sm.OLS(y, X.to_numpy(float)).fit()
    return pd.Series(res.params, index=X.columns), tR, tD


def shocks(fits, data, crop, spec, path_set=None):
    """fits: series -> (params, tR, tD); data: series -> (d, y, LR, LD, base) on the full
    sample; path_set: name -> path (default paths()). Returns national shocks by path,
    scenario quarter and series (plus the combined series of CONF) and the central regional
    shocks."""
    rows, regs = [], []
    for name, path in (path_set or paths()).items():
        nats, y0q = {}, {}
        for eco in CONF[crop]["series"]:
            params, tR, tD = fits[eco]
            d, y, LR, LD, base = data[eco]
            reg = regional_shocks(params, spec, tR, tD, path, list(REGIONS), spec.K)
            X = pd.concat([climate_design(d, LR, LD, tR, tD, spec), base], axis=1)
            y0 = neutral_production(params, X, d, m.CONTROLS)
            nat = aggregate(reg, y0)
            y0q[eco] = y0.groupby(level="q").sum()
            nat["S_D"] = seasonal_scaling(nat, y0q[eco])
            nats[eco] = nat
            regs.append(reg.assign(path=name, crop=eco))
        if CONF[crop]["combine"]:
            cname, parts = CONF[crop]["combine"]
            comb = combine({k: nats[k] for k in parts})
            comb["S_D"] = seasonal_scaling(comb, sum(y0q[k] for k in parts))
            nats[cname] = comb
        for series, nat in nats.items():
            rows.append(nat.assign(path=name, crop=series, path_start=path.index.min(),
                                   path_end=path.index.max()))
    out = pd.concat(rows, ignore_index=True)
    out["step"] = [(q - s).n for q, s in zip(out.scenario_q, out.path_start)]
    out["in_path"] = out.scenario_q <= out.path_end
    return out.drop(columns=["path_start", "path_end"]), pd.concat(regs, ignore_index=True)


def episode_totals(out, draws):
    """Total loss over each scenario (path + 4 quarters) in % of one year's neutral
    production: sum of S^D (Eq. 13b) / 4, central and bootstrap 5th-95th percentiles, and
    the share of draws with a loss."""
    cen = out.groupby(["path", "crop"]).S_D.sum() / 4 * 100
    tot = draws.groupby(["path", "crop", "rep"]).S_D.sum() / 4 * 100
    q = tot.groupby(["path", "crop"]).quantile([0.05, 0.95]).unstack()
    t = pd.concat([cen.rename("total_loss_pct_of_annual"),
                   q.rename(columns={0.05: "p05", 0.95: "p95"}),
                   (tot > 0).groupby(["path", "crop"]).mean().mul(100).rename("share_of_draws_with_loss_pct")],
                  axis=1)
    return t.reset_index()


def spec_of(crop, dmi=False):
    spec = m.RECOMMENDED_BY_CROP[crop]
    return m.with_dmi(spec) if dmi else spec


def boot(job):
    rep, crop, dmi = job
    spec = spec_of(crop, dmi)
    rng = np.random.default_rng(1000 + rep)
    data = {eco: prepare(eco, spec) for eco in CONF[crop]["series"]}
    first = min(int(data[e][0].period.str[:4].min()) for e in CONF[crop]["series"])
    years = np.arange(first, 2026)
    draw = rng.choice(years, size=len(years), replace=True)
    fits = {}
    for eco in CONF[crop]["series"]:
        d, y, LR, LD, base = data[eco]
        yr = d.period.str[:4].astype(int).to_numpy()
        idx = np.concatenate([np.flatnonzero(yr == v) for v in draw])
        db = d.iloc[idx].reset_index(drop=True)
        fits[eco] = fit_params(db, y[idx], LR[idx], LD[idx], base.iloc[idx].reset_index(drop=True),
                               "ppml", BOOT_GRID, spec)
    nat, _ = shocks(fits, data, crop, spec)
    return nat.assign(rep=rep, **{f"theta_R_{e}": fits[e][1] for e in CONF[crop]["series"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crop", choices=list(CONF), default="rice")
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--with-dmi", action="store_true")
    args = ap.parse_args()
    crop = args.crop
    dmi = args.with_dmi
    spec = spec_of(crop, dmi)
    sfx = "_with_dmi" if dmi else ""
    series = CONF[crop]["series"]
    data = {eco: prepare(eco, spec) for eco in series}
    central = {eco: fit_params(*data[eco], "ppml", THETA_GRID, spec) for eco in series}
    nat, reg = shocks(central, data, crop, spec)
    ols_data = {eco: prepare(eco, spec, "ols") for eco in series}
    ols = {eco: fit_params(*ols_data[eco], "ols", THETA_GRID, spec) for eco in series}
    nat_ols, _ = shocks(ols, ols_data, crop, spec)
    print("central thetas (Poisson):", {e: central[e][1:] for e in series})

    with ProcessPoolExecutor(WORKERS) as ex:
        draws = pd.concat(list(ex.map(boot, [(r, crop, dmi) for r in range(args.reps)])), ignore_index=True)
    draws.round(6).to_csv(TAB / f"shocks_{crop}_bootstrap{sfx}.csv", index=False)
    key = ["path", "crop", "scenario_q"]
    q = draws.groupby(key).agg(S_p05=("S", lambda s: s.quantile(0.05)),
                               S_p95=("S", lambda s: s.quantile(0.95)),
                               S_D_p05=("S_D", lambda s: s.quantile(0.05)),
                               S_D_p95=("S_D", lambda s: s.quantile(0.95))).reset_index()
    out = (nat.merge(q, on=key)
              .merge(nat_ols[key + ["S", "S_D"]].rename(columns={"S": "S_logLS_check",
                                                                  "S_D": "S_D_logLS_check"}), on=key))
    out = out[["path", "crop", "scenario_q", "q", "step", "in_path", "S", "S_p05", "S_p95",
               "S_D", "S_D_p05", "S_D_p95", "S_logLS_check", "S_D_logLS_check"]]
    note = "recommended spec, differs from methodology v5; provisional" + ("; with the DMI (variant)" if dmi else "; RONI only")
    out.assign(reps=args.reps, spec_note=note).round(5).to_csv(TAB / f"shocks_{crop}{sfx}.csv", index=False)
    reg.assign(spec_note=note).round(5).to_csv(TAB / f"shocks_{crop}_regional{sfx}.csv", index=False)
    episode_totals(out, draws).assign(spec_note=note).round(2).to_csv(
        TAB / f"shocks_{crop}_episode_totals{sfx}.csv", index=False)

    pd.set_option("display.width", 220, "display.max_rows", 200)
    main_series = CONF[crop]["main"]
    show = out[out.crop == main_series].copy()
    for c in ("S", "S_p05", "S_p95", "S_D", "S_D_p05", "S_D_p95", "S_logLS_check"):
        show[c] = (show[c] * 100).round(1)
    print(f"\n{main_series} shock, % of neutral production (S, Eq. 13a) and scaled for DEFINE-PH (S_D, Eq. 13b):")
    print(show.drop(columns=["crop", "S_D_logLS_check"]).to_string(index=False))

    if not dmi:
        plot(out, crop)

def plot(out, crop):
    """Main shock (Eq. 13a) by path with the 90% bootstrap range, 2 x 2 panels; dashed: the
    component series (irrigated and rainfed palay; white and yellow corn) or the checks
    (VR without root crops; PF without banana, without Cavendish)."""
    main_series = CONF[crop]["main"]
    parts = CONF[crop]["dashed"]
    label = LABEL[crop]
    names = list(dict.fromkeys(out.path))
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.2), sharey=True, constrained_layout=True)
    for ax, name in zip(axes.flat, names):
        e = out[(out.path == name) & (out.crop == main_series)]
        ax.fill_between(e.step, e.S_p05 * 100, e.S_p95 * 100, color="#b7d3f6", lw=0,
                        label=f"{label}, 90% range (bootstrap)")
        ax.plot(e.step, e.S * 100, color="#2a78d6", lw=2, marker="o", ms=4, label=f"{label} (central)")
        for eco, col in zip(parts, ("#0d366b", "#eb6834")):
            f = out[(out.path == name) & (out.crop == eco)]
            ax.plot(f.step, f.S * 100, color=col, lw=1, ls="--", label=DASHED_LABEL.get(eco, eco))
        ax.axhline(0, color="#52514e", lw=0.8)
        last = e[e.in_path].step.max()
        ax.axvspan(-0.5, last + 0.5, color="#e6e5e1", lw=0, zorder=0)
        labels = [f"+{v}" for v in e.step] if name.startswith("unit") else [str(v) for v in e.scenario_q]
        ax.set_xticks(e.step, labels, fontsize=8, rotation=45)
        ax.set_title(name, fontsize=10, color="#0b0b0b", loc="left")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=8, colors="#52514e")
        ax.grid(axis="y", color="#d9d8d4", lw=0.5)
    for ax in axes[:, 0]:
        ax.set_ylabel("share of the quarter's production lost (%)", fontsize=8, color="#52514e")
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"PROVISIONAL. El Niño shock to {label} under today's conditions (recommended "
                 "specification, differs from v5)\nshaded: quarters of the path", fontsize=10,
                 color="#0b0b0b")
    fig.savefig(FIG / f"shocks_{crop}.png", dpi=150, facecolor="white")
    plt.close(fig)

if __name__ == "__main__":
    main()
