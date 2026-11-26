"""Agricultural production shocks for DEFINE-PH by food category (methodology v5 Section 3.5,
"Aggregation"; tracker G6). PROVISIONAL.

Inputs: the shocks of the direct approach, RONI only (scripts/shocks_direct.py:
outputs/tables/shocks_{rice,corn,vr,pf}.csv and the bootstrap draws *_bootstrap.csv), and the
rice sensitivity without the Luzon typhoon quarters of late 2015 (*_no_luzon2015).

Categories (v5 Section 3.2 and 3.5). Main delivery, the four food categories agreed by the BSP
and SOAS:
- rice            palay shock (irrigated and rainfed combined with neutral production shares)
- corn            total corn (white and yellow, including feed corn)
- veg_fruit       VR and PF combined with calorie shares (one category for vegetables and
                  fruits); vr and pf are also delivered separately
- other_food      NO El Nino production shock (v5: "A fourth category, other food, takes no El
                  Nino production shock"): zero in every quarter
Fallback, only if DEFINE-PH still has two food types (rice and other food, Eq. D74) at the
delivery (v5 Section 3.5):
- nonrice_fallback   corn, VR and PF combined with calorie shares, applied to all food except
                  rice. This assumes the items not estimated (e.g. coconut, fisheries) are hit
                  equally; the lower bound with no effect on them is nonrice_fallback x s, with s
                  the calorie share of corn, VR and PF in DEFINE-PH's other food (not known here;
                  the calorie totals used are written to the notes file for that purpose)
Sensitivity:
- rice_sensitivity_no_luzon2015   rice estimated without the Luzon regions in 2015Q4-2016Q2
                  (an upper bound; write-up section 2.6, Table 4a)

Combination (calorie shares, base 2021-2023 as for the VR and PF indices): with E_c,q the
average 2021-2023 calorie production of crop c in quarter-of-year q and E_c its annual total,
  S_q   = sum_c E_c,q S_c,q / sum_c E_c,q                (share of the quarter's production)
  S^D_q = sum_c E_c S^D_c,q / sum_c E_c                  (Eq. 13b, scaled for DEFINE-PH)
The second follows from Eq. 13b: S^D_c,q = S_c,q * 4 y_c,q / Y_c, so the combined loss as a
share of a quarter-average of annual production is the annual-calorie-weighted mean.
Ranges: the combinations are computed draw by draw on the bootstrap draws of each crop (draws
of different crops are independent re-estimations, combined by their index), then 5th-95th
percentiles.

Corn calories: PROVISIONAL factor 3,570 kcal/kg = FNRI PhilFCT "Corn grits, white" (food ID
A001, 357 kcal/100 g, edible portion 100%), the closest FNRI record to dried shelled corn
grain found while the FNRI site was unavailable (19 Nov 2026); to confirm. Corn dominates
other_food in calories (about 29,000 against about 11,000 billion kcal a year for VR + PF),
so a few percent on the factor barely moves the combined shock.

Two-stage approach and the rule of v5 Section 3.5 (26 Nov 2026): for rice and corn the two-stage
shocks (scripts/chain_two_stage.py, main variant) are added as extra columns (two_stage_*), and the
rule is applied to the total over each path: "The direct approach gives the central estimate. The
two-stage result is reported as the upper end of a range when it lies outside the 90 percent confidence
interval of the direct approach; otherwise only the direct estimate is given. If the two-stage result is
clearly smaller, the direct estimate is used ... and the difference is noted." The rule is applied to the
totals, not quarter by quarter: the two approaches distribute the loss differently over the quarters
(the direct corn shock has recovery gains after the dry-season loss, the two-stage one has none), so a
quarter-by-quarter rule would splice two different paths. The quarterly comparison is reported
(two_stage_vs_direct_90pct). The central shocks and ranges are those of the direct approach.

Run:  python scripts/deliver_food_shocks.py
Writes outputs/delivery/food_shocks_define_ph.csv (path x category x quarter),
outputs/delivery/food_shocks_episode_totals.csv, outputs/delivery/README_food_shocks.md
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

TAB, PROC = ROOT / "outputs/tables", ROOT / "data/processed"
OUT = ROOT / "outputs/delivery"
CORN_KCAL_PER_KG = 3570.0  # provisional, see the module doc
BASE = (2021, 2023)
# category -> (crop of shocks_direct.py, file suffix, series)
SINGLE = {"rice": ("rice", "", "palay"), "corn": ("corn", "", "corn"),
          "vr": ("vr", "", "vr"), "pf": ("pf", "", "pf"),
          "rice_sensitivity_no_luzon2015": ("rice", "_no_luzon2015", "palay")}
COMBINED = {"veg_fruit": ["vr", "pf"], "nonrice_fallback": ["corn", "vr", "pf"]}
ZERO = "other_food"  # the fourth category: no El Nino production shock (v5)
KEY = ["path", "scenario_q"]


def calories():
    """Average 2021-2023 calorie production (billion kcal) by crop and quarter of the year."""
    c = pd.read_csv(PROC / "crop_region_quarter.csv")
    c = c[c.period.str[:4].astype(int).between(*BASE)]
    q = c.period.str[-1].astype(int)
    vrpf = c[c.series.isin(["vr", "pf"]) & (c.variable == "energy_bkcal")]
    corn = c[(c.series == "corn") & (c.variable == "production_t")].assign(
        value=lambda d: d.value * CORN_KCAL_PER_KG * 1e-6)
    e = pd.concat([vrpf, corn]).assign(q=q).groupby(["series", "q"]).value.sum() / (BASE[1] - BASE[0] + 1)
    return e.unstack("q")  # crop x quarter of the year


def single(crop, sfx, series):
    s = pd.read_csv(TAB / f"shocks_{crop}{sfx}.csv")
    s = s[s.crop == series]
    b = pd.read_csv(TAB / f"shocks_{crop}_bootstrap{sfx}.csv")
    b = b[b.crop == series][KEY + ["rep", "S", "S_D"]]
    return s, b


def combine(parts, e, central, draws):
    """Calorie-weighted combination of crops `parts` (central rows and bootstrap draws)."""
    q_w = e.loc[parts]                       # crop x quarter of year
    a_w = e.loc[parts].sum(axis=1)           # annual
    base = central[parts[0]][KEY + ["q", "step", "in_path"]].copy()
    num_s = sum(central[c].set_index(KEY).S * central[c].set_index(KEY).q.map(q_w.loc[c]) for c in parts)
    den_s = sum(central[c].set_index(KEY).q.map(q_w.loc[c]) for c in parts)
    base = base.set_index(KEY)
    base["S"] = num_s / den_s
    base["S_D"] = sum(central[c].set_index(KEY).S_D * a_w[c] for c in parts) / a_w.sum()
    # draws, draw by draw
    d = None
    for c in parts:
        x = draws[c].merge(central[c][KEY + ["q"]], on=KEY)
        x = x.assign(ws=x.q.map(q_w.loc[c]), wa=a_w[c])
        x = x.assign(nS=x.S * x.ws, nD=x.S_D * x.wa)[KEY + ["rep", "nS", "ws", "nD", "wa"]]
        d = x if d is None else d.merge(x, on=KEY + ["rep"], suffixes=("", f"_{c}"))
    ns = d.filter(like="nS").sum(axis=1)
    ws = d.filter(like="ws").sum(axis=1)
    nd = d.filter(like="nD").sum(axis=1)
    wa = d.filter(like="wa").sum(axis=1)
    d = d[KEY + ["rep"]].assign(S=ns / ws, S_D=nd / wa)
    return base.reset_index(), d


def pct(draws, col):
    return draws.groupby(KEY)[col].quantile([0.05, 0.95]).unstack().rename(
        columns={0.05: f"{col}_p05", 0.95: f"{col}_p95"})


TWO_STAGE_PATHS = {"1997-98": "1997-98", "2015-16": "2015-16", "2023-24": "2023-24",
                   "unit": "unit RONI +1 (4 quarters from Q3)"}


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
    e = calories()
    central, draws, rows, totals = {}, {}, [], []
    for cat, (crop, sfx, series) in SINGLE.items():
        central[cat], draws[cat] = single(crop, sfx, series)
    for cat, parts in COMBINED.items():
        central[cat], draws[cat] = combine(parts, e, central, draws)
    zc = central["rice"].copy()
    zc[["S", "S_D"]] = 0.0
    zd = draws["rice"].copy()
    zd[["S", "S_D"]] = 0.0
    central[ZERO], draws[ZERO] = zc, zd
    for cat in list(SINGLE) + list(COMBINED) + [ZERO]:
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
    order = {k: i for i, k in enumerate(["rice", "corn", "veg_fruit", "other_food", "vr", "pf",
                                         "nonrice_fallback", "rice_sensitivity_no_luzon2015"])}
    out = out.sort_values(["category", "path", "scenario_q"], key=lambda s: s.map(order) if s.name == "category" else s)
    ts = two_stage()
    out = out.merge(ts, on=["category", "path", "scenario_q"], how="left")
    # running totals over the path (% of a year's production: sum of S_D / 4), so that the two approaches
    # can be compared quarter by quarter without splicing their different timings
    g = out.groupby(["category", "path"], sort=False)
    out["cum_loss_pct_of_annual"] = g.S_D.cumsum() / 4 * 100
    out["two_stage_cum_loss_pct_of_annual"] = g.two_stage_S_D.cumsum() / 4 * 100
    out["two_stage_vs_direct_90pct"] = [
        "" if pd.isna(t) else ("above" if t > hi else ("below" if t < lo else "within"))
        for t, lo, hi in zip(out.two_stage_S, out.S_p05, out.S_p95)]
    note = ("provisional; direct approach, RONI only (recommended specification, differs from v5); "
            "two_stage_* columns: two-stage approach (Stage 1 Van f6ddf65, Stage 2 compact boosting from 2000), "
            "for comparison (v5 Section 3.5 rule applied to the totals)")
    out.assign(status=note).round(6).to_csv(OUT / "food_shocks_define_ph.csv", index=False)
    tot = pd.DataFrame(totals)
    t2 = (ts.groupby(["category", "path"]).two_stage_S_D.sum() / 4 * 100).rename("two_stage_total_pct").reset_index()
    tot = tot.merge(t2, on=["category", "path"], how="left")
    tot["v5_rule_3_5"] = [rule(t, lo, hi) for t, lo, hi in zip(tot.two_stage_total_pct, tot.p05, tot.p95)]
    tot.assign(status=note).round(3).to_csv(OUT / "food_shocks_episode_totals.csv", index=False)

    kcal = e.sum(axis=1)

    def cum2(cat, pth):
        r = out[(out.category == cat) & (out.path == pth)]
        return (f"direct peak {r.cum_loss_pct_of_annual.max():.1f}% and end {r.cum_loss_pct_of_annual.iloc[-1]:.1f}%, "
                f"two-stage end {r.two_stage_cum_loss_pct_of_annual.iloc[-1]:.1f}%")

    def tot2(cat, pth):
        r = tot[(tot.category == cat) & (tot.path == pth)].iloc[0]
        return (f"two-stage {r.two_stage_total_pct:.1f}% against direct {r.total_loss_pct_of_annual:.1f}% "
                f"({r.p05:.1f} to {r.p95:.1f})")
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
  - `two_stage_*` (rice and corn only): the two-stage approach for the same path and quarter (mean over
    Van's 73 weather draws; `_p90` the 90th percentile, for stress scenarios; `flag_share` the share of
    production where the El Niño weather goes beyond the range observed in 1987–2025), and
    `two_stage_vs_direct_90pct`: where the two-stage value lies against the direct 90% range.
  - `cum_loss_pct_of_annual`, `two_stage_cum_loss_pct_of_annual`: running total of the loss from the start
    of the path to the quarter, % of a year's production. Use these to compare the two approaches over
    time: their quarterly values distribute the loss differently (see below), their running totals show
    where they converge.
- `food_shocks_episode_totals.csv`: total loss over each path and the quarters after it, % of one year's
  production, with the 90% range; for rice and corn also the two-stage total and the outcome of the rule
  of v5 Section 3.5 (`v5_rule_3_5`).

## Direct and two-stage approach (v5 Section 3.5)
The direct approach gives the central estimate. The two-stage result would become the upper end of the
range where it lies outside the direct 90% range. Applied to the total over each path, it lies inside for
every path, for rice and corn (e.g. 1997–98: rice {tot2('rice', '1997-98')}, corn {tot2('corn', '1997-98')}),
so only the direct estimate is delivered, and the two-stage columns are there for comparison. The two
approaches distribute the loss differently over the quarters: the direct corn shock is a large dry-season
loss followed by gains (the recovery seen after past El Niños), while the two-stage shock has a smaller
peak and no gains, since it only measures the effect of the weather in the growing window. The two-stage
path is therefore closer to the gross loss before recovery that SOAS asked for (their November 2026
comments); it could be used for that run if agreed with Alper. The running totals show the same thing
over time: for corn in 1997–98 the direct running total peaks after the dry-season harvests and then
falls back as the rebound comes in, while the two-stage one rises more slowly and stays; both end close
together ({cum2('corn', '1997-98')}). The rule is not applied quarter by quarter, which would splice
the two paths.

## Paths
The El Niño quarters (RONI ≥ 0.5) of 1997–98, 2015–16 and 2023–24, replayed under today's conditions,
and a unit path (RONI +1 for four quarters from Q3).

## Categories
Main delivery: the four food categories agreed by the BSP and SOAS (v5 Section 3.2).

| category | content |
|---|---|
| rice | palay (irrigated + rainfed) |
| corn | total corn, including feed corn |
| veg_fruit | vegetables and root crops (VR) and perennial fruits (PF), combined with calorie shares |
| other_food | **no El Niño production shock (zero)**, as in v5 |
| vr, pf | VR and PF separately (also delivered, v5 Section 3.5) |

Fallback, only if DEFINE-PH still has two food types (rice and other food, Eq. D74) at the delivery
(v5 Section 3.5):

| category | content |
|---|---|
| nonrice_fallback | corn + VR + PF with calorie shares, applied to all food except rice |

The fallback assumes that the items not estimated (coconut, fisheries, ...) lose as much as corn, VR
and PF. Its lower bound, with no effect on them, is `nonrice_fallback × s`, with s the calorie share of
corn, VR and PF in DEFINE-PH's other food. Calories of the estimated items, 2021–2023 average (billion
kcal a year): corn {kcal['corn']:,.0f}, VR {kcal['vr']:,.0f}, PF {kcal['pf']:,.0f}; total {kcal.sum():,.0f}.

Sensitivity: `rice_sensitivity_no_luzon2015`, rice without the Luzon typhoon quarters of late 2015,
an upper bound.

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
- Corn calorie factor provisional (FNRI A001, corn grits, white, 357 kcal/100 g), to confirm.
- The rice shocks may be too low (typhoon rain over Luzon in late 2015; write-up section 2.6);
  `rice_sensitivity_no_luzon2015` gives an upper bound. The two-stage approach, which treats the
  observed rain as weather rather than through RONI, gives practically the same rice totals as the
  direct approach, so it does not support a large understatement; the sensitivity stays as an upper bound.
- Severe droughts are understated (1997–98 against FAOSTAT and in the validation of both approaches,
  write-up sections 2.2 and 7.5); for stress scenarios read the shocks as lower bounds.
- Ranges of combined categories combine the draws of each crop by their index (independent
  re-estimations).
"""
    (OUT / "README_food_shocks.md").write_text(readme)
    pd.set_option("display.width", 200)
    print(tot[tot.path != "unit RONI +1 (4 quarters from Q3)"].round(1).to_string(index=False))
    print("\ncalories 2021-2023 (billion kcal/yr):", kcal.round(0).to_dict())


if __name__ == "__main__":
    main()
