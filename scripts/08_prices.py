#!/usr/bin/env python3
"""Step 8, prices: the world rice price shock (price note of the methodology, Section 2, Eqs. 1-2a).

  1 estimate  helpers/prices_estimate_rice.py   Eq. (1) on the real Thai 5% export price, 1960-2025, its checks and
                                                  the episode validation (a few seconds)
  2 shocks    helpers/prices_shocks_rice.py     Eq. (2) for the El Nino paths, with the block-bootstrap range and the
                                                  upper estimate with an export ban (under a minute)

Inputs in data/prices/ and data/indices/; outputs in outputs/prices/world_rice/ (shocks.csv is the hand-off). It
uses the RONI directly (no Stage 1 weather), so it can run at any time. See src/prices/README.md.

  python scripts/08_prices.py
  python scripts/08_prices.py --reps 200          # a quicker bootstrap
  python scripts/08_prices.py --skip-estimate     # only the shocks
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

HELPERS = pathlib.Path(__file__).resolve().parent / "helpers"


def helper(name: str):
    f = HELPERS / name
    spec = importlib.util.spec_from_file_location(f"_prices_{f.stem}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=1000, help="bootstrap replications (default 1000)")
    ap.add_argument("--block-years", type=int, default=5, help="length of the bootstrap blocks in years (default 5)")
    ap.add_argument("--skip-estimate", action="store_true", help="only the shocks")
    a = ap.parse_args(argv)
    if not a.skip_estimate:
        print("=== world rice price: estimation (Eq. 1)")
        helper("prices_estimate_rice.py")()
    print("\n=== world rice price: shocks (Eq. 2)")
    helper("prices_shocks_rice.py")(["--reps", str(a.reps), "--block-years", str(a.block_years)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
