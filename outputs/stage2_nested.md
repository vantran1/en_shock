# Stage 2: nested choice of the model (PROVISIONAL)

Candidates fixed in advance: regression (T, SM_RZ hinges), compact boosting (9 features), full boosting (30 features), each with the weather response changing from 2000, 2005, 2010 or not at all. In every outer fold the candidate is chosen by inner cross-validation on the training years only. See scripts/select_stage2.py.

## Nested out-of-sample skill (% of the no-weather deviance removed; the whole procedure)

| series | block | episode |
|---|---|---|
| corn | 6.0 | 14.8 |
| irrigated | 5.1 | 19.3 |
| rainfed | 8.3 | 23.8 |

## Choice for the chain (inner CV on all years)

| series | config |
|---|---|
| irrigated | gbm_compact, from 2000 |
| rainfed | gbm_full, from 2000 |
| corn | gbm_compact, from 2000 |

## How often each candidate is chosen in the outer folds (of 11 per series)

| series | config | folds_chosen |
|---|---|---|
| corn | gbm_compact, from 2000 | 4 |
| corn | gbm_compact, from 2005 | 1 |
| corn | gbm_full, from 2000 | 2 |
| corn | gbm_full, from 2005 | 4 |
| irrigated | gbm_compact, from 2000 | 7 |
| irrigated | gbm_compact, from 2005 | 2 |
| irrigated | reg, from 2000 | 1 |
| irrigated | reg, from 2005 | 1 |
| rainfed | gbm_compact, from 2000 | 2 |
| rainfed | gbm_compact, from 2010 | 1 |
| rainfed | gbm_full, from 2000 | 5 |
| rainfed | gbm_full, from 2010 | 1 |
| rainfed | reg, from 2000 | 1 |
| rainfed | reg, from 2010 | 1 |

## Each candidate's own outer skill (for reference; not nested)

| series | config | block | episode |
|---|---|---|---|
| corn | gbm_compact, from 2000 | 8.8 | 18.7 |
| corn | gbm_compact, from 2005 | 6.5 | 22.4 |
| corn | gbm_compact, from 2010 | 5.8 | 25.0 |
| corn | gbm_compact, no change | 4.5 | 21.8 |
| corn | gbm_full, from 2000 | 7.0 | 5.8 |
| corn | gbm_full, from 2005 | 8.0 | 7.7 |
| corn | gbm_full, from 2010 | 5.2 | 7.2 |
| corn | gbm_full, no change | 5.0 | 5.6 |
| corn | reg, from 2000 | 0.9 | 15.2 |
| corn | reg, from 2005 | 0.2 | 16.1 |
| corn | reg, from 2010 | -0.8 | 15.9 |
| corn | reg, no change | 0.7 | 12.4 |
| irrigated | gbm_compact, from 2000 | 7.6 | 19.3 |
| irrigated | gbm_compact, from 2005 | 6.3 | 21.8 |
| irrigated | gbm_compact, from 2010 | 3.8 | 18.3 |
| irrigated | gbm_compact, no change | 3.3 | 10.6 |
| irrigated | gbm_full, from 2000 | 5.2 | 17.3 |
| irrigated | gbm_full, from 2005 | 4.4 | 17.9 |
| irrigated | gbm_full, from 2010 | 2.6 | 16.2 |
| irrigated | gbm_full, no change | 1.9 | 16.2 |
| irrigated | reg, from 2000 | 5.4 | 20.8 |
| irrigated | reg, from 2005 | 3.2 | 18.9 |
| irrigated | reg, from 2010 | 0.4 | 17.6 |
| irrigated | reg, no change | 0.8 | 10.9 |
| rainfed | gbm_compact, from 2000 | 8.5 | 18.3 |
| rainfed | gbm_compact, from 2005 | 7.8 | 19.4 |
| rainfed | gbm_compact, from 2010 | 7.5 | 19.2 |
| rainfed | gbm_compact, no change | 6.9 | 20.0 |
| rainfed | gbm_full, from 2000 | 10.5 | 23.8 |
| rainfed | gbm_full, from 2005 | 9.5 | 27.1 |
| rainfed | gbm_full, from 2010 | 9.1 | 26.6 |
| rainfed | gbm_full, no change | 6.7 | 24.7 |
| rainfed | reg, from 2000 | 7.4 | 24.5 |
| rainfed | reg, from 2005 | 2.6 | 23.0 |
| rainfed | reg, from 2010 | 5.8 | 23.2 |
| rainfed | reg, no change | 2.9 | 19.1 |

## Episodes held out, chosen model: national production vs no-weather model (%)

| series | episode | observed_% | chosen_% |
|---|---|---|---|
| corn | 1997-98 | -7.8 | -12.9 |
| corn | 2015-16 | -8.5 | -3.8 |
| corn | 2023-24 | -1.4 | -5.3 |
| irrigated | 1997-98 | -11.7 | -16.1 |
| irrigated | 2015-16 | -2.9 | -2.8 |
| irrigated | 2023-24 | -0.9 | -2.7 |
| rainfed | 1997-98 | -23.9 | -25.6 |
| rainfed | 2015-16 | -8.8 | -5.7 |
| rainfed | 2023-24 | 0.3 | -4.5 |

## Grouped importance (boosting, change from 2000): rise in held-out deviance when a mechanism's features are shuffled, % (mean, min, max over the 11 outer folds)

| series | model | group | mean | min | max |
|---|---|---|---|---|---|
| corn | gbm_compact | dry spells | 22.4 | 3.4 | 73.2 |
| corn | gbm_compact | heat | 20.8 | -2.4 | 79.1 |
| corn | gbm_compact | night heat | 4.2 | 1.5 | 7.5 |
| corn | gbm_compact | soil water | 1.5 | -1.9 | 8.5 |
| corn | gbm_compact | runoff (irrigation water) | 1.0 | -3.2 | 3.5 |
| corn | gbm_compact | rainfall | -0.3 | -3.0 | 1.8 |
| corn | gbm_full | radiation | 52.9 | 11.3 | 91.7 |
| corn | gbm_full | soil water | 15.6 | -2.3 | 34.5 |
| corn | gbm_full | heat | 14.7 | -8.2 | 40.3 |
| corn | gbm_full | dry spells | 3.2 | -4.0 | 9.7 |
| corn | gbm_full | night heat | 2.3 | -0.5 | 9.2 |
| corn | gbm_full | rainfall | 1.5 | -6.4 | 4.8 |
| corn | gbm_full | air dryness (VPD) | 0.2 | -5.6 | 4.7 |
| corn | gbm_full | runoff (irrigation water) | -0.6 | -3.4 | 2.4 |
| irrigated | gbm_compact | heat | 13.6 | -1.9 | 36.6 |
| irrigated | gbm_compact | soil water | 11.8 | -2.1 | 39.4 |
| irrigated | gbm_compact | night heat | 8.7 | 1.4 | 16.6 |
| irrigated | gbm_compact | dry spells | 0.9 | -1.8 | 5.1 |
| irrigated | gbm_compact | runoff (irrigation water) | 0.2 | -0.9 | 3.0 |
| irrigated | gbm_compact | rainfall | -0.2 | -0.9 | 0.2 |
| irrigated | gbm_full | heat | 11.5 | 1.5 | 29.5 |
| irrigated | gbm_full | radiation | 10.7 | -9.4 | 35.2 |
| irrigated | gbm_full | night heat | 7.1 | 1.0 | 16.8 |
| irrigated | gbm_full | soil water | 6.1 | -2.1 | 12.6 |
| irrigated | gbm_full | air dryness (VPD) | 1.3 | -2.8 | 7.1 |
| irrigated | gbm_full | rainfall | 0.1 | -4.3 | 5.6 |
| irrigated | gbm_full | runoff (irrigation water) | -0.1 | -0.3 | 0.0 |
| irrigated | gbm_full | dry spells | -0.4 | -2.9 | 1.3 |
| rainfed | gbm_compact | heat | 21.6 | 11.5 | 40.2 |
| rainfed | gbm_compact | soil water | 15.4 | -2.9 | 34.6 |
| rainfed | gbm_compact | runoff (irrigation water) | 12.0 | -3.5 | 29.9 |
| rainfed | gbm_compact | dry spells | 2.4 | -3.6 | 10.5 |
| rainfed | gbm_compact | night heat | 2.3 | -0.7 | 6.0 |
| rainfed | gbm_compact | rainfall | -0.2 | -3.5 | 1.7 |
| rainfed | gbm_full | radiation | 31.3 | -0.6 | 67.4 |
| rainfed | gbm_full | soil water | 25.7 | 5.0 | 50.1 |
| rainfed | gbm_full | heat | 7.2 | -1.6 | 18.5 |
| rainfed | gbm_full | night heat | 5.2 | 0.6 | 14.2 |
| rainfed | gbm_full | air dryness (VPD) | 1.0 | -5.2 | 7.8 |
| rainfed | gbm_full | rainfall | 1.0 | -6.3 | 11.7 |
| rainfed | gbm_full | dry spells | 0.2 | -1.8 | 2.3 |
| rainfed | gbm_full | runoff (irrigation water) | -0.0 | -2.0 | 1.4 |
