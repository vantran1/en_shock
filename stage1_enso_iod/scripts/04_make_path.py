#!/usr/bin/env python3
"""Step 4: the scenario path x^S (monthly RONI and DMI) from the latest C3S forecast.

The path runs from January of the forecast's year (config path.start) to the last forecast month: observed
indices up to the forecast, then the median of the C3S members (10 per system). Writes
outputs/shared/path.csv, path_members.csv and path_systems.csv.

  python scripts/04_make_path.py                         # the forecast issued this month (from the 11th)
  python scripts/04_make_path.py --forecast-start 2026-11
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import indices as I  # noqa: E402
from stage1 import paths  # noqa: E402
from stage1.outputs import update_metadata, write_csv  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="a variant of config.yaml (e.g. roni_dmi): its own path, e.g. a stress scenario")
    ap.add_argument("--forecast-start", help="YYYY-MM of the forecast issue")
    ap.add_argument("--no-refresh", action="store_true", help="use the cached RONI and DMI")
    a = ap.parse_args(argv)
    cfg = C.load(a.config, a.variant)
    idx, info = I.model_indices(cfg, False if a.no_refresh else None)
    raw_dmi = info.pop("raw_dmi")
    print(f"observed: RONI to {info['roni_last']}, DMI to {info['dmi_raw_last']} (smoothed to {info['dmi_smoothed_last']})")
    path, members, meta = paths.build_path(cfg, idx, raw_dmi, a.forecast_start)
    out = path.reset_index()
    write_csv(out, C.out(cfg, "shared", "path.csv"))
    if members is not None:
        write_csv(members, C.out(cfg, "shared", "path_members.csv"))
        write_csv(pd.DataFrame(meta["systems"]), C.out(cfg, "shared", "path_systems.csv"))
    show = out[["date", "roni", "roni_source", "dmi", "dmi_source"]].copy()
    show["date"] = show["date"].dt.strftime("%Y-%m")
    print(show.round(2).to_string(index=False))
    update_metadata(cfg, "04_make_path", {**meta, "indices": info})
    print("Next: python scripts/05_simulate.py")


if __name__ == "__main__":
    main()
