# v5 direct approach for pf: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop pf --set dmi`. With and without the DMI, on the crop's recommended specification (the DMI moves together with RONI when El Niño builds and its timing is poorly identified). `ic_minus_base` (relative to `recommended_vrpf`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t |
|---|---|---|---|---|---|---|---|---|
| pf | ols | recommended_vrpf | 124 | 0.000 | 0.050 | 0.050 | -0.012 | -1.371 |
| pf | ols | recommended_vrpf_no_dmi | 123 | -6.378 | 0.050 |  | -0.010 | -1.255 |
| pf | ppml | recommended_vrpf | 124 | 0.000 | 0.600 | 0.950 | -0.012 | -3.271 |
| pf | ppml | recommended_vrpf_no_dmi | 123 | -4.533 | 0.250 |  | -0.009 | -2.603 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| pf | recommended_vrpf | 0.1 | 1.5 | -2.1 | -0.8 | 1.3 |
| pf | recommended_vrpf_no_dmi | 0.4 | 0.9 | -2.1 | -0.1 | 1.2 |