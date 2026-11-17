#!/usr/bin/env python3
"""Step 3: fit Stage 1 on the ERA5 cells and verify it with each section's weights.

One EOF-CCA per variable and target month (Section 3.3.3), cross-validated leave-5-years-out, with the
configuration (lags, My, Mc) chosen by the mean CV Spearman correlation over the cells. The cell predictions
are then aggregated with the weights of each section for the regional skill. Also: nested CV, the joint
model as a check, the temperature coefficients for labour and, for each section, the historical fitted values.

  python scripts/03_fit_stage1.py              # full run (about 10 minutes with nested CV)
  python scripts/03_fit_stage1.py --quick      # 3 months x 3 variables, for a trial
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import engine as E  # noqa: E402
from stage1 import fit as F  # noqa: E402
from stage1.outputs import update_metadata, write_csv  # noqa: E402
from stage1.regions import grid_of  # noqa: E402
from stage1.verify import add_fdr, verify  # noqa: E402

QUARTER = {m: f"Q{(m - 1) // 3 + 1}" for m in range(1, 13)}
QUARTER_NAME = {"Q1": "JFM", "Q2": "AMJ", "Q3": "JAS", "Q4": "OND"}


def skill_rows(D, ws, var, month, obs, pred, cv):
    regions, codes = D.regions(ws)
    t = verify(obs, pred, codes).rename(columns={"column": "code"})
    t.insert(0, "weights", ws)
    t.insert(0, "cv", cv)
    t.insert(0, "month", month)
    t.insert(0, "var", var)
    t.insert(5, "region", regions)
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="a variant of config.yaml (e.g. roni_dmi): its own models and outputs")
    ap.add_argument("--quick", action="store_true", help="months 1, 4, 10 and variables P, T, SPEI3 only")
    ap.add_argument("--no-nested", action="store_true")
    ap.add_argument("--no-refresh", action="store_true", help="use the cached RONI and DMI")
    a = ap.parse_args(argv)
    cfg = C.load(a.config, a.variant)
    if cfg["_variant"] and cfg["_models_from"] != cfg["_variant"]:
        raise SystemExit(f"variant '{cfg['_variant']}' uses the models of '{cfg['_models_from']}': "
                         f"fit those with --variant {cfg['_models_from']}")
    print(f"Stage 1 fit, {C.label(cfg)}")
    mc = cfg["model"]
    D, variables, extra = F.load_data(cfg, refresh_indices=False if a.no_refresh else None)
    print(f"indices: RONI to {extra['index_info']['roni_last']}, DMI to {extra['index_info']['dmi_raw_last']}")
    months = [1, 4, 10] if a.quick else list(range(1, 13))
    if a.quick:
        variables = [v for v in ("P", "T", "SPEI3") if v in variables]
    nested = mc.get("nested_cv", True) and not a.no_nested
    wsets = F.all_weight_sets(cfg)
    sec_sets = F.weight_sets(cfg)
    main_sets = list(dict.fromkeys(s[0] for s in sec_sets.values()))
    cells = D.cells
    lat, lon = D.weights["lat"], D.weights["lon"]
    print(f"{len(variables)} variables x {len(months)} months on {len(cells)} cells; weight sets {wsets}; "
          f"nested CV {'on' if nested else 'off'}")

    models, diag, skill, cell_rows, hind, prob_rows = {}, {}, [], [], {}, []
    oos = {ws: {} for ws in main_sets}           # out-of-sample regional predictions, physical units
    t_all = time.time()
    for v in variables:
        t0 = time.time()
        for m in months:
            model, res = F.fit_one(D, v, m, wsets)
            models[(v, m)] = model
            diag[(v, m)] = dict(scores=res["scores"], cell_rho=res["cell_rho"], years=res["years"])
            for ws, (o, p) in res["regional"].items():
                skill.append(skill_rows(D, ws, v, m, o, p, "plain"))
                if ws in main_sets:
                    _, codes = D.regions(ws)
                    yy = res["years"].astype(int)
                    hind[(ws, v, m)] = pd.DataFrame({"weights": ws, "var": v, "month": m, "year": np.repeat(yy, len(codes)),
                                                     "code": np.tile(codes, len(yy)), "obs": o.reshape(-1),
                                                     "pred_cv": p.reshape(-1)})
                    oos[ws][(v, m)] = {"cv": res["regional_phys"][ws]}
            nres = None
            if nested:
                nres = F.nested_one(D, v, m, wsets, main_sets)
                diag[(v, m)]["nested_cell_rho"] = nres["cell_rho"]
                diag[(v, m)]["nested_configs"] = nres["chosen"]
                for ws, d in nres["regional"].items():
                    skill.append(skill_rows(D, ws, v, m, d["obs"], d["pred"], "nested"))
                for ws, pr in nres["prob"].items():
                    _, codes = D.regions(ws)
                    prob_rows.append(pd.DataFrame({"weights": ws, "var": v, "month": m, "code": codes,
                                                   "crps": pr["crps"].mean(0), "crps_clim": pr["crps_clim"].mean(0),
                                                   "coverage_10_90": pr["covered"].mean(0), "width_10_90": pr["width"].mean(0)}))
                diag[(v, m)]["nested_blocks"] = nres["held"]
                for ws in main_sets:
                    hind[(ws, v, m)]["pred_nested"] = nres["regional"][ws]["pred"].reshape(-1)
                    oos[ws][(v, m)]["nested"] = nres["regional"][ws]["phys"]
            cell_rows.append(pd.DataFrame({"var": v, "month": m, "cell": cells, "lat": lat[cells // len(lon)],
                                           "lon": lon[cells % len(lon)], "rho_cv": res["cell_rho"],
                                           "rho_nested": nres["cell_rho"] if nres else np.nan}))
        ms = np.mean([np.nanmean(diag[(v, m)]["cell_rho"]) for m in months])
        last = pd.concat(skill[-len(months) * len(wsets) * (2 if nested else 1):])
        rs = last[(last["cv"] == "plain") & (last["var"] == v)].groupby("weights")["spearman"].mean()
        rs = ", ".join(f"{k} {x:.3f}" for k, x in rs.items())
        print(f"  {v:7s} mean CV rho: cells {ms:.3f}; {rs}  [{time.time() - t0:.0f} s]", flush=True)
    print(f"fitted in {time.time() - t_all:.0f} s")

    # ---------------------------------------------------------------- skill tables
    SK = add_fdr(pd.concat(skill, ignore_index=True), mc.get("fdr_q", 0.10), by=("var", "cv", "weights"))
    for ws in wsets:
        write_csv(SK[SK["weights"] == ws].drop(columns="weights"), C.out(cfg, "skill", f"skill_{ws}.csv"))
    CR = pd.concat(cell_rows, ignore_index=True)
    write_csv(CR, C.out(cfg, "skill", "skill_cells.csv"))
    if hind:
        write_csv(pd.concat(hind.values(), ignore_index=True), C.out(cfg, "skill", "hindcasts.csv"))
    PR = pd.concat(prob_rows, ignore_index=True) if prob_rows else None
    if PR is not None:
        write_csv(PR, C.out(cfg, "skill", "probabilistic.csv"))

    best = "nested" if nested else "plain"
    rows = []
    for v in variables:
        for ws in wsets:
            s = SK[(SK["var"] == v) & (SK["weights"] == ws)]
            sp, sn = s[s["cv"] == "plain"], s[s["cv"] == best]
            r = {"var": v, "long_name": C.PREDICTANDS[v][0], "weights": ws,
                 "rho_cv": sp["spearman"].mean(), "rho_nested": sn["spearman"].mean() if nested else np.nan,
                 "pct_significant": 100 * sn["significant"].mean(), "rpss": sn["rpss"].mean(), "two_afc": sn["two_afc"].mean(),
                 "rho_cells_cv": CR[CR["var"] == v]["rho_cv"].mean(),
                 "rho_cells_nested": CR[CR["var"] == v]["rho_nested"].mean()}
            if PR is not None and ws in set(PR["weights"]):
                p = PR[(PR["var"] == v) & (PR["weights"] == ws)]
                r.update(crpss=1 - p["crps"].mean() / p["crps_clim"].mean(), coverage_10_90=100 * p["coverage_10_90"].mean(),
                         width_10_90=p["width_10_90"].mean())
            rows.append(r)
    SUM = pd.DataFrame(rows)
    write_csv(SUM, C.out(cfg, "skill", "skill_summary.csv"))
    print("\nSkill (mean over regions and months; nested CV where run):")
    piv = SUM.pivot(index="var", columns="weights", values="rho_nested" if nested else "rho_cv").loc[variables]
    piv["cells"] = SUM.groupby("var")["rho_cells_nested" if nested else "rho_cells_cv"].first()
    print(piv.round(3).to_string())

    cfgrows = []
    for (v, m), mdl in models.items():
        cfgrows.append(dict(var=v, month=m, lagset=mdl.lagset, My=mdl.My, Mc=mdl.Mc, n_years=len(mdl.years),
                            first_year=int(mdl.years.min()), last_year=int(mdl.years.max()),
                            cv_rho_cells=mdl.score, rho1=mdl.rho[0], rho2=mdl.rho[1] if len(mdl.rho) > 1 else np.nan,
                            transform=C.PREDICTANDS[v][3],
                            nested_configs="; ".join(f"{c[0]} {c[1]}/{c[2]}" for c in diag[(v, m)].get("nested_configs", []))))
    write_csv(pd.DataFrame(cfgrows), C.out(cfg, "shared", "model_configs.csv"))

    # ---------------------------------------------------------------- joint model check
    if mc.get("joint_check", True) and not a.quick:
        t0 = time.time()
        ws = sec_sets["agriculture"][0]
        jrows = []
        for m in months:
            jrows += F.joint_one(D, m, [v for v in variables if C.PREDICTANDS[v][4] == "monthly"], ws)
        J = pd.DataFrame(jrows)
        per = pd.DataFrame([dict(var=v, month=m, per_variable_cells_rho=np.nanmean(diag[(v, m)]["cell_rho"]),
                                 per_variable_regional_rho=SK[(SK["var"] == v) & (SK["month"] == m) & (SK["weights"] == ws)
                                                              & (SK["cv"] == "plain")]["spearman"].mean())
                            for v in J["var"].unique() for m in months])
        J = J.merge(per, on=["var", "month"])
        J["delta_regional"] = J["joint_regional_rho"] - J["per_variable_regional_rho"]
        write_csv(J, C.out(cfg, "skill", "joint_check.csv"))
        print(f"\nJoint model check ({time.time() - t0:.0f} s), mean CV rho on {ws} (per variable vs joint):")
        print(J.groupby("var")[["per_variable_regional_rho", "joint_regional_rho", "delta_regional"]].mean().round(3).to_string())

    # ---------------------------------------------------------------- electricity: historical fitted values
    grid = grid_of(cfg)
    ec = cfg["sections"]["electricity"]
    ews = sec_sets["electricity"][0]
    evars = [v for v in ec.get("variables", ["T"]) if v in variables]
    regions, codes = D.regions(ews)
    cframes = []
    if ec.get("cell_level", True):
        for v in evars:
            for m in months:
                years, phys = F.historical_fitted(D, models[(v, m)])
                _, Y, _ = D.month_data(v, m)
                dates = pd.to_datetime(pd.DataFrame({"year": years.astype(int), "month": m, "day": 1}))
                cframes.append(pd.DataFrame({"var": v, "date": np.repeat(dates.values, len(cells)),
                                             "cell": np.tile(cells, len(years)), "obs": Y.reshape(-1), "fitted": phys.reshape(-1)}))
    if evars:
        H = F.hist_fitted_table(D, models, ews, evars, months, oos[ews])
        H.insert(3, "grid", H["code"].map(grid))
        write_csv(H, C.out(cfg, "electricity", "hist_fitted_17regions.csv"))
        if cframes:
            HC = pd.concat(cframes).pivot_table(index=["date", "cell"], columns="var", values=["obs", "fitted"]).sort_index()
            HC.columns = [f"{v}_{k}" for k, v in HC.columns]
            write_csv(HC.reset_index(), C.out(cfg, "electricity", "cells_hist_fitted.csv.gz"))

    # ---------------------------------------------------------------- agriculture: historical fitted values
    aws = sec_sets["agriculture"][0]
    avars = [v for v in variables if all((v, m) in models for m in months)]
    if avars:
        write_csv(F.hist_fitted_table(D, models, aws, avars, months, oos[aws]), C.out(cfg, "agriculture", "hist_fitted_16regions.csv"))
    lws = sec_sets["labour"][0]
    lv0 = [v for v in cfg["sections"]["labour"].get("variables", ["T"]) if v in variables]
    if lv0:
        write_csv(F.hist_fitted_table(D, models, lws, lv0, months, oos[lws]), C.out(cfg, "labour", "hist_fitted_17regions.csv"))

    # ---------------------------------------------------------------- labour: temperature coefficients
    lc = cfg["sections"]["labour"]
    lvars = [v for v in lc.get("variables", ["T"]) if v in variables and C.PREDICTANDS[v][3] == "none"]
    crow, qrow = [], []
    B = int(mc.get("n_boot_coef", 200)) if not a.quick else 20
    for ws in sec_sets["labour"]:
        regions, codes = D.regions(ws)
        W = D.W(ws)
        for v in lvars:
            boots = F.bootstrap_coefficients(D, v, models, W, B, mc.get("seed", 42)) if B else {}
            per_q = {}
            for m in months:
                mdl = models[(v, m)]
                c = F.linear_coefficients(mdl, W)               # (regions, predictors)
                names = mdl.x_names()
                pn = mdl.predictors
                sus = F.sustained(c, len(pn))
                bs = boots.get(m)
                bsus = F.sustained(bs, len(pn)) if bs is not None else None
                for i, code in enumerate(codes):
                    r = dict(weights=ws, var=v, month=m, quarter=QUARTER[m], code=code, region=regions[i], lagset=mdl.lagset)
                    for j, nm in enumerate(names):
                        r[f"coef_{nm}"] = c[i, j]
                    for j, nm in enumerate(pn):
                        r[f"sustained_{nm}"] = sus[i, j]
                    if bsus is not None:
                        for j, nm in enumerate(pn):
                            r[f"sustained_{nm}_p05"], r[f"sustained_{nm}_p95"] = np.quantile(bsus[:, i, j], [0.05, 0.95])
                    crow.append(r)
                per_q.setdefault(QUARTER[m], []).append((sus, bsus))
            for q, lst in per_q.items():
                sus = np.mean([s for s, _ in lst], axis=0)
                bq = np.mean([b for _, b in lst], axis=0) if lst[0][1] is not None else None
                for i, code in enumerate(codes):
                    r = dict(weights=ws, var=v, quarter=q, months=QUARTER_NAME[q], n_months=len(lst), code=code,
                             region=regions[i], **{f"sustained_{nm}": sus[i, j] for j, nm in enumerate(D.predictors)})
                    if bq is not None:
                        for j, nm in enumerate(D.predictors):
                            r[f"sustained_{nm}_p05"], r[f"sustained_{nm}_p95"] = np.quantile(bq[:, i, j], [0.05, 0.95])
                    qrow.append(r)
    if crow:
        write_csv(pd.DataFrame(crow), C.out(cfg, "labour", "T_coefficients_monthly_17regions.csv"))
        write_csv(pd.DataFrame(qrow), C.out(cfg, "labour", "T_coefficients_quarterly_17regions.csv"))

    C.save(models, C.work(cfg, "models.pkl"))
    C.save(diag, C.work(cfg, "fit_diagnostics.pkl"))
    update_metadata(cfg, "03_fit_stage1", dict(
        variables=variables, months=months, quick=a.quick, nested_cv=nested, weight_sets=wsets,
        variant=cfg["_variant"], predictors=list(D.predictors), nested_blocks=F.nested_settings(cfg),
        n_cells=int(len(cells)), indices=extra["index_info"], t_ref=E.T_REF,
        settings={k: mc[k] for k in ("cv_window", "my_grid", "mc_grid", "lag_sets", "detrend_predictors")},
        weights={ws: D.weights["sets"][ws.split("_", 1)[0]]["flags"][ws.split("_", 1)[1]] for ws in wsets}))
    print("Next: python scripts/04_make_path.py, then 05_simulate.py")


if __name__ == "__main__":
    main()
