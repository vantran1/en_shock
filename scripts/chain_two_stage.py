"""Two-stage shocks: Van's Stage-1 simulations chained with Stage 2 (methodology v5 Section 3.5).
PROVISIONAL.

Inputs
- Van's Stage-1 runs on the four scenario paths of the direct approach (dev_Van f6ddf65, 25 Nov
  2026; data/reference/van/f6ddf65/scenarios/, untracked): monthly weather by region for 73 draws,
  scenario and neutral path with the same residuals, today's climate (trend at t* = 2026). RONI
  model (main) and RONI + DMI model (variant, --model roni_dmi).
- Stage 2 fitted on observed weather and PSA production, 1987-2025 (estimation.stage2;
  data/processed/stage2_features.csv). Models (scripts/select_stage2.py, nested choice, and the
  decision of 25 Nov 2026 to use one common break year, 2000):
    main: boosting on the 9 compact features for all three series (decision of 26 Nov 2026; the
          nested choice picks it for irrigated palay and corn), weather response changing from 2000,
          today's (post-2000) response;
    sensitivities: the same with the change from 2005, from 2010, or no change (the response
          averaged over 1987-2025: a stress case, the 1990s response included), and the hinge
          regression on temperature and soil moisture changing from 2000, and the full 30 features
          for all three series (with solar radiation: in the full model El Nino's sunnier skies raise
          rainfed production, partly a genuine effect, partly low radiation marking typhoon months).

Steps, for each path, draw and crop series (v5 Eqs. 12-13b)
1. Window features of the simulated weather (estimation.stage2.window_features, the crop
   calendars of section 7.1), for the scenario and the neutral run.
2. Weather factor f(W) of Stage 2 for both runs; region, season, trend and control terms are the
   same in both runs ("no event" controls) and cancel: S_{r,q,b} = 1 - f(W^S_{r,q,b}) / f(W^0_{r,q,b})
   (Eq. 12).
3. National shock with neutral production shares (Eq. 13a): y0_{r,q,b} = ybar_{r,qtr(q)} f(W^0)
   with ybar the model's non-weather prediction for 2025 (controls at no event);
   S_{q,b} = 1 - sum_r ybar f(W^S) / sum_r ybar f(W^0). Palay = irrigated + rainfed in the same way.
4. Across draws: mean (the two-stage estimate), 5th, 10th, 90th and 95th percentiles (v5: the 90th
   for stress scenarios). Scaled for DEFINE-PH (Eq. 13b) with the neutral production of the quarter.
5. Reliability flag (v5 Section 3.4 "Limits"; change log C12): a region-quarter of a draw is flagged
   when a feature the model uses is outside the range observed in 1987-2025 for that region and
   quarter of the year on the side where losses are extrapolated (hotter, drier, longer dry spells;
   estimation.stage2.HINGE), in the scenario run but not in the neutral run (so today's warmer
   climate alone does not flag it). Reported as the production-weighted share flagged, mean over draws.
Quarters: those of the direct shocks (first quarter of the path to 4 quarters after it).

Run:  python scripts/chain_two_stage.py [--model roni|roni_dmi]
Writes outputs/tables/two_stage_shocks[_roni_dmi].csv (path x crop x variant x quarter: mean,
percentiles, scaled, flag share), two_stage_draws[_roni_dmi].csv (national shock by draw, main
variant), two_stage_regional[_roni_dmi].csv (main variant, mean over draws),
outputs/two_stage_shocks[_roni_dmi].md, outputs/figures/two_stage_vs_direct[_roni_dmi].png
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from build_stage2_features import calendars  # noqa: E402
from estimate_stage2 import base_design, md, panel  # noqa: E402
from estimation.data import CONTROLS  # noqa: E402
from estimation.stage2 import (FEATURES, HINGE, VARS, Stage2Spec, fit_gbm, fit_hinge,  # noqa: E402
                               predict_gbm, predict_hinge, window_features)
from select_stage2 import COMPACT  # noqa: E402

VAN = ROOT / "data/reference/van/f6ddf65/scenarios"
TAB, FIG, OUT = ROOT / "outputs/tables", ROOT / "outputs/figures", ROOT / "outputs"
SCEN = {"1997-98": "1997-98", "2015-16": "2015-16", "2023-24": "2023-24",
        "unit": "unit RONI +1 (4 quarters from Q3)"}  # Van's folder -> direct shocks' path name
SERIES = ["irrigated", "rainfed", "corn"]
# compact features for all three series (decision of 26 Nov 2026): the nested choice (re-run with the
# water constraint) picks the compact boosting for irrigated palay and corn and the full one for rainfed
# palay; the full model for rainfed palay predicts somewhat better but gives the same shocks, and its
# solar radiation partly stands in for typhoon months (flood damage belongs to the CAT channel)
MAIN_FEATURES = {"irrigated": COMPACT, "rainfed": COMPACT, "corn": COMPACT}
VARIANTS = {"main (from 2000)": ("gbm", 2000), "from 2005": ("gbm", 2005), "from 2010": ("gbm", 2010),
            "no change (stress)": ("gbm", None), "regression T+SM_RZ (from 2000)": ("reg", 2000),
            "full features for all (from 2000)": ("gbm_full", 2000)}
MAIN = "main (from 2000)"
T_YEAR = 2025
STATUS = "provisional; two-stage approach (Stage 1 Van f6ddf65, Stage 2 compact boosting from 2000)"
INK, MUTED, GRID, BLUE, ORANGE = "#0b0b0b", "#52514e", "#d9d8d4", "#2a78d6", "#eb6834"


def fit_variant(series, kind, brk):
    """Fit on all years; returns f(features) -> weather factor (today's response), the features
    used, and ybar (non-weather prediction for 2025 by region and quarter, controls at no event)."""
    d, y = panel(series)
    for b in (2000, 2005, 2010):
        d[f"post{b}"] = (d.period.str[:4].astype(int) >= b).astype(float)
    train = np.ones(len(d), bool)
    base = base_design(d, train, series)
    if kind in ("gbm", "gbm_full"):
        fset = FEATURES if kind == "gbm_full" else MAIN_FEATURES[series]
        feats = fset + ([f"post{brk}"] if brk else [])
        r = fit_gbm(d, y, base, feats, train)
        params = r["params"]

        def f(dd):
            dd = dd.copy()
            if brk:
                dd[f"post{brk}"] = 1.0  # today's response
            return predict_gbm(r, dd, None, weather_only=True)
        used = fset
    else:
        spec = Stage2Spec(f"reg_{brk}", hinge=("T", "SM_RZ"), post=brk)
        r = fit_hinge(d, y, base, spec, train)
        params = r["params"][[c for c in r["params"].index if c in base.columns]]

        def f(dd):
            dd = dd.copy()
            dd["period"] = f"{T_YEAR}Q1"  # post-break terms on: today's response
            return predict_hinge(r, dd, None, spec, weather_only=True)
        used = ["T", "SM_RZ"]
    m = (d.period.str[:4].astype(int) == T_YEAR).to_numpy()
    B = base.loc[m, params.index].copy()
    B[[c for c in B.columns if c in CONTROLS]] = 0.0
    ybar = pd.Series(np.exp(B.to_numpy(float) @ params.to_numpy()),
                     index=pd.MultiIndex.from_arrays([d.loc[m, "region_code"].values, d.loc[m, "q"].values],
                                                     names=["region_code", "q"]))
    obs = d[["region_code", "q"] + used]
    return f, used, ybar, obs


def sim_features(scen, model, series):
    w = pd.read_csv(VAN / scen / model / "simulated_monthly_16regions.csv").rename(columns={"code": "region_code"})
    f = window_features(w[["path", "draw", "date", "region_code"] + VARS], calendars()[series], keys=["path", "draw"])
    f["q"] = f.period.str[-1].astype(int)
    return f


def flags(feat_s, feat_0, obs, used):
    """True where a used feature is beyond the 1987-2025 range (region x quarter of the year) on the
    loss side in the scenario run but not in the neutral run."""
    lo = obs.groupby(["region_code", "q"])[used].min()
    hi = obs.groupby(["region_code", "q"])[used].max()
    idx = pd.MultiIndex.from_frame(feat_s[["region_code", "q"]])
    out_s = np.zeros(len(feat_s), bool)
    out_0 = np.zeros(len(feat_s), bool)
    for v in used:
        if HINGE.get(v) == "upper":
            lim = hi[v].reindex(idx).to_numpy()
            out_s |= feat_s[v].to_numpy() > lim
            out_0 |= feat_0[v].to_numpy() > lim
        elif HINGE.get(v) == "lower":
            lim = lo[v].reindex(idx).to_numpy()
            out_s |= feat_s[v].to_numpy() < lim
            out_0 |= feat_0[v].to_numpy() < lim
    return out_s & ~out_0


def main(model="roni"):
    sfx = "" if model == "roni" else f"_{model}"
    direct = pd.concat([pd.read_csv(TAB / "shocks_rice.csv"), pd.read_csv(TAB / "shocks_corn.csv")])
    direct = direct[direct.crop.isin(["palay", "corn"])]
    fits = {(s_, v): fit_variant(s_, *VARIANTS[v]) for s_ in SERIES for v in VARIANTS}
    print("stage 2 fitted", flush=True)
    rows, draws, regional = [], [], []
    for scen, pname in SCEN.items():
        quarters = sorted(direct[direct.path == pname].scenario_q.unique())
        feats = {s_: sim_features(scen, model, s_) for s_ in SERIES}
        for v in VARIANTS:
            parts = {}
            for s_ in SERIES:
                f, used, ybar, obs = fits[(s_, v)]
                ft = feats[s_][feats[s_].period.isin(quarters)]
                fs = ft[ft.path == "scenario"].sort_values(["draw", "region_code", "period"]).reset_index(drop=True)
                f0 = ft[ft.path == "neutral"].sort_values(["draw", "region_code", "period"]).reset_index(drop=True)
                assert (fs[["draw", "region_code", "period"]].values == f0[["draw", "region_code", "period"]].values).all()
                x = fs[["draw", "region_code", "period", "q"]].copy()
                x["yb"] = ybar.reindex(pd.MultiIndex.from_frame(x[["region_code", "q"]])).fillna(0).to_numpy()
                x["fS"], x["f0"] = f(fs), f(f0)
                x["flag"] = flags(fs, f0, obs, used)
                parts[s_] = x
                if v == MAIN:
                    regional.append(x.assign(S=1 - x.fS / x.f0).groupby(["region_code", "period"]).S.mean()
                                    .reset_index().assign(path=scen, series=s_))
            for crop, members in (("palay", ["irrigated", "rainfed"]), ("corn", ["corn"])):
                x = pd.concat([parts[m_] for m_ in members])
                x["yS"], x["y0"] = x.yb * x.fS, x.yb * x.f0
                x["yflag"] = x.y0 * x.flag
                g = x.groupby(["period", "draw"])[["yS", "y0", "yflag"]].sum().reset_index()
                g["S"] = 1 - g.yS / g.y0
                g["flag"] = g.yflag / g.y0
                # Eq. 13b: scaling with the quarter's share of annual neutral production (y0 summed over
                # draws, i.e. the mean over draws up to a constant)
                g["q"] = g.period.str[-1].astype(int)
                y0q = x.groupby("q").y0.sum() / x.groupby("q").period.nunique()
                g["S_D"] = g.S * 4 * g.q.map(y0q / y0q.sum())
                if v == MAIN:
                    draws.append(g.assign(path=scen, crop=crop)[["path", "crop", "period", "draw", "S", "S_D", "flag"]])
                agg = g.groupby("period").agg(S=("S", "mean"), S_p05=("S", lambda s: s.quantile(.05)),
                                              S_p10=("S", lambda s: s.quantile(.10)),
                                              S_p90=("S", lambda s: s.quantile(.90)),
                                              S_p95=("S", lambda s: s.quantile(.95)),
                                              S_D=("S_D", "mean"), S_D_p90=("S_D", lambda s: s.quantile(.90)),
                                              flag_share=("flag", "mean"), draws=("draw", "nunique")).reset_index()
                rows.append(agg.assign(path=scen, crop=crop, variant=v))
        print(f"{scen}: done", flush=True)
    res = pd.concat(rows).rename(columns={"period": "scenario_q"})
    res = res[["path", "crop", "variant", "scenario_q", "S", "S_p05", "S_p10", "S_p90", "S_p95", "S_D", "S_D_p90",
               "flag_share", "draws"]]
    res.assign(stage1_model=model, status=STATUS).round(5).to_csv(TAB / f"two_stage_shocks{sfx}.csv", index=False)
    pd.concat(draws).round(5).to_csv(TAB / f"two_stage_draws{sfx}.csv", index=False)
    pd.concat(regional).round(5).to_csv(TAB / f"two_stage_regional{sfx}.csv", index=False)
    report(res, direct, sfx, model)
    figure(res, direct, sfx, model)


def report(res, direct, sfx, model):
    d = direct.assign(path=direct.path.map({v: k for k, v in SCEN.items()}))
    m = res[res.variant == MAIN].merge(d[["path", "crop", "scenario_q", "S", "S_p05", "S_p95"]],
                                       on=["path", "crop", "scenario_q"], suffixes=("", "_direct"))
    t = m[["path", "crop", "scenario_q", "S", "S_p10", "S_p90", "flag_share", "S_direct", "S_p05_direct",
           "S_p95_direct"]].copy()
    for c in t.columns[3:]:
        t[c] = t[c] * 100
    # episode totals: sum of S_D over the quarters (% of a year's production / 4 per quarter -> /4)
    tot = (res.groupby(["path", "crop", "variant"]).S_D.sum() / 4 * 100).unstack("variant").reset_index()
    dtot = (d.groupby(["path", "crop"]).S_D.sum() / 4 * 100).rename("direct").reset_index()
    tot = tot.merge(dtot, on=["path", "crop"], how="left")
    s = [f"# Two-stage shocks (PROVISIONAL; Stage 1 model {model})\n",
         "Van's Stage 1 (f6ddf65, 73 draws) chained with Stage 2 (main: boosting, response changing from 2000, "
         "today's response). Shock = share of the quarter's neutral production lost (v5 Eq. 12-13a), mean over "
         "draws with the 10th-90th percentiles; flag = production-weighted share of region-quarters where the "
         "El Nino weather goes beyond the 1987-2025 range on the loss side (mean over draws). Direct: the direct "
         "approach (central, 5th-95th bootstrap). All in %.\n",
         "## Quarterly shocks, main variant, next to the direct approach\n", md(t, "{:.1f}"),
         "\n## Total loss over the episode, % of a year's production (sum of scaled quarterly shocks / 4), by variant\n",
         md(tot, "{:.1f}")]
    (OUT / f"two_stage_shocks{sfx}.md").write_text("\n".join(s) + "\n")
    print("\n".join(s))


def figure(res, direct, sfx, model):
    d = direct.assign(path=direct.path.map({v: k for k, v in SCEN.items()}))
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True, sharey="row")
    for i, crop in enumerate(["palay", "corn"]):
        for j, scen in enumerate(SCEN):
            ax = axes[i, j]
            t = res[(res.path == scen) & (res.crop == crop) & (res.variant == MAIN)].sort_values("scenario_q")
            x = np.arange(len(t))
            ax.fill_between(x, t.S_p10 * 100, t.S_p90 * 100, color=ORANGE, alpha=0.2, lw=0)
            ax.plot(x, t.S * 100, color=ORANGE, lw=2, marker="o", ms=3, label="two-stage (mean, 10-90%)")
            for v, ls in (("no change (stress)", ":"), ("regression T+SM_RZ (from 2000)", "--")):
                tv = res[(res.path == scen) & (res.crop == crop) & (res.variant == v)].sort_values("scenario_q")
                ax.plot(x, tv.S * 100, color=ORANGE, lw=1, ls=ls, label=v)
            dd = d[(d.path == scen) & (d.crop == crop)].set_index("scenario_q").reindex(t.scenario_q)
            ax.errorbar(x + 0.15, dd.S * 100, yerr=[(dd.S - dd.S_p05) * 100, (dd.S_p95 - dd.S) * 100], fmt="s",
                        ms=3.5, color=BLUE, lw=1, capsize=2, label="direct (5-95%)")
            ax.axhline(0, color=MUTED, lw=0.8)
            ax.set_xticks(x, t.scenario_q.str[2:], fontsize=7, rotation=45)
            ax.tick_params(labelsize=7, colors=MUTED)
            ax.grid(axis="y", color=GRID, lw=0.5)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            if i == 0:
                ax.set_title(scen, fontsize=9, color=INK, loc="left")
            if j == 0:
                ax.set_ylabel(f"{crop}: % of the quarter's production lost", fontsize=8, color=MUTED)
    axes[0, 0].legend(frameon=False, fontsize=7)
    fig.suptitle(f"PROVISIONAL. Two-stage shocks (Stage 1 {model}, 73 draws) and direct shocks, by quarter",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.savefig(FIG / f"two_stage_vs_direct{sfx}.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["roni", "roni_dmi"], default="roni")
    main(ap.parse_args().model)
