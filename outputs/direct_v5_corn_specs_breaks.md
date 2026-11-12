# v5 direct approach for corn: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop corn --set breaks`. Break year of the El Niño effect on the full sample: no break versus a step in 2000, 2005 or 2010 (candidate specification otherwise; B_RP = effect before the break, B_RP_today = from the break on, shift_RP_post = the change). `ic_minus_base` (relative to `no_break`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | ols | no_break | 175 | 0.000 | 0.850 | 0.950 | -0.382 | -5.299 | -0.012 | -0.216 | 0.049 | 0.531 |  |  |  |  |  |  |  |  |
| corn | ols | step_2000 | 177 | 8.344 | 0.900 | 0.950 | -0.414 | -4.873 | 0.048 | 0.755 | 0.009 | 0.075 | -0.304 | -6.445 | 0.110 | 1.438 | -0.119 | -1.940 | -0.304 | -0.414 |
| corn | ols | step_2005 | 177 | 8.144 | 0.900 | 0.950 | -0.411 | -4.679 | 0.049 | 0.820 | 0.009 | 0.071 | -0.305 | -5.918 | 0.106 | 1.258 | -0.141 | -2.050 | -0.305 | -0.411 |
| corn | ols | step_2010 | 177 | 10.085 | 0.850 | 0.950 | -0.348 | -3.432 | -0.054 | -0.803 | 0.089 | 0.792 | -0.426 | -6.396 | -0.078 | -0.888 | 0.124 | 2.025 | -0.426 | -0.348 |
| corn | ppml | no_break | 175 | 0.000 | 0.700 | 0.950 | -0.310 | -4.777 | -0.041 | -0.724 | 0.122 | 2.587 |  |  |  |  |  |  |  |  |
| corn | ppml | step_2000 | 177 | -13.315 | 0.700 | 0.950 | -0.320 | -3.918 | 0.004 | 0.055 | 0.112 | 2.002 | -0.305 | -5.064 | 0.015 | 0.292 | -0.063 | -1.034 | -0.305 | -0.320 |
| corn | ppml | step_2005 | 177 | -101.191 | 0.750 | 0.950 | -0.354 | -4.770 | 0.038 | 0.632 | 0.077 | 1.279 | -0.261 | -5.235 | 0.093 | 1.720 | -0.136 | -2.503 | -0.261 | -0.354 |
| corn | ppml | step_2010 | 177 | -3.557 | 0.700 | 0.950 | -0.283 | -3.394 | -0.062 | -0.882 | 0.145 | 2.509 | -0.328 | -4.827 | -0.045 | -0.810 | 0.044 | 0.826 | -0.328 | -0.283 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| corn | no_break | 8.3 | -0.3 | 8.8 | 4.7 | -0.7 | 1.9 | 5.1 |
| corn | step_2000 | 8.6 | -2.3 | 7.9 | 4.3 | -2.0 | 1.3 | 5.9 |
| corn | step_2005 | 11.1 | 2.7 | 5.4 | 0.7 | -4.1 | -1.4 | 5.3 |
| corn | step_2010 | 5.9 | -4.4 | 11.0 | 10.9 | 1.2 | 3.8 | 4.3 |