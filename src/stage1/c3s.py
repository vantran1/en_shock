"""Scenario path from the C3S multi-system seasonal forecast (ported from climate-mode-navigator's
scripts/update_outlook.py).

For every C3S system, the monthly SST anomalies of the latest forecast (dataset
"seasonal-postprocessed-single-levels", relative to each system's 1993-2016 hindcasts) are turned into RONI
and DMI per ensemble member, on the scale of the indices the model was fitted with:

  RONI = a(month) x (Nino-3.4 anomaly - 20S-20N mean anomaly) + mean observed RONI 1993-2016 (that month)
  DMI  = west box - east box anomaly                         + mean observed DMI 1993-2016 (that month)

and both are averaged over three months centred on each month, with the observed months leading into the
forecast. Every system gets the same number of members. The central path is the median across members.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import tempfile
import zipfile

import numpy as np
import pandas as pd

DATASET = "seasonal-postprocessed-single-levels"
VARIABLE = "sea_surface_temperature_anomaly"
LEADS = 6
REF = (1993, 2016)
# RONI's rescaling of relative Nino-3.4: sd(Nino-3.4) / sd(relative Nino-3.4) by calendar month, 1991-2020, ERSSTv5.
A_RONI = {1: 1.211, 2: 1.232, 3: 1.284, 4: 1.256, 5: 1.165, 6: 1.133,
          7: 1.062, 8: 1.054, 9: 1.127, 10: 1.172, 11: 1.182, 12: 1.203}
BOXES = {"n34": (-5, 5, 190, 240), "trop": (-20, 20, 0, 360), "west": (-10, 10, 50, 70), "east": (-10, 0, 90, 110)}


def default_start(now: dt.datetime | None = None) -> tuple[int, int]:
    """This month once all systems are out (the 10th, 12 UTC), otherwise last month."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.day > 10 or (now.day == 10 and now.hour >= 12):
        return now.year, now.month
    d = now.date().replace(day=1) - dt.timedelta(days=1)
    return d.year, d.month


def latest_available(folder: pathlib.Path, not_after: tuple[int, int] | None = None) -> tuple[int, int] | None:
    """Most recent forecast month with files in `folder` (no later than `not_after`, if given)."""
    import re
    months = set()
    for f in folder.glob("*.nc"):
        m = re.search(r"_(\d{4})(\d{2})\.nc$", f.name)
        if m:
            months.add((int(m.group(1)), int(m.group(2))))
    months = sorted(m for m in months if not_after is None or m <= not_after)
    return months[-1] if months else None


def parse_month(spec, default):
    if spec in (None, "auto"):
        return default
    y, m = (int(v) for v in str(spec).split("-")[:2])
    return y, m


def download(centre: str, system: str, year: int, month: int, target: pathlib.Path) -> None:
    import cdsapi
    request = {
        "originating_centre": centre, "system": str(system),
        "variable": [VARIABLE], "product_type": ["monthly_mean"],
        "year": [str(year)], "month": [f"{month:02d}"],
        "leadtime_month": [str(i) for i in range(1, LEADS + 1)],
        "area": [21, -180, -21, 180],
        "data_format": "netcdf", "download_format": "unarchived",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    cdsapi.Client(quiet=True).retrieve(DATASET, request, str(target))


def file_name(s: dict, year: int, month: int) -> str:
    return f"{s['centre']}_{s['system']}_{year}{month:02d}.nc"


def open_anomalies(path: pathlib.Path):
    """(members x leads x lat x lon) SST anomaly, longitudes 0-360, from a CDS netCDF (or GRIB) file."""
    import xarray as xr
    if zipfile.is_zipfile(path):
        tmp = pathlib.Path(tempfile.mkdtemp())
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.endswith((".nc", ".grib", ".grb"))]
            z.extract(names[0], tmp)
        path = tmp / names[0]
    try:
        ds = xr.open_dataset(path)
    except Exception:  # noqa: BLE001
        ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"time_dims": ("forecastMonth", "time")})
    var = [v for v in ds.data_vars if ds[v].ndim >= 3][0]
    da = ds[var]
    ren = {d: "lat" for d in da.dims if d.lower() in ("lat", "latitude")}
    ren.update({d: "lon" for d in da.dims if d.lower() in ("lon", "longitude")})
    ren.update({d: "member" for d in da.dims if d.lower() in ("number", "realization", "member", "ensemble_member")})
    ren.update({d: "lead" for d in da.dims if d.lower() in ("forecastmonth", "leadtime_month", "lead")})
    da = da.rename(ren)
    for d in list(da.dims):
        if d not in ("member", "lead", "lat", "lon") and da.sizes[d] == 1:
            da = da.isel({d: 0}, drop=True)
    if "member" not in da.dims:
        da = da.expand_dims(member=[0])
    da = da.assign_coords(lon=da["lon"] % 360).sortby("lat").sortby("lon")
    return da.transpose("member", "lead", "lat", "lon").load()


def box_mean(da, box):
    la0, la1, lo0, lo1 = box
    b = da.sel(lat=slice(la0, la1))
    b = b.sel(lon=slice(lo0, lo1)) if lo1 < 360 else b
    w = np.cos(np.deg2rad(b["lat"]))
    return b.weighted(w).mean(("lat", "lon")).values      # (members, leads); land cells are skipped


def offsets(series: pd.Series) -> dict:
    ref = series.loc[f"{REF[0]}":f"{REF[1]}"]
    return {int(m): float(v) for m, v in ref.groupby(ref.index.month).mean().items()}


def centred3(values: dict) -> dict:
    """Centred 3-month means over the months present, needing at least two of the three."""
    out = {}
    if not values:
        return out
    for t in pd.date_range(min(values), max(values), freq="MS"):     # also months between observation and forecast
        win = [values.get(t + pd.DateOffset(months=k)) for k in (-1, 0, 1)]
        win = [v for v in win if v is not None and np.isfinite(v)]
        if len(win) >= 2:
            out[t] = float(np.mean(win))
    return out


def pick(n: int, k: int) -> np.ndarray:
    return np.round(np.linspace(0, n - 1, k)).astype(int) if n >= k else np.arange(k) % n


def members(folder: pathlib.Path, systems: list[dict], year: int, month: int, roni_obs: pd.Series,
            dmi_raw_obs: pd.Series, per_system: int = 10) -> tuple[pd.DataFrame, list[dict]]:
    """Member paths (long table: system, member, date, roni, dmi), smoothed, with the observed lead-in."""
    start = pd.Timestamp(year, month, 1)
    fc = [start + pd.DateOffset(months=k) for k in range(LEADS)]
    off = {"roni": offsets(roni_obs), "dmi": offsets(dmi_raw_obs)}
    rows, used = [], []
    for s in systems:
        f = folder / file_name(s, year, month)
        if not f.exists():
            alt = sorted(folder.glob(f"{s['centre']}_{s['system']}_*.nc"))
            alt = [a for a in alt if a.stem.endswith(f"{year}{month:02d}")]
            if not alt:
                print(f"  {s['label']}: no file {f.name}; skipped")
                continue
            f = alt[0]
        try:
            da = open_anomalies(f)
        except Exception as exc:  # noqa: BLE001
            print(f"  {s['label']}: cannot read {f.name} ({type(exc).__name__}: {str(exc)[:200]}); skipped")
            continue
        leads = min(da.sizes["lead"], LEADS)
        rel = box_mean(da, BOXES["n34"]) - box_mean(da, BOXES["trop"])
        dmi = box_mean(da, BOXES["west"]) - box_mean(da, BOXES["east"])
        ok = np.isfinite(rel[:, :leads]).all(1) & np.isfinite(dmi[:, :leads]).all(1)
        rel, dmi = rel[ok], dmi[ok]
        if not len(rel):
            print(f"  {s['label']}: no complete members; skipped")
            continue
        for k_m, j in enumerate(pick(len(rel), per_system)):
            raw = {"roni": {}, "dmi": {}}
            for k, t in enumerate(fc[:leads]):
                raw["roni"][t] = A_RONI[t.month] * rel[j, k] + off["roni"][t.month]
                raw["dmi"][t] = dmi[j, k] + off["dmi"][t.month]
            for kind, obs in (("roni", roni_obs), ("dmi", dmi_raw_obs)):          # observed months leading in
                for back in range(1, 7):
                    t = start - pd.DateOffset(months=back)
                    if t in obs.index and np.isfinite(obs.loc[t]):
                        raw[kind][t] = float(obs.loc[t])
            sm = {kind: centred3(raw[kind]) for kind in raw}
            for t in sorted(set(sm["roni"]) | set(sm["dmi"])):
                rows.append(dict(system=s["label"], member=k_m, date=t, roni=sm["roni"].get(t, np.nan),
                                 dmi=sm["dmi"].get(t, np.nan), forecast=t >= start))
        used.append(dict(label=s["label"], centre=s["centre"], system=str(s["system"]), members_available=int(len(rel)),
                         members_used=int(per_system), leads=int(leads)))
        print(f"  {s['label']}: {len(rel)} members, {per_system} used")
    if not rows:
        raise SystemExit(f"No C3S file could be read in {folder} for {year}-{month:02d}. "
                         "Run scripts/00_download_inputs.py --c3s first.")
    return pd.DataFrame(rows), used


def central_path(M: pd.DataFrame, how: str = "median") -> pd.DataFrame:
    g = M.groupby("date")
    f = g[["roni", "dmi"]].median() if how == "median" else g[["roni", "dmi"]].mean()
    q = g[["roni", "dmi"]].quantile([0.1, 0.9]).unstack()
    out = f.copy()
    for v in ("roni", "dmi"):
        out[f"{v}_q10"], out[f"{v}_q90"] = q[(v, 0.1)], q[(v, 0.9)]
    out["n_members"] = g.size()
    return out
