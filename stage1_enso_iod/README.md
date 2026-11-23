# Stage 1: ENSO and IOD → monthly weather (DEFINE-PH)

This folder runs Stage 1 of the ENSO/IOD methodology and writes the inputs of the agricultural, electricity and labour sections. It sits in the en_shock repository (`en_shock/stage1_enso_iod/`) and shares the region boundaries, the land-sea mask and the land cover with the rest of the repository (see *In the repository* below).

The model is one EOF–CCA per variable and target month (Section 3.3 of the agricultural note). It is fitted on the ERA5 grid cells, with the RONI as predictor (in the target month, alone or together with its value 1, 3 or 6 months earlier), and cross-validated leave-5-years-out. RONI alone is the main specification because adding the DMI does not improve the out-of-sample hindcasts; the RONI + DMI fit is kept as the variant `roni_dmi`, for the sensitivity and for stress scenarios (see *Variants* in section 2). The cell results are then aggregated to regions with each section's weights:

| Section | Regions | Weights | Main outputs |
|---|---|---|---|
| Agriculture | 16 (pre-2024, no NCR; Sulu and Cotabato City in BARMM) | cropland area (Eq. 7) | observed and simulated region × month tables of the Table 2 variables |
| Electricity | 17 (the 16 + NCR), on 3 grids | population (Eq. 2) | temperature response for Eq. 3: path, neutral, historical fitted, shift by block |
| Labour | 17 (as the LFS tables) | population (area as sensitivity) | temperature response by region and quarter, and its coefficients, for the §11.1 check |

Every section draws on the same fit and the same historical blocks $Y_b$. A draw therefore carries one weather path through all three channels.

`notebooks/Stage1_EOF_CCA_explainer.ipynb` explains the method step by step and shows the hindcast skill. It reads the outputs of the scripts below.

---

## 1 · Set-up (once)

```bash
cd en_shock/stage1_enso_iod        # every command in this README runs from here
python -m pip install -r requirements.txt
```

**Data.**
- The monthly ERA5 files are in en_shock's `data/era5/monthly/` and the hourly ones in `data/era5/hourly/` (`paths.era5_monthly_dir` and `paths.era5_hourly_dir` in `config.yaml`). Both folders are ignored by git; the hourly files are also on Azure (`scripts/sync_era5_hourly.py`).
- The region polygons, the ERA5 land-sea mask and the land cover are en_shock's own files (`../data/boundaries/`, `../data/era5/`, `../data/agriculture/cropland_weights/`). NCR is taken from the ADM1 file.
- RONI (CPC) and DMI (NOAA PSL) are downloaded on each run. The copies in `data/indices/` are the fallback.

**Downloads.** Run this once on your laptop:

```bash
python scripts/00_download_inputs.py --all
```

| Input | Source | Size | Used for |
|---|---|---|---|
| `../data/era5/era5_land_sea_mask_0.25deg_phl.nc` (in the repository) | CDS `reanalysis-era5-single-levels`, `land_sea_mask` | < 1 MB | dropping cells with land fraction < 0.5 |
| `../data/agriculture/cropland_weights/esa_cci_lc_2022_phl.nc` (in the repository) | CDS `satellite-land-cover` (ESA CCI / C3S, 300 m, v2.1.1) | Philippine box only (CDS area subset), ~1 MB | cropland weights |
| `data/inputs/phl_ppp_2020_1km_Aggregated_UNadj.tif` (in the repository) | WorldPop 2020, 1 km, UN-adjusted | ~2 MB | population weights |
| `data/inputs/c3s/*.nc` (not in the repository) | CDS `seasonal-postprocessed-single-levels`, SST anomaly, 10 systems | ~10 MB each | the scenario path |

The CDS uses the key in `~/.cdsapirc` that you already use for ERA5. Before the first download, accept the licence of **"Land cover classification gridded maps from 1992 to present"** and of the **seasonal forecast** datasets on their CDS pages.

**The land-sea mask is required.** Step 1 keeps the cells with an ERA5 land fraction of at least 0.5 (v5, Section 3.3.2), which needs the mask at `paths.land_sea_mask`: en_shock's `data/era5/era5_land_sea_mask_0.25deg_phl.nc` (or `python scripts/00_download_inputs.py --lsm`, which writes it there). Without it, step 1 stops. With the 2020 mask the model has **349 cells**. (`land.allow_fallback: true` instead keeps the cells at least half inside the region polygons that have ERA5 soil water. That is only an approximation: it kept 35 cells that ERA5 treats as sea, whose soil moisture is far below that of land cells, and missed 17 land cells. Runs before 17 November 2026 used it by mistake, with 367 cells.)

**Other missing inputs.** Without the cropland or population files, area weights are used instead, and every output that depends on them says so (`weights` column, `shared/weights_coverage.csv`, `shared/run_metadata.json`).

**In the repository.** Stage 1 lives in `en_shock/stage1_enso_iod/`. `.gitignore` in this folder decides what is pushed:

* **tracked:** the code (`stage1/`, `scripts/`, `analysis/`), `config.yaml`, `requirements.txt`, this README, the notebook, the small inputs (`data/indices/`, `data/labour/`, the population raster) and the **hand-off outputs**: each section's `hist_fitted` table, the cell weights and island reassignment tables, the temperature coefficients for labour, the cell-level hindcast for electricity, `shared/cells.csv`, `model_configs.csv`, `variables.csv`, `weights_coverage.csv`, `skill/skill_summary.csv`, the DMI, SST and non-linearity summaries and figures, the lag figures, and the RONI + DMI variant's agriculture `hist_fitted` and skill summary (about 18 MB); from steps 4 and 5, the path (`shared/path.csv`, `path_members.csv`, `path_systems.csv`), `shared/blocks.csv` and the agriculture tables (`simulated_monthly_16regions.csv`, `deterministic_monthly_16regions.csv`, `effects_16regions.csv`; about 6 MB), and `outputs/scenarios/` (the scenarios of the direct approach, about 75 MB); `shocks_quarterly.csv` (step 8) is tracked too once it exists;
* **local only:** `work/` (rebuilt by steps 1–3), the seasonal forecasts (`data/inputs/c3s/`), the hourly ERA5, the rest of `outputs/` (rebuilt by the scripts) and the notebook's HTML export.

To hand off another output, add a `!outputs/...` line to `.gitignore`.

## 2 · Running

```bash
python scripts/run_all.py                    # steps 1-5 (about 15 minutes)
```

or step by step:

| Step | Script | What it does | Time |
|---|---|---|---|
| 1 | `01_prepare_inputs.py` | land cells; area, cropland and population weights; Table 2 fields at the cells; observed regional tables | < 1 min |
| 2 | `02_hourly_metrics.py` | hourly rows of Table 2, including EDD (once hourly files are there; see *Hourly data* below) | ~30 min for 76 years |
| 3 | `03_fit_stage1.py` | fit, cross-validation, nested CV, joint check, skill tables; electricity historical fitted values; labour coefficients | ~12 min |
| 4 | `04_make_path.py` | scenario path from the latest C3S forecast | < 1 min |
| 5 | `05_simulate.py` | simulated weather for the scenario and neutral paths; section outputs | < 1 min |

`python scripts/03_fit_stage1.py --quick` fits 3 months × 3 variables as a trial run.

**Each month, when a new forecast is out** (ECMWF on the 5th, the other systems on the 10th at 12 UTC):

```bash
python scripts/run_all.py --download-c3s --from 4
```

This refits nothing. It rebuilds the path and the scenario outputs. Step 4 uses the most recent forecast in `data/inputs/c3s/`. To use another forecast, pass `--forecast-start YYYY-MM`.

**Hourly data: EDD and WBGT.** Both come from the hourly ERA5 files (`era5_YYYY_MM.nc`, one per month, with `t2m`, `d2m`, `tp`, `sp`, `u10`, `v10` and `ssrd`, the files in the Azure container):

* **EDD** and the other hourly rows of Table 2 (TMAX, TMIN, NHOT, NDRY, LDRY, N50, VPDMAX), on Philippine days: $EDD = \sum_h \max(0, T_h - T^*)/24$ per month, with $T^*$ = `hourly.t_star` (35 °C, rice at flowering). Step 2: they are Stage 1 weather variables, fitted with the others in step 3.
* **WBGT** in the sun and in the shade for every working hour (Liljegren model of pywbgt), for the labour steps only. Step 6, described in section 7.

Each side has its own command, which pulls from Azure what is not here:

```bash
python scripts/run_all.py --from 2 --azure --delete-raw   # Stage 1: the hourly variables (step 2), then fit, path, simulate
python scripts/run_labour.py --delete-raw                 # labour: WBGT only, its fit and the shocks (section 7)
```

Step 2 with `--azure` stops the run if months are missing (add `--allow-incomplete` to go on with them as NaN); the RONI + DMI variant is then refitted with `python scripts/run_all.py --from 3 --to 5 --variant roni_dmi`. With `--delete-raw`, a raw file is kept until both commands have used it, so neither has to download it again.

Both commands use `scripts/hourly_wbgt_edd.py` (with `--only edd` and `--only wbgt`), which can also do both in one pass, month by month, straight from Azure while the download goes on:

```bash
python scripts/sync_era5_hourly.py list                  # what is in Azure
python scripts/hourly_wbgt_edd.py --azure                # download and compute every month that is ready
python scripts/hourly_wbgt_edd.py --azure --delete-raw   # the same, keeping only a few raw files on disk
python scripts/hourly_wbgt_edd.py --status               # what is done, what is waiting
python scripts/hourly_wbgt_edd.py --tables               # once every month is done: the outputs of steps 2 and 6
```

Each month is read once and both products are saved (`work/hourly_metrics/`, `work/wbgt_hourly/`), so the script can be stopped and run again: it does only the months that have arrived since. A month waits until the month before it is there, because its first Philippine day starts at 16:00 UTC on the last day of the previous month. With `--delete-raw`, a raw file is removed once both products of its month and of the next month are saved (about 26 MB a month; the Azure copy stays). Without `--azure`, it uses the files already in the local folder (`paths.era5_hourly_dir`, else `data/inputs/era5_hourly/`, as `sync_era5_hourly.py`). It takes a few seconds a month, about an hour for 1950–2025, plus the downloads.

`--tables` refuses to write while months are missing (`--allow-incomplete` writes them with those months as NaN). It writes `work/fields_hourly.pkl` and the observed tables with the hourly columns (step 2), and `work/fields_wbgt.pkl` with `outputs/labour/observed_wbgt_monthly_17regions.csv` (step 6). Then:

* `python scripts/03_fit_stage1.py` (and `--variant roni_dmi`): TMAX, TMIN, EDD, NHOT, NDRY, LDRY, N50 and VPDMAX become extra variables of the model and extra columns of the same region × month tables, and TMAX and TMIN are added to the electricity outputs;
* `python scripts/07_fit_wbgt.py`, then `08_labour_shocks.py`, for labour.

Steps 2 and 6 can also be run on their own, on a local folder (`paths.era5_hourly_dir`). They share the same monthly store, so they only compute the months that are not stored yet (`--overwrite` recomputes, `--no-compute` only writes the tables). A stored month computed with other settings (for example another `hourly.t_star`) is computed again. To test step 2 on one month, run `python scripts/02_hourly_metrics.py --months 1955-01 1955-01 --allow-partial`.

**Labour (WBGT and productivity shocks)**: steps 6–8, described in section 7. They run only when asked for: `python scripts/run_all.py --from 6 --to 8`.

**The lag analysis** (stand-alone; it does not change the fit): `python analysis/lag_analysis.py` (about 15 minutes), then `python analysis/lag_summary.py` for the tables and figures in `outputs/analysis/lags/`. `python analysis/lag_mechanism.py` checks whether the lagged signal is in RONI or DMI.

**The DMI analysis** (stand-alone): `python analysis/dmi_analysis.py` (about 15 minutes; it needs the `roni_dmi` variant fitted) writes `outputs/analysis/dmi/`, and `python analysis/dmi_figure.py` its one-page figure.

**The SST analysis** (stand-alone): download ERSSTv5 to `data/inputs/sst/` (about 160 MB, not tracked; the command is at the top of the script), then `python analysis/sst_predictors.py` (about an hour on 2 cores) writes `outputs/analysis/sst/`, with `summary.txt` and `sst_summary.png`.

**The non-linearity test** (stand-alone; it uses the same ERSSTv5 file): `python analysis/nonlinear_test.py` (about 15 minutes on 2 cores) writes `outputs/analysis/nonlinear/`, with `summary.txt` and `nonlinear_summary.png`.

**Variants: RONI + DMI, and stress scenarios.** `model.predictors` in `config.yaml` sets the indices of the main run (`[roni]`). A *variant* is a named set of overrides under `variants:`. It has its own models (`work/variants/<name>/`) and outputs (`outputs/variants/<name>/`, with the same file names as `outputs/`), and reads the shared inputs of the main run: fields, weights, cells, and the path unless it builds its own.

```bash
python scripts/03_fit_stage1.py --variant roni_dmi          # fit RONI + DMI (~12 min); its skill and hist_fitted tables
python scripts/run_all.py --from 3 --variant roni_dmi       # the same, then its path and simulation
```

`roni_dmi` is the RONI + DMI model: the sensitivity, and the model of any scenario that sets the IOD as well as ENSO. Use its two effects together, the RONI effect holding the DMI fixed plus the DMI effect, both from this model. Adding the DMI effect to the RONI-alone model would count the IOD twice, because the RONI-alone coefficient already carries the positive IOD that usually comes with El Niño.

For a stress scenario, such as a strong El Niño with a strong positive IOD, write the monthly path (`date`, `roni`, `dmi`, in the model's units) to a csv, uncomment the example `stress_nino_piod` in `config.yaml` (it uses the `roni_dmi` models through `models_from`), and run steps 4 and 5 with `--variant stress_nino_piod`.

**The El Niño scenarios of the direct approach.** The variants `scen_1997_98`, `scen_2015_16`, `scen_2023_24` and `scen_unit` run the path tables of the direct approach (`data/paths/path_*.csv`, from `scripts/make_stage1_paths.py` on the `ginevra-agriculture` branch) on the main RONI-alone models (`models_from: main`); the `*_dmi` variants run them on the RONI + DMI models. Each table is 6 zero months, the El Niño months and 12 zero months: the 6 leading months keep the observed lead-in of step 4 out of the El Niño months (no model lag is longer than 6 months). One command runs steps 4 and 5 for all eight (about 30 seconds) and writes `outputs/scenarios/<scenario>/<roni|roni_dmi>/` without the 6 leading months (see `outputs/scenarios/README.md`):

```bash
python scripts/run_scenarios.py                      # all eight; --only scen_unit for one
```

Steps 5 and 8 stop with a message if the saved models were fitted with other predictors than the run asks for, so a main run never uses the RONI + DMI models by mistake, or the reverse.

## 3 · Outputs

All tables are CSV with one row per region (or cell) and month. Dates are the first day of the month. Each table has both `code` (NCR, CAR, R01 … R13, R04A, MIMAROPA, BARMM) and the PSA `region` name.

### `outputs/agriculture/`

| File | Content |
|---|---|
| `observed_monthly_16regions_cropland.csv` | **Stage 2 estimation data**: observed ERA5 Table 2 variables, 1950–2025, cropland-weighted |
| `observed_monthly_16regions_area.csv` | the same with area weights (sensitivity) |
| `hist_fitted_16regions.csv` | **hindcast**: for every month 1950–2025 and region, each variable's observed value `<v>_obs`, the in-sample model value `<v>_fitted` and the out-of-sample ones `<v>_cv` and `<v>_nested` (cropland-weighted; CWB3 in mm next to SPEI3). See *What `*_fitted`, `*_cv` and `*_nested` are* in section 6 |
| `simulated_monthly_16regions.csv` | `path` (scenario / neutral) × `draw` × month × region. `block_year` is the historical year whose residuals the draw uses at the start of the path; `hist_date` is the historical month used in each row |
| `deterministic_monthly_16regions.csv` | the response with the residual set to zero, for both paths |
| `effects_16regions.csv` | scenario − neutral by variable, region and month: mean over draws, 10th and 90th percentiles, deterministic |
| `cell_weights_16regions.csv` | every cell–region piece: area, cropland area, and the weights. `*_reassigned_km2` is the part that came from dropped cells |
| `island_reassignment_16regions.csv` | every piece of land moved from a dropped cell (island or coastal sliver) to its nearest model cell: from and to cell, `distance_km` between cell centres, `farther_than_threshold` (`weights.far_km` in `config.yaml`, 100 km), whether the receiving cell belongs mainly to another region, and the cropland moved. The same for the 17 regions is in `shared/island_reassignment_17regions.csv`. Equally distant cells go to the lowest cell index, so the result is the same on every machine. The standalone version for the shared repository is `en_shock/scripts/cropland_weights.py` |

**Variables** (`shared/variables.csv`):

| Column | Variable | Units |
|---|---|---|
| T | mean 2 m temperature | °C |
| VPD | vapour pressure deficit | kPa |
| P | precipitation | mm/month |
| SM_RZ | root-zone soil moisture (swvl1–3 weighted 7/21/72 cm) | m³/m³ |
| SM_DEEP | deep soil moisture (swvl4) | m³/m³ |
| PET | potential evaporation, × −1 | mm/month |
| E | actual evaporation, × −1 | mm/month |
| SPEI3 | 3-month P − PET, standardised | std. units |
| CWB3 | 3-month P − PET | mm |
| RS | solar radiation | MJ m⁻² day⁻¹ |
| RO | runoff | mm/month |

Accumulated fields are the monthly means × days in the month.

### `outputs/electricity/`

| File | Content |
|---|---|
| `path_response_17regions.csv` | $\widehat W_{T,r,m}(x^S; t^*)$ and $\widehat W_{T,r,m}(0; t^*)$ for every month of the path (`T_scenario`, `T_neutral`) |
| `hist_fitted_17regions.csv` | $\widehat W_{T,r,m}(x_{obs}; Y)$ for every historical month 1950–2025 (`T_fitted`), next to the observed population-weighted value (`T_obs`) and the out-of-sample values `T_cv` and `T_nested` |
| `shift_by_block_17regions.csv` | **the bracket of Eq. 3** for every draw, path month and region: `T_shift_scenario` and `T_shift_neutral`, to be added to the observed hourly temperatures of `hist_date` |
| `cells_path_response.csv.gz`, `cells_hist_fitted.csv.gz` | the same per cell, for a version of Eq. 3 that uses the cell's own response instead of its region's |
| `cell_weights_17regions.csv` | population weights of every cell–region piece: within the region, and within the grid (Eq. 2), with and without MIMAROPA |
| `region_grid_map.csv` | region → grid, with population and the MIMAROPA flag |

For Eq. 3, $r(i)$ is the region holding most of the cell's population. It is given as `region17_majority_population` in `shared/cells.csv`.

### `outputs/labour/`

| File | Content |
|---|---|
| `T_coefficients_monthly_17regions.csv` | the Stage 1 temperature response per unit of each predictor (RONI; RONI and DMI in the variant), by region and month. Columns: `coef_*` per predictor; `sustained_*` = target month + lagged month, i.e. the response to an anomaly that holds steady from the lagged month to the target month (`lagset` says which lag); bootstrap 5–95 % ranges |
| `T_coefficients_quarterly_17regions.csv` | the same averaged over JFM, AMJ, JAS, OND, **for the comparison with the panel regression on mean temperature (§11.1)** |

Compare the panel regression with the `sustained_*` coefficients, not the `coef_*` ones. RONI and DMI are persistent 3-month means, so the value in the target month and the lagged value are correlated. Where the model uses both, the two `coef_*` often have opposite signs: the model also responds to how fast the index is changing. In spring, for example, warming follows a decaying El Niño. The sustained coefficient is the response to an anomaly that holds steady, which is what a panel regression on RONI and DMI estimates. Where the model uses lag 3 or lag 6, it is the response to an anomaly that has lasted four or seven months, which is how El Niño episodes behave; keep this in mind when comparing months with different lags.
| `hist_fitted_17regions.csv` | **hindcast**: `T_obs`, `T_fitted`, `T_cv` and `T_nested` for every month 1950–2025 and region (population-weighted; same values as the T columns of the electricity file) |
| `T_response_monthly_17regions.csv`, `T_response_quarterly_17regions.csv` | scenario, neutral and their difference for the path |
| `cell_weights_17regions.csv` | as for electricity |

The WBGT and shock files of steps 6–8 are listed in section 7.

### `outputs/shared/`

| File | Content |
|---|---|
| `path.csv` | monthly RONI and DMI of the path, with the source of every value (observed / forecast / interpolated), the members' 10–90 % range and the lead-in months (`lead_in`: the 6 observed months before the path's start, needed for the lagged predictors) |
| `path_members.csv`, `path_systems.csv` | |
| `blocks.csv` | the historical blocks $Y_b$, the same for all three sections |
| `observed_monthly_17regions_population.csv`, `..._area.csv` | observed Table 2 variables for the 17 regions |
| `cells.csv`, `weights_coverage.csv`, `variables.csv`, `model_configs.csv` | |
| `run_metadata.json` | the settings, input files, fallbacks and index dates of every step |

### `outputs/skill/`

| File | Content |
|---|---|
| `skill_summary.csv` | per variable and weight set: CV and nested-CV Spearman ρ, share of significant region–months (FDR 10 %), RPSS, 2AFC, CRPSS, coverage |
| `skill_<weights>.csv` | per variable, month and region (`cv` = plain or nested) |
| `skill_cells.csv` | per cell |
| `hindcasts.csv` | observed and cross-validated standardised anomalies, for checking past episodes |
| `probabilistic.csv` | |
| `joint_check.csv` | the joint model of all variables, against one model per variable |

## 4 · Method in brief

For each variable $v$ and target month $m$:

1. **Transform each cell.** Gamma for P and RO, empirical for the counts from hourly data, identity otherwise. Within each training window, remove a linear trend and standardise.
2. **Reduce the cells.** Take the leading EOFs of the cells (the $M_y$ modes).
3. **Fit the CCA.** Run a CCA between those EOFs and the standardised predictors (the $M_c$ modes). The predictors are the indices of `model.predictors` (RONI; RONI and DMI in the `roni_dmi` variant) in the target month, alone (`sync`) or together with their values 1, 3 or 6 months earlier (`sync+lag1`, `sync+lag3`, `sync+lag6`; `model.lag_sets` in `config.yaml`). With RONI alone and one lag, $M_c$ is 1.
4. **Choose the configuration.** $M_y \in 1..6$, $M_c \in 1..2$ and the lag set are chosen by the mean leave-5-out CV Spearman ρ over the cells. The transform, trend, standardisation, EOFs and CCA are re-estimated inside every fold; the choice of configuration is made once, on all years. The nested cross-validation (`outputs/skill/`, `*_nested`) repeats the choice inside each outer fold: 5-year blocks of July–June seasons (Jul 1950–Jun 1955, Jul 1955–Jun 1960, …) are held out in turn, so every month of an ENSO season is held out together and no El Niño (1997–98, 2015–16, 2023–24, but also 1994–95 or 2009–10) is split between training and test. January–June targets are counted with the season that began the previous July.
5. **Refit and simulate.** The model is refitted on all years, and the CV residual maps are kept for simulation.

**Weather for path $x$ in draw $b$.** At each cell,

$$W = T^{-1}\big(\mu + \zeta\,t^* + \sigma\,[\hat y(x) + e_b]\big),$$

where:
- $e_b$ is the CV residual map of the same calendar month in block $Y_b$;
- $t^*$ = 2026 is today's climate.

The cell values are then averaged with the section's weights.

**SPEI3.** It is not additive, so it is aggregated as millimetres of 3-month P − PET and re-standardised with the region's 1991–2020 climatology.

**Neutral path.** The neutral path $x = 0$ uses the same residuals. For temperature, the scenario-minus-neutral difference is therefore the same in every draw.

**The path.** It runs from January of the forecast year to the last forecast month:
- before the forecast, the observed RONI and DMI;
- after it, the median of the C3S members, 10 from each system. Each member's SST anomalies are turned into RONI and DMI on the model's scale, and smoothed to centred 3-month means with the observed lead-in.

Months between the last observation and the forecast are flagged, and are interpolated if no member covers them. The DMI from PSL lags by about two months.

## 5 · Choices to confirm with the section leads

* **RONI alone as the main predictor.** Proposed because the DMI adds no out-of-sample skill (section 6, *The DMI*). To go back to RONI + DMI, set `model.predictors: [roni, dmi]` and re-run from step 3.
* **MIMAROPA and the Luzon grid.** Mindoro, Palawan, Marinduque and Romblon are not connected to the Luzon grid. The first Batangas–Mindoro submarine cable is due in January 2028. MIMAROPA is therefore left out of the Luzon grid weights by default (`sections.electricity.mimaropa_in_luzon_grid: false`), but its region rows stay in every table. The grid weights with and without it are both in `cell_weights_17regions.csv`.
* **Population weights** for electricity and labour, with area weights as the labour sensitivity, as in the v5 comments. WorldPop 2020 is held fixed.
* **Cropland** is ESA CCI / C3S land cover for 2022:
  - classes 10, 11, 12 (rainfed) and 20 (irrigated) count fully;
  - class 30 (mosaic, cropland > 50 %) counts 0.75, and class 40 (mosaic, cropland < 50 %) counts 0.25.

  Change `weights.cropland_classes` to use other shares.
* **NCR** comes from the same grid fit as everything else, so no separate regression is needed. Step 5 prints the NCR temperature effect next to the mean of Central Luzon and CALABARZON, which is the check named in §3.2 of the electricity note.

## 6 · Where this differs from the v5 text

* **Agri §3.3.2, step 2.** Stage 1 is fitted on the cells, and Eq. 7 is applied to its outputs (observed and simulated) rather than to its inputs. Tests on the same data gave the same regional skill either way (Δρ between −0.007 and +0.012). Fitting on the cells lets one fit serve the three sets of weights.
* **Agri §3.3.3.** One model per variable, with the joint model of Eq. 8 run as a check (`skill/joint_check.csv`). The selection criterion is the mean CV Spearman correlation over the cells of that variable.
* **Electricity §3.2, NCR paragraph.** NCR is covered by the grid model (its cells are population-weighted). The multiple regression is no longer needed; the average of Central Luzon and CALABARZON remains as a check.
* **Land mask.** Cells with ERA5 land fraction < 0.5 are dropped, as in the text (349 cells). So are cells without soil water in ERA5, though with the 2020 mask none is.
* **Agri §3.3.3, model selection (predictor lags).** The text leaves the lags open. The candidates are now the target month alone, or with the index 1, 3 or 6 months earlier (lags 3 and 6 are the two previous non-overlapping 3-month seasons). A suggested sentence: "The predictor is the RONI in the target month, alone or together with its value one, three or six months earlier; the lag set is chosen with M_y and M_c." See *Predictor lags* below for why.
* **Predictors (to be agreed).** The text uses RONI and DMI. The main specification here uses RONI alone, and keeps RONI + DMI as a sensitivity and for stress scenarios (variant `roni_dmi`); see *The DMI* below. A suggested sentence: "The DMI does not improve the out-of-sample hindcasts and is therefore left out of the main specification; a model with both indices is kept for sensitivity analyses and for scenarios that combine El Niño with a positive IOD."

**Predictor lags.** `analysis/lag_analysis.py` compared 19 lag sets (sync; sync + lag 1…k for k ≤ 6; single lags 1–6; sync + one lag of 1–6; sync + lags 3 and 6) with the fit's own cross-validation, on 1951–2025, and tested whole menus of lag sets with nested cross-validation (`outputs/analysis/lags/`). (It was run before the switch to the ERA5 land-sea mask and to RONI alone, on 367 cells with RONI and DMI; the choice of lags it supports does not depend on those changes, but the numbers would move slightly if it were run again.) Averaged over the 10 variables and 12 months, the selection-honest skill over the 16 regions (cropland weights) was:

| Lag sets to choose from | Nested CV ρ |
|---|---|
| sync, sync+lag1 (before) | 0.335 |
| sync + lag 1…k, k ≤ 6 | 0.337 |
| sync, sync + any one lag 1–6 | 0.370 |
| **sync, sync+lag1, sync+lag3, sync+lag6 (now)** | **0.368** |
| all 19 lag sets | 0.363 |

The gain is from March to August (e.g. May 0.40 → 0.48, August 0.01 → 0.11) and largest for soil moisture, runoff, SPEI-3 and temperature; October to February barely change. In those months the selection points back to the RONI of the previous December–February, the ENSO peak: the Philippine weather of spring and summer still responds to the El Niño or La Niña of the past winter. The signal is in the lagged RONI, not the DMI (`analysis/lag_mechanism.py`). Of the menus that gained, the one used here lost more than 0.02 in the fewest variable-months (18 %) and gave the most stable choice across folds. Because lag 6 needs the indices of the second half of 1949, which do not exist, January–June targets are fitted on 1951–2025.

**What `*_fitted`, `*_cv` and `*_nested` are.** All three are the deterministic response $\widehat W(x_{obs}(Y); Y)$ to the observed indices of that month (RONI in the main run, RONI and DMI in the `roni_dmi` variant), with no residual, in physical units and averaged over the region. They differ in what the model saw:

| Column | Model | Use |
|---|---|---|
| `<v>_fitted` | fitted on all years (the model of the simulation) | in-sample: how past episodes look in the model; flatters the skill |
| `<v>_cv` | fitted without the year and the two years on each side; configuration (lag set, $M_y$, $M_c$) chosen once on all years | out of sample, except for the choice of configuration |
| `<v>_nested` | fitted without the 5-year July–June block of the month (e.g. Jul 1995–Jun 2000), and the configuration chosen again without it | fully out of sample: **use this one to validate past episodes** |

`<v>_cv` and `<v>_nested` are the predictions scored in `outputs/skill/` (there as standardised anomalies, here in physical units). For SPEI3, `CWB3_cv` and `CWB3_nested` are the same predictions in mm.

**The DMI.** `analysis/dmi_analysis.py` asks what the DMI adds to the RONI: the nested skill of RONI + DMI against RONI alone with the same lag sets, by variable, quarter and region; the observed effect of a positive IOD holding the RONI fixed, by quarter; and the RONI–DMI correlation by season (`outputs/analysis/dmi/`, with a `summary.txt` and `dmi_summary.png`). In short:

* adding the DMI improves no variable significantly out of sample, and rainfall is slightly worse with it; it hurts in July–September and helps a little, not significantly, in October–December and April–June;
* holding the RONI fixed, a positive IOD dries October–December (about −4.5 % of the national rainfall per standard deviation of the DMI, the same sign in all 16 regions), about a third to a quarter of the El Niño effect, and has no national effect from January to June;
* RONI and DMI correlate at about 0.4 in July–September and 0.45–0.6 in October–December, and hardly at all from January to June; since 1990 only 2019 has a positive IOD without an El Niño in October–December.

This is why RONI alone is the main specification, with the DMI kept in the `roni_dmi` variant.

**Other SST predictors.** `analysis/sst_predictors.py` asks whether more of the ocean than the RONI improves Stage 1, with the nested cross-validation and paired bootstrap of the DMI analysis (`outputs/analysis/sst/`). Every predictor is built from ERSSTv5 anomalies minus the tropical-mean anomaly, like the RONI, so the warming trend cannot enter. Step 1 adds one index to the RONI at a time, then the first three together: the El Niño Modoki index (EMI), the Indian Ocean basin (IOB), the Philippine Sea (125–150°E, 5–20°N, the mean of the three months before the target month only, our choice of box) and the tropical North Atlantic (TNA). Step 2 replaces the indices with the leading EOFs of the tropical Indo-Pacific SST map (30°S–30°N, 40°E–80°W), recomputed in every fold, with the number of EOFs (2–15) chosen along with the lag set, My and Mc; a second run masks the waters around the Philippines (110–135°E, 0–25°N). In short:

* no index improves the hindcasts: over all variables the error changes by −1.6 % (TNA, significantly worse) to +0.3 % (Philippine Sea). Each index moves with the RONI (Philippine Sea −0.6 to −0.9 by season, EMI +0.3 to +0.7), which leaves it little to add;
* the SST field ranks the years better than the RONI alone (mean nested Spearman 0.366 → 0.400), most for temperature (0.26 → 0.35), soil moisture, runoff and SPEI-3, but its error is no smaller (+0.5 %, 90 % interval −2.9 to +3.4 %) and rainfall is worse (−3.8 %, significant). At these skill levels a gain of 0.03 in correlation is worth only a few per cent of the error;
* about 30 % of the field's gain in ranking needs the waters around the Philippines, where the SST partly responds to the local weather (0.390 with them masked);
* the few seasons that look better, such as January–March SPEI-3 with the Philippine Sea, are fewer than chance would give in 280 variable–season–predictor tests, and are mostly accumulated variables, whose accumulation period overlaps the months of the Philippine Sea index.

RONI alone stays the main specification. The field CCA is the linear benchmark that a model of SST patterns (a CNN, for example) would have to beat out of sample.

**Non-linear responses.** `analysis/nonlinear_test.py` asks whether the weather responds to ENSO non-linearly enough for a non-linear model to beat the linear EOF-CCA, with the same nested cross-validation and test (`outputs/analysis/nonlinear/`). It compares four models with the RONI alone: separate El Niño and La Niña parts of the RONI (max and min of RONI and 0); RONI and RONI²; analogues, the mean weather of the k past years closest in RONI (no linearity at all); and analogues in the SST map, the k past years with the closest tropical Indo-Pacific SST map, the Philippine waters masked. In short:

* all four are worse than the linear RONI alone, significantly so over all variables: −1.9 % (El Niño and La Niña parts), −2.3 % (RONI²), −9.3 % (analogues in RONI) and −6.6 % (analogues in the SST map). The analogues in the SST map also rank the years worse than the linear SST field (mean nested Spearman 0.338 against 0.390);
* the observed response is somewhat asymmetric: in January–March a La Niña of one unit of RONI raises the national rainfall by about 47 % of the mean, an El Niño of one unit lowers it by about 28 % (p = 0.06 for equal slopes), with the same pattern in SPEI-3 and runoff. But the two slopes differ at p < 0.1 in only 15 % of 640 region–quarter–variable cases (10 % by chance), and estimating them separately costs more out of sample than it gains.

With 76 years, the extra freedom of a non-linear model costs more than any non-linearity returns. This is why the main specification stays linear, and why a CNN trained on the observations alone would not help.

## 7 · Labour: WBGT and productivity shocks (steps 6–8)

These three steps implement the labour note. They reuse the cells, weights, EOF-CCA engine, path and historical blocks of steps 1–5, and they do not change any output of those steps.

```
hourly ERA5 ──► 06 hourly WBGT in working hours (sun, shade) ──► monthly P50, P90, daily max
                                   │                                      │
                                   │                              07 EOF-CCA on the predictors
                                   ▼                                      ▼
        08 shift the hours of each historical block ◄── shifts of P50 and P90 for the path
                                   ▼
        Hothaps capacity per hour ──► month ──► region ──► sector (employment) ──► quarterly shock
```

**Set-up.** The steps need two more packages and the hourly files:

```bash
brew install libomp                      # macOS only: pywbgt compiles C code that uses OpenMP
python -m pip install pywbgt pythermalcomfort openpyxl
```

Set `paths.era5_hourly_dir` in `config.yaml`. The files are one per month, `era5_YYYY_MM.nc`, with `t2m`, `d2m`, `sp`, `u10`, `v10` and `ssrd` (the January 1955 test file has all six). `fdir` and `strd`, listed in Table 3 of the note, are not needed: the Liljegren model estimates the direct share of the radiation itself.

**Running.**

```bash
python scripts/06_wbgt_hourly.py        # about 3 s per month of data; can be stopped and resumed
python scripts/07_fit_wbgt.py           # about 20 minutes with the nested cross-validation
python scripts/08_labour_shocks.py      # needs outputs/shared/path.csv (step 4); a few minutes
```

or `python scripts/run_all.py --from 6 --to 8`. Steps 6 and 7 are the hindcast side and need no forecast. Step 8 needs the path of step 4, and uses the blocks of step 5 when that has been run, so that each draw has the same historical weather in the three channels.

**In one go, from Azure.** `scripts/run_labour.py` runs the whole labour chain: it downloads every month that is not here from Azure and computes its hourly WBGT (`hourly_wbgt_edd.py --azure --only wbgt`), writes the monthly WBGT statistics and observed tables (`--tables`), fits them on RONI and on RONI + DMI (step 7, main run and `roni_dmi`), and computes the shocks of `outputs/shared/path.csv` with both models (step 8). It computes WBGT only: the hourly variables of Table 2 (EDD and the rest) are Stage 1 variables, computed by step 2 (`python scripts/run_all.py --from 2 --azure`; see *Hourly data* in section 2). It can be stopped and run again, and stops before the fit if months are missing.

```bash
python scripts/sync_era5_hourly.py set-token     # once: the Blob Container SAS URL, with read and list (r, l) permission
python scripts/run_labour.py --delete-raw        # everything; a raw file is removed once WBGT and step 2 have both used it
python scripts/run_labour.py --allow-incomplete  # the same with the months there are (30 years at least)
python scripts/run_labour.py --from fit          # only steps 7 and 8, e.g. after a new forecast path
```

Without `--delete-raw` the raw files stay in `data/inputs/era5_hourly/` (about 26 MB a month). If the files are already on your computer, set `paths.era5_hourly_dir` to their folder: only the months that are not there are downloaded, into the same folder (then leave out `--delete-raw`, which would remove your copies).

### What each step does

**Step 6: WBGT.** WBGT is computed with the Liljegren model of [pywbgt](https://github.com/kwodzicki/pywbgt) at the 349 model cells:

* **sun** (outdoor work): with the solar radiation of ERA5;
* **shade** (indoor work without air conditioning): the same with solar radiation set to zero, which is the note's definition (Section 2).

The working window is 7:00 to 17:00 Philippine Time (`wbgt.working_hours`), split into the ten hourly intervals 7–8, …, 16–17. ERA5 radiation at a time stamp is the energy of the hour that ends there, so each interval uses the radiation of its end stamp, the mean of the two stamps around it for temperature, dewpoint, pressure and wind speed, and the sun's position at the middle of the interval. The 10 m wind is brought to 2 m by the package, with its default minimum of 2 knots.

The hourly values are kept in `work/wbgt_hourly/` (about 0.3 GB for 1950–2025), because step 8 shifts them. Three monthly statistics are formed per cell and environment:

| Variable | Meaning |
|---|---|
| `WBGTSUN_P50`, `WBGTSHD_P50` | median of WBGT over the working hours of the month |
| `WBGTSUN_P90`, `WBGTSHD_P90` | 90th percentile over the working hours of the month |
| `WBGTSUN_DMAX`, `WBGTSHD_DMAX` | mean over the days of the daily maximum in working hours (Eq. 20 of the note) |

**Step 7: EOF-CCA.** The six statistics are fitted on the predictors of the run (RONI; RONI and DMI with `--variant roni_dmi`) exactly like the Stage 1 variables: one model per statistic and calendar month on the cells, with the same lag sets, numbers of modes and leave-5-years-out selection. They are fitted apart from the Stage 1 variables, so the agricultural and electricity outputs do not change.

**Step 8: shocks.** For every historical block and month of the path, each working hour of the block's month is shifted, the Hothaps function of [pythermalcomfort](https://pythermalcomfort.readthedocs.io) (`work_capacity_hothaps`, Eq. 1 of the note) is applied to every hour, and the capacities are averaged, in the order the note requires (function first, aggregation afterwards):

* **Shift.** For percentile $q \in \{50, 90\}$, $\Delta_q = \widehat W_q(x; t^*) - \widehat W_q(x_{obs}(Y_b); Y_b)$: the fitted effect of the block's own indices and trend is removed, and that of the scenario path $x^S$ (or of the neutral path $x = 0$) in today's climate is added. An hour at percentile $r$ of its cell and month moves by $\Delta_{50} + (\Delta_{90} - \Delta_{50})(r - 50)/40$, linear between and beyond the two percentiles (Section 11.1).
* **Capacity.** Mean over the working hours of the month with equal weights (Eq. 8), for heavy, moderate and light work, in the sun and in the shade.
* **Regions.** Cell capacities are averaged to the 17 regions with the population weights (area weights are a sensitivity case).
* **Sectors.** Regions are combined with each sector's regional employment (Eq. 19a; PSA Table 11.9, 2021). Agriculture and construction are outdoor and heavy; electricity and industry (mining, manufacturing, water) are indoor and moderate; each services group follows Table 2a (Eq. 17a). Construction, industry and services form the *other* sector with national employment shares (Eq. 18).
* **Quarters.** Monthly capacities are averaged over the complete quarters of the path, weighted by the days of each month, and the shock is 1 − scenario / neutral for each draw (Eqs. 3 and 19).

### The services assumptions (Table 2a)

`data/labour/services_assumptions.csv` holds, for each services group, the share of workers outdoors, the share of indoor workers with air conditioning, and the work intensity. **These are draft assumptions for review, not data.** They were drafted by `analysis/draft_services_table.py` from the occupation mix of each group in PSA Table 11.8 (2021) and an assumed outdoor share per occupation, written at the top of that script (for example, drivers in transport 100 %, service and sales workers in trade 25 %). Only information and communication, and finance and insurance, are air-conditioned, as in the note's central case. Edit the CSV directly, or change the assumptions in the script and re-run it. Step 8 reads only the CSV.

### Outputs in `outputs/labour/`

| File | Content |
|---|---|
| `observed_wbgt_monthly_17regions.csv` | step 6: the six WBGT statistics and the observed capacity (`CAP_<env>_<intensity>`) by region and month |
| `wbgt_skill_summary.csv`, `wbgt_skill_17regions.csv`, `wbgt_skill_cells.csv` | step 7: hindcast skill of the WBGT statistics (plain and nested cross-validation) |
| `wbgt_model_configs.csv` | step 7: lag set and numbers of modes of each model |
| `wbgt_hist_fitted_17regions.csv` | step 7: fitted next to observed for every month and region |
| `shocks_quarterly.csv` | **step 8, the deliverable**: shock by sector, quarter and case. `shock_mean` is the central estimate and `shock_q90` the stress value named in the note. Positive = loss, as DEFINE-PH expects (one minus the shock). The `use` column says which rows go to the model |
| `shocks_monthly.csv`, `shocks_by_draw_quarterly.csv` | the central case by month, and for every draw |
| `capacity_regional_monthly.csv` | regional capacity by environment and intensity, neutral and scenario |
| `wbgt_shift_monthly.csv` | the shifts of the median and of the 90th percentile, scenario minus neutral, by region |
| `employment_shares.csv` | the employment figures and the shares ω used |

**Cases** in `shocks_quarterly.csv`: `central`; `outdoor_low` and `outdoor_high` (outdoor share of trade and transport at half and at one and a half times the central value); `aircon_all_indoor` and `aircon_none` (all, or none, of the indoor services work air-conditioned); `area_weights_in_regions`; and `national_area_average` (the area-weighted national mean of the cells in place of regions and regional employment, the note's sensitivity check).

### Where the labour steps differ from the note

* **Section 11.1, the El Niño effect.** The note estimates the effect on the median and the 90th percentile with a panel regression across regions. Here the two percentiles are predicted by the EOF-CCA, cell by cell, with the trend and the lags of Stage 1. The rest of Section 11.1 is unchanged. The comparison with the Stage 1 temperature response that the note asks for can be made with `T_coefficients_quarterly_17regions.csv`.
* **Weights within regions.** The note averages the cells of a region with area weights (Eq. 9). The population weights are used here, as agreed for labour, and the area weights are a sensitivity case.
* **Agriculture** is computed for reference only (the note proposes a zero input), and **Equation 13a**, the adjustment for the persistence of productivity in DEFINE-PH, is not applied: it needs the persistence coefficient from SOAS. `shocks_quarterly.csv` holds the shocks before that adjustment.
* **Working-time weights** τ are equal within the window, and every day of the month counts, including weekends.
* **Below the median**, the linear rule of Section 11.1 is applied as written, so the coolest hours shift less than the median hour and can shift the other way when the 90th percentile moves more than the median. These hours have a capacity close to one, so this has almost no effect on the shocks.
