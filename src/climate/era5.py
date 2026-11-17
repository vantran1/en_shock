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
- ssrd: mean daily accumulation in J m-2 -> mean daily total in MJ m-2 (/ 1e6), as in
  methodology v5 Table 2.
- swvl1-4: volumetric soil water (m3 m-3), layers 0-7, 7-28, 28-100, 100-289 cm; unchanged.
Accumulated fields are stamped 06:00 on the first of the month; all times are set to the
first of the month.
Caution: ERA5 potential evaporation (pev) is known to be unreliable over land; an FAO-56
estimate from t2m, d2m and ssrd is the safer choice for a drought index (SPEI).

Derived (v5 Table 2): vapour pressure deficit es(T) - es(Td) with the Tetens formula
es(T) = 0.6108 exp(17.27 T / (T + 237.3)) kPa, relative humidity 100 es(Td)/es(T), and
root-zone soil moisture = thickness-weighted mean of swvl1-3 (7, 21, 72 cm). They are
computed from the monthly means, cell by cell, before averaging over regions; this
slightly understates the monthly mean of daily VPD (es is convex).

Regional averages (region_weights / regional_mean): cells with land fraction > 0.5
(v5 Section 3.3.2) whose centre lies in one of Van's 16 region polygons
(data/boundaries/phl_16_regions.gpkg); land cells whose centre falls just outside every
polygon (coastline simplification) go to the nearest region within NEAREST_KM. Cells are
weighted by their area (cos latitude) for now; v5 Eq. 7 weights by cropland area, whose
source (ESA WorldCover or CCI) is still to be confirmed.
"""
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from config import local_path

ROOT = Path(__file__).resolve().parents[2]
MASK = ROOT / "data" / "era5" / "era5_land_sea_mask_0.25deg_phl.nc"
REGIONS_FILE = ROOT / "data" / "boundaries" / "phl_16_regions.gpkg"
LAND_MIN = 0.5      # land fraction threshold (v5)
NEAREST_KM = 30.0   # land cells just outside the simplified coastline
METRIC_CRS = 32651  # UTM 51N, for distances
SOIL_LAYERS_CM = {"swvl1": 7, "swvl2": 21, "swvl3": 72}

# long name used in the file names -> (short name in the file, unit after conversion)
VARIABLES = {
    "2m_temperature": ("t2m", "deg C"),
    "2m_dewpoint_temperature": ("d2m", "deg C"),
    "total_precipitation": ("tp", "mm/month"),
    "evaporation": ("e", "mm/month"),
    "potential_evaporation": ("pev", "mm/month"),
    "runoff": ("ro", "mm/month"),
    "surface_solar_radiation_downwards": ("ssrd", "MJ m-2 day-1"),
    "volumetric_soil_water_layer_1": ("swvl1", "m3 m-3"),
    "volumetric_soil_water_layer_2": ("swvl2", "m3 m-3"),
    "volumetric_soil_water_layer_3": ("swvl3", "m3 m-3"),
    "volumetric_soil_water_layer_4": ("swvl4", "m3 m-3"),
}
ACCUMULATED = {"tp", "e", "pev", "ro"}
UPWARD_NEGATIVE = {"e", "pev"}


def era5_dir(directory=None) -> Path:
    """Folder of the ERA5 files: the argument if given, else era5_monthly_dir in
    config/paths.toml (read by config.local_path)."""
    d = Path(directory).expanduser() if directory else local_path("era5_monthly_dir")
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
        return da / 1e6
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


def saturation_vp(t_c):
    """Saturation vapour pressure (kPa), Tetens; t_c in deg C."""
    return 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))


def vpd_kpa(t2m_c, d2m_c):
    return saturation_vp(t2m_c) - saturation_vp(d2m_c)


def rh_pct(t2m_c, d2m_c):
    return 100 * saturation_vp(d2m_c) / saturation_vp(t2m_c)


def root_zone(sw1, sw2, sw3):
    w = SOIL_LAYERS_CM
    return (sw1 * w["swvl1"] + sw2 * w["swvl2"] + sw3 * w["swvl3"]) / sum(w.values())


def region_weights(regions_file=REGIONS_FILE) -> pd.DataFrame:
    """One row per ERA5 land cell used: latitude, longitude, land fraction, region code,
    how it was assigned ('inside' or 'nearest', with the distance) and its weight within
    the region (cell area, cos latitude)."""
    lsm = land_sea_mask()
    cells = lsm.to_dataframe(name="lsm").reset_index()
    cells = cells[cells["lsm"] > LAND_MIN].copy()
    pts = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells.longitude, cells.latitude),
                           crs=4326)
    reg = gpd.read_file(regions_file)[["code", "geometry"]]
    inside = gpd.sjoin(pts, reg, predicate="within", how="left")
    inside = inside[~inside.index.duplicated()]
    out = inside.drop(columns=["index_right"]).rename(columns={"code": "region_code"})
    out["assigned"] = np.where(out["region_code"].notna(), "inside", "")
    out["distance_km"] = 0.0
    miss = out["region_code"].isna()
    if miss.any():
        near = gpd.sjoin_nearest(pts[miss].to_crs(METRIC_CRS), reg.to_crs(METRIC_CRS),
                                 how="left", distance_col="distance_km")
        near = near[~near.index.duplicated()]
        near["distance_km"] /= 1000
        ok = near["distance_km"] <= NEAREST_KM
        out.loc[near.index[ok], "region_code"] = near.loc[ok, "code"]
        out.loc[near.index[ok], "assigned"] = "nearest"
        out.loc[near.index, "distance_km"] = near["distance_km"]
    out = out[out["region_code"].notna()].copy()
    out["area_w"] = np.cos(np.radians(out["latitude"]))
    out["weight"] = out["area_w"] / out.groupby("region_code")["area_w"].transform("sum")
    return pd.DataFrame(out.drop(columns=["geometry", "area_w"]))


CROPLAND_WEIGHTS = ROOT / "data" / "reference" / "van" / "cropland_weights" / "cropland_weights_16regions.csv"


def cropland_weights(path=CROPLAND_WEIGHTS) -> pd.DataFrame:
    """v5 Eq. 7: Van's cropland weights (ESA CCI 2022 cropland share of each kept ERA5 cell in
    the region; kept cells = land fraction >= 0.5; the cropland of islands without a kept
    cell moved to the nearest kept cell, which may lie in another region). Same columns as
    region_weights: latitude, longitude, lsm, region_code, assigned ('own': the cell holds
    cropland of its own area in the region; 'island': only cropland moved there from
    islands), reassigned_share (part of the cell's weight that came from islands), weight."""
    w = pd.read_csv(path)
    w = w[w["w_cropland"] > 0]
    lsm = land_sea_mask().to_dataframe(name="lsm").reset_index()
    w = w.merge(lsm, left_on=["lat", "lon"], right_on=["latitude", "longitude"], how="left",
                validate="m:1")
    if w["lsm"].isna().any() or (w["lsm"] < LAND_MIN).any():
        raise ValueError("a weighted cell is not an ERA5 land cell")
    own = w["cropland_km2"] - w["cropland_reassigned_km2"]
    out = pd.DataFrame({"latitude": w["lat"], "longitude": w["lon"], "lsm": w["lsm"],
                        "region_code": w["code"],
                        "assigned": np.where(own > 1e-9, "own", "island"),
                        "reassigned_share": w["cropland_reassigned_km2"] / w["cropland_km2"],
                        "weight": w["w_cropland"]})
    s = out.groupby("region_code")["weight"].sum()
    if not np.allclose(s, 1):
        raise ValueError(f"cropland weights do not sum to 1: {s[~np.isclose(s, 1)]}")
    return out.reset_index(drop=True)


def regional_mean(da: xr.DataArray, w: pd.DataFrame) -> pd.DataFrame:
    """Weighted regional mean of a (time, latitude, longitude) field -> region x month."""
    vals = da.sel(latitude=xr.DataArray(w["latitude"].values, dims="cell"),
                  longitude=xr.DataArray(w["longitude"].values, dims="cell")).values  # time x cell
    wr = pd.get_dummies(w["region_code"]).mul(w["weight"].values, axis=0)        # cell x region
    out = pd.DataFrame(vals @ wr.values, index=pd.DatetimeIndex(da.time.values), columns=wr.columns)
    return out
