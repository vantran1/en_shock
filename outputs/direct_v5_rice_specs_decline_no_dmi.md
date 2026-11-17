# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop rice --set decline`. Step versus gradual change of the El Niño effect, both on the candidate (El Niño / La Niña split + season shift + spline trends + regional effects): step_2000 = effects shift from 2000; gradual_linear = effects change linearly over time (B_RP = today's effect, change_per_decade_RP its rate of change). B_RP_today and B_RP_1995 compare the two (dry-season harvest). `ic_minus_base` (relative to `step_2000`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 | change_per_decade_RP | t_change_per_decade_RP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | step_2000 | 159 | 0.000 | 0.700 |  | -0.186 | -3.615 | 0.003 | 0.095 | -0.219 | -3.465 | -0.037 | -1.458 | 0.149 | 3.067 | -0.054 | -1.707 | -0.037 | -0.186 |  |  |
| irrigated | ols | gradual_linear | 159 | 9.243 | 0.700 |  | 0.004 | 0.071 | -0.066 | -1.512 | -0.028 | -0.442 |  |  |  |  |  |  | 0.004 | -0.178 | 0.060 | 1.749 |
| irrigated | ppml | step_2000 | 159 | 0.000 | 0.650 |  | -0.159 | -4.489 | 0.029 | 1.246 | -0.109 | -1.993 | -0.046 | -2.384 | 0.113 | 2.923 | -0.051 | -2.079 | -0.046 | -0.159 |  |  |
| irrigated | ppml | gradual_linear | 159 | 47.994 | 0.650 |  | -0.005 | -0.139 | -0.049 | -1.770 | 0.043 | 1.034 |  |  |  |  |  |  | -0.005 | -0.154 | 0.050 | 2.174 |
| rainfed | ols | step_2000 | 159 | 0.000 | 0.700 |  | -0.599 | -3.321 | -0.001 | -0.009 | -0.430 | -4.137 | -0.161 | -1.780 | 0.438 | 3.239 | -0.184 | -2.066 | -0.161 | -0.599 |  |  |
| rainfed | ols | gradual_linear | 159 | 25.692 | 0.650 |  | -0.090 | -0.909 | -0.235 | -3.084 | 0.117 | 0.628 |  |  |  |  |  |  | -0.090 | -0.581 | 0.164 | 1.776 |
| rainfed | ppml | step_2000 | 159 | 0.000 | 0.750 |  | -0.260 | -3.373 | 0.037 | 0.791 | -0.172 | -2.643 | -0.143 | -3.382 | 0.116 | 1.627 | -0.115 | -2.743 | -0.143 | -0.260 |  |  |
| rainfed | ppml | gradual_linear | 159 | 31.984 | 0.750 |  | -0.104 | -1.573 | -0.114 | -2.585 | -0.019 | -0.303 |  |  |  |  |  |  | -0.104 | -0.250 | 0.049 | 1.279 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | step_2000 | 13.5 | 11.0 | 2.2 | 2.9 | -1.0 | 0.4 | 1.6 |
| irrigated | gradual_linear | 13.7 | 8.0 | 2.7 | 3.8 | -3.3 | -1.7 | 2.8 |
| rainfed | step_2000 | 26.3 | 11.3 | 8.8 | 8.3 | -4.8 | 3.2 | 7.8 |
| rainfed | gradual_linear | 26.9 | 12.0 | 9.4 | 7.5 | -8.9 | 1.7 | 9.2 |