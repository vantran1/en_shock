#!/usr/bin/env python3
"""Step 6, labour: hourly ERA5 from Azure -> hourly WBGT -> monthly statistics -> their response to RONI (and
RONI + DMI) -> productivity shocks of the path (labour note; README section 7).

  1 hourly   helpers/hourly_wbgt_edd.py --azure --only wbgt   every month not done yet: download it if it is not
                                                      in the local folder, then its hourly WBGT in working hours
                                                      (sun and shade)
  2 tables   helpers/hourly_wbgt_edd.py --only wbgt --tables  monthly P50, P90 and mean daily maximum of WBGT per
                                                      cell; observed WBGT and work-capacity tables
  3 fit      helpers/labour_fit_wbgt.py                      EOF-CCA of the six statistics on RONI, then on RONI + DMI
  4 shocks   helpers/labour_shocks.py                        shocks of outputs/shared/path.csv, with both models

Only WBGT is computed here. The hourly variables of Stage 1 (TMAX, TMIN, EDD, NHOT, NDRY, LDRY, N50, VPDMAX) come
from the same files but belong to step 2: python scripts/run_all.py --from 2 --to 2 --azure.

Every stage can be stopped and run again: stage 1 does only the months that are not done, and the access token is
taken as usual (ERA5_SAS_URL, the saved token of `scripts/helpers/sync_era5_hourly.py set-token`, or a hidden prompt).

  python scripts/06_labour.py                       # all four stages, from Azure, both models
  python scripts/06_labour.py --local               # only the files already in the local folder (no Azure)
  python scripts/06_labour.py --delete-raw          # remove each raw file once WBGT and step 2 have both used it
  python scripts/06_labour.py --allow-incomplete    # tables and fit with the months there are (30 years at least)
  python scripts/06_labour.py --from fit            # start at a later stage (hourly, tables, fit, shocks)
  python scripts/06_labour.py --no-dmi --no-nested  # RONI alone; plain cross-validation only (faster)

--delete-raw keeps a raw file until both WBGT and the Stage 1 hourly variables of its month (and of the next month)
are done, so that step 2 does not have to download it again; it also removes files of the local folder
(paths.era5_hourly_dir) once used: leave it out if that folder holds your only copy.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
HELPERS = HERE / "helpers"
sys.path.insert(0, str(HERE.parent / "src"))
from stage1 import config as C  # noqa: E402

STAGES = ("hourly", "tables", "fit", "shocks")


def script(name: str):
    spec = importlib.util.spec_from_file_location(f"_labour_{name.removesuffix('.py')}", HELPERS / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def banner(text: str):
    print(f"\n{'=' * 100}\n{text}\n{'=' * 100}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--from", dest="first", choices=STAGES, default="hourly")
    ap.add_argument("--to", dest="last", choices=STAGES, default="shocks")
    ap.add_argument("--local", action="store_true", help="use only the local folder, do not download from Azure")
    ap.add_argument("--delete-raw", action="store_true",
                    help="remove each raw file once WBGT and the Stage 1 hourly variables of its month and the next are done")
    ap.add_argument("--allow-incomplete", action="store_true", help="write the tables and fit even if months are missing")
    ap.add_argument("--no-dmi", action="store_true", help="only the RONI-alone model (skip the roni_dmi variant)")
    ap.add_argument("--no-nested", action="store_true", help="step 7 with plain cross-validation only")
    ap.add_argument("--no-refresh", action="store_true", help="use the cached RONI and DMI in step 7")
    a = ap.parse_args(argv)
    common = ["--config", a.config] if a.config else []
    run = STAGES[STAGES.index(a.first): STAGES.index(a.last) + 1]
    models = [None] if a.no_dmi else [None, "roni_dmi"]
    t0 = time.time()

    if "hourly" in run:
        banner("1/4  hourly WBGT, month by month" + ("" if a.local else " (downloading from Azure what is not here)"))
        rc = script("hourly_wbgt_edd.py")(common + ["--only", "wbgt"] + ([] if a.local else ["--azure"])
                                          + (["--delete-raw"] if a.delete_raw else []))
        if rc:
            return rc
    if "tables" in run:
        banner("2/4  monthly WBGT statistics and observed tables")
        rc = script("hourly_wbgt_edd.py")(common + ["--only", "wbgt", "--no-compute", "--tables"]
                                          + (["--allow-incomplete"] if a.allow_incomplete else []))
        if rc:
            print("Stopped: the tables were not written (see above).")
            return rc
    if "fit" in run:
        for v in models:
            banner(f"3/4  EOF-CCA of the WBGT statistics on {'RONI + DMI (variant roni_dmi)' if v else 'RONI (main run)'}")
            script("labour_fit_wbgt.py")(common + (["--variant", v] if v else []) + (["--no-nested"] if a.no_nested else [])
                                     + (["--no-refresh"] if a.no_refresh else []))
    if "shocks" in run:
        cfg = C.load(a.config)
        if not C.out(cfg, "shared", "path.csv").exists():
            raise SystemExit("outputs/shared/path.csv is missing: run python scripts/04_simulate.py first")
        for v in models:
            banner(f"4/4  labour-productivity shocks with {'RONI + DMI' if v else 'RONI'}")
            script("labour_shocks.py")(common + (["--variant", v] if v else []))
    print(f"\nDone in {(time.time() - t0) / 60:.0f} min. Outputs: outputs/labour/ (RONI) and "
          f"outputs/shared/variants/roni_dmi/labour/ (RONI + DMI).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
