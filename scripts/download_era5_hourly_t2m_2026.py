"""Download hourly ERA5 2 m temperature, 31 Jul 2026 (16-23 UTC) to the latest available day of
Nov 2026, for the electricity pipeline test (tracker G3). Download and verification only: no
processing.

Same CDS set-up as the hourly 1950-1969 download (~/era5_tmp/download_era5.py): dataset
reanalysis-era5-single-levels, product type reanalysis, Philippine box [N 21.5, W 116, S 4.5,
E 127] on the native 0.25 deg grid, data_format netcdf, download_format unarchived, one file per
month named era5_YYYY_MM.nc. Only the variable differs (2m_temperature only).

Requests, one per month:
- era5_2026_07.nc: 31 Jul only, 16:00-23:00 UTC (the first Philippine day of August at UTC+8);
  note that this file holds 8 hours, not a whole month.
- era5_2026_08.nc, _09, _10: whole months.
- era5_2026_11.nc: 1 Nov to the latest day available. ERA5 runs about 5 days behind, so the
  request starts at today - 5 days and, if the CDS refuses it, steps back one day at a time
  (up to 5 times).
Resumable: months already downloaded are skipped (delete era5_2026_11.nc to extend November
later). Each file is written to a .part file and renamed when complete.

Verification (after the downloads, or alone with --verify-only): hours per file against the
hours requested, with no gaps; first and last UTC time stamp; whether the file has an expver
dimension or variable (recent ERA5T data); and whether latitude and longitude are identical to
a 1950-1969 file (default ~/era5_tmp/era5_wbgt/era5_1950_01.nc).

Run:  python3 scripts/download_era5_hourly_t2m_2026.py [--out ~/data_tmp/era5_2026] [--verify-only]
Needs cdsapi (>= 0.7.7) and ~/.cdsapirc; xarray and netCDF4 for the verification.
"""
import argparse
import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

DATASET = "reanalysis-era5-single-levels"
AREA = [21.5, 116.0, 4.5, 127.0]  # N, W, S, E: as in ~/era5_tmp/download_era5.py
OUT = Path.home() / "data_tmp" / "era5_2026"
REFERENCE = Path.home() / "era5_tmp" / "era5_wbgt" / "era5_1950_01.nc"
LAG_DAYS = 5
STEP_BACK = 5


def request(year, month, days, hours):
    return {"product_type": ["reanalysis"], "variable": ["2m_temperature"],
            "year": str(year), "month": f"{month:02d}", "day": [f"{d:02d}" for d in days],
            "time": [f"{h:02d}:00" for h in hours], "area": AREA,
            "data_format": "netcdf", "download_format": "unarchived"}


def jobs(today):
    """(file name, year, month, days, hours) for each request; November up to the latest day
    that can be available (today - LAG_DAYS)."""
    out = [("era5_2026_07.nc", 2026, 7, [31], range(16, 24))]
    for m in (8, 9, 10):
        out.append((f"era5_2026_{m:02d}.nc", 2026, m, range(1, calendar.monthrange(2026, m)[1] + 1), range(24)))
    last = min(date(2026, 11, 30), today - timedelta(days=LAG_DAYS))
    if last >= date(2026, 11, 1):
        out.append(("era5_2026_11.nc", 2026, 11, range(1, last.day + 1), range(24)))
    return out


def looks_like_zip(path):
    with open(path, "rb") as f:
        return f.read(2) == b"PK"


def download(out, today):
    import cdsapi
    client = None
    failed = []
    for name, y, m, days, hours in jobs(today):
        dest = out / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[skip] {name} already exists")
            continue
        client = client or cdsapi.Client()
        days = list(days)
        tries = STEP_BACK + 1 if m == 11 else 1
        for t in range(tries):
            d = days[: len(days) - t]
            tmp = dest.with_suffix(".nc.part")
            print(f"[get ] {name}: {y}-{m:02d}, days {d[0]}-{d[-1]}, hours {min(hours):02d}-{max(hours):02d} UTC")
            try:
                client.retrieve(DATASET, request(y, m, d, hours), str(tmp))
                tmp.rename(dest)
                if looks_like_zip(dest):
                    print(f"[note] {name} arrived as a zip archive; kept unchanged", file=sys.stderr)
                break
            except Exception as exc:
                if tmp.exists():
                    tmp.unlink()
                if t + 1 < tries:
                    print(f"[back] {name}: not available up to day {d[-1]} ({str(exc)[:120]}); trying one day earlier")
                else:
                    print(f"[FAIL] {name}: {exc}", file=sys.stderr)
                    failed.append(name)
    return failed


def verify(out, reference, today):
    import numpy as np
    import pandas as pd
    import xarray as xr
    ref = xr.open_dataset(reference) if reference.exists() else None
    expected = {name: len(list(days)) * len(list(hours)) for name, _, _, days, hours in jobs(today)}
    print(f"\nVerification (reference grid: {reference if ref is not None else 'not found'})")
    for f in sorted(out.glob("era5_2026_*.nc")):
        with xr.open_dataset(f) as ds:
            tname = "valid_time" if "valid_time" in ds.coords else "time"
            t = pd.DatetimeIndex(ds[tname].values)
            step = pd.Series(t).diff().dropna()
            gaps = int((step != pd.Timedelta(hours=1)).sum())
            exp_hours = expected.get(f.name)
            if f.name == "era5_2026_11.nc":  # November length depends on the day it was downloaded
                exp_hours = (t.max().normalize() - t.min().normalize()).days * 24 + 24
            expver = ("dimension" if "expver" in ds.dims else
                      "variable/coordinate" if ("expver" in ds.variables) else "no")
            ev = ""
            if expver != "no":
                ev = " values " + ",".join(sorted(map(str, np.unique(ds["expver"].values))))
            grid = ""
            if ref is not None:
                same = (np.array_equal(ds.latitude.values, ref.latitude.values)
                        and np.array_equal(ds.longitude.values, ref.longitude.values))
                grid = (f"; grid {ds.sizes['latitude']}x{ds.sizes['longitude']} "
                        f"{'identical to reference' if same else 'DIFFERS from reference'}")
            print(f"{f.name}: {len(t)} hours (expected {exp_hours}), gaps {gaps}, "
                  f"{t.min():%Y-%m-%d %H:%M} to {t.max():%Y-%m-%d %H:%M} UTC; "
                  f"vars {list(ds.data_vars)}; expver {expver}{ev}{grid}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--reference", default=str(REFERENCE))
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    today = date.today()
    failed = [] if a.verify_only else download(out, today)
    verify(out, Path(a.reference).expanduser(), today)
    if failed:
        print("\nFailed (re-run to retry):", *failed, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
