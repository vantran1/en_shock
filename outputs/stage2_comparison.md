# Stage 2: hinge regression vs gradient boosting (PROVISIONAL)

Diagnostic for the choice of the stage 2 model (methodology v5 Section 3.4). Monthly weather only (Van's `_obs`, 349 cells, cropland weights), window means over the crop calendars. Poisson pseudo-ML, region x quarter effects, regional spline trends, exposure controls.

## Out-of-sample skill (% of the base model's deviance removed; held-out quarters, all folds)

| series | model | block | episode |
|---|---|---|---|
| corn | gbm4 | 1.7 | 10.0 |
| corn | gbm_all | 5.5 | 9.6 |
| corn | gbm_daily | 4.2 | 13.2 |
| corn | gbm_daily_post2000 | 6.0 | 15.6 |
| corn | hinge | 0.4 | 16.8 |
| corn | hinge_extremes | -0.3 | 16.7 |
| corn | hinge_ldry_tmax | 1.6 | 16.4 |
| corn | hinge_sm_edd30 | 1.5 | 14.2 |
| corn | hinge_sm_t | 0.7 | 12.4 |
| corn | hinge_sm_t_post2000 | 0.9 | 15.2 |
| corn | hinge_sm_tmax | 1.7 | 14.4 |
| corn | linear | 1.2 | 17.1 |
| irrigated | gbm4 | -0.3 | -0.2 |
| irrigated | gbm_all | 0.4 | 6.8 |
| irrigated | gbm_daily | 2.8 | 11.5 |
| irrigated | gbm_daily_post2000 | 5.3 | 14.0 |
| irrigated | hinge | 0.4 | 11.0 |
| irrigated | hinge_extremes | -0.4 | 7.1 |
| irrigated | hinge_ldry_tmax | 1.5 | 9.1 |
| irrigated | hinge_sm_edd30 | 1.3 | 11.6 |
| irrigated | hinge_sm_t | 0.8 | 10.9 |
| irrigated | hinge_sm_t_post2000 | 5.4 | 20.8 |
| irrigated | hinge_sm_tmax | 0.8 | 8.1 |
| irrigated | linear | 0.9 | 10.9 |
| rainfed | gbm4 | 1.0 | 13.5 |
| rainfed | gbm_all | 6.1 | 22.9 |
| rainfed | gbm_daily | 7.1 | 23.2 |
| rainfed | gbm_daily_post2000 | 8.8 | 26.4 |
| rainfed | hinge | 2.3 | 19.9 |
| rainfed | hinge_extremes | 4.9 | 19.7 |
| rainfed | hinge_ldry_tmax | 4.0 | 22.7 |
| rainfed | hinge_sm_edd30 | 3.5 | 18.5 |
| rainfed | hinge_sm_t | 2.9 | 19.1 |
| rainfed | hinge_sm_t_post2000 | 7.4 | 24.5 |
| rainfed | hinge_sm_tmax | 3.6 | 20.2 |
| rainfed | linear | 3.2 | 19.0 |

## Folds in which each model predicts best

| series | model | folds_best |
|---|---|---|
| corn | gbm4 | 1 |
| corn | gbm_all | 1 |
| corn | gbm_daily | 1 |
| corn | gbm_daily_post2000 | 5 |
| corn | hinge_extremes | 1 |
| corn | hinge_sm_t_post2000 | 2 |
| irrigated | gbm4 | 1 |
| irrigated | gbm_daily_post2000 | 4 |
| irrigated | hinge_ldry_tmax | 1 |
| irrigated | hinge_sm_t_post2000 | 4 |
| irrigated | hinge_sm_tmax | 1 |
| rainfed | gbm_all | 1 |
| rainfed | gbm_daily | 2 |
| rainfed | gbm_daily_post2000 | 2 |
| rainfed | hinge_ldry_tmax | 1 |
| rainfed | hinge_sm_t | 1 |
| rainfed | hinge_sm_t_post2000 | 4 |

## Episodes held out: national production anomaly against the base model (%), whole window

| series | episode | observed_% | linear_% | hinge_% | hinge_sm_t_% | hinge_extremes_% | hinge_sm_tmax_% | hinge_sm_edd30_% | hinge_ldry_tmax_% | hinge_sm_t_post2000_% | gbm4_% | gbm_all_% | gbm_daily_% | gbm_daily_post2000_% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| corn | 1997-98 | -7.8 | -6.6 | -5.0 | -5.7 | -5.6 | -6.2 | -6.9 | -6.4 | -3.7 | -6.2 | -8.3 | -9.7 | -10.8 |
| corn | 2015-16 | -8.5 | -1.6 | -3.4 | -4.4 | -1.4 | -3.6 | -3.5 | -3.7 | -2.6 | -4.9 | -2.5 | -4.4 | -4.0 |
| corn | 2023-24 | -1.4 | -2.2 | -3.0 | -4.3 | -2.1 | -4.5 | -5.2 | -4.3 | -4.7 | -1.4 | -6.0 | -5.0 | -4.5 |
| irrigated | 1997-98 | -11.7 | -3.2 | -2.9 | -3.1 | -3.2 | -3.3 | -3.7 | -4.2 | -12.6 | -3.1 | -5.6 | -7.7 | -11.6 |
| irrigated | 2015-16 | -2.9 | -2.5 | -2.4 | -2.3 | -3.0 | -1.9 | -1.9 | -2.6 | -1.5 | -2.3 | -1.8 | -2.3 | -1.9 |
| irrigated | 2023-24 | -0.9 | -3.1 | -4.2 | -3.8 | -3.9 | -3.5 | -3.3 | -3.7 | -1.6 | -6.0 | -2.8 | -4.5 | -3.5 |
| rainfed | 1997-98 | -23.9 | -8.4 | -10.1 | -9.2 | -9.5 | -10.6 | -10.7 | -11.8 | -23.1 | -9.3 | -17.0 | -19.0 | -22.6 |
| rainfed | 2015-16 | -8.8 | -7.0 | -6.5 | -7.0 | -6.3 | -6.0 | -6.3 | -5.7 | -3.2 | -6.0 | -4.4 | -5.5 | -5.6 |
| rainfed | 2023-24 | 0.3 | -6.4 | -8.2 | -8.0 | -7.2 | -5.5 | -6.3 | -6.9 | -2.8 | -7.1 | -3.4 | -6.6 | -6.0 |

## Thresholds and coefficients, full sample (DK s.e.)

| series | model | term | est | se | t | threshold |
|---|---|---|---|---|---|---|
| irrigated | linear | W_T | -0.044 | 0.024 | -1.850 | nan |
| irrigated | linear | W_VPD | -0.219 | 0.198 | -1.107 | nan |
| irrigated | linear | W_P | -0.001 | 0.000 | -3.869 | nan |
| irrigated | linear | W_SM_RZ | 1.679 | 0.514 | 3.265 | nan |
| irrigated | hinge | W_T | -0.014 | 0.027 | -0.540 | nan |
| irrigated | hinge | W_VPD | -0.450 | 0.244 | -1.844 | nan |
| irrigated | hinge | W_P | -0.001 | 0.000 | -4.614 | nan |
| irrigated | hinge | W_SM_RZ | -0.829 | 1.101 | -0.753 | nan |
| irrigated | hinge | H_T | -0.065 | 0.028 | -2.309 | 25.619 |
| irrigated | hinge | H_VPD | 0.555 | 0.185 | 3.006 | 0.736 |
| irrigated | hinge | H_P | -0.001 | 0.000 | -3.076 | 175.450 |
| irrigated | hinge | H_SM_RZ | -2.009 | 1.125 | -1.785 | 0.392 |
| irrigated | hinge_sm_t | W_T | -0.022 | 0.025 | -0.885 | nan |
| irrigated | hinge_sm_t | W_SM_RZ | -1.965 | 1.024 | -1.920 | nan |
| irrigated | hinge_sm_t | H_T | -0.056 | 0.027 | -2.061 | 25.619 |
| irrigated | hinge_sm_t | H_SM_RZ | -3.259 | 1.203 | -2.710 | 0.392 |
| irrigated | hinge_sm_t_post2000 | P_W_T | -0.015 | 0.015 | -0.970 | nan |
| irrigated | hinge_sm_t_post2000 | P_W_SM_RZ | 0.746 | 0.934 | 0.799 | nan |
| irrigated | hinge_sm_t_post2000 | P_H_T | 0.159 | 0.049 | 3.232 | nan |
| irrigated | hinge_sm_t_post2000 | P_H_SM_RZ | 2.712 | 1.171 | 2.316 | nan |
| irrigated | hinge_extremes | W_T | -0.003 | 0.031 | -0.100 | nan |
| irrigated | hinge_extremes | W_VPD | -0.071 | 0.202 | -0.353 | nan |
| irrigated | hinge_extremes | W_P | -0.001 | 0.000 | -3.343 | nan |
| irrigated | hinge_extremes | W_SM_RZ | 1.628 | 0.578 | 2.816 | nan |
| irrigated | hinge_extremes | W_T_max | -0.027 | 0.041 | -0.658 | nan |
| irrigated | hinge_extremes | W_SM_RZ_min | -2.913 | 1.045 | -2.788 | nan |
| irrigated | hinge_extremes | H_T_max | -0.027 | 0.042 | -0.632 | 25.671 |
| irrigated | hinge_extremes | H_SM_RZ_min | -2.988 | 1.050 | -2.847 | 0.383 |
| irrigated | hinge_sm_tmax | W_TMAX | -0.041 | 0.023 | -1.789 | nan |
| irrigated | hinge_sm_tmax | W_SM_RZ | -2.158 | 1.029 | -2.096 | nan |
| irrigated | hinge_sm_tmax | H_TMAX | -0.117 | 0.074 | -1.573 | 31.104 |
| irrigated | hinge_sm_tmax | H_SM_RZ | -3.171 | 1.186 | -2.673 | 0.392 |
| irrigated | hinge_sm_edd30 | W_EDD30 | -0.270 | 0.077 | -3.497 | nan |
| irrigated | hinge_sm_edd30 | W_SM_RZ | -2.475 | 1.057 | -2.342 | nan |
| irrigated | hinge_sm_edd30 | H_EDD30 | 0.254 | 0.076 | 3.326 | 0.744 |
| irrigated | hinge_sm_edd30 | H_SM_RZ | -3.257 | 1.211 | -2.689 | 0.392 |
| irrigated | hinge_ldry_tmax | W_LDRY | -0.019 | 0.004 | -4.657 | nan |
| irrigated | hinge_ldry_tmax | W_TMAX | -0.047 | 0.022 | -2.184 | nan |
| irrigated | hinge_ldry_tmax | H_LDRY | 0.020 | 0.007 | 2.772 | 10.470 |
| irrigated | hinge_ldry_tmax | H_TMAX | -0.138 | 0.074 | -1.867 | 31.104 |
| irrigated | hinge_sm_t_post2000 | W_T | -0.002 | 0.026 | -0.088 | nan |
| irrigated | hinge_sm_t_post2000 | W_SM_RZ | -4.083 | 1.446 | -2.823 | nan |
| irrigated | hinge_sm_t_post2000 | H_T | -0.210 | 0.049 | -4.331 | 25.758 |
| irrigated | hinge_sm_t_post2000 | H_SM_RZ | -6.707 | 1.771 | -3.788 | 0.403 |
| rainfed | linear | W_T | -0.083 | 0.042 | -1.972 | nan |
| rainfed | linear | W_VPD | -0.400 | 0.386 | -1.035 | nan |
| rainfed | linear | W_P | -0.000 | 0.000 | -2.222 | nan |
| rainfed | linear | W_SM_RZ | 3.765 | 0.845 | 4.457 | nan |
| rainfed | hinge | W_T | -0.095 | 0.041 | -2.281 | nan |
| rainfed | hinge | W_VPD | -5.310 | 1.791 | -2.964 | nan |
| rainfed | hinge | W_P | -0.000 | 0.000 | -1.826 | nan |
| rainfed | hinge | W_SM_RZ | 3.665 | 0.877 | 4.180 | nan |
| rainfed | hinge | H_T | -0.344 | 0.137 | -2.508 | 27.548 |
| rainfed | hinge | H_VPD | 5.325 | 1.743 | 3.055 | 0.436 |
| rainfed | hinge | H_P | -0.008 | 0.002 | -3.605 | 82.253 |
| rainfed | hinge | H_SM_RZ | -13.211 | 5.219 | -2.531 | 0.245 |
| rainfed | hinge_sm_t | W_T | -0.080 | 0.044 | -1.808 | nan |
| rainfed | hinge_sm_t | W_SM_RZ | 3.415 | 0.664 | 5.145 | nan |
| rainfed | hinge_sm_t | H_T | -0.261 | 0.109 | -2.390 | 27.285 |
| rainfed | hinge_sm_t | H_SM_RZ | -21.598 | 3.781 | -5.712 | 0.245 |
| rainfed | hinge_sm_t_post2000 | P_W_T | 0.064 | 0.014 | 4.623 | nan |
| rainfed | hinge_sm_t_post2000 | P_W_SM_RZ | -4.526 | 1.063 | -4.259 | nan |
| rainfed | hinge_sm_t_post2000 | P_H_T | 0.176 | 0.185 | 0.951 | nan |
| rainfed | hinge_sm_t_post2000 | P_H_SM_RZ | -12.164 | 8.806 | -1.381 | nan |
| rainfed | hinge_extremes | W_T | -0.009 | 0.054 | -0.163 | nan |
| rainfed | hinge_extremes | W_VPD | -0.016 | 0.385 | -0.042 | nan |
| rainfed | hinge_extremes | W_P | -0.000 | 0.000 | -0.925 | nan |
| rainfed | hinge_extremes | W_SM_RZ | 3.968 | 1.197 | 3.315 | nan |
| rainfed | hinge_extremes | W_T_max | -0.067 | 0.045 | -1.481 | nan |
| rainfed | hinge_extremes | W_SM_RZ_min | -0.801 | 0.549 | -1.458 | nan |
| rainfed | hinge_extremes | H_T_max | -0.256 | 0.155 | -1.652 | 28.367 |
| rainfed | hinge_extremes | H_SM_RZ_min | -7.679 | 1.727 | -4.446 | 0.227 |
| rainfed | hinge_sm_tmax | W_TMAX | -0.123 | 0.037 | -3.321 | nan |
| rainfed | hinge_sm_tmax | W_SM_RZ | 2.995 | 0.632 | 4.737 | nan |
| rainfed | hinge_sm_tmax | H_TMAX | 0.040 | 0.046 | 0.877 | 29.300 |
| rainfed | hinge_sm_tmax | H_SM_RZ | -21.339 | 4.126 | -5.172 | 0.245 |
| rainfed | hinge_sm_edd30 | W_EDD30 | -0.045 | 0.013 | -3.324 | nan |
| rainfed | hinge_sm_edd30 | W_SM_RZ | 2.680 | 0.703 | 3.812 | nan |
| rainfed | hinge_sm_edd30 | H_EDD30 | 0.038 | 0.021 | 1.864 | 5.610 |
| rainfed | hinge_sm_edd30 | H_SM_RZ | -22.959 | 4.863 | -4.721 | 0.245 |
| rainfed | hinge_ldry_tmax | W_LDRY | -0.027 | 0.009 | -3.001 | nan |
| rainfed | hinge_ldry_tmax | W_TMAX | -0.151 | 0.033 | -4.555 | nan |
| rainfed | hinge_ldry_tmax | H_LDRY | -0.048 | 0.020 | -2.428 | 5.351 |
| rainfed | hinge_ldry_tmax | H_TMAX | -0.142 | 0.110 | -1.293 | 30.544 |
| rainfed | hinge_sm_t_post2000 | W_T | 0.181 | 0.087 | 2.067 | nan |
| rainfed | hinge_sm_t_post2000 | W_SM_RZ | -15.255 | 6.396 | -2.385 | nan |
| rainfed | hinge_sm_t_post2000 | H_T | -0.472 | 0.122 | -3.856 | 25.482 |
| rainfed | hinge_sm_t_post2000 | H_SM_RZ | -22.446 | 7.048 | -3.185 | 0.412 |
| corn | linear | W_T | 0.070 | 0.049 | 1.432 | nan |
| corn | linear | W_VPD | -1.915 | 0.547 | -3.499 | nan |
| corn | linear | W_P | -0.000 | 0.000 | -1.582 | nan |
| corn | linear | W_SM_RZ | -1.810 | 1.001 | -1.808 | nan |
| corn | hinge | W_T | -0.109 | 0.067 | -1.636 | nan |
| corn | hinge | W_VPD | -0.240 | 0.642 | -0.373 | nan |
| corn | hinge | W_P | -0.001 | 0.000 | -3.120 | nan |
| corn | hinge | W_SM_RZ | 0.382 | 0.819 | 0.466 | nan |
| corn | hinge | H_T | 0.192 | 0.084 | 2.296 | 23.981 |
| corn | hinge | H_VPD | -1.951 | 0.585 | -3.332 | 0.549 |
| corn | hinge | H_P | -0.002 | 0.001 | -3.085 | 231.501 |
| corn | hinge | H_SM_RZ | 3.408 | 1.115 | 3.057 | 0.357 |
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
| corn | hinge_sm_tmax | W_TMAX | 0.012 | 0.040 | 0.311 | nan |
| corn | hinge_sm_tmax | W_SM_RZ | 0.098 | 0.553 | 0.178 | nan |
| corn | hinge_sm_tmax | H_TMAX | -0.163 | 0.049 | -3.307 | 29.715 |
| corn | hinge_sm_tmax | H_SM_RZ | -6.588 | 2.218 | -2.970 | 0.257 |
| corn | hinge_sm_edd30 | W_EDD30 | -0.019 | 0.013 | -1.496 | nan |
| corn | hinge_sm_edd30 | W_SM_RZ | -0.024 | 0.611 | -0.040 | nan |
| corn | hinge_sm_edd30 | H_EDD30 | -0.015 | 0.013 | -1.124 | 9.260 |
| corn | hinge_sm_edd30 | H_SM_RZ | -6.009 | 2.282 | -2.633 | 0.257 |
| corn | hinge_ldry_tmax | W_LDRY | -0.040 | 0.011 | -3.584 | nan |
| corn | hinge_ldry_tmax | W_TMAX | 0.039 | 0.035 | 1.139 | nan |
| corn | hinge_ldry_tmax | H_LDRY | 0.056 | 0.017 | 3.328 | 9.496 |
| corn | hinge_ldry_tmax | H_TMAX | -0.180 | 0.045 | -3.963 | 29.715 |
| corn | hinge_sm_t_post2000 | W_T | 0.009 | 0.041 | 0.210 | nan |
| corn | hinge_sm_t_post2000 | W_SM_RZ | 1.765 | 0.796 | 2.217 | nan |
| corn | hinge_sm_t_post2000 | H_T | 0.166 | 0.110 | 1.508 | 26.659 |
| corn | hinge_sm_t_post2000 | H_SM_RZ | -16.560 | 2.679 | -6.180 | 0.257 |

## Do the weather effects change from 2000? (hinge_sm_t, Wald test, DK)

| series | test | wald | df | p_value | deviance_no_break | deviance_break |
|---|---|---|---|---|---|---|
| irrigated | weather effects (linear + hinge) shift from 2000 | 24.888 | 4 | 0.000 | 16427.076 | 15785.851 |
| rainfed | weather effects (linear + hinge) shift from 2000 | 27.943 | 4 | 0.000 | 11778.075 | 11345.408 |
| corn | weather effects (linear + hinge) shift from 2000 | 32.801 | 4 | 0.000 | 20606.263 | 20088.715 |
