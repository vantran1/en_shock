"""Typhoon rainfall by region and quarter: the rain that falls while a tropical cyclone is close.

Alper (27 Nov 2026) asked to test a control for typhoon rainfall as an alternative to dropping
the Luzon quarters of late 2015 (write-up section 2.6): the wind-exposure controls
(hazards.typhoon) do not measure rain, and the typhoon rain over Luzon in Oct-Dec 2015 made the
2016 dry-season drought milder than its RONI implies.

Definition (the usual one in the literature, e.g. Khouakhi et al. 2017, J. Climate): the rain of a
cell on a day counts as typhoon rain if the centre of a tropical cyclone (IBTrACS, any intensity,
interpolated to hours by hazards.typhoon.load_tracks) passes within RADIUS_KM of the cell centre
on that day. Days are UTC days, as in ERA5 and IBTrACS.

Rainfall: ERA5 total precipitation on the 0.25 deg grid of Van's Stage 1 (the 349 kept cells),
hourly or daily. Hourly ERA5 'tp' is the accumulation over the hour ENDING at the time stamp,
so the hour stamped 00 UTC belongs to the previous day; daily totals are built accordingly.
Regional values use Van's cropland weights (v5 Eq. 7, climate.era5.cropland_weights), as the
weather of Stage 2.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from climate.era5 import cropland_weights
from hazards.typhoon import EARTH_R, load_tracks

RADIUS_KM = 500.0


def _dist_km(lat1, lon1, lat2, lon2):
    """Great-circle distance, broadcasting (km)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl, dp = np.radians(lon2 - lon1), p2 - p1
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def cells() -> pd.DataFrame:
    """The weighted cells (latitude, longitude), once each."""
    w = cropland_weights()
    return w[["latitude", "longitude"]].drop_duplicates().reset_index(drop=True)


def cyclone_days(tracks: pd.DataFrame, cell: pd.DataFrame, radius_km: float = RADIUS_KM) -> pd.DataFrame:
    """Cell-days with a cyclone centre within radius_km: columns latitude, longitude, date, n_storms."""
    t = tracks.assign(date=tracks.time.dt.floor("D"))
    lat, lon = cell.latitude.values, cell.longitude.values
    rows = []
    for (sid, day), g in t.groupby(["SID", "date"]):
        d = _dist_km(g.LAT.values[:, None], g.LON.values[:, None], lat[None, :], lon[None, :])
        hit = (d <= radius_km).any(axis=0)
        if hit.any():
            rows.append(pd.DataFrame({"latitude": lat[hit], "longitude": lon[hit], "date": day, "SID": sid}))
    out = pd.concat(rows, ignore_index=True)
    return out.groupby(["latitude", "longitude", "date"]).SID.nunique().rename("n_storms").reset_index()


def daily_precip(files: list[Path], var: str = "tp") -> xr.DataArray:
    """Daily total precipitation (mm) on the 0.25 deg grid, from hourly or daily ERA5 files (m)."""
    parts = []
    for f in sorted(files):
        with xr.open_dataset(f) as ds:
            da = ds[var].load()
        tname = "valid_time" if "valid_time" in da.dims else "time"
        da = da.drop_vars([c for c in ("number", "expver") if c in da.coords]).rename({tname: "time"})
        parts.append(da)
    da = xr.concat(parts, dim="time").sortby("time")
    t = pd.DatetimeIndex(da.time.values)
    if t.duplicated().any():
        raise ValueError(f"duplicated time stamps, e.g. {t[t.duplicated()][:3].tolist()}")
    step = pd.Series(t).diff().median()
    if step == pd.Timedelta("1h"):
        # hour ending at the stamp: shift back one hour so that 00 UTC goes to the previous day
        da = da.assign_coords(time=t - pd.Timedelta("1h")).resample(time="1D").sum(min_count=24)
    elif step != pd.Timedelta("1D"):
        raise ValueError(f"unexpected time step {step}; expected hourly or daily")
    return (da * 1000.0).rename("tp_mm")


def cell_quarter(pr: xr.DataArray, cdays: pd.DataFrame, cell: pd.DataFrame) -> pd.DataFrame:
    """Total and typhoon rain (mm) by cell and quarter."""
    vals = pr.sel(latitude=xr.DataArray(cell.latitude.values, dims="cell"),
                  longitude=xr.DataArray(cell.longitude.values, dims="cell")).values  # day x cell
    days = pd.DatetimeIndex(pr.time.values)
    df = pd.DataFrame(vals, index=days).stack().rename("tp_mm").reset_index()
    df.columns = ["date", "cell", "tp_mm"]
    df = df.join(cell, on="cell")
    df = df.merge(cdays[["latitude", "longitude", "date"]].assign(tc=1),
                  on=["latitude", "longitude", "date"], how="left")
    df["tc_rain_mm"] = df.tp_mm * df.tc.fillna(0)
    df["tc_day"] = df.tc.fillna(0)
    df["period"] = df.date.dt.to_period("Q").astype(str)
    return df.groupby(["latitude", "longitude", "period"])[["tp_mm", "tc_rain_mm", "tc_day"]].sum().reset_index()


def region_quarter(cq: pd.DataFrame) -> pd.DataFrame:
    """Cropland-weighted regional values with the previous quarter (a storm can feed a later harvest)."""
    w = cropland_weights()[["latitude", "longitude", "region_code", "weight"]]
    m = cq.merge(w, on=["latitude", "longitude"])
    cols = ["tp_mm", "tc_rain_mm", "tc_day"]
    r = m[cols].mul(m.weight, axis=0).assign(region_code=m.region_code, period=m.period)
    r = r.groupby(["region_code", "period"])[cols].sum().reset_index().sort_values(["region_code", "period"])
    r = r.rename(columns={"tc_day": "tc_days"})
    r["tc_rain_share"] = r.tc_rain_mm / r.tp_mm
    for c in ("tc_rain_mm", "tc_rain_share", "tc_days"):
        r[f"{c}_lag1"] = r.groupby("region_code")[c].shift(1)
    return r.reset_index(drop=True)


def build(files: list[Path], radius_km: float = RADIUS_KM) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Region x quarter typhoon rain, and the cell-day cyclone mask it is built from."""
    cell = cells()
    cdays = cyclone_days(load_tracks(), cell, radius_km)
    pr = daily_precip(files)
    return region_quarter(cell_quarter(pr, cdays, cell)), cdays
