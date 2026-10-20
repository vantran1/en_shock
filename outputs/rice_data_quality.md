# Rice data preparation: data-quality report

Built by `scripts/build_rice_panel.py` from the raw PSA files in `data/agriculture/`.
Tables referred to are in `outputs/tables/`. No estimation.

## 1. What the files contain

| File | Content | Geography | Breakdown | Frequency, period |
|---|---|---|---|---|
| `palay_and_corn_volume.csv` | PSA OpenSTAT **2E4EVCP0**, production in metric tons | national, 17 regions, 91 province rows | Irrigated / Rainfed / total Palay; White / Yellow / total Corn | Q1–Q4 + semesters + annual, 1987Q1–2026Q2 (2026Q3–Q4 empty) |
| `palay_and_corn_area.csv` | PSA OpenSTAT **2E4EAHC0**, area harvested in hectares | same | same | same |
| `palay_yield.csv` | derived file, unknown origin: region, period, area, production, yield, ln yield, Δln yield | 17 published regions (NIR only 2024+) | total palay only | quarterly, 1987Q1–2025Q4 |
| `corn_yield.csv` | same as above for total corn | same | total corn only | same |

- The two PSA files are exactly the required tables, with province and ecosystem detail, so **no download is needed**.
- The two `*_yield.csv` files use the published regional boundaries, which break in 2024, and have no ecosystem split. They are not used.
- `..` = not available. The footnote text is not in the CSV export; it was retrieved from the OpenSTAT API (release of 29 Jul 2026): a/ Negros Occidental "still part of Western Visayas prior to 2024"; b/ Negros Oriental, Siquijor "still part of Central Visayas prior to 2024"; c/ Sulu "still part of BARMM prior to 2026", realigned to Region IX by Executive Order No. 91; d/ BARMM 2026 data exclude Sulu.

## 2. Fixed regional boundaries

Alper's reply: "The regional series should therefore be rebuilt from provincial data,
using the same boundaries throughout". Every province is assigned to its **current**
region (`src/agriculture/regions.py`, saved as `data/processed/province_region_map.csv`).
That gives 17 regions (NCR has no rice). Full list in `rice_boundary_changes.csv`.

**Changes that move output between regions**
- **Negros Island Region (2024, RA 12000).**
  - Negros Occidental (from VI), Negros Oriental and Siquijor (from VII): PSA lists them under VI/VII until 2023Q4 and under NIR from 2024Q1.
  - Put in NIR for all years.
- **Sulu (BARMM → IX).** Realigned to Region IX by Executive Order No. 91; PSA lists it under IX from 2026Q1. Put in IX for all years; its rice output is 0–550 t per quarter.
- **ARMM → BARMM (2019).** PSA has a single BARMM row from 1987. Cotabato City and the Eight Cluster Areas (63 barangays previously in the Province of Cotabato) have no province row (see section 5).

**Changes with no regional effect** (PSA already lists every province under its current region from 1987)

| Province or region | Change | In the PSA data |
|---|---|---|
| Maguindanao | split into del Norte and del Sur (2022) | del Norte from 2024; before that, all of Maguindanao is in the "del Sur" row |
| Compostela Valley | renamed Davao de Oro (2019) | one row |
| Davao Occidental | created 2013 | back-cast to 1987 |
| Dinagat Islands | created 2006 | back-cast to 1987 |
| Zamboanga Sibugay | created 2001 | back-cast to 1987 |
| Apayao | created 1995 | back-cast to 1987 |
| Biliran, Guimaras, Sarangani | created 1992 | back-cast to 1987 |
| Caraga (1995), the 2001 Mindanao regrouping, the IV-A/MIMAROPA split, Aurora's move to III (2002) | regional reorganisations | already back-cast |
| Puerto Princesa, Bacolod, Butuan | separate city rows | only from 2026Q1, outside the sample |

## 3. Output

- `data/processed/rice_region_quarter.csv` has one row per ecosystem (irrigated, rainfed, total) × 17 regions × 156 quarters, 1987Q1–2025Q4, giving 7,956 rows. Columns: `production_t`, `area_ha`, `n_prov_reporting`.
- `data/processed/rice_barmm_unallocated.csv` holds the Eight Cluster Areas' output, which is in BARMM's total but in no province row (section 5).

## 4. Checks

| Check | Result |
|---|---|
| Missing region-quarters / province-quarters | **none** |
| Duplicates | only in 2025Q1: Negros Occidental, Negros Oriental and Siquijor still appear under VI/VII with value **0** as well as under NIR. The sums are correct; no double counting |
| Irrigated + rainfed = total | exact in every region-quarter |
| Rebuilt vs published regions | **identical** for the 12 regions untouched by boundary changes. For VI/VII/NIR and IX/BARMM the differences cancel exactly within each group once BARMM's unallocated output is accounted for (residual ≤ 0.01 t) |
| Rebuilt vs national | gap of up to 0.7% from 2023; zero (< 1e-7) once BARMM's unallocated output is added |
| Zeros (region level) | 51 rainfed region-quarters: Region I mostly Q2 (36), CAR (8), NIR/VI/II (6), all with zero production and zero area, i.e. no rainfed harvest that quarter. One NIR quarter has production > 0 with zero area |
| Implausible yields (< 1 or > 7 t/ha, area > 500 ha) | 21 cases, almost all rainfed VII in 1987–92 (0.4–1.0 t/ha) |
| Annual level breaks (\|Δ ln\| > 0.4) | 65 cases, almost all rainfed and mostly 1990–94 and 1998–99 (El Niño years and recovery). In 26 of them the total palay series barely moves: small rainfed series in mostly irrigated regions (CAR, II, IV-A, X, XI) |

## 5. Problems

1. **BARMM Eight Cluster Areas, from 2023Q1.**
   - PSA's note: "TOTAL of BARMM starting Q1 2023 is not equal to the sum of provinces as the estimates of the Eight Cluster Areas is already included in the total estimate of BARMM."
   - The cluster areas add 45,000–63,000 t of palay per year (about 5–7% of BARMM), 79% irrigated, and a similar amount of corn.
   - **Treatment:** kept out of BARMM's series, because adding them from 2023 would create a step at the start of the 2023–24 El Niño. Saved separately for national weights.
   - **Open question:** before 2023, these villages belonged to the Province of Cotabato (Region XII). Were their harvests counted in Cotabato's figures then? Cotabato falls only 12,000 t (rice) in 2023, much less than the cluster areas' output. This is a question for PSA.
2. **Rainfed zero and near-zero quarters.**
   - Some regions have no rainfed harvest in some quarters (Region I Q2), and a few quarters have only a few tonnes (NIR 1990, X 1998, BARMM 1992).
   - CLAUDE.md specifies log production, so these quarters will have to be left out of the rainfed regression. They carry no information on El Niño losses anyway.
3. **Possible statistical breaks in rainfed series.**
   - CAR rainfed: level shift around 1999–2000 and gaps in 1991–93.
   - XI rainfed: falls a level around 1990–93.
   - Several rainfed series jump while the total stays stable, which may mean irrigated/rainfed reclassification.
   - To be checked before estimation.
4. **Crop-calendar drift.** Between 1987–96 and 2016–25, quarterly shares moved by up to 15–19 points in some regions (rainfed XI and IV-A, irrigated NIR and X; `rice_qc_calendar_drift.csv`). This supports region × quarter trends, as agreed.
5. **PSA revision notes.** The table notes list revised quarters (e.g. Q3 2022 rainfed palay in Occidental Mindoro, Q1 2025 rainfed palay in Negros Occidental and Oriental, Q2 2025 irrigated palay in BARMM). The data used already include these revisions.
