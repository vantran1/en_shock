# v5 direct approach for vr: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop vr --set one_change`. Each variant changes one choice of the base specification (v5 Eq. 4). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr | ols | base | 122 | 0.000 | 0.150 | 0.150 | 0.031 | 1.257 |  |  |  |  |
| vr | ols | split | 138 | 89.180 | 0.250 | 0.250 | -0.015 | -0.301 | 0.085 | 2.443 |  |  |
| vr | ols | season | 124 | 8.430 | 0.050 | 0.050 | 0.033 | 1.949 |  |  | 0.020 | 0.734 |
| vr | ols | trend_rq | 170 | 16.415 | 0.150 | 0.150 | 0.030 | 1.281 |  |  |  |  |
| vr | ols | trend_spline | 154 | -349.134 | 0.050 | 0.950 | -0.004 | -0.805 |  |  |  |  |
| vr | ols | lags_0_4 | 122 | -13.962 | 0.950 | 0.700 | 0.050 | 2.703 |  |  |  |  |
| vr | ols | lags_1_6 | 122 | -65.948 | 0.200 | 0.150 | 0.054 | 3.379 |  |  |  |  |
| vr | ols | pool_island | 96 | -120.632 | 0.250 | 0.200 | 0.050 | 1.999 |  |  |  |  |
| vr | ols | pool_national | 92 | -147.510 | 0.200 | 0.200 | 0.046 | 1.922 |  |  |  |  |
| vr | ppml | base | 122 | 0.000 | 0.100 | 0.050 | 0.039 | 2.177 |  |  |  |  |
| vr | ppml | split | 138 | 82.413 | 0.100 | 0.050 | 0.007 | 0.223 | 0.076 | 2.614 |  |  |
| vr | ppml | season | 124 | -17.091 | 0.100 | 0.050 | 0.062 | 4.727 |  |  | 0.015 | 0.623 |
| vr | ppml | trend_rq | 170 | 25.191 | 0.100 | 0.050 | 0.038 | 2.232 |  |  |  |  |
| vr | ppml | trend_spline | 154 | -426.813 | 0.050 | 0.950 | -0.001 | -0.229 |  |  |  |  |
| vr | ppml | lags_0_4 | 122 | 0.581 | 0.050 | 0.050 | 0.038 | 2.243 |  |  |  |  |
| vr | ppml | lags_1_6 | 122 | -88.047 | 0.250 | 0.150 | 0.049 | 3.154 |  |  |  |  |
| vr | ppml | pool_island | 96 | -37.809 | 0.050 | 0.050 | 0.036 | 2.175 |  |  |  |  |
| vr | ppml | pool_national | 92 | -39.073 | 0.050 | 0.100 | 0.035 | 2.161 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| vr | base | -7.7 | -0.9 | 6.6 | -1.9 | 7.7 |
| vr | split | -3.2 | 13.9 | 7.6 | -0.3 | 12.5 |
| vr | season | -8.2 | -0.2 | 9.9 | 3.4 | 7.3 |
| vr | trend_rq | -7.9 | -0.9 | 7.0 | -2.1 | 8.1 |
| vr | trend_spline | -2.1 | -0.3 | -2.2 | 1.6 | 2.8 |
| vr | lags_0_4 | -10.0 | 1.9 | 8.8 | -0.6 | 10.7 |
| vr | lags_1_6 | -7.0 | -1.8 | 13.4 | 3.4 | 7.6 |
| vr | pool_island | -7.7 | -0.9 | 7.0 | -1.4 | 7.6 |
| vr | pool_national | -7.5 | -1.0 | 9.5 | 2.5 | 6.7 |