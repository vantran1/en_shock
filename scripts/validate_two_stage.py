"""Validation of the whole two-stage chain on the past episodes (methodology v5 Section 3.6: "each
episode is left out in turn, the models are re-estimated without it, and the predicted losses are
compared with the observed ones"). PROVISIONAL; a diagnostic.

For each series (irrigated palay, rainfed palay, corn; palay = both) and each episode (1997Q2-1998Q4,
2015Q2-2016Q4, 2023Q2-2024Q4):
- Stage 2 (the chain's model: boosting on the features of chain_two_stage.MAIN_FEATURES, response
  changing from 2000 except for VR and PF, whose data start in 2010; water constraint) is re-estimated without the episode and the 4 quarters after it (the held-out window of the strict
  validation of the direct approach, scripts/validate_strict.py).
- Stage 1 enters through Van's nested hindcast (`<var>_nested`, dev_Van 40db708): the weather of each
  month predicted from RONI alone by a model estimated without the 5-year block holding that month
  (lags and modes also chosen without it). It is the weather the chain predicts knowing only RONI,
  with no residual (the deterministic response).
- Over the episode window, national production against the model without weather (region, season,
  trend and control terms of the same fit; i.e. production at average weather):
    observed:            1 - sum(actual) / sum(reference)
    stage 2, obs weather: 1 - sum(prediction with the observed weather) / sum(reference)
                          (as if Stage 1 were perfect)
    chain:               1 - sum(prediction with the nested Stage-1 weather) / sum(reference)
  The gap between the second and the third is what Stage 1 loses; between the third and the first,
  the error of the whole method.
- Direct approach, for comparison: scripts/validate_strict.py, recommended specification without the
  DMI (its own reference is the neutral path RONI = 0, so its observed loss differs slightly).
Quarterly profiles are written too.

Run:  python scripts/validate_two_stage.py
Writes outputs/tables/validation_two_stage.csv (episode totals), validation_two_stage_quarterly.csv,
outputs/validation_two_stage.md, outputs/figures/validation_two_stage.png
"""
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

from build_stage2_features import HIST, calendars  # noqa: E402
from estimate_stage2 import base_design, md, panel  # noqa: E402
from estimation.stage2 import FEATURES, fit_gbm, observed_weather, predict_gbm, window_features  # noqa: E402
from chain_two_stage import MAIN_FEATURES, VRPF  # noqa: E402

TAB, FIG, OUT = ROOT / "outputs/tables", ROOT / "outputs/figures", ROOT / "outputs"
SERIES = ["irrigated", "rainfed", "corn"]  # VR and PF not chained (no out-of-sample skill; see chain_two_stage)
EPISODES = {"1997-98": ("1997Q2", "1998Q4"), "2015-16": ("2015Q2", "2016Q4"), "2023-24": ("2023Q2", "2024Q4")}
EXTRA_AFTER = 4
STATUS = "provisional; diagnostic (validation of the two-stage chain, v5 Section 3.6)"
INK, MUTED, GRID, BLUE, ORANGE, GREEN = "#0b0b0b", "#52514e", "#d9d8d4", "#2a78d6", "#eb6834", "#3a9a5b"


def nested_features(series):
    w = observed_weather(pd.read_csv(HIST), suffix="_nested")
    return window_features(w, calendars()[series])


def run(series, episode):
    d, y = panel(series)
    d["post2000"] = (d.period.str[:4].astype(int) >= 2000).astype(float)
    a, z = EPISODES[episode]
    per = pd.PeriodIndex(d.period, freq="Q")
    held = np.asarray((per >= pd.Period(a, "Q")) & (per <= pd.Period(z, "Q") + EXTRA_AFTER))
    window = np.asarray((per >= pd.Period(a, "Q")) & (per <= pd.Period(z, "Q")))
    if window.sum() == 0:  # episode before the data (VR and PF start in 2010)
        return None
    base = base_design(d, ~held, series)
    feats = MAIN_FEATURES[series] + ([] if series in VRPF else ["post2000"])
    r = fit_gbm(d, y, base, feats, ~held)
    ref = np.exp(base[r["params"].index].to_numpy(float) @ r["params"].to_numpy())
    mu_obs = predict_gbm(r, d, base)
    nf = nested_features(series)
    dn = d[["region_code", "period", "post2000"]].merge(nf, on=["region_code", "period"], how="left")
    assert not dn[MAIN_FEATURES[series]].isna().any().any()
    dn.index = d.index
    mu_nest = predict_gbm(r, dn, base)
    q = d.loc[window, ["period"]].assign(actual=y[window], reference=ref[window], stage2_obs=mu_obs[window],
                                         chain=mu_nest[window])
    return q.groupby("period").sum().reset_index().assign(series=series, episode=episode)


def main():
    q = pd.concat([x for x in (run(s_, e) for s_ in SERIES for e in EPISODES) if x is not None])
    q = pd.concat([q, q[q.series.isin(["irrigated", "rainfed"])].groupby(["episode", "period"])
                   [["actual", "reference", "stage2_obs", "chain"]].sum().reset_index().assign(series="palay")])
    tot = q.groupby(["series", "episode"])[["actual", "reference", "stage2_obs", "chain"]].sum()
    res = pd.DataFrame({"observed_loss_pct": (1 - tot.actual / tot.reference) * 100,
                        "stage2_obs_weather_pct": (1 - tot.stage2_obs / tot.reference) * 100,
                        "chain_pct": (1 - tot.chain / tot.reference) * 100}).reset_index()
    res["chain_error_pts"] = res.chain_pct - res.observed_loss_pct
    direct = []
    for crop in ("rice", "corn", "vr", "pf"):
        v = pd.read_csv(TAB / f"validation_strict_{crop}.csv")
        v = v[v.variant.str.startswith("recommended") & v.variant.str.contains("no DMI")]
        direct.append(v[["series", "episode", "observed_loss_pct", "predicted_loss_pct", "error_pts"]]
                      .rename(columns={"observed_loss_pct": "direct_observed_pct",
                                       "predicted_loss_pct": "direct_predicted_pct",
                                       "error_pts": "direct_error_pts"}))
    res = res.merge(pd.concat(direct), on=["series", "episode"], how="left")
    order = {"palay": 0, "irrigated": 1, "rainfed": 2, "corn": 3, "vr": 4, "pf": 5}
    res = res.sort_values(["series", "episode"], key=lambda c: c.map(order) if c.name == "series" else c)
    res.assign(status=STATUS).round(3).to_csv(TAB / "validation_two_stage.csv", index=False)
    q.round(4).to_csv(TAB / "validation_two_stage_quarterly.csv", index=False)
    mae = res.groupby("series")[["chain_error_pts", "direct_error_pts"]].apply(lambda x: x.abs().mean()).round(1)
    s = ["# Validation of the two-stage chain on past episodes (PROVISIONAL)\n",
         "Each episode left out of Stage 2 (with the 4 quarters after it); Stage 1 weather from Van's nested "
         "hindcast (out of sample, from RONI alone). Loss over the episode window, % of production at average "
         "weather. Direct: strict validation of the direct approach (recommended, no DMI; its own reference "
         "is RONI = 0). See scripts/validate_two_stage.py.\n",
         md(res, "{:.1f}"), "\n## Mean absolute error over the three episodes (points)\n",
         md(mae.reset_index(), "{:.1f}")]
    (OUT / "validation_two_stage.md").write_text("\n".join(s) + "\n")
    print("\n".join(s))
    figure(q)


def figure(q):
    series = SERIES
    fig, axes = plt.subplots(len(series), 3, figsize=(13, 2.9 * len(series)), constrained_layout=True,
                             sharey="row")
    for i, s_ in enumerate(series):
        for j, e in enumerate(EPISODES):
            ax = axes[i, j]
            t = q[(q.series == s_) & (q.episode == e)].sort_values("period")
            x = np.arange(len(t))
            for col, c, lab, lw in (("actual", INK, "observed", 2), ("stage2_obs", GREEN, "stage 2, observed weather", 1.3),
                                    ("chain", ORANGE, "chain (Stage 1 out of sample)", 1.6)):
                ax.plot(x, (t[col] / t.reference - 1) * 100, color=c, lw=lw, marker="o" if col == "actual" else None,
                        ms=3, label=lab)
            ax.axhline(0, color=MUTED, lw=0.8)
            ax.set_xticks(x, t.period.str[2:], fontsize=7, rotation=45)
            ax.tick_params(labelsize=7, colors=MUTED)
            ax.grid(axis="y", color=GRID, lw=0.5)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            if i == 0:
                ax.set_title(f"{e} held out", fontsize=9, color=INK, loc="left")
            if j == 0:
                ax.set_ylabel(f"{s_}: % vs average weather", fontsize=8, color=MUTED)
    axes[0, 0].legend(frameon=False, fontsize=7)
    fig.suptitle("PROVISIONAL. Validation of the two-stage chain: national production in each held-out episode",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.savefig(FIG / "validation_two_stage.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
