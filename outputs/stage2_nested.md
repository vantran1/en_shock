# Stage 2: nested choice of the model (PROVISIONAL)

Candidates fixed in advance: regression (T, SM_RZ hinges), compact boosting (9 features), full boosting (30 features), each with the weather response changing from 2000, 2005, 2010 or not at all. In every outer fold the candidate is chosen by inner cross-validation on the training years only. See scripts/select_stage2.py.

## Nested out-of-sample skill (% of the no-weather deviance removed; the whole procedure)

| series | block | episode |
|---|---|---|
| corn | 7.1 | 19.3 |
| irrigated | 4.0 | 18.3 |
| rainfed | 6.4 | 22.1 |

## Choice for the chain (inner CV on all years)

| series | config |
|---|---|
| irrigated | gbm_full, from 2005 |
| rainfed | gbm_full, from 2010 |
| corn | gbm_compact, from 2000 |

## How often each candidate is chosen in the outer folds (of 11 per series)

| series | config | folds_chosen |
|---|---|---|
| corn | gbm_compact, from 2000 | 3 |
| corn | gbm_compact, from 2005 | 6 |
| corn | gbm_full, from 2000 | 1 |
| corn | gbm_full, from 2010 | 1 |
| irrigated | gbm_compact, from 2005 | 2 |
| irrigated | gbm_full, from 2005 | 3 |
| irrigated | reg, from 2000 | 4 |
| irrigated | reg, from 2005 | 2 |
| rainfed | gbm_compact, from 2000 | 2 |
| rainfed | gbm_compact, from 2005 | 4 |
| rainfed | gbm_compact, from 2010 | 1 |
| rainfed | gbm_full, from 2010 | 3 |
| rainfed | reg, from 2010 | 1 |

## Each candidate's own outer skill (for reference; not nested)

| series | config | block | episode |
|---|---|---|---|
| corn | gbm_compact, from 2000 | 9.9 | 19.3 |
| corn | gbm_compact, from 2005 | 9.1 | 20.6 |
| corn | gbm_compact, from 2010 | 7.7 | 20.0 |
| corn | gbm_compact, no change | 5.5 | 15.1 |
| corn | gbm_full, from 2000 | 6.0 | 15.6 |
| corn | gbm_full, from 2005 | 6.7 | 18.6 |
| corn | gbm_full, from 2010 | 6.4 | 17.0 |
| corn | gbm_full, no change | 4.2 | 13.2 |
| corn | reg, from 2000 | 0.9 | 15.2 |
| corn | reg, from 2005 | 0.2 | 16.1 |
| corn | reg, from 2010 | -0.8 | 15.9 |
| corn | reg, no change | 0.7 | 12.4 |
| irrigated | gbm_compact, from 2000 | 5.3 | 10.4 |
| irrigated | gbm_compact, from 2005 | 5.1 | 11.3 |
| irrigated | gbm_compact, from 2010 | 3.6 | 9.6 |
| irrigated | gbm_compact, no change | 1.1 | 1.4 |
| irrigated | gbm_full, from 2000 | 5.3 | 14.0 |
| irrigated | gbm_full, from 2005 | 5.6 | 11.8 |
| irrigated | gbm_full, from 2010 | 3.5 | 12.1 |
| irrigated | gbm_full, no change | 2.8 | 11.5 |
| irrigated | reg, from 2000 | 5.4 | 20.8 |
| irrigated | reg, from 2005 | 3.2 | 18.9 |
| irrigated | reg, from 2010 | 0.4 | 17.6 |
| irrigated | reg, no change | 0.8 | 10.9 |
| rainfed | gbm_compact, from 2000 | 8.9 | 20.3 |
| rainfed | gbm_compact, from 2005 | 8.4 | 20.4 |
| rainfed | gbm_compact, from 2010 | 8.5 | 22.7 |
| rainfed | gbm_compact, no change | 6.4 | 21.1 |
| rainfed | gbm_full, from 2000 | 8.8 | 26.4 |
| rainfed | gbm_full, from 2005 | 9.0 | 26.1 |
| rainfed | gbm_full, from 2010 | 9.2 | 25.9 |
| rainfed | gbm_full, no change | 7.1 | 23.2 |
| rainfed | reg, from 2000 | 7.4 | 24.5 |
| rainfed | reg, from 2005 | 2.6 | 23.0 |
| rainfed | reg, from 2010 | 5.8 | 23.2 |
| rainfed | reg, no change | 2.9 | 19.1 |

## Episodes held out, chosen model: national production vs no-weather model (%)

| series | episode | observed_% | chosen_% |
|---|---|---|---|
| corn | 1997-98 | -7.8 | -10.4 |
| corn | 2015-16 | -8.5 | -3.5 |
| corn | 2023-24 | -1.4 | -2.5 |
| irrigated | 1997-98 | -11.7 | -9.5 |
| irrigated | 2015-16 | -2.9 | -1.5 |
| irrigated | 2023-24 | -0.9 | -1.6 |
| rainfed | 1997-98 | -23.9 | -20.6 |
| rainfed | 2015-16 | -8.8 | -4.6 |
| rainfed | 2023-24 | 0.3 | -6.4 |

## Grouped importance (boosting, change from 2000): rise in held-out deviance when a mechanism's features are shuffled, % (mean, min, max over the 11 outer folds)

| series | model | group | mean | min | max |
|---|---|---|---|---|---|
| corn | gbm_compact | runoff (irrigation water) | 58.8 | 15.8 | 150.2 |
| corn | gbm_compact | heat | 22.0 | 3.1 | 77.3 |
| corn | gbm_compact | dry spells | 15.9 | 4.9 | 28.7 |
| corn | gbm_compact | rainfall | 12.7 | 0.4 | 24.7 |
| corn | gbm_compact | soil water | 7.4 | -0.6 | 31.7 |
| corn | gbm_compact | night heat | 1.5 | -0.3 | 3.7 |
| corn | gbm_full | runoff (irrigation water) | 43.1 | 5.1 | 99.9 |
| corn | gbm_full | soil water | 24.7 | 3.5 | 64.0 |
| corn | gbm_full | radiation | 9.6 | -2.3 | 17.6 |
| corn | gbm_full | heat | 7.0 | -6.8 | 26.8 |
| corn | gbm_full | rainfall | 4.9 | -2.4 | 10.0 |
| corn | gbm_full | dry spells | 3.9 | -4.7 | 9.9 |
| corn | gbm_full | night heat | 0.5 | -1.4 | 3.4 |
| corn | gbm_full | air dryness (VPD) | 0.4 | -6.6 | 6.3 |
| irrigated | gbm_compact | runoff (irrigation water) | 17.9 | -2.9 | 45.7 |
| irrigated | gbm_compact | soil water | 11.6 | -1.2 | 21.1 |
| irrigated | gbm_compact | heat | 11.5 | -5.5 | 23.6 |
| irrigated | gbm_compact | dry spells | 4.1 | -0.9 | 15.0 |
| irrigated | gbm_compact | night heat | 3.6 | 0.1 | 7.9 |
| irrigated | gbm_compact | rainfall | 3.3 | -4.5 | 10.2 |
| irrigated | gbm_full | soil water | 9.2 | 2.7 | 16.1 |
| irrigated | gbm_full | heat | 8.4 | -1.1 | 17.3 |
| irrigated | gbm_full | runoff (irrigation water) | 8.0 | -3.0 | 22.8 |
| irrigated | gbm_full | night heat | 3.3 | 0.3 | 7.5 |
| irrigated | gbm_full | rainfall | 3.2 | -4.3 | 8.8 |
| irrigated | gbm_full | radiation | 2.1 | -5.0 | 6.3 |
| irrigated | gbm_full | air dryness (VPD) | 0.6 | -4.3 | 6.7 |
| irrigated | gbm_full | dry spells | 0.0 | -1.3 | 1.9 |
| rainfed | gbm_compact | soil water | 26.3 | 8.3 | 55.9 |
| rainfed | gbm_compact | heat | 15.9 | 9.1 | 24.8 |
| rainfed | gbm_compact | runoff (irrigation water) | 10.4 | 1.1 | 20.3 |
| rainfed | gbm_compact | dry spells | 6.8 | -4.0 | 15.5 |
| rainfed | gbm_compact | rainfall | 3.7 | -3.6 | 10.8 |
| rainfed | gbm_compact | night heat | 1.0 | -0.8 | 3.1 |
| rainfed | gbm_full | soil water | 44.3 | 18.7 | 85.0 |
| rainfed | gbm_full | heat | 5.6 | -2.7 | 13.6 |
| rainfed | gbm_full | radiation | 5.6 | -3.5 | 19.4 |
| rainfed | gbm_full | rainfall | 5.3 | -5.1 | 12.8 |
| rainfed | gbm_full | runoff (irrigation water) | 3.6 | -1.8 | 12.2 |
| rainfed | gbm_full | night heat | 3.0 | -0.7 | 7.7 |
| rainfed | gbm_full | air dryness (VPD) | 1.1 | -4.1 | 7.6 |
| rainfed | gbm_full | dry spells | 0.9 | -1.6 | 4.2 |
