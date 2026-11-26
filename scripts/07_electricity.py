#!/usr/bin/env python3
"""Step 7, electricity: the hand-off of Stage 1 to the electricity section.

Stage 1 writes the electricity files while it runs (steps 1, 3 and 4, to outputs/electricity/; the population-
weighted observed table is in outputs/shared/). This step checks that each one is there, is newer than the model it
comes from, and covers the months it should, and lists them for the electricity model (Eqs. 2-3 of the electricity
note), which runs from here once its code is in this repository.

  python scripts/07_electricity.py                       # the main run (RONI)
  python scripts/07_electricity.py --variant roni_dmi    # the RONI + DMI variant (outputs/shared/variants/roni_dmi/)

The daily cooling degree days and temperatures by grid (observed, and simulated for the forecast path and the
scenarios; Eqs. 1-3 of the electricity note) are made by scripts/helpers/electricity_daily.py.

Exits with 1 if a file is missing or stale.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import handoff  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="check a variant's outputs (e.g. roni_dmi)")
    a = ap.parse_args(argv)
    cfg = C.load(a.config, a.variant)
    return 1 if handoff.check(cfg, "electricity") else 0


if __name__ == "__main__":
    sys.exit(main())
