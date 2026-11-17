"""Simulated weather under the scenario path and the neutral path (Eq. 10 with residual draws).

For draw b and path month d: W_b(x) = T^-1(mu + zeta t* + sigma [y_hat(x_d) + e_b(d)]) at every cell, where
e_b(d) is the CV residual map of historical month d - shift_b years. The same residual map is used for the
scenario and the neutral path, for every variable, and across all cells; the cells are then aggregated with
each section's weights. The deterministic response uses e = 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .fit import Data


def x_vector(model, path: pd.DataFrame, d: pd.Timestamp, neutral: bool = False) -> np.ndarray:
    if neutral:
        return np.zeros(len(model.x_names()))
    x = []
    for L in model.lags:
        t = d - pd.DateOffset(months=L)
        x += [path.loc[t, v] for v in model.predictors]
    return np.array(x, float)


def run(D: Data, models: dict, path: pd.DataFrame, blocks: pd.DataFrame, variables: list[str], wsets: list[str],
        t_star: float, cell_vars: list[str] = ()):
    """Returns per weight set: draws (dict var -> array [path(2), draw, month, region]), deterministic
    (dict var -> [path(2), month, region]); and cell-level deterministic responses for `cell_vars`."""
    dates = path.index[~path["lead_in"].to_numpy()]
    nb = len(blocks)
    res = {ws: {"draws": {}, "det": {}} for ws in wsets}
    cells_det = {}
    for v in variables:
        for ws in wsets:
            R = len(D.regions(ws)[0])
            res[ws]["draws"][v] = np.empty((2, nb, len(dates), R))
            res[ws]["det"][v] = np.empty((2, len(dates), R))
            if v == "SPEI3":
                res[ws]["draws"]["CWB3"] = np.empty((2, nb, len(dates), R))
                res[ws]["det"]["CWB3"] = np.empty((2, len(dates), R))
        if v in cell_vars:
            cells_det[v] = np.empty((2, len(dates), len(D.cells)))
        for j, d in enumerate(dates):
            mdl = models[(v, d.month)]
            pos = np.searchsorted(mdl.years.astype(int), d.year - blocks["shift_years"].to_numpy())
            Eb = mdl.cv_resid[pos].astype(float)                             # (draws, cells)
            for p, neutral in enumerate((False, True)):
                y = mdl.predict_std(x_vector(mdl, path, d, neutral), t_star)[0]
                W_draw = mdl.prep.to_physical(y + Eb, t_star)                   # (draws, cells)
                W_det = mdl.prep.to_physical(y[None, :], t_star)[0]
                if v in cell_vars:
                    cells_det[v][p, j] = W_det
                for ws in wsets:
                    agg = D.aggregator(ws, v, d.month)
                    a_draw, a_det = agg(W_draw), agg(W_det[None, :])[0]
                    res[ws]["draws"][v][p, :, j] = a_draw
                    res[ws]["det"][v][p, j] = a_det
                    if v == "SPEI3":
                        res[ws]["draws"]["CWB3"][p, :, j] = D.cwb3_from_spei3(ws, d.month, a_draw)
                        res[ws]["det"]["CWB3"][p, j] = D.cwb3_from_spei3(ws, d.month, a_det)
    return res, cells_det, dates


def draws_table(D: Data, ws: str, r: dict, dates, blocks: pd.DataFrame) -> pd.DataFrame:
    regions, codes = D.regions(ws)
    keys = list(r["draws"])
    nb, L, R = len(blocks), len(dates), len(regions)
    base = pd.DataFrame({
        "path": np.repeat(["scenario", "neutral"], nb * L * R),
        "draw": np.tile(np.repeat(blocks["draw"].to_numpy(), L * R), 2),
        "block_year": np.tile(np.repeat(blocks["block_year"].to_numpy(), L * R), 2),
        "date": np.tile(np.repeat(dates.values, R), 2 * nb),
        "code": np.tile(codes, 2 * nb * L), "region": np.tile(regions, 2 * nb * L),
    })
    shift = np.tile(np.repeat(blocks["shift_years"].to_numpy(), L * R), 2)
    dt = pd.to_datetime(base["date"])
    base["hist_date"] = pd.to_datetime(pd.DataFrame({"year": dt.dt.year - shift, "month": dt.dt.month, "day": 1}))
    for k in keys:
        base[k] = r["draws"][k].reshape(-1)
    return base


def det_table(D: Data, ws: str, r: dict, dates) -> pd.DataFrame:
    regions, codes = D.regions(ws)
    L, R = len(dates), len(regions)
    base = pd.DataFrame({"path": np.repeat(["scenario", "neutral"], L * R), "date": np.tile(np.repeat(dates.values, R), 2),
                         "code": np.tile(codes, 2 * L), "region": np.tile(regions, 2 * L)})
    for k, a in r["det"].items():
        base[k] = a.reshape(-1)
    return base


def effect_summary(D: Data, ws: str, r: dict, dates) -> pd.DataFrame:
    """Scenario minus neutral per variable, region and month: mean over draws, 10th and 90th percentiles,
    and the deterministic difference."""
    regions, codes = D.regions(ws)
    rows = []
    for k, a in r["draws"].items():
        diff = a[0] - a[1]                                                  # (draws, months, regions)
        det = r["det"][k][0] - r["det"][k][1]
        neu = a[1].mean(0)
        for j, d in enumerate(dates):
            for i, c in enumerate(codes):
                rows.append(dict(var=k, date=d, code=c, region=regions[i], neutral_mean=neu[j, i],
                                 effect_mean=diff[:, j, i].mean(), effect_q10=np.quantile(diff[:, j, i], 0.1),
                                 effect_q90=np.quantile(diff[:, j, i], 0.9), effect_deterministic=det[j, i]))
    out = pd.DataFrame(rows)
    units = {**{k: v[1] for k, v in C.PREDICTANDS.items()}, **{k: v[1] for k, v in C.EXTRA_COLUMNS.items()}}
    out.insert(1, "units", out["var"].map(units))
    return out
