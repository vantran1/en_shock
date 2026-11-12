# Stricter leave-one-episode-out validation: rice (PROVISIONAL)

Built by `scripts/validate_strict.py`. Held-out window = episode + 4 quarters; break year chosen inside each fold (2000, 2005, 2010 or none) on the training data; trends set on the training years (restricted cubic splines). Poisson. Losses in % of the model's neutral path over the episode window. Error = predicted − observed.

## irrigated

| variant | episode | chosen_break | theta_R | observed_loss_pct | predicted_loss_pct | error_pts |
|---|---|---|---|---|---|---|
| recommended (nested break) | 1997-98 | 2000 | 0.8 | 14.2 | 10.7 | -3.5 |
| recommended (nested break) | 2015-16 | 2000 | 0.7 | 2.3 | 3.1 | 0.8 |
| recommended (nested break) | 2023-24 | 2000 | 0.7 | 1.5 | 2.4 | 0.8 |
| recommended, no DMI (nested break) | 1997-98 | 2000 | 0.8 | 13.8 | 11.1 | -2.7 |
| recommended, no DMI (nested break) | 2015-16 | 2000 | 0.7 | 2.0 | 3.5 | 1.6 |
| recommended, no DMI (nested break) | 2023-24 | 2000 | 0.7 | 0.9 | 0.6 | -0.3 |
| v5 as written | 1997-98 | none | 0.8 | 11.9 | 2.4 | -9.6 |
| v5 as written | 2015-16 | none | 0.8 | -5.7 | 5.0 | 10.6 |
| v5 as written | 2023-24 | none | 0.8 | 14.6 | 2.7 | -11.8 |
| v5 as written, no DMI | 1997-98 | none | 0.8 | 11.7 | 2.6 | -9.1 |
| v5 as written, no DMI | 2015-16 | none | 0.8 | -5.1 | 4.4 | 9.4 |
| v5 as written, no DMI | 2023-24 | none | 0.8 | 13.5 | 0.4 | -13.0 |

Mean absolute error, all three episodes and leaving each one out (to see whether a single episode drives the comparison):

| variant | mean abs error | without 1997-98 | without 2015-16 | without 2023-24 |
|---|---|---|---|---|
| recommended (nested break) | 1.7 | 0.8 | 2.2 | 2.2 |
| recommended, no DMI (nested break) | 1.5 | 0.9 | 1.5 | 2.1 |
| v5 as written | 10.7 | 11.2 | 10.7 | 10.1 |
| v5 as written, no DMI | 10.5 | 11.2 | 11.1 | 9.3 |

Break year chosen in each fold (information criterion of each candidate relative to the chosen one):

| variant | episode | chosen_break | ic_by_break |
|---|---|---|---|
| recommended (nested break) | 1997-98 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(32.0), '2010': np.float64(33.9), 'none': np.float64(40.0)} |
| recommended (nested break) | 2015-16 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(33.8), '2010': np.float64(56.7), 'none': np.float64(67.9)} |
| recommended (nested break) | 2023-24 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(35.0), '2010': np.float64(47.4), 'none': np.float64(96.6)} |
| recommended, no DMI (nested break) | 1997-98 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(29.5), '2010': np.float64(26.2), 'none': np.float64(43.1)} |
| recommended, no DMI (nested break) | 2015-16 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(34.9), '2010': np.float64(64.6), 'none': np.float64(63.4)} |
| recommended, no DMI (nested break) | 2023-24 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(37.3), '2010': np.float64(69.3), 'none': np.float64(119.3)} |

## rainfed

| variant | episode | chosen_break | theta_R | observed_loss_pct | predicted_loss_pct | error_pts |
|---|---|---|---|---|---|---|
| recommended (nested break) | 1997-98 | 2005 | 0.7 | 29.0 | 10.9 | -18.2 |
| recommended (nested break) | 2015-16 | 2000 | 0.7 | 7.6 | 10.6 | 3.0 |
| recommended (nested break) | 2023-24 | 2000 | 0.7 | -0.4 | 1.8 | 2.2 |
| recommended, no DMI (nested break) | 1997-98 | 2005 | 0.8 | 27.8 | 11.1 | -16.7 |
| recommended, no DMI (nested break) | 2015-16 | 2000 | 0.8 | 8.0 | 8.4 | 0.3 |
| recommended, no DMI (nested break) | 2023-24 | 2000 | 0.8 | 0.2 | 3.6 | 3.4 |
| v5 as written | 1997-98 | none | 0.8 | 28.2 | 3.9 | -24.3 |
| v5 as written | 2015-16 | none | 0.7 | -2.8 | 6.6 | 9.5 |
| v5 as written | 2023-24 | none | 0.8 | 8.1 | -0.2 | -8.3 |
| v5 as written, no DMI | 1997-98 | none | 0.8 | 27.7 | 4.4 | -23.4 |
| v5 as written, no DMI | 2015-16 | none | 0.8 | -2.1 | 6.2 | 8.3 |
| v5 as written, no DMI | 2023-24 | none | 0.8 | 8.7 | 0.9 | -7.8 |

Mean absolute error, all three episodes and leaving each one out (to see whether a single episode drives the comparison):

| variant | mean abs error | without 1997-98 | without 2015-16 | without 2023-24 |
|---|---|---|---|---|
| recommended (nested break) | 7.8 | 2.6 | 10.2 | 10.6 |
| recommended, no DMI (nested break) | 6.8 | 1.9 | 10.0 | 8.5 |
| v5 as written | 14.0 | 8.9 | 16.3 | 16.9 |
| v5 as written, no DMI | 13.1 | 8.0 | 15.6 | 15.8 |

Break year chosen in each fold (information criterion of each candidate relative to the chosen one):

| variant | episode | chosen_break | ic_by_break |
|---|---|---|---|
| recommended (nested break) | 1997-98 | 2005 | {'2000': np.float64(25.7), '2005': np.float64(0.0), '2010': np.float64(29.3), 'none': np.float64(18.9)} |
| recommended (nested break) | 2015-16 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(0.1), '2010': np.float64(48.1), 'none': np.float64(38.0)} |
| recommended (nested break) | 2023-24 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(5.5), '2010': np.float64(52.4), 'none': np.float64(43.6)} |
| recommended, no DMI (nested break) | 1997-98 | 2005 | {'2000': np.float64(18.1), '2005': np.float64(0.0), '2010': np.float64(20.7), 'none': np.float64(6.8)} |
| recommended, no DMI (nested break) | 2015-16 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(6.2), '2010': np.float64(46.1), 'none': np.float64(31.6)} |
| recommended, no DMI (nested break) | 2023-24 | 2000 | {'2000': np.float64(0.0), '2005': np.float64(5.4), '2010': np.float64(40.4), 'none': np.float64(27.7)} |
