# El Niño production shocks for DEFINE-PH, by food category (PROVISIONAL)

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
every path, for rice and corn (e.g. 1997–98: rice two-stage 6.2% against direct 5.7% (-0.3 to 13.7), corn two-stage 9.2% against direct 9.1% (-5.6 to 16.6)),
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
