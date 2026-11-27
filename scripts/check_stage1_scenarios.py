"""Check of Van's Stage-1 simulations on the El Nino scenario paths (dev_Van 40db708, 27 Nov 2026, fixed 6-month lag; before that f6ddf65, the
re-run with the complete hourly record, copied to data/reference/van/f6ddf65/scenarios/; earlier versions
with --van 30cc20c or --van af5e28f), before they are chained with Stage 2 (methodology v5
Section 3.5). A check, not a result.

Checks
1. Structure: paths, draws, months, regions, missing values; months against Van's README.
2. Path: Van's RONI (path.csv) against ours (outputs/stage1_paths/path_*.csv), month by month.
3. Same residuals in both runs: within a draw, the scenario and the neutral path use the same
   historical month (hist_date) in every region and month (v5: the difference reflects only
   ENSO).
4. Neutral path: the deterministic neutral weather depends only on the calendar month (today's
   climate, trend at t* = 2026), so it should be the same in every scenario and every year.
5. Van's effects table: recomputed from the draws (mean of scenario - neutral; deterministic
   difference).
6. Size and timing of the effects: palay-weighted national effect by month (mean and 10th-90th
   percentiles over the draws) for T, P, SM_RZ, VPD; effects after the El Nino months should
   fade within the 6 months of the longest Stage-1 lag.
7. Growing windows: harvest quarters whose window reaches before the first month of the tables
   (af5e28f dropped the 6 leading zero months; 30cc20c keeps them).
7b. Leading zero months exactly neutral: scenario = neutral in every draw before the first El Nino
   month (30cc20c sets the observed lead-in to zero so nothing leaks in through the lags).
9. Residual years: the historical years drawn (30cc20c drops the years without hourly data).
8. Range: share of simulated region-months (scenario path) outside the range observed in the
   production period (1987-2025) for that region and calendar month: a first look at v5's
   reliability flag, which will be applied to the window features in the chain.

Run:  python scripts/check_stage1_scenarios.py [--van 30cc20c|af5e28f]
Writes outputs/tables/stage1_scenarios_check.csv (checks 1-5, 7), stage1_scenarios_effects.csv
(check 6), stage1_scenarios_range.csv (check 8), outputs/stage1_scenarios_check.md,
outputs/figures/stage1_scenarios_effects.png
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from estimation.data import production  # noqa: E402
from estimation.stage2 import VARS, window_features  # noqa: E402

VAN_ROOT = ROOT / "data/reference/van"
VAN = VAN_ROOT / "40db708/scenarios"
HIST = VAN.parent / "agriculture/hist_fitted_16regions.csv"  # observed weather (all variables) of the same version
PATHS = ROOT / "outputs/stage1_paths"
PROC, TAB, FIG, OUT = (ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures",
                       ROOT / "outputs")
SCEN = ["1997-98", "2015-16", "2023-24", "unit"]
MODELS = ["roni", "roni_dmi"]
README_MONTHS = {"af5e28f": {"1997-98": ("1997-04", "1999-03", 24), "2015-16": ("2015-04", "2017-03", 24),
                             "2023-24": ("2023-07", "2025-03", 21), "unit": ("2001-07", "2003-06", 24)},
                 "30cc20c": {"1997-98": ("1996-10", "1999-03", 30), "2015-16": ("2014-10", "2017-03", 30),
                             "2023-24": ("2023-01", "2025-03", 27), "unit": ("2001-01", "2003-06", 30)}}
SHOW = ["T", "P", "SM_RZ", "VPD"]
UNIT = {"T": "°C", "P": "mm/month", "SM_RZ": "m³/m³", "VPD": "kPa"}
INK, MUTED, GRID, BLUE, ORANGE = "#0b0b0b", "#52514e", "#d9d8d4", "#2a78d6", "#eb6834"


def palay_weights() -> pd.Series:
    p = pd.concat([production("irrigated"), production("rainfed")])
    p = p[p.period.str[:4].astype(int).between(2016, 2025)]
    w = p.groupby("region_code").production_t.sum()
    return w / w.sum()


def load(scen, model):
    f = VAN / scen / model
    sim = pd.read_csv(f / "simulated_monthly_16regions.csv").rename(columns={"code": "region_code"})
    det = pd.read_csv(f / "deterministic_monthly_16regions.csv").rename(columns={"code": "region_code"})
    eff = pd.read_csv(f / "effects_16regions.csv").rename(columns={"code": "region_code"})
    path = pd.read_csv(f / "path.csv")
    return sim, det, eff, path


def diff_draws(sim):
    """scenario - neutral by draw, date, region (same residuals)."""
    k = ["draw", "date", "region_code"]
    s = sim[sim.path == "scenario"].set_index(k)
    n = sim[sim.path == "neutral"].set_index(k)
    return s[VARS] - n[VARS].reindex(s.index), (s.hist_date == n.hist_date.reindex(s.index)).all()


def main():
    rows, eff_rows, rng_rows = [], [], []
    w = palay_weights()
    hist = pd.read_csv(HIST)
    obs = hist.rename(columns={"code": "region_code", **{f"{v}_obs": v for v in VARS}})
    obs["date"] = pd.to_datetime(obs.date)
    obs = obs[obs.date.dt.year.between(1987, 2025)]
    obs["cm"] = obs.date.dt.month
    lim = obs.groupby(["region_code", "cm"])[VARS].agg(["min", "max"])
    rice_win = pd.read_csv(PROC / "rice_growing_window.csv")
    corn_win = pd.read_csv(PROC / "corn_growing_window.csv")
    wins = {"irrigated": rice_win[rice_win.ecosystem == "irrigated"],
            "rainfed": rice_win[rice_win.ecosystem == "rainfed"],
            "corn": corn_win[corn_win.calendar == "rainfed"]}
    det_neutral = {}
    for scen in SCEN:
        for model in MODELS:
            sim, det, eff, path = load(scen, model)
            tag = {"scenario": scen, "model": model}

            def add(check, ok, detail):
                rows.append({**tag, "check": check, "ok": bool(ok), "detail": detail})

            # 1. structure
            a, z, n = README_MONTHS.get(VAN.parent.name, README_MONTHS["30cc20c"])[scen]  # 30cc20c on: same months
            months = sorted(sim.date.str[:7].unique())
            add("1 structure", months[0] == a and months[-1] == z and len(months) == n
                and sim.region_code.nunique() == 16 and set(sim.path) == {"scenario", "neutral"}
                and not sim[VARS].isna().any().any(),
                f"{sim.draw.nunique()} draws, {len(months)} months {months[0]} to {months[-1]}, "
                f"{sim.region_code.nunique()} regions, {int(sim[VARS].isna().sum().sum())} missing values")
            # 2. path vs ours
            ours = pd.read_csv(PATHS / f"path_{scen}.csv")
            m = path.merge(ours, on="date", suffixes=("_van", "_ours"))
            dmax = float((m.roni_van - m.roni_ours).abs().max())
            lead = path[path.lead_in.astype(str) == "True"]
            add("2 RONI path = ours", dmax < 1e-6,
                f"{len(m)} common months, max |difference| {dmax:.3g}; Van adds {len(lead)} observed "
                f"lead-in months ({lead.date.min()} to {lead.date.max()}) before our 6 zero months")
            # 3. same residuals
            dd, same = diff_draws(sim)
            add("3 same residual months in both runs", same, "hist_date identical for every draw, month, region"
                if same else "hist_date differs between scenario and neutral")
            # 7b. leading zero months exactly neutral
            first_nino = path[(path.lead_in.astype(str) == "False") & (path.roni != 0)].date.min()
            lead = dd.reset_index()
            lead = lead[lead.date < first_nino]
            if len(lead):
                mx = float(lead[VARS].abs().max().max())
                add("7b leading zero months: scenario = neutral", mx < 1e-9,
                    f"{lead.date.nunique()} months before {first_nino[:7]}, max |scenario - neutral| {mx:.2g}")
            # 9. residual years drawn
            yrs = sorted(sim.block_year.unique())
            gaps = [y for y in range(min(yrs), max(yrs) + 1) if y not in yrs]
            add("9 residual years drawn", not gaps,
                f"{len(yrs)} draws, block years {yrs[0]}-{yrs[-1]}"
                + (f"; missing {gaps[0]}-{gaps[-1]} ({len(gaps)} years)" if gaps else ""))
            # 4. deterministic neutral by calendar month
            dn = det[det.path == "neutral"].copy()
            dn["cm"] = dn.date.str[5:7].astype(int)
            spread = dn.groupby(["region_code", "cm"])[VARS].agg(lambda x: x.max() - x.min()).max().max()
            add("4 neutral depends on calendar month only", spread < 1e-4,
                f"max spread across years of the same calendar month {spread:.2g}")
            det_neutral[(scen, model)] = dn.groupby(["region_code", "cm"])[VARS].mean()
            # 5. effects table
            em = dd.groupby(["date", "region_code"]).mean()
            e = eff.pivot_table(index=["date", "region_code"], columns="var", values="effect_mean")
            # relative to each variable's typical size: the CSVs carry 6 significant digits
            scale = det[VARS].abs().max()
            err = float(((em[VARS] - e[VARS].reindex(em.index)).abs().max() / scale).max())
            ds = det[det.path == "scenario"].set_index(["date", "region_code"])[VARS]
            dn_ = det[det.path == "neutral"].set_index(["date", "region_code"])[VARS]
            ed = eff.pivot_table(index=["date", "region_code"], columns="var", values="effect_deterministic")
            err_d = float((((ds - dn_.reindex(ds.index)) - ed[VARS].reindex(ds.index)).abs().max()
                           / scale).max())
            add("5 effects table = draws", err < 1e-5 and err_d < 1e-5,
                f"max |mean effect recomputed - table| {err:.1g}, deterministic {err_d:.1g} "
                "(relative to each variable's largest value)")
            # 6. national effect by month (palay weights)
            nat = dd.mul(dd.index.get_level_values("region_code").map(w).to_numpy(), axis=0)
            nat = nat.groupby(["draw", "date"]).sum()
            for v in VARS:
                g = nat[v].groupby("date")
                for date, mean, q10, q90 in zip(g.mean().index, g.mean(), g.quantile(0.1), g.quantile(0.9)):
                    eff_rows.append({**tag, "var": v, "date": date, "mean": mean, "q10": q10, "q90": q90})
            # fade-out: El Nino months end at the last nonzero RONI of the path table
            nz = path[(path.lead_in.astype(str) == "False") & (path.roni != 0)].date.max()
            after = pd.Period(nz[:7], "M") + 7
            late = nat.reset_index()
            late = late[pd.PeriodIndex(late.date.str[:7], freq="M") >= after]
            mx = late.groupby("date")[["T", "P", "SM_RZ"]].mean().abs().max()
            add("6 effects fade after the El Nino months", (mx < [0.02, 2.0, 0.002]).all(),
                f"from {after} on: max |national mean effect| T {mx['T']:.3f} °C, P {mx['P']:.2f} mm, "
                f"SM_RZ {mx['SM_RZ']:.4f}")
            # 7. growing windows reaching before the tables
            det_s = det[det.path == "scenario"]
            for crop, win in wins.items():
                f = window_features(det_s, win)
                bad = f[f["T"].isna()].period.unique()
                # harvest quarters from the first El Nino month on (before it the shock is zero)
                first_q = pd.Period(first_nino[:7], "M").asfreq("Q")
                bad = sorted(q for q in bad if pd.Period(q, "Q") >= first_q)
                add(f"7 windows inside the tables ({crop})", not bad,
                    "all harvest quarters complete" if not bad else
                    f"incomplete windows for harvest quarters {', '.join(bad)}")
            # 8. range (both paths, all draws): the neutral path shows how much comes from today's
            # climate alone (trend at t* = 2026), the scenario path adds El Nino
            for run in ("scenario", "neutral"):
                s = sim[sim.path == run].copy()
                s["cm"] = s.date.str[5:7].astype(int)
                L = lim.reindex(pd.MultiIndex.from_frame(s[["region_code", "cm"]]))
                for v in VARS:
                    lo, hi = L[(v, "min")].to_numpy(), L[(v, "max")].to_numpy()
                    x = s[v].to_numpy()
                    rng_rows.append({**tag, "path": run, "var": v,
                                     "share_below_pct": float(np.mean(x < lo) * 100),
                                     "share_above_pct": float(np.mean(x > hi) * 100)})
    # 4b. neutral the same across scenarios
    for (scen, model), dn in det_neutral.items():
        ref = det_neutral[("unit", model)]
        diff = float((dn - ref.reindex(dn.index)).abs().max().max())
        rows.append({"scenario": scen, "model": model, "check": "4b neutral = neutral of the unit path",
                     "ok": diff < 1e-4,
                     "detail": f"max |difference| {diff:.2g} (calendar months in common, same model)"})

    chk = pd.DataFrame(rows)
    eff = pd.DataFrame(eff_rows)
    rng = pd.DataFrame(rng_rows)
    chk.to_csv(TAB / "stage1_scenarios_check.csv", index=False)
    eff.round(5).to_csv(TAB / "stage1_scenarios_effects.csv", index=False)
    rng.round(3).to_csv(TAB / "stage1_scenarios_range.csv", index=False)
    report(chk, eff, rng)
    figure(eff)


def md(df, fmt="{:.2f}"):
    def cell(v):
        return fmt.format(v) if isinstance(v, (float, np.floating)) else str(v)
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    return "\n".join(lines + ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)])


def report(chk, eff, rng):
    peak = (eff[(eff.model == "roni") & eff["var"].isin(SHOW)]
            .assign(absmean=lambda x: x["mean"].abs())
            .loc[lambda x: x.groupby(["scenario", "var"]).absmean.idxmax()]
            [["scenario", "var", "date", "mean", "q10", "q90"]])
    r = (rng[rng.model == "roni"].assign(outside=lambda x: x.share_below_pct + x.share_above_pct)
         .pivot_table(index="var", columns=["scenario", "path"], values="outside"))
    r.columns = [f"{a} {b}" for a, b in r.columns]
    r = r.reset_index()
    s = [f"# Check of Van's Stage-1 scenario simulations ({VAN.parent.name})\n",
         "A check before the chain, not a result. Details in scripts/check_stage1_scenarios.py.\n",
         "## Checks\n", md(chk[["scenario", "model", "check", "ok", "detail"]]),
         "\n## Largest national effect by scenario (RONI model; palay-weighted, scenario - neutral; "
         "mean and 10th-90th percentiles over draws)\n", md(peak, "{:.3f}"),
         "\n## Simulated region-months outside the range observed in 1987-2025 (% of region-months, "
         "RONI model, all draws; neutral = today's climate alone)\n", md(r, "{:.1f}")]
    (OUT / "stage1_scenarios_check.md").write_text("\n".join(s) + "\n")
    print("\n".join(s))


def figure(eff):
    fig, axes = plt.subplots(len(SHOW), len(SCEN), figsize=(12, 8.5), constrained_layout=True, sharey="row")
    for i, v in enumerate(SHOW):
        for j, scen in enumerate(SCEN):
            ax = axes[i, j]
            for model, col in (("roni", BLUE), ("roni_dmi", ORANGE)):
                e = eff[(eff.scenario == scen) & (eff.model == model) & (eff["var"] == v)].sort_values("date")
                x = pd.to_datetime(e.date)
                if model == "roni":
                    ax.fill_between(x, e.q10, e.q90, color=col, alpha=0.18, lw=0)
                ax.plot(x, e["mean"], color=col, lw=1.4, label={"roni": "RONI (main), 10–90%",
                                                                "roni_dmi": "RONI + DMI"}[model])
            ax.axhline(0, color=MUTED, lw=0.8)
            ax.tick_params(labelsize=7, colors=MUTED)
            ax.grid(color=GRID, lw=0.5)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            for lab in ax.get_xticklabels():
                lab.set_rotation(45)
            if i == 0:
                ax.set_title(scen, fontsize=9, color=INK, loc="left")
            if j == 0:
                ax.set_ylabel(f"{v} ({UNIT[v]})", fontsize=8, color=MUTED)
    axes[0, 0].legend(frameon=False, fontsize=7)
    fig.suptitle("Van's Stage 1 on the scenario paths: national effect (scenario − neutral, palay-weighted), "
                 "by month", fontsize=10, color=INK, x=0.01, ha="left")
    fig.savefig(FIG / "stage1_scenarios_effects.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--van", default="40db708", help="Van's commit folder under data/reference/van/")
    VAN = VAN_ROOT / ap.parse_args().van / "scenarios"
    HIST = VAN.parent / "agriculture/hist_fitted_16regions.csv"
    main()
