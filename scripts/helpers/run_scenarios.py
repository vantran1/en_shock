#!/usr/bin/env python3
"""Stage 1 on the El Nino scenarios of the direct approach: the path and the simulation of step 4 for each scenario
variant, and the hand-off (python scripts/04_simulate.py --scenarios-only runs this).

The scenario variants (scen_* in config.yaml) each read a path table from data/shared/paths/ (date, roni, dmi; written
by scripts/make_stage1_paths.py on the ginevra-agriculture branch, in the units of data/indices/). Each table is
6 zero months, the El Nino months, and 12 zero months. The variants set path.lead_in: zero, so the 6 lead-in months
that the lagged predictors need before a table are zeros, not the observed indices: the 6 leading zero months of
the table are then exactly neutral (scenario = neutral, draw by draw) and stay in the hand-off, where Stage 2's
growing windows need them. scen_<name> runs the main RONI-alone models, scen_<name>_dmi the RONI + DMI models.

Writes, for each scenario and model (roni, roni_dmi), outputs/shared/scenarios/<scenario>/<model>/:
  path.csv                              the path of step 4, with its observed lead-in (lead_in = True)
  blocks.csv                            the historical blocks (draws); first/last_hist_month for the months written
  simulated_monthly_16regions.csv       draws x months x regions, scenario and neutral path (step 5)
  deterministic_monthly_16regions.csv   the same with e = 0
  effects_16regions.csv                 scenario minus neutral: mean, 10th and 90th percentiles over the draws
The simulations use the trend at t* (period.t_star in config.yaml), i.e. today's climate.

  python scripts/helpers/run_scenarios.py                      # all scen_* variants
  python scripts/helpers/run_scenarios.py --only scen_unit     # one
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]   # the en_shock repository
sys.path.insert(0, str(ROOT / "src"))
from stage1 import config as C  # noqa: E402
from stage1.outputs import write_csv  # noqa: E402

FILES = ("simulated_monthly_16regions.csv", "deterministic_monthly_16regions.csv", "effects_16regions.csv")


def step(name: str):
    f = ROOT / "scripts" / "helpers" / name
    spec = importlib.util.spec_from_file_location(f"_step_{f.stem}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def handoff(cfg: dict, drop: int) -> tuple[pathlib.Path, pd.DataFrame]:
    """Writes the step 4-5 outputs of one variant, from the month after the first `drop` months of its path table
    (drop = 0: every month of the table), and checks that the table's leading zero months are exactly neutral."""
    csv = pathlib.Path(cfg["path"]["csv"])
    scenario = csv.stem.removeprefix("path_")
    model = "_".join(C.predictors(cfg))
    src = pd.read_csv(ROOT / csv if not csv.is_absolute() else csv, parse_dates=["date"]).sort_values("date")
    lead = src.head(drop)
    if len(src) <= drop or (lead[["roni", "dmi"]].abs().to_numpy() > 0).any():
        raise SystemExit(f"{csv}: the first {drop} months are not all zero; nothing dropped")
    keep_from = src["date"].iloc[drop]
    nz = (src[["roni", "dmi"]].abs() > 0).any(axis=1).to_numpy()
    zeros = src["date"][: int(nz.argmax()) if nz.any() else len(src)]      # the table's leading zero months
    det = pd.read_csv(C.out(cfg, "agriculture", "deterministic_monthly_16regions.csv"), parse_dates=["date"])
    det = det[det["date"].isin(zeros) & (det["date"] >= keep_from)]
    if len(det):
        num = det.select_dtypes("number").columns.difference(["draw", "block_year"])
        w = det.pivot_table(index=["date", "code"], columns="path", values=list(num))
        gap = max((w[v]["scenario"] - w[v]["neutral"]).abs().max() for v in num)
        print(f"  leading zero months {zeros.iloc[0]:%Y-%m} to {zeros.iloc[-1]:%Y-%m}: largest |scenario - neutral| = {gap:.2g}")
        if gap > 1e-6 and str(cfg["path"].get("lead_in", "observed")) == "zero":
            raise SystemExit(f"{scenario} {model}: the leading zero months are not neutral (|difference| up to {gap:.3g})")
    dest = C.path(cfg, "outputs_dir") / "shared" / "scenarios" / scenario / model
    path = pd.read_csv(C.out(cfg, "shared", "path.csv"), parse_dates=["date"])
    write_csv(path, dest / "path.csv")
    dates = path.loc[~path["lead_in"] & (path["date"] >= keep_from), "date"]
    bl = pd.read_csv(C.out(cfg, "shared", "blocks.csv"))
    first, last = dates.iloc[0], dates.iloc[-1]
    bl["first_hist_month"] = [f"{first.year - s}-{first.month:02d}" for s in bl["shift_years"]]
    bl["last_hist_month"] = [f"{last.year - s}-{last.month:02d}" for s in bl["shift_years"]]
    write_csv(bl, dest / "blocks.csv")
    for f in FILES:
        d = pd.read_csv(C.out(cfg, "agriculture", f), parse_dates=["date"])
        write_csv(d[d["date"] >= keep_from], dest / f)
    eff = pd.read_csv(dest / "effects_16regions.csv", parse_dates=["date"])
    nino = set(src.loc[src["roni"] != 0, "date"])
    e = eff[eff["date"].isin(nino)].groupby("var")["effect_mean"].mean().rename(f"{scenario} {model}")
    return dest, e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--only", nargs="+", help="variant names (default: every scen_* variant)")
    ap.add_argument("--drop", type=int, default=0, help="leading zero months of each path table to leave out (default: none)")
    ap.add_argument("--handoff-only", action="store_true", help="only rewrite the hand-off from existing outputs")
    a = ap.parse_args(argv)
    names = a.only or [v for v in (C.load(a.config).get("variants") or {}) if v.startswith("scen_")]
    make_path, simulate = step("make_path.py"), step("simulate_path.py")
    summary = []
    for v in names:
        cfg = C.load(a.config, v)
        if cfg["path"].get("source") != "csv":
            raise SystemExit(f"variant {v}: path.source is not csv")
        print(f"\n=== {v} ({C.label(cfg)}) ===")
        base = ["--variant", v] + (["--config", a.config] if a.config else [])
        if not a.handoff_only:
            make_path(base + ["--no-refresh"])   # the cached indices (with lead_in: zero they are not used)
            simulate(base)
        dest, e = handoff(cfg, a.drop)
        summary.append(e)
        print(f"  hand-off: {dest.relative_to(ROOT)}")
    print("\nScenario minus neutral, mean over draws, regions and the El Nino months (agricultural weights):")
    print(pd.concat(summary, axis=1).T.round(3).to_string())


if __name__ == "__main__":
    main()
