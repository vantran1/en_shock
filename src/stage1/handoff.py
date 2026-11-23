"""Hand-off check of a section: are the files that Stage 1 writes for it there, complete and up to date?

Stage 1 writes each section's files while it runs (step 1 the weights and observed tables, step 3 the historical
fitted values, step 4 the simulation of the path). The section scripts (05_agriculture.py, 07_electricity.py) list
them, check that each one exists, is newer than the model it comes from and covers the months it should, and are the
place where the section's own code (Stage 2) runs once it is in this repository.
"""
from __future__ import annotations

import datetime as dt
import gzip
import pathlib

import pandas as pd

from . import config as C

# (section folder, file, step that writes it, what it is)
FILES = {
    "agriculture": [
        ("agriculture", "cell_weights_16regions.csv", 1, "cropland and area weights of the 16 regions on the model cells"),
        ("agriculture", "island_reassignment_16regions.csv", 1, "land of dropped cells moved to the nearest kept cell"),
        ("agriculture", "observed_monthly_16regions_cropland.csv", 1, "observed region x month weather, cropland weights"),
        ("agriculture", "observed_monthly_16regions_area.csv", 1, "the same with area weights (sensitivity)"),
        ("agriculture", "hist_fitted_16regions.csv", 3, "fitted next to observed for every month (the Stage 2 input)"),
        ("agriculture", "simulated_monthly_16regions.csv", 4, "draws x months x regions, scenario and neutral path"),
        ("agriculture", "deterministic_monthly_16regions.csv", 4, "the same without the residuals (e = 0)"),
        ("agriculture", "effects_16regions.csv", 4, "scenario minus neutral: mean and percentiles over the draws"),
    ],
    "electricity": [
        ("electricity", "cell_weights_17regions.csv", 1, "population weights of the 17 regions on the model cells"),
        ("electricity", "region_grid_map.csv", 1, "region -> grid (Luzon, Visayas, Mindanao)"),
        ("shared", "observed_monthly_17regions_population.csv", 1, "observed region x month weather, population weights"),
        ("electricity", "hist_fitted_17regions.csv", 3, "fitted next to observed temperature for every month"),
        ("electricity", "cells_hist_fitted.csv.gz", 3, "the same at every cell"),
        ("electricity", "path_response_17regions.csv", 4, "temperature of the path and of the neutral path (Eq. 3)"),
        ("electricity", "shift_by_block_17regions.csv", 4, "shift by historical block (Eq. 3)"),
        ("electricity", "cells_path_response.csv.gz", 4, "the path response at every cell"),
    ],
}
# the work file each step's outputs derive from. A step writes its outputs within minutes of saving that file
# (step 3 even writes them just before it saves models.pkl), so an output counts as stale only when the file is more
# than STALE_AFTER seconds newer: the model was refitted, or the weights rebuilt, after the output was written.
SOURCE = {1: "weights.pkl", 3: "models.pkl", 4: "models.pkl"}
STALE_AFTER = 3600
SCRIPT = {1: "scripts/01_prepare_inputs.py", 3: "scripts/03_fit_climate_model.py", 4: "scripts/04_simulate.py"}


def _rows_and_dates(p: pathlib.Path) -> tuple[int, str]:
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split(",")
        n = sum(1 for _ in fh)
    if "date" not in header:
        return n, ""
    d = pd.to_datetime(pd.read_csv(p, usecols=["date"])["date"], errors="coerce").dropna()
    return n, f"{d.min():%Y-%m} to {d.max():%Y-%m}" if len(d) else ""


def check(cfg: dict, section: str) -> int:
    """Prints the hand-off table of a section (main run, or a variant with --variant); returns the number of
    missing or stale files."""
    bad = 0
    print(f"{section} hand-off, {C.label(cfg)}\n")
    rows = []
    for folder, name, step, what in FILES[section]:
        # step 1 outputs are shared by every variant; steps 3-4 are the variant's own
        p = C.out_in(cfg, folder, name) if step == 1 else C.out(cfg, folder, name)
        src = C.work(cfg, SOURCE[step])
        if not p.exists():
            status, n, dates, when = "MISSING", "", "", ""
            bad += 1
        else:
            n, dates = _rows_and_dates(p)
            mtime = p.stat().st_mtime
            when = dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            status = "ok"
            if src.exists() and mtime < src.stat().st_mtime - STALE_AFTER:
                status = "STALE"
                bad += 1
        rows.append(dict(step=f"{step:02d}", file=str(p.relative_to(C.path(cfg, "outputs_dir").parent)),
                         status=status, rows=n, months=dates, written=when, what=what))
    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    print(pd.DataFrame(rows).to_string(index=False))
    if bad:
        steps = sorted({r["step"] for r in rows if r["status"] != "ok"})
        flag = f" --variant {cfg['_variant']}" if cfg.get("_variant") else ""
        print(f"\n{bad} file(s) missing, or written before the model they come from was refitted: re-run "
              + ", then ".join(f"python {SCRIPT[int(s)]}{flag if int(s) > 1 else ''}" for s in steps))
    else:
        print("\nEvery file is there and up to date.")
    return bad
