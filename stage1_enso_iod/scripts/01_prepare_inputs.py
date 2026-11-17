#!/usr/bin/env python3
"""Step 1: ERA5 land cells, the section weights, and the monthly Table 2 fields at the cells.

Reads the monthly ERA5 files and the region polygons; uses the land-sea mask, cropland and population files of
data/inputs/ when they are there (otherwise the fallbacks of config.yaml, flagged in the outputs). Writes
work/fields_monthly.pkl and work/weights.pkl, and the observed regional tables and cell weights in outputs/.
"""
from __future__ import annotations

import argparse
import pathlib
import sys


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import era5, outputs, regions  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = C.load(a.config)

    with C.Timer("reading the monthly ERA5 files"):
        E5 = era5.load_monthly(C.path(cfg, "era5_monthly_dir"))
    lat, lon, times = E5["lat"], E5["lon"], E5["times"]
    print(f"  {len(times)} months, {times[0]:%Y-%m} to {times[-1]:%Y-%m}; grid {len(lat)} x {len(lon)}")

    land, land_kind, land_info = regions.land_mask(cfg, lat, lon, E5["grids"]["swvl_root"])
    print(f"  land cells: {land_info['source']}")
    if "cells_differing_from_fallback_rule" in land_info:
        print(f"  cells where the mask and the fallback rule disagree: {land_info['cells_differing_from_fallback_rule']}")

    with C.Timer("cell weights (area, cropland, population)"):
        W = regions.build_weights(cfg, lat, lon, land)
    cells = W["cells"]
    print(f"  {len(cells)} ERA5 land cells overlap the 17 regions")
    for rs, s in W["sets"].items():
        for kind, f in s["flags"].items():
            tag = "FALLBACK to area" if f["fallback"] else f["source"]
            print(f"  {rs} {kind:10s}: {tag}")
    cov = W["sets"]["r17"]["coverage"]
    if len(cov.columns):
        print("  share of each region's total inside its own land cells:\n" + cov.round(3).to_string())
        mov = W["sets"]["r17"]["reassigned"]
        print("  share moved from dropped cells (small islands) to the nearest land cell:\n" + mov.round(3).to_string())

    with C.Timer("Table 2 fields at the cells"):
        T2 = era5.table2_fields(E5["grids"], cells, times, tuple(cfg["period"]["clim"]))
    C.save(dict(fields=T2["fields"], cwb_clim=T2["cwb_clim"], times=times, cells=cells, lat=lat, lon=lon,
                land_info=land_info), C.work(cfg, "fields_monthly.pkl"))
    W_save = {k: v for k, v in W.items()}
    C.save(W_save, C.work(cfg, "weights.pkl"))

    with C.Timer("writing observed tables and weights"):
        outputs.export_weights(cfg, W)
        outputs.export_observed(cfg, T2["fields"], W)
    flags = {f"{rs}_{k}": f for rs, s in W["sets"].items() for k, f in s["flags"].items()}
    outputs.update_metadata(cfg, "01_prepare_inputs", dict(
        era5_dir=str(C.path(cfg, "era5_monthly_dir")), months=f"{times[0]:%Y-%m} to {times[-1]:%Y-%m}",
        land=land_info, n_cells=int(len(cells)), weights=flags))
    print("Next: python scripts/02_hourly_metrics.py (once the hourly files exist), then 03_fit_stage1.py")


if __name__ == "__main__":
    main()
