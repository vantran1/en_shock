# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop rice --set one_change`. Each variant changes one choice of the base specification (v5 Eq. 4). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | base | 107 | 0.000 | 0.750 |  | -0.082 | -3.463 |  |  |  |  |
| irrigated | ols | split | 123 | 68.450 | 0.750 |  | -0.171 | -3.128 | 0.011 | 0.282 |  |  |
| irrigated | ols | season | 108 | 3.097 | 0.750 |  | -0.069 | -3.242 |  |  | -0.105 | -3.069 |
| irrigated | ols | trend_rq | 155 | -295.231 | 0.750 |  | -0.079 | -3.675 |  |  |  |  |
| irrigated | ols | trend_spline | 139 | -194.377 | 0.750 |  | -0.081 | -4.601 |  |  |  |  |
| irrigated | ols | lags_0_4 | 107 | 6.731 | 0.550 |  | -0.084 | -3.465 |  |  |  |  |
| irrigated | ols | lags_1_6 | 107 | 0.893 | 0.850 |  | -0.082 | -3.431 |  |  |  |  |
| irrigated | ols | pool_island | 94 | -75.019 | 0.700 |  | -0.075 | -3.153 |  |  |  |  |
| irrigated | ols | pool_national | 92 | -87.325 | 0.700 |  | -0.082 | -3.219 |  |  |  |  |
| irrigated | ppml | base | 107 | 0.000 | 0.750 |  | -0.037 | -2.202 |  |  |  |  |
| irrigated | ppml | split | 123 | -261.080 | 0.700 |  | -0.108 | -2.334 | 0.032 | 0.983 |  |  |
| irrigated | ppml | season | 108 | 0.480 | 0.700 |  | -0.042 | -2.369 |  |  | -0.029 | -1.417 |
| irrigated | ppml | trend_rq | 155 | -3676.517 | 0.750 |  | -0.035 | -2.106 |  |  |  |  |
| irrigated | ppml | trend_spline | 139 | -3433.280 | 0.750 |  | -0.039 | -3.925 |  |  |  |  |
| irrigated | ppml | lags_0_4 | 107 | 59.143 | 0.550 |  | -0.035 | -2.036 |  |  |  |  |
| irrigated | ppml | lags_1_6 | 107 | 10.367 | 0.850 |  | -0.036 | -2.170 |  |  |  |  |
| irrigated | ppml | pool_island | 94 | 33.097 | 0.750 |  | -0.037 | -2.198 |  |  |  |  |
| irrigated | ppml | pool_national | 92 | 63.614 | 0.700 |  | -0.038 | -2.211 |  |  |  |  |
| rainfed | ols | base | 107 | 0.000 | 0.700 |  | -0.217 | -4.175 |  |  |  |  |
| rainfed | ols | split | 123 | 65.243 | 0.700 |  | -0.356 | -2.653 | -0.075 | -0.972 |  |  |
| rainfed | ols | season | 108 | 4.410 | 0.700 |  | -0.241 | -3.224 |  |  | -0.182 | -5.084 |
| rainfed | ols | trend_rq | 155 | 3.976 | 0.700 |  | -0.220 | -4.381 |  |  |  |  |
| rainfed | ols | trend_spline | 139 | 61.004 | 0.700 |  | -0.224 | -4.480 |  |  |  |  |
| rainfed | ols | lags_0_4 | 107 | 11.378 | 0.500 |  | -0.222 | -4.112 |  |  |  |  |
| rainfed | ols | lags_1_6 | 107 | 0.997 | 0.800 |  | -0.221 | -4.139 |  |  |  |  |
| rainfed | ols | pool_island | 94 | -53.696 | 0.700 |  | -0.245 | -4.539 |  |  |  |  |
| rainfed | ols | pool_national | 92 | -53.642 | 0.700 |  | -0.240 | -4.302 |  |  |  |  |
| rainfed | ppml | base | 107 | 0.000 | 0.800 |  | -0.074 | -3.801 |  |  |  |  |
| rainfed | ppml | split | 123 | -126.177 | 0.750 |  | -0.145 | -2.677 | -0.008 | -0.213 |  |  |
| rainfed | ppml | season | 108 | -32.862 | 0.800 |  | -0.102 | -4.338 |  |  | -0.048 | -1.933 |
| rainfed | ppml | trend_rq | 155 | -1835.365 | 0.800 |  | -0.073 | -3.840 |  |  |  |  |
| rainfed | ppml | trend_spline | 139 | -1237.070 | 0.800 |  | -0.080 | -5.261 |  |  |  |  |
| rainfed | ppml | lags_0_4 | 107 | 63.394 | 0.600 |  | -0.071 | -3.429 |  |  |  |  |
| rainfed | ppml | lags_1_6 | 107 | 9.184 | 0.900 |  | -0.072 | -3.829 |  |  |  |  |
| rainfed | ppml | pool_island | 94 | 137.866 | 0.800 |  | -0.073 | -3.685 |  |  |  |  |
| rainfed | ppml | pool_national | 92 | 131.553 | 0.750 |  | -0.075 | -3.549 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | base | 11.5 | 2.4 | -4.9 | 4.5 | 11.6 | 0.4 | 9.9 |
| irrigated | split | 15.0 | 8.8 | 2.2 | 16.2 | 15.4 | 5.1 | 10.2 |
| irrigated | season | 11.5 | 2.4 | -4.8 | 4.5 | 11.7 | 0.5 | 9.9 |
| irrigated | trend_rq | 10.7 | 2.4 | -5.2 | 4.2 | 12.6 | 0.3 | 10.0 |
| irrigated | trend_spline | 11.3 | 2.7 | 1.7 | 3.8 | -2.4 | 0.5 | 4.5 |
| irrigated | lags_0_4 | 11.5 | 2.2 | -4.9 | 4.4 | 11.7 | 0.3 | 9.9 |
| irrigated | lags_1_6 | 11.5 | 2.5 | -4.9 | 4.4 | 11.6 | 0.4 | 9.8 |
| irrigated | pool_island | 11.6 | 2.5 | -4.9 | 4.6 | 11.6 | 0.4 | 9.9 |
| irrigated | pool_national | 11.6 | 2.4 | -4.9 | 4.7 | 11.5 | 0.4 | 10.0 |
| rainfed | base | 27.2 | 3.6 | -1.9 | 6.5 | 6.8 | 0.9 | 12.6 |
| rainfed | split | 30.3 | 9.7 | 4.7 | 17.2 | 11.0 | 5.6 | 12.8 |
| rainfed | season | 27.2 | 3.6 | -1.6 | 6.2 | 7.2 | 1.2 | 12.5 |
| rainfed | trend_rq | 26.3 | 3.7 | -2.3 | 6.4 | 8.6 | 0.8 | 13.0 |
| rainfed | trend_spline | 23.3 | 4.2 | 7.5 | 5.7 | -7.6 | 1.1 | 9.8 |
| rainfed | lags_0_4 | 27.2 | 3.4 | -1.8 | 6.4 | 7.0 | 0.8 | 12.7 |
| rainfed | lags_1_6 | 27.2 | 3.6 | -1.9 | 6.5 | 6.8 | 0.9 | 12.6 |
| rainfed | pool_island | 27.1 | 3.8 | -2.2 | 6.7 | 6.6 | 0.8 | 12.7 |
| rainfed | pool_national | 27.1 | 3.9 | -2.3 | 6.7 | 6.7 | 0.8 | 12.7 |