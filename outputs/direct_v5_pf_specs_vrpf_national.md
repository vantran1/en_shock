# v5 direct approach for pf: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop pf --set vrpf_national`. VR / PF, second round: smooth regional trends with one national effect (best in the first round), and with one choice changed (El Niño / La Niña split, season shift, lags 1-6, effects by island group or by region). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pf | ols | base | 122 | 0.000 | 0.450 | 0.350 | -0.010 | -2.146 |  |  |  |  |
| pf | ols | spline_national | 124 | -132.611 | 0.050 | 0.050 | -0.012 | -1.371 |  |  |  |  |
| pf | ols | spline_national_split | 125 | -125.901 | 0.050 | 0.050 | -0.017 | -1.393 | -0.007 | -0.347 |  |  |
| pf | ols | spline_national_season | 126 | -142.704 | 0.900 | 0.950 | 0.006 | 0.684 |  |  | -0.044 | -2.092 |
| pf | ols | spline_national_lags_1_6 | 124 | -134.627 | 0.200 | 0.700 | -0.014 | -1.956 |  |  |  |  |
| pf | ols | spline_island | 128 | -107.184 | 0.050 | 0.050 | -0.004 | -1.133 |  |  |  |  |
| pf | ols | spline_region | 154 | 47.621 | 0.800 | 0.950 | -0.016 | -3.011 |  |  |  |  |
| pf | ppml | base | 122 | 0.000 | 0.700 | 0.950 | -0.015 | -3.624 |  |  |  |  |
| pf | ppml | spline_national | 124 | -120.345 | 0.600 | 0.950 | -0.012 | -3.271 |  |  |  |  |
| pf | ppml | spline_national_split | 125 | -113.679 | 0.550 | 0.950 | -0.008 | -1.071 | -0.018 | -1.587 |  |  |
| pf | ppml | spline_national_season | 126 | -111.476 | 0.200 | 0.650 | -0.010 | -1.144 |  |  | -0.010 | -1.971 |
| pf | ppml | spline_national_lags_1_6 | 124 | -120.339 | 0.700 | 0.950 | -0.013 | -3.262 |  |  |  |  |
| pf | ppml | spline_island | 128 | -95.425 | 0.650 | 0.950 | -0.014 | -3.634 |  |  |  |  |
| pf | ppml | spline_region | 154 | 63.395 | 0.700 | 0.950 | -0.014 | -3.537 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| pf | base | -0.3 | 2.1 | -0.4 | -1.6 | 1.8 |
| pf | spline_national | 0.1 | 1.5 | -2.1 | -0.8 | 1.3 |
| pf | spline_national_split | -0.3 | -0.7 | -2.6 | -1.3 | 0.8 |
| pf | spline_national_season | -0.2 | 1.7 | -2.0 | -0.0 | 1.9 |
| pf | spline_national_lags_1_6 | 0.1 | 1.6 | -2.2 | -0.8 | 1.4 |
| pf | spline_island | 0.1 | 1.6 | -2.0 | 0.4 | 1.9 |
| pf | spline_region | 0.3 | 1.5 | -2.2 | -0.9 | 1.2 |