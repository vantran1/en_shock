# Population

`phl_ppp_2020_1km_Aggregated_UNadj.tif`: WorldPop 2020 population counts, Philippines, 1 km, adjusted to
UN totals, aggregated to 1 km (file name as distributed by WorldPop). Copied on 24 Nov 2026 from Van's branch
(`dev_Van`, `data/shared/population/`), where it is the population weight of the electricity and labour
channels, so that all channels use the same population. Source: WorldPop (www.worldpop.org).

Used by `scripts/build_national_hazard_controls.py` (population-weighted national typhoon and flood
exposure, check version for the food price equation).
