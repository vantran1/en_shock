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
