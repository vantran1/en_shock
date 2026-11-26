# Stage 2: nested choice of the model (VR and PF) (PROVISIONAL)

Candidates fixed in advance: regression (T, SM_RZ hinges), compact boosting (9 features), full boosting (30 features), no change in the response (data from 2010). In every outer fold the candidate is chosen by inner cross-validation on the training years only. See scripts/select_stage2.py.

## Nested out-of-sample skill (% of the no-weather deviance removed; the whole procedure)

| series | block | episode |
|---|---|---|
| pf | -2.4 | -3.6 |
| vr | -3.0 | -7.6 |

## Choice for the chain (inner CV on all years)

| series | config |
|---|---|
| vr | reg, no change |
| pf | reg, no change |

## How often each candidate is chosen in the outer folds (6 per series: four 5-year blocks with data, two episodes)

| series | config | folds_chosen |
|---|---|---|
| pf | gbm_compact, no change | 6 |
| vr | gbm_compact, no change | 5 |
| vr | reg, no change | 1 |

## Each candidate's own outer skill (for reference; not nested)

| series | config | block | episode |
|---|---|---|---|
| pf | gbm_compact, no change | -2.4 | -3.6 |
| pf | gbm_full, no change | -10.3 | -15.1 |
| pf | reg, no change | 0.2 | -1.6 |
| vr | gbm_compact, no change | -3.0 | -10.7 |
| vr | gbm_full, no change | -5.5 | -12.1 |
| vr | reg, no change | -0.9 | -2.0 |

## Episodes held out, chosen model: national production vs no-weather model (%)

| series | episode | observed_% | chosen_% |
|---|---|---|---|
| pf | 2015-16 | -0.6 | -0.7 |
| pf | 2023-24 | 1.3 | -1.1 |
| vr | 2015-16 | 2.3 | -1.1 |
| vr | 2023-24 | 1.1 | -2.1 |

## Grouped importance (boosting, no change): rise in held-out deviance when a mechanism's features are shuffled, % (mean, min, max over the outer folds)

| series | model | group | mean | min | max |
|---|---|---|---|---|---|
| pf | gbm_compact | soil water | 1.9 | -0.7 | 4.0 |
| pf | gbm_compact | heat | 1.3 | -5.9 | 5.9 |
| pf | gbm_compact | night heat | 0.7 | -1.8 | 3.4 |
| pf | gbm_compact | dry spells | 0.3 | -2.0 | 2.6 |
| pf | gbm_compact | rainfall | 0.3 | -0.5 | 1.6 |
| pf | gbm_compact | runoff (irrigation water) | -0.5 | -3.4 | 0.2 |
| pf | gbm_full | radiation | 11.8 | 3.4 | 25.6 |
| pf | gbm_full | heat | 10.1 | -0.7 | 36.7 |
| pf | gbm_full | rainfall | 3.2 | -3.1 | 8.6 |
| pf | gbm_full | soil water | 1.6 | -4.6 | 6.6 |
| pf | gbm_full | air dryness (VPD) | 0.7 | -0.5 | 2.4 |
| pf | gbm_full | dry spells | 0.0 | -1.1 | 1.1 |
| pf | gbm_full | runoff (irrigation water) | -0.1 | -0.7 | 0.2 |
| pf | gbm_full | night heat | -0.6 | -4.0 | 2.9 |
| vr | gbm_compact | heat | 2.1 | -1.5 | 5.7 |
| vr | gbm_compact | night heat | 1.2 | -1.1 | 4.2 |
| vr | gbm_compact | soil water | 0.7 | -1.1 | 3.0 |
| vr | gbm_compact | dry spells | -0.0 | -0.9 | 0.6 |
| vr | gbm_compact | rainfall | 0.0 | -1.4 | 1.4 |
| vr | gbm_compact | runoff (irrigation water) | -0.2 | -1.5 | 1.4 |
| vr | gbm_full | radiation | 21.7 | 4.1 | 32.1 |
| vr | gbm_full | heat | 14.9 | 4.3 | 33.0 |
| vr | gbm_full | rainfall | 2.4 | -0.4 | 9.0 |
| vr | gbm_full | night heat | 1.8 | -0.2 | 4.2 |
| vr | gbm_full | soil water | 1.5 | -1.5 | 5.1 |
| vr | gbm_full | air dryness (VPD) | 0.9 | -0.3 | 1.8 |
| vr | gbm_full | dry spells | -0.0 | -0.8 | 0.6 |
| vr | gbm_full | runoff (irrigation water) | -0.6 | -1.5 | -0.0 |
