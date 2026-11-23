"""Hourly Wet Bulb Globe Temperature (WBGT) at the cells in working hours, in the sun and in the shade, and
its monthly statistics (labour note, Sections 2, 7 and 11).

WBGT is computed with the Liljegren model of the pywbgt package (https://github.com/kwodzicki/pywbgt) from
hourly ERA5: 2 m temperature and dewpoint, surface pressure, 10 m wind and surface solar radiation downwards.

  sun    outdoor WBGT with the solar radiation of ERA5
  shade  the same with solar radiation set to zero: the note's indoor WBGT for workplaces without air
         conditioning

Time. The working window of the note is 7:00 to 17:00 Philippine Time (UTC+8). It is split into the hourly
intervals 7-8, ..., 16-17. ERA5 solar radiation at a time stamp is the energy received over the hour that
ends at the stamp, so each interval uses the radiation of its end stamp, the mean of the two stamps around it
for temperature, dewpoint, pressure and wind speed, and the position of the sun at the middle of the interval.

Monthly statistics per cell and environment (the predictands of the WBGT EOF-CCA):
  P50, P90  median and 90th percentile of WBGT over the working hours of the month (Section 11.1)
  DMAX      mean over the days of the month of the daily maximum over the working hours (Eq. 20)
"""
from __future__ import annotations

import pathlib
import warnings

import numpy as np
import pandas as pd

from .era5 import open_any

ENVS = ("SUN", "SHD")
ENV_NAME = {"SUN": "sun (outdoor)", "SHD": "shade (indoor, no air conditioning)"}
STATS = ("P50", "P90", "DMAX")
METRICS = [f"WBGT{e}_{s}" for e in ENVS for s in STATS]
INTENSITIES = ("heavy", "moderate", "light")
NEEDED = ("t2m", "d2m", "sp", "u10", "v10", "ssrd")


def settings(cfg: dict) -> dict:
    w = dict(cfg.get("wbgt", {}))
    w.setdefault("working_hours", [7, 17])
    w.setdefault("utc_offset_hours", cfg.get("hourly", {}).get("utc_offset_hours", 8))
    w.setdefault("method", "liljegren")
    w.setdefault("percentiles", [50, 90])
    w.setdefault("allow_partial_months", False)
    return w


def interval_ends(S: dict) -> np.ndarray:
    """Local hours at which the hourly working intervals end: 8, ..., 17 for the window 7:00-17:00."""
    h0, h1 = S["working_hours"]
    return np.arange(h0 + 1, h1 + 1)


def read_hourly(path: pathlib.Path) -> dict:
    with open_any(path) as ds:
        tname = "valid_time" if "valid_time" in ds.dims else "time"
        missing = [v for v in NEEDED if v not in ds]
        if missing:
            raise SystemExit(f"{path.name} has no {', '.join(missing)}: WBGT needs {', '.join(NEEDED)}")
        out = {v: ds[v].transpose(tname, "latitude", "longitude").values.astype(np.float32) for v in NEEDED}
        out["time"] = pd.DatetimeIndex(ds[tname].values)
        out["lat"], out["lon"] = ds["latitude"].values, ds["longitude"].values
    return out


def at_cells(d: dict, index: np.ndarray) -> dict:
    """Keep the model cells only: arrays (time, cells)."""
    out = {v: d[v].reshape(len(d["time"]), -1)[:, index] for v in NEEDED}
    out["time"] = d["time"]
    return out


def liljegren(stamps: pd.DatetimeIndex, lat, lon, solar_wm2, pres_pa, t_k, td_k, speed_ms) -> np.ndarray:
    """WBGT (deg C) with pywbgt's Liljegren model. `stamps` are the ends (UTC) of 60-minute averaging periods;
    all other inputs are 1-D arrays of the same length."""
    from metpy.units import units
    from pywbgt import wbgt
    q = units.Quantity
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = wbgt(stamps, np.asarray(lat, float), np.asarray(lon, float), q(np.asarray(solar_wm2, float), "W/m^2"),
                   q(np.asarray(pres_pa, float), "Pa"), q(np.asarray(t_k, float), "K"), q(np.asarray(td_k, float), "K"),
                   q(np.asarray(speed_ms, float), "m/s"), method="liljegren",
                   avg=60.0)             # the sun is placed at the middle of the hour that ends at the stamp
    twbg = out["Twbg"] if isinstance(out, dict) else out[3]
    return np.asarray(twbg.to("degC").magnitude, dtype=np.float32)


def month_wbgt(cur: dict, prev: dict | None, year: int, month: int, S: dict, clat, clon):
    """WBGT of one Philippine month: array (env, day, hour, cell), NaN where an hour is missing, and the days."""
    off = pd.Timedelta(hours=S["utc_offset_hours"])
    ends = interval_ends(S)
    days = pd.date_range(pd.Timestamp(year, month, 1), periods=pd.Timestamp(year, month, 1).days_in_month, freq="D")
    if prev is not None:
        t = prev["time"][-12:].append(cur["time"])
        X = {v: np.concatenate([prev[v][-12:], cur[v]]) for v in NEEDED}
    else:
        t, X = cur["time"], {v: cur[v] for v in NEEDED}
    stamp = pd.DatetimeIndex([d + pd.Timedelta(hours=int(h)) - off for d in days for h in ends])     # UTC, interval ends
    i1 = t.get_indexer(stamp)
    i0 = t.get_indexer(stamp - pd.Timedelta(hours=1))
    ok = i1 >= 0
    i0 = np.where(i0 >= 0, i0, i1)                         # no earlier stamp (start of the record): use the end stamp
    nc = len(clat)
    W = np.full((len(ENVS), len(stamp), nc), np.nan, np.float32)
    if ok.any():
        a, b = i0[ok], i1[ok]
        mean2 = lambda v: 0.5 * (X[v][a] + X[v][b])  # noqa: E731
        speed = 0.5 * (np.hypot(X["u10"][a], X["v10"][a]) + np.hypot(X["u10"][b], X["v10"][b]))
        solar = np.clip(X["ssrd"][b], 0, None) / 3600.0                                              # W/m2, hourly mean
        n = int(ok.sum())
        st = pd.DatetimeIndex(np.repeat(stamp[ok].values, nc))
        la, lo = np.tile(clat, n), np.tile(clon, n)
        args = (mean2("sp").ravel(), mean2("t2m").ravel(), mean2("d2m").ravel(), speed.ravel())
        W[0, ok] = liljegren(st, la, lo, solar.ravel(), *args).reshape(n, nc)
        W[1, ok] = liljegren(st, la, lo, np.zeros(n * nc), *args).reshape(n, nc)
    return W.reshape(len(ENVS), len(days), len(ends), nc), days


def month_stats(W: np.ndarray, S: dict) -> tuple[dict, int]:
    """Monthly statistics per cell from W (env, day, hour, cell); the number of complete days."""
    complete = np.isfinite(W).all(axis=(0, 2, 3))
    nd = int(complete.sum())
    if nd == 0 or (nd < W.shape[1] and not S["allow_partial_months"]):
        return {}, nd
    V = W[:, complete]
    q50, q90 = (float(p) for p in S["percentiles"])
    out = {}
    for k, e in enumerate(ENVS):
        flat = V[k].reshape(-1, V.shape[-1])
        p = np.percentile(flat, [q50, q90], axis=0)
        out[f"WBGT{e}_P50"], out[f"WBGT{e}_P90"] = p[0], p[1]
        out[f"WBGT{e}_DMAX"] = V[k].max(axis=1).mean(axis=0)
    return out, nd


def hothaps(w, intensity: str) -> np.ndarray:
    """Remaining work capacity (fraction, 0.1 to 1) at WBGT `w` (deg C): Eq. 1 of the labour note, from
    pythermalcomfort's work_capacity_hothaps (which returns per cent)."""
    from pythermalcomfort.models import work_capacity_hothaps
    w = np.asarray(w, dtype=float)
    return np.asarray(work_capacity_hothaps(wbgt=w.ravel(), work_intensity=intensity).capacity, dtype=float).reshape(w.shape) / 100.0


def capacities(W: np.ndarray) -> np.ndarray:
    """Mean capacity over the working hours (Eq. 8, equal weights) from W (env, day, hour, cell):
    array (env, intensity, cell). Hours that are NaN are left out."""
    out = np.empty((W.shape[0], len(INTENSITIES), W.shape[-1]))
    for k in range(W.shape[0]):
        flat = W[k].reshape(-1, W.shape[-1])
        good = np.isfinite(flat)
        for j, it in enumerate(INTENSITIES):
            c = hothaps(np.where(good, flat, 20.0), it)
            out[k, j] = np.where(good, c, 0.0).sum(0) / np.maximum(good.sum(0), 1)
    return out


def store_path(folder: pathlib.Path, t: pd.Timestamp) -> pathlib.Path:
    return folder / f"wbgt_{t.year}_{t.month:02d}.npz"


def save_month(p: pathlib.Path, W: np.ndarray, cells: np.ndarray, S: dict) -> None:
    """Hourly WBGT of one month as hundredths of a degree (int16), -32768 = missing."""
    p.parent.mkdir(parents=True, exist_ok=True)
    A = np.where(np.isfinite(W), np.round(W * 100.0), -32768).astype(np.int16)
    np.savez_compressed(p, wbgt=A, cells=np.asarray(cells), ends=interval_ends(S), envs=np.array(ENVS))


def load_month(p: pathlib.Path, cells: np.ndarray | None = None) -> np.ndarray:
    with np.load(p) as z:
        A = z["wbgt"]
        if cells is not None and not np.array_equal(z["cells"], cells):
            raise SystemExit(f"{p.name} was computed for other cells: re-run scripts/helpers/labour_wbgt_hourly.py --overwrite")
    W = A.astype(np.float32) / 100.0
    W[A == -32768] = np.nan
    return W


def cell_index(hlat, hlon, lat, lon, cells):
    from .hourly import _cell_index
    return _cell_index(hlat, hlon, lat, lon, cells)
