#!/usr/bin/env python3
"""EDD and WBGT from the hourly ERA5, month by month, as the files arrive from Azure.

One pass over the hourly files: every month is read once, at the model cells, and gives
  * the hourly rows of Table 2 (agricultural note): TMAX, TMIN, EDD, NHOT, NDRY, LDRY, N50, VPDMAX, and the
    monthly mean of hourly VPD (which replaces the VPD of the monthly means), with
    EDD = sum over the hours of max(0, T_h - T*) / 24 and T* = hourly.t_star (35 °C, rice at flowering), and
    EDD30, NHOT30, EDD32, NHOT32 at the lower thresholds of hourly.t_star_extra
    -> outputs/shared/work/hourly_metrics/   (what step 2 computes)
  * WBGT in the sun and in the shade for every working hour, with pywbgt's Liljegren model (labour note)
    -> outputs/shared/work/wbgt_hourly/      (what step 6 computes)
Months already done are skipped, so the script can be run again and again while the ERA5 download goes on: each run
does the months that have arrived since. A month waits until the month before it is there too, because its first
Philippine day starts at 16:00 UTC on the last day of the previous month (only the first month of the record is done
without it).

Where the files come from: the local folder (paths.era5_hourly_dir, else data/shared/era5/hourly/, as for
scripts/helpers/sync_era5_hourly.py) and, with --azure, the Azure container: a month that is not here is downloaded first
(and checked against the MD5 that Azure holds). With --delete-raw a downloaded or local file is removed once both
products of its month and of the following month are saved, which keeps the disk use to a few files (the raw files
are about 26 MB a month; the Azure copy stays).

When every month of the training period is done, --tables writes what steps 2 and 6 write: outputs/shared/work/fields_hourly.pkl
with the observed tables (the hourly variables then enter the fit of step 3), and outputs/shared/work/fields_wbgt.pkl with the
observed WBGT table (for step 7).

  python scripts/helpers/sync_era5_hourly.py list                    # what is in Azure
  python scripts/helpers/hourly_wbgt_edd.py --azure                  # download and compute every month that is ready
  python scripts/helpers/hourly_wbgt_edd.py --azure --delete-raw     # the same, keeping only a few raw files on disk
  python scripts/helpers/hourly_wbgt_edd.py --status                 # what is done, what is waiting
  python scripts/helpers/hourly_wbgt_edd.py --tables                 # once every month is done (or add --allow-incomplete)
  python scripts/helpers/hourly_wbgt_edd.py --months 1955-01 1955-12 --only edd     # part of the record, one product

Stop it at any time (Ctrl-C): finished months are kept, and the next run carries on.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import time

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import hourly as HR  # noqa: E402
from stage1 import wbgt as WB  # noqa: E402

PRODUCTS = {"edd": "EDD and the other hourly rows of Table 2", "wbgt": "WBGT in working hours (sun and shade)"}


def fmt_months(ts) -> str:
    """1955-01..1955-12, 1957-03 ..."""
    ts = sorted(pd.DatetimeIndex(ts))
    if not ts:
        return "-"
    out, i = [], 0
    while i < len(ts):
        j = i
        while j + 1 < len(ts) and ts[j + 1] == ts[j] + pd.DateOffset(months=1):
            j += 1
        out.append(f"{ts[i]:%Y-%m}" if i == j else f"{ts[i]:%Y-%m}..{ts[j]:%Y-%m}")
        i = j + 1
    return ", ".join(out)


def n_months(n: int) -> str:
    return f"{n} month" + ("" if n == 1 else "s")


def run_step(f: pathlib.Path, args: list[str]) -> None:
    name = f.name
    spec = importlib.util.spec_from_file_location(f.stem, f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"\n=== {name} {' '.join(args)}")
    mod.main(args)


class Source:
    """The hourly files: the local folder and, with azure=True, the Azure container (downloads on demand)."""

    def __init__(self, cfg: dict, azure: bool):
        from stage1 import azure_era5 as AZ
        self.AZ = AZ
        folder = C.path(cfg, "era5_hourly_dir")
        self.pattern = cfg["paths"]["hourly_pattern"]
        self.store, self.remote = None, set()
        if azure:
            self.store = AZ.Store(local_dir=folder) if folder is not None else AZ.Store()
            self.folder = self.store.local_dir
            self.pattern = AZ.FILE_PATTERN
            self.remote = {pd.Timestamp(y, m, 1) for (y, m) in self.store.blobs()}
        else:
            self.folder = folder if folder is not None else AZ.default_local_dir()
        self.downloaded: list[pd.Timestamp] = []

    def local(self, t: pd.Timestamp) -> pathlib.Path:
        return self.folder / self.pattern.format(year=t.year, month=t.month)

    def available(self, t: pd.Timestamp) -> bool:
        return self.local(t).exists() or t in self.remote

    def get(self, t: pd.Timestamp) -> pathlib.Path:
        p = self.local(t)
        if p.exists():
            return p
        p = self.store.fetch(t.year, t.month)
        self.downloaded.append(t)
        return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--months", nargs=2, metavar=("FIRST", "LAST"), help="YYYY-MM YYYY-MM (default: the training period)")
    ap.add_argument("--only", choices=list(PRODUCTS), help="compute one product only (default: both)")
    ap.add_argument("--azure", action="store_true", help="download the months that are not here from Azure")
    ap.add_argument("--delete-raw", action="store_true",
                    help="remove a raw file once both products of its month and of the next month are saved")
    ap.add_argument("--overwrite", action="store_true", help="recompute months that are already done")
    ap.add_argument("--allow-partial", action="store_true", help="use the complete days of months with missing hours")
    ap.add_argument("--status", action="store_true", help="only report what is done and what is waiting")
    ap.add_argument("--no-compute", action="store_true", help="compute nothing (with --tables: only the tables)")
    ap.add_argument("--tables", action="store_true", help="then write the fields and tables of steps 2 and 6")
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="with --tables: write them even if some months are not done (they are NaN)")
    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    if a.allow_partial:
        cfg["hourly"]["allow_partial_months"] = True
        cfg.setdefault("wbgt", {})["allow_partial_months"] = True
    products = [a.only] if a.only else list(PRODUCTS)

    M = C.load_pickle(C.work(cfg, "fields_monthly.pkl"), "scripts/01_prepare_inputs.py")
    cells, lat, lon = M["cells"], M["lat"], M["lon"]
    clat, clon = lat[cells // len(lon)], lon[cells % len(lon)]
    period = M["times"]
    months = pd.date_range(a.months[0] + "-01", a.months[1] + "-01", freq="MS") if a.months else period
    first, last = HR.first_month(cfg), period[-1]
    H, S = HR.settings(cfg), WB.settings(cfg)
    store = {"edd": C.work(cfg, "hourly_metrics"), "wbgt": C.work(cfg, "wbgt_hourly")}
    for d in store.values():
        d.mkdir(parents=True, exist_ok=True)
    ends = WB.interval_ends(S)

    def done(t, prods) -> bool:
        for k in prods:
            if k == "edd":
                if HR.month_state(HR.store_path(store["edd"], t), cells, H) not in ("ok", "incomplete"):
                    return False
            else:
                p = WB.store_path(store["wbgt"], t)
                if not p.exists():
                    return False
                with np.load(p) as z:
                    if not (np.array_equal(z["cells"], cells) and np.array_equal(z["ends"], ends)):
                        return False
        return True

    src = Source(cfg, a.azure)
    where = f"{src.folder}" + (f" and Azure ({src.store.location}/{src.store.prefix}/, {len(src.remote)} months)" if a.azure else "")
    print(f"Hourly ERA5 for {months[0]:%Y-%m} to {months[-1]:%Y-%m} ({len(months)} months) from {where}")
    print("  products: " + "; ".join(PRODUCTS[k] for k in products) + f"; T* = {H['t_star']:g} °C, working hours "
          f"{S['working_hours'][0]}:00-{S['working_hours'][1]}:00 PHT")

    # ---------------------------------------------------------------- compute
    todo = [t for t in months if a.overwrite or not done(t, products)]
    computed, waiting, absent, failed, deleted = [], [], [], [], []
    if a.status or a.no_compute:
        todo_now = []
    else:
        todo_now = todo
    if todo_now and "wbgt" in products:
        try:
            import pythermalcomfort  # noqa: F401
            import pywbgt  # noqa: F401
        except ImportError as exc:
            raise SystemExit(f"{exc.name} is not installed: see 'Labour' in the README") from exc
    variables = sorted(set(HR.VARIABLES if "edd" in products else ()) | set(WB.NEEDED if "wbgt" in products else ()))

    def delete_if_done(t):
        """Remove the raw file of month t once it is no longer needed."""
        p = src.local(t)
        if not a.delete_raw or not p.exists():
            return
        nxt = t + pd.DateOffset(months=1)
        if done(t, PRODUCTS) and (t >= last or done(nxt, PRODUCTS)):
            p.unlink()
            deleted.append(t)

    t_start, prev, prev_key, index = time.time(), None, None, None
    try:
        for i, t in enumerate(todo_now):
            if not src.available(t):
                absent.append(t)
                prev, prev_key = None, None
                continue
            pk = t - pd.DateOffset(months=1)
            if t > first and prev_key != pk and not src.available(pk):
                waiting.append(t)
                continue
            try:
                raw = HR.read_vars(src.get(t), variables)
                if index is None:
                    index = HR._cell_index(raw["lat"], raw["lon"], lat, lon, cells)
                cur = HR.at_cells(raw, index, variables)
                p = prev if prev_key == pk else None
                if p is None and src.available(pk):          # always the case after the first month (else it waits)
                    p = HR.at_cells(HR.read_vars(src.get(pk), variables), index, variables)
            except (src.AZ.AzureIntegrityError, src.AZ.AzureAccessError, FileNotFoundError) as e:
                if isinstance(e, src.AZ.AzureUnreachable):
                    raise
                print(f"  {t:%Y-%m}: {e}")
                failed.append(t)
                prev, prev_key = None, None
                continue
            if "edd" in products and (a.overwrite or not done(t, ["edd"])):
                m, nd = HR.compute_month(cur, p, t, H)
                HR.save_month(HR.store_path(store["edd"], t), m, nd, cells, H)
            if "wbgt" in products and (a.overwrite or not done(t, ["wbgt"])):
                W, _ = WB.month_wbgt(cur, p, t.year, t.month, S, clat, clon)
                WB.save_month(WB.store_path(store["wbgt"], t), W, cells, S)
            computed.append(t)
            prev, prev_key = cur, t
            delete_if_done(pk)
            delete_if_done(t)
            if len(computed) % 12 == 0:
                el = time.time() - t_start
                left = len(todo_now) - i - 1
                print(f"  {t:%Y-%m}  {n_months(len(computed))} done, {el / 60:.1f} min"
                      + (f"; about {el / len(computed) * left / 60:.0f} min for the {left} left" if left else ""), flush=True)
    except KeyboardInterrupt:
        print(f"\nStopped after {len(computed)} months; they are kept, and the next run carries on.")
        return 130

    if computed:
        print(f"  computed {n_months(len(computed))} ({fmt_months(computed)}) in {(time.time() - t_start) / 60:.1f} min")
    if waiting:
        print(f"  {n_months(len(waiting))} wait for the file of the month before: {fmt_months(waiting)}")
    if absent:
        print(f"  {n_months(len(absent))} have no file yet" + (" here or in Azure" if a.azure else " here (--azure to download them)")
              + f": {fmt_months(absent)}")
    if failed:
        print(f"  {n_months(len(failed))} failed (run again to retry): {fmt_months(failed)}")
    if deleted:
        print(f"  removed {len(deleted)} raw files that are no longer needed")

    # ---------------------------------------------------------------- status
    rows = []
    for k in products:
        st = [HR.month_state(HR.store_path(store["edd"], t), cells, H) if k == "edd"
              else ("ok" if done(t, ["wbgt"]) else "absent") for t in period]
        rows.append((k, sum(s == "ok" for s in st), sum(s == "incomplete" for s in st),
                     [t for t, s in zip(period, st) if s not in ("ok", "incomplete")]))
    print(f"\nStatus over the training period ({period[0]:%Y-%m} to {last:%Y-%m}, {len(period)} months):")
    for k, n_ok, n_inc, miss in rows:
        print(f"  {PRODUCTS[k]}: {n_ok} done" + (f", {n_inc} incomplete (missing hours)" if n_inc else "")
              + (f"; not done: {fmt_months(miss)}" if miss else "; complete"))
    if "wbgt" in products and not a.status:
        bad = []
        for t in period:
            p = WB.store_path(store["wbgt"], t)
            if p.exists() and t in computed:
                st, _ = WB.month_stats(WB.load_month(p, cells), S)
                if not st:
                    bad.append(t)
        if bad:
            print(f"  WBGT of {fmt_months(bad)} has missing hours; those months are left out of the tables "
                  "(or use --allow-partial)")

    # ---------------------------------------------------------------- tables
    if a.tables:
        missing = sorted(set().union(*[set(m) for *_, m in rows]))
        if missing and not a.allow_incomplete:
            print(f"\nTables not written: {n_months(len(missing))} are not done ({fmt_months(missing)}). Run again when "
                  "they have arrived, or add --allow-incomplete to write the tables with those months as NaN.")
            return 1
        common = (["--config", a.config] if a.config else []) + ["--no-compute"] + (["--allow-partial"] if a.allow_partial else [])
        if "edd" in products:
            run_step(HERE.parent / "02_hourly_metrics.py", common)
        if "wbgt" in products:
            run_step(HERE / "labour_wbgt_hourly.py", common)
        nxt = (["python scripts/03_fit_climate_model.py (and --variant roni_dmi) to fit the hourly variables"] if "edd" in products
               else []) + (["python scripts/06_labour.py --from fit for WBGT"] if "wbgt" in products else [])
        print("\nNext: " + "; ".join(nxt))
    elif not a.status and all(not m for *_, m in rows):
        print("\nEvery month is done: run with --tables to write the fields and tables of step 2 and of labour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
