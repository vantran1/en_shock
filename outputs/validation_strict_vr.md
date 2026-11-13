# Stricter leave-one-episode-out validation: vr (PROVISIONAL)

Built by `scripts/validate_strict.py`. Held-out window = episode + 4 quarters; break year chosen inside each fold (2000, 2005, 2010 or none) on the training data; trends set on the training years (restricted cubic splines). Poisson. Losses in % of the model's neutral path over the episode window. Error = predicted − observed.

## vr

| variant | episode | chosen_break | theta_R | observed_loss_pct | predicted_loss_pct | error_pts |
|---|---|---|---|---|---|---|
| recommended | 2015-16 | none | 0.1 | -2.6 | -0.2 | 2.3 |
| recommended | 2023-24 | none | 0.8 | 3.2 | 3.2 | 0.1 |
| recommended, no DMI | 2015-16 | none | 0.4 | -3.4 | 0.7 | 4.1 |
| recommended, no DMI | 2023-24 | none | 0.1 | 3.8 | 0.1 | -3.7 |
| v5 as written | 2015-16 | none | 0.7 | -10.8 | 1.6 | 12.3 |
| v5 as written | 2023-24 | none | 0.1 | 16.8 | 4.4 | -12.4 |
| v5 as written, no DMI | 2015-16 | none | 0.3 | -10.4 | 1.4 | 11.8 |
| v5 as written, no DMI | 2023-24 | none | 0.2 | 13.8 | 0.1 | -13.7 |

Mean absolute error, all three episodes and leaving each one out (to see whether a single episode drives the comparison):

| variant | mean abs error | without 2015-16 | without 2023-24 |
|---|---|---|---|
| recommended | 1.2 | 0.1 | 2.3 |
| recommended, no DMI | 3.9 | 3.7 | 4.1 |
| v5 as written | 12.4 | 12.4 | 12.3 |
| v5 as written, no DMI | 12.8 | 13.7 | 11.8 |
