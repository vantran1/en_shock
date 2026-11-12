# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --set decline`. Step versus gradual change of the El Niño effect, both on the candidate (El Niño / La Niña split + season shift + spline trends + regional effects): step_2000 = effects shift from 2000; gradual_linear = effects change linearly over time (B_RP = today's effect, change_per_decade_RP its rate of change). B_RP_today and B_RP_1995 compare the two (dry-season harvest). `ic_minus_base` (relative to `step_2000`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 | change_per_decade_RP | t_change_per_decade_RP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | step_2000 | 176 | 0.000 | 0.750 | 0.950 | -0.220 | -4.474 | 0.004 | 0.151 | -0.241 | -3.948 | -0.066 | -2.589 | 0.154 | 3.602 | -0.059 | -1.843 | -0.066 | -0.220 |  |  |
| irrigated | ols | gradual_linear | 176 | 12.697 | 0.750 | 0.950 | -0.025 | -0.600 | -0.082 | -1.759 | -0.051 | -0.797 |  |  |  |  |  |  | -0.025 | -0.203 | 0.059 | 2.015 |
| irrigated | ppml | step_2000 | 176 | 0.000 | 0.650 | 0.500 | -0.159 | -4.434 | 0.029 | 1.220 | -0.105 | -2.036 | -0.048 | -2.651 | 0.112 | 2.964 | -0.049 | -1.935 | -0.048 | -0.159 |  |  |
| irrigated | ppml | gradual_linear | 176 | 47.566 | 0.650 | 0.500 | -0.008 | -0.264 | -0.036 | -1.097 | 0.042 | 1.027 |  |  |  |  |  |  | -0.008 | -0.149 | 0.047 | 2.029 |
| rainfed | ols | step_2000 | 176 | 0.000 | 0.700 | 0.950 | -0.708 | -3.531 | 0.002 | 0.015 | -0.456 | -4.298 | -0.236 | -2.355 | 0.472 | 3.417 | -0.204 | -2.144 | -0.236 | -0.708 |  |  |
| rainfed | ols | gradual_linear | 176 | 33.517 | 0.700 | 0.950 | -0.135 | -1.358 | -0.290 | -3.397 | 0.098 | 0.567 |  |  |  |  |  |  | -0.135 | -0.643 | 0.169 | 1.892 |
| rainfed | ppml | step_2000 | 176 | 0.000 | 0.650 | 0.050 | -0.307 | -3.623 | 0.073 | 1.600 | -0.195 | -2.814 | -0.177 | -4.681 | 0.130 | 1.659 | -0.126 | -2.919 | -0.177 | -0.307 |  |  |
| rainfed | ppml | gradual_linear | 176 | 33.096 | 0.650 | 0.050 | -0.141 | -2.608 | -0.108 | -2.560 | -0.036 | -0.561 |  |  |  |  |  |  | -0.141 | -0.291 | 0.050 | 1.335 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | step_2000 | 13.8 | 10.6 | 2.8 | 2.3 | -0.8 | 2.1 | 2.2 |
| irrigated | gradual_linear | 14.0 | 7.5 | 3.5 | 3.0 | -2.4 | 0.6 | 3.3 |
| rainfed | step_2000 | 27.3 | 11.5 | 8.8 | 10.9 | -6.1 | 1.1 | 8.4 |
| rainfed | gradual_linear | 28.3 | 12.2 | 10.1 | 13.5 | -12.3 | -1.8 | 10.0 |