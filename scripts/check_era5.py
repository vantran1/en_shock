"""Check the ERA5 monthly files (outside the repo) before they are used.

- every file matches the sha256 in its .json download record;
- every variable covers 1950-01..2025-12 with no gap, duplicate or preliminary month;
- units are right: land-mean annual rainfall and temperature for the Philippines are in
  the expected range (about 2,000-3,500 mm and 25-28 deg C; land cells include mountains).

Run:  python scripts/check_era5.py                     (folder from config/paths.toml)
      python scripts/check_era5.py --era5-dir /path/to/era5_monthly
Writes outputs/tables/era5_inventory.csv (file names only, no data).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from climate.era5 import VARIABLES, era5_dir, inventory, land_sea_mask, load  # noqa: E402

TAB = ROOT / "outputs/tables"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--era5-dir", help="folder of the ERA5 .nc files (overrides config/paths.toml)")
    args = ap.parse_args()
    d = era5_dir(args.era5_dir)
    print(f"ERA5 folder: {d}")

    inv = inventory(d)
    TAB.mkdir(parents=True, exist_ok=True)
    inv.to_csv(TAB / "era5_inventory.csv", index=False)
    bad = inv[inv.sha256_matches != True]  # noqa: E712
    print(f"{len(inv)} files, {inv.variable.nunique()} variables; "
          f"sha256 mismatches or missing records: {len(bad)}")
    if len(bad):
        print(bad.to_string(index=False))

    land = land_sea_mask() > 0.5
    rows = []
    for v in VARIABLES:
        da = load(v, d)
        if land.shape != da.isel(time=0).shape:
            raise ValueError(f"{v}: grid differs from the land-sea mask")
        m = da.where(land).mean(["latitude", "longitude"]).to_series()
        annual = m.groupby(m.index.year).sum() if da.attrs["units"] == "mm/month" else m.groupby(m.index.year).mean()
        rows.append(dict(variable=v, unit=da.attrs["units"],
                         first=da.time.dt.strftime("%Y-%m").values[0],
                         last=da.time.dt.strftime("%Y-%m").values[-1], months=da.sizes["time"],
                         land_mean_annual=round(float(annual.mean()), 3),
                         min_year=int(annual.idxmin()), max_year=int(annual.idxmax())))
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print("\nLand-cell mean (land fraction > 0.5), annual total for mm/month variables, "
          "annual mean otherwise:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
