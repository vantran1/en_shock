# Stage 1 on the El Niño scenarios of the direct approach

Steps 4 and 5 on the path tables of the direct approach (`data/paths/path_*.csv`, written by
`scripts/make_stage1_paths.py` on the `ginevra-agriculture` branch from `data/indices/`), so that the two-stage
and the direct shocks can be compared. Rebuild with `python scripts/run_scenarios.py` (about 30 seconds).

| Folder | El Niño months | Months in the tables |
|---|---|---|
| `1997-98/` | Apr 1997 – Mar 1998 | Apr 1997 – Mar 1999 (24) |
| `2015-16/` | Apr 2015 – Mar 2016 | Apr 2015 – Mar 2017 (24) |
| `2023-24/` | Jul 2023 – Mar 2024 | Jul 2023 – Mar 2025 (21) |
| `unit/` | RONI + 1, Jul 2001 – Jun 2002 | Jul 2001 – Jun 2003 (24) |

Each folder has `roni/` (the main RONI-alone model) and `roni_dmi/` (the RONI + DMI model, which also uses the
path's DMI column).

**Months.** Each path table is 6 zero months, the El Niño months and 12 zero months. Step 4 puts the 6 observed
months before the table in front of it (the lagged predictors need them); the 6 leading zero months keep these
out of the El Niño months, as no model lag is longer than 6 months. The 6 leading months are dropped from every
table here except `path.csv`.

**Climate.** Every month is simulated in today's climate: the trend is evaluated at t\* = 2026
(`period.t_star` in `config.yaml`), for the scenario and the neutral path alike. The dates are the calendar of the
path table: they pick the calendar month, and so the model of that month, not the climate. The neutral path is
therefore the same in the four scenarios. Its temperature is 0.45 °C above the 1991–2020 observed mean and 0.04 °C
below the 2016–2025 mean (annual means over the 16 regions, cropland weights).

**Files** (the columns of the step 5 tables in `outputs/agriculture/`; see the Stage 1 README, section 3, and
`outputs/shared/variables.csv` for the units):

| File | Contents |
|---|---|
| `path.csv` | the path of step 4: the 6 observed lead-in months (`lead_in` = True), then the whole path table |
| `blocks.csv` | the historical blocks, one per draw; `first_hist_month` and `last_hist_month` are the historical months of the first and last months in the tables |
| `simulated_monthly_16regions.csv` | `path` (scenario / neutral) × `draw` × month × region. `hist_date` is the historical month whose residuals the row uses. `block_year` is, as in the main outputs, the historical year of the path's first month (here a dropped month) |
| `deterministic_monthly_16regions.csv` | the same without residuals (e = 0) |
| `effects_16regions.csv` | scenario − neutral by variable, region and month: mean, 10th and 90th percentiles over the draws, and the deterministic difference |

A draw uses the same residual maps for the scenario and the neutral path, for every variable and region, so take
the shock draw by draw from the scenario-minus-neutral difference.

The forecast path (C3S, the main run) is not here: it is `outputs/shared/path.csv`, with its simulation in
`outputs/agriculture/`.
