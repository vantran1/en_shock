# PSA consumer price index (2018 = 100)

Inputs of the residual food price shock (price note, Section 3.1, Eq. 3): food CPI and rice CPI relative to the
all-items CPI, Philippines. Downloaded by hand from PSA OpenSTAT, database "CPI 2018-based (New Geographic Code)"
(https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/DB__2M__PI__CPI__2018NEW/), on 24 November 2026, as the full
tables (all geolocations and 354 commodity items, monthly and annual averages; CSV export).

| File | OpenSTAT table | Period |
|---|---|---|
| `psa_cpi_2018base_2018-01_2026-10.csv` | 0012M4ACP22: Consumer Price Index for All Income Households by Commodity Group (2018=100): January 2018 - October 2026 | Jan 2018 - Oct 2026 |
| `psa_cpi_2018base_1994-01_2017-12_backcast.csv` | 0012M4ACP28: Consumer Price Index for All Income Households by Commodity Group (2018=100): January 1994 - December 2017 (Backcasted Values) | Jan 1994 - Dec 2017 |

Both are on the 2018 base with the same commodity list, so they join end to end into one series from January 1994;
the values before 2018 are PSA's backcast. Rows used: geolocation `PHILIPPINES`, commodities `0 - ALL ITEMS`,
`01.1 - FOOD` and `01.1.1.12 - Rice` (`01 - FOOD AND NON-ALCOHOLIC BEVERAGES` as a check). `..` = not available.
The national series is the same under the old and the new geographic codes, which differ only in how provinces are
grouped into regions.

Not tracked by git: the backcast file is larger than GitHub's 100 MB limit. The code will extract the national rows
into a small tracked file.
