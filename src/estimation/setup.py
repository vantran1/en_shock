"""Estimation set-up shared by the direct models: PSA measurement breaks and the sample
variants that check them. Breaks are handled here, in the estimation, never in the data
(data/processed keeps the series as PSA publishes them; the issue is noted in the paper).

Known breaks
- Corn, Region VI (R06): Negros Occidental corn area harvested falls from 2023Q3
  (-24% on a year earlier while the rest of VI and the country do not fall) and keeps
  falling to about 27,000 ha in 2025 (68,000-70,000 ha in 2018-2022); yellow corn yield
  falls too, white corn yield does not. It does not reappear in any other row
  (outputs/panel_validation.md, section 5). Treated as a PSA measurement break.
  Main: a level dummy for R06 corn (all corn series: total, white, yellow) from 2023Q3,
  where the quarterly data show the Negros-specific fall beginning (proposed 12 Nov 2026;
  to be confirmed). Test of the start (scripts/test_break_start_corn.py): with the spline
  trends of the recommended specification the R06 trend absorbs the fall, the dummy is
  small and its start not identified; with v5's linear trends the dummy is large (-0.55 to
  -0.73). In both, the national El Nino effect does not depend on the start.
  Check: R06 corn quarters from 2023Q3 on are dropped.
"""
import pandas as pd

# crop group -> list of (region_code, first quarter of the dummy, first quarter dropped in
# the check sample, name of the dummy)
BREAKS = {
    "corn": [("R06", "2023Q3", "2023Q3", "break_r06_corn")],
}


def break_dummies(p: pd.DataFrame, group: str, start: str | None = None) -> pd.DataFrame:
    """Level-shift dummies for the breaks of a crop group: 1 for the region from the dummy
    start on (start overrides it, for the test of the start date; 'none' = no dummy).
    p needs region_code and period (pd.Period or 'YYYYQn' strings)."""
    per = pd.PeriodIndex(p["period"].astype(str), freq="Q")
    out = pd.DataFrame(index=p.index)
    if start == "none":
        return out
    for region, default_start, _, name in BREAKS.get(group, []):
        start = start or default_start
        out[name] = ((p["region_code"].values == region)
                     & (per >= pd.Period(start, "Q"))).astype(float)
    return out


def sample(p: pd.DataFrame, group: str, variant: str = "main") -> pd.DataFrame:
    """'main': full sample (the breaks enter as dummies);
    'end_before_break': for each break, the region's quarters from the check start on are
    dropped (R06 corn ends in 2023Q2)."""
    if variant == "main":
        return p
    if variant != "end_before_break":
        raise ValueError(variant)
    per = pd.PeriodIndex(p["period"].astype(str), freq="Q")
    keep = pd.Series(True, index=p.index)
    for region, _, check_start, _ in BREAKS.get(group, []):
        keep &= ~((p["region_code"].values == region) & (per >= pd.Period(check_start, "Q")))
    return p[keep.values]
