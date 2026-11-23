# Stage 2: hinge regression vs gradient boosting (PROVISIONAL)

Diagnostic for the choice of the stage 2 model (methodology v5 Section 3.4). Monthly weather only (Van's `_obs`, 349 cells, cropland weights), window means over the crop calendars. Poisson pseudo-ML, region x quarter effects, regional spline trends, exposure controls.

## Out-of-sample skill (% of the base model's deviance removed; held-out quarters, all folds)

| series | model | block | episode |
|---|---|---|---|
| corn | gbm4 | 1.7 | 10.0 |
| corn | gbm_all | 5.5 | 9.6 |
| corn | hinge | -0.3 | 15.4 |
| corn | hinge_extremes | 0.1 | 16.7 |
| corn | hinge_sm_t | 1.0 | 12.7 |
| corn | linear | 1.2 | 17.1 |
| irrigated | gbm4 | -0.3 | -0.2 |
| irrigated | gbm_all | 0.4 | 6.8 |
| irrigated | hinge | 0.7 | 11.1 |
| irrigated | hinge_extremes | -0.5 | 7.3 |
| irrigated | hinge_sm_t | 0.7 | 10.5 |
| irrigated | linear | 0.9 | 10.9 |
| rainfed | gbm4 | 1.0 | 13.5 |
| rainfed | gbm_all | 6.1 | 22.9 |
| rainfed | hinge | 1.6 | 20.3 |
| rainfed | hinge_extremes | 4.8 | 19.3 |
| rainfed | hinge_sm_t | 3.0 | 20.5 |
| rainfed | linear | 3.2 | 19.0 |

## Folds in which each model predicts best

| series | model | folds_best |
|---|---|---|
| corn | gbm4 | 1 |
| corn | gbm_all | 5 |
| corn | hinge_extremes | 1 |
| corn | hinge_sm_t | 2 |
| corn | linear | 2 |
| irrigated | gbm4 | 1 |
| irrigated | gbm_all | 5 |
| irrigated | hinge_sm_t | 4 |
| irrigated | linear | 1 |
| rainfed | gbm_all | 6 |
| rainfed | hinge_extremes | 3 |
| rainfed | hinge_sm_t | 2 |

## Episodes held out: national production anomaly against the base model (%), whole window

| series | episode | observed_% | linear_% | hinge_% | hinge_sm_t_% | hinge_extremes_% | gbm4_% | gbm_all_% |
|---|---|---|---|---|---|---|---|---|
| corn | 1997-98 | -7.8 | -6.6 | -4.8 | -5.4 | -5.6 | -6.2 | -8.3 |
| corn | 2015-16 | -8.5 | -1.6 | -3.1 | -4.4 | -1.4 | -4.9 | -2.5 |
| corn | 2023-24 | -1.4 | -2.2 | -3.3 | -4.3 | -2.1 | -1.4 | -6.0 |
| irrigated | 1997-98 | -11.7 | -3.2 | -2.9 | -3.1 | -3.2 | -3.1 | -5.6 |
| irrigated | 2015-16 | -2.9 | -2.5 | -2.5 | -2.4 | -3.0 | -2.3 | -1.8 |
| irrigated | 2023-24 | -0.9 | -3.1 | -4.3 | -3.8 | -3.9 | -6.0 | -2.8 |
| rainfed | 1997-98 | -23.9 | -8.4 | -9.8 | -8.7 | -8.9 | -9.3 | -17.0 |
| rainfed | 2015-16 | -8.8 | -7.0 | -6.0 | -7.0 | -6.4 | -6.0 | -4.4 |
| rainfed | 2023-24 | 0.3 | -6.4 | -7.9 | -7.4 | -7.3 | -7.1 | -3.4 |

## Thresholds and coefficients, full sample (DK s.e.)

| series | model | term | est | se | t | threshold |
|---|---|---|---|---|---|---|
| irrigated | linear | W_T | -0.044 | 0.024 | -1.850 | nan |
| irrigated | linear | W_VPD | -0.219 | 0.198 | -1.107 | nan |
| irrigated | linear | W_P | -0.001 | 0.000 | -3.869 | nan |
| irrigated | linear | W_SM_RZ | 1.679 | 0.514 | 3.265 | nan |
| irrigated | hinge | W_T | -0.014 | 0.027 | -0.537 | nan |
| irrigated | hinge | W_VPD | -0.457 | 0.246 | -1.856 | nan |
| irrigated | hinge | W_P | -0.001 | 0.000 | -4.669 | nan |
| irrigated | hinge | W_SM_RZ | -1.354 | 1.252 | -1.081 | nan |
| irrigated | hinge | H_T | -0.065 | 0.028 | -2.291 | 25.619 |
| irrigated | hinge | H_VPD | 0.538 | 0.184 | 2.923 | 0.736 |
| irrigated | hinge | H_P | -0.001 | 0.000 | -3.095 | 175.450 |
| irrigated | hinge | H_SM_RZ | -2.456 | 1.340 | -1.832 | 0.403 |
| irrigated | hinge_sm_t | W_T | -0.022 | 0.025 | -0.883 | nan |
| irrigated | hinge_sm_t | W_SM_RZ | -2.894 | 1.163 | -2.488 | nan |
| irrigated | hinge_sm_t | H_T | -0.055 | 0.027 | -2.001 | 25.619 |
| irrigated | hinge_sm_t | H_SM_RZ | -4.103 | 1.368 | -3.000 | 0.403 |
| irrigated | hinge_sm_t_post2000 | P_W_T | -0.037 | 0.018 | -2.042 | nan |
| irrigated | hinge_sm_t_post2000 | P_W_SM_RZ | 2.084 | 1.081 | 1.928 | nan |
| irrigated | hinge_sm_t_post2000 | P_H_T | 0.189 | 0.055 | 3.454 | nan |
| irrigated | hinge_sm_t_post2000 | P_H_SM_RZ | 4.081 | 1.376 | 2.966 | nan |
| irrigated | hinge_extremes | W_T | -0.003 | 0.031 | -0.105 | nan |
| irrigated | hinge_extremes | W_VPD | -0.071 | 0.202 | -0.354 | nan |
| irrigated | hinge_extremes | W_P | -0.001 | 0.000 | -3.342 | nan |
| irrigated | hinge_extremes | W_SM_RZ | 1.629 | 0.578 | 2.820 | nan |
| irrigated | hinge_extremes | W_T_max | -0.030 | 0.038 | -0.805 | nan |
| irrigated | hinge_extremes | W_SM_RZ_min | -2.909 | 1.049 | -2.773 | nan |
| irrigated | hinge_extremes | H_T_max | -0.023 | 0.038 | -0.621 | 25.858 |
| irrigated | hinge_extremes | H_SM_RZ_min | -2.986 | 1.055 | -2.830 | 0.383 |
| rainfed | linear | W_T | -0.083 | 0.042 | -1.972 | nan |
| rainfed | linear | W_VPD | -0.400 | 0.386 | -1.035 | nan |
| rainfed | linear | W_P | -0.000 | 0.000 | -2.222 | nan |
| rainfed | linear | W_SM_RZ | 3.765 | 0.845 | 4.457 | nan |
| rainfed | hinge | W_T | -0.096 | 0.043 | -2.232 | nan |
| rainfed | hinge | W_VPD | -0.504 | 0.459 | -1.097 | nan |
| rainfed | hinge | W_P | -0.000 | 0.000 | -1.950 | nan |
| rainfed | hinge | W_SM_RZ | 3.135 | 0.838 | 3.740 | nan |
| rainfed | hinge | H_T | -0.244 | 0.116 | -2.106 | 27.285 |
| rainfed | hinge | H_VPD | 0.843 | 0.587 | 1.436 | 0.576 |
| rainfed | hinge | H_P | -0.008 | 0.002 | -3.966 | 82.253 |
| rainfed | hinge | H_SM_RZ | -3.644 | 1.183 | -3.080 | 0.297 |
| rainfed | hinge_sm_t | W_T | -0.083 | 0.044 | -1.881 | nan |
| rainfed | hinge_sm_t | W_SM_RZ | 3.199 | 0.624 | 5.128 | nan |
| rainfed | hinge_sm_t | H_T | -0.267 | 0.109 | -2.442 | 27.285 |
| rainfed | hinge_sm_t | H_SM_RZ | -9.105 | 2.837 | -3.209 | 0.266 |
| rainfed | hinge_sm_t_post2000 | P_W_T | 0.061 | 0.014 | 4.218 | nan |
| rainfed | hinge_sm_t_post2000 | P_W_SM_RZ | -4.238 | 1.092 | -3.881 | nan |
| rainfed | hinge_sm_t_post2000 | P_H_T | 0.156 | 0.185 | 0.846 | nan |
| rainfed | hinge_sm_t_post2000 | P_H_SM_RZ | 3.137 | 4.184 | 0.750 | nan |
| rainfed | hinge_extremes | W_T | -0.004 | 0.055 | -0.064 | nan |
| rainfed | hinge_extremes | W_VPD | -0.043 | 0.376 | -0.113 | nan |
| rainfed | hinge_extremes | W_P | -0.000 | 0.000 | -1.005 | nan |
| rainfed | hinge_extremes | W_SM_RZ | 4.004 | 1.193 | 3.356 | nan |
| rainfed | hinge_extremes | W_T_max | -0.067 | 0.049 | -1.375 | nan |
| rainfed | hinge_extremes | W_SM_RZ_min | -0.697 | 0.546 | -1.276 | nan |
| rainfed | hinge_extremes | H_T_max | -0.201 | 0.110 | -1.824 | 28.134 |
| rainfed | hinge_extremes | H_SM_RZ_min | -11.335 | 2.712 | -4.180 | 0.213 |
| corn | linear | W_T | 0.070 | 0.049 | 1.432 | nan |
| corn | linear | W_VPD | -1.915 | 0.547 | -3.499 | nan |
| corn | linear | W_P | -0.000 | 0.000 | -1.582 | nan |
| corn | linear | W_SM_RZ | -1.810 | 1.001 | -1.808 | nan |
| corn | hinge | W_T | -0.059 | 0.055 | -1.069 | nan |
| corn | hinge | W_VPD | -0.065 | 0.669 | -0.098 | nan |
| corn | hinge | W_P | -0.001 | 0.000 | -3.142 | nan |
| corn | hinge | W_SM_RZ | -0.003 | 0.832 | -0.003 | nan |
| corn | hinge | H_T | 0.134 | 0.069 | 1.942 | 24.662 |
| corn | hinge | H_VPD | -2.065 | 0.638 | -3.238 | 0.537 |
| corn | hinge | H_P | -0.002 | 0.001 | -3.177 | 231.501 |
| corn | hinge | H_SM_RZ | 3.190 | 1.089 | 2.928 | 0.350 |
| corn | hinge_sm_t | W_T | 0.019 | 0.044 | 0.429 | nan |
| corn | hinge_sm_t | W_SM_RZ | 0.765 | 0.472 | 1.619 | nan |
| corn | hinge_sm_t | H_T | -0.137 | 0.064 | -2.154 | 26.006 |
| corn | hinge_sm_t | H_SM_RZ | -7.402 | 2.394 | -3.091 | 0.257 |
| corn | hinge_sm_t_post2000 | P_W_T | 0.020 | 0.010 | 1.947 | nan |
| corn | hinge_sm_t_post2000 | P_W_SM_RZ | -1.592 | 0.745 | -2.138 | nan |
| corn | hinge_sm_t_post2000 | P_H_T | -0.227 | 0.074 | -3.078 | nan |
| corn | hinge_sm_t_post2000 | P_H_SM_RZ | 12.121 | 3.218 | 3.766 | nan |
| corn | hinge_extremes | W_T | 0.056 | 0.064 | 0.883 | nan |
| corn | hinge_extremes | W_VPD | -2.015 | 0.617 | -3.263 | nan |
| corn | hinge_extremes | W_P | -0.000 | 0.000 | -2.016 | nan |
| corn | hinge_extremes | W_SM_RZ | -0.844 | 1.358 | -0.622 | nan |
| corn | hinge_extremes | W_T_max | 0.033 | 0.049 | 0.669 | nan |
| corn | hinge_extremes | W_SM_RZ_min | 0.141 | 0.765 | 0.184 | nan |
| corn | hinge_extremes | H_T_max | -0.113 | 0.056 | -2.018 | 27.392 |
| corn | hinge_extremes | H_SM_RZ_min | 1.724 | 0.818 | 2.108 | 0.331 |

## Do the weather effects change from 2000? (hinge_sm_t, Wald test, DK)

| series | test | wald | df | p_value | deviance_no_break | deviance_break |
|---|---|---|---|---|---|---|
| irrigated | weather effects (linear + hinge) shift from 2000 | 25.229 | 4 | 0.000 | 16451.883 | 15767.275 |
| rainfed | weather effects (linear + hinge) shift from 2000 | 29.322 | 4 | 0.000 | 11783.372 | 11357.228 |
| corn | weather effects (linear + hinge) shift from 2000 | 32.801 | 4 | 0.000 | 20606.263 | 20088.715 |
