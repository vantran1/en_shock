#!/usr/bin/env python3
"""
Download hourly ERA5 (single levels) fields needed to compute WBGT with pywbgt
(Liljegren for outdoor work, Bernard for indoor work) over the Philippines,
plus hourly total precipitation.

One NetCDF file is written per month, named era5_YYYY_MM.nc. The script is
safe to re-run: files that already exist are skipped, so an interrupted
download resumes where it stopped.

Variables (the six pywbgt needs, plus hourly precipitation):
    2m_temperature                      -> t2m   (K)
    2m_dewpoint_temperature             -> d2m   (K)
    surface_pressure                    -> sp    (Pa)
    10m_u_component_of_wind             -> u10   (m/s)
    10m_v_component_of_wind             -> v10   (m/s)
    surface_solar_radiation_downwards   -> ssrd  (J/m2, accumulated over the hour
                                                  ending at the time stamp)
    total_precipitation                 -> tp    (m of water, accumulated over the
                                                  hour ending at the time stamp)

Note: unlike ERA5-Land (accumulated from 00 UTC), ERA5 single-levels
accumulations cover only the preceding hour. ssrd / 3600 gives the hourly mean
in W/m2 and tp * 1000 gives mm per hour; no differencing is needed.

The CDS may deliver instantaneous and accumulated variables as a zip of two
NetCDF files. The script detects this and merges them into one NetCDF per month
automatically (needs xarray and netcdf4); a file already downloaded as a zip is
repaired in place by simply re-running the same command.

Setup (once) - see the accompanying LaTeX guide for the full walkthrough:
  1. Create a free account at https://cds.climate.copernicus.eu
  2. Accept the ERA5 licence on the dataset page:
     https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels
  3. Put your personal access token in ~/.cdsapirc :
         url: https://cds.climate.copernicus.eu/api
         key: <your-personal-access-token>
  4. pip install "cdsapi>=0.7.7"

Usage examples:
  # one-month test (April 2024, whole Philippines)
  python download_era5.py --start 2024 --end 2024 --months 4

  # same month over a smaller box (Luzon) for a faster, smaller test
  python download_era5.py --start 2024 --end 2024 --months 4 --area 19.5 119.5 12.0 124.5

  # full period
  python download_era5.py --start 1990 --end 2024

  # show what would be requested without contacting the CDS
  python download_era5.py --start 2024 --end 2024 --months 4 --dry-run
"""
import argparse
import calendar
import json
import sys
from pathlib import Path

DATASET = "reanalysis-era5-single-levels"

VARIABLES = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "surface_pressure",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_solar_radiation_downwards",
    "total_precipitation",
]

# Philippines bounding box in CDS order: [North, West, South, East]
PHILIPPINES_AREA = [21.5, 116.0, 4.5, 127.0]


def build_request(year, month, area):
    ndays = calendar.monthrange(year, month)[1]
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": str(year),
        "month": f"{month:02d}",
        "day": [f"{d:02d}" for d in range(1, ndays + 1)],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": area,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def looks_like_zip(path):
    with open(path, "rb") as f:
        return f.read(2) == b"PK"


def merge_zip_to_netcdf(path):
    """Replace a CDS zip archive at `path` with one merged NetCDF of the same name.

    ERA5 single levels mixes instantaneous variables (t2m, d2m, sp, u10, v10) with
    accumulated ones (ssrd, tp), and the CDS then delivers one NetCDF per step
    type inside a zip. They share the same grid and hours, so they are merged
    into a single file with all seven variables. Needs xarray and netCDF4."""
    import tempfile
    import zipfile

    try:
        import xarray as xr
    except ImportError:
        sys.exit("xarray is needed to merge the CDS zip archive. Run:  pip install xarray netcdf4")

    path = Path(path)
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(path) as zf:
            zf.extractall(tmp)
        files = sorted(tmp.rglob("*.nc"))
        if not files:
            raise RuntimeError(f"{path.name} is a zip archive but contains no .nc files")
        parts = []
        for f in files:
            with xr.open_dataset(f) as d:
                scalar = [c for c in ("number",) if c in d.coords and c not in d.dims]
                parts.append(d.drop_vars(scalar).load())
        merged = xr.merge(parts, compat="override")
        merged_path = tmp / "merged.nc"
        merged.to_netcdf(merged_path)
        merged_path.replace(path)  # overwrite the zip with the merged NetCDF
    return list(merged.data_vars)


def main():
    p = argparse.ArgumentParser(
        description="Download hourly ERA5 single-levels inputs for WBGT plus "
                    "total precipitation (one NetCDF per month).",
        epilog="See the module docstring (or the LaTeX guide) for setup and examples.",
    )
    p.add_argument("--start", type=int, required=True, help="first year")
    p.add_argument("--end", type=int, required=True, help="last year (inclusive)")
    p.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)),
                   metavar="M", help="months to fetch, 1-12 (default: all)")
    p.add_argument("--outdir", default=str(Path(__file__).resolve().parents[2] / "data" / "shared" / "era5" / "hourly"),
                   help="output directory (default: en_shock/data/shared/era5/hourly)")
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
        print(f"Output  : {outdir}/era5_YYYY_MM.nc  ({len(jobs)} file(s))")
        print("Request for the first file:")
        print(json.dumps(build_request(*jobs[0], args.area), indent=2))
        return

    outdir.mkdir(parents=True, exist_ok=True)
    client = None  # created lazily, only when something actually has to be downloaded

    failed = []
    for year, month in jobs:
        outfile = outdir / f"era5_{year}_{month:02d}.nc"
        if outfile.exists() and outfile.stat().st_size > 0:
            if looks_like_zip(outfile):  # repair a file downloaded as a zip archive
                try:
                    names = merge_zip_to_netcdf(outfile)
                    print(f"[fix ] {outfile.name} was a zip archive; merged into one NetCDF ({', '.join(names)})")
                except Exception as exc:
                    print(f"[FAIL] {outfile.name}: could not merge zip archive: {exc}", file=sys.stderr)
                    failed.append(outfile.name)
            else:
                print(f"[skip] {outfile.name} already exists")
            continue
        if client is None:
            try:
                import cdsapi
            except ImportError:
                sys.exit('cdsapi is not installed. Run:  pip install "cdsapi>=0.7.7"')
            client = cdsapi.Client()
        print(f"[get ] {outfile.name}")
        try:
            client.retrieve(DATASET, build_request(year, month, args.area), str(outfile))
            if looks_like_zip(outfile):  # CDS splits instant and accumulated variables into a zip
                names = merge_zip_to_netcdf(outfile)
                print(f"[merge] {outfile.name}: zip archive merged into one NetCDF ({', '.join(names)})")
        except Exception as exc:  # keep going; report everything at the end
            print(f"[FAIL] {outfile.name}: {exc}", file=sys.stderr)
            failed.append(outfile.name)
            if outfile.exists() and not looks_like_zip(outfile):
                outfile.unlink()  # never leave a partial file behind
                # (a zip that failed to merge is kept so nothing downloaded is lost)

    if failed:
        print("\nFailed (re-run the same command to retry):", *failed, sep="\n  ")
        sys.exit(1)
    print("\nDone.")


if __name__ == "__main__":
    main()