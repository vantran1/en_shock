# Van's cropland-weight outputs (reference copy, do not edit)

`cropland_weights/` and `scripts/cropland_weights.py`: copied on 2026-11-17 from branch `dev_Van`,
commit f879f0f2b5838001259f53b1fd11c4e387b2eb22 ("Build kept cells from the ERA5 land-sea mask (349
cells)"), byte-identical (blob hashes checked). Kept cells: ERA5 land fraction ≥ 0.5 (v5 §3.3.2), 349
cells, now written by the script (they replace the earlier 367-cell list of commit 084fa70, which used
polygon coverage). The weights in `cropland_weights_16regions.csv` (`w_cropland`) are those of
`scripts/build_weather_monthly.py` (v5 Eq. 7).

`boundaries/`: copied on 2026-11-12 from commit 084fa70d038896379406d8c161a35887934fec58 ("Adding
agricultural regions and weights."), unchanged since.

- `cropland_weights/`: Van's `data/agriculture/cropland_weights/` (weights, island reassignment, kept cells,
  ESA CCI land cover 2022 clip `esa_cci_lc_2022_phl.nc`, gitignored by the `*.nc` rule; 1.2 MB).
- `boundaries/`: Van's `data/boundaries/` (16-region gpkg + json sidecar, geoBoundaries sources).

`scripts/cropland_weights.py` in this branch is his script, unchanged (same commit).

## Stage 1 hindcasts

16 regions, monthly 1950-07 to 2025-12. Each weather variable has four columns:
`_obs` (ERA5), `_fitted` (all years), `_cv` (year ± 2 held out, lags/modes chosen on all
years) and `_nested` (5-year block held out, lags/modes chosen without it).

- `hist_fitted_16regions_v2_2026-11-13.csv`: RONI + DMI, calendar-year blocks (email of 13 Nov 2026).
- `hist_fitted_16regions_roni_2026-11-16.csv`: RONI alone, July–June blocks, old kept cells (email of
  16 Nov 2026; superseded).
- `hist_fitted_16regions_roni_18fe296.csv`: **RONI alone, July–June blocks, the 349 ERA5-mask cells and
  cropland weights (dev_Van commit 18fe296, `stage1_enso_iod/outputs/agriculture/`; use this for
  stage 2)**. Its `_obs` columns equal our `data/processed/weather_region_month.csv` (checked 17 Nov).
- `hist_fitted_16regions_roni_dmi_18fe296.csv`: the RONI + DMI variant of the same commit
  (`outputs/variants/roni_dmi/agriculture/`).
- `hist_fitted_16regions_roni_dmi_2026-11-16.csv`: RONI + DMI variant (his `outputs/variants/roni_dmi/`),
  July–June blocks; identical to the 13 Nov file except the nested values of January–June (checked).

The email copies (13 and 16 Nov) used Van's earlier 367-cell list (polygon coverage); the 18fe296
files use the 349 ERA5-mask cells (agreed with Van, 17 Nov 2026).
