"""Shared loader for climate indices (CLAUDE.md: one loader used by every module).

- RONI (main): data/roni/ersst/roni_nino34_monthly_ersst.csv = MONTHLY relative Nino-3.4
  anomaly (column rel_ssta). Its 3-month centred mean reproduces the official seasonal
  RONI (roni_nino34_seasonal_ersst.csv) to within 0.007 C, so a calendar-quarter mean
  of the monthly file = the official RONI for JFM, AMJ, JAS, OND.
- ONI (robustness): data/oni/ersst/oni_nino34_monthly_ersst.csv, column ssta.
- DMI: data/dmi/dmi_had.csv (HadISST Dipole Mode Index), -9999 = missing.
OISST versions exist in data/ for robustness only.
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"


def _clean(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    return s.mask(s <= -9998)


def monthly(index: str = "roni", source: str = "ersst") -> pd.Series:
    """Monthly series indexed by pd.Period('M'). index: 'roni' | 'oni' | 'dmi'."""
    if index == "roni":
        df = pd.read_csv(DATA / "roni" / source / f"roni_nino34_monthly_{source}.csv")
        s, idx = _clean(df["rel_ssta"]), pd.PeriodIndex(df["month"], freq="M")
    elif index == "oni":
        df = pd.read_csv(DATA / "oni" / source / f"oni_nino34_monthly_{source}.csv")
        s, idx = _clean(df["ssta"]), pd.PeriodIndex(df["month"], freq="M")
    elif index == "dmi":
        df = pd.read_csv(DATA / "dmi" / "dmi_had.csv", skipinitialspace=True)
        df.columns = df.columns.str.strip()
        s, idx = _clean(df["DMI"]), pd.PeriodIndex(pd.to_datetime(df["Date"]), freq="M")
    else:
        raise ValueError(index)
    s.index = idx
    return s.rename(index)


def quarterly(index: str = "roni", source: str = "ersst") -> pd.Series:
    """Calendar-quarter mean; a quarter with any missing month is missing."""
    m = monthly(index, source)
    g = m.groupby(m.index.asfreq("Q"))
    q = g.mean().where(g.count() == 3)
    q.index.name = "period"
    return q


def lags(q: pd.Series, k_max: int = 4, split_sign: bool = True) -> pd.DataFrame:
    """Lags 0..k_max. split_sign: El Nino part max(x,0) and La Nina part min(x,0)."""
    out = {}
    for k in range(k_max + 1):
        x = q.shift(k)
        if split_sign:
            out[f"{q.name}_pos_l{k}"] = x.clip(lower=0)
            out[f"{q.name}_neg_l{k}"] = x.clip(upper=0)
        else:
            out[f"{q.name}_l{k}"] = x
    return pd.DataFrame(out, index=q.index)
