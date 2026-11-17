# v5 direct approach for pf: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop pf --set vrpf_national`. VR / PF, second round: smooth regional trends with one national effect (best in the first round), and with one choice changed (El Niño / La Niña split, season shift, lags 1-6, effects by island group or by region). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pf | ols | base | 106 | 0.000 | 0.400 |  | -0.011 | -2.792 |  |  |  |  |
| pf | ols | spline_national | 123 | -43.968 | 0.050 |  | -0.010 | -1.255 |  |  |  |  |
| pf | ols | spline_national_split | 124 | -37.441 | 0.050 |  | -0.016 | -1.319 | -0.003 | -0.188 |  |  |
| pf | ols | spline_national_season | 124 | -37.155 | 0.050 |  | -0.007 | -0.497 |  |  | -0.011 | -1.218 |
| pf | ols | spline_national_lags_1_6 | 123 | -46.107 | 0.250 |  | -0.014 | -1.963 |  |  |  |  |
| pf | ols | spline_island | 125 | -31.137 | 0.050 |  | -0.005 | -1.533 |  |  |  |  |
| pf | ols | spline_region | 138 | 51.951 | 0.250 |  | -0.011 | -2.735 |  |  |  |  |
| pf | ppml | base | 106 | 0.000 | 0.500 |  | -0.011 | -3.002 |  |  |  |  |
| pf | ppml | spline_national | 123 | -35.037 | 0.250 |  | -0.009 | -2.603 |  |  |  |  |
| pf | ppml | spline_national_split | 124 | -28.344 | 0.250 |  | -0.005 | -0.737 | -0.014 | -1.402 |  |  |
| pf | ppml | spline_national_season | 124 | -28.598 | 0.250 |  | -0.014 | -1.843 |  |  | -0.008 | -1.633 |
| pf | ppml | spline_national_lags_1_6 | 123 | -36.154 | 0.450 |  | -0.012 | -3.042 |  |  |  |  |
| pf | ppml | spline_island | 125 | -22.536 | 0.400 |  | -0.010 | -2.786 |  |  |  |  |
| pf | ppml | spline_region | 138 | 56.712 | 0.450 |  | -0.010 | -2.854 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| pf | base | 0.4 | 1.3 | -0.3 | 0.0 | 0.6 |
| pf | spline_national | 0.4 | 0.9 | -2.1 | -0.1 | 1.2 |
| pf | spline_national_split | 0.0 | -0.6 | -2.2 | -0.2 | 1.3 |
| pf | spline_national_season | 0.4 | 0.9 | -2.2 | -0.1 | 1.2 |
| pf | spline_national_lags_1_6 | 0.4 | 0.9 | -2.1 | -0.2 | 1.2 |
| pf | spline_island | 0.4 | 1.0 | -2.2 | -0.0 | 1.4 |
| pf | spline_region | 0.5 | 1.0 | -2.2 | 0.0 | 1.4 |