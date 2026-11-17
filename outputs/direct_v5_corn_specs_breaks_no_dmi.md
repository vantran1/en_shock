# v5 direct approach for corn: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop corn --set breaks`. Break year of the El Niño effect on the full sample: no break versus a step in 2000, 2005 or 2010 (candidate specification otherwise; B_RP = effect before the break, B_RP_today = from the break on, shift_RP_post = the change). `ic_minus_base` (relative to `no_break`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | ols | no_break | 158 | 0.000 | 0.850 |  | -0.318 | -4.810 | -0.003 | -0.049 | 0.074 | 0.772 |  |  |  |  |  |  |  |  |
| corn | ols | step_2000 | 160 | 9.392 | 0.900 |  | -0.345 | -4.650 | 0.054 | 0.914 | 0.038 | 0.340 | -0.242 | -4.505 | 0.103 | 1.468 | -0.112 | -1.909 | -0.242 | -0.345 |
| corn | ols | step_2005 | 160 | 9.407 | 0.900 |  | -0.341 | -4.425 | 0.053 | 0.916 | 0.038 | 0.331 | -0.242 | -4.035 | 0.099 | 1.249 | -0.128 | -1.826 | -0.242 | -0.341 |
| corn | ols | step_2010 | 160 | 8.128 | 0.800 |  | -0.292 | -3.035 | -0.053 | -0.761 | 0.102 | 0.969 | -0.396 | -6.028 | -0.104 | -1.233 | 0.151 | 2.433 | -0.396 | -0.292 |
| corn | ppml | no_break | 158 | 0.000 | 0.550 |  | -0.304 | -4.699 | -0.002 | -0.035 | 0.109 | 2.354 |  |  |  |  |  |  |  |  |
| corn | ppml | step_2000 | 160 | -22.780 | 0.550 |  | -0.269 | -3.312 | 0.010 | 0.125 | 0.140 | 2.840 | -0.329 | -4.526 | -0.060 | -1.419 | -0.014 | -0.276 | -0.329 | -0.269 |
| corn | ppml | step_2005 | 160 | -46.182 | 0.550 |  | -0.312 | -4.294 | 0.052 | 0.765 | 0.102 | 1.880 | -0.301 | -4.327 | 0.011 | 0.245 | -0.087 | -1.757 | -0.301 | -0.312 |
| corn | ppml | step_2010 | 160 | -43.161 | 0.550 |  | -0.255 | -3.153 | -0.035 | -0.436 | 0.155 | 2.997 | -0.343 | -4.467 | -0.089 | -1.897 | 0.057 | 1.204 | -0.343 | -0.255 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| corn | no_break | 8.4 | 2.7 | 9.3 | 3.3 | -0.3 | 2.7 | 4.9 |
| corn | step_2000 | 7.7 | -4.4 | 10.7 | 9.4 | -0.6 | 3.6 | 5.9 |
| corn | step_2005 | 9.7 | 2.5 | 7.9 | 4.6 | -2.6 | 1.5 | 4.8 |
| corn | step_2010 | 4.4 | -4.3 | 12.1 | 12.3 | 1.9 | 5.2 | 4.0 |