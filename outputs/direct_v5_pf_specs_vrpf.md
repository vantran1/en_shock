# v5 direct approach for pf: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop pf --set vrpf`. VR / PF set: v5 as written, the rice/corn candidate (El Niño / La Niña split + season shift + spline trends + regional effects) and the candidate with one choice changed (linear trends, no season shift, effects pooled by island group or nationally, lags 1-6). Calorie index from 2010; only the 2015-16 and 2023-24 episodes are in the data. `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pf | ols | base | 122 | 0.000 | 0.450 | 0.350 | -0.010 | -2.146 |  |  |  |  |
| pf | ols | candidate | 173 | 136.465 | 0.900 | 0.950 | -0.015 | -1.092 | 0.018 | 0.886 | -0.006 | -0.360 |
| pf | ols | candidate_linear_trend | 141 | 103.625 | 0.800 | 0.950 | -0.015 | -1.381 | 0.021 | 1.317 | -0.004 | -0.181 |
| pf | ols | candidate_no_season | 170 | 148.220 | 0.750 | 0.950 | -0.014 | -1.895 | -0.018 | -1.420 |  |  |
| pf | ols | candidate_island | 134 | -98.204 | 0.900 | 0.950 | -0.008 | -0.679 | 0.033 | 1.743 | 0.000 | 0.010 |
| pf | ols | candidate_national | 128 | -136.234 | 0.900 | 0.950 | -0.011 | -0.801 | 0.027 | 1.253 | -0.003 | -0.143 |
| pf | ols | candidate_lags_1_6 | 173 | 130.941 | 0.150 | 0.950 | -0.015 | -1.362 | -0.004 | -0.181 | 0.009 | 0.367 |
| pf | ols | candidate_island_lags_1_6 | 134 | -96.409 | 0.950 | 0.950 | -0.009 | -0.719 | 0.033 | 1.794 | 0.001 | 0.037 |
| pf | ppml | base | 122 | 0.000 | 0.700 | 0.950 | -0.015 | -3.624 |  |  |  |  |
| pf | ppml | candidate | 173 | 169.243 | 0.550 | 0.950 | -0.011 | -1.036 | -0.014 | -0.889 | 0.002 | 0.160 |
| pf | ppml | candidate_linear_trend | 141 | 99.531 | 0.550 | 0.950 | -0.015 | -2.185 | -0.016 | -1.399 | -0.003 | -0.161 |
| pf | ppml | candidate_no_season | 170 | 152.313 | 0.550 | 0.950 | -0.009 | -1.196 | -0.020 | -1.755 |  |  |
| pf | ppml | candidate_island | 134 | -61.240 | 0.600 | 0.750 | -0.008 | -0.711 | -0.010 | -0.676 | -0.001 | -0.078 |
| pf | ppml | candidate_national | 128 | -98.612 | 0.200 | 0.700 | -0.017 | -1.504 | -0.004 | -0.200 | -0.001 | -0.070 |
| pf | ppml | candidate_lags_1_6 | 173 | 166.359 | 0.150 | 0.950 | -0.006 | -0.724 | -0.013 | -0.971 | 0.003 | 0.232 |
| pf | ppml | candidate_island_lags_1_6 | 134 | -69.544 | 0.100 | 0.800 | -0.006 | -0.758 | -0.013 | -0.947 | 0.004 | 0.339 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| pf | base | -0.3 | 2.1 | -0.4 | -1.6 | 1.8 |
| pf | candidate | -0.3 | -1.5 | -2.7 | -1.2 | 1.4 |
| pf | candidate_linear_trend | -0.1 | 1.8 | -0.6 | -1.6 | 1.4 |
| pf | candidate_no_season | -0.1 | -0.9 | -2.6 | -1.1 | 1.1 |
| pf | candidate_island | -0.5 | -0.5 | -2.5 | -0.5 | 1.0 |
| pf | candidate_national | -0.6 | -0.4 | -2.0 | -0.2 | 1.0 |
| pf | candidate_lags_1_6 | 0.5 | 1.1 | -1.8 | -1.6 | 0.4 |
| pf | candidate_island_lags_1_6 | 0.6 | 1.9 | -1.6 | -1.3 | 0.9 |