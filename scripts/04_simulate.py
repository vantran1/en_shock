#!/usr/bin/env python3
"""Step 4, simulate: the weather of the scenario path and of the neutral path, at every cell and for every
historical block, aggregated with each section's weights.

  1 path        helpers/make_path.py       the path x^S (monthly RONI and DMI): observed indices, then the median of
                                            the latest C3S forecast (or a variant's own path table)
                                            -> outputs/shared/path.csv, path_members.csv, path_systems.csv
  2 simulation  helpers/simulate_path.py   for every block Y_b and month of the path, the model prediction plus the
                                            block's CV residuals, back-transformed at t* (Eq. 10)
                                            -> outputs/shared/blocks.csv and the section tables (agriculture,
                                               electricity, labour)
  3 scenarios   helpers/run_scenarios.py   with --scenarios: the El Nino scenarios of the direct approach (scen_*)
                                            -> outputs/shared/scenarios/

  python scripts/04_simulate.py                              # the latest downloaded C3S forecast
  python scripts/04_simulate.py --forecast-start 2026-11     # another forecast
  python scripts/04_simulate.py --skip-path                  # simulate outputs/shared/path.csv as it is
  python scripts/04_simulate.py --variant roni_dmi           # on the RONI + DMI models
  python scripts/04_simulate.py --scenarios                  # then the scenario variants too
  python scripts/04_simulate.py --scenarios-only --only scen_unit

Each month, when a new forecast is out: python scripts/00_download_inputs.py --c3s, then this script. It refits
nothing.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

HELPERS = pathlib.Path(__file__).resolve().parent / "helpers"


def helper(name: str):
    f = HELPERS / name
    spec = importlib.util.spec_from_file_location(f"_simulate_{f.stem}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="a variant of config.yaml (e.g. roni_dmi): its own models, path and outputs")
    ap.add_argument("--forecast-start", help="YYYY-MM of the C3S forecast issue (default: the latest downloaded)")
    ap.add_argument("--no-refresh", action="store_true", help="use the index files as they are (no download)")
    ap.add_argument("--skip-path", action="store_true", help="do not rebuild the path; simulate the existing one")
    ap.add_argument("--scenarios", action="store_true", help="then run the scenario variants (scen_* in config.yaml)")
    ap.add_argument("--scenarios-only", action="store_true", help="only the scenario variants")
    ap.add_argument("--only", nargs="+", help="with --scenarios: these scenario variants only")
    a = ap.parse_args(argv)
    common = ["--config", a.config] if a.config else []
    var = ["--variant", a.variant] if a.variant else []
    if not a.scenarios_only:
        if not a.skip_path:
            print("=== path")
            helper("make_path.py")(common + var + (["--forecast-start", a.forecast_start] if a.forecast_start else [])
                                   + (["--no-refresh"] if a.no_refresh else []))
        print("\n=== simulation")
        helper("simulate_path.py")(common + var)
    if a.scenarios or a.scenarios_only:
        print("\n=== scenarios of the direct approach")
        helper("run_scenarios.py")(common + (["--only", *a.only] if a.only else []))
    return 0


if __name__ == "__main__":
    sys.exit(main())
