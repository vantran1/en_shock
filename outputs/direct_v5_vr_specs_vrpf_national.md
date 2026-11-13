# v5 direct approach for vr: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop vr --set vrpf_national`. VR / PF, second round: smooth regional trends with one national effect (best in the first round), and with one choice changed (El Niño / La Niña split, season shift, lags 1-6, effects by island group or by region). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr | ols | base | 122 | 0.000 | 0.150 | 0.150 | 0.031 | 1.257 |  |  |  |  |
| vr | ols | spline_national | 124 | -511.334 | 0.500 | 0.450 | 0.026 | 3.532 |  |  |  |  |
| vr | ols | spline_national_split | 125 | -504.418 | 0.500 | 0.450 | 0.028 | 2.453 | 0.024 | 1.491 |  |  |
| vr | ols | spline_national_season | 126 | -497.613 | 0.550 | 0.450 | 0.024 | 2.271 |  |  | 0.027 | 3.555 |
| vr | ols | spline_national_lags_1_6 | 124 | -513.944 | 0.550 | 0.500 | 0.030 | 4.280 |  |  |  |  |
| vr | ols | spline_island | 128 | -485.702 | 0.600 | 0.600 | 0.032 | 3.265 |  |  |  |  |
| vr | ols | spline_region | 154 | -349.134 | 0.050 | 0.950 | -0.004 | -0.805 |  |  |  |  |
| vr | ppml | base | 122 | 0.000 | 0.100 | 0.050 | 0.039 | 2.177 |  |  |  |  |
| vr | ppml | spline_national | 124 | -585.672 | 0.050 | 0.100 | 0.012 | 1.683 |  |  |  |  |
| vr | ppml | spline_national_split | 125 | -578.822 | 0.050 | 0.100 | 0.014 | 1.731 | 0.008 | 0.637 |  |  |
| vr | ppml | spline_national_season | 126 | -582.679 | 0.050 | 0.050 | 0.026 | 3.201 |  |  | -0.001 | -0.066 |
| vr | ppml | spline_national_lags_1_6 | 124 | -586.376 | 0.350 | 0.400 | 0.015 | 2.369 |  |  |  |  |
| vr | ppml | spline_island | 128 | -564.117 | 0.050 | 0.950 | -0.000 | -0.011 |  |  |  |  |
| vr | ppml | spline_region | 154 | -426.813 | 0.050 | 0.950 | -0.001 | -0.229 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| vr | base | -7.7 | -0.9 | 6.6 | -1.9 | 7.7 |
| vr | spline_national | -2.0 | -0.5 | -0.4 | 3.0 | 2.5 |
| vr | spline_national_split | -2.5 | -1.4 | -1.0 | 2.4 | 2.3 |
| vr | spline_national_season | -3.1 | -0.1 | -0.8 | 2.3 | 3.0 |
| vr | spline_national_lags_1_6 | -2.0 | -0.7 | -0.3 | 3.1 | 2.4 |
| vr | spline_island | -2.1 | -0.4 | -1.8 | 1.8 | 2.7 |
| vr | spline_region | -2.1 | -0.3 | -2.2 | 1.6 | 2.8 |