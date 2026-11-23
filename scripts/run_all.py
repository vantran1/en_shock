#!/usr/bin/env python3
"""The main run, steps 00-08 in order.

  00  download_inputs     inputs that are not in the repository (only with --from 0, or --download-c3s for the
                          monthly forecast)
  01  prepare_inputs      ERA5 land cells, section weights, Table 2 fields at the cells, observed tables
  02  hourly_metrics      hourly rows of Table 2 (EDD, TMAX, ...), once the hourly ERA5 files are there
  03  fit_climate_model   EOF-CCA from the RONI to the weather, cross-validated; skill; historical fitted values
  04  simulate            the scenario path and its simulated weather (--scenarios: the direct-approach scenarios)
  05  agriculture         hand-off check of the agriculture files
  06  labour              hourly WBGT, its EOF-CCA and the productivity shocks (only with --labour: it needs the
                          hourly ERA5, from the local folder or with --azure from Azure, and pywbgt)
  07  electricity         hand-off check of the electricity files
  08  prices              world rice price shock (independent of Stage 1)

  python scripts/run_all.py                          # steps 01-08 without labour (about 15 minutes)
  python scripts/run_all.py --labour                 # with labour
  python scripts/run_all.py --from 0                 # download the inputs first (00_download_inputs.py --all)
  python scripts/run_all.py --download-c3s --from 4  # each month, when a new forecast is out: refits nothing
  python scripts/run_all.py --from 3 --to 5 --variant roni_dmi   # the RONI + DMI variant (steps 03, 04, 05, 07)
  python scripts/run_all.py --from 2 --to 2 --azure  # step 02 from Azure (helpers/hourly_wbgt_edd.py --only edd)
  python scripts/run_all.py --quick --to 3           # trial fit: 3 months x 3 variables

The run stops at the first step that fails. Every step can also be run on its own: python scripts/0N_<name>.py
(--help lists its options).
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
STEPS = {0: "00_download_inputs.py", 1: "01_prepare_inputs.py", 2: "02_hourly_metrics.py",
         3: "03_fit_climate_model.py", 4: "04_simulate.py", 5: "05_agriculture.py", 6: "06_labour.py",
         7: "07_electricity.py", 8: "08_prices.py"}
VARIANT_STEPS = {3, 4, 5, 7}   # 06 fits and shocks both models itself; 08 does not use Stage 1


def run(f: pathlib.Path, args: list[str]):
    spec = importlib.util.spec_from_file_location(f"_run_{f.stem}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"\n{'=' * 100}\n{f.relative_to(HERE.parent)} {' '.join(args)}\n{'=' * 100}", flush=True)
    return mod.main(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="first", type=int, default=1, choices=range(0, 9))
    ap.add_argument("--to", dest="last", type=int, default=8, choices=range(0, 9))
    ap.add_argument("--config")
    ap.add_argument("--labour", action="store_true", help="include step 06 (labour)")
    ap.add_argument("--quick", action="store_true", help="step 03 on 3 months x 3 variables (step 04 is skipped)")
    ap.add_argument("--download-c3s", action="store_true", help="download this month's C3S forecast first")
    ap.add_argument("--forecast-start", help="step 04: YYYY-MM of the C3S forecast")
    ap.add_argument("--scenarios", action="store_true", help="step 04: also the scenarios of the direct approach")
    ap.add_argument("--variant", help="steps 03, 04, 05, 07 for this variant of config.yaml (e.g. roni_dmi)")
    ap.add_argument("--azure", action="store_true", help="steps 02 and 06: download the hourly files that are not here")
    ap.add_argument("--delete-raw", action="store_true", help="steps 02 and 06 with --azure: remove raw files once used")
    ap.add_argument("--allow-incomplete", action="store_true", help="steps 02 and 06: go on if hourly months are missing")
    ap.add_argument("--reps", type=int, default=1000, help="step 08: bootstrap replications")
    a = ap.parse_args()
    common = ["--config", a.config] if a.config else []

    if a.download_c3s and a.first > 0:
        run(HERE / STEPS[0], common + ["--c3s"] + (["--c3s-start", a.forecast_start] if a.forecast_start else []))
    for k in range(a.first, a.last + 1):
        args = list(common)
        if k == 0:
            args += ["--all"]
        if k == 2 and a.azure:
            rc = run(HERE / "helpers" / "hourly_wbgt_edd.py",
                     common + ["--azure", "--only", "edd", "--tables"] + (["--delete-raw"] if a.delete_raw else [])
                     + (["--allow-incomplete"] if a.allow_incomplete else []))
            if rc:
                raise SystemExit("Stopped after step 02: the hourly variables were not written (see above).")
            continue
        if k == 3 and a.quick:
            args += ["--quick"]
        if k == 4:
            if a.quick:
                print("\n(step 04 skipped in --quick mode: it needs all 12 months)")
                continue
            args += (["--forecast-start", a.forecast_start] if a.forecast_start else []) + (["--scenarios"] if a.scenarios else [])
        if k == 6:
            if not a.labour and a.first != 6:
                print("\n(step 06, labour, skipped: add --labour to run it)")
                continue
            args += ([] if a.azure else ["--local"]) + (["--delete-raw"] if a.delete_raw else []) \
                + (["--allow-incomplete"] if a.allow_incomplete else [])
        if k == 8:
            if a.variant:
                print("\n(step 08 skipped with --variant: the price shock does not use Stage 1)")
                continue
            args = ["--reps", str(a.reps)]
        if a.variant and k in VARIANT_STEPS:
            args += ["--variant", a.variant]
        rc = run(HERE / STEPS[k], args)
        if isinstance(rc, int) and rc != 0:
            raise SystemExit(f"Stopped after {STEPS[k]} (exit code {rc}).")


if __name__ == "__main__":
    main()
