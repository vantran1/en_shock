# v5 direct approach for corn: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop corn --set summary`. Summary set: v5 as written (base), the candidate (El Niño / La Niña split + season shift + spline trends), and the candidate with the effect changing in a step in 2000 or gradually (B_RP_today / B_RP_1995 compare them). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 | change_per_decade_RP | t_change_per_decade_RP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | ols | base | 108 | 0.000 | 0.900 |  | -0.109 | -3.397 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| corn | ols | candidate | 158 | -110.412 | 0.850 |  | -0.318 | -4.810 | -0.003 | -0.049 | 0.074 | 0.772 |  |  |  |  |  |  |  |  |  |  |
| corn | ols | step_2000 | 160 | -101.020 | 0.900 |  | -0.345 | -4.650 | 0.054 | 0.914 | 0.038 | 0.340 | -0.242 | -4.505 | 0.103 | 1.468 | -0.112 | -1.909 | -0.242 | -0.345 |  |  |
| corn | ols | gradual_linear | 160 | -95.091 | 0.900 |  | -0.270 | -3.257 | -0.043 | -0.594 | 0.115 | 1.091 |  |  |  |  |  |  | -0.270 | -0.315 | 0.015 | 0.383 |
| corn | ppml | base | 108 | 0.000 | 0.950 |  | -0.042 | -2.325 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| corn | ppml | candidate | 158 | -6202.427 | 0.550 |  | -0.304 | -4.699 | -0.002 | -0.035 | 0.109 | 2.354 |  |  |  |  |  |  |  |  |  |  |
| corn | ppml | step_2000 | 160 | -6225.208 | 0.550 |  | -0.269 | -3.312 | 0.010 | 0.125 | 0.140 | 2.840 | -0.329 | -4.526 | -0.060 | -1.419 | -0.014 | -0.276 | -0.329 | -0.269 |  |  |
| corn | ppml | gradual_linear | 160 | -6203.445 | 0.550 |  | -0.339 | -4.347 | -0.001 | -0.018 | 0.072 | 1.514 |  |  |  |  |  |  | -0.339 | -0.280 | -0.020 | -0.860 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| corn | base | 16.3 | -1.1 | -1.3 | 3.8 | 6.6 | 0.5 | 9.5 |
| corn | candidate | 8.4 | 2.7 | 9.3 | 3.3 | -0.3 | 2.7 | 4.9 |
| corn | step_2000 | 7.7 | -4.4 | 10.7 | 9.4 | -0.6 | 3.6 | 5.9 |
| corn | gradual_linear | 7.9 | 1.0 | 10.4 | 7.8 | -1.7 | 3.1 | 4.8 |