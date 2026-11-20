# Electricity inputs

## `doe_capacity_peak_by_grid.csv`

**Content:** annual dependable capacity and system peak demand for the three grids (Luzon, Visayas,
Mindanao), 2003–2025. One row per year.

**Columns:** `year`, `cap_luzon_mw`, `cap_visayas_mw`, `cap_mindanao_mw` (dependable capacity, MW),
`peak_luzon_mw`, `peak_visayas_mw`, `peak_mindanao_mw` (system peak demand, MW).

**Sources:**
- Capacity: DOE 2025 Power Statistics, “Installed and Dependable Capacity per Grid and per
  Technology, 2003–2025” (updated 10 June 2026), first “Dependable Capacity per Grid” table, Total
  row per grid. This is grid-connected plus embedded, not the “On Grid + Off Grid” table.
- Peak demand: DOE 2025 Power Statistics, “System Peak Demand per Grid, 2001–2025”. Original source
  NGCP; grid only, includes PECO.

Both PDFs are stored on the team drive with the raw electricity data.

**Use:** reserve margin in the electricity price equation (methodology v5, Eq. 6):
RM(g,y) = (dependable capacity(g,y) − Ē(g,y)) / Ē(g,y), where Ē is the mean peak demand of years
y−1, y−2 and y−3.

**Caveats:**
- Off-grid capacity is reported separately only from 2021, so grid totals before 2021 may include a
  few hundred MW of off-grid capacity (about 2–3%).
- Dependable capacity counts solar at its AC rating, so the margin at the evening peak is smaller
  than RM suggests.

**Check done:** all values verified against both PDFs (19 Nov 2026).

## `pinksheet_crude_coal_monthly.csv`

**Content:** monthly world fuel prices, January 2013 – October 2026. One row per month.

**Columns:** `month` (YYYY-MM), `crude_avg_usd_bbl` (crude oil, average of Brent, Dubai and WTI,
US$/bbl), `coal_aus_usd_mt` (coal, Australian, US$/metric ton). Nominal US dollars.

**Source:** World Bank Commodity Price Data (Pink Sheet), “CMO-Historical-Data-Monthly.xlsx”, sheet
“Monthly Prices”, updated 3 November 2026; columns “Crude oil, average” and “Coal, Australian”. The
original Excel is on the team drive as CMO-Historical-Data-Monthly_2026-11.xlsx.

**Use:** fuel price controls F_m in the electricity price equation (methodology v5, Eq. 5), converted
to pesos with the monthly PHP/USD rate (to be added). The same crude oil series is also used in the
food price equation (price note, Eq. 3).

**Caveat:** the World Bank revises recent months, so if the file is updated later, the last few values
may change slightly.

## `php_per_usd_monthly.csv`

**Content:** monthly average exchange rate, pesos per US dollar, January 2013 – October 2026.

**Columns:** `month` (YYYY-MM), `php_per_usd_avg` (monthly average, PHP per USD).

**Source:** Bangko Sentral ng Pilipinas, “Daily, Monthly (Average and End-of-Period) and Annual Peso
per US Dollar” (pesodollar.xlsx), sheet “monthly”, column “Average”, downloaded 19 Nov 2026. The
original Excel is on the team drive as pesodollar_2026-11.xlsx.

**Use:** converts the Pink Sheet fuel prices (pinksheet_crude_coal_monthly.csv, same months) to pesos
for the fuel controls in the electricity price equation (methodology v5, Eq. 5). Also used in the food
price equation (price note, Eqs. 1–3).

## `ph_holidays_2013_2026.csv`

**Content:** Philippine public holidays, 1 January 2013 – 31 December 2026: regular holidays and
special (non-working) days declared throughout the country, plus the special (non-working) days declared
for Metro Manila (NCR) as a whole. Special working days and other local days (single cities or provinces)
are excluded. One row per date, sorted, no duplicates.

**Columns:** `date` (YYYY-MM-DD), `name`, `type` (`regular` or `special_non_working`), `scope` (`national`
or `ncr`).

**Source:** Python `holidays` package, version 0.109, country "PH", category "public" (the package
has no separate category for special non-working days; `type` is set from the holiday names, with
the regular holidays fixed by law). Built by `scripts/build_ph_holidays.py`.
- **Checked against the Official Gazette proclamations** (base proclamation for each year plus the
  later ones: election days, Eid'l Fitr, Eid'l Adha, added special days) for **2013–2020 and 2024**.
  9 corrections (2013, 2016, 2017), listed with their proclamation numbers as `OVERRIDES` in the
  script; 0 unverified dates.
- **Not checked:** 2021–2023 and 2025–2026 (package as is).
- **NCR days (`scope = ncr`), 12 dates,** from the LawPhil yearly indexes of proclamations 2013–2026 (the
  2026 index runs to 24 September 2026), listed as `NCR_DAYS` in the script: papal visit 15, 16 and 19 Jan
  2015 (Proc. 936 s.2014); APEC 18–19 Nov 2015 (Proc. 1072 s.2015); ASEAN Summit 28 Apr 2017 (Proc. 197
  s.2017) and 13–15 Nov 2017 (Proc. 332 s.2017, which also covered Bulacan and Pampanga, both on the Luzon
  grid); 16–18 Nov 2026 (Proc. 1447 s.2026).

**Use:** public-holiday indicator in the day-of-week effect o(g, dow) of the electricity price and
demand equations (methodology v5, Eqs. 5 and 7). `national` days are holidays for all three grids; `ncr`
days are used as holidays for the Luzon grid only.

## `wesm_price_caps.csv`

**Content:** WESM price mitigation measures, 2006–2026: the offer price cap and floor on generator offers,
and the secondary price cap (SPC), which pegs the market price at the cap once the rolling average of
the generator weighted average price (GWAP) breaches the cumulative price threshold (CPT). One row per
regime.

**Columns:** `measure` (`offer_cap`, `offer_floor`, `secondary_price_cap`), `start_date`, `end_date`
(empty = still in force), `cap_php_mwh` (cap or floor, PHP/MWh), `cpt_php_mwh` (SPC trigger: average GWAP
over the window, PHP/MWh), `window_hours` (rolling window of the trigger), `scope`, `instrument`,
`signed_date`, `effectivity_clause` (as written in the resolution), `start_basis`, `source`, `note`.

**Dates:** each resolution takes effect relative to its publication in a newspaper, which it does not
date. `start_date` is therefore the signed (or approved) date plus the stated lag, i.e. the **earliest
possible** effective date; the true date is a few days to weeks later. Res. No. 8 s.2014 was in force by
15 May 2014 (first breach). Between the end of the interim SPC (~7 Dec 2014) and the permanent one (Res.
No. 20 s.2014, from ~30 Dec 2014 at the earliest) there may have been a few weeks without an SPC.

**Sources:** ERC Resolutions No. 8, 14 and 20 s.2014, No. 4 s.2017, No. 7 s.2021 and No. 26 s.2025 (PDFs
from erc.gov.ph, downloaded 20 Nov 2026; to be filed on the team drive with the raw electricity data:
`ResolutionNo8seriesof2014.pdf`, `ResolutionNo.14Seriesof20140001.pdf`, `ERCResolutionNo.20,Seriesof2014.pdf`,
`ResolutionNo04Seriesof2017.pdf`, `For Posting 746 -Resolution No. 07, Series of 2021 (HVB sgd).pdf`,
`For Posting 2440-2025. Resolution No. 26, Series of 2025 with Annex A.pdf`). The offer cap and floor
(WESM Tripartite Committee Joint Resolutions No. 2 of 17 Dec 2013 and No. 3 of 17 Dec 2015) are from a
secondary source, IES (2024), *Assessment of WESM Price Analysis* (Energy Transition Partnership), pp.
18–20, as the joint resolutions could not be found. The IES report gives the first SPC as a 7-day window
with a 9,000 trigger; the resolutions show it was 72 hours and 8,186 (Res. No. 8 s.2014), and 7 days and
9,000 only from Res. No. 20 s.2014.

**Use:** censoring of the daily price in the electricity price equation (methodology v5, Eq. 5): prices at
the offer cap, and intervals under the SPC, are treated as censored. For the 2026 public IEMOP months the
SPC is 7,423 PHP/MWh with a 12,413 trigger over 72 hours.
