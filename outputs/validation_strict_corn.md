# Stricter leave-one-episode-out validation: corn (PROVISIONAL)

Built by `scripts/validate_strict.py`. Held-out window = episode + 4 quarters; break year chosen inside each fold (2000, 2005, 2010 or none) on the training data; trends set on the training years (restricted cubic splines). Poisson. Losses in % of the model's neutral path over the episode window. Error = predicted − observed.

## corn

| variant | episode | chosen_break | theta_R | observed_loss_pct | predicted_loss_pct | error_pts |
|---|---|---|---|---|---|---|
| recommended (nested break) | 1997-98 | 2005 | 0.8 | 12.1 | 3.9 | -8.2 |
| recommended (nested break) | 2015-16 | 2005 | 0.7 | 5.3 | 3.8 | -1.5 |
| recommended (nested break) | 2023-24 | 2005 | 0.8 | -3.5 | -1.7 | 1.8 |
| recommended, no DMI (nested break) | 1997-98 | 2010 | 0.6 | 4.7 | -4.7 | -9.5 |
| recommended, no DMI (nested break) | 2015-16 | 2010 | 0.6 | 11.9 | 13.6 | 1.7 |
| recommended, no DMI (nested break) | 2023-24 | 2005 | 0.6 | -0.3 | 1.9 | 2.2 |
| v5 as written | 1997-98 | none | 0.3 | 16.6 | -0.6 | -17.2 |
| v5 as written | 2015-16 | none | 0.5 | -0.9 | 1.8 | 2.7 |
| v5 as written | 2023-24 | none | 0.9 | 10.6 | -0.1 | -10.7 |
| v5 as written, no DMI | 1997-98 | none | 0.9 | 17.3 | 2.3 | -15.0 |
| v5 as written, no DMI | 2015-16 | none | 0.9 | -1.5 | 3.7 | 5.1 |
| v5 as written, no DMI | 2023-24 | none | 0.9 | 10.9 | 0.6 | -10.3 |

Mean absolute error, all three episodes and leaving each one out (to see whether a single episode drives the comparison):

| variant | mean abs error | without 1997-98 | without 2015-16 | without 2023-24 |
|---|---|---|---|---|
| recommended (nested break) | 3.9 | 1.7 | 5.0 | 4.9 |
| recommended, no DMI (nested break) | 4.5 | 2.0 | 5.9 | 5.6 |
| v5 as written | 10.2 | 6.7 | 13.9 | 9.9 |
| v5 as written, no DMI | 10.2 | 7.7 | 12.7 | 10.1 |

Break year chosen in each fold (information criterion of each candidate relative to the chosen one):

| variant | episode | chosen_break | ic_by_break |
|---|---|---|---|
| recommended (nested break) | 1997-98 | 2005 | {'2000': np.float64(81.5), '2005': np.float64(0.0), '2010': np.float64(88.3), 'none': np.float64(123.8)} |
| recommended (nested break) | 2015-16 | 2005 | {'2000': np.float64(53.4), '2005': np.float64(0.0), '2010': np.float64(33.7), 'none': np.float64(60.1)} |
| recommended (nested break) | 2023-24 | 2005 | {'2000': np.float64(66.8), '2005': np.float64(0.0), '2010': np.float64(76.6), 'none': np.float64(72.5)} |
| recommended, no DMI (nested break) | 1997-98 | 2010 | {'2000': np.float64(27.5), '2005': np.float64(23.4), '2010': np.float64(0.0), 'none': np.float64(93.9)} |
| recommended, no DMI (nested break) | 2015-16 | 2010 | {'2000': np.float64(20.2), '2005': np.float64(39.1), '2010': np.float64(0.0), 'none': np.float64(64.5)} |
| recommended, no DMI (nested break) | 2023-24 | 2005 | {'2000': np.float64(13.7), '2005': np.float64(0.0), '2010': np.float64(3.2), 'none': np.float64(31.9)} |
