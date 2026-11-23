#!/usr/bin/env python3
"""Step 5, agriculture: the hand-off of Stage 1 to the agricultural section.

Stage 1 writes the agriculture files while it runs (steps 1, 3 and 4, to outputs/agriculture/). This step checks
that each one is there, is newer than the model it comes from, and covers the months it should, and lists them for
Stage 2. Stage 2 itself (the crop models, Eqs. A4-A6 of the agricultural note) is on the ginevra-agriculture branch;
once it is merged it runs from here, after the check.

  python scripts/05_agriculture.py                       # the main run (RONI)
  python scripts/05_agriculture.py --variant roni_dmi    # the RONI + DMI variant (outputs/shared/variants/roni_dmi/)

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
    return 1 if handoff.check(cfg, "agriculture") else 0


if __name__ == "__main__":
    sys.exit(main())
