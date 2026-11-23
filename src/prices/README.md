# World rice price shock (price note, Section 2)

The world rice price shock of the DEFINE-PH methodology (v5, price note "El Niño and food prices", Section 2, Eqs. 1–2a): how much an El Niño raises the real world rice price, quarter by quarter, for a RONI path. It uses the same direct approach as the crop models on `ginevra-agriculture`: lagged RONI with a binomial lag profile (K = 6 quarters, timing chosen by profile estimation), Newey–West errors and a block bootstrap for the range. RONI only, as agreed for all channels.

## Run

Step 08 of the main run (needs numpy, pandas, openpyxl; matplotlib for the figures):

```bash
python scripts/08_prices.py               # Eq. 1 with its checks and validation, then Eq. 2 with its range (about a minute)
python scripts/08_prices.py --reps 200    # a quicker bootstrap; --block-years sets the block length (default 5)
```

The two parts are `scripts/helpers/prices_estimate_rice.py` and `scripts/helpers/prices_shocks_rice.py`; each also runs alone.

## Inputs

| File | What | Source |
|---|---|---|
| `data/prices/CMO-Historical-Data-Monthly.xlsx` | Thai 5% (main price, from 1960), Viet Nam 5% (check, from Dec 2003), urea (from 1960), DAP (from Jan 1967), crude oil average | World Bank Pink Sheet, sheet "Monthly Prices" |
| `data/prices/CMO-Historical-Data-Annual.xlsx` | MUV index, the deflator (annual, 1960–2025) | World Bank Pink Sheet, sheet "Annual Prices (Real)" |
| `data/prices/fred_CPIAUCNS.csv` | US CPI, the alternative deflator of one check | FRED, series CPIAUCNS |
| `data/prices/rice_export_restrictions.csv` | Rice export restrictions, one row per episode, with sources | Compiled (Slayton 2009, DGFT, Global Trade Alert, IFPRI and others) |
| `data/indices/roni/ersst/roni_nino34_monthly_ersst.csv` | RONI (monthly relative Niño-3.4), averaged to quarters | NOAA CPC; same file as the crop models |
| `data/indices/dmi/dmi_had.csv` | DMI, only for the DMI variant check | NOAA PSL |

## Outputs (`outputs/prices/world_rice/`)

| File | Content |
|---|---|
| `shocks.csv` | **The deliverable.** Shock `S` by path and quarter (path quarters and the 6 after), its 90% range (`S_p05`, `S_p95`), and the upper estimate with an export ban (`S_upper_ban`) |
| `summary_estimation.txt`, `summary_shocks.txt` | Readable summaries of both runs |
| `coefficients.csv`, `lag_profile.csv`, `profile.csv` | Eq. 1 coefficients, the lag weights, and the fit for each timing parameter |
| `checks.csv` | The note's checks (year-on-year changes, lagged price, Viet Nam 5%, from 1990, test after 1990) and further ones |
| `validation.csv`, `validation_2026.csv` | Each episode left out and predicted (note Section 4); real-time check for 2026 |
| `shocks_bootstrap.csv`, `shocks_block1_check.csv` | Every bootstrap draw; the range with 1-year blocks as a check |
| `figure_price.png`, `figure_shocks.png`, `estimation_data.csv` | Figures and the quarterly estimation data |

## Choices to confirm

- **Fertiliser control: urea alone from 1960.** The note names fertiliser prices; DAP starts only in January 1967, and requiring it would start the sample in 1967 and drop the 1963 and 1965–66 El Niños. DAP is added as a check from 1967 (`CONTROLS_WITH_DAP` in `world_rice.py`), next to the main model on the same years.
- **Export restrictions: major exporters only (India, Thailand, Viet Nam).** Bans, suspensions of new sales and prohibitive minimum export prices count, as the share of each quarter in force; export taxes, routine quotas and minor exporters (Egypt and Cambodia in 2008, kept in the file with `in_main_indicator = 0`) do not. Waiting on Alper's confirmation; edit the CSV to change it.
- **Deflator: MUV** (the note says "a world price index"); annual, interpolated to quarters and extended through 2026 at its 2025 growth. US CPI is an added check.
- **Bootstrap: moving blocks of 5 years**, not single years as for the crops, because the price moves in long swings (residual autocorrelation 0.84); 1-year blocks are reported as a check.
- **Upper estimate: the ban lasts for the quarters of the path.** The note does not say how long.
- **FAO All Rice Price Index: not used.** FAO only publishes 2022–2026 in its dashboard, which holds one El Niño.
- **Eq. 2a** needs rice's share of real agricultural imports in DEFINE-PH (SOAS); the shock here is S, to be multiplied by that share.
