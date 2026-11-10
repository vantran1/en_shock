# El Niño Shocks on Macroeconomic Models

This GitHub explores the application of machine learning models to predict agricultural, labor, and hydropower shocks from El Niño and the Indian Ocean Dipole (IOD).

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-in%20development-orange)

## Motivation
 
El Niño-Southern Oscillation (ENSO) is one of the strongest drivers of year-to-year climate variability, and the Indian Ocean Dipole (IOD) is a second major mode that often co-occurs with it and can amplify or offset its regional effects. Their effects propagate through the real economy: crop yields fall or rise, heat and rainfall anomalies change how much people can safely work, and shifts in precipitation alter reservoir inflows and hydropower output. Macroeconomic models typically treat these as exogenous noise. This project asks whether machine learning can turn ENSO and IOD signals into usable, forecastable shock estimates that feed into macroeconomic analysis.

## Research Questions
 
1. How well can ML models predict sector-level shocks (agriculture, labor, hydropower) from El Niño indicators?
2. How do ENSO and IOD interact? Do joint events produce larger or different shocks than either mode alone?
3. How do ML-based shock estimates compare with traditional econometric baselines (e.g., distributed-lag regression approaches)?
4. Can predicted shocks be integrated into macroeconomic models to improve scenario analysis?

## Data Sources
 
- **ENSO indices:** NOAA Climate Prediction Center (Niño 3.4, ONI/RONI)
- **IOD index:** NOAA Physical Sciences Laboratory (Dipole Mode Index, DMI)
- **Climate reanalysis:** ECMWF ERA5 (temperature, precipitation, humidity)
- **Agriculture:** OpenSTAT
- **Labor:** TBD
- **Hydropower:** TBD

## Getting Started
 
```bash
# Clone the repository
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

## Data

Raw inputs sit in `data/`, one folder per source (there is no `data/raw/`); they are
read-only. Derived files go to `data/processed/` and are rebuilt by the scripts below.
Large or licensed inputs are kept out of git (marked "local").

### Regions

All agricultural series, weather and controls use the **16 regions of methodology v5**:
the structure before the Negros Island Region (2024), so Negros Occidental is in VI and
Negros Oriental and Siquijor in VII for all years; Sulu and Cotabato City in BARMM for all
years; no NCR. From 2023 the PSA BARMM total includes the Eight Cluster Areas (63 barangays
of Cotabato province, Region XII until 2022), which are in no province row: their output
(BARMM total minus BARMM provinces) is added to XII, so both regions keep their pre-2023
boundaries. Region codes (R01–R13, R04A, CAR, MIMAROPA, BARMM) follow Van's boundary file.
Rules: `src/agriculture/regions.py`, `src/agriculture/rebuild.py`.

### Sources

| File | Source | Version / downloaded | Used by |
|---|---|---|---|
| `data/agriculture/palay_and_corn_volume.csv`, `palay_and_corn_area.csv` | PSA OpenSTAT tables 2E4EVCP0 (production, t) and 2E4EAHC0 (area harvested, ha), palay by ecosystem and corn by type, province × quarter | release of 29 Jul 2026, 1987Q1–2026Q2 | `build_rice_panel.py`, `build_crop_panel.py`, `hazards/weights.py` |
| `data/agriculture/psa_veg_root_crops_2010-2026.csv`, `psa_fruit_crops_2010-2026.csv` | PSA OpenSTAT, Vegetables and Root Crops / Fruit Crops: volume of production by region, province and quarter | downloaded 9 Nov 2026, 2010Q1–2026Q2 | `build_crop_panel.py` |
| `data/agriculture/fnri_calorie_factors.csv` | FNRI PhilFCT, compiled by A. Aras (UNDRR ROAP), 9 Nov 2026 | one row per PSA commodity | `build_crop_panel.py` (`agriculture/calories.py`) |
| `data/agriculture/FNRI_calorie_factors_VR_PF_v35.xlsx` (local, gitignored) | Alper Aras, UNDRR ROAP: calorie factors, shares and quarterly VR/PF indices | v35 | comparison in `build_crop_panel.py` |
| `data/roni/`, `data/oni/`, `data/dmi/` | NOAA CPC (RONI, ONI; ERSST and OISST) and NOAA PSL (DMI, HadISST) | in the repo since 12 Oct 2026 | `src/climate/indices.py` |
| ERA5 monthly single levels (local: folder `era5_monthly_dir` in `config/paths.toml`) | Copernicus CDS, `reanalysis-era5-single-levels-monthly-means`, monthly averaged reanalysis, 0.25°, N22 W116 S4 E127.5, 11 variables, 1950–2025 (one `.json` download record per file) | downloaded 28–31 Oct 2026 by `scripts/01_download_era5.py` | `src/climate/era5.py`, `build_weather_monthly.py`, `check_era5.py` |
| `data/era5/era5_land_sea_mask_0.25deg_phl.nc` | Copernicus CDS, ERA5 land-sea mask (same grid) | downloaded 9 Nov 2026 | `build_weather_monthly.py` |
| `data/boundaries/phl_16_regions.gpkg` (+ `.json`) | built by `scripts/make_regions.py` (Van, branch `dev_Van`, commit 8271a50, copied unchanged) from geoBoundaries gbOpen PHL ADM1/ADM2, simplified, 2020 vintage (NAMRIA/PSA/OCHA), CC BY 3.0 IGO | the script downloads geoBoundaries `main` (not a pinned release), so the output is committed; downloaded 10 Nov 2026, same files (sha256 in the `.json`) as Van's check of 21 Oct 2026 | `build_weather_monthly.py`, `hazards/geophysical.py` |
| `data/hazards/boundaries/geoBoundaries-PHL-ADM2_simplified.geojson` | geoBoundaries gbOpen PHL ADM2, commit 41af8f1 | downloaded 20 Oct 2026 | typhoon and flood controls |
| `data/hazards/ibtracs/` (local, 109 MB) | IBTrACS v04r01, Western Pacific (NOAA NCEI) | downloaded 20 Oct 2026 by `scripts/download_hazards.py` | `build_typhoon_exposure.py` |
| `data/hazards/emdat/` (local, licence: no redistribution) | EM-DAT (CRED), Philippines floods and storms 1986–2025 | downloaded by hand 20 Oct 2026 | `build_flood_exposure.py` |
| `data/hazards/earthquakes/usgs_earthquakes_m6.5_1987-2025.csv` | USGS ComCat, M ≥ 6.5, Philippines, 1987–2025 | downloaded 9 Nov 2026 | `build_geophysical_controls.py` |
| `data/hazards/volcanoes/gvp_volcano_list_holocene_v5.4.0.xlsx` | Smithsonian Global Volcanism Program, Holocene volcano list | v5.4.0, downloaded 9 Nov 2026 | `build_geophysical_controls.py` |
| `data/hazards/volcanoes/gvp_eruption_list_holocene_20260424.xlsx` | GVP, confirmed Holocene eruptions (the only eruption spreadsheet GVP offers during its 2026 website rebuild) | generated 24 Apr 2026 from v5.3.5 | `build_geophysical_controls.py` |

More detail on the hazard downloads: `data/hazards/DOWNLOADS.txt`, `data/era5/DOWNLOADS.txt`.

Notes:
- Kanlaon's October 2024 eruption is VEI 2 in the GVP eruption file but VEI 3 in the current
  GVP database, so it is not among the eruptions with VEI ≥ 3 (Kanlaon's June 2024 eruption,
  VEI 3, is).
- `data/agriculture/palay_yield.csv` and `corn_yield.csv` (origin unknown, published
  boundaries, no ecosystem split) are not used.

### Local paths

Copy `config/paths.example.toml` to `config/paths.toml` (gitignored) and set
`era5_monthly_dir`; scripts that read ERA5 also take `--era5-dir`. The `.nc` files are never
copied into or committed to the repo (`*.nc` is gitignored except the land-sea mask).

### Processed data (`data/processed/`)

| File | Content | Script |
|---|---|---|
| `crop_region_quarter.csv` | long panel: `group`, `series`, `region_code`, `period`, `variable` (`production_t` t, `area_ha` ha, `energy_bkcal` billion kcal, `index` 2021–2023 = 100), `value`, `provisional` (2026). Palay (irrigated, rainfed, total) and corn (white, yellow, total) 1987Q1–2026Q2; the 13 VR and PF crops (bananas by variety) and the calorie indices `vr`, `vr_noroot`, `pf`, `pf_nobanana`, `pf_nocavendish` 2010Q1–2026Q2 | `build_crop_panel.py` |
| `barmm_cluster_residual.csv` | Eight Cluster Areas (BARMM total − BARMM provinces) by crop and quarter | `build_crop_panel.py` |
| `weather_region_month.csv` | **PROVISIONAL: cells weighted by area, to be replaced by Van's cropland weights (v5 Eq. 7).** Region × month, 1950-01–2025-12: `t2m_c`, `d2m_c` (°C), `tp_mm`, `e_mm`, `pev_mm`, `ro_mm` (mm/month; evaporation positive), `ssrd_mj` (MJ m⁻² day⁻¹), `swvl1`–`swvl4`, `swvl_rz` (m³ m⁻³), `rh_pct` (%), `vpd_kpa` (kPa) | `build_weather_monthly.py` |
| `era5_region_cells.csv` | ERA5 land cells used per region and their (provisional, area) weights | `build_weather_monthly.py` |
| `geophysical_region_quarter.csv` | `eq`, `eq_next`, `eruption`, `eruption_kanlaon_vi_vii`, `pinatubo_1991` by region × quarter, 1987Q1–2026Q2 | `build_geophysical_controls.py` |
| `typhoon_region_quarter.csv`, `typhoon_storm_province.csv` | typhoon exposure by PAGASA category (rice-production weights) | `build_typhoon_exposure.py` |
| `flood_region_quarter.csv` | flood occurrence (rice-production weights) | `build_flood_exposure.py` |
| `rice_region_quarter.csv`, `province_region_map.csv` | rice panel with area; province → region map | `build_rice_panel.py` |

Validation report: `outputs/panel_validation.md` (`scripts/report_panel.py`).

### Direct model (agriculture)

**Recommended specification — differs from the current methodology (v5).** It is v5,
Eqs. (4)-(6), with the changes the palay data support: El Niño and La Niña with separate
effects, smooth regional trends, effects that shift from 2000 on, and a wet-season shift
(Poisson main, log-LS check). It fits and predicts the past El Niño episodes better than
the v5 specification, so we suggest going forward with it; the changes are proposed to
Alper and are not in the v5 text yet.
Code: `src/estimation/direct.py`; palay: `scripts/estimate_direct_rice.py` (results in
`outputs/tables/direct_rice_*`, provisional, column `spec_note`). Specification tests and
leave-one-episode-out validation: `scripts/compare_direct_v5_rice.py`, which also runs the
current-methodology (v5 base) version. The free-lag first look
(`scripts/estimate_rice_direct.py`) is kept for comparison.

### Rebuilding from scratch

```bash
python scripts/make_regions.py                # 16-region boundaries (downloads geoBoundaries)
python scripts/download_hazards.py            # IBTrACS + ADM2 boundaries
python scripts/01_download_era5.py            # ERA5 monthly, to era5_monthly_dir (needs ~/.cdsapirc)
python scripts/check_era5.py
python scripts/build_rice_panel.py
python scripts/build_crop_panel.py
python scripts/build_weather_monthly.py
python scripts/check_island_coverage.py     # provinces with no ERA5 cell
python scripts/build_typhoon_exposure.py
python scripts/build_flood_exposure.py        # needs the EM-DAT file
python scripts/build_geophysical_controls.py
python scripts/report_panel.py
```

### Attribution

- ERA5 (CC-BY 4.0): Contains modified Copernicus Climate Change Service information [2026].
  Neither the European Commission nor ECMWF is responsible for any use of this information.
- Calorie factors: FNRI PhilFCT, compiled by A. Aras (UNDRR ROAP), 9 Nov 2026.
- Volcanoes: Global Volcanism Program, 2026. [Database] Volcanoes of the World (v. 5.4.0;
  7 Aug 2026). Distributed by Smithsonian Institution, compiled by Venzke, E.
  https://doi.org/10.5479/si.GVP.VOTW5-2026.5.4 (the eruption list was generated on
  24 Apr 2026 from v. 5.3.5).
- Boundaries: geoBoundaries (Runfola et al. 2020), CC BY 3.0 IGO.
- Earthquakes: U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog (ComCat).
- Typhoon tracks: IBTrACS v04r01 (Knapp et al. 2010; Gahtan et al. 2024), NOAA NCEI.
- Floods: EM-DAT, CRED / UCLouvain, www.emdat.be (not redistributed).
