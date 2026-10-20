# en_shock — El Niño shock framework, Philippines (UNDRR)

Produces quarterly El Niño shocks for the DEFINE-PH macro model through three channels:
agriculture (food production), labour productivity (heat) and electricity (demand and
price). Driver for all channels: RONI + DMI (NOAA). Deadline for results: 30 Jan 2027.

## Reference documents (local only, in docs/ — gitignored, never commit)
- docs/Reply_to_Van_Ge.docx — Alper's reply (Oct 2026) defining the AGREED SCOPE and
  methods for all three channels. This is the most recent and authoritative reference.
- docs/UNDRR_comments_DEFINE-PH_manual_VT.docx — UNDRR comments on the DEFINE-PH manual:
  how the El Niño shocks plug into the model (comment numbers referenced below).
- El Niño paper (Bringing El Niño into the Central Bank's Macro-Financial Framework) —
  methodological background; "paper eq. X" refers to it.
- The DEFINE-PH manual is confidential and NOT in this repo; refer to model equations by
  number only.
- Order of precedence: Alper's reply > UNDRR comments > paper.

## Team split
- Agriculture: Van = stage 1 of the two-stage approach (RONI + DMI -> regional weather);
  Ginevra = direct model and stage 2 (weather -> production).
- Labour and electricity: to be confirmed.
- Shared: climate-index loader, ERA5-Land processing, uncertainty method, output format.

## Channel 1 — Agriculture
Output: quarterly share of planned production lost, for DEFINE-PH's two food types:
- rice = irrigated + rainfed palay (estimated separately, combined with production shares);
- other food = corn (white + yellow) and a vegetable-and-fruit index (13 PSA crops:
  banana, pineapple, mango, calamansi, mung bean, potato, cabbage, eggplant, tomato,
  bitter gourd, onion, sweet potato, cassava), combined by their shares; the resulting
  shock is applied to all of other food (assumption, report a lower bound).
Method:
- Outcome is PRODUCTION, not yield. Regions rebuilt from provinces with fixed boundaries.
- Direct model (main): log production on region effects, region-specific seasonals and
  trends, lagged RONI (El Niño and La Niña separately) and DMI, constrained lag profile,
  typhoon/flood controls (needed to avoid double counting with CAT, comment 4).
  Lags ~4 quarters for rice/corn, longer for the vegetable-and-fruit index.
- Two-stage (check): stage 1 RONI + DMI -> regional weather (ERA5-Land, from 1950);
  stage 2 weather -> production (regression vs gradient boosting / GP, compared out of
  sample on held-out years). Combine by SIMULATION (draw weather outcomes, average losses).
- Reliability flag: mark scenario results where simulated weather goes beyond the
  extremes observed in the production period (by region and quarter).
Data: PSA OpenSTAT 2E4EVCP0 / 2E4EAHC0 (palay and corn by ecosystem/croptype, province,
quarterly, 1987–); vegetable/fruit crops quarterly from 2010; PSA annual 1990–2009 and
DA damage records for validation only.

## Channel 2 — Labour productivity
Output: quarterly productivity loss for agriculture, electricity and other sectors.
Method: ERA5-Land hourly -> WBGT (Liljegren outdoor, Bernard indoor; cross-check pywbgt
vs PyWBGT) -> El Niño effect on WBGT -> Hothaps loss functions (Kjellstrom 2018 /
Bröde 2018; heavy/moderate/light) hourly -> daily loss -> quarterly average.
Sectors: agriculture outdoor heavy; electricity indoor moderate; other = construction
(outdoor heavy) + industry (indoor moderate) + services (indoor light), weighted by LFS
employment. Dasgupta et al. (2021) as sensitivity. Deliver per quarter (comment 3.5.2).

## Channel 3 — Electricity
Outputs: (1) rise in electricity demand (household electricity share); (2) rise in the
marginal generation price (DEFINE-PH Eq. 168), by grid, as a range; (3) theta = spot
market share. Hydropower dropped.
Method: RONI + DMI -> CDD (ERA5-Land, population-weighted, threshold chosen by fit per
grid) -> monthly consumption and peak demand (paper eq. 5) -> price on reserve margin
(available capacity), oil as control -> quarterly values.
Fallback if El Niño -> CDD is too weak: scenario assumptions based on 2024.

## Not in current scope (to be confirmed with Alper)
World rice price response, food price pass-through and timing, residual food price shock,
El Niño public spending.

## Data
- data/ holds raw inputs: read-only, never modify. Write derived data to data/processed/.
- Climate indices: RONI from ERSST (main; from 1950); OISST and legacy ONI for robustness
  only. DMI: dmi_had. Treat -9999 as missing. Check whether a file is monthly relative
  Niño-3.4 or the 3-month RONI before use.
- ERA5-Land (Copernicus CDS) for all weather variables; no PAGASA station requests.
- One shared loader for climate indices and ERA5-Land (src/climate/), used by every module.

## Conventions
- Python; reusable code in src/, exploration in notebooks/, figures and tables in outputs/.
- Every result must be reproducible from data/ by re-running scripts or notebooks.
- Climate indices are common to all regions and autocorrelated: use Driscoll–Kraay or
  quarter-clustered SEs, never naive p-values.
- Nonlinear steps (two-stage, WBGT loss, price curve): simulate and average outcomes,
  never plug in average conditions.
- Uncertainty: one shared method (block bootstrap by year, or Bayesian draws).
- Output format for DEFINE-PH: quarterly shocks, central value plus range.
- Never add the DEFINE-PH manual, the UNDRR comments, Alper's reply or any BSP material
  to the repo (confidential).