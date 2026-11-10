#!/usr/bin/env python3
"""
01_download_era5.py
===================

Download ERA5 (single levels) *monthly means* for the Philippines.


Streams
-------
  * "mean"     -> product_type "monthly_averaged_reanalysis" (all variables)
  * "byhour00" -> product_type "monthly_averaged_reanalysis_by_hour_of_day",
                  time 00:00, accumulated variables only (optional)

Variables
---------
2 m temperature, 2 m dewpoint, total precipitation, volumetric soil water layers
1-4 (0-7, 7-28, 28-100, 100-289 cm), potential evaporation, evaporation,
surface solar radiation downwards and runoff.

One-time setup
--------------
1. Create a free account at https://cds.climate.copernicus.eu
2. Open the dataset page "ERA5 monthly averaged data on single levels from 1940
   to present", go to the Download tab and ACCEPT the licence.
3. Copy your personal access token into ~/.cdsapirc:
       url: https://cds.climate.copernicus.eu/api
       key: <YOUR-PERSONAL-ACCESS-TOKEN>
4. pip install cdsapi

Usage
-----
    python scripts/01_download_era5.py --dry-run
    python scripts/01_download_era5.py
    python scripts/01_download_era5.py --workers 2
    python scripts/01_download_era5.py --outdir /some/other/folder

The files are NOT kept in the repo: by default they go to era5_monthly_dir in
config/paths.toml (gitignored; template config/paths.example.toml), the folder that
src/climate/era5.py reads; --outdir overrides it. Never copy or commit the .nc files.

The script is resumable: existing files are skipped.

Notes
-----
* Default area covers the whole Philippines with a margin (N=22, W=116, S=4, E=127.5).
  ERA5 is 0.25 deg, so the grid is much coarser than ERA5-Land; coastal and
  island cells will be mostly ocean/mixed. Consider also downloading the
  land-sea mask ("land_sea_mask", a single-level variable) if you want to
  restrict to land.
* Soil moisture and evaporation over ocean points are not physically meaningful
  in ERA5; mask them in processing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import local_path  # noqa: E402

DATASET = "reanalysis-era5-single-levels-monthly-means"
STREAM_MEAN = "monthly_averaged_reanalysis"
STREAM_BYHOUR = "monthly_averaged_reanalysis_by_hour_of_day"
STREAM_TAG = {STREAM_MEAN: "mean", STREAM_BYHOUR: "byhour00"}

# CDS variable name -> (NetCDF short name, accumulated field?)
VARIABLES: dict[str, tuple[str, bool]] = {
    "2m_temperature": ("t2m", False),
    "2m_dewpoint_temperature": ("d2m", False),
    "total_precipitation": ("tp", True),
    "volumetric_soil_water_layer_1": ("swvl1", False),
    "volumetric_soil_water_layer_2": ("swvl2", False),
    "volumetric_soil_water_layer_3": ("swvl3", False),
    "volumetric_soil_water_layer_4": ("swvl4", False),
    "potential_evaporation": ("pev", True),
    "evaporation": ("e", True),  # ERA5-Land calls this "total_evaporation"
    "surface_solar_radiation_downwards": ("ssrd", True),
    "runoff": ("ro", True),
}

log = logging.getLogger("era5.download")


@dataclass(frozen=True)
class Job:
    variable: str
    stream: str
    y0: int
    y1: int
    target: Path
    request: dict

    @property
    def label(self) -> str:
        return f"{self.variable} [{STREAM_TAG[self.stream]}] {self.y0}-{self.y1}"


def build_jobs(variables, start, end, chunk, outdir, include_byhour, data_format, area):
    """Return the list of CDS requests (one per variable x stream x year block)."""
    jobs: list[Job] = []
    for var in variables:
        _, accumulated = VARIABLES[var]
        streams = [STREAM_MEAN]
        if accumulated and include_byhour:
            streams.append(STREAM_BYHOUR)
        for stream in streams:
            for y0 in range(start, end + 1, chunk):
                y1 = min(y0 + chunk - 1, end)
                request = {
                    "product_type": [stream],
                    "variable": [var],
                    "year": [str(y) for y in range(y0, y1 + 1)],
                    "month": [f"{m:02d}" for m in range(1, 13)],
                    "time": ["00:00"],
                    "data_format": data_format,
                    "download_format": "unarchived",
                    "area": list(area),  # [North, West, South, East]
                }
                name = f"era5_{STREAM_TAG[stream]}_{var}_{y0}-{y1}.nc"
                jobs.append(Job(var, stream, y0, y1, outdir / name, request))
    return jobs


def looks_like_netcdf(path: Path) -> bool:
    with open(path, "rb") as fh:
        head = fh.read(8)
    return head[:3] == b"CDF" or head[:4] == b"\x89HDF"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _unzip_single(part: Path) -> None:
    """If CDS returned a zip with exactly one NetCDF inside, replace the zip by it."""
    if not zipfile.is_zipfile(part):
        return
    with zipfile.ZipFile(part) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".nc")]
        if len(members) != 1:
            raise RuntimeError(f"zip with {len(members)} NetCDF members; inspect {part} manually")
        data = zf.read(members[0])
    part.write_bytes(data)


def make_client():
    import cdsapi  # imported lazily so --dry-run works without it

    return cdsapi.Client()


def run_job(job: Job, retries: int, client_factory=make_client) -> tuple[str, str]:
    """Download one job. Returns (label, status) with status in {skipped, ok, failed:<msg>}."""
    if job.target.exists() and job.target.stat().st_size > 0:
        return job.label, "skipped"

    part = job.target.with_suffix(".nc.part")
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            log.info("requesting %s (attempt %d/%d)", job.label, attempt, retries)
            client = client_factory()
            client.retrieve(DATASET, job.request, str(part))
            _unzip_single(part)
            if not looks_like_netcdf(part):
                raise RuntimeError("downloaded file is not NetCDF (check --data-format)")
            os.replace(part, job.target)
            sidecar = {
                "dataset": DATASET,
                "request": job.request,
                "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bytes": job.target.stat().st_size,
                "sha256": sha256(job.target),
            }
            try:
                import cdsapi

                sidecar["cdsapi_version"] = getattr(cdsapi, "__version__", "unknown")
            except ImportError:
                pass
            job.target.with_suffix(".json").write_text(json.dumps(sidecar, indent=2))
            return job.label, "ok"
        except Exception as exc:  # noqa: BLE001 - we retry on anything
            last_err = f"{type(exc).__name__}: {exc}"
            log.warning("%s failed: %s", job.label, last_err)
            if part.exists():
                part.unlink()
            if attempt < retries:
                time.sleep(min(60, 5 * 2 ** (attempt - 1)))
    return job.label, f"failed:{last_err}"


def credentials_present() -> bool:
    if os.environ.get("CDSAPI_KEY"):
        return True
    return (Path.home() / ".cdsapirc").exists()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--outdir", type=Path, default=None,
                   help="where to store the files (default: era5_monthly_dir in config/paths.toml)")
    p.add_argument("--start-year", type=int, default=1950, help="ERA5 starts in 1940")
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--chunk-years", type=int, default=10, help="years per request (default 10)")
    p.add_argument("--area", type=float, nargs=4, metavar=("N", "W", "S", "E"), default=[22.0, 116.0, 4.0, 127.5])
    p.add_argument("--variables", nargs="+", choices=sorted(VARIABLES), default=sorted(VARIABLES),
                   help="subset of ERA5 variables (default: all 11, incl. the 4 soil layers)")
    p.add_argument("--include-byhour", action="store_true",
                   help="also download the by-hour-of-day stream (00:00) for accumulated variables, "
                        "as a cross-check. Not needed for ERA5 (the ERA5-Land accumulation bug does not apply).")
    p.add_argument("--data-format", choices=("netcdf_legacy", "netcdf"), default="netcdf")
    p.add_argument("--workers", type=int, default=1, help="simultaneous CDS requests (default 1)")
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--dry-run", action="store_true", help="only list the requests")
    return p.parse_args(argv)


def main(argv=None, client_factory=make_client) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.start_year < 1940 or args.end_year < args.start_year:
        log.error("invalid year range (ERA5 monthly means start in 1940)")
        return 2

    if args.outdir is None:
        args.outdir = local_path("era5_monthly_dir", must_exist=False)
    args.outdir.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(args.variables, args.start_year, args.end_year, args.chunk_years, args.outdir,
                      args.include_byhour, args.data_format, args.area)
    todo = [j for j in jobs if not (j.target.exists() and j.target.stat().st_size > 0)]
    log.info("%d requests in total, %d still to do (%d already on disk)", len(jobs), len(todo), len(jobs) - len(todo))

    if args.dry_run:
        for j in jobs:
            state = "exists" if j not in todo else "todo  "
            print(f"[{state}] {j.target.name}")
        return 0

    if todo and client_factory is make_client and not credentials_present():
        log.error("No CDS credentials found. Create ~/.cdsapirc (see the docstring at the top of this script).")
        return 2

    failures: list[tuple[str, str]] = []
    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_job, j, args.retries, client_factory) for j in todo]
            for fut in as_completed(futures):
                label, status = fut.result()
                if status.startswith("failed"):
                    failures.append((label, status))
    else:
        for j in todo:
            label, status = run_job(j, args.retries, client_factory)
            if status.startswith("failed"):
                failures.append((label, status))

    if failures:
        log.error("%d request(s) failed:", len(failures))
        for label, status in failures:
            log.error("  %s -> %s", label, status)
        log.error("Re-run the script to retry only the missing files.")
    else:
        log.info("all ERA5 requests complete")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())