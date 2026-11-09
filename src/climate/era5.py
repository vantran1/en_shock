"""Shared loader for ERA5 monthly single-level data (CLAUDE.md: one loader for every module).

The .nc files are NOT in the repo. Their folder is set once in config/paths.toml
(gitignored; template config/paths.example.toml) or passed explicitly as `directory`
(scripts expose it as --era5-dir).

Source: reanalysis-era5-single-levels-monthly-means, product monthly_averaged_reanalysis,
area 22N/116E/4N/127.5E, 0.25 deg (73 x 47 cells), 1950-01 to 2025-12, one file per
variable and decade (era5_mean_<variable>_<years>.nc) with a .json download record
(request, sha256). Same grid as data/era5/era5_land_sea_mask_0.25deg_phl.nc.

Units as stored by ECMWF and as returned by load() (convert=True):
- t2m, d2m: monthly mean, K -> deg C.
- tp, e, pev, ro: "avgad" = mean DAILY accumulation in metres -> monthly total in mm
  (x 1000 x days in month). This is the common trap: tp is not a monthly total.
  e and pev are negative when water leaves the surface (ECMWF sign convention); they are
  returned with the sign flipped, so positive = evaporation.
- ssrd: mean daily accumulation in J m-2 -> mean flux in W m-2 (/ 86400).
- swvl1-4: volumetric soil water (m3 m-3), layers 0-7, 7-28, 28-100, 100-289 cm; unchanged.
Accumulated fields are stamped 06:00 on the first of the month; all times are set to the
first of the month.
Caution: ERA5 potential evaporation (pev) is known to be unreliable over land; an FAO-56
estimate from t2m, d2m and ssrd is the safer choice for a drought index (SPEI).
"""
import hashlib
import json
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "paths.toml"
MASK = ROOT / "data" / "era5" / "era5_land_sea_mask_0.25deg_phl.nc"

# long name used in the file names -> (short name in the file, unit after conversion)
VARIABLES = {
    "2m_temperature": ("t2m", "deg C"),
    "2m_dewpoint_temperature": ("d2m", "deg C"),
    "total_precipitation": ("tp", "mm/month"),
    "evaporation": ("e", "mm/month"),
    "potential_evaporation": ("pev", "mm/month"),
    "runoff": ("ro", "mm/month"),
    "surface_solar_radiation_downwards": ("ssrd", "W m-2"),
    "volumetric_soil_water_layer_1": ("swvl1", "m3 m-3"),
    "volumetric_soil_water_layer_2": ("swvl2", "m3 m-3"),
    "volumetric_soil_water_layer_3": ("swvl3", "m3 m-3"),
    "volumetric_soil_water_layer_4": ("swvl4", "m3 m-3"),
}
ACCUMULATED = {"tp", "e", "pev", "ro"}
UPWARD_NEGATIVE = {"e", "pev"}


def era5_dir(directory=None) -> Path:
    """Folder of the ERA5 files: the argument if given, else config/paths.toml."""
    if directory is None:
        if not CONFIG.exists():
            raise FileNotFoundError(
                f"{CONFIG} not found: copy config/paths.example.toml to config/paths.toml "
                "and set era5_monthly_dir, or pass the folder explicitly (--era5-dir).")
        with open(CONFIG, "rb") as f:
            directory = tomllib.load(f).get("era5_monthly_dir")
        if not directory:
            raise KeyError(f"era5_monthly_dir is not set in {CONFIG}")
    d = Path(directory).expanduser()
    if not d.is_dir():
        raise FileNotFoundError(f"ERA5 folder does not exist: {d}")
    return d


def files(variable: str, directory=None) -> list[Path]:
    if variable not in VARIABLES:
        raise KeyError(f"unknown ERA5 variable {variable!r}; known: {sorted(VARIABLES)}")
    fs = sorted(era5_dir(directory).glob(f"era5_mean_{variable}_[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].nc"))
    if not fs:
        raise FileNotFoundError(f"no files for {variable} in {era5_dir(directory)}")
    return fs


def _convert(da: xr.DataArray, short: str) -> xr.DataArray:
    if short in ("t2m", "d2m"):
        return da - 273.15
    if short in ACCUMULATED:
        days = xr.DataArray(da.time.dt.days_in_month, coords={"time": da.time})
        out = da * 1000.0 * days
        return -out if short in UPWARD_NEGATIVE else out
    if short == "ssrd":
        return da / 86400.0
    return da


def load(variable: str, directory=None, convert: bool = True) -> xr.DataArray:
    """Monthly field (time, latitude, longitude) for 1950-01..2025-12, all decade files joined.

    Raises if months are duplicated or missing, or if any month is preliminary data."""
    short, unit = VARIABLES[variable]
    parts = []
    for f in files(variable, directory):
        with xr.open_dataset(f) as ds:
            da = ds[short].load()
            expver = np.atleast_1d(ds["expver"].values)
        if not set(expver.tolist()) <= {"0001"}:
            raise ValueError(f"{f.name}: preliminary ERA5T months (expver {set(expver)})")
        da = da.drop_vars([c for c in ("number", "expver") if c in da.coords])
        parts.append(da.rename({"valid_time": "time"}))
    da = xr.concat(parts, dim="time").sortby("time")
    da["time"] = pd.DatetimeIndex(da.time.values).to_period("M").to_timestamp()
    t = pd.DatetimeIndex(da.time.values)
    if t.duplicated().any():
        raise ValueError(f"{variable}: duplicated months {t[t.duplicated()].strftime('%Y-%m').tolist()}")
    full = pd.date_range(t.min(), t.max(), freq="MS")
    if len(full) != len(t):
        missing = full.difference(t).strftime("%Y-%m").tolist()
        raise ValueError(f"{variable}: missing months {missing}")
    if convert:
        da = _convert(da, short)
        da.attrs = {"long_name": variable, "units": unit}
    return da.rename(short)


def land_sea_mask() -> xr.DataArray:
    """Land fraction (0-1) per 0.25 deg cell, same grid as the ERA5 files (in the repo)."""
    with xr.open_dataset(MASK) as ds:
        return ds["lsm"].squeeze(drop=True).drop_vars(["number", "expver"], errors="ignore").load()


def inventory(directory=None) -> pd.DataFrame:
    """One row per .nc file: variable, years, months, and whether the sha256 matches the
    .json download record."""
    d = era5_dir(directory)
    rows = []
    for f in sorted(d.glob("era5_mean_*.nc")):
        stem = f.stem.removeprefix("era5_mean_")
        variable, years = stem.rsplit("_", 1)
        rec = f.with_suffix(".json")
        sha_ok = None
        if rec.exists():
            sha_ok = json.loads(rec.read_text()).get("sha256") == hashlib.sha256(f.read_bytes()).hexdigest()
        with xr.open_dataset(f) as ds:
            n = ds.sizes["valid_time"]
            grid = f"{ds.sizes['latitude']}x{ds.sizes['longitude']}"
        rows.append(dict(file=f.name, variable=variable, years=years, months=n, grid=grid,
                         json_record=rec.exists(), sha256_matches=sha_ok))
    return pd.DataFrame(rows)
