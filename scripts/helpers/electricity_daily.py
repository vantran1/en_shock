#!/usr/bin/env python3
"""Step 7 helper, electricity: daily cooling degree days and temperatures by grid (electricity note, Eqs. 1-3).

Stages (each can be run on its own with --only; every stage reads what the earlier ones wrote):
  store     the hourly 2 m temperature of every model cell in Philippine Time (PHT), one file per month in
            outputs/shared/work/electricity_hourly/. This is the only stage that reads the hourly ERA5 files, and
            each file is read once; it resumes where it stopped (--max-minutes ends it cleanly).
  observed  outputs/electricity/observed_daily_3grids.csv: by PHT day and grid, CDD at the base temperatures of
            sections.electricity.daily.cdd_bases (22-26 °C): Eq. 1 for each cell, CDD = (1/24) sum over the hours of
            max(0, T_h - T*), then Eq. 2, the population-weighted mean over the grid's cells (NCR included); and the
            population-weighted mean of each cell's daily mean, maximum and minimum temperature.
            outputs/electricity/observed_hourly_3grids.csv.gz: the population-weighted hourly temperature by grid.
  simulate  the same by draw and run (scenario, neutral) for the forecast path and the scenarios (--paths). Eq. 3:
            each cell's observed hours in the draw's historical month, shifted by the change in its region's monthly
            temperature that Stage 1 gives, i.e. the response to the path in today's climate (t*) minus the fitted
            value of the historical month (its own RONI and trend). One historical month serves every draw and path
            that uses it, so each stored month is read once per path.
            With sections.electricity.daily.shift: maxmin (Section 3.2 of the note), the daily maximum and minimum
            are shifted by Stage 1's TMAX and TMIN responses instead, and the hours in between in proportion.
  check     Section 3.2 of the note: outputs/electricity/check_section32_*.csv. (1) Stage 1's responses of TMAX and
            TMIN against that of T (population weights, by grid). (2) Hot days: Stage 1's response of NHOT, NHOT32 and
            NHOT30 against the response that a single shift of the month by Stage 1's T implies for the same draws
            (agricultural regions and weights, where NHOT is modelled).

  python scripts/helpers/electricity_daily.py                                 # all stages, forecast + scenarios
  python scripts/helpers/electricity_daily.py --only store --max-minutes 2.5   # part of the store; run it again to go on
  python scripts/helpers/electricity_daily.py --only simulate --paths forecast 1997-98
  python scripts/helpers/electricity_daily.py --only simulate --with-dmi       # also the RONI + DMI models

Paths: forecast (outputs/electricity/), forecast_dmi (outputs/shared/variants/roni_dmi/electricity/), and the
scenarios 1997-98, 2015-16, 2023-24, unit (outputs/shared/scenarios/<name>/roni/, and roni_dmi/ with --with-dmi).
Output columns of the simulated tables: draw, block_year, date (the path's day), hist_date (the day of the historical
month it comes from), grid, then <variable>_scenario and <variable>_neutral. Next to each, shift_by_block_3grids.csv
holds Eq. 3's shift by grid, draw and month (population-weighted mean of the regions' shifts): with the single shift,
a simulated hourly grid temperature is the observed one of the historical hour plus this shift. A path month keeps the days of its
historical month that exist in it: a 29 February of the historical year is dropped in a common year, and a leap-year
path February has 28 days when its historical year is a common year.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import hourly as HR  # noqa: E402

GRIDS = ["Luzon", "Visayas", "Mindanao"]
STAGES = ("store", "observed", "simulate", "check")
SCENARIOS = ("1997-98", "2015-16", "2023-24", "unit")
MISSING = np.int16(-32768)
OFFSET = pd.Timedelta(hours=8)                     # PHT = UTC + 8


def write_csv(df: pd.DataFrame, p: pathlib.Path) -> None:
    """As stage1.outputs.write_csv (same number format), without its geopandas import."""
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, float_format="%.6g", date_format="%Y-%m-%d")
    print(f"  wrote {p.relative_to(p.parents[2]) if len(p.parents) > 2 else p} ({len(df):,} rows)")


# ---------------------------------------------------------------- settings and weights
def settings(cfg: dict) -> dict:
    e = dict(cfg["sections"]["electricity"].get("daily") or {})
    bases = [float(b) for b in e.get("cdd_bases", [22, 23, 24, 25, 26])]
    shift = str(e.get("shift", "mean"))
    if shift not in ("mean", "maxmin"):
        raise SystemExit(f"sections.electricity.daily.shift must be mean or maxmin, not {shift}")
    return dict(bases=bases, shift=shift)


def value_names(bases) -> list[str]:
    return [f"CDD{b:g}" for b in bases] + ["TMEAN", "TMAX", "TMIN"]


def pairs(cfg: dict) -> pd.DataFrame:
    """Cell x region pairs of the electricity weights (outputs/electricity/cell_weights_17regions.csv), with the
    population weight of each pair in its grid (MIMAROPA follows sections.electricity.mimaropa_in_luzon_grid)."""
    w = pd.read_csv(C.out_in(cfg, "electricity", "cell_weights_17regions.csv"))
    w = w[w["w_population_in_grid"] > 0].reset_index(drop=True)
    return w


def store_cells(cfg: dict) -> pd.DataFrame:
    w = pd.read_csv(C.out_in(cfg, "electricity", "cell_weights_17regions.csv"))
    return w.drop_duplicates("cell")[["cell", "lat", "lon"]].sort_values("cell").reset_index(drop=True)


# ---------------------------------------------------------------- stage 1: the PHT hourly store
def store_dir(cfg: dict) -> pathlib.Path:
    d = C.path(cfg, "work_dir") / "electricity_hourly"
    d.mkdir(parents=True, exist_ok=True)
    return d


def store_file(cfg: dict, t: pd.Timestamp) -> pathlib.Path:
    return store_dir(cfg) / f"T_{t:%Y_%m}.npz"


def hourly_months(cfg: dict) -> list[pd.Timestamp]:
    folder = C.path(cfg, "era5_hourly_dir")
    out = []
    for f in sorted(folder.glob("era5_*_*.nc")):
        try:
            y, m = int(f.stem[5:9]), int(f.stem[10:12])
        except ValueError:
            continue
        out.append(pd.Timestamp(y, m, 1))
    return out


def read_cells(path: pathlib.Path, cells: pd.DataFrame, index=None):
    """2 m temperature (°C) of the store cells, (time, cells), with the UTC times; and the cell index."""
    raw = HR.read_vars(path, ("t2m",))
    if index is None:
        ia = np.abs(raw["lat"][None, :] - cells["lat"].to_numpy()[:, None]).argmin(1)
        io = np.abs(raw["lon"][None, :] - cells["lon"].to_numpy()[:, None]).argmin(1)
        index = ia * len(raw["lon"]) + io
    T = raw["t2m"].reshape(len(raw["time"]), -1)[:, index] - 273.15
    return pd.DatetimeIndex(raw["time"]), T.astype(np.float32), index


def pht_month(t: pd.Timestamp, parts) -> tuple[np.ndarray, int]:
    """Hours of PHT month t from (times, values) parts in UTC; (cells, hours) float32 with NaN where an hour is
    missing (the first 8 hours of the month when the previous UTC file is not there), and the hours missing."""
    hours = pd.date_range(t, t + pd.DateOffset(months=1), freq="h", inclusive="left")
    times = pd.DatetimeIndex(np.concatenate([p[0].values for p in parts])) + OFFSET
    vals = np.concatenate([p[1] for p in parts], axis=0)
    pos = pd.Series(np.arange(len(times)), index=times)
    pos = pos[~pos.index.duplicated(keep="last")].reindex(hours)
    out = np.full((vals.shape[1], len(hours)), np.nan, np.float32)
    ok = pos.notna().to_numpy()
    out[:, ok] = vals[pos.to_numpy()[ok].astype(int)].T
    return out, int((~ok).sum())


def stage_store(cfg: dict, max_minutes: float | None, overwrite: bool) -> bool:
    """Returns True when every month with an hourly file is stored."""
    cells = store_cells(cfg)
    folder, pattern = C.path(cfg, "era5_hourly_dir"), cfg["paths"]["hourly_pattern"]
    months = hourly_months(cfg)
    if not months:
        raise SystemExit(f"no hourly files in {folder}")
    have = set(months)
    todo = [t for t in months if overwrite or not store_file(cfg, t).exists()]
    print(f"store: {len(months)} hourly months ({months[0]:%Y-%m} to {months[-1]:%Y-%m}), {len(todo)} to do, "
          f"{len(cells)} cells -> {store_dir(cfg)}")
    t0, index, cache = time.time(), None, {}
    for i, t in enumerate(todo):
        if max_minutes and time.time() - t0 > 60 * max_minutes:
            print(f"  stopped after {i} months (--max-minutes); run again to go on")
            return False
        pk = t - pd.DateOffset(months=1)
        parts = []
        if pk in have:
            if pk not in cache:
                tt, vv, index = read_cells(folder / pattern.format(year=pk.year, month=pk.month), cells, index)
                cache[pk] = (tt[-24:], vv[-24:])
            parts.append(cache[pk])
        tt, vv, index = read_cells(folder / pattern.format(year=t.year, month=t.month), cells, index)
        parts.append((tt, vv))
        cache = {t: (tt[-24:], vv[-24:])}
        T, n_missing = pht_month(t, parts)
        q = np.where(np.isfinite(T), np.round(T * 100), MISSING).astype(np.int16)
        np.savez_compressed(store_file(cfg, t), T=q, cells=cells["cell"].to_numpy(), month=f"{t:%Y-%m}",
                            hours_missing=n_missing)
        if (i + 1) % 24 == 0 or i + 1 == len(todo):
            print(f"  {t:%Y-%m}  ({i + 1}/{len(todo)}, {time.time() - t0:.0f}s)", flush=True)
    return True


def load_month(cfg: dict, t: pd.Timestamp, cell_ids: np.ndarray) -> np.ndarray | None:
    """Stored month t as (cells, days, 24) °C float32, in the order of cell_ids; None if not stored."""
    f = store_file(cfg, t)
    if not f.exists():
        return None
    z = np.load(f)
    q, cells = z["T"], z["cells"]
    pos = pd.Series(np.arange(len(cells)), index=cells).reindex(cell_ids).to_numpy()
    T = q[pos].astype(np.float32) / 100.0
    T[q[pos] == MISSING] = np.nan
    return T.reshape(len(cell_ids), -1, 24)


# ---------------------------------------------------------------- daily values
def daily_values(T: np.ndarray, bases) -> np.ndarray:
    """(..., days, 24) hourly °C -> (..., days, n_values): CDD at each base (Eq. 1), daily mean, max and min.
    A day with a missing hour is NaN."""
    out = [np.clip(T - b, 0, None).mean(-1) for b in bases]
    out += [T.mean(-1), T.max(-1), T.min(-1)]
    return np.stack(out, -1)


def grid_matrix(p: pd.DataFrame, col: str = "w_population_in_grid") -> np.ndarray:
    """(pairs, 3) population weights of each pair in its grid (Eq. 2)."""
    G = np.zeros((len(p), len(GRIDS)))
    for j, g in enumerate(GRIDS):
        m = (p["grid"] == g).to_numpy()
        G[m, j] = p.loc[m, col].to_numpy()
    return G


# ---------------------------------------------------------------- stage 2: observed
def stage_observed(cfg: dict, S: dict) -> None:
    p = pairs(cfg)
    cell_ids = p["cell"].to_numpy()
    G = grid_matrix(p)
    months = sorted(pd.Timestamp(f.stem[2:6] + "-" + f.stem[7:9] + "-01") for f in store_dir(cfg).glob("T_*.npz"))
    if not months:
        raise SystemExit("nothing stored yet: run --only store first")
    names = value_names(S["bases"])
    daily, hourly = [], []
    for t in months:
        T = load_month(cfg, t, cell_ids)                         # (pairs, days, 24)
        V = daily_values(T, S["bases"])                          # (pairs, days, n)
        g = np.einsum("pdn,pg->gdn", V, G)                       # (3, days, n)
        days = pd.date_range(t, periods=T.shape[1], freq="D")
        for j, grid in enumerate(GRIDS):
            df = pd.DataFrame(g[j], columns=names)
            df.insert(0, "date", days)
            df.insert(1, "grid", grid)
            daily.append(df)
        h = np.einsum("ph,pg->hg", T.reshape(len(p), -1), G)     # (hours, 3)
        hourly.append(pd.DataFrame(h, columns=GRIDS, index=pd.date_range(t, periods=h.shape[0], freq="h")))
    d = pd.concat(daily, ignore_index=True).dropna(subset=names)
    d["grid"] = pd.Categorical(d["grid"], GRIDS, ordered=True)
    d = d.sort_values(["date", "grid"]).reset_index(drop=True)
    d["grid"] = d["grid"].astype(str)
    write_csv(d.round(4), C.out(cfg, "electricity", "observed_daily_3grids.csv"))
    h = pd.concat(hourly).dropna()
    h = h.round(3).reset_index(names="datetime_pht")
    h["datetime_pht"] = h["datetime_pht"].dt.strftime("%Y-%m-%d %H:%M")
    write_csv(h, C.out(cfg, "electricity", "observed_hourly_3grids.csv.gz"))
    print(f"observed: {d['date'].min():%Y-%m-%d} to {d['date'].max():%Y-%m-%d} ({d['date'].nunique():,} days), "
          f"hourly {h['datetime_pht'].iloc[0]} to {h['datetime_pht'].iloc[-1]} PHT")


# ---------------------------------------------------------------- stage 3: simulate
def path_specs(with_dmi: bool, which=None) -> list[dict]:
    specs = [dict(name="forecast", variant=None)]
    if with_dmi:
        specs.append(dict(name="forecast_dmi", variant="roni_dmi"))
    for s in SCENARIOS:
        v = "scen_" + s.replace("-", "_")
        specs.append(dict(name=s, variant=v, scenario=s, model="roni"))
        if with_dmi:
            specs.append(dict(name=s + "_dmi", variant=v + "_dmi", scenario=s, model="roni_dmi"))
    if which:
        want = set(which)
        specs = [s for s in specs if s["name"] in want]
        if not specs:
            raise SystemExit(f"--paths: none of {sorted(want)} (forecast, forecast_dmi, {', '.join(SCENARIOS)}, "
                             "and <scenario>_dmi)")
    return specs


def spec_cfg(cfg_main: dict, spec: dict) -> dict:
    return C.load(cfg_main.get("_config_path"), spec["variant"]) if spec["variant"] else cfg_main


def models_out(cfg_v: dict, *parts) -> pathlib.Path:
    """An output of the run whose models a variant uses (main, or the variant named by models_from)."""
    mf = cfg_v.get("_models_from")
    root = C.path(cfg_v, "outputs_dir")
    return root.joinpath("shared", "variants", mf, *parts) if mf else C._main_out(cfg_v, parts)


def out_path(cfg_v: dict, spec: dict, name: str) -> pathlib.Path:
    if spec.get("scenario"):
        p = C.path(cfg_v, "outputs_dir") / "shared" / "scenarios" / spec["scenario"] / spec["model"] / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return C.out(cfg_v, "electricity", name)


def shift_table(cfg_v: dict, section: str = "electricity", variables=("T", "TMAX", "TMIN")) -> pd.DataFrame:
    """Eq. 3's shift for every draw, path month and region: Stage 1's response to the path today (scenario and
    neutral, residual 0) minus the fitted value of the draw's historical month.
    electricity: population weights, 17 regions; agriculture: cropland weights, 16 regions (for the check)."""
    if section == "electricity":
        pr = pd.read_csv(C.out(cfg_v, "electricity", "path_response_17regions.csv"), parse_dates=["date"])
        hf = models_out(cfg_v, "electricity", "hist_fitted_17regions.csv")
    else:
        det = pd.read_csv(C.out(cfg_v, "agriculture", "deterministic_monthly_16regions.csv"), parse_dates=["date"])
        det = det[["path", "date", "code"] + list(variables)]
        pr = det.pivot_table(index=["date", "code"], columns="path", values=list(variables))
        pr.columns = [f"{v}_{p}" for v, p in pr.columns]
        pr = pr.reset_index()
        hf = models_out(cfg_v, "agriculture", "hist_fitted_16regions.csv")
    H = pd.read_csv(hf, parse_dates=["date"], usecols=lambda c: c in ("date", "code") or
                    any(c == f"{v}_fitted" for v in variables))
    blocks = pd.read_csv(C.out_in(cfg_v, "shared", "blocks.csv"))
    path = pd.read_csv(C.out_in(cfg_v, "shared", "path.csv"), parse_dates=["date"])
    dates = pd.DatetimeIndex(path.loc[~path["lead_in"].astype(bool), "date"])
    pr = pr[pr["date"].isin(dates)]
    rows = []
    for _, b in blocks.iterrows():
        x = pr.copy()
        x["draw"], x["block_year"] = int(b["draw"]), int(b["block_year"])
        x["hist_date"] = [pd.Timestamp(d.year - int(b["shift_years"]), d.month, 1) for d in x["date"]]
        rows.append(x)
    x = pd.concat(rows, ignore_index=True).merge(H.rename(columns={"date": "hist_date"}), on=["hist_date", "code"],
                                                 how="left")
    for v in variables:
        if x[f"{v}_fitted"].isna().any():
            miss = x.loc[x[f"{v}_fitted"].isna(), "hist_date"].dt.strftime("%Y-%m").unique()[:5]
            raise SystemExit(f"{hf}: no fitted {v} for {', '.join(miss)}: re-run step 3 of that model")
        for run in ("scenario", "neutral"):
            x[f"{v}_shift_{run}"] = x[f"{v}_{run}"] - x[f"{v}_fitted"]
    keep = ["draw", "block_year", "date", "hist_date", "code"] + [f"{v}_shift_{r}" for v in variables
                                                                  for r in ("scenario", "neutral")]
    return x[keep].sort_values(["draw", "date", "code"]).reset_index(drop=True)


def grid_shifts(sh: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Eq. 3's shift by grid: the population-weighted mean of the regions' shifts. With the single shift, the
    simulated hourly temperature of a grid is its observed hourly temperature in the historical month
    (observed_hourly_3grids.csv.gz) plus this shift (Version 2 of the note)."""
    wr = p.groupby(["grid", "code"], as_index=False)["w_population_in_grid"].sum()
    x = sh.merge(wr, on="code")
    cols = [c for c in sh.columns if "_shift_" in c]
    x[cols] = x[cols].mul(x["w_population_in_grid"], axis=0)
    g = x.groupby(["draw", "block_year", "date", "hist_date", "grid"], as_index=False)[cols].sum()
    g["grid"] = pd.Categorical(g["grid"], GRIDS, ordered=True)
    g = g.sort_values(["draw", "date", "grid"]).reset_index(drop=True)
    g["grid"] = g["grid"].astype(str)
    return g


def shifted(T: np.ndarray, sT: np.ndarray, sX: np.ndarray, sN: np.ndarray, mode: str) -> np.ndarray:
    """T (pairs, days, 24) shifted by run-and-pair shifts (K, pairs): mean = by T's shift; maxmin = the daily maximum
    by sX, the minimum by sN and the hours in between in proportion to where they lie in the day's range."""
    if mode == "mean":
        return T[None] + sT[:, :, None, None]
    lo, hi = np.nanmin(T, -1, keepdims=True), np.nanmax(T, -1, keepdims=True)
    rng = hi - lo
    frac = np.divide(T - lo, rng, out=np.full_like(T, 0.5), where=rng > 1e-6)
    return T[None] + sN[:, :, None, None] + (sX - sN)[:, :, None, None] * frac[None]


def simulate_one(cfg_main: dict, spec: dict, S: dict, p: pd.DataFrame, G: np.ndarray) -> pd.DataFrame:
    cfg_v = spec_cfg(cfg_main, spec)
    sh = shift_table(cfg_v)
    write_csv(grid_shifts(sh, p).round(5), out_path(cfg_v, spec, "shift_by_block_3grids.csv"))
    codes = p["code"].to_numpy()
    cell_ids = p["cell"].to_numpy()
    names = value_names(S["bases"])
    nd = sh["draw"].nunique()
    print(f"  {spec['name']}: {nd} draws, {sh['date'].min():%Y-%m} to {sh['date'].max():%Y-%m}, "
          f"{sh['hist_date'].nunique()} historical months", flush=True)
    # one row per (draw, path month); pair shifts looked up by region code
    piv = {}
    for v in ("T", "TMAX", "TMIN"):
        for run in ("scenario", "neutral"):
            piv[(v, run)] = sh.pivot_table(index=["draw", "block_year", "date", "hist_date"], columns="code",
                                           values=f"{v}_shift_{run}")
    keys = piv[("T", "scenario")].index.to_frame(index=False)
    cols = {k: [] for k in ("draw", "block_year", "date", "hist_date", "grid")}
    vals = []
    for hm, grp in keys.groupby("hist_date"):
        T = load_month(cfg_main, hm, cell_ids)
        if T is None:
            raise SystemExit(f"historical month {hm:%Y-%m} is not stored: run --only store")
        idx = pd.MultiIndex.from_frame(grp)
        shifts = {k: df.loc[idx, codes].to_numpy(float) for k, df in piv.items()}   # (K, pairs)
        res = []
        for run in ("scenario", "neutral"):
            Ts = shifted(T, shifts[("T", run)], shifts[("TMAX", run)], shifts[("TMIN", run)], S["shift"])
            res.append(np.einsum("kpdn,pg->kgdn", daily_values(Ts, S["bases"]), G))     # (K, 3, days, n)
        both = np.concatenate(res, -1)                                                 # (K, 3, days, 2n)
        for k, r in enumerate(grp.itertuples(index=False)):
            n_days = min(T.shape[1], r.date.days_in_month)
            days = pd.date_range(r.date, periods=n_days, freq="D").values
            hdays = pd.date_range(hm, periods=n_days, freq="D").values
            for j, g in enumerate(GRIDS):
                cols["draw"].append(np.full(n_days, r.draw)); cols["block_year"].append(np.full(n_days, r.block_year))
                cols["date"].append(days); cols["hist_date"].append(hdays); cols["grid"].append(np.full(n_days, g))
                vals.append(both[k, j, :n_days])
    d = pd.DataFrame({k: np.concatenate(v) for k, v in cols.items()})
    V = np.concatenate(vals)
    for i, nm in enumerate([f"{n}_{run}" for run in ("scenario", "neutral") for n in names]):
        d[nm] = V[:, i]
    d["grid"] = pd.Categorical(d["grid"], GRIDS, ordered=True)
    d = d.sort_values(["draw", "date", "grid"]).reset_index(drop=True)
    d["grid"] = d["grid"].astype(str)
    f = out_path(cfg_v, spec, "simulated_daily_3grids.csv.gz")
    write_csv(d.round(4), f)
    return d


def stage_simulate(cfg: dict, S: dict, which, with_dmi: bool) -> None:
    p = pairs(cfg)
    G = grid_matrix(p)
    print(f"simulate: shift = {S['shift']}, CDD bases {', '.join(f'{b:g}' for b in S['bases'])} °C")
    for spec in path_specs(with_dmi, which):
        with C.Timer(spec["name"]):
            d = simulate_one(cfg, spec, S, p, G)
        eff = d.groupby([d["date"].dt.to_period("Q"), "grid"])[[c for c in d.columns if c.endswith("_scenario")]].mean()
        neu = d.groupby([d["date"].dt.to_period("Q"), "grid"])[[c for c in d.columns if c.endswith("_neutral")]].mean()
        diff = pd.DataFrame(eff.to_numpy() - neu.to_numpy(), index=eff.index,
                            columns=[c.removesuffix("_scenario") for c in eff.columns])
        cols = [c for c in (f"CDD{S['bases'][len(S['bases']) // 2]:g}", "TMEAN", "TMAX", "TMIN") if c in diff]
        print(f"    scenario minus neutral, mean over draws and days (by quarter):\n"
              + diff[cols].unstack("grid").round(3).to_string().replace("\n", "\n    "))


# ---------------------------------------------------------------- stage 4: check (Section 3.2)
def stage_check(cfg: dict, which, with_dmi: bool) -> None:
    specs = path_specs(with_dmi, which)
    # (1) TMAX and TMIN against T, population weights, by grid
    rg = pd.read_csv(C.out_in(cfg, "electricity", "region_grid_map.csv"))
    rg = rg[rg["in_grid_weights"]]
    rows = []
    for spec in specs:
        cfg_v = spec_cfg(cfg, spec)
        pr = pd.read_csv(C.out(cfg_v, "electricity", "path_response_17regions.csv"), parse_dates=["date"])
        pr = pr.merge(rg[["code", "population_in_land_cells"]], on="code")
        for v in ("T", "TMAX", "TMIN"):
            pr[f"d{v}"] = pr[f"{v}_scenario"] - pr[f"{v}_neutral"]
        for (d, g), x in pr.groupby(["date", "grid"]):
            w = x["population_in_land_cells"] / x["population_in_land_cells"].sum()
            rows.append(dict(path=spec["name"], date=d, grid=g, **{f"d{v}": float((w * x[f"d{v}"]).sum())
                                                                     for v in ("T", "TMAX", "TMIN")}))
    a = pd.DataFrame(rows)
    write_csv(a.round(4), C.out(cfg, "electricity", "check_section32_tmax_tmin.csv"))
    big = a[a["dT"].abs() >= 0.1]
    print("Section 3.2 (1): Stage 1's responses, population weights, months with |dT| >= 0.1 °C")
    s = big.groupby(["path", "grid"]).apply(lambda x: pd.Series({
        "months": len(x), "mean dT": x["dT"].mean(), "mean dTMAX": x["dTMAX"].mean(), "mean dTMIN": x["dTMIN"].mean(),
        "slope dTMAX on dT": np.polyfit(x["dT"], x["dTMAX"], 1)[0] if len(x) > 2 else np.nan,
        "slope dTMIN on dT": np.polyfit(x["dT"], x["dTMIN"], 1)[0] if len(x) > 2 else np.nan}), include_groups=False)
    print(s.round(2).to_string())
    write_csv(s.round(4).reset_index(), C.out(cfg, "electricity", "check_section32_tmax_tmin_summary.csv"))

    # (2) hot days: Stage 1's NHOT responses against those implied by one shift of the month by T (or by TMAX)
    thr = [float(cfg.get("hourly", {}).get("t_star", 35.0))] + [float(t) for t in cfg.get("hourly", {}).get("t_star_extra", [])]
    nh = {t: ("NHOT" if t == thr[0] else f"NHOT{t:g}") for t in thr}
    w = pd.read_csv(C.out_in(cfg, "agriculture", "cell_weights_16regions.csv"))
    w = w[w["w_cropland"] > 0].reset_index(drop=True)
    cell_ids, codes = w["cell"].to_numpy(), w["code"].to_numpy()
    R = sorted(w["code"].unique())
    Wr = np.zeros((len(w), len(R)))
    for j, r in enumerate(R):
        m = codes == r
        Wr[m, j] = w.loc[m, "w_cropland"].to_numpy()
    rows = []
    for spec in specs:
        cfg_v = spec_cfg(cfg, spec)
        sh = shift_table(cfg_v, "agriculture", ("T", "TMAX"))
        eff = pd.read_csv(out_path(cfg_v, spec, "effects_16regions.csv") if spec.get("scenario")
                          else C.out(cfg_v, "agriculture", "effects_16regions.csv"), parse_dates=["date"])
        eff = eff[eff["var"].isin(nh.values())].pivot_table(index=["date", "code"], columns="var", values="effect_mean")
        piv = {(v, r): sh.pivot_table(index=["draw", "date", "hist_date"], columns="code", values=f"{v}_shift_{r}")
               for v in ("T", "TMAX") for r in ("scenario", "neutral")}
        keys = piv[("T", "scenario")].index.to_frame(index=False)
        acc = {}
        for hm, grp in keys.groupby("hist_date"):
            T = load_month(cfg, hm, cell_ids)
            tmax = np.nanmax(T, -1)                                                  # (pairs, days)
            idx = pd.MultiIndex.from_frame(grp)
            for k, (_, r) in enumerate(grp.iterrows()):
                n_days = min(tmax.shape[1], r["date"].days_in_month)
                for v in ("T", "TMAX"):
                    sS = piv[(v, "scenario")].loc[idx[k], codes].to_numpy(float)
                    s0 = piv[(v, "neutral")].loc[idx[k], codes].to_numpy(float)
                    for t in thr:
                        dn = ((tmax[:, :n_days] + sS[:, None] > t).sum(1) - (tmax[:, :n_days] + s0[:, None] > t).sum(1))
                        acc.setdefault((r["date"], v, t), []).append(dn @ Wr)
        for (d, v, t), lst in acc.items():
            m = np.mean(lst, 0)
            for j, r in enumerate(R):
                rows.append(dict(path=spec["name"], date=d, code=r, threshold=t, shift_by=v, implied=m[j],
                                 stage1=eff.loc[(d, r), nh[t]] if (d, r) in eff.index else np.nan))
    h = pd.DataFrame(rows)
    h = h.pivot_table(index=["path", "date", "code", "threshold", "stage1"], columns="shift_by", values="implied").reset_index()
    h = h.rename(columns={"T": "implied_by_T_shift", "TMAX": "implied_by_TMAX_shift", "stage1": "stage1_NHOT"})
    write_csv(h.round(4), C.out(cfg, "electricity", "check_section32_hot_days.csv"))
    print("\nSection 3.2 (2): hot days, scenario minus neutral, days per region-month (cropland weights), mean over "
          "the path's months")
    s2 = h.groupby(["path", "threshold"])[["stage1_NHOT", "implied_by_T_shift", "implied_by_TMAX_shift"]].mean()
    print(s2.round(3).to_string())
    write_csv(s2.round(4).reset_index(), C.out(cfg, "electricity", "check_section32_hot_days_summary.csv"))


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--only", nargs="+", choices=STAGES, help="stages to run (default: all)")
    ap.add_argument("--paths", nargs="+", help="forecast, forecast_dmi, 1997-98, 2015-16, 2023-24, unit, <scenario>_dmi")
    ap.add_argument("--with-dmi", action="store_true", help="also the RONI + DMI models")
    ap.add_argument("--max-minutes", type=float, help="store: stop after this many minutes (run again to go on)")
    ap.add_argument("--overwrite", action="store_true", help="store: redo the months already stored")
    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    cfg["_config_path"] = a.config
    S = settings(cfg)
    stages = a.only or list(STAGES)
    if "store" in stages and not stage_store(cfg, a.max_minutes, a.overwrite):
        return 0
    if "observed" in stages:
        with C.Timer("observed"):
            stage_observed(cfg, S)
    if "simulate" in stages:
        stage_simulate(cfg, S, a.paths, a.with_dmi)
    if "check" in stages:
        with C.Timer("check"):
            stage_check(cfg, a.paths, a.with_dmi)
    return 0


if __name__ == "__main__":
    sys.exit(main())
