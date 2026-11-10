"""Estimation set-up shared by the direct models: PSA measurement breaks and the sample
variants that check them. Breaks are handled here, in the estimation, never in the data
(data/processed keeps the series as PSA publishes them).

Known breaks
- Corn, Region VI (R06), from 2024Q1: Negros Occidental corn (about 40% of VI corn in
  2019-2022) halves in 2024 and falls again in 2025, from the year PSA reports it under
  NIR. The fall is mostly area harvested, is not concentrated in the El Nino months and
  does not reappear in any other row (outputs/panel_validation.md, section 5; question
  sent to PSA). Treated as a PSA measurement break.
  Main: a level dummy for R06 corn from 2024Q1 (all corn series: total, white, yellow).
  Check: R06 corn ends in 2023Q4 (later quarters dropped).
"""
import pandas as pd

# crop group -> list of (region_code, first quarter of the new level, name of the dummy)
BREAKS = {
    "corn": [("R06", "2024Q1", "break_r06_corn_2024q1")],
}


def break_dummies(p: pd.DataFrame, group: str) -> pd.DataFrame:
    """Level-shift dummies for the breaks of a crop group: 1 for the region from the break
    quarter on. p needs region_code and period (pd.Period or 'YYYYQn' strings)."""
    per = pd.PeriodIndex(p["period"].astype(str), freq="Q")
    out = pd.DataFrame(index=p.index)
    for region, start, name in BREAKS.get(group, []):
        out[name] = ((p["region_code"].values == region)
                     & (per >= pd.Period(start, "Q"))).astype(float)
    return out


def sample(p: pd.DataFrame, group: str, variant: str = "main") -> pd.DataFrame:
    """'main': full sample (the breaks enter as dummies);
    'end_before_break': for each break, the region's quarters from the break on are dropped
    (e.g. R06 corn ends in 2023Q4)."""
    if variant == "main":
        return p
    if variant != "end_before_break":
        raise ValueError(variant)
    per = pd.PeriodIndex(p["period"].astype(str), freq="Q")
    keep = pd.Series(True, index=p.index)
    for region, start, _ in BREAKS.get(group, []):
        keep &= ~((p["region_code"].values == region) & (per >= pd.Period(start, "Q")))
    return p[keep.values]
