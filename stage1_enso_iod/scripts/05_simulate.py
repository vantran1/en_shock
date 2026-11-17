#!/usr/bin/env python3
"""Step 5: simulated weather for the scenario and neutral paths, and the section outputs.

For every historical block Y_b (the same for all sections) and every month of the path, the CV residual map
of the block's year is added to the model prediction at every cell, back-transformed with the trend at t*,
and aggregated with each section's weights (Eq. 10). The neutral path x = 0 uses the same residuals.

Writes
  outputs/shared/blocks.csv
  outputs/agriculture/simulated_monthly_16regions.csv, deterministic_monthly_16regions.csv, effects_16regions.csv
  outputs/electricity/path_response_17regions.csv, shift_by_block_17regions.csv (Eq. 3), cells_path_response.csv.gz
  outputs/labour/T_response_monthly_17regions.csv, T_response_quarterly_17regions.csv
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import fit as F  # noqa: E402
from stage1 import paths, simulate  # noqa: E402
from stage1.outputs import update_metadata, write_csv  # noqa: E402
from stage1.regions import grid_of  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="a variant of config.yaml (e.g. roni_dmi): its own models and outputs")
    a = ap.parse_args(argv)
    cfg = C.load(a.config, a.variant)
    models = C.load_pickle(C.work(cfg, "models.pkl"), "scripts/03_fit_stage1.py")
    C.check_models(cfg, models)
    print(f"simulation, {C.label(cfg)}")
    D, variables, _ = F.load_data(cfg, refresh_indices=False)
    variables = [v for v in variables if all((v, m) in models for m in range(1, 13))]
    pp = C.out_in(cfg, "shared", "path.csv")
    if not pp.exists():
        raise SystemExit("outputs/shared/path.csv is missing: run scripts/04_make_path.py first")
    print(f"path: {pp}")
    path = pd.read_csv(pp, parse_dates=["date"]).set_index("date")
    dates = path.index[~path["lead_in"].to_numpy()]
    t_star = float(cfg["period"]["t_star"])
    blocks = paths.blocks(models, dates, variables)
    print(f"path {dates[0]:%Y-%m} to {dates[-1]:%Y-%m} ({len(dates)} months); {len(blocks)} historical blocks "
          f"({blocks['block_year'].min()}-{blocks['block_year'].max()}); t* = {t_star:g}")

    sec = F.weight_sets(cfg)
    ws_agri, ws_elec, ws_lab = sec["agriculture"][0], sec["electricity"][0], sec["labour"][0]
    wsets = list(dict.fromkeys([ws_agri, ws_elec, ws_lab]))
    ec = cfg["sections"]["electricity"]
    evars = [v for v in ec.get("variables", ["T"]) if v in variables]
    lvars = [v for v in cfg["sections"]["labour"].get("variables", ["T"]) if v in variables]
    with C.Timer("simulating"):
        res, cells_det, dates = simulate.run(D, models, path, blocks, variables, wsets, t_star,
                                             cell_vars=evars if ec.get("cell_level", True) else [])

    # shared
    bl = blocks.copy()
    bl["first_hist_month"] = [f"{dates[0].year - s}-{dates[0].month:02d}" for s in bl["shift_years"]]
    bl["last_hist_month"] = [f"{dates[-1].year - s}-{dates[-1].month:02d}" for s in bl["shift_years"]]
    write_csv(bl, C.out(cfg, "shared", "blocks.csv"))

    # agriculture
    write_csv(simulate.draws_table(D, ws_agri, res[ws_agri], dates, blocks),
              C.out(cfg, "agriculture", "simulated_monthly_16regions.csv"))
    write_csv(simulate.det_table(D, ws_agri, res[ws_agri], dates),
              C.out(cfg, "agriculture", "deterministic_monthly_16regions.csv"))
    eff = simulate.effect_summary(D, ws_agri, res[ws_agri], dates)
    write_csv(eff, C.out(cfg, "agriculture", "effects_16regions.csv"))

    # electricity: Eq. 3 of the electricity note
    grid = grid_of(cfg)
    regions, codes = D.regions(ws_elec)
    det = simulate.det_table(D, ws_elec, res[ws_elec], dates)
    keep = ["path", "date", "code", "region"] + evars
    pr = det[keep].pivot_table(index=["date", "code"], columns="path", values=evars)
    pr.columns = [f"{v}_{p}" for v, p in pr.columns]
    pr = pr.reset_index()
    pr.insert(2, "region", pr["code"].map(dict(zip(codes, regions))))
    pr.insert(3, "grid", pr["code"].map(grid))
    write_csv(pr, C.out(cfg, "electricity", "path_response_17regions.csv"))
    hp = C.out(cfg, "electricity", "hist_fitted_17regions.csv")
    if hp.exists():
        H = pd.read_csv(hp, parse_dates=["date"]).set_index(["date", "code"])
        rows = []
        for _, b in blocks.iterrows():
            for d in dates:
                hd = pd.Timestamp(d.year - int(b["shift_years"]), d.month, 1)
                sub = pr[pr["date"] == d].set_index("code")
                for c in codes:
                    r = dict(draw=int(b["draw"]), block_year=int(b["block_year"]), date=d, hist_date=hd, code=c, grid=grid.get(c))
                    for v in evars:
                        hf = H.loc[(hd, c), f"{v}_fitted"]
                        r[f"{v}_hist_fitted"] = hf
                        r[f"{v}_shift_scenario"] = sub.loc[c, f"{v}_scenario"] - hf
                        r[f"{v}_shift_neutral"] = sub.loc[c, f"{v}_neutral"] - hf
                    rows.append(r)
        write_csv(pd.DataFrame(rows), C.out(cfg, "electricity", "shift_by_block_17regions.csv"))
    if cells_det:
        cells = D.cells
        lat, lon = D.weights["lat"], D.weights["lon"]
        cmap = pd.read_csv(C.out_in(cfg, "shared", "cells.csv")).set_index("cell")
        L = len(dates)
        cd = pd.DataFrame({"date": np.repeat(dates.values, len(cells)), "cell": np.tile(cells, L),
                           "lat": np.tile(lat[cells // len(lon)], L), "lon": np.tile(lon[cells % len(lon)], L)})
        cd["code"] = cd["cell"].map(cmap["region17_majority_population"])
        cd["grid"] = cd["cell"].map(cmap["grid"])
        for v, arr in cells_det.items():
            cd[f"{v}_scenario"], cd[f"{v}_neutral"] = arr[0].reshape(-1), arr[1].reshape(-1)
        write_csv(cd, C.out(cfg, "electricity", "cells_path_response.csv.gz"))

    # labour: T response by region and month, and by quarter
    regions, codes = D.regions(ws_lab)
    det = simulate.det_table(D, ws_lab, res[ws_lab], dates)
    lr = det[["path", "date", "code", "region"] + lvars].pivot_table(index=["date", "code"], columns="path", values=lvars)
    lr.columns = [f"{v}_{p}" for v, p in lr.columns]
    lr = lr.reset_index()
    for v in lvars:
        lr[f"{v}_effect"] = lr[f"{v}_scenario"] - lr[f"{v}_neutral"]
    lr.insert(2, "region", lr["code"].map(dict(zip(codes, regions))))
    write_csv(lr, C.out(cfg, "labour", "T_response_monthly_17regions.csv"))
    lr["quarter"] = pd.PeriodIndex(lr["date"], freq="Q").astype(str)
    agg = {c: "mean" for c in lr.columns if any(c.startswith(f"{v}_") for v in lvars)}
    q = lr.groupby(["quarter", "code", "region"], as_index=False).agg({**agg, "date": "count"}).rename(columns={"date": "n_months"})
    write_csv(q, C.out(cfg, "labour", "T_response_quarterly_17regions.csv"))

    # NCR check of the electricity note (Section 3.2): NCR against the mean of Central Luzon and CALABARZON
    if "T" in lvars and {"NCR", "R03", "R04A"} <= set(codes):
        q2 = q.set_index(["quarter", "code"])["T_effect"].unstack()
        chk = pd.DataFrame({"NCR": q2["NCR"], "mean of R03 and R04A": q2[["R03", "R04A"]].mean(axis=1)})
        print("\nT effect (scenario - neutral, deg C) by quarter: NCR vs the mean of Central Luzon and CALABARZON")
        print(chk.round(3).to_string())

    # a quick look
    print("\nScenario minus neutral, mean over draws and regions (agricultural weights):")
    e = eff.assign(q=pd.PeriodIndex(eff["date"], freq="Q").astype(str))
    print(e.pivot_table(index="var", columns="q", values="effect_mean", aggfunc="mean").round(2).to_string())
    update_metadata(cfg, "05_simulate", dict(path=f"{dates[0]:%Y-%m} to {dates[-1]:%Y-%m}", n_blocks=int(len(blocks)),
                                             block_years=[int(blocks['block_year'].min()), int(blocks['block_year'].max())],
                                             t_star=t_star, variables=variables, weight_sets=wsets))


if __name__ == "__main__":
    main()
