# en_shock — El Niño shock framework, Philippines (UNDRR)

Produces quarterly El Niño shocks for the DEFINE-PH macro model: food production, heat/labour productivity and electricity.

## Reference documents (local only, in docs/ — gitignored, never commit)
- docs/UNDRR_comments_DEFINE-PH_manual_VT.docx — LATEST UNDRR comments on the DEFINE-PH
  manual. This is the authoritative statement of what the El Niño framework must deliver
  and how it plugs into the model. Where it differs from the original El Niño paper,
  the comments take precedence. Read it before designing any channel.
- Original El Niño paper (Bringing El Niño into the Central Bank's Macro-Financial
  Framework) — methodological background; equation numbers below refer to it as "paper".
- The DEFINE-PH manual itself is confidential and is NOT in this repo; refer to model
  equations by number only.

## Deliverables required by the latest comments (El Niño parts)
- Food production shock for rice and "other food" (comments 4, 4.1.1): share of planned
  production lost, from a regional panel that CONTROLS for typhoon and flood exposure
  (this is what rules out double counting with the CAT model). Other food = weighted
  average of crop-specific shocks (coconut, banana, sugarcane, fisheries).
- World rice price response to El Niño (4.2.1): estimated on world prices in USD, with
  controls for exporter restrictions and input costs; delivered as a range. Plus the
  world-to-domestic pass-through, before/after the 2019 Rice Tariffication Law.
- Quarterly profile of the food price response (4.2.2), from the food price equation
  (paper eq. 8), used to calibrate the timing of the model's price response.
- Residual food price shock (comment 1, 3.2.1, paper Box 7): computed jointly with SOAS,
  enters at the RETAIL food price.
- Heat productivity shock (3.4.1, 3.5.1, 3.5.2): by sector, delivered PER QUARTER (the
  loss depends only on that quarter's heat; not carried through lagged productivity).
- Electricity (5.1.1): El Niño -> peak demand -> rise in the marginal generation price
  in peak quarters, using spot prices vs AVAILABLE capacity; delivered as a range.
- Extra El Niño public spending (comment 2): calibrated, excluding regular programmes.

## Data
- data/ holds raw inputs: read-only, never modify. Write derived data to data/processed/.
- Climate indices: RONI from ERSST (main; official NOAA basis, from 1950); OISST and
  legacy ONI for robustness only. DMI: dmi_had (standard index). Treat -9999 as missing.
  Check whether a file is monthly relative Niño-3.4 or the 3-month RONI before use.
- One shared loader for all climate indices (src/climate/), used by every module.

## Conventions
- Python; reusable code in src/, exploration in notebooks/, figures and tables in outputs/.
- Every result must be reproducible from data/ by re-running scripts or notebooks.
- Climate indices are autocorrelated and common to all regions: use Driscoll–Kraay or
  quarter-clustered SEs, never naive p-values.
- Uncertainty: one shared method (block bootstrap by year, or Bayesian draws).
- Never add the DEFINE-PH manual, the UNDRR comments or any BSP material to the repo
  (confidential).