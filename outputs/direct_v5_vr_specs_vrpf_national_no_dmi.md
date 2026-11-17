# v5 direct approach for vr: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop vr --set vrpf_national`. VR / PF, second round: smooth regional trends with one national effect (best in the first round), and with one choice changed (El Niño / La Niña split, season shift, lags 1-6, effects by island group or by region). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr | ols | base | 106 | 0.000 | 0.050 |  | 0.010 | 0.467 |  |  |  |  |
| vr | ols | spline_national | 123 | -445.591 | 0.400 |  | 0.004 | 0.573 |  |  |  |  |
| vr | ols | spline_national_split | 124 | -441.217 | 0.950 |  | 0.024 | 1.692 | -0.021 | -1.527 |  |  |
| vr | ols | spline_national_season | 124 | -439.086 | 0.550 |  | -0.001 | -0.094 |  |  | 0.009 | 0.963 |
| vr | ols | spline_national_lags_1_6 | 123 | -446.054 | 0.100 |  | 0.006 | 0.708 |  |  |  |  |
| vr | ols | spline_island | 125 | -432.603 | 0.950 |  | 0.003 | 0.416 |  |  |  |  |
| vr | ols | spline_region | 138 | -364.110 | 0.050 |  | -0.004 | -0.599 |  |  |  |  |
| vr | ppml | base | 106 | 0.000 | 0.050 |  | 0.016 | 0.957 |  |  |  |  |
| vr | ppml | spline_national | 123 | -597.611 | 0.500 |  | -0.003 | -0.459 |  |  |  |  |
| vr | ppml | spline_national_split | 124 | -591.956 | 0.950 |  | 0.012 | 1.385 | -0.013 | -0.939 |  |  |
| vr | ppml | spline_national_season | 124 | -592.024 | 0.050 |  | 0.010 | 1.610 |  |  | -0.004 | -0.565 |
| vr | ppml | spline_national_lags_1_6 | 123 | -597.572 | 0.150 |  | 0.002 | 0.369 |  |  |  |  |
| vr | ppml | spline_island | 125 | -588.069 | 0.100 |  | 0.000 | 0.069 |  |  |  |  |
| vr | ppml | spline_region | 138 | -519.941 | 0.050 |  | -0.000 | -0.029 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| vr | base | -9.5 | 1.8 | 7.8 | -0.1 | 9.6 |
| vr | spline_national | -2.5 | 0.9 | -0.9 | 0.0 | 2.2 |
| vr | spline_national_split | -3.2 | -1.8 | -2.4 | -1.0 | 1.4 |
| vr | spline_national_season | -2.5 | 0.3 | -1.4 | -0.1 | 2.0 |
| vr | spline_national_lags_1_6 | -2.5 | 0.8 | -1.0 | 0.2 | 2.2 |
| vr | spline_island | -2.5 | 0.8 | -1.0 | 0.1 | 2.2 |
| vr | spline_region | -2.3 | 0.2 | -1.2 | 0.0 | 1.8 |