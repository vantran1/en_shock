#!/usr/bin/env python3
"""Labour, fit (scripts/06_labour.py runs it): EOF-CCA of the monthly WBGT statistics on RONI and DMI, with the same engine, lag sets and
cross-validation as step 3.

Predictands, per cell: the median (P50) and the 90th percentile (P90) of WBGT over the working hours of the
month and the mean daily maximum (DMAX, Eq. 20 of the labour note), in the sun and in the shade. P50 and P90
drive the shift of the hourly distribution in step 8 (Section 11.1); DMAX is fitted for the skill report.

Writes outputs/shared/work/models_wbgt.pkl and, in outputs/labour/:
  wbgt_skill_summary.csv, wbgt_skill_17regions.csv, wbgt_skill_cells.csv   hindcast skill (plain and nested CV)
  wbgt_model_configs.csv                                                   lag set, My and Mc of each model
  wbgt_hist_fitted_17regions.csv                                           fitted next to observed, every month

  python scripts/helpers/labour_fit_wbgt.py
  python scripts/helpers/labour_fit_wbgt.py --no-nested     # faster, plain cross-validation only
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import fit as F  # noqa: E402
from stage1 import wbgt as WB  # noqa: E402
from stage1.outputs import update_metadata, write_csv  # noqa: E402
from stage1.verify import add_fdr, verify  # noqa: E402


def skill_rows(D, ws, var, month, obs, pred, cv):
    regions, codes = D.regions(ws)
    t = verify(obs, pred, codes).rename(columns={"column": "code"})
    for k, v in (("weights", ws), ("cv", cv), ("month", month), ("var", var)):
        t.insert(0, k, v)
    t.insert(5, "region", regions)
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="a variant of config.yaml (e.g. roni_dmi): its own models and outputs")
    ap.add_argument("--no-nested", action="store_true")
    ap.add_argument("--no-refresh", action="store_true", help="use the cached RONI and DMI")
    a = ap.parse_args(argv)
    cfg = C.load(a.config, a.variant)
    if cfg["_variant"] and cfg["_models_from"] != cfg["_variant"]:
        raise SystemExit(f"variant '{cfg['_variant']}' uses the models of '{cfg['_models_from']}': "
                         f"fit those with --variant {cfg['_models_from']}")
    print(f"WBGT fit, {C.label(cfg)}")
    mc = cfg["model"]
    D0, _, extra = F.load_data(cfg, refresh_indices=False if a.no_refresh else None)
    FW = C.load_pickle(C.work(cfg, "fields_wbgt.pkl"), "scripts/helpers/labour_wbgt_hourly.py")
    D = F.Data(cfg, FW["fields"], D0.cwb_clim, D0.weights, D0.P)
    variables = [v for v in WB.METRICS if v in FW["fields"]]
    nested = bool(mc.get("nested_cv", True)) and not a.no_nested
    wsets = F.weight_sets(cfg)["labour"]
    main_ws = wsets[0]
    months = list(range(1, 13))
    cells, lat, lon = D.cells, D.weights["lat"], D.weights["lon"]
    ny = FW["fields"][variables[0]].dropna(how="any").index.year.nunique()
    print(f"{len(variables)} WBGT statistics x 12 months on {len(cells)} cells, {ny} years; weight sets {wsets}; "
          f"nested CV {'on' if nested else 'off'}")
    if ny < 30:
        raise SystemExit(f"only {ny} years of WBGT: the EOF-CCA needs the whole hourly record (step 6)")

    models, skill, cell_rows, cfgrows, prob, oos = {}, [], [], [], [], {}
    rule = F.lag_rule(cfg)
    for v in variables:
        t0 = time.time()
        packs, chosen = {}, {}
        if rule["kind"] == "window":                 # the lag choice of Stage 1 (model.lag_choice)
            packs = {m: F.cv_month(D, v, m) for m in months}
            chosen = F.window_choice({m: F.E.select(p["cv"])[2] for m, p in packs.items()}, rule["width"])
        nested_all = F.nested_var(D, v, months, wsets, [main_ws]) if nested else {}
        for m in months:
            model, res = F.fit_one(D, v, m, wsets, pack=packs.pop(m, None), cfg=chosen.get(m))
            models[(v, m)] = model
            for ws, (o, p) in res["regional"].items():
                skill.append(skill_rows(D, ws, v, m, o, p, "plain"))
            oos[(v, m)] = {"cv": res["regional_phys"][main_ws]}
            nres = nested_all.pop(m) if nested else None
            if nres:
                for ws, d in nres["regional"].items():
                    skill.append(skill_rows(D, ws, v, m, d["obs"], d["pred"], "nested"))
                oos[(v, m)]["nested"] = nres["regional"][main_ws]["phys"]
                pr = nres["prob"][main_ws]
                prob.append(dict(var=v, month=m, crps=pr["crps"].mean(), crps_clim=pr["crps_clim"].mean(),
                                 coverage_10_90=100 * pr["covered"].mean()))
            cell_rows.append(pd.DataFrame({"var": v, "month": m, "cell": cells, "lat": lat[cells // len(lon)],
                                           "lon": lon[cells % len(lon)], "rho_cv": res["cell_rho"],
                                           "rho_nested": nres["cell_rho"] if nres else np.nan}))
            cfgrows.append(dict(var=v, month=m, lagset=model.lagset, My=model.My, Mc=model.Mc, n_years=len(model.years),
                                first_year=int(model.years.min()), last_year=int(model.years.max()),
                                cv_rho_cells=model.score, rho1=model.rho[0]))
        print(f"  {v:13s} mean CV rho at the cells {np.mean([r['cv_rho_cells'] for r in cfgrows[-12:]]):.3f}  "
              f"[{time.time() - t0:.0f} s]", flush=True)
    C.save(models, C.work(cfg, "models_wbgt.pkl"))

    SK = add_fdr(pd.concat(skill, ignore_index=True), mc.get("fdr_q", 0.10), by=("var", "cv", "weights"))
    write_csv(SK, C.out(cfg, "labour", "wbgt_skill_17regions.csv"))
    CR = pd.concat(cell_rows, ignore_index=True)
    write_csv(CR, C.out(cfg, "labour", "wbgt_skill_cells.csv"))
    write_csv(pd.DataFrame(cfgrows), C.out(cfg, "labour", "wbgt_model_configs.csv"))
    best = "nested" if nested else "plain"
    PR = pd.DataFrame(prob)
    rows = []
    for v in variables:
        for ws in wsets:
            s = SK[(SK["var"] == v) & (SK["weights"] == ws)]
            sp, sn = s[s["cv"] == "plain"], s[s["cv"] == best]
            r = dict(var=v, long_name=C.PREDICTANDS[v][0], weights=ws, rho_cv=sp["spearman"].mean(),
                     rho_nested=sn["spearman"].mean() if nested else np.nan, pct_significant=100 * sn["significant"].mean(),
                     rho_cells_cv=CR[CR["var"] == v]["rho_cv"].mean(), rho_cells_nested=CR[CR["var"] == v]["rho_nested"].mean())
            if len(PR) and ws == main_ws:
                p = PR[PR["var"] == v]
                r.update(crpss=1 - p["crps"].mean() / p["crps_clim"].mean(), coverage_10_90=p["coverage_10_90"].mean())
            rows.append(r)
    SUM = pd.DataFrame(rows)
    write_csv(SUM, C.out(cfg, "labour", "wbgt_skill_summary.csv"))
    write_csv(F.hist_fitted_table(D, models, main_ws, variables, months, oos), C.out(cfg, "labour", "wbgt_hist_fitted_17regions.csv"))
    print(f"\nSkill, mean over regions and months ({best} CV), weights {main_ws}:")
    print(SUM[SUM["weights"] == main_ws].set_index("var").drop(columns=["long_name", "weights"]).round(3).to_string())
    by_m = SK[(SK["cv"] == best) & (SK["weights"] == main_ws)].pivot_table(index="var", columns="month", values="spearman")
    print("\nBy target month:\n" + by_m.reindex(variables).round(2).to_string())
    update_metadata(cfg, "07_fit_wbgt", dict(variables=variables, nested=nested, weights=wsets,
                                             lag_sets=cfg["model"]["lag_sets"],
                                             indices={k: str(x) for k, x in extra["index_info"].items()}))
    print("Next: python scripts/helpers/labour_shocks.py (needs outputs/shared/path.csv from scripts/04_simulate.py)")


if __name__ == "__main__":
    main()
