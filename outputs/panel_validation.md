# Region x quarter panel: validation report

Built by `scripts/build_crop_panel.py`, `scripts/build_weather_monthly.py`, `scripts/build_geophysical_controls.py`; this report by `scripts/report_panel.py`. Rules follow methodology v5 (16 regions, pre-2024 structure). No model is estimated.

## 1. Regions and coverage

Every series has **16 regions** 
| group | series | n_regions | first | last |
|---|---|---|---|---|
| corn | corn | 16 | 1987Q1 | 2026Q2 |
| corn | corn_white | 16 | 1987Q1 | 2026Q2 |
| corn | corn_yellow | 16 | 1987Q1 | 2026Q2 |
| palay | palay | 16 | 1987Q1 | 2026Q2 |
| palay | palay_irrigated | 16 | 1987Q1 | 2026Q2 |
| palay | palay_rainfed | 16 | 1987Q1 | 2026Q2 |
| pf | banana_bungulan | 16 | 2010Q1 | 2026Q2 |
| pf | banana_cavendish | 16 | 2010Q1 | 2026Q2 |
| pf | banana_lakatan | 16 | 2010Q1 | 2026Q2 |
| pf | banana_latundan | 16 | 2010Q1 | 2026Q2 |
| pf | banana_others | 16 | 2010Q1 | 2026Q2 |
| pf | banana_saba | 16 | 2010Q1 | 2026Q2 |
| pf | calamansi | 16 | 2010Q1 | 2026Q2 |
| pf | mango | 16 | 2010Q1 | 2026Q2 |
| pf | pineapple | 16 | 2010Q1 | 2026Q2 |
| vr | ampalaya_fruit_bitter_gourd | 16 | 2010Q1 | 2026Q2 |
| vr | cabbage | 16 | 2010Q1 | 2026Q2 |
| vr | camote_sweet_potato | 16 | 2010Q1 | 2026Q2 |
| vr | cassava_fresh_tubers | 16 | 2010Q1 | 2026Q2 |
| vr | eggplant | 16 | 2010Q1 | 2026Q2 |
| vr | mongo_mungbean | 16 | 2010Q1 | 2026Q2 |
| vr | onion_mature_bulb | 16 | 2010Q1 | 2026Q2 |
| vr | potato | 16 | 2010Q1 | 2026Q2 |
| vr | tomato | 16 | 2010Q1 | 2026Q2 |

## 2. Missing values

Region-quarters where every province of the region is '..' (within the crop's span). All other region-quarters have data. These are regions that do not grow the crop (e.g. Cavendish banana in Luzon); in the calorie indices they count as zero.

| crop | region_code | quarters_missing |
|---|---|---|
| Banana Cavendish | CAR | 56 |
| Banana Cavendish | MIMAROPA | 44 |
| Banana Cavendish | R01 | 56 |
| Banana Cavendish | R02 | 1 |
| Banana Cavendish | R03 | 64 |
| Banana Cavendish | R04A | 4 |
| Banana Cavendish | R05 | 56 |
| Mango | CAR | 16 |
| Mango | R02 | 13 |
| Mango | R03 | 7 |
| Mango | R04A | 15 |
| Pineapple | R03 | 4 |

## 3. National totals

Sum of the 16 rebuilt regions against the PHILIPPINES row of the PSA tables, every quarter. Largest relative gap: 1.4e-05 (rounding of the published figures), so the regions add up to the national total, including the Eight Cluster Areas (section 4).

| crop | max_rel_gap_production_t | max_rel_gap_area_ha | quarters_gap_over_1e-6 | source |
|---|---|---|---|---|
| Corn | 8.5e-09 | 1.7e-08 | 0 | palay/corn |
| Irrigated Palay | 5.5e-09 | 1.8e-08 | 0 | palay/corn |
| Palay | 7.1e-09 | 2.3e-08 | 0 | palay/corn |
| Rainfed Palay | 1.8e-08 | 4.8e-08 | 0 | palay/corn |
| White Corn | 1.2e-07 | 8.0e-08 | 0 | palay/corn |
| Yellow Corn | 1.6e-08 | 3.7e-08 | 0 | palay/corn |
| Ampalaya fruit [Bitter gourd] | 1.8e-06 |  | 4 | VR/PF |
| Banana Bungulan | 9.1e-07 |  | 0 | VR/PF |
| Banana Cavendish | 2.6e-08 |  | 0 | VR/PF |
| Banana Lakatan | 1.6e-07 |  | 0 | VR/PF |
| Banana Latundan | 1.8e-07 |  | 0 | VR/PF |
| Banana Others | 1.8e-06 |  | 2 | VR/PF |
| Banana Saba | 5.8e-08 |  | 0 | VR/PF |
| Cabbage | 8.9e-07 |  | 0 | VR/PF |
| Calamansi | 1.3e-06 |  | 1 | VR/PF |
| Camote [Sweet potato] | 5.9e-07 |  | 0 | VR/PF |
| Cassava, fresh tubers | 3.9e-08 |  | 0 | VR/PF |
| Eggplant | 1.3e-06 |  | 1 | VR/PF |
| Mango | 7.3e-07 |  | 0 | VR/PF |
| Mongo [Mungbean] | 1.4e-05 |  | 27 | VR/PF |
| Onion, mature bulb | 3.0e-06 |  | 3 | VR/PF |
| Pineapple | 4.1e-08 |  | 0 | VR/PF |
| Potato | 1.4e-06 |  | 1 | VR/PF |
| Tomato | 1.2e-06 |  | 1 | VR/PF |

## 4. BARMM and the Eight Cluster Areas

From 2023Q1 PSA's BARMM total includes the Eight Cluster Areas (63 barangays of the Province of Cotabato, Region XII until 2022), which are in no province row. Their output, BARMM total minus the BARMM provinces, is added to Region XII from 2023Q1, so both regions keep their pre-2023 boundaries. Before 2023 the residual is zero for every crop. Residual by crop and year (t, and % of the BARMM provinces; 2026 = Q1–Q2):

| series | t 2023 | t 2024 | t 2025 | t 2026 | % 2023 | % 2024 | % 2025 | % 2026 |
|---|---|---|---|---|---|---|---|---|
| ampalaya_fruit_bitter_gourd | 0.00 | 5.50 | 2.24 | -0.01 | 0.00 | 0.39 | 0.16 | -0.00 |
| banana_lakatan | -0.00 | 0.00 | 0.02 | 161.22 | -0.00 | 0.00 | 0.00 | 0.22 |
| banana_latundan | 0.00 | 0.22 | 0.57 | 0.78 | 0.00 | 0.00 | 0.00 | 0.00 |
| banana_saba | -0.00 | 2,077.41 | 2,191.54 | 1,214.84 | -0.00 | 1.22 | 1.09 | 1.13 |
| camote_sweet_potato | 0.00 | 10.92 | 2.73 | 2.43 | 0.00 | 0.27 | 0.06 | 0.14 |
| cassava_fresh_tubers | -0.00 | 10.98 | 2,726.08 | 3,181.31 | -0.00 | 0.00 | 0.26 | 0.92 |
| corn | 66,466.19 | 58,132.99 | 68,236.00 | 39,658.00 | 5.70 | 4.97 | 5.69 | 7.18 |
| corn_white | 8,990.48 | 5,038.00 | 5,354.00 | 2,587.00 | 1.74 | 1.04 | 1.09 | 1.29 |
| corn_yellow | 57,475.71 | 53,095.00 | 62,882.00 | 37,071.00 | 8.85 | 7.74 | 8.87 | 10.54 |
| eggplant | 0.00 | 5.00 | 1.97 | 656.15 | 0.00 | 0.51 | 0.09 | 32.53 |
| mango | 0.00 | 35.74 | 0.01 | 342.88 | 0.00 | 0.23 | 0.00 | 2.51 |
| palay | 45,159.48 | 61,083.00 | 62,659.00 | 17,106.00 | 5.31 | 7.14 | 7.10 | 4.28 |
| palay_irrigated | 35,746.27 | 47,997.00 | 49,260.00 | 14,294.00 | 14.14 | 19.00 | 18.50 | 10.27 |
| palay_rainfed | 9,413.20 | 13,086.00 | 13,399.00 | 2,812.00 | 1.58 | 2.17 | 2.17 | 1.08 |

The residual is mainly palay and corn (the cluster areas are lowland farmland). Maguindanao del Norte and del Sur are parts of the Maguindanao row in the VR table from 2025 and are dropped there to avoid counting them twice (in the fruit table the Maguindanao row is empty from 2025 and the two halves are used).

## 5. Negros Island Region: VI and VII across 2023–2024

Annual production (palay and corn in t, VR and PF in billion kcal) of VI and VII as rebuilt, of the provinces PSA moved to NIR, and of the country. The Negros provinces are present in every year, so adding them back leaves no gap. The 2024 falls in VI and VII come from their own provinces (VI palay: Iloilo -22%) in the 2024 El Niño year. One series to ask PSA about: Negros Occidental corn halves in 2024 (-49%) and falls again in 2025, the year it starts being reported under NIR.

| series | unit | 2021 | 2022 | 2023 | 2024 | 2025 | pct_change_2023_2024 |
|---|---|---|---|---|---|---|---|
| corn | Negros Occidental | 159,888.0 | 155,196.0 | 136,091.0 | 69,977.1 | 51,840.0 | -48.6 |
| corn | Negros Or. + Siquijor | 49,174.0 | 40,181.0 | 50,765.8 | 42,599.0 | 47,889.1 | -16.1 |
| corn | PHILIPPINES | 8,287,191.1 | 8,255,609.7 | 8,405,004.3 | 8,138,177.9 | 8,318,911.8 | -3.2 |
| corn | R06 | 351,433.7 | 344,460.6 | 329,148.8 | 250,316.1 | 253,698.6 | -24.0 |
| corn | R07 | 107,314.0 | 97,156.4 | 119,555.3 | 94,323.7 | 116,943.2 | -21.1 |
| palay | Negros Occidental | 483,534.0 | 460,535.0 | 486,053.6 | 427,871.6 | 425,158.4 | -12.0 |
| palay | Negros Or. + Siquijor | 66,719.0 | 60,409.4 | 68,308.6 | 71,825.2 | 98,464.1 | 5.1 |
| palay | PHILIPPINES | 19,960,170.2 | 19,756,513.4 | 20,059,562.0 | 19,087,135.4 | 19,674,390.0 | -4.8 |
| palay | R06 | 2,356,902.4 | 2,321,593.7 | 2,263,158.3 | 1,891,368.1 | 1,910,916.4 | -16.4 |
| palay | R07 | 289,502.0 | 242,394.6 | 293,073.4 | 316,573.6 | 347,068.1 | 8.0 |
| pf | Negros Occidental | 64.8 | 64.6 | 69.1 | 68.6 | 67.3 | -0.7 |
| pf | Negros Or. + Siquijor | 78.4 | 63.7 | 102.8 | 76.3 | 75.2 | -25.7 |
| pf | PHILIPPINES | 7,232.0 | 7,183.8 | 7,229.7 | 6,996.2 | 6,899.6 | -3.2 |
| pf | R06 | 232.4 | 229.9 | 236.0 | 235.6 | 240.6 | -0.2 |
| pf | R07 | 177.8 | 138.9 | 186.1 | 162.4 | 164.1 | -12.7 |
| vr | Negros Occidental | 53.7 | 53.3 | 53.2 | 53.2 | 52.8 | 0.1 |
| vr | Negros Or. + Siquijor | 39.9 | 38.3 | 40.2 | 33.2 | 30.6 | -17.4 |
| vr | PHILIPPINES | 3,850.2 | 3,882.8 | 3,834.6 | 3,600.4 | 3,508.2 | -6.1 |
| vr | R06 | 131.4 | 132.4 | 129.3 | 125.5 | 126.2 | -2.9 |
| vr | R07 | 95.4 | 90.3 | 92.5 | 78.2 | 74.2 | -15.4 |

## 6. Banana varieties

The six varieties add up to the 'Banana' row in every published row and quarter:

| level | rows_compared | max_abs_gap_t | rows_gap_over_1t | max_rel_gap |
|---|---|---|---|---|
| province | 5416 | 0.02 | 0 | 0.00077 |
| region | 1066 | 0.02 | 0 | 3.7e-06 |

## 7. Calorie indices compared with Alper's workbook

Sheet 'Quarterly indices' of FNRI_calorie_factors_VR_PF_v35.xlsx (A. Aras, built from PSA's regional table). Alper combines VI + VII + NIR into one unit, compared with our R06 + R07. His sheet has no 'PF without Cavendish' (our extra check) and runs to 2026Q3, one quarter beyond our files. kcal per kg is recomputed from the factor file and matches its own column.

**Identical** (largest index difference < 0.05 points): CAR, MIMAROPA, PH, R01, R02, R03, R04A, R05, R06+R07, R08, R10, R11, R13.

**Different, as expected from the boundary rules**: BARMM and XII from 2023 (Eight Cluster Areas moved from BARMM to XII here, in BARMM in Alper's regional table), and IX and BARMM in 2026 (Sulu kept in BARMM here, under IX in PSA's 2026 table). Largest absolute index difference (points), by window:

| unit | series | 2010-2022 | 2023-2025 | 2026 |
|---|---|---|---|---|
| BARMM | pf | 0.000 | 0.695 | 2.044 |
| BARMM | pf_nobanana | 0.000 | 0.846 | 5.458 |
| BARMM | vr | 0.000 | 0.989 | 9.686 |
| BARMM | vr_noroot | 0.001 | 0.086 | 5.233 |
| R09 | pf | 0.000 | 0.000 | 5.506 |
| R09 | pf_nobanana | 0.000 | 0.000 | 0.226 |
| R09 | vr | 0.000 | 0.000 | 86.505 |
| R09 | vr_noroot | 0.003 | 0.000 | 2.322 |
| R12 | pf | 0.000 | 0.265 | 0.330 |
| R12 | pf_nobanana | 0.000 | 0.023 | 0.177 |
| R12 | vr | 0.000 | 10.487 | 10.248 |
| R12 | vr_noroot | 0.000 | 0.190 | 14.074 |

## 8. Weather (ERA5 monthly)

`weather_region_month.csv`: 16 regions x 912 months (1950-01 to 2025-12). 349 ERA5 cells with land fraction > 0.5; 27 of them have their centre just outside the simplified coastline and go to the nearest region (at most 11 km). See `outputs/figures/era5_land_sea_mask.png`.

| region_code | cells | nearest | max_distance_km |
|---|---|---|---|
| BARMM | 13 | 1 | 2.7 |
| CAR | 25 | 0 | 0.0 |
| MIMAROPA | 22 | 2 | 6.6 |
| R01 | 15 | 1 | 11.1 |
| R02 | 34 | 0 | 0.0 |
| R03 | 28 | 3 | 1.5 |
| R04A | 18 | 3 | 4.3 |
| R05 | 18 | 3 | 3.0 |
| R06 | 28 | 4 | 6.4 |
| R07 | 14 | 2 | 2.4 |
| R08 | 27 | 3 | 3.8 |
| R09 | 15 | 1 | 0.1 |
| R10 | 20 | 1 | 1.8 |
| R11 | 27 | 1 | 6.1 |
| R12 | 21 | 1 | 4.1 |
| R13 | 24 | 1 | 1.0 |

Caveats:
- Provinces with no ERA5 cell (land fraction > 0.5) at 0.25°, so not represented in their region's weather: Basilan, Batanes, Biliran, Camiguin, Catanduanes, City of Isabela, Cotabato City, Dinagat Islands, Guimaras, Marinduque, Romblon, Siquijor, Sulu, Tawi-Tawi. BARMM's weather comes from mainland Mindanao (Lanao del Sur, Maguindanao) only.
- Cells are weighted by area; v5 Eq. 7 weights by cropland area, whose source (ESA WorldCover or CCI) is to be confirmed.
- RH and VPD are computed from the monthly means of t2m and d2m (v5 Table 2). Because saturation vapour pressure is convex, this slightly understates the monthly mean of daily VPD; the hourly-based variables of Table 2 will correct this.
- ERA5 potential evaporation is known to be unreliable over land; for the climatic water balance an FAO-56 estimate from t2m, d2m and ssrd is preferable.

## 9. Earthquakes

USGS ComCat, M >= 6.5, 1987–2025: 78 events; 62 kept, dropped 14 deeper than 300 km, 2 more than 100 km from land. Kept events are assigned to the nearest region (distance 0 = epicentre on land); time in Philippine Time. Markers: `eq` (event quarter), `eq_next` (event quarter and the next).

| date | period | mag | depth | dist_land_km | region_code | place |
|---|---|---|---|---|---|---|
| 2025-10-10 | 2025Q4 | 6.7 | 47.0 | 9.0 | R11 | 12 km SE of Santiago, Philippines |
| 2025-10-10 | 2025Q4 | 7.4 | 59.4 | 9.4 | R11 | 12 km E of Santiago, Philippines |
| 2025-09-30 | 2025Q3 | 6.9 | 10.0 | 8.2 | R07 | 8 km ESE of Calape, Philippines |
| 2024-08-03 | 2024Q3 | 6.8 | 32.0 | 18.0 | R13 | 20 km E of Barcelona, Philippines |
| 2024-01-09 | 2024Q1 | 6.7 | 62.6 | 91.6 | R11 | 93 km SE of Sarangani, Philippines |
| 2023-12-04 | 2023Q4 | 6.9 | 20.0 | 31.4 | R13 | 34 km ENE of Aras-asan, Philippines |
| 2023-12-03 | 2023Q4 | 6.6 | 19.0 | 38.4 | R13 | 47 km ENE of Hinatuan, Philippines |
| 2023-12-02 | 2023Q4 | 7.6 | 40.0 | 3.5 | R13 | 19 km E of Gamut, Philippines |
| 2023-11-17 | 2023Q4 | 6.7 | 52.0 | 30.8 | R12 | 32 km SW of Kablalan, Philippines |
| 2022-07-27 | 2022Q3 | 7.0 | 33.7 | 0.0 | CAR | 11 km NE of Bantay, Philippines |
| 2021-08-12 | 2021Q3 | 7.1 | 55.1 | 54.2 | R11 | 60 km ENE of Pondaguitan, Philippines |
| 2021-07-24 | 2021Q3 | 6.7 | 110.0 | 9.8 | R04A | 15 km S of Hukay, Philippines |
| 2020-08-18 | 2020Q3 | 6.6 | 10.0 | 3.0 | R08 | 13 km E of San Pedro, Philippines |
| 2019-12-15 | 2019Q4 | 6.8 | 18.0 | 0.0 | R11 | 7 km S of Magsaysay, Philippines |
| 2019-10-31 | 2019Q4 | 6.5 | 10.0 | 0.0 | R12 | 2 km ENE of Bulatukan, Philippines |
| 2019-10-29 | 2019Q4 | 6.6 | 15.0 | 0.0 | R12 | 10 km NE of Columbio, Philippines |
| 2018-12-29 | 2018Q4 | 7.0 | 60.2 | 90.4 | R11 | 96 km ESE of Pondaguitan, Philippines |
| 2017-07-06 | 2017Q3 | 6.5 | 9.0 | 0.0 | R08 | 2 km S of Lim-oo, Philippines |
| 2017-04-29 | 2017Q2 | 6.9 | 26.0 | 26.7 | R12 | 31 km SW of Burias, Philippines |
| 2017-02-10 | 2017Q1 | 6.5 | 15.0 | 0.1 | R13 | 11 km N of Mabua, Philippines |
| 2013-10-15 | 2013Q4 | 7.1 | 19.0 | 0.0 | R07 | 4 km SE of Sagbayan, Philippines |
| 2012-08-31 | 2012Q3 | 7.6 | 28.0 | 73.5 | R08 | 89 km E of Sulangan, Philippines |
| 2012-02-06 | 2012Q1 | 6.7 | 11.0 | 0.0 | R07 | 2 km NNE of Jimalalud, Philippines |
| 2008-03-03 | 2008Q1 | 6.9 | 24.0 | 95.9 | R08 | Philippine Islands region |
| 2004-10-08 | 2004Q4 | 6.5 | 105.0 | 8.6 | R04A | 9 km W of Talisay, Philippines |
| 2003-11-19 | 2003Q4 | 6.5 | 35.0 | 0.0 | R08 | 4 km NW of Can-Avid, Philippines |
| 2002-03-06 | 2002Q1 | 7.5 | 31.0 | 12.1 | R12 | Mindanao, Philippines |
| 2001-01-01 | 2001Q1 | 6.8 | 33.0 | 63.2 | R11 | Mindanao, Philippines |
| 2001-01-01 | 2001Q1 | 7.5 | 33.0 | 17.1 | R11 | 21 km SE of Lukatan, Philippines |
| 1999-12-12 | 1999Q4 | 7.3 | 33.0 | 5.6 | R03 | 14 km WNW of Bolitoc, Philippines |
| 1999-03-04 | 1999Q1 | 7.1 | 33.0 | 67.2 | BARMM | 69 km S of Tabiauan, Philippines |
| 1997-10-06 | 1997Q4 | 6.5 | 105.6 | 4.3 | R13 | 18 km E of Talisay, Philippines |
| 1996-09-20 | 1996Q3 | 6.6 | 33.0 | 21.5 | R13 | 24 km NE of Cortes, Philippines |
| 1996-09-20 | 1996Q3 | 6.6 | 33.0 | 19.2 | R13 | 22 km NNE of Cortes, Philippines |
| 1996-06-12 | 1996Q2 | 7.1 | 33.0 | 1.8 | R08 | 8 km NNE of Palapag, Philippines |
| 1995-05-05 | 1995Q2 | 7.1 | 16.0 | 13.5 | R08 | 14 km NE of Cabatuan, Philippines |
| 1995-04-23 | 1995Q2 | 6.8 | 24.1 | 6.3 | R08 | 10 km E of Gamay, Philippines |
| 1995-04-21 | 1995Q2 | 6.8 | 27.4 | 37.9 | R08 | 47 km E of Dapdap, Philippines |
| 1995-04-21 | 1995Q2 | 7.2 | 20.7 | 0.8 | R08 | 10 km E of Dapdap, Philippines |
| 1995-04-21 | 1995Q2 | 6.8 | 17.4 | 9.1 | R08 | 14 km ESE of Can-Avid, Philippines |
| 1995-04-21 | 1995Q2 | 6.9 | 20.1 | 10.4 | R08 | 19 km E of Dolores, Philippines |
| 1995-04-20 | 1995Q2 | 6.6 | 94.1 | 63.4 | R11 | 66 km E of Pondaguitan, Philippines |
| 1994-11-15 | 1994Q4 | 7.1 | 31.5 | 1.0 | R04A | 10 km E of Sabang, Philippines |
| 1993-05-18 | 1993Q2 | 6.8 | 168.6 | 62.3 | R02 | 77 km SE of Basco, Philippines |
| 1993-05-12 | 1993Q2 | 7.0 | 58.7 | 0.2 | R11 | 3 km E of Manay, Philippines |
| 1992-05-17 | 1992Q2 | 7.3 | 33.0 | 20.1 | R11 | 23 km ESE of Santiago, Philippines |
| 1992-05-17 | 1992Q2 | 7.1 | 32.8 | 6.2 | R11 | 9 km SE of Santiago, Philippines |
| 1991-11-13 | 1991Q4 | 6.8 | 35.9 | 1.9 | R13 | 4 km ESE of Hinatuan, Philippines |
| 1991-02-18 | 1991Q1 | 7.0 | 23.9 | 15.2 | R13 | 18 km E of Aras-asan, Philippines |
| 1990-10-25 | 1990Q4 | 6.5 | 44.1 | 6.9 | R13 | 13 km E of Tidman, Philippines |
| 1990-07-18 | 1990Q3 | 6.5 | 23.1 | 0.0 | R02 | 14 km NNW of Salinas, Philippines |
| 1990-07-16 | 1990Q3 | 7.7 | 25.1 | 0.0 | R03 | 4 km E of Macapsing, Philippines |
| 1990-06-14 | 1990Q2 | 7.1 | 18.1 | 0.0 | R06 | 0 km ESE of Union, Philippines |
| 1990-02-08 | 1990Q1 | 6.6 | 30.3 | 4.9 | R07 | 6 km ESE of Bacong, Philippines |
| 1990-02-08 | 1990Q1 | 6.8 | 25.9 | 10.9 | R07 | 13 km E of Bacong, Philippines |
| 1989-12-20 | 1989Q4 | 6.5 | 21.0 | 41.4 | R13 | 43 km ENE of Santa Maria, Philippines |
| 1989-12-16 | 1989Q4 | 7.6 | 24.4 | 31.8 | R13 | 37 km ENE of Barcelona, Philippines |
| 1988-11-17 | 1988Q4 | 6.6 | 19.3 | 0.0 | R08 | 10 km W of Polañge, Philippines |
| 1988-02-24 | 1988Q1 | 7.3 | 24.9 | 30.1 | R05 | 37 km ESE of Bato, Philippines |
| 1987-06-07 | 1987Q2 | 6.5 | 14.4 | 18.2 | R08 | 42 km SE of Sulangan, Philippines |
| 1987-05-12 | 1987Q2 | 6.7 | 24.7 | 19.8 | R11 | 22 km SE of Manay, Philippines |
| 1987-04-25 | 1987Q2 | 6.9 | 107.0 | 0.8 | R01 | 4 km N of Canaoalan, Philippines |

## 10. Volcanic eruptions

GVP eruption list joined to the volcano list; Philippines, VEI >= 3, start year >= 1987: **6 eruptions**. Region = the volcano's own region; Kanlaon to VI (check version `eruption_kanlaon_vi_vii` gives it to VI and VII). Pinatubo 1991 has its own marker `pinatubo_1991`. Kanlaon October 2024 is VEI 2 in this file (VEI 3 in the current GVP database), so it is not included.

| Volcano Name | VEI | start | end | first_quarter | last_quarter | region_of_coordinates | region_code | region_code_check |
|---|---|---|---|---|---|---|---|---|
| Pinatubo | 6 | 1991-04 | 1991-09 | 1991Q2 | 1991Q3 | R03 | R03 | R03 |
| Mayon | 3 | 1999-06 | 2000-03 | 1999Q2 | 2000Q1 | R05 | R05 | R05 |
| Mayon | 3 | 2001-01 | 2001-08 | 2001Q1 | 2001Q3 | R05 | R05 | R05 |
| Mayon | 3 | 2018-01 | 2019-07 | 2018Q1 | 2019Q3 | R05 | R05 | R05 |
| Taal | 4 | 2020-01 | 2020-01 | 2020Q1 | 2020Q1 | R04A | R04A | R04A |
| Kanlaon | 3 | 2024-06 | 2024-06 | 2024Q2 | 2024Q2 | R06 | R06 | R06+R07 |

## 11. Changes to earlier outputs

The rice panel (`rice_region_quarter.csv`), the typhoon and flood controls and `province_region_map.csv` were rebuilt on the same 16 regions (codes as in Van's boundary file: R01–R13, R04A, CAR, MIMAROPA, BARMM). `rice_barmm_unallocated.csv` is replaced by `barmm_cluster_residual.csv` (all crops). The first rice estimation (`outputs/tables/rice_direct_*`) still uses the old 17 regions and has to be re-run.
