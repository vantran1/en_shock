# Validation of the two-stage chain on past episodes (PROVISIONAL)

Each episode left out of Stage 2 (with the 4 quarters after it); Stage 1 weather from Van's nested hindcast (out of sample, from RONI alone). Loss over the episode window, % of production at average weather. Direct: strict validation of the direct approach (recommended, no DMI; its own reference is RONI = 0). See scripts/validate_two_stage.py.

| series | episode | observed_loss_pct | stage2_obs_weather_pct | chain_pct | chain_error_pts | direct_observed_pct | direct_predicted_pct | direct_error_pts |
|---|---|---|---|---|---|---|---|---|
| palay | 1997-98 | 14.0 | 16.1 | 11.0 | -3.0 | nan | nan | nan |
| palay | 2015-16 | 4.6 | 3.7 | 1.1 | -3.5 | nan | nan | nan |
| palay | 2023-24 | 3.8 | 4.9 | -0.4 | -4.2 | nan | nan | nan |
| irrigated | 1997-98 | 11.1 | 13.8 | 11.1 | 0.0 | 13.8 | 11.1 | -2.7 |
| irrigated | 2015-16 | 2.9 | 2.7 | 0.3 | -2.6 | 2.0 | 3.5 | 1.6 |
| irrigated | 2023-24 | 3.8 | 4.4 | -0.8 | -4.6 | 0.9 | 0.6 | -0.3 |
| rainfed | 1997-98 | 22.3 | 22.6 | 10.7 | -11.6 | 27.8 | 11.1 | -16.7 |
| rainfed | 2015-16 | 9.8 | 6.7 | 3.3 | -6.4 | 8.0 | 8.4 | 0.3 |
| rainfed | 2023-24 | 3.9 | 6.5 | 1.0 | -2.9 | 0.2 | 3.6 | 3.4 |
| corn | 1997-98 | 4.4 | 7.2 | 0.8 | -3.6 | 4.7 | -4.8 | -9.5 |
| corn | 2015-16 | 10.3 | 8.1 | 5.0 | -5.3 | 11.9 | 13.6 | 1.7 |
| corn | 2023-24 | 7.7 | 8.6 | 1.3 | -6.5 | -0.3 | 1.9 | 2.2 |

## Mean absolute error over the three episodes (points)

| series | chain_error_pts | direct_error_pts |
|---|---|---|
| corn | 5.1 | 4.5 |
| irrigated | 2.4 | 1.5 |
| palay | 3.6 | nan |
| rainfed | 7.0 | 6.8 |
