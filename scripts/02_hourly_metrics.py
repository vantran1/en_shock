#!/usr/bin/env python3
"""Step 2, the hourly metrics (optional): the hourly rows of Table 2 at the cells, on Philippine days.

Needs paths.era5_hourly_dir in config.yaml (one file per month, era5_YYYY_MM.nc with t2m, d2m and tp).
Each month is computed once and kept in outputs/shared/work/hourly_metrics/, so the step can be stopped and resumed, and a re-run
only computes the months that have arrived since (scripts/helpers/hourly_wbgt_edd.py fills the same store, together with
the WBGT of step 6, straight from Azure). The step then writes outputs/shared/work/fields_hourly.pkl; steps 3-5 add TMAX, TMIN,
EDD, NHOT, NDRY, LDRY, N50 and VPDMAX as extra columns of the same region x month tables. Months without a file
are NaN. Without hourly files or stored months this step does nothing.

  python scripts/02_hourly_metrics.py
  python scripts/02_hourly_metrics.py --months 1955-01 1955-12   # a test on part of the record
  python scripts/02_hourly_metrics.py --no-compute              # only the tables, from the stored months
  python scripts/02_hourly_metrics.py --overwrite               # recompute every month
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import hourly, outputs  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--months", nargs=2, metavar=("FIRST", "LAST"), help="YYYY-MM YYYY-MM (default: all months)")
    ap.add_argument("--allow-partial", action="store_true", help="use the complete days of months with missing hours")
    ap.add_argument("--no-compute", action="store_true", help="only build the tables from the stored months")
    ap.add_argument("--overwrite", action="store_true", help="recompute the stored months too")
    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    if a.allow_partial:
        cfg["hourly"]["allow_partial_months"] = True
    folder = C.path(cfg, "era5_hourly_dir")
    store = C.work(cfg, "hourly_metrics")
    have_folder = folder is not None and folder.exists()
    if not have_folder and not any(store.glob("metrics_*.npz")):
        print("No hourly folder set (paths.era5_hourly_dir) and no stored months; nothing to do.")
        return
    M = C.load_pickle(C.work(cfg, "fields_monthly.pkl"), "scripts/01_prepare_inputs.py")
    months = M["times"]
    if a.months:
        months = pd.date_range(a.months[0] + "-01", a.months[1] + "-01", freq="MS")
    if have_folder and not a.no_compute:
        with C.Timer(f"hourly metrics for the months of {months[0]:%Y-%m} to {months[-1]:%Y-%m} not stored yet, from {folder}"):
            n = hourly.compute(cfg, months, folder, cfg["paths"]["hourly_pattern"], M["lat"], M["lon"], M["cells"],
                               store, overwrite=a.overwrite)
        print(f"  {n['computed']} months computed, {len(months) - n['todo']} already stored, {n['missing']} without a file"
              + (f", {n['waiting']} waiting for the file of the month before" if n["waiting"] else ""))
    F, log = hourly.assemble(cfg, months, store, M["cells"])
    bad = log[log["status"] != "ok"]
    if len(bad):
        print(f"  {len(bad)} months missing or incomplete (their values are NaN):\n" + bad.head(20).to_string(index=False))
    if a.months:                                     # a partial run: keep it apart from the full record
        target = C.work(cfg, f"fields_hourly_{a.months[0]}_{a.months[1]}.pkl")
        C.save(dict(fields=F, log=log), target)
        print(f"  test run written to {target} (not used by the model)")
        print(pd.concat({k: v.iloc[:, :3] for k, v in F.items()}, axis=1).round(2).T.to_string())
        return
    full = F
    C.save(dict(fields=full, log=log), C.work(cfg, "fields_hourly.pkl"))
    log.to_csv(C.work(cfg, "hourly_log.csv"), index=False)
    W = C.load_pickle(C.work(cfg, "weights.pkl"), "scripts/01_prepare_inputs.py")
    fields = {**M["fields"], **full}
    with C.Timer("re-writing the observed tables with the hourly columns"):
        outputs.export_observed(cfg, fields, W)
    outputs.update_metadata(cfg, "02_hourly_metrics", dict(folder=str(folder) if have_folder else None,
                                                            months_ok=int((log["status"] == "ok").sum()),
                                                            months_missing=int((log["status"] != "ok").sum()),
                                                            settings=hourly.settings(cfg)))


if __name__ == "__main__":
    main()
