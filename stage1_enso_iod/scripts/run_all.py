#!/usr/bin/env python3
"""Run steps 1-5 in order (step 2 only does something once the hourly files are set in config.yaml).
The labour steps 6-8 (WBGT, its EOF-CCA and the productivity shocks) run only when asked for with --to 8.

  python scripts/run_all.py                  # prepare, fit, path, simulate
  python scripts/run_all.py --from 4         # only the path and the simulation (e.g. a new monthly forecast)
  python scripts/run_all.py --download-c3s   # download this month's C3S forecast first
  python scripts/run_all.py --from 6 --to 8  # labour: hourly WBGT, its EOF-CCA, the shocks (needs the path of step 4)
  python scripts/run_all.py --from 3 --to 3 --variant roni_dmi   # fit the RONI + DMI variant as well

With --variant, the steps that depend on the predictors (3, 4, 5, 7, 8) run for that variant and write to
outputs/variants/<name>/; steps 1, 2 and 6 prepare the shared inputs and run as usual.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
VARIANT_STEPS = {3, 4, 5, 7, 8}
STEPS = {1: "01_prepare_inputs.py", 2: "02_hourly_metrics.py", 3: "03_fit_stage1.py", 4: "04_make_path.py",
         5: "05_simulate.py", 6: "06_wbgt_hourly.py", 7: "07_fit_wbgt.py", 8: "08_labour_shocks.py"}


def run(name, args):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), HERE / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"\n=== {name} {' '.join(args)}")
    mod.main(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="first", type=int, default=1)
    ap.add_argument("--to", dest="last", type=int, default=5)
    ap.add_argument("--config")
    ap.add_argument("--quick", action="store_true", help="step 3 on 3 months x 3 variables (step 5 is skipped)")
    ap.add_argument("--download-c3s", action="store_true")
    ap.add_argument("--forecast-start")
    ap.add_argument("--variant", help="run steps 3, 4, 5, 7 and 8 for this variant of config.yaml (e.g. roni_dmi)")
    a = ap.parse_args()
    common = ["--config", a.config] if a.config else []
    if a.download_c3s:
        run("00_download_inputs.py", common + ["--c3s"] + (["--c3s-start", a.forecast_start] if a.forecast_start else []))
    for k in range(a.first, a.last + 1):
        extra = []
        if k == 3 and a.quick:
            extra = ["--quick"]
        if k == 4 and a.forecast_start:
            extra = ["--forecast-start", a.forecast_start]
        if k == 5 and a.quick:
            print("\n(step 5 skipped in --quick mode: it needs all 12 months)")
            continue
        if a.variant and k in VARIANT_STEPS:
            extra = extra + ["--variant", a.variant]
        run(STEPS[k], common + extra)


if __name__ == "__main__":
    main()
