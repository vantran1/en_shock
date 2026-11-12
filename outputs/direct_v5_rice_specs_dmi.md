# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop rice --set dmi`. With and without the DMI, on the crop's recommended specification (the DMI moves together with RONI when El Niño builds and its timing is poorly identified). `ic_minus_base` (relative to `recommended`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | recommended | 176 | 0.000 | 0.750 | 0.950 | -0.220 | -4.474 | 0.004 | 0.151 | -0.241 | -3.948 | -0.066 | -2.589 | 0.154 | 3.602 | -0.059 | -1.843 | -0.066 | -0.220 |
| irrigated | ols | recommended_no_dmi | 159 | -104.070 | 0.700 |  | -0.186 | -3.615 | 0.003 | 0.095 | -0.219 | -3.465 | -0.037 | -1.458 | 0.149 | 3.067 | -0.054 | -1.707 | -0.037 | -0.186 |
| irrigated | ppml | recommended | 176 | 0.000 | 0.650 | 0.500 | -0.159 | -4.434 | 0.029 | 1.220 | -0.105 | -2.036 | -0.048 | -2.651 | 0.112 | 2.964 | -0.049 | -1.935 | -0.048 | -0.159 |
| irrigated | ppml | recommended_no_dmi | 159 | -49.387 | 0.650 |  | -0.159 | -4.489 | 0.029 | 1.246 | -0.109 | -1.993 | -0.046 | -2.384 | 0.113 | 2.923 | -0.051 | -2.079 | -0.046 | -0.159 |
| rainfed | ols | recommended | 176 | 0.000 | 0.700 | 0.950 | -0.708 | -3.531 | 0.002 | 0.015 | -0.456 | -4.298 | -0.236 | -2.355 | 0.472 | 3.417 | -0.204 | -2.144 | -0.236 | -0.708 |
| rainfed | ols | recommended_no_dmi | 159 | -90.204 | 0.700 |  | -0.599 | -3.321 | -0.001 | -0.009 | -0.430 | -4.137 | -0.161 | -1.780 | 0.438 | 3.239 | -0.184 | -2.066 | -0.161 | -0.599 |
| rainfed | ppml | recommended | 176 | 0.000 | 0.650 | 0.050 | -0.307 | -3.623 | 0.073 | 1.600 | -0.195 | -2.814 | -0.177 | -4.681 | 0.130 | 1.659 | -0.126 | -2.919 | -0.177 | -0.307 |
| rainfed | ppml | recommended_no_dmi | 159 | 30.275 | 0.750 |  | -0.260 | -3.373 | 0.037 | 0.791 | -0.172 | -2.643 | -0.143 | -3.382 | 0.116 | 1.627 | -0.115 | -2.743 | -0.143 | -0.260 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | recommended | 13.8 | 10.6 | 2.8 | 2.3 | -0.8 | 2.1 | 2.2 |
| irrigated | recommended_no_dmi | 13.5 | 11.0 | 2.2 | 2.9 | -1.0 | 0.4 | 1.6 |
| rainfed | recommended | 27.3 | 11.5 | 8.8 | 10.9 | -6.1 | 1.1 | 8.4 |
| rainfed | recommended_no_dmi | 26.3 | 11.3 | 8.8 | 8.3 | -4.8 | 3.2 | 7.8 |