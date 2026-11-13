# v5 direct approach for vr: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop vr --set vrpf`. VR / PF set: v5 as written, the rice/corn candidate (El Niño / La Niña split + season shift + spline trends + regional effects) and the candidate with one choice changed (linear trends, no season shift, effects pooled by island group or nationally, lags 1-6). Calorie index from 2010; only the 2015-16 and 2023-24 episodes are in the data. `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vr | ols | base | 122 | 0.000 | 0.150 | 0.150 | 0.031 | 1.257 |  |  |  |  |
| vr | ols | candidate | 173 | -241.502 | 0.150 | 0.950 | -0.012 | -0.567 | -0.009 | -0.360 | 0.008 | 0.705 |
| vr | ols | candidate_linear_trend | 141 | 106.395 | 0.150 | 0.150 | -0.001 | -0.011 | 0.080 | 1.848 | -0.024 | -0.429 |
| vr | ols | candidate_no_season | 170 | -260.895 | 0.100 | 0.950 | 0.003 | 0.298 | -0.012 | -0.915 |  |  |
| vr | ols | candidate_island | 134 | -450.585 | 0.850 | 0.900 | 0.019 | 1.120 | 0.032 | 1.518 | 0.069 | 2.557 |
| vr | ols | candidate_national | 128 | -485.174 | 0.800 | 0.600 | 0.018 | 1.563 | 0.023 | 1.560 | 0.068 | 2.899 |
| vr | ols | candidate_lags_1_6 | 173 | -255.719 | 0.300 | 0.950 | -0.014 | -0.735 | 0.003 | 0.114 | 0.031 | 1.860 |
| vr | ols | candidate_island_lags_1_6 | 134 | -453.340 | 0.400 | 0.400 | -0.015 | -0.891 | 0.085 | 2.905 | 0.031 | 2.020 |
| vr | ppml | base | 122 | 0.000 | 0.100 | 0.050 | 0.039 | 2.177 |  |  |  |  |
| vr | ppml | candidate | 173 | -327.306 | 0.050 | 0.950 | -0.007 | -0.579 | 0.016 | 0.995 | 0.011 | 1.088 |
| vr | ppml | candidate_linear_trend | 141 | 72.453 | 0.100 | 0.050 | 0.023 | 0.625 | 0.101 | 3.496 | -0.010 | -0.235 |
| vr | ppml | candidate_no_season | 170 | -339.389 | 0.050 | 0.950 | 0.005 | 0.489 | -0.008 | -0.642 |  |  |
| vr | ppml | candidate_island | 134 | -540.659 | 0.050 | 0.950 | -0.007 | -0.633 | 0.014 | 0.946 | 0.018 | 2.148 |
| vr | ppml | candidate_national | 128 | -570.076 | 0.800 | 0.700 | 0.011 | 1.096 | 0.025 | 1.200 | 0.035 | 1.964 |
| vr | ppml | candidate_lags_1_6 | 173 | -337.076 | 0.350 | 0.950 | -0.006 | -0.348 | 0.019 | 0.857 | 0.021 | 1.638 |
| vr | ppml | candidate_island_lags_1_6 | 134 | -540.798 | 0.400 | 0.950 | -0.007 | -0.352 | 0.018 | 0.784 | 0.026 | 2.278 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| vr | base | -7.7 | -0.9 | 6.6 | -1.9 | 7.7 |
| vr | candidate | -2.9 | -0.7 | -1.6 | 2.8 | 3.3 |
| vr | candidate_linear_trend | -3.8 | 13.3 | 11.9 | 5.9 | 11.6 |
| vr | candidate_no_season | -3.1 | -1.9 | -1.7 | 2.2 | 2.6 |
| vr | candidate_island | -2.9 | -6.6 | -1.8 | 2.4 | 3.9 |
| vr | candidate_national | -2.4 | 2.2 | -2.3 | 1.2 | 4.1 |
| vr | candidate_lags_1_6 | -3.1 | -0.6 | -1.7 | 2.4 | 3.3 |
| vr | candidate_island_lags_1_6 | -3.1 | -6.8 | -1.9 | 2.2 | 3.9 |