# v5 direct approach for palay: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop rice --set candidate`. Candidate = El Niño / La Niña split + season shift + spline trends + regional effects; the break variants let the El Niño and La Niña effects shift from 2000, 2005 or 2010 on (B_RP = El Niño effect in dry-season harvest quarters before the break; B_RP_post after; shift_RP_post = the change, with its t). `ic_minus_base` (relative to `candidate`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet | B_RP_post | t_RP_post | shift_RP_post | t_shift_RP_post | shift_RN_post | t_shift_RN_post | B_RP_today | B_RP_1995 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| irrigated | ols | candidate | 157 | 0.000 | 0.750 |  | -0.119 | -3.175 | -0.016 | -0.759 | -0.177 | -2.568 |  |  |  |  |  |  |  |  |
| irrigated | ols | candidate_break2000 | 159 | -8.911 | 0.700 |  | -0.186 | -3.615 | 0.003 | 0.095 | -0.219 | -3.465 | -0.037 | -1.458 | 0.149 | 3.067 | -0.054 | -1.707 | -0.037 | -0.186 |
| irrigated | ols | candidate_break2005 | 159 | -4.555 | 0.700 |  | -0.181 | -3.438 | 0.006 | 0.194 | -0.221 | -3.281 | -0.034 | -1.301 | 0.147 | 2.690 | -0.066 | -1.712 | -0.034 | -0.181 |
| irrigated | ols | candidate_break2010 | 159 | 4.036 | 0.750 |  | -0.148 | -2.850 | -0.028 | -1.115 | -0.199 | -2.643 | -0.080 | -4.410 | 0.068 | 1.299 | 0.036 | 1.150 | -0.080 | -0.148 |
| irrigated | ppml | candidate | 157 | 0.000 | 0.700 |  | -0.087 | -2.773 | -0.002 | -0.123 | -0.051 | -1.158 |  |  |  |  |  |  |  |  |
| irrigated | ppml | candidate_break2000 | 159 | -141.793 | 0.650 |  | -0.159 | -4.489 | 0.029 | 1.246 | -0.109 | -1.993 | -0.046 | -2.384 | 0.113 | 2.923 | -0.051 | -2.079 | -0.046 | -0.159 |
| irrigated | ppml | candidate_break2005 | 159 | -103.298 | 0.650 |  | -0.149 | -3.867 | 0.025 | 1.051 | -0.106 | -1.819 | -0.046 | -2.153 | 0.104 | 2.338 | -0.049 | -1.684 | -0.046 | -0.149 |
| irrigated | ppml | candidate_break2010 | 159 | -46.773 | 0.700 |  | -0.117 | -2.984 | -0.008 | -0.381 | -0.077 | -1.342 | -0.064 | -2.965 | 0.053 | 1.248 | 0.015 | 0.534 | -0.064 | -0.117 |
| rainfed | ols | candidate | 157 | 0.000 | 0.650 |  | -0.425 | -2.345 | -0.080 | -0.731 | -0.250 | -3.169 |  |  |  |  |  |  |  |  |
| rainfed | ols | candidate_break2000 | 159 | -37.306 | 0.700 |  | -0.599 | -3.321 | -0.001 | -0.009 | -0.430 | -4.137 | -0.161 | -1.780 | 0.438 | 3.239 | -0.184 | -2.066 | -0.161 | -0.599 |
| rainfed | ols | candidate_break2005 | 159 | -11.609 | 0.650 |  | -0.563 | -2.645 | -0.047 | -0.337 | -0.373 | -3.115 | -0.235 | -2.416 | 0.328 | 1.890 | -0.091 | -0.939 | -0.235 | -0.563 |
| rainfed | ols | candidate_break2010 | 159 | -12.650 | 0.650 |  | -0.555 | -2.657 | -0.066 | -0.510 | -0.364 | -3.194 | -0.247 | -2.515 | 0.308 | 1.985 | -0.021 | -0.258 | -0.247 | -0.555 |
| rainfed | ppml | candidate | 157 | 0.000 | 0.700 |  | -0.206 | -3.515 | -0.035 | -1.022 | -0.113 | -2.431 |  |  |  |  |  |  |  |  |
| rainfed | ppml | candidate_break2000 | 159 | -50.662 | 0.750 |  | -0.260 | -3.373 | 0.037 | 0.791 | -0.172 | -2.643 | -0.143 | -3.382 | 0.116 | 1.627 | -0.115 | -2.743 | -0.143 | -0.260 |
| rainfed | ppml | candidate_break2005 | 159 | -46.916 | 0.700 |  | -0.262 | -3.144 | 0.037 | 0.804 | -0.172 | -2.466 | -0.158 | -3.389 | 0.104 | 1.348 | -0.125 | -2.938 | -0.158 | -0.262 |
| rainfed | ppml | candidate_break2010 | 159 | 9.257 | 0.700 |  | -0.229 | -2.819 | -0.028 | -0.605 | -0.134 | -1.942 | -0.185 | -3.833 | 0.044 | 0.601 | -0.013 | -0.298 | -0.185 | -0.229 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| irrigated | candidate | 12.5 | 5.1 | 4.6 | 9.5 | 0.2 | 2.9 | 5.0 |
| irrigated | candidate_break2000 | 13.5 | 11.0 | 2.2 | 2.9 | -1.0 | 0.4 | 1.6 |
| irrigated | candidate_break2005 | 13.8 | 8.4 | 2.5 | 4.1 | -0.6 | 0.7 | 2.8 |
| irrigated | candidate_break2010 | 12.4 | 6.1 | 4.7 | 7.9 | 1.0 | 2.2 | 3.6 |
| rainfed | candidate | 25.8 | 10.0 | 11.8 | 14.2 | -2.2 | 5.6 | 8.7 |
| rainfed | candidate_break2000 | 26.3 | 11.3 | 8.8 | 8.3 | -4.8 | 3.2 | 7.8 |
| rainfed | candidate_break2005 | 27.6 | 12.1 | 8.8 | 10.7 | -5.1 | 3.3 | 8.6 |
| rainfed | candidate_break2010 | 25.7 | 9.3 | 11.5 | 13.3 | -3.0 | 5.0 | 8.7 |