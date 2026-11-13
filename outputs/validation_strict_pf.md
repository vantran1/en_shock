# Stricter leave-one-episode-out validation: pf (PROVISIONAL)

Built by `scripts/validate_strict.py`. Held-out window = episode + 4 quarters; break year chosen inside each fold (2000, 2005, 2010 or none) on the training data; trends set on the training years (restricted cubic splines). Poisson. Losses in % of the model's neutral path over the episode window. Error = predicted − observed.

## pf

| variant | episode | chosen_break | theta_R | observed_loss_pct | predicted_loss_pct | error_pts |
|---|---|---|---|---|---|---|
| recommended | 2015-16 | none | 0.6 | 0.1 | 1.7 | 1.5 |
| recommended | 2023-24 | none | 0.4 | -1.5 | -0.6 | 0.9 |
| recommended, no DMI | 2015-16 | none | 0.2 | 0.4 | 1.0 | 0.7 |
| recommended, no DMI | 2023-24 | none | 0.2 | -2.0 | -0.1 | 1.9 |
| v5 as written | 2015-16 | none | 0.6 | -0.3 | 2.2 | 2.4 |
| v5 as written | 2023-24 | none | 0.7 | 1.4 | -1.1 | -2.4 |
| v5 as written, no DMI | 2015-16 | none | 0.3 | 0.4 | 1.3 | 1.0 |
| v5 as written, no DMI | 2023-24 | none | 0.5 | 1.5 | 0.0 | -1.5 |

Mean absolute error, all three episodes and leaving each one out (to see whether a single episode drives the comparison):

| variant | mean abs error | without 2015-16 | without 2023-24 |
|---|---|---|---|
| recommended | 1.2 | 0.9 | 1.5 |
| recommended, no DMI | 1.3 | 1.9 | 0.7 |
| v5 as written | 2.4 | 2.4 | 2.4 |
| v5 as written, no DMI | 1.2 | 1.5 | 1.0 |
