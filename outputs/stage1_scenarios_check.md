# Check of Van's Stage-1 scenario simulations (f6ddf65)

A check before the chain, not a result. Details in scripts/check_stage1_scenarios.py.

## Checks

| scenario | model | check | ok | detail |
|---|---|---|---|---|
| 1997-98 | roni | 1 structure | True | 73 draws, 30 months 1996-10 to 1999-03, 16 regions, 0 missing values |
| 1997-98 | roni | 2 RONI path = ours | True | 30 common months, max |difference| 0; Van adds 6 observed lead-in months (1996-04-01 to 1996-09-01) before our 6 zero months |
| 1997-98 | roni | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| 1997-98 | roni | 7b leading zero months: scenario = neutral | True | 6 months before 1997-04, max |scenario - neutral| 0 |
| 1997-98 | roni | 9 residual years drawn | True | 73 draws, block years 1950-2022 |
| 1997-98 | roni | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| 1997-98 | roni | 5 effects table = draws | True | max |mean effect recomputed - table| 3e-06, deterministic 7e-06 (relative to each variable's largest value) |
| 1997-98 | roni | 6 effects fade after the El Nino months | True | from 1998-10 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| 1997-98 | roni | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| 1997-98 | roni | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| 1997-98 | roni | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| 1997-98 | roni_dmi | 1 structure | True | 73 draws, 30 months 1996-10 to 1999-03, 16 regions, 0 missing values |
| 1997-98 | roni_dmi | 2 RONI path = ours | True | 30 common months, max |difference| 0; Van adds 6 observed lead-in months (1996-04-01 to 1996-09-01) before our 6 zero months |
| 1997-98 | roni_dmi | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| 1997-98 | roni_dmi | 7b leading zero months: scenario = neutral | True | 6 months before 1997-04, max |scenario - neutral| 0 |
| 1997-98 | roni_dmi | 9 residual years drawn | True | 73 draws, block years 1950-2022 |
| 1997-98 | roni_dmi | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| 1997-98 | roni_dmi | 5 effects table = draws | True | max |mean effect recomputed - table| 3e-06, deterministic 7e-06 (relative to each variable's largest value) |
| 1997-98 | roni_dmi | 6 effects fade after the El Nino months | True | from 1998-10 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| 1997-98 | roni_dmi | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| 1997-98 | roni_dmi | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| 1997-98 | roni_dmi | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| 2015-16 | roni | 1 structure | True | 73 draws, 30 months 2014-10 to 2017-03, 16 regions, 0 missing values |
| 2015-16 | roni | 2 RONI path = ours | True | 30 common months, max |difference| 0; Van adds 6 observed lead-in months (2014-04-01 to 2014-09-01) before our 6 zero months |
| 2015-16 | roni | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| 2015-16 | roni | 7b leading zero months: scenario = neutral | True | 6 months before 2015-04, max |scenario - neutral| 0 |
| 2015-16 | roni | 9 residual years drawn | True | 73 draws, block years 1950-2022 |
| 2015-16 | roni | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| 2015-16 | roni | 5 effects table = draws | True | max |mean effect recomputed - table| 3e-06, deterministic 7e-06 (relative to each variable's largest value) |
| 2015-16 | roni | 6 effects fade after the El Nino months | True | from 2016-10 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| 2015-16 | roni | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| 2015-16 | roni | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| 2015-16 | roni | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| 2015-16 | roni_dmi | 1 structure | True | 73 draws, 30 months 2014-10 to 2017-03, 16 regions, 0 missing values |
| 2015-16 | roni_dmi | 2 RONI path = ours | True | 30 common months, max |difference| 0; Van adds 6 observed lead-in months (2014-04-01 to 2014-09-01) before our 6 zero months |
| 2015-16 | roni_dmi | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| 2015-16 | roni_dmi | 7b leading zero months: scenario = neutral | True | 6 months before 2015-04, max |scenario - neutral| 0 |
| 2015-16 | roni_dmi | 9 residual years drawn | True | 73 draws, block years 1950-2022 |
| 2015-16 | roni_dmi | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| 2015-16 | roni_dmi | 5 effects table = draws | True | max |mean effect recomputed - table| 3e-06, deterministic 7e-06 (relative to each variable's largest value) |
| 2015-16 | roni_dmi | 6 effects fade after the El Nino months | True | from 2016-10 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| 2015-16 | roni_dmi | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| 2015-16 | roni_dmi | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| 2015-16 | roni_dmi | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| 2023-24 | roni | 1 structure | True | 73 draws, 27 months 2023-01 to 2025-03, 16 regions, 0 missing values |
| 2023-24 | roni | 2 RONI path = ours | True | 27 common months, max |difference| 0; Van adds 6 observed lead-in months (2022-07-01 to 2022-12-01) before our 6 zero months |
| 2023-24 | roni | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| 2023-24 | roni | 7b leading zero months: scenario = neutral | True | 6 months before 2023-07, max |scenario - neutral| 0 |
| 2023-24 | roni | 9 residual years drawn | True | 73 draws, block years 1951-2023 |
| 2023-24 | roni | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| 2023-24 | roni | 5 effects table = draws | True | max |mean effect recomputed - table| 9e-07, deterministic 7e-06 (relative to each variable's largest value) |
| 2023-24 | roni | 6 effects fade after the El Nino months | True | from 2024-10 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| 2023-24 | roni | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| 2023-24 | roni | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| 2023-24 | roni | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| 2023-24 | roni_dmi | 1 structure | True | 73 draws, 27 months 2023-01 to 2025-03, 16 regions, 0 missing values |
| 2023-24 | roni_dmi | 2 RONI path = ours | True | 27 common months, max |difference| 0; Van adds 6 observed lead-in months (2022-07-01 to 2022-12-01) before our 6 zero months |
| 2023-24 | roni_dmi | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| 2023-24 | roni_dmi | 7b leading zero months: scenario = neutral | True | 6 months before 2023-07, max |scenario - neutral| 0 |
| 2023-24 | roni_dmi | 9 residual years drawn | True | 73 draws, block years 1951-2023 |
| 2023-24 | roni_dmi | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| 2023-24 | roni_dmi | 5 effects table = draws | True | max |mean effect recomputed - table| 4e-06, deterministic 6e-06 (relative to each variable's largest value) |
| 2023-24 | roni_dmi | 6 effects fade after the El Nino months | True | from 2024-10 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| 2023-24 | roni_dmi | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| 2023-24 | roni_dmi | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| 2023-24 | roni_dmi | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| unit | roni | 1 structure | True | 73 draws, 30 months 2001-01 to 2003-06, 16 regions, 0 missing values |
| unit | roni | 2 RONI path = ours | True | 30 common months, max |difference| 0; Van adds 6 observed lead-in months (2000-07-01 to 2000-12-01) before our 6 zero months |
| unit | roni | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| unit | roni | 7b leading zero months: scenario = neutral | True | 6 months before 2001-07, max |scenario - neutral| 0 |
| unit | roni | 9 residual years drawn | True | 73 draws, block years 1951-2023 |
| unit | roni | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| unit | roni | 5 effects table = draws | True | max |mean effect recomputed - table| 2e-06, deterministic 7e-06 (relative to each variable's largest value) |
| unit | roni | 6 effects fade after the El Nino months | True | from 2003-01 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| unit | roni | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| unit | roni | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| unit | roni | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| unit | roni_dmi | 1 structure | True | 73 draws, 30 months 2001-01 to 2003-06, 16 regions, 0 missing values |
| unit | roni_dmi | 2 RONI path = ours | True | 30 common months, max |difference| 0; Van adds 6 observed lead-in months (2000-07-01 to 2000-12-01) before our 6 zero months |
| unit | roni_dmi | 3 same residual months in both runs | True | hist_date identical for every draw, month, region |
| unit | roni_dmi | 7b leading zero months: scenario = neutral | True | 6 months before 2001-07, max |scenario - neutral| 0 |
| unit | roni_dmi | 9 residual years drawn | True | 73 draws, block years 1951-2023 |
| unit | roni_dmi | 4 neutral depends on calendar month only | True | max spread across years of the same calendar month 0 |
| unit | roni_dmi | 5 effects table = draws | True | max |mean effect recomputed - table| 3e-06, deterministic 7e-06 (relative to each variable's largest value) |
| unit | roni_dmi | 6 effects fade after the El Nino months | True | from 2003-01 on: max |national mean effect| T 0.000 °C, P 0.00 mm, SM_RZ 0.0000 |
| unit | roni_dmi | 7 windows inside the tables (irrigated) | True | all harvest quarters complete |
| unit | roni_dmi | 7 windows inside the tables (rainfed) | True | all harvest quarters complete |
| unit | roni_dmi | 7 windows inside the tables (corn) | True | all harvest quarters complete |
| 1997-98 | roni | 4b neutral = neutral of the unit path | True | max |difference| 1.1e-13 (calendar months in common, same model) |
| 1997-98 | roni_dmi | 4b neutral = neutral of the unit path | True | max |difference| 1.1e-13 (calendar months in common, same model) |
| 2015-16 | roni | 4b neutral = neutral of the unit path | True | max |difference| 1.1e-13 (calendar months in common, same model) |
| 2015-16 | roni_dmi | 4b neutral = neutral of the unit path | True | max |difference| 1.1e-13 (calendar months in common, same model) |
| 2023-24 | roni | 4b neutral = neutral of the unit path | True | max |difference| 5.7e-14 (calendar months in common, same model) |
| 2023-24 | roni_dmi | 4b neutral = neutral of the unit path | True | max |difference| 5.7e-14 (calendar months in common, same model) |
| unit | roni | 4b neutral = neutral of the unit path | True | max |difference| 0 (calendar months in common, same model) |
| unit | roni_dmi | 4b neutral = neutral of the unit path | True | max |difference| 0 (calendar months in common, same model) |

## Largest national effect by scenario (RONI model; palay-weighted, scenario - neutral; mean and 10th-90th percentiles over draws)

| scenario | var | date | mean | q10 | q90 |
|---|---|---|---|---|---|
| 1997-98 | P | 1997-10-01 | -129.789 | -172.686 | -93.382 |
| 1997-98 | SM_RZ | 1998-04-01 | -0.050 | -0.050 | -0.050 |
| 1997-98 | T | 1998-04-01 | 0.739 | 0.739 | 0.739 |
| 1997-98 | VPD | 1998-04-01 | 0.244 | 0.244 | 0.244 |
| 2015-16 | P | 2015-10-01 | -114.099 | -150.979 | -83.187 |
| 2015-16 | SM_RZ | 2016-04-01 | -0.051 | -0.051 | -0.051 |
| 2015-16 | T | 2016-04-01 | 0.676 | 0.676 | 0.676 |
| 2015-16 | VPD | 2016-04-01 | 0.245 | 0.245 | 0.245 |
| 2023-24 | P | 2023-10-01 | -55.890 | -72.810 | -42.561 |
| 2023-24 | SM_RZ | 2024-05-01 | -0.030 | -0.030 | -0.030 |
| 2023-24 | T | 2024-04-01 | 0.433 | 0.433 | 0.433 |
| 2023-24 | VPD | 2024-04-01 | 0.129 | 0.129 | 0.129 |
| unit | P | 2001-10-01 | -89.130 | -116.644 | -63.881 |
| unit | SM_RZ | 2002-05-01 | -0.033 | -0.033 | -0.033 |
| unit | T | 2002-05-01 | 0.329 | 0.329 | 0.329 |
| unit | VPD | 2002-05-01 | 0.077 | 0.077 | 0.077 |

## Simulated region-months outside the range observed in 1987-2025 (% of region-months, RONI model, all draws; neutral = today's climate alone)

| var | 1997-98 neutral | 1997-98 scenario | 2015-16 neutral | 2015-16 scenario | 2023-24 neutral | 2023-24 scenario | unit neutral | unit scenario |
|---|---|---|---|---|---|---|---|---|
| CWB3 | 3.3 | 6.8 | 3.3 | 6.3 | 3.3 | 3.7 | 3.2 | 3.7 |
| E | 6.0 | 7.0 | 6.0 | 7.0 | 6.1 | 6.4 | 6.2 | 6.5 |
| P | 4.0 | 6.0 | 4.0 | 5.6 | 4.0 | 4.2 | 4.2 | 4.8 |
| PET | 4.3 | 6.6 | 4.3 | 6.2 | 4.4 | 4.8 | 4.5 | 5.0 |
| RO | 4.8 | 7.1 | 4.8 | 6.7 | 4.8 | 4.8 | 4.7 | 4.8 |
| RS | 4.1 | 6.6 | 4.1 | 6.1 | 4.2 | 4.5 | 4.3 | 4.8 |
| SM_DEEP | 21.1 | 20.0 | 21.1 | 20.0 | 19.7 | 17.9 | 18.5 | 16.4 |
| SM_RZ | 13.8 | 14.4 | 13.8 | 14.3 | 13.5 | 12.4 | 12.7 | 11.7 |
| SPEI3 | 3.3 | 6.8 | 3.3 | 6.3 | 3.3 | 3.7 | 3.2 | 3.7 |
| T | 8.4 | 13.1 | 8.4 | 12.5 | 8.3 | 11.0 | 8.1 | 10.2 |
| VPD | 5.7 | 7.6 | 5.7 | 7.6 | 5.7 | 6.2 | 5.7 | 6.1 |
