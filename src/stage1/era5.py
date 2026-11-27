"""Monthly ERA5 fields at the land cells, in the units of Table 2 (as en_shock/scripts/process_era5_monthly.py)."""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import xarray as xr

# NetCDF short name -> CDS variable name, as used in the file names era5_mean_<name>_<years>.nc
VARIABLES = {
    "t2m": "2m_temperature",
    "d2m": "2m_dewpoint_temperature",
    "tp": "total_precipitation",
    "swvl1": "volumetric_soil_water_layer_1",
    "swvl2": "volumetric_soil_water_layer_2",
    "swvl3": "volumetric_soil_water_layer_3",
    "swvl4": "volumetric_soil_water_layer_4",
    "pev": "potential_evaporation",
    "e": "evaporation",
    "ssrd": "surface_solar_radiation_downwards",
    "ro": "runoff",
}
ROOT_CM = {"swvl1": 7, "swvl2": 21, "swvl3": 72}          # layer thickness, cm (root zone 0-100 cm)


def open_any(path: pathlib.Path) -> xr.Dataset:
    for engine in ("h5netcdf", "netcdf4", None):
        try:
            return xr.open_dataset(path, engine=engine) if engine else xr.open_dataset(path)
        except Exception:  # noqa: BLE001
            continue
    raise SystemExit(f"cannot open {path} (install h5netcdf or netCDF4)")


def load_variable(raw_dir: pathlib.Path, short: str) -> xr.DataArray:
    """All blocks of one variable, time labelled by month start."""
    files = sorted(pathlib.Path(raw_dir).glob(f"era5_mean_{VARIABLES[short]}_*.nc"))
    if not files:
        raise SystemExit(f"no files for {short} ({VARIABLES[short]}) in {raw_dir}")
    blocks = []
    for f in files:
        with open_any(f) as ds:
            da = ds[short].load().drop_vars(["number", "expver"], errors="ignore")
            if "valid_time" not in da.dims and "time" in da.dims:
                da = da.rename(time="valid_time")
            blocks.append(da)
    da = xr.concat(blocks, "valid_time").sortby("valid_time").rename(valid_time="time")
    month_start = pd.DatetimeIndex(da["time"].values).to_period("M").to_timestamp()
    expected = pd.date_range(month_start[0], month_start[-1], freq="MS")
    if not month_start.equals(expected):
        raise SystemExit(f"{short}: months are missing or duplicated in {raw_dir}")
    return da.assign_coords(time=month_start)


def sat_vapour_pressure_kpa(t_c):
    return 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))


def load_monthly(raw_dir: pathlib.Path) -> dict:
    """Converted monthly fields on the ERA5 grid: dict of (time, lat*lon) arrays plus the grid."""
    raw = {k: load_variable(raw_dir, k) for k in VARIABLES}
    tmpl = raw["t2m"]
    for k, da in raw.items():
        if da.shape != tmpl.shape or not np.allclose(da["latitude"], tmpl["latitude"]) or not np.allclose(da["longitude"], tmpl["longitude"]):
            raise SystemExit(f"{k} is not on the same grid or period as t2m")
    for k in ("pev", "e"):
        if float(raw[k].median()) >= 0:
            raise SystemExit(f"{k}: expected ECMWF's negative-upward sign convention")
    lat, lon = tmpl["latitude"].values, tmpl["longitude"].values
    times = pd.DatetimeIndex(tmpl["time"].values)
    flat = {k: v.transpose("time", "latitude", "longitude").values.reshape(len(times), -1).astype(float) for k, v in raw.items()}
    t_c, td_c = flat["t2m"] - 273.15, flat["d2m"] - 273.15
    es, ea = sat_vapour_pressure_kpa(t_c), sat_vapour_pressure_kpa(td_c)
    root = sum(flat[k] * cm for k, cm in ROOT_CM.items()) / sum(ROOT_CM.values())
    grids = {
        "t2m_c": t_c,
        "vpd_kpa": np.clip(es - ea, 0, None),         # fallback only: step 2 replaces it by the mean of hourly VPD
        "tp_mm_day": flat["tp"] * 1000.0,
        "pev_mm_day": -flat["pev"] * 1000.0,           # evaporation fields x -1 (ECMWF sign convention)
        "e_mm_day": -flat["e"] * 1000.0,
        "ssrd_w_m2": flat["ssrd"] / 86400.0,
        "ro_mm_day": flat["ro"] * 1000.0,
        "swvl_root": root,
        "swvl4": flat["swvl4"],
    }
    return dict(grids=grids, lat=lat, lon=lon, times=times)


def table2_fields(grids: dict, cells: np.ndarray, times: pd.DatetimeIndex, clim: tuple[int, int]) -> dict:
    """Monthly Table 2 predictands at the cells (DataFrames, time x cells), and the cells' CWB3 climatology.

    Accumulated fields are mean daily accumulations in the monthly means, so monthly totals scale by the
    number of days. SPEI3 is the 3-month P - PET in mm, standardised per calendar month on `clim`. VPD here is the
    VPD of the monthly-mean t2m and d2m, a fallback: the monthly mean of hourly VPD (hourly.py, step 2) replaces it."""
    days = times.days_in_month.values[:, None]
    D = {k: v[:, cells] for k, v in grids.items()}
    names = [f"c{c}" for c in cells]
    F = {
        "T": D["t2m_c"], "VPD": D["vpd_kpa"], "P": D["tp_mm_day"] * days,
        "SM_RZ": D["swvl_root"], "SM_DEEP": D["swvl4"], "PET": D["pev_mm_day"] * days,
        "E": D["e_mm_day"] * days, "RS": D["ssrd_w_m2"] * 0.0864, "RO": D["ro_mm_day"] * days,
    }
    F = {k: pd.DataFrame(v, index=times, columns=names) for k, v in F.items()}
    cwb3 = (F["P"] - F["PET"]).rolling(3, min_periods=3).sum()
    mu, sd = monthly_clim(cwb3, clim)
    F["SPEI3"] = standardise(cwb3, mu, sd)
    F["CWB3"] = cwb3
    return dict(fields=F, cwb_clim=(mu, sd))


def monthly_clim(df: pd.DataFrame, clim: tuple[int, int]):
    ref = df.loc[f"{clim[0]}":f"{clim[1]}"]
    return ref.groupby(ref.index.month).mean(), ref.groupby(ref.index.month).std()


def standardise(df: pd.DataFrame, mu: pd.DataFrame, sd: pd.DataFrame) -> pd.DataFrame:
    m = df.index.month
    return (df - mu.reindex(m).values) / sd.reindex(m).values
