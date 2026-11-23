# RiceAtlas (rice crop calendars)

**Source:** Laborte, A. G. et al. (2017), "RiceAtlas, a spatial database of global rice calendars and
production", *Scientific Data* 4:170074. Harvard Dataverse, doi:10.7910/DVN/JE6R48. Downloaded by
Ginevra on 20 Nov 2026 ("dataverse_files"); copied here unchanged and made read-only on 23 Nov 2026.

**Files:**
- `RiceCalendar_v1.zip` (gitignored, 107 MB; SHA-256 607f58db…5f15): shapefile with the planting and harvest
  dates per season. Only the attribute table (`RiceCalendar_v1.dbf`) is used.
- `RiceProduction_v1.zip` (gitignored, 98 MB; SHA-256 4f490dac…bfff): production per season and month. Not used yet
  (possible check against the PSA quarterly production).
- `RiceCalendar_v1_variables.csv`, `RiceProduction_v1_variables.csv`: variable descriptions.

To rebuild, download the two zips from the Dataverse record into this folder.

**Use:** `scripts/build_rice_calendar.py` → growing windows by region and harvest quarter for the
Stage 2 weather features (`data/processed/rice_growing_window.csv`).

**Philippines:** 81 provinces in all 16 regions. One fixed calendar, no irrigated/rainfed split.
