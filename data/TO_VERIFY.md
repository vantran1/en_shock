# Data values to double-check

Values used in the results that come from a stand-in, an assumption or a secondary source. Each needs
someone with access to the original source to confirm it or give the right value. The FNRI PhilFCT site
(https://i.fnri.dost.gov.ph/fct/library) cannot be opened from Bangkok.

When a value is confirmed or corrected, update it where it is set (column "Set in") and re-run the outputs
listed under "Affects".

Last updated: 24 Nov 2026 (after Alper's notes on the workbook).

## FNRI calorie factors (kcal per 100 g edible portion, and edible portion)

The VR and PF factors come from Alper Aras's workbook `data/agriculture/FNRI_calorie_factors_VR_PF_v35.xlsx`
(9 Nov 2026; gitignored working file, extract in `data/agriculture/fnri_calorie_factors.csv`). Its notes
document the sources and choices: FNRI PhilFCT Release 1 December 2019, accessed 9 Nov 2026 (note 1); edible
portion and energy per kg as produced (note 2); mungbean, onion, sweet potato, cassava and mango records
(notes 3-6, 8); bananas (note 7); calamansi (note 9); base period 2021-2023 (note 10). Only what is still
open is listed here.

1. **Rice, well-milled (FNRI A019).** Not in Alper's workbook (it covers VR and PF only). Current value:
   3,600 kcal/kg of milled rice, NOT the FNRI figure (the record would not load).
   Source of the current value: none. It is a placeholder chosen on 24 Nov 2026 (Claude, while building the
   series) from general knowledge of raw milled rice (about 360 kcal/100 g), not taken from a document.
   FNRI record to use instead: https://i.fnri.dost.gov.ph/fct/library/report/2981 (A019; returned a server
   error on 24 Nov 2026).
   Set in: `scripts/build_national_hazard_controls.py` (`RICE_KCAL_PER_KG`).
   Affects: the food weights of the national typhoon and flood series for the food price equation (Eq. 3).
   The effect is very small: changing the palay factor by ±20% leaves the series correlated at 0.9995 or more.

2. **Corn, dried shelled.** Not in Alper's workbook. Current value: 357 kcal/100 g, edible portion 1.0, from
   FNRI A001 "Corn grits, white", the closest record found. Is there a record for dried shelled corn?
   Source of the current value: FNRI PhilFCT A001, looked up on 19 Nov 2026 while the FNRI site was not
   working properly; the page URL was not recorded.
   Set in: `scripts/deliver_food_shocks.py` and `scripts/build_national_hazard_controls.py`
   (`CORN_KCAL_PER_KG`).
   Affects: the two-food-type fallback of the delivery (`nonrice_fallback`), and the food weights of the
   national typhoon and flood series.

3. **Bananas Lakatan (E011), Latundan (E012) and Bungulan (E006): edible portion.** The workbook (note 7)
   assumed the Cavendish values for these varieties because PhilFCT had no raw records for them; on 11 Nov
   2026 Alper sent their FNRI energy values (E011 126, E012 105, E006 106 kcal/100 g), which replace the
   Cavendish energy. Their edible portion is still the Cavendish value (0.64, E008,
   https://i.fnri.dost.gov.ph/fct/library/report/3590).
   Set in: `data/agriculture/fnri_calorie_factors.csv`.
   Affects: the PF index (bananas are about 82% of its calories), and so the PF shocks.

4. **Banana, others.** No PhilFCT record; the Cavendish values (E008) are used, as in the workbook (note 7).
   Open only if a better record exists.
   Set in: `data/agriculture/fnri_calorie_factors.csv`.

5. **Calamansi.** 44 kcal/100 g, edible portion 0.38, from Juan Nutrisyon citing PhilFCT
   (https://nuxt-ssr-juanutrisyon.pages.dev/food/calamansiphilippine-lemon), workbook note 9. Alper (24 Nov
   2026): its share is very small (about 0.2% of PF calories), so it does not affect the results. Kept as is;
   verify only if the FNRI record becomes available.

## Other

6. **Palay milling recovery rate.** Current value: 0.63 kg of milled rice per kg of palay. Source: a USDA FAS
   report that PSA lowered the rate from 0.654 to 0.63 from January 2025 (found on 24 Nov 2026)
   (https://www.fas.usda.gov/data/philippines-philippine-statistics-authority-lowers-milling-recovery-rate-palay-rice-63-percent).
   A PSA release would be the better source to cite.
   Set in: `scripts/build_national_hazard_controls.py` (`MILLING_RECOVERY`).
   Affects: as item 1.

## Re-running after a change

- FNRI file (items 3-4): `python scripts/build_crop_panel.py`, then the VR/PF estimation, shocks and delivery
  (`scripts/estimate_direct.py --crop pf|vr`, `scripts/shocks_direct.py --crop pf|vr`,
  `scripts/deliver_food_shocks.py`), the FAOSTAT check (`scripts/check_faostat_vrpf.py`), the hazard controls (`scripts/build_typhoon_exposure.py`,
  `scripts/build_flood_exposure.py`, whose VR/PF weights are in kcal) and `scripts/build_writeup.py`.
- Items 1, 2 and 6: `python scripts/build_national_hazard_controls.py`; item 2 also
  `scripts/deliver_food_shocks.py`.
