# Data values to double-check

Values used in the results that come from a stand-in, an assumption or a secondary source. Each needs
someone with access to the original source to confirm it or give the right value. The FNRI PhilFCT site
(https://i.fnri.dost.gov.ph/fct/library) cannot be opened from Bangkok.

When a value is confirmed or corrected, update it where it is set (column "Set in") and re-run the outputs
listed under "Affects".

Last updated: 24 Nov 2026.

## FNRI calorie factors (kcal per 100 g edible portion, and edible portion)

1. **Rice, well-milled (FNRI A019).** Current value: 3,600 kcal/kg of milled rice. This is a typical value
   for raw milled rice, NOT the FNRI figure (the record would not load).
   Set in: `scripts/build_national_hazard_controls.py` (`RICE_KCAL_PER_KG`).
   Affects: the food weights of the national typhoon and flood series for the food price equation (Eq. 3).
   The effect is very small: changing the palay factor by ±20% leaves the series correlated at 0.9995 or more.

2. **Corn, dried shelled.** Current value: 357 kcal/100 g, edible portion 1.0, from FNRI A001 "Corn grits,
   white", the closest record found. Is there a record for dried shelled corn?
   Set in: `scripts/deliver_food_shocks.py` and `scripts/build_national_hazard_controls.py`
   (`CORN_KCAL_PER_KG`).
   Affects: the two-food-type fallback of the delivery (`nonrice_fallback`), and the food weights of the
   national typhoon and flood series.

3. **Bananas Lakatan (E011), Latundan (E012) and Bungulan (E006): edible portion.** Current value: 0.64,
   assumed from Cavendish (E008). The kcal values are from FNRI.
   Set in: `data/agriculture/fnri_calorie_factors.csv`.
   Affects: the PF index (bananas are most of its calories), and so the PF shocks.

4. **Banana, others.** No FNRI record found; the Cavendish values (E008) are used. Is there a better record?
   Set in: `data/agriculture/fnri_calorie_factors.csv`.
   Affects: the PF index.

5. **Calamansi.** Current value: 44 kcal/100 g, edible portion 0.38, from a secondary website citing
   PhilFCT.
   Set in: `data/agriculture/fnri_calorie_factors.csv`.
   Affects: the PF index (very small weight).

## Other

6. **Palay milling recovery rate.** Current value: 0.63 kg of milled rice per kg of palay. Source: a USDA FAS
   report that PSA lowered the rate from 0.654 to 0.63 from January 2025
   (https://www.fas.usda.gov/data/philippines-philippine-statistics-authority-lowers-milling-recovery-rate-palay-rice-63-percent).
   A PSA release would be the better source to cite.
   Set in: `scripts/build_national_hazard_controls.py` (`MILLING_RECOVERY`).
   Affects: as item 1.

## Re-running after a change

- FNRI file (items 3-5): `python scripts/build_crop_panel.py`, then the VR/PF estimation, shocks and delivery
  (`scripts/estimate_direct.py --crop pf|vr`, `scripts/shocks_direct.py --crop pf|vr`,
  `scripts/deliver_food_shocks.py`), the FAOSTAT check (`scripts/check_faostat_vrpf.py`), the hazard controls (`scripts/build_typhoon_exposure.py`,
  `scripts/build_flood_exposure.py`, whose VR/PF weights are in kcal) and `scripts/build_writeup.py`.
- Items 1, 2 and 6: `python scripts/build_national_hazard_controls.py`; item 2 also
  `scripts/deliver_food_shocks.py`.
