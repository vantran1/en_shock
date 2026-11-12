# Cropland weights of the 16 regions (with the island fix)

Weights for Eq. 7 of the agricultural note: for each region, the share of its cropland (ESA CCI land cover, 2022) that lies in each ERA5 cell kept by the model. Use these exact weights in Stage 2.

Run: `python scripts/make_regions.py` (once), then `python scripts/cropland_weights.py`.

| File | Content |
|---|---|
| `cropland_weights_16regions.csv` | one row per (region, kept cell). `w_cropland` is the weight (rows of a region sum to 1); `cropland_km2` and `area_km2` are what the weight is built from; `*_reassigned_km2` is the part that came from dropped cells (see below); `w_area` is the area-weighted alternative |
| `island_reassignment_16regions.csv` | one row per piece of land moved from a dropped cell to a kept cell: from-cell, to-cell, `distance_km` between the two cell centres, `farther_than_threshold` (> 100 km, `--far-km` to change), `to_cell_in_other_region`, cropland moved and its share of the region's cropland |
| `kept_cells.csv` | the 367 ERA5 cells kept by the model (land fraction >= 0.5 and not a sea point of ERA5), input of the script |
| `esa_cci_lc_2022_phl.nc` | land cover (input). Classes 10, 11, 12, 20 count fully as cropland, 30 as 75 %, 40 as 25 % |

**Island fix.** ERA5 cells with land fraction < 0.5 are dropped, which leaves small islands (and some coastal slivers) without a cell. Each such piece is moved to the nearest kept cell (distance between cell centres). Only kept cells are candidates, and these are all in Philippine territory, so a cell in Sabah or Indonesia is never chosen. The cropland stays with the island's own region, so a cell that receives an island from another region counts for both regions. Equally distant cells are broken by the lowest cell index, which makes the result identical on every machine.
