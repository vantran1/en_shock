# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py`. Each variant changes one choice of the base specification (v5 Eq. 4). `ic_minus_base` < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | base | 123 | 0.000 | 0.750 | 0.950 | -0.094 | -3.428 |  |  |  |  |
| irrigated | ols | split | 139 | 61.998 | 0.800 | 0.950 | -0.191 | -3.350 | 0.007 | 0.194 |  |  |
| irrigated | ols | season | 125 | 11.364 | 0.800 | 0.950 | -0.080 | -2.838 |  |  | -0.115 | -3.108 |
| irrigated | ols | trend_rq | 171 | -295.392 | 0.750 | 0.950 | -0.088 | -3.450 |  |  |  |  |
| irrigated | ols | trend_spline | 155 | -199.341 | 0.750 | 0.950 | -0.093 | -4.566 |  |  |  |  |
| irrigated | ols | lags_0_4 | 123 | 4.649 | 0.600 | 0.950 | -0.090 | -3.506 |  |  |  |  |
| irrigated | ols | lags_1_6 | 123 | -0.152 | 0.850 | 0.050 | -0.092 | -3.572 |  |  |  |  |
| irrigated | ols | pool_island | 97 | -168.774 | 0.750 | 0.950 | -0.083 | -3.035 |  |  |  |  |
| irrigated | ols | pool_national | 93 | -194.649 | 0.750 | 0.950 | -0.091 | -3.065 |  |  |  |  |
| irrigated | ppml | base | 123 | 0.000 | 0.750 | 0.450 | -0.028 | -1.620 |  |  |  |  |
| irrigated | ppml | split | 139 | -220.018 | 0.700 | 0.450 | -0.098 | -2.072 | 0.034 | 1.030 |  |  |
| irrigated | ppml | season | 125 | -13.802 | 0.750 | 0.500 | -0.034 | -1.875 |  |  | -0.022 | -0.945 |
| irrigated | ppml | trend_rq | 171 | -3669.393 | 0.800 | 0.400 | -0.027 | -1.646 |  |  |  |  |
| irrigated | ppml | trend_spline | 155 | -3404.314 | 0.800 | 0.450 | -0.031 | -3.538 |  |  |  |  |
| irrigated | ppml | lags_0_4 | 123 | 58.978 | 0.550 | 0.350 | -0.027 | -1.474 |  |  |  |  |
| irrigated | ppml | lags_1_6 | 123 | -4.682 | 0.850 | 0.050 | -0.044 | -2.436 |  |  |  |  |
| irrigated | ppml | pool_island | 97 | -46.122 | 0.800 | 0.400 | -0.028 | -1.683 |  |  |  |  |
| irrigated | ppml | pool_national | 93 | -11.712 | 0.750 | 0.400 | -0.030 | -1.712 |  |  |  |  |
| rainfed | ols | base | 123 | 0.000 | 0.750 | 0.950 | -0.230 | -4.268 |  |  |  |  |
| rainfed | ols | split | 139 | 62.229 | 0.750 | 0.950 | -0.375 | -2.779 | -0.087 | -1.193 |  |  |
| rainfed | ols | season | 125 | 8.795 | 0.750 | 0.950 | -0.265 | -3.235 |  |  | -0.196 | -5.157 |
| rainfed | ols | trend_rq | 171 | 0.307 | 0.750 | 0.950 | -0.234 | -4.460 |  |  |  |  |
| rainfed | ols | trend_spline | 155 | 59.933 | 0.750 | 0.950 | -0.237 | -4.620 |  |  |  |  |
| rainfed | ols | lags_0_4 | 123 | -2.247 | 0.550 | 0.950 | -0.234 | -4.313 |  |  |  |  |
| rainfed | ols | lags_1_6 | 123 | 0.880 | 0.800 | 0.050 | -0.223 | -4.208 |  |  |  |  |
| rainfed | ols | pool_island | 97 | -143.911 | 0.750 | 0.950 | -0.257 | -4.755 |  |  |  |  |
| rainfed | ols | pool_national | 93 | -158.298 | 0.700 | 0.950 | -0.254 | -4.539 |  |  |  |  |
| rainfed | ppml | base | 123 | 0.000 | 0.700 | 0.050 | -0.078 | -3.830 |  |  |  |  |
| rainfed | ppml | split | 139 | -150.410 | 0.650 | 0.050 | -0.163 | -2.761 | -0.000 | -0.001 |  |  |
| rainfed | ppml | season | 125 | -33.345 | 0.700 | 0.050 | -0.108 | -4.012 |  |  | -0.053 | -2.222 |
| rainfed | ppml | trend_rq | 171 | -1834.874 | 0.700 | 0.050 | -0.076 | -3.836 |  |  |  |  |
| rainfed | ppml | trend_spline | 155 | -1242.117 | 0.700 | 0.050 | -0.084 | -5.256 |  |  |  |  |
| rainfed | ppml | lags_0_4 | 123 | 15.094 | 0.650 | 0.950 | -0.084 | -3.791 |  |  |  |  |
| rainfed | ppml | lags_1_6 | 123 | 2.382 | 0.850 | 0.050 | -0.077 | -3.575 |  |  |  |  |
| rainfed | ppml | pool_island | 97 | 95.413 | 0.750 | 0.050 | -0.076 | -3.662 |  |  |  |  |
| rainfed | ppml | pool_national | 93 | 89.662 | 0.800 | 0.950 | -0.080 | -3.646 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | base | 11.7 | 2.3 | -5.5 | 5.1 | 11.0 | -1.8 | 10.9 |
| irrigated | split | 15.2 | 8.6 | 1.5 | 16.9 | 14.7 | 2.6 | 11.4 |
| irrigated | season | 11.2 | 2.7 | -4.0 | 4.0 | 11.1 | -1.7 | 9.7 |
| irrigated | trend_rq | 10.8 | 2.3 | -4.4 | 3.9 | 12.2 | -1.3 | 10.1 |
| irrigated | trend_spline | 11.5 | 2.4 | 2.5 | 3.4 | -1.4 | 2.9 | 4.8 |
| irrigated | lags_0_4 | 11.9 | 1.9 | -5.6 | 5.0 | 10.8 | -2.7 | 11.4 |
| irrigated | lags_1_6 | 11.0 | 1.4 | -4.4 | 5.0 | 12.6 | 0.7 | 10.3 |
| irrigated | pool_island | 11.8 | 2.3 | -4.1 | 4.2 | 11.0 | -1.6 | 10.1 |
| irrigated | pool_national | 11.3 | 2.5 | -4.1 | 4.2 | 11.0 | -1.6 | 9.9 |
| rainfed | base | 27.7 | 3.2 | -2.2 | 6.7 | 6.0 | -0.8 | 13.4 |
| rainfed | split | 31.0 | 9.4 | 4.8 | 18.5 | 10.5 | 4.0 | 14.0 |
| rainfed | season | 27.8 | 3.2 | -2.2 | 6.7 | 6.3 | -0.6 | 13.5 |
| rainfed | trend_rq | 26.8 | 3.2 | -2.6 | 6.6 | 8.0 | -0.6 | 13.8 |
| rainfed | trend_spline | 24.1 | 3.6 | 7.0 | 6.2 | -8.2 | -0.3 | 9.7 |
| rainfed | lags_0_4 | 27.9 | 2.5 | -3.1 | 7.5 | 5.5 | -3.5 | 15.0 |
| rainfed | lags_1_6 | 26.9 | 3.1 | -1.5 | 6.8 | 6.3 | 0.2 | 12.7 |
| rainfed | pool_island | 27.7 | 3.5 | -3.1 | 7.3 | 5.9 | -0.7 | 13.7 |
| rainfed | pool_national | 27.6 | 3.4 | -3.2 | 7.3 | 5.9 | -1.6 | 14.1 |