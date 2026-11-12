# v5 direct approach for corn: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop corn --set summary`. Summary set: v5 as written (base), the candidate (El Niño / La Niña split + season shift + spline trends), and the candidate with the effect changing in a step in 2000 or gradually (B_RP_today / B_RP_1995 compare them). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 | change_per_decade_RP | t_change_per_decade_RP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | ols | base | 124 | 0.000 | 0.950 | 0.500 | -0.097 | -3.432 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| corn | ols | candidate | 175 | -112.608 | 0.850 | 0.950 | -0.382 | -5.299 | -0.012 | -0.216 | 0.049 | 0.531 |  |  |  |  |  |  |  |  |  |  |
| corn | ols | step_2000 | 177 | -104.264 | 0.900 | 0.950 | -0.414 | -4.873 | 0.048 | 0.755 | 0.009 | 0.075 | -0.304 | -6.445 | 0.110 | 1.438 | -0.119 | -1.940 | -0.304 | -0.414 |  |  |
| corn | ols | gradual_linear | 177 | -97.765 | 0.900 | 0.950 | -0.349 | -4.479 | -0.066 | -0.877 | 0.074 | 0.848 |  |  |  |  |  |  | -0.349 | -0.375 | 0.008 | 0.216 |
| corn | ppml | base | 124 | 0.000 | 0.950 | 0.700 | -0.043 | -2.058 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| corn | ppml | candidate | 175 | -6524.285 | 0.700 | 0.950 | -0.310 | -4.777 | -0.041 | -0.724 | 0.122 | 2.587 |  |  |  |  |  |  |  |  |  |  |
| corn | ppml | step_2000 | 177 | -6537.600 | 0.700 | 0.950 | -0.320 | -3.918 | 0.004 | 0.055 | 0.112 | 2.002 | -0.305 | -5.064 | 0.015 | 0.292 | -0.063 | -1.034 | -0.305 | -0.320 |  |  |
| corn | ppml | gradual_linear | 177 | -6535.169 | 0.700 | 0.950 | -0.281 | -4.535 | -0.098 | -1.464 | 0.155 | 2.393 |  |  |  |  |  |  | -0.281 | -0.335 | 0.018 | 0.715 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| corn | base | 16.3 | -0.9 | -0.5 | 2.1 | 6.0 | -1.5 | 9.1 |
| corn | candidate | 8.3 | -0.3 | 8.8 | 4.7 | -0.7 | 1.9 | 5.1 |
| corn | step_2000 | 8.6 | -2.3 | 7.9 | 4.3 | -2.0 | 1.3 | 5.9 |
| corn | gradual_linear | 9.3 | 0.7 | 7.3 | 1.8 | -5.8 | -1.6 | 6.1 |