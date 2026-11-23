# GGCMI Phase 3 crop calendar, maize

**Source:** Jägermeyr, J. et al. (2021), "Climate impacts on global agriculture emerge earlier in new
generation of climate and crop models", *Nature Food* 2:873–885; crop calendar on Zenodo,
doi:10.5281/zenodo.5062513, version 1.01 (CC BY 4.0). Downloaded by Ginevra on 23 Nov 2026 and copied
here unchanged (read-only).

**Files** (0.5° global grid; planting_day, maturity_day, growing_season_length, data_source_used):
- `mai_rf_ggcmi_crop_calendar_phase3_v1.01.nc4`: rainfed maize (md5 30886422bdfb9d3655e8396c4f7cff41)
- `mai_ir_ggcmi_crop_calendar_phase3_v1.01.nc4`: irrigated maize (md5 b51586de1f1017ab06439300386b1abb)

**Use:** `scripts/build_corn_calendar.py` → corn growing windows for Stage 2
(`data/processed/corn_growing_window.csv`).

**Philippines:** one season per cell, mostly the wet-season crop (planted around May, harvested
July–September); sources Dimou et al. 2018, MIRCA2000, SAGE, Iizumi et al. 2019. The GGCMI rice files
were not kept: for the Philippines they are taken from RiceAtlas (data/agriculture/riceatlas).
