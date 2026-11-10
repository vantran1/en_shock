# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --set candidate`. Candidate = El Niño / La Niña split + season shift + spline trends + regional effects; the break variants let the El Niño and La Niña effects shift from 2000, 2005 or 2010 on (B_RP = El Niño effect in dry-season harvest quarters before the break; B_RP_post after; shift_RP_post = the change, with its t). `ic_minus_base` (relative to `candidate`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | candidate | 174 | 0.000 | 0.800 | 0.950 | -0.149 | -3.088 | -0.016 | -0.827 | -0.195 | -2.783 |  |  |  |  |  |  |
| irrigated | ols | candidate_break2000 | 176 | -10.844 | 0.750 | 0.950 | -0.220 | -4.474 | 0.004 | 0.151 | -0.241 | -3.948 | -0.066 | -2.589 | 0.154 | 3.602 | -0.059 | -1.843 |
| irrigated | ols | candidate_break2005 | 176 | -5.302 | 0.750 | 0.950 | -0.212 | -3.981 | 0.010 | 0.346 | -0.242 | -3.703 | -0.064 | -2.567 | 0.148 | 2.977 | -0.075 | -1.966 |
| irrigated | ols | candidate_break2010 | 176 | 5.756 | 0.800 | 0.950 | -0.179 | -3.174 | -0.021 | -0.967 | -0.219 | -2.993 | -0.105 | -3.969 | 0.073 | 1.501 | 0.016 | 0.475 |
| irrigated | ppml | candidate | 174 | 0.000 | 0.750 | 0.500 | -0.078 | -2.841 | -0.001 | -0.039 | -0.047 | -1.074 |  |  |  |  |  |  |
| irrigated | ppml | candidate_break2000 | 176 | -125.825 | 0.650 | 0.500 | -0.159 | -4.434 | 0.029 | 1.220 | -0.105 | -2.036 | -0.048 | -2.651 | 0.112 | 2.964 | -0.049 | -1.935 |
| irrigated | ppml | candidate_break2005 | 176 | -89.629 | 0.650 | 0.500 | -0.148 | -3.813 | 0.024 | 0.960 | -0.101 | -1.837 | -0.047 | -2.401 | 0.101 | 2.338 | -0.044 | -1.413 |
| irrigated | ppml | candidate_break2010 | 176 | -53.541 | 0.700 | 0.500 | -0.107 | -2.739 | -0.015 | -0.651 | -0.068 | -1.218 | -0.062 | -3.103 | 0.045 | 1.085 | 0.030 | 1.048 |
| rainfed | ols | candidate | 174 | 0.000 | 0.700 | 0.950 | -0.480 | -2.454 | -0.089 | -0.855 | -0.279 | -3.516 |  |  |  |  |  |  |
| rainfed | ols | candidate_break2000 | 176 | -46.936 | 0.700 | 0.950 | -0.708 | -3.531 | 0.002 | 0.015 | -0.456 | -4.298 | -0.236 | -2.355 | 0.472 | 3.417 | -0.204 | -2.144 |
| rainfed | ols | candidate_break2005 | 176 | -17.438 | 0.700 | 0.950 | -0.642 | -2.809 | -0.042 | -0.319 | -0.418 | -3.439 | -0.279 | -2.723 | 0.363 | 2.031 | -0.127 | -1.319 |
| rainfed | ols | candidate_break2010 | 176 | -16.521 | 0.700 | 0.950 | -0.630 | -2.803 | -0.060 | -0.497 | -0.405 | -3.537 | -0.291 | -2.759 | 0.338 | 2.108 | -0.065 | -0.802 |
| rainfed | ppml | candidate | 174 | 0.000 | 0.650 | 0.050 | -0.232 | -3.814 | -0.011 | -0.320 | -0.128 | -2.706 |  |  |  |  |  |  |
| rainfed | ppml | candidate_break2000 | 176 | -64.641 | 0.650 | 0.050 | -0.307 | -3.623 | 0.073 | 1.600 | -0.195 | -2.814 | -0.177 | -4.681 | 0.130 | 1.659 | -0.126 | -2.919 |
| rainfed | ppml | candidate_break2005 | 176 | -60.129 | 0.650 | 0.050 | -0.297 | -3.437 | 0.070 | 1.638 | -0.195 | -2.684 | -0.179 | -4.248 | 0.118 | 1.460 | -0.139 | -3.424 |
| rainfed | ppml | candidate_break2010 | 176 | 6.329 | 0.650 | 0.050 | -0.259 | -3.036 | 0.007 | 0.160 | -0.153 | -2.155 | -0.208 | -4.463 | 0.051 | 0.662 | -0.032 | -0.758 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | candidate | 12.9 | 4.8 | 5.1 | 9.2 | 0.4 | 5.1 | 5.6 |
| irrigated | candidate_break2000 | 13.8 | 10.6 | 2.8 | 2.3 | -0.8 | 2.1 | 2.2 |
| irrigated | candidate_break2005 | 14.1 | 7.9 | 2.9 | 3.2 | -0.3 | 2.5 | 3.0 |
| irrigated | candidate_break2010 | 12.7 | 5.8 | 5.5 | 6.9 | 1.7 | 4.9 | 3.8 |
| rainfed | candidate | 26.7 | 9.9 | 12.0 | 16.3 | -3.0 | 4.5 | 9.6 |
| rainfed | candidate_break2000 | 27.3 | 11.5 | 8.8 | 10.9 | -6.1 | 1.1 | 8.4 |
| rainfed | candidate_break2005 | 28.7 | 11.1 | 8.9 | 14.0 | -6.6 | 0.9 | 10.1 |
| rainfed | candidate_break2010 | 26.8 | 8.1 | 11.8 | 17.5 | -4.7 | 3.0 | 10.7 |