#!/usr/bin/env python3
"""Labour, shocks (scripts/06_labour.py runs it): labour-productivity shocks of the scenario path, by simulation (labour note, Sections 6-12).

For every historical block Y_b (the blocks of scripts/04_simulate.py when it has been run, so that the three channels share
one weather path per draw) and every month d of the path:

  1. take the hourly WBGT of the working hours of the block's month, at every cell, in the sun and in the shade;
  2. shift every hour by  D(r) = D50 + (D90 - D50) (r - 50) / 40, where r is the hour's percentile within the
     cell and month, and D50 and D90 are the shifts of the median and of the 90th percentile from the WBGT
     EOF-CCA of step 7:  Dq = W_hat_q(x; t*) - W_hat_q(x_obs(Y_b); Y_b).  This removes the effect of the block's
     own RONI, DMI and trend and adds that of the scenario path (x = x^S) or of the neutral path (x = 0) in
     today's climate t* (Section 11.1);
  3. apply the Hothaps capacity function (pythermalcomfort) to every hour and average over the hours of the
     month (Eq. 8), for heavy, moderate and light work;
  4. average the cells to the 17 regions, combine the regions with the employment of each sector and the
     services assumptions of Table 2a (Eqs. 17a-19a), and average the months of each quarter.

The shock of a draw is 1 - capacity(scenario) / capacity(neutral) (Eqs. 3, 12, 13 and 19).

Writes in outputs/labour/:
  shocks_quarterly.csv            sector x quarter x case: mean and quantiles of the shock across draws
  shocks_monthly.csv              the same by month (central case)
  shocks_by_draw_quarterly.csv    the central case for every draw
  capacity_regional_monthly.csv   regional capacity by environment and intensity, neutral and scenario
  wbgt_shift_monthly.csv          the shifts D50 and D90 of the scenario against neutral, by region
  employment_shares.csv           the employment figures and shares used

  python scripts/helpers/labour_shocks.py
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import fit as F  # noqa: E402
from stage1 import labour as L  # noqa: E402
from stage1 import paths, simulate  # noqa: E402
from stage1 import wbgt as WB  # noqa: E402
from stage1.outputs import update_metadata, write_csv  # noqa: E402

SECTORS = ["agriculture", "electricity", "other", "construction", "industry", "services"]
NOTE = {"agriculture": "reference only: the note sets the agricultural input to zero (Section 9)",
        "electricity": "input to DEFINE-PH", "other": "input to DEFINE-PH",
        "construction": "part of other", "industry": "part of other", "services": "part of other"}


def percentile_rank(V: np.ndarray) -> np.ndarray:
    """Percentile (0-100) of every hour within its cell: V is (hours, cells)."""
    n = V.shape[0]
    return (np.argsort(np.argsort(V, axis=0, kind="stable"), axis=0) + 0.5) / n * 100.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--variant", help="a variant of config.yaml (e.g. roni_dmi): its own models and outputs")
    a = ap.parse_args(argv)
    cfg = C.load(a.config, a.variant)
    S = WB.settings(cfg)
    q50, q90 = (float(p) for p in S["percentiles"])
    models = C.load_pickle(C.work(cfg, "models_wbgt.pkl"), "scripts/helpers/labour_fit_wbgt.py")
    C.check_models(cfg, models, "models_wbgt.pkl")
    print(f"labour shocks, {C.label(cfg)}")
    FW = C.load_pickle(C.work(cfg, "fields_wbgt.pkl"), "scripts/helpers/labour_wbgt_hourly.py")
    D0, _, _ = F.load_data(cfg, refresh_indices=False)
    D = F.Data(cfg, FW["fields"], D0.cwb_clim, D0.weights, D0.P)
    cells, lat, lon = D.cells, D.weights["lat"], D.weights["lon"]
    pp = C.out_in(cfg, "shared", "path.csv")
    if not pp.exists():
        raise SystemExit("outputs/shared/path.csv is missing: run python scripts/04_simulate.py first")
    path = pd.read_csv(pp, parse_dates=["date"]).set_index("date")
    dates = path.index[~path["lead_in"].to_numpy()]
    t_star = float(cfg["period"]["t_star"])
    store = C.work(cfg, "wbgt_hourly")
    qvars = [f"WBGT{e}_P{int(q)}" for e in WB.ENVS for q in (q50, q90)]

    # ---------------------------------------------------------------- blocks: those of step 5 when available
    bp = C.out_in(cfg, "shared", "blocks.csv")
    cand = paths.blocks(models, dates, qvars)
    if bp.exists():
        shared = pd.read_csv(bp)
        blocks = shared[shared["shift_years"].isin(cand["shift_years"])].reset_index(drop=True)
        src = "the blocks of step 5 (outputs/shared/blocks.csv)"
    else:
        blocks, src = cand, "blocks from the WBGT models (step 5 has not been run)"
    ok = [all(WB.store_path(store, pd.Timestamp(d.year - int(s), d.month, 1)).exists() for d in dates) for s in blocks["shift_years"]]
    blocks = blocks[ok].reset_index(drop=True)
    if not len(blocks):
        raise SystemExit("no historical block has hourly WBGT for every month of the path (step 6)")
    nb = len(blocks)
    print(f"path {dates[0]:%Y-%m} to {dates[-1]:%Y-%m} ({len(dates)} months); {nb} draws, {src}; t* = {t_star:g}")

    # ---------------------------------------------------------------- weights and tables
    ws_main, *ws_alt = F.weight_sets(cfg)["labour"]
    regions, codes = D.regions(ws_main)
    Wsets = {"employment, " + ws_main.split("_", 1)[1] + " weights within regions": D.W(ws_main)}
    if ws_alt:
        Wsets["employment, " + ws_alt[0].split("_", 1)[1] + " weights within regions"] = D.W(ws_alt[0])
    cosw = np.cos(np.deg2rad(lat[cells // len(lon)]))
    Wsets["national area average of the cells (Eq. 9, no regional employment)"] = np.tile(cosw / cosw.sum(), (len(codes), 1))
    wnames = list(Wsets)
    ld = C.path(cfg, "labour_dir")
    emp, emp_year = L.read_regional_employment(ld / cfg["labour"]["regional_employment_table"], cfg["labour"].get("employment_year", "latest"))
    emp = emp.loc[codes]
    svc = L.read_services_table(ld / cfg["labour"]["services_table"])
    print(f"employment: PSA Table 11.9, {emp_year}; services assumptions: {cfg['labour']['services_table']}")

    hist = {}                                                         # fitted response to the observed indices, by year
    for k in models:
        if k[0] in qvars:
            yy, ph = F.historical_fitted(D, models[k])
            hist[k] = dict(zip(yy.astype(int), ph))
    nE, nI, nR, nL = len(WB.ENVS), len(WB.INTENSITIES), len(codes), len(dates)
    Creg = np.empty((len(wnames), 2, nb, nL, nE, nI, nR))            # weights, path (scenario, neutral), draw, month
    shift = np.zeros((2, nL, nE, nR))                                 # D50, D90 of scenario minus neutral, regional
    Wm = Wsets[wnames[0]]

    with C.Timer("simulating the hourly WBGT and the work capacity"):
        for j, d in enumerate(dates):
            resp = {}
            for ke, e in enumerate(WB.ENVS):
                for q in (q50, q90):
                    mdl = models[(f"WBGT{e}_P{int(q)}", d.month)]
                    resp[(ke, q)] = [mdl.physical(simulate.x_vector(mdl, path, d, neutral), t_star)[0] for neutral in (False, True)]
                shift[0, j, ke] = (resp[(ke, q50)][0] - resp[(ke, q50)][1]) @ Wm.T
                shift[1, j, ke] = (resp[(ke, q90)][0] - resp[(ke, q90)][1]) @ Wm.T
            for b, sh in enumerate(blocks["shift_years"].to_numpy()):
                hy = d.year - int(sh)
                W = WB.load_month(WB.store_path(store, pd.Timestamp(hy, d.month, 1)), cells)
                W = W[:, np.isfinite(W).all(axis=(0, 2, 3))]
                for ke, e in enumerate(WB.ENVS):
                    V = W[ke].reshape(-1, len(cells)).astype(float)
                    r = (percentile_rank(V) - q50) / (q90 - q50)
                    h50 = hist[(f"WBGT{e}_P{int(q50)}", d.month)][hy]
                    h90 = hist[(f"WBGT{e}_P{int(q90)}", d.month)][hy]
                    for p in range(2):
                        d50, d90 = resp[(ke, q50)][p] - h50, resp[(ke, q90)][p] - h90
                        Vs = V + d50 + (d90 - d50) * r
                        for ki, it in enumerate(WB.INTENSITIES):
                            c = WB.hothaps(Vs, it).mean(axis=0)                     # Eq. 8, equal weights
                            for kw, name in enumerate(wnames):
                                Creg[kw, p, b, j, ke, ki] = c @ Wsets[name].T
            if (j + 1) % 4 == 0 or j + 1 == nL:
                print(f"  {d:%Y-%m}", flush=True)

    # ---------------------------------------------------------------- sectors, quarters, shocks
    qlab, qpos, days = L.quarters_of(dates)
    quant = [float(x) for x in cfg["labour"].get("quantiles", [0.05, 0.5, 0.9, 0.95])]

    def summarise(sc, cs, cn):
        out = dict(shock_mean=sc.mean(), capacity_neutral=cn.mean(), capacity_scenario=cs.mean())
        out.update({f"shock_q{int(round(100 * x)):02d}": np.quantile(sc, x) for x in quant})
        return out

    def quarterly(X):                                                  # [..., month] -> [..., quarter], day weights
        return np.stack([(X[..., ix] * days[ix]).sum(-1) / days[ix].sum() for ix in qpos], axis=-1)

    rows_q, rows_m, rows_d = [], [], []
    for kw, wn in enumerate(wnames):
        for case in (L.CASES if kw == 0 else ["central"]):
            cap = L.sector_capacity(Creg[kw], emp, svc, case)          # sector -> [path, draw, month]
            label = case if kw == 0 else ("area_weights_in_regions" if "area weights within" in wn else "national_area_average")
            for sct in SECTORS:
                Cq = quarterly(cap[sct])
                sq = 1 - Cq[0] / Cq[1]                                 # [draw, quarter]
                for k, ql in enumerate(qlab):
                    rows_q.append(dict(sector=sct, quarter=ql, case=label, **summarise(sq[:, k], Cq[0][:, k], Cq[1][:, k]),
                                       n_draws=nb, use=NOTE[sct]))
                if label == "central":
                    sm = 1 - cap[sct][0] / cap[sct][1]
                    for jm, dm in enumerate(dates):
                        rows_m.append(dict(sector=sct, date=dm, **summarise(sm[:, jm], cap[sct][0][:, jm], cap[sct][1][:, jm])))
                    for b in range(nb):
                        for k, ql in enumerate(qlab):
                            rows_d.append(dict(sector=sct, quarter=ql, draw=int(blocks["draw"].iloc[b]),
                                               block_year=int(blocks["block_year"].iloc[b]), shock=sq[b, k],
                                               capacity_scenario=Cq[0][b, k], capacity_neutral=Cq[1][b, k]))
    SQ = pd.DataFrame(rows_q)
    write_csv(SQ, C.out(cfg, "labour", "shocks_quarterly.csv"))
    write_csv(pd.DataFrame(rows_m), C.out(cfg, "labour", "shocks_monthly.csv"))
    write_csv(pd.DataFrame(rows_d), C.out(cfg, "labour", "shocks_by_draw_quarterly.csv"))

    mean_c = Creg[0].mean(axis=1)                                      # [path, month, env, intensity, region]
    rows = []
    for jm, dm in enumerate(dates):
        for ke, e in enumerate(WB.ENVS):
            for ki, it in enumerate(WB.INTENSITIES):
                for kr, cd in enumerate(codes):
                    rows.append(dict(date=dm, code=cd, region=regions[kr], environment=WB.ENV_NAME[e], intensity=it,
                                     capacity_neutral=mean_c[1, jm, ke, ki, kr], capacity_scenario=mean_c[0, jm, ke, ki, kr],
                                     shock=1 - mean_c[0, jm, ke, ki, kr] / mean_c[1, jm, ke, ki, kr]))
    write_csv(pd.DataFrame(rows), C.out(cfg, "labour", "capacity_regional_monthly.csv"))
    rows = [dict(date=dm, code=cd, region=regions[kr], environment=WB.ENV_NAME[e],
                 shift_median=shift[0, jm, ke, kr], shift_p90=shift[1, jm, ke, kr])
            for jm, dm in enumerate(dates) for ke, e in enumerate(WB.ENVS) for kr, cd in enumerate(codes)]
    write_csv(pd.DataFrame(rows), C.out(cfg, "labour", "wbgt_shift_monthly.csv"))
    es = L.employment_shares(emp)
    es.insert(0, "year", emp_year)
    write_csv(es, C.out(cfg, "labour", "employment_shares.csv"))

    pd.set_option("display.width", 200)
    cen = SQ[SQ["case"] == "central"]
    print("\nShock by quarter, central case, mean across draws (per cent of baseline productivity):")
    print((100 * cen.pivot(index="sector", columns="quarter", values="shock_mean").reindex(SECTORS)).round(3).to_string())
    print("\nOther sector, by case (per cent):")
    print((100 * SQ[SQ["sector"] == "other"].pivot(index="case", columns="quarter", values="shock_mean")).round(3).to_string())
    update_metadata(cfg, "08_labour_shocks", dict(path=f"{dates[0]:%Y-%m} to {dates[-1]:%Y-%m}", quarters=qlab, n_draws=nb,
                                                  blocks=src, t_star=t_star, employment_year=emp_year, weights=wnames,
                                                  wbgt=S))


if __name__ == "__main__":
    main()
