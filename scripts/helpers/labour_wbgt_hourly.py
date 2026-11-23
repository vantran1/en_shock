#!/usr/bin/env python3
"""Labour, hourly WBGT (scripts/06_labour.py does this through hourly_wbgt_edd.py; this script does it
from the local folder only): hourly WBGT in working hours at the cells, in the sun and in the shade, and its monthly
statistics.

Needs paths.era5_hourly_dir in config.yaml: one file per month (era5_YYYY_MM.nc) with t2m, d2m, sp, u10, v10
and ssrd, and the packages pywbgt and pythermalcomfort (see the README). For every month it writes the hourly
WBGT of the working hours to outputs/shared/work/wbgt_hourly/ (kept: the shocks of labour_shocks.py shift these hours), then

  outputs/shared/work/fields_wbgt.pkl                                  monthly P50, P90 and mean daily maximum per cell
  outputs/labour/observed_wbgt_monthly_17regions.csv    the same by region, with the observed work capacity

Months already computed are skipped, so the step can be stopped and resumed.

  python scripts/helpers/labour_wbgt_hourly.py
  python scripts/helpers/labour_wbgt_hourly.py --months 1955-01 1955-12     # only these months (then the tables are rebuilt)
  python scripts/helpers/labour_wbgt_hourly.py --overwrite                  # recompute everything
  python scripts/helpers/labour_wbgt_hourly.py --no-compute                 # only the tables, from the stored months

scripts/helpers/hourly_wbgt_edd.py fills the same store (outputs/shared/work/wbgt_hourly/) straight from Azure, together with step 2.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import wbgt as WB  # noqa: E402
from stage1.fit import weight_sets  # noqa: E402
from stage1.outputs import update_metadata, write_csv  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--months", nargs=2, metavar=("FIRST", "LAST"), help="YYYY-MM YYYY-MM (default: all months)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--no-tables", action="store_true", help="only compute the hourly WBGT (rebuild the tables later)")
    ap.add_argument("--allow-partial", action="store_true", help="use the complete days of months with missing hours")
    ap.add_argument("--no-compute", action="store_true", help="only build the tables from the stored months")
    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    S = WB.settings(cfg)
    if a.allow_partial:
        S["allow_partial_months"] = True
    M = C.load_pickle(C.work(cfg, "fields_monthly.pkl"), "scripts/01_prepare_inputs.py")
    Wt = C.load_pickle(C.work(cfg, "weights.pkl"), "scripts/01_prepare_inputs.py")
    cells, lat, lon = M["cells"], M["lat"], M["lon"]
    clat, clon = lat[cells // len(lon)], lon[cells % len(lon)]
    all_months = M["times"]
    months = pd.date_range(a.months[0] + "-01", a.months[1] + "-01", freq="MS") if a.months else all_months
    store = C.work(cfg, "wbgt_hourly")
    store.mkdir(parents=True, exist_ok=True)
    folder = C.path(cfg, "era5_hourly_dir")
    pattern = cfg["paths"]["hourly_pattern"]

    # ---------------------------------------------------------------- hourly WBGT, month by month
    todo = [] if a.no_compute else [t for t in months if a.overwrite or not WB.store_path(store, t).exists()]
    if todo and (folder is None or not folder.exists()):
        print("No hourly folder set (paths.era5_hourly_dir); nothing to compute.")
        todo = []
    if todo:
        try:
            import pythermalcomfort  # noqa: F401
            import pywbgt  # noqa: F401
        except ImportError as exc:
            raise SystemExit(f"{exc.name} is not installed: see 'Labour' in the README") from exc
        print(f"WBGT ({S['method']}) for {len(todo)} months, working hours {S['working_hours'][0]}:00-"
              f"{S['working_hours'][1]}:00 (UTC+{S['utc_offset_hours']}), {len(cells)} cells")
    t0, prev, prev_key, index, n_missing, n_wait = time.time(), None, None, None, 0, 0
    first = pd.Timestamp(int(cfg["period"]["train"][0]), 1, 1)
    for i, t in enumerate(todo):
        f = folder / pattern.format(year=t.year, month=t.month)
        if not f.exists():
            n_missing += 1
            prev, prev_key = None, None
            continue
        pk = t - pd.DateOffset(months=1)
        pf = folder / pattern.format(year=pk.year, month=pk.month)
        if t > first and prev_key != pk and not pf.exists():
            n_wait += 1                    # the first working hours of the month are in the previous UTC month
            continue
        raw = WB.read_hourly(f)
        if index is None:
            index = WB.cell_index(raw["lat"], raw["lon"], lat, lon, cells)
        cur = WB.at_cells(raw, index)
        p = prev if prev_key == pk else None
        if p is None and pf.exists():
            p = WB.at_cells(WB.read_hourly(pf), index)
        W, _ = WB.month_wbgt(cur, p, t.year, t.month, S, clat, clon)
        WB.save_month(WB.store_path(store, t), W, cells, S)
        prev, prev_key = cur, t
        if (i + 1) % 12 == 0 or i + 1 == len(todo):
            print(f"  {t:%Y-%m}  ({i + 1}/{len(todo)}, {time.time() - t0:.0f} s)", flush=True)
    if n_missing:
        print(f"  {n_missing} months have no hourly file in {folder}")
    if n_wait:
        print(f"  {n_wait} months wait for the file of the month before (their first working hours are in it)")

    if a.no_tables:
        return

    # ---------------------------------------------------------------- monthly statistics from the stored hours
    have = [t for t in all_months if WB.store_path(store, t).exists()]
    if not have:
        print("No hourly WBGT has been computed yet.")
        return
    with C.Timer(f"monthly statistics of {len(have)} months"):
        names = [f"c{c}" for c in cells]
        stats = {k: np.full((len(all_months), len(cells)), np.nan) for k in WB.METRICS}
        cap = {(e, it): np.full((len(all_months), len(cells)), np.nan) for e in WB.ENVS for it in WB.INTENSITIES}
        pos = pd.Series(np.arange(len(all_months)), index=all_months)
        log = []
        for t in have:
            W = WB.load_month(WB.store_path(store, t), cells)
            st, nd = WB.month_stats(W, S)
            log.append(dict(month=t, days=W.shape[1], complete_days=nd, status="ok" if st else "incomplete"))
            if not st:
                continue
            for k, v in st.items():
                stats[k][pos[t]] = v
            Cm = WB.capacities(W[:, np.isfinite(W).all(axis=(0, 2, 3))])
            for ke, e in enumerate(WB.ENVS):
                for ki, it in enumerate(WB.INTENSITIES):
                    cap[(e, it)][pos[t]] = Cm[ke, ki]
        fields = {k: pd.DataFrame(v, index=all_months, columns=names) for k, v in stats.items()}
        capacity = {k: pd.DataFrame(v, index=all_months, columns=names) for k, v in cap.items()}
        log = pd.DataFrame(log)
    C.save(dict(fields=fields, capacity=capacity, log=log, settings=S), C.work(cfg, "fields_wbgt.pkl"))
    bad = log[log["status"] != "ok"]
    if len(bad):
        print(f"  {len(bad)} months are incomplete (left out; --allow-partial uses their complete days):\n"
              + bad.head(12).to_string(index=False))

    # ---------------------------------------------------------------- observed regional tables
    ws = weight_sets(cfg)["labour"][0]
    rs, kind = ws.split("_", 1)
    s = Wt["sets"][rs]
    Wm = s["W"][kind]
    ok = fields[WB.METRICS[0]].notna().all(axis=1)
    idx = all_months[ok.to_numpy()]
    tab = pd.DataFrame({"date": np.repeat(idx.values, len(s["codes"])), "code": np.tile(s["codes"], len(idx)),
                        "region": np.tile(s["regions"], len(idx))})
    for k in WB.METRICS:
        tab[k] = (fields[k].loc[idx].to_numpy() @ Wm.T).reshape(-1)
    for (e, it), df in capacity.items():
        tab[f"CAP_{e}_{it}"] = (df.loc[idx].to_numpy() @ Wm.T).reshape(-1)
    write_csv(tab, C.out(cfg, "labour", "observed_wbgt_monthly_17regions.csv"))
    print(f"  {len(idx)} complete months, {idx[0]:%Y-%m} to {idx[-1]:%Y-%m}; regional values with the {kind} weights")
    yr = tab.assign(year=pd.to_datetime(tab["date"]).dt.year).groupby("year")[["WBGTSUN_P50", "WBGTSUN_P90", "WBGTSHD_P50",
                                                                             "CAP_SUN_heavy", "CAP_SHD_moderate"]].mean()
    print("  mean over regions and months, first and last years:\n" + pd.concat([yr.head(2), yr.tail(2)]).round(3).to_string())
    update_metadata(cfg, "06_wbgt_hourly", dict(folder=str(folder), months=int(len(idx)), settings=S,
                                                weights=ws, months_incomplete=int(len(bad))))
    print("Next: python scripts/helpers/labour_fit_wbgt.py")


if __name__ == "__main__":
    main()
