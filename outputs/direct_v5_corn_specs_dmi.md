# v5 direct approach for corn: specification tests and validation (PROVISIONAL)

Built by `scripts/compare_direct_v5_rice.py --crop corn --set dmi`. With and without the DMI, on the crop's recommended specification (the DMI moves together with RONI when El Niño builds and its timing is poorly identified). `ic_minus_base` (relative to `recommended_corn`) < 0 means a better fit after charging for extra parameters (BIC for log-LS, deviance + k ln n for Poisson). El Niño effect = production-weighted national total effect of a sustained +1 °C RONI (log points; the El Niño part when El Niño and La Niña are split; a negative La Niña coefficient on RONI- means La Niña raises production).

## Specification tests

| ecosystem | model | spec | k | ic_minus_base | theta_R | theta_D | El Nino effect | t | B_RN | t_RN | B_RP_wet | t_RP_wet |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | ols | recommended_corn | 175 | 0.000 | 0.850 | 0.950 | -0.382 | -5.299 | -0.012 | -0.216 | 0.049 | 0.531 |
| corn | ols | recommended_corn_no_dmi | 158 | -112.177 | 0.850 |  | -0.318 | -4.810 | -0.003 | -0.049 | 0.074 | 0.772 |
| corn | ppml | recommended_corn | 175 | 0.000 | 0.700 | 0.950 | -0.310 | -4.777 | -0.041 | -0.724 | 0.122 | 2.587 |
| corn | ppml | recommended_corn_no_dmi | 158 | 327.980 | 0.550 |  | -0.304 | -4.699 | -0.002 | -0.035 | 0.109 | 2.354 |

## Leave-one-episode-out validation (Poisson)

Loss in % of the model's neutral path over the episode's quarters, all regions; obs = observed, pred = predicted by the model estimated without the episode.

| ecosystem | spec | obs 1997-98 | pred 1997-98 | obs 2015-16 | pred 2015-16 | obs 2023-24 | pred 2023-24 | mean abs error (pts) |
|---|---|---|---|---|---|---|---|---|
| corn | recommended_corn | 8.3 | -0.3 | 8.8 | 4.7 | -0.7 | 1.9 | 5.1 |
| corn | recommended_corn_no_dmi | 8.4 | 2.7 | 9.3 | 3.3 | -0.3 | 2.7 | 4.9 |