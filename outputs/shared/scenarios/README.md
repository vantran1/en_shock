# Stage 1 on the El Niño scenarios of the direct approach

The path and simulation of step 04 on the path tables of the direct approach (`data/shared/paths/path_*.csv`,
written by `scripts/make_stage1_paths.py` on the `ginevra-agriculture` branch from `data/indices/`), so that the
two-stage and the direct shocks can be compared. Rebuild with `python scripts/04_simulate.py --scenarios-only`
(under a minute).

| Folder | El Niño months | Months in the tables |
|---|---|---|
| `1997-98/` | Apr 1997 – Mar 1998 | Oct 1996 – Mar 1999 (30) |
| `2015-16/` | Apr 2015 – Mar 2016 | Oct 2014 – Mar 2017 (30) |
| `2023-24/` | Jul 2023 – Mar 2024 | Jan 2023 – Mar 2025 (27) |
| `unit/` | RONI + 1, Jul 2001 – Jun 2002 | Jan 2001 – Jun 2003 (30) |

Each folder has `roni/` (the main RONI-alone model) and `roni_dmi/` (the RONI + DMI model, which also uses the
path's DMI column).

**Months.** Each path table is 6 zero months, the El Niño months and 12 zero months, and every month of it is in
the tables: Stage 2's growing windows reach up to 5 months before a harvest, so the first quarters need the
leading zero months, for the scenario and the neutral path. The lagged predictors also need the 6 months before
the table; for these scenarios they are zeros (`lead_in: zero` in their variants in `config.yaml`), not the
observed indices. The leading zero months are therefore exactly neutral: in every draw the scenario equals the
neutral path there, and the scenario run checks it.

**Climate.** Every month is simulated in today's climate: the trend is evaluated at t\* = 2026
(`period.t_star` in `config.yaml`), for the scenario and the neutral path alike. The dates are the calendar of the
path table: they pick the calendar month, and so the model of that month, not the climate. The neutral path is
therefore the same in the four scenarios. Its temperature is 0.45 °C above the 1991–2020 observed mean and 0.04 °C
below the 2016–2025 mean (annual means over the 16 regions, cropland weights).

**Files** (the columns of the step 5 tables in `outputs/agriculture/`; see the Stage 1 README, section 3, and
`outputs/shared/variables.csv` for the units):

| File | Contents |
|---|---|
| `path.csv` | the path: the 6 zero lead-in months (`lead_in` = True), then the whole path table |
| `blocks.csv` | the historical blocks, one per draw; `first_hist_month` and `last_hist_month` are the historical months of the first and last months in the tables |
| `simulated_monthly_16regions.csv` | `path` (scenario / neutral) × `draw` × month × region. `hist_date` is the historical month whose residuals the row uses. `block_year` is, as in the main outputs, the historical year of the path's first month |
| `deterministic_monthly_16regions.csv` | the same without residuals (e = 0) |
| `effects_16regions.csv` | scenario − neutral by variable, region and month: mean, 10th and 90th percentiles over the draws, and the deterministic difference |

A draw uses the same residual maps for the scenario and the neutral path, for every variable and region and over
the whole path, so take the shock draw by draw from the scenario-minus-neutral difference. Only the historical
years in which every variable has residuals for every month of the path are drawn: 51 draws with RONI alone and
50 with RONI + DMI while the hourly variables (TMAX to VPDMAX) still miss 1990–92 and 1997–2009.

The forecast path (C3S, the main run) is not here: it is `outputs/shared/path.csv`, with its simulation in
`outputs/agriculture/`. Its lead-in months are the observed indices.
