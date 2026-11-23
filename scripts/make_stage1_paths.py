"""Scenario paths for Van's Stage 1 simulation (stage1_enso_iod, step 5), the same four paths as the
direct-approach shocks (scripts/shocks_direct.py), so that the two-stage and direct shocks can be
compared. Writes small csv files only; nothing is simulated here.

Format required by stage1_enso_iod (config.yaml, path.source: csv): columns date (YYYY-MM-01), roni,
dmi, in the model's units (centred 3-month means), one row per month. Stage 1 fills the 6 months
before the first row (its longest lag) with the observed indices of those dates, so every path
starts with 6 months at zero: they keep the observed lead-in out of the El Nino months and are to be
discarded from the results.

Paths:
- 1997-98, 2015-16, 2023-24: RONI and DMI of the El Nino quarters of the direct approach (quarters
  with quarterly RONI >= 0.5: 1997Q2-1998Q1, 2015Q2-2016Q1, 2023Q3-2024Q1), month by month, taken
  from Van's own index files (stage1_enso_iod/data/indices on dev_Van, so in the model's units);
  zero before and after.
- unit: RONI +1 for twelve months from July (as the direct unit path, 2001Q3-2002Q2), DMI 0.
Each path: 6 zero months, the El Nino months, then 12 zero months (harvest effects lag the weather).
The DMI column is used only by the RONI + DMI variant; the main Stage 1 runs on RONI alone. DMI is
taken as the centred 3-month mean of Van's monthly DMI (his RONI file is already in that form).

Run:  python scripts/make_stage1_paths.py   (reads Van's index files from the dev_Van branch)
Writes outputs/stage1_paths/path_<name>.csv
"""
import subprocess
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/stage1_paths"
BRANCH = "origin/dev_Van"
PAD_BEFORE, PAD_AFTER = 6, 12
EPISODES = {"1997-98": ("1997-04", "1998-03"), "2015-16": ("2015-04", "2016-03"),
            "2023-24": ("2023-07", "2024-03")}
UNIT = ("2001-07", "2002-06")


def van_index(name):
    txt = subprocess.run(["git", "show", f"{BRANCH}:stage1_enso_iod/data/indices/{name}_monthly.csv"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    s = pd.read_csv(StringIO(txt), parse_dates=["date"]).set_index("date")[name]
    return s


def frame(start, end, roni, dmi):
    """Zero pad, the El Nino months with the given values, zero pad."""
    months = pd.date_range(pd.Timestamp(start) - pd.DateOffset(months=PAD_BEFORE),
                           pd.Timestamp(end) + pd.DateOffset(months=PAD_AFTER), freq="MS")
    d = pd.DataFrame({"date": months, "roni": 0.0, "dmi": 0.0})
    inside = d.date.between(pd.Timestamp(start), pd.Timestamp(end))
    d.loc[inside, "roni"] = roni.reindex(d.date[inside]).to_numpy()
    d.loc[inside, "dmi"] = dmi.reindex(d.date[inside]).to_numpy()
    if d[["roni", "dmi"]].isna().any().any():
        raise ValueError(f"missing index values in {start}-{end}")
    return d


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    roni = van_index("roni")
    dmi = van_index("dmi").rolling(3, center=True).mean()
    paths = {name: frame(a, b, roni, dmi) for name, (a, b) in EPISODES.items()}
    one = pd.Series(1.0, index=pd.date_range(*UNIT, freq="MS"))
    paths["unit"] = frame(*UNIT, one, one * 0.0)
    for name, d in paths.items():
        f = OUT / f"path_{name}.csv"
        d.assign(date=d.date.dt.strftime("%Y-%m-%d")).round(3).to_csv(f, index=False)
        nino = d[(d.roni != 0) | (d.dmi != 0)]
        print(f"{f.name}: {len(d)} months ({d.date.min():%Y-%m} to {d.date.max():%Y-%m}); El Nino months "
              f"{nino.date.min():%Y-%m} to {nino.date.max():%Y-%m}, RONI max {d.roni.max():.2f}")


if __name__ == "__main__":
    main()
