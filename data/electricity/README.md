# Electricity inputs

The electricity section's own inputs (demand, generation and grid data) go here when its code joins this repository.

Stage 1 already writes what the section needs from the weather side, with population weights (Eq. 2 of the
electricity note): `outputs/electricity/` (historical fitted temperature, path response, shift by block, cell-level
versions, cell weights and the region-to-grid map) and `outputs/shared/observed_monthly_17regions_population.csv`.
`python scripts/07_electricity.py` checks that these files are complete and up to date.
