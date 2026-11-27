"""Agricultural production shocks for DEFINE-PH by food category (methodology v5 Section 3.5,
"Aggregation"; tracker G6). PROVISIONAL.

Inputs: the shocks of the direct approach, RONI only (scripts/shocks_direct.py:
outputs/tables/shocks_{rice,corn,vr,pf}.csv and the bootstrap draws *_bootstrap.csv), and the
rice sensitivity without the Luzon typhoon quarters of late 2015 (*_no_luzon2015).

Categories: the five food types of the DEFINE-PH equations (SOAS, November 2026, Section 4.1;
confirmed by Alper 27 Nov 2026), each with its own shock, so nothing is combined across crops:
- rice            palay shock (irrigated and rainfed combined with neutral production shares)
- corn            total corn (white and yellow, including feed corn)
- vegetables      the VR index (vegetables, root crops and pulses)
- fruits          the PF index (perennial fruits)
- other_food      NO El Nino production shock (v5: "other food takes no El Nino production
                  shock"): zero in every quarter
Sensitivity:
- rice_sensitivity_no_luzon2015   rice estimated without the Luzon regions in 2015Q4-2016Q2
                  (an upper bound; write-up section 2.6, Table 4a; kept at Alper's request)
The combined vegetables-and-fruits shock and the two-food-type fallback (corn + VR + PF for all
food except rice) of earlier versions were dropped on 27 Nov 2026 (no longer needed).
Ranges: 5th-95th percentiles of the block-bootstrap draws of each crop.

Two-stage approach and the rule of v5 Section 3.5 (26 Nov 2026): for rice and corn the two-stage
shocks (scripts/chain_two_stage.py, main variant) are written to separate comparison files (the main
delivery file holds only what goes into DEFINE-PH), and the rule is applied to the total over each path: "The direct approach gives the central estimate. The
two-stage result is reported as the upper end of a range when it lies outside the 90 percent confidence
interval of the direct approach; otherwise only the direct estimate is given. If the two-stage result is
clearly smaller, the direct estimate is used ... and the difference is noted." The rule is applied to the
totals, not quarter by quarter: the two approaches distribute the loss differently over the quarters
(the direct corn shock has recovery gains after the dry-season loss, the two-stage one has none), so a
quarter-by-quarter rule would splice two different paths. The central shocks and ranges are those of
the direct approach.

Run:  python scripts/deliver_food_shocks.py
Writes outputs/delivery/food_shocks_define_ph.csv (path x category x quarter),
outputs/delivery/food_shocks_episode_totals.csv, outputs/delivery/README_food_shocks.md, and the
comparison with the two-stage approach (not for DEFINE-PH): outputs/delivery/comparison/
two_stage_comparison.csv (quarterly) and two_stage_comparison_totals.csv
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

TAB = ROOT / "outputs/tables"
OUT = ROOT / "outputs/delivery"
# category -> (crop of shocks_direct.py, file suffix, series)
SINGLE = {"rice": ("rice", "", "palay"), "corn": ("corn", "", "corn"),
          "vegetables": ("vr", "", "vr"), "fruits": ("pf", "", "pf"),
          "rice_sensitivity_no_luzon2015": ("rice", "_no_luzon2015", "palay")}
ZERO = "other_food"  # the fifth food type: no El Nino production shock (v5)
KEY = ["path", "scenario_q"]


def single(crop, sfx, series):
    s = pd.read_csv(TAB / f"shocks_{crop}{sfx}.csv")
    s = s[s.crop == series]
    b = pd.read_csv(TAB / f"shocks_{crop}_bootstrap{sfx}.csv")
    b = b[b.crop == series][KEY + ["rep", "S", "S_D"]]
    return s, b


def pct(draws, col):
    return draws.groupby(KEY)[col].quantile([0.05, 0.95]).unstack().rename(
        columns={0.05: f"{col}_p05", 0.95: f"{col}_p95"})


TWO_STAGE_PATHS = {"1997-98": "1997-98", "2015-16": "2015-16", "2023-24": "2023-24",
                   "unit": "unit RONI +1 (4 quarters from Q3)", "c3s": "C3S forecast (Nov 2026)"}


def two_stage():
    """Two-stage shocks of the chain (main variant) for rice (palay) and corn, delivery keys."""
    t = pd.read_csv(TAB / "two_stage_shocks.csv")
    t = t[t.variant == "main (from 2000)"].copy()
    t["category"] = t.crop.map({"palay": "rice", "corn": "corn"})
    t["path"] = t.path.map(TWO_STAGE_PATHS)
    return t.rename(columns={"S": "two_stage_S", "S_D": "two_stage_S_D", "S_p90": "two_stage_S_p90",
                             "S_D_p90": "two_stage_S_D_p90", "flag_share": "two_stage_flag_share"})[
        ["category", "path", "scenario_q", "two_stage_S", "two_stage_S_D", "two_stage_S_p90",
         "two_stage_S_D_p90", "two_stage_flag_share"]]


def rule(two, lo, hi):
    """v5 Section 3.5 outcome for a two-stage value against the direct 90% range."""
    if pd.isna(two):
        return ""
    if two > hi:
        return "above the direct 90% range: two-stage = upper end of the range"
    if two < lo:
        return "below the direct 90% range: direct used, difference noted"
    return "within the direct 90% range: direct only"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    central, draws, rows, totals = {}, {}, [], []
    for cat, (crop, sfx, series) in SINGLE.items():
        central[cat], draws[cat] = single(crop, sfx, series)
    zc = central["rice"].copy()
    zc[["S", "S_D"]] = 0.0
    zd = draws["rice"].copy()
    zd[["S", "S_D"]] = 0.0
    central[ZERO], draws[ZERO] = zc, zd
    for cat in list(SINGLE) + [ZERO]:
        c = central[cat].set_index(KEY)[["q", "step", "in_path", "S", "S_D"]]
        r = c.join(pct(draws[cat], "S")).join(pct(draws[cat], "S_D")).reset_index()
        rows.append(r.assign(category=cat))
        t = draws[cat].groupby(["path", "rep"]).S_D.sum() / 4 * 100
        for pth, g in t.groupby(level="path"):
            totals.append({"category": cat, "path": pth,
                           "total_loss_pct_of_annual": central[cat][central[cat].path == pth].S_D.sum() / 4 * 100,
                           "p05": g.quantile(0.05), "p95": g.quantile(0.95)})
    out = pd.concat(rows, ignore_index=True)
    out = out[["category", "path", "scenario_q", "q", "step", "in_path", "S", "S_p05", "S_p95",
               "S_D", "S_D_p05", "S_D_p95"]]
    order = {k: i for i, k in enumerate(["rice", "corn", "vegetables", "fruits", "other_food",
                                         "rice_sensitivity_no_luzon2015"])}
    out = out.sort_values(["category", "path", "scenario_q"], key=lambda s: s.map(order) if s.name == "category" else s)
    note = "provisional; direct approach, RONI only (recommended specification, differs from v5)"
    out.assign(status=note).round(6).to_csv(OUT / "food_shocks_define_ph.csv", index=False)
    tot = pd.DataFrame(totals)
    tot.assign(status=note).round(3).to_csv(OUT / "food_shocks_episode_totals.csv", index=False)

    # comparison with the two-stage approach (rice and corn), separate from the delivery
    ts = two_stage()
    cmp_dir = OUT / "comparison"
    cmp_dir.mkdir(exist_ok=True)
    cq = out[out.category.isin(["rice", "corn"])][["category", "path", "scenario_q", "S", "S_p05", "S_p95",
                                                   "S_D"]].rename(columns={
        "S": "direct_S", "S_p05": "direct_S_p05", "S_p95": "direct_S_p95", "S_D": "direct_S_D"})
    cq = cq.merge(ts, on=["category", "path", "scenario_q"], how="left")
    cmp_note = ("provisional; comparison only, not for DEFINE-PH; two-stage approach (Stage 1 Van 40db708, "
                "Stage 2 compact boosting from 2000)")
    cq.assign(status=cmp_note).round(6).to_csv(cmp_dir / "two_stage_comparison.csv", index=False)
    # totals over the quarters both approaches cover (the two-stage forecast run starts without lead-in
    # months, so its first harvest quarters are missing), direct range from its bootstrap draws
    ts = ts.dropna(subset=["two_stage_S_D"])
    t2 = (ts.groupby(["category", "path"]).two_stage_S_D.sum() / 4 * 100).rename("two_stage_total_pct")
    span = ts.groupby(["category", "path"]).scenario_q.agg(["min", "max"])
    crow = []
    for (cat, pth), (a, z) in span.iterrows():
        sel = lambda x: x[(x.path == pth) & (x.scenario_q >= a) & (x.scenario_q <= z)]  # noqa: E731
        dr = sel(draws[cat]).groupby("rep").S_D.sum() / 4 * 100
        crow.append({"category": cat, "path": pth, "quarters": f"{a}-{z}",
                     "direct_total_pct": sel(central[cat]).S_D.sum() / 4 * 100,
                     "direct_p05": dr.quantile(0.05), "direct_p95": dr.quantile(0.95),
                     "two_stage_total_pct": t2[(cat, pth)]})
    ct = pd.DataFrame(crow)
    ct["v5_rule_3_5"] = [rule(t, lo, hi) for t, lo, hi in zip(ct.two_stage_total_pct, ct.direct_p05, ct.direct_p95)]
    ct.assign(status=cmp_note).round(3).to_csv(cmp_dir / "two_stage_comparison_totals.csv", index=False)

    def tot2(cat, pth):
        r = ct[(ct.category == cat) & (ct.path == pth)].iloc[0]
        return (f"two-stage {r.two_stage_total_pct:.1f}% against direct {r.direct_total_pct:.1f}% "
                f"({r.direct_p05:.1f} to {r.direct_p95:.1f})")
    readme = f"""# El Niño production shocks for DEFINE-PH, by food category (PROVISIONAL)

Built by `scripts/deliver_food_shocks.py` (methodology v5 Section 3.5). Direct approach, RONI only
(the recommended specification, which differs from v5; see the write-up). All shocks are national,
quarterly, against the neutral path (RONI = 0), on today's conditions.

## Files
- `food_shocks_define_ph.csv`: one row per category, El Niño path and quarter.
  - `S`: share of the quarter's production lost (v5 Eq. 13a; negative = production above the neutral path).
  - `S_D`: the same, scaled for DEFINE-PH's quarters (Eq. 13b): loss as a share of a quarter-average of
    annual production. This is the input to DEFINE-PH (food shock, Eqs. D77, D105).
  - `_p05`, `_p95`: 90% range from the block bootstrap (200 draws).
  - `step`: quarters since the start of the path; `in_path`: quarter inside the El Niño path (the shocks
    continue for the 4 quarters after it, through the lags).
- `food_shocks_episode_totals.csv`: total loss over each path and the quarters after it, % of one year's
  production, with the 90% range.
- `comparison/` (**not for DEFINE-PH**): the two-stage approach for rice and corn next to the direct one,
  `two_stage_comparison.csv` by quarter (mean over Van's 73 weather draws; `_p90` the 90th percentile;
  `flag_share` the share of production where the El Niño weather goes beyond the range observed in
  1987–2025) and `two_stage_comparison_totals.csv` by path, with the outcome of the rule of v5 Section 3.5.

## Direct and two-stage approach (v5 Section 3.5)
The direct approach gives the central estimate. The two-stage result would become the upper end of the
range where it lies outside the direct 90% range. Applied to the total over each path, it lies inside for
every path, for rice and corn (e.g. 1997–98: rice {tot2('rice', '1997-98')}, corn {tot2('corn', '1997-98')}),
so only the direct estimate is delivered; the two-stage shocks are in `comparison/`. The two
approaches distribute the loss differently over the quarters: the direct corn shock is a large dry-season
loss followed by gains (the recovery seen after past El Niños), while the two-stage shock has a smaller
peak and no gains, since it only measures the effect of the weather in the growing window. The two-stage
path is therefore closer to the gross loss before recovery that SOAS asked for (their November 2026
comments); it could be used for that run if agreed with Alper. The rule is not applied quarter by quarter, which would splice
the two paths.

## Paths
The El Niño quarters (RONI ≥ 0.5) of 1997–98, 2015–16 and 2023–24, replayed under today's conditions,
a unit path (RONI +1 for four quarters from Q3), and the **C3S forecast of November 2026** for the
current episode (`C3S forecast (Nov 2026)`).

The forecast path is the one of Van's Stage 1 (dev_Van f6ddf65): RONI observed to September 2026, then
the median of the C3S members, a linear decay to zero by July 2027, and zero to June 2028
(`data/processed/c3s_path_2026-11.csv`, quarterly means). It starts in 2025Q3, so that the observed
2025–26 La Niña enters the lags: the first quarters show the end of that La Niña (small negative or
positive values), not the El Niño. Two cautions:
- The forecast peak (quarterly RONI 2.8 in 2026Q4) is above anything in the data (2.25 in 1997Q4).
  The direct model is linear in RONI, so it extrapolates the response of past episodes; the true loss
  of an episode this strong could be larger (losses accelerate in severe droughts) or smaller.
- It is a forecast: the C3S members range from about 2.7 to 3.7 at the peak (10th–90th percentiles).
  The shocks use the median path only.

## Categories
The five food types of the DEFINE-PH equations (November 2026, Section 4.1), one shock each:

| category | content |
|---|---|
| rice | palay (irrigated + rainfed) |
| corn | total corn, including feed corn |
| vegetables | the VR index: vegetables, root crops and pulses (calorie-weighted) |
| fruits | the PF index: perennial fruits (calorie-weighted) |
| other_food | **no El Niño production shock (zero)**, as in v5 |

Upper bound for rice: `rice_sensitivity_no_luzon2015`, rice estimated without the Luzon typhoon
quarters of late 2015 (write-up section 2.6).

## For the DEFINE-PH runs (v5 Section 3.5)
- **Today's climate.** The shocks are the El Niño effect under today's climate: the trends in the
  estimation keep the slow warming since the 1950s out of the El Niño effect, and the shocks do not
  include any future warming. Climate change is added to DEFINE-PH separately, by SOAS, so it can be
  combined with these shocks without double counting.
- **Check after the first run.** DEFINE-PH raises planned production after a shortfall (Eq. D76),
  while the shocks, estimated from data, already include the recovery seen after past El Niños. Realised
  production in the model may therefore fall by less than the shock in later quarters. After the first
  model run, compare the path of realised production with the shock and report any gap to SOAS.
- The shocks enter as the El Niño food shock in Eqs. D77 and D105 (`S_D`), for every quarter of the path
  and the four quarters after it.

## Caveats
- The rice shocks may be too low (typhoon rain over Luzon in late 2015; write-up section 2.6);
  `rice_sensitivity_no_luzon2015` gives an upper bound. The two-stage approach, which treats the
  observed rain as weather rather than through RONI, gives practically the same rice totals as the
  direct approach, so it does not support a large understatement; the sensitivity stays as an upper bound.
- Severe droughts are understated (1997–98 against FAOSTAT and in the validation of both approaches,
  write-up sections 2.2 and 7.5); for stress scenarios read the shocks as lower bounds.
"""
    (OUT / "README_food_shocks.md").write_text(readme)
    pd.set_option("display.width", 200)
    print(tot[tot.path != "unit RONI +1 (4 quarters from Q3)"].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
