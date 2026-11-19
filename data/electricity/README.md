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
