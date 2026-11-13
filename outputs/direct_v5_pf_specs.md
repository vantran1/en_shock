# v5 direct approach for pf: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop pf --set one_change`. Each variant changes one choice of the base specification (v5 Eq. 4). `ic_minus_base` (relative to `base`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_R_wet | t_R_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pf | ols | base | 122 | 0.000 | 0.450 | 0.350 | -0.010 | -2.146 |  |  |  |  |
| pf | ols | split | 138 | 95.801 | 0.350 | 0.300 | -0.012 | -1.244 | -0.007 | -0.682 |  |  |
| pf | ols | season | 124 | -0.714 | 0.800 | 0.950 | 0.001 | 0.201 |  |  | -0.033 | -2.196 |
| pf | ols | trend_rq | 170 | -178.119 | 0.850 | 0.950 | -0.012 | -2.784 |  |  |  |  |
| pf | ols | trend_spline | 154 | 47.621 | 0.800 | 0.950 | -0.016 | -3.011 |  |  |  |  |
| pf | ols | lags_0_4 | 122 | -1.899 | 0.950 | 0.900 | -0.006 | -1.259 |  |  |  |  |
| pf | ols | lags_1_6 | 122 | -11.426 | 0.200 | 0.100 | -0.006 | -1.182 |  |  |  |  |
| pf | ols | pool_island | 96 | -157.191 | 0.500 | 0.450 | 0.004 | 0.412 |  |  |  |  |
| pf | ols | pool_national | 92 | -178.661 | 0.050 | 0.400 | -0.005 | -0.736 |  |  |  |  |
| pf | ppml | base | 122 | 0.000 | 0.700 | 0.950 | -0.015 | -3.624 |  |  |  |  |
| pf | ppml | split | 138 | 82.317 | 0.600 | 0.950 | -0.013 | -1.839 | -0.018 | -1.511 |  |  |
| pf | ppml | season | 124 | 10.794 | 0.700 | 0.950 | -0.013 | -3.512 |  |  | -0.013 | -1.326 |
| pf | ppml | trend_rq | 170 | 132.372 | 0.750 | 0.950 | -0.014 | -3.199 |  |  |  |  |
| pf | ppml | trend_spline | 154 | 63.395 | 0.700 | 0.950 | -0.014 | -3.537 |  |  |  |  |
| pf | ppml | lags_0_4 | 122 | 1.995 | 0.550 | 0.750 | -0.015 | -3.060 |  |  |  |  |
| pf | ppml | lags_1_6 | 122 | 0.382 | 0.800 | 0.950 | -0.015 | -3.421 |  |  |  |  |
| pf | ppml | pool_island | 96 | -151.106 | 0.750 | 0.950 | -0.015 | -3.784 |  |  |  |  |
| pf | ppml | pool_national | 92 | -170.690 | 0.700 | 0.950 | -0.014 | -3.294 |  |  |  |  |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| pf | base | -0.3 | 2.1 | -0.4 | -1.6 | 1.8 |
| pf | split | -0.1 | 1.8 | -0.5 | -1.5 | 1.5 |
| pf | season | -0.4 | 1.9 | -0.3 | -1.5 | 1.8 |
| pf | trend_rq | -0.6 | 1.9 | 0.0 | -1.8 | 2.2 |
| pf | trend_spline | 0.3 | 1.5 | -2.2 | -0.9 | 1.2 |
| pf | lags_0_4 | -0.3 | 2.0 | -0.4 | -1.5 | 1.7 |
| pf | lags_1_6 | -0.3 | 2.1 | -0.4 | -1.6 | 1.8 |
| pf | pool_island | -0.3 | 2.1 | -0.4 | -1.8 | 1.9 |
| pf | pool_national | -0.4 | 2.1 | -0.4 | -1.7 | 1.8 |