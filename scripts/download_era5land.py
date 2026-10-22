#!/usr/bin/env python3
"""
Download the hourly ERA5-Land fields needed to compute WBGT with pywbgt
(Liljegren for outdoor work, Bernard for indoor work) over the Philippines.

One NetCDF file is written per month, named era5land_YYYY_MM.nc. The script is
safe to re-run: files that already exist are skipped, so an interrupted
download resumes where it stopped.

Variables (the six pywbgt needs; nothing else is required):
    2m_temperature                      -> t2m   (K)
    2m_dewpoint_temperature             -> d2m   (K)
    surface_pressure                    -> sp    (Pa)
    10m_u_component_of_wind             -> u10   (m/s)
    10m_v_component_of_wind             -> v10   (m/s)
    surface_solar_radiation_downwards   -> ssrd  (J/m2, ACCUMULATED from 00 UTC)

Setup (once) - see the accompanying LaTeX guide for the full walkthrough:
  1. Create a free account at https://cds.climate.copernicus.eu
  2. Accept the ERA5-Land licence on the dataset page:
     https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land
  3. Put your personal access token in ~/.cdsapirc :
         url: https://cds.climate.copernicus.eu/api
         key: <your-personal-access-token>
  4. pip install "cdsapi>=0.7.7"

Usage examples:
  # one-month test (April 2024, whole Philippines)
  python download_era5land.py --start 2024 --end 2024 --months 4

  # same month over a smaller box (Luzon) for a faster, smaller test
  python download_era5land.py --start 2024 --end 2024 --months 4 --area 19.5 119.5 12.0 124.5

  # full period
  python download_era5land.py --start 1990 --end 2024

  # show what would be requested without contacting the CDS
  python download_era5land.py --start 2024 --end 2024 --months 4 --dry-run
"""
import argparse
import calendar
import json
import sys
from pathlib import Path

DATASET = "reanalysis-era5-land"

VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "surface_pressure",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_solar_radiation_downwards",
]

# Philippines bounding box in CDS order: [North, West, South, East]
PHILIPPINES_AREA = [21.5, 116.0, 4.5, 127.0]


def build_request(year, month, area):
    ndays = calendar.monthrange(year, month)[1]
    return {
        "variable": VARIABLES,
        "year": str(year),
        "month": f"{month:02d}",
        "day": [f"{d:02d}" for d in range(1, ndays + 1)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def main():
    p = argparse.ArgumentParser(
        description="Download hourly ERA5-Land inputs for WBGT (one NetCDF per month).",
        epilog="See the module docstring (or the LaTeX guide) for setup and examples.",
    )
    p.add_argument("--start", type=int, required=True, help="first year")
    p.add_argument("--end", type=int, required=True, help="last year (inclusive)")
    p.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)),
                   metavar="M", help="months to fetch, 1-12 (default: all)")
    p.add_argument("--outdir", default="era5land_wbgt", help="output directory")
    p.add_argument("--area", type=float, nargs=4, default=PHILIPPINES_AREA,
                   metavar=("N", "W", "S", "E"),
                   help="bounding box in degrees (default: Philippines)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the requests and exit without contacting the CDS")
    args = p.parse_args()

    if args.end < args.start:
        p.error("--end must be >= --start")
    if any(m < 1 or m > 12 for m in args.months):
        p.error("--months must be between 1 and 12")

    outdir = Path(args.outdir)
    jobs = [(y, m) for y in range(args.start, args.end + 1) for m in args.months]

    if args.dry_run:
        print(f"Dataset : {DATASET}")
        print(f"Output  : {outdir}/era5land_YYYY_MM.nc  ({len(jobs)} file(s))")
        print("Request for the first file:")
        print(json.dumps(build_request(*jobs[0], args.area), indent=2))
        return

    try:
        import cdsapi
    except ImportError:
        sys.exit('cdsapi is not installed. Run:  pip install "cdsapi>=0.7.7"')

    outdir.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()

    failed = []
    for year, month in jobs:
        outfile = outdir / f"era5land_{year}_{month:02d}.nc"
        if outfile.exists() and outfile.stat().st_size > 0:
            print(f"[skip] {outfile.name} already exists")
            continue
        print(f"[get ] {outfile.name}")
        try:
            client.retrieve(DATASET, build_request(year, month, args.area), str(outfile))
        except Exception as exc:  # keep going; report everything at the end
            print(f"[FAIL] {outfile.name}: {exc}", file=sys.stderr)
            failed.append(outfile.name)
            if outfile.exists():
                outfile.unlink()  # never leave a partial file behind

    if failed:
        print("\nFailed (re-run the same command to retry):", *failed, sep="\n  ")
        sys.exit(1)
    print("\nDone.")


if __name__ == "__main__":
    main()