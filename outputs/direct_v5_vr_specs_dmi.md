# v5 direct approach for vr: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop vr --set dmi`. With and without the DMI, on the crop's recommended specification (the DMI moves together with RONI when El Niño builds and its timing is poorly identified). `ic_minus_base` (relative to `recommended_vrpf`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t |
|---|---|---|---|---|---|---|---|---|
| vr | ols | recommended_vrpf | 124 | 0.000 | 0.500 | 0.450 | 0.026 | 3.532 |
| vr | ols | recommended_vrpf_no_dmi | 123 | 5.468 | 0.400 |  | 0.004 | 0.573 |
| vr | ppml | recommended_vrpf | 124 | 0.000 | 0.050 | 0.100 | 0.012 | 1.683 |
| vr | ppml | recommended_vrpf_no_dmi | 123 | 0.550 | 0.500 |  | -0.003 | -0.459 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|
| vr | recommended_vrpf | -2.0 | -0.5 | -0.4 | 3.0 | 2.5 |
| vr | recommended_vrpf_no_dmi | -2.5 | 0.9 | -0.9 | 0.0 | 2.2 |