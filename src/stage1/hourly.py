"""Monthly statistics of hourly ERA5 at the cells (the hourly rows of Table 2), on Philippine days.

Conventions (Section 3.3.2): hours are UTC and shifted by +8 h before days are formed; hourly tp is the
accumulation over the hour ending at the time stamp, so it belongs to the day of (time - 1 h). A PHT month
therefore needs the last hours of the previous UTC month, which are read from the previous file.

EDD (Table 2) is the extreme degree-days above the threshold T* (hourly.t_star, 35 °C: rice at flowering):
EDD = sum over the hours of the month of max(0, T_h - T*) / 24, in °C·day per month, and NHOT the days whose maximum
exceeds T*. Each threshold of hourly.t_star_extra (30 and 32 °C) adds the same two metrics, named after it (EDD30,
NHOT30, EDD32, NHOT32): at 35 °C EDD is zero in most region-months.

VPD (a monthly row of Table 2) is also computed here, as the mean over every hour of the month of
max(e_s(T_h) - e_s(Td_h), 0), and replaces the VPD of the monthly-mean t2m and d2m (era5.table2_fields) wherever the
hourly fields are loaded. e_s is convex, so VPD from monthly means is biased low, and by more in months with a wide
daily temperature range. VPDMAX is the mean over the days of each day's highest hourly VPD (the afternoon VPD).

Each month is computed once and kept in outputs/shared/work/hourly_metrics/ (one small file per month, with the settings it was
computed with), so step 2 and scripts/helpers/hourly_wbgt_edd.py can be stopped, resumed and re-run as hourly files arrive.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

from .era5 import open_any, sat_vapour_pressure_kpa

METRICS = ["TMAX", "TMIN", "EDD", "NHOT", "NDRY", "LDRY", "N50", "VPDMAX", "VPD"]   # plus EDD<t>, NHOT<t>: metric_names()
VARIABLES = ("t2m", "d2m", "tp")
SETTING_KEYS = ("t_star", "t_star_extra", "dry_mm", "heavy_mm", "utc_offset_hours", "allow_partial_months")


def settings(cfg: dict) -> dict:
    """The settings a month's metrics depend on (a stored month computed with other settings is recomputed)."""
    H = dict(cfg.get("hourly", {}))
    H.setdefault("t_star", 35.0)
    H.setdefault("t_star_extra", [])
    H.setdefault("dry_mm", 1.0)
    H.setdefault("heavy_mm", 50.0)
    H.setdefault("utc_offset_hours", 8)
    H.setdefault("allow_partial_months", False)
    out = {}
    for k in SETTING_KEYS:
        if k == "allow_partial_months":
            out[k] = bool(H[k])
        elif k == "t_star_extra":
            out[k] = sorted(float(t) for t in (H[k] or []))
            bad = [t for t in out[k] if t != int(t) or t == float(H["t_star"])]
            if bad:
                raise SystemExit(f"hourly.t_star_extra: {bad} must be whole degrees and differ from hourly.t_star "
                                 "(each names the variables EDD<t> and NHOT<t>)")
        else:
            out[k] = float(H[k])
    return out


def metric_names(H: dict) -> list[str]:
    """The stored metrics: METRICS, then EDD<t> and NHOT<t> for each threshold t of hourly.t_star_extra."""
    extra = H.get("t_star_extra", [])
    return METRICS + [f"EDD{t:g}" for t in extra] + [f"NHOT{t:g}" for t in extra]


def read_vars(path: pathlib.Path, variables) -> dict:
    """Hourly fields of one file: arrays (time, lat, lon), float32, and time (UTC), lat, lon."""
    with open_any(path) as ds:
        tname = "valid_time" if "valid_time" in ds.dims else "time"
        missing = [v for v in variables if v not in ds]
        if missing:
            raise SystemExit(f"{path.name} has no {', '.join(missing)} (needed: {', '.join(variables)})")
        out = {v: ds[v].transpose(tname, "latitude", "longitude").values.astype(np.float32) for v in variables}
        out["time"] = pd.DatetimeIndex(ds[tname].values)
        out["lat"], out["lon"] = ds["latitude"].values, ds["longitude"].values
    return out


def _read(path: pathlib.Path):
    return read_vars(path, VARIABLES)


def at_cells(d: dict, index: np.ndarray, variables) -> dict:
    """Keep the model cells only: arrays (time, cells)."""
    out = {v: d[v].reshape(len(d["time"]), -1)[:, index] for v in variables}
    out["time"] = d["time"]
    return out


def month_metrics(cur: dict, prev: dict | None, year: int, month: int, H: dict, allow_partial: bool):
    """Metrics (lat x lon arrays) for one PHT month, and the number of complete days used."""
    off = pd.Timedelta(hours=H["utc_offset_hours"])
    keep = 10                                                     # hours taken from the end of the previous file

    def joined(var):
        if prev is None:
            return cur["time"], cur[var]
        return prev["time"][-keep:].append(cur["time"]), np.concatenate([prev[var][-keep:], cur[var]])

    t_inst, T = joined("t2m")
    _, Td = joined("d2m")
    t_acc, P = joined("tp")
    day_inst = (t_inst + off).floor("D")
    day_acc = (t_acc + off - pd.Timedelta(hours=1)).floor("D")
    days = pd.date_range(pd.Timestamp(year, month, 1), periods=pd.Timestamp(year, month, 1).days_in_month, freq="D")
    ok_days = [d for d in days if (day_inst == d).sum() == 24 and (day_acc == d).sum() == 24]
    if len(ok_days) < len(days) and not allow_partial:
        return None, len(ok_days)
    if not ok_days:
        return None, 0
    sel_i = np.concatenate([np.where(day_inst == d)[0] for d in ok_days])
    sel_a = np.concatenate([np.where(day_acc == d)[0] for d in ok_days])
    nd = len(ok_days)
    shp = T.shape[1:]
    Tc = (T[sel_i] - 273.15).reshape(nd, 24, *shp)
    Tdc = (Td[sel_i] - 273.15).reshape(nd, 24, *shp)
    Pd = (np.clip(P[sel_a], 0, None) * 1000.0).reshape(nd, 24, *shp).sum(1)       # mm/day
    vpd = np.clip(sat_vapour_pressure_kpa(Tc) - sat_vapour_pressure_kpa(Tdc), 0, None)
    tmax, tmin = Tc.max(1), Tc.min(1)
    tstar = H["t_star"]
    dry = Pd < H["dry_mm"]
    run = np.zeros(shp, np.int16)
    longest = np.zeros(shp, np.int16)
    for d in range(nd):
        run = (run + 1) * dry[d]
        longest = np.maximum(longest, run)
    scale = len(days) / nd                                          # only differs from 1 with allow_partial
    m = {
        "TMAX": tmax.mean(0), "TMIN": tmin.mean(0),
        "EDD": np.clip(Tc - tstar, 0, None).sum((0, 1)) / 24.0 * scale,
        "NHOT": (tmax > tstar).sum(0) * scale,
        "NDRY": dry.sum(0) * scale,
        "LDRY": longest.astype(float),
        "N50": (Pd >= H["heavy_mm"]).sum(0) * scale,
        "VPDMAX": vpd.max(1).mean(0),
        "VPD": vpd.mean((0, 1)),                                    # monthly mean of hourly VPD
    }
    for t in H.get("t_star_extra", []):                             # lower thresholds (EDD30, NHOT30, ...)
        m[f"EDD{t:g}"] = np.clip(Tc - t, 0, None).sum((0, 1)) / 24.0 * scale
        m[f"NHOT{t:g}"] = (tmax > t).sum(0) * scale
    return m, nd


# ------------------------------------------------------------------ the per-month store
def store_path(folder: pathlib.Path, t: pd.Timestamp) -> pathlib.Path:
    return folder / f"metrics_{t.year}_{t.month:02d}.npz"


def save_month(p: pathlib.Path, m: dict | None, nd: int, cells, H: dict) -> None:
    """One month's metrics at the cells (NaN when the month is incomplete), its complete days and settings."""
    names = metric_names(H)
    vals = np.full((len(names), len(cells)), np.nan)
    if m is not None:
        for i, k in enumerate(names):
            vals[i] = np.asarray(m[k], float).ravel()
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, values=vals, metrics=np.array(names), cells=np.asarray(cells), days=np.int32(nd),
                        status=np.array("ok" if m is not None else "incomplete"),
                        settings=np.array(json.dumps(H, sort_keys=True)))


def month_state(p: pathlib.Path, cells, H: dict) -> str:
    """'absent', 'stale' (other cells or settings: recompute), or the stored status ('ok' / 'incomplete')."""
    if not p.exists():
        return "absent"
    with np.load(p) as z:
        if not np.array_equal(z["cells"], np.asarray(cells)) or list(z["metrics"]) != metric_names(H):
            return "stale"
        if json.loads(str(z["settings"])) != H:
            return "stale"
        return str(z["status"])


def load_month(p: pathlib.Path) -> tuple[np.ndarray, int, str]:
    with np.load(p) as z:
        return z["values"], int(z["days"]), str(z["status"])


def compute_month(cur: dict, prev: dict | None, t: pd.Timestamp, H: dict) -> tuple[dict | None, int]:
    """Metrics of one PHT month from the hourly fields at the cells (arrays (time, cells)) of its UTC month and of
    the month before (None at the start of the record)."""
    return month_metrics(cur, prev, t.year, t.month, H, bool(H["allow_partial_months"]))


def first_month(cfg: dict) -> pd.Timestamp:
    """The first month of the record: the only one computed without the month before it."""
    return pd.Timestamp(int(cfg["period"]["train"][0]), 1, 1)


def compute(cfg: dict, months: pd.DatetimeIndex, folder: pathlib.Path, pattern: str, target_lat, target_lon, cells,
            store: pathlib.Path, overwrite: bool = False, log_every: int = 12) -> dict:
    """Compute and store every month of `months` that is not stored yet (or whose settings changed).

    A month whose previous month has no file yet waits (it is not stored), because its first Philippine day
    starts in the previous UTC month; only the first month of the record is computed without it.
    Returns counts: computed, missing (no hourly file), waiting (previous month missing), todo."""
    H = settings(cfg)
    t0 = first_month(cfg)
    todo = [t for t in months if overwrite or month_state(store_path(store, t), cells, H) in ("absent", "stale")]
    n_done, n_missing, n_wait, prev, prev_key, index = 0, 0, 0, None, None, None
    for i, t in enumerate(todo):
        f = folder / pattern.format(year=t.year, month=t.month)
        if not f.exists():
            n_missing += 1
            prev, prev_key = None, None
            continue
        pk = t - pd.DateOffset(months=1)
        pf = folder / pattern.format(year=pk.year, month=pk.month)
        if t > t0 and prev_key != pk and not pf.exists():
            n_wait += 1
            continue
        raw = _read(f)
        if index is None:
            index = _cell_index(raw["lat"], raw["lon"], target_lat, target_lon, cells)
        cur = at_cells(raw, index, VARIABLES)
        p = prev if prev_key == pk else None
        if p is None and pf.exists():
            p = at_cells(_read(pf), index, VARIABLES)
        m, nd = compute_month(cur, p, t, H)
        save_month(store_path(store, t), m, nd, cells, H)
        n_done += 1
        prev, prev_key = cur, t
        if log_every and (i + 1) % log_every == 0:
            print(f"  {t:%Y-%m}  ({i + 1}/{len(todo)})", flush=True)
    return dict(computed=n_done, missing=n_missing, waiting=n_wait, todo=len(todo))


def assemble(cfg: dict, months: pd.DatetimeIndex, store: pathlib.Path, cells) -> tuple[dict, pd.DataFrame]:
    """Cell metrics for every month from the store: dict metric -> DataFrame (months x cells), NaN where a month
    is missing, incomplete or was computed with other settings; and a log of the days used."""
    H = settings(cfg)
    names = metric_names(H)
    res = {k: np.full((len(months), len(cells)), np.nan) for k in names}
    log = []
    for i, t in enumerate(months):
        p = store_path(store, t)
        state = month_state(p, cells, H)
        if state in ("absent", "stale"):
            log.append({"month": t, "file": p.name, "status": "missing" if state == "absent" else "other settings", "days": 0})
            continue
        vals, nd, status = load_month(p)
        log.append({"month": t, "file": p.name, "status": status, "days": nd})
        if status == "ok":
            for j, k in enumerate(names):
                res[k][i] = vals[j]
    names = [f"c{c}" for c in cells]
    return {k: pd.DataFrame(v, index=months, columns=names) for k, v in res.items()}, pd.DataFrame(log)


def _cell_index(hlat, hlon, lat, lon, cells):
    """Position of each model cell in the hourly grid (nearest hourly cell if it lies outside the file's area)."""
    clat, clon = lat[cells // len(lon)], lon[cells % len(lon)]
    ia = np.abs(hlat[None, :] - clat[:, None]).argmin(1)
    io = np.abs(hlon[None, :] - clon[:, None]).argmin(1)
    off = (np.abs(hlat[ia] - clat) > 1e-6) | (np.abs(hlon[io] - clon) > 1e-6)
    if off.any():
        print(f"  {off.sum()} model cells lie outside the hourly files' area; their nearest hourly cell is used")
    return ia * len(hlon) + io
