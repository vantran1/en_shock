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
kcal a year): corn 29,688, VR 3,856, PF 7,356; total 40,900.

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
- The rice shocks are probably too low (typhoon rain over Luzon in late 2015; write-up section 2.6);
  `rice_sensitivity_no_luzon2015` gives an upper bound. Stage 2 is to settle this.
- Severe droughts are understated (1997–98 against FAOSTAT and in the validation); for stress scenarios
  read the shocks as lower bounds.
- Ranges of combined categories combine the draws of each crop by their index (independent
  re-estimations).
