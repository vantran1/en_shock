"""Fitting Stage 1 on the grid: one EOF-CCA per variable and target month, selected on the cells, then
aggregated with each section's weights for the regional skill. Also the nested cross-validation, the joint
model check, the temperature coefficients for labour and the historical fitted values for electricity."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C
from . import engine as E
from . import indices as I
from .verify import crps_sample


# ------------------------------------------------------------------ data container
@dataclass
class Data:
    cfg: dict
    fields: dict                      # var -> DataFrame (months x cells), physical units
    cwb_clim: tuple                   # cells' CWB3 mean and sd by calendar month (12 x cells)
    weights: dict                     # from regions.build_weights
    P: pd.DataFrame                   # both indices (roni, dmi), monthly; I.design takes the used ones and their lags
    reg_cwb_clim: dict = field(default_factory=dict)

    @property
    def S(self):
        m = self.cfg["model"]
        return dict(cv_window=m["cv_window"], my_grid=list(m["my_grid"]), mc_grid=list(m["mc_grid"]),
                    detrend_predictors=m.get("detrend_predictors", False))

    @property
    def lag_sets(self):
        """The lag sets the selection chooses from: model.lag_sets, or the subset named in model.lag_candidates."""
        m = self.cfg["model"]
        sets = {k: tuple(v) for k, v in m["lag_sets"].items()}
        cand = m.get("lag_candidates")
        if cand:
            missing = [k for k in cand if k not in sets]
            if missing:
                raise SystemExit(f"model.lag_candidates: {missing} not in model.lag_sets")
            sets = {k: sets[k] for k in cand}
        return sets

    @property
    def predictors(self) -> tuple:
        return C.predictors(self.cfg)

    @property
    def cells(self):
        return self.weights["cells"]

    def W(self, ws: str) -> np.ndarray:
        rs, kind = ws.split("_", 1)
        return self.weights["sets"][rs]["W"][kind]

    def regions(self, ws: str):
        rs = ws.split("_", 1)[0]
        s = self.weights["sets"][rs]
        return s["regions"], s["codes"]

    def month_data(self, var: str, month: int):
        """Cell series and predictors for one target month, on the training years where all exist."""
        y0, y1 = self.cfg["period"]["train"]
        F = self.fields[var]
        F = F[(F.index.month == month) & (F.index.year >= y0) & (F.index.year <= y1)]
        Y = F.set_axis(F.index.year)
        X = {ls: I.design(self.P, month, lags, self.predictors).reindex(Y.index) for ls, lags in self.lag_sets.items()}
        ok = Y.notna().all(axis=1)
        for x in X.values():
            ok &= x.notna().all(axis=1)
        idx = Y.index[ok]
        return idx.values.astype(float), Y.loc[idx].values, {ls: x.loc[idx].values for ls, x in X.items()}

    def region_cwb_clim(self, ws: str):
        if ws not in self.reg_cwb_clim:
            c3 = self.fields["CWB3"] @ self.W(ws).T
            y0, y1 = self.cfg["period"]["clim"]
            ref = c3.loc[f"{y0}":f"{y1}"]
            self.reg_cwb_clim[ws] = (ref.groupby(ref.index.month).mean().values, ref.groupby(ref.index.month).std().values)
        return self.reg_cwb_clim[ws]

    def aggregator(self, ws: str, var: str, month: int):
        """Cell values in physical units (..., cells) -> regional values (..., regions).

        SPEI3 is not additive: cell SPEI3 goes back to its 3-month P - PET in mm, the mm are averaged, and the
        regional total is standardised with the region's climatology for that month."""
        W = self.W(ws)
        if var == "SPEI3":
            mc, sc = self.cwb_clim[0].loc[month].values, self.cwb_clim[1].loc[month].values
            mr, sr = (a[month - 1] for a in self.region_cwb_clim(ws))
            return lambda A: ((A * sc + mc) @ W.T - mr) / sr
        return lambda A: A @ W.T

    def cwb3_from_spei3(self, ws: str, month: int, regional_spei3: np.ndarray) -> np.ndarray:
        mr, sr = (a[month - 1] for a in self.region_cwb_clim(ws))
        return regional_spei3 * sr + mr


def lag_rule(cfg: dict) -> dict:
    """How the lag set is chosen (model.lag_choice):
    month   for each variable and calendar month, the lag set and modes with the best CV skill of that month;
    window  the lag set with the best CV skill pooled over the month and its model.lag_window neighbours on each
            side (December and January are neighbours), then the modes with the best skill of the month itself.
            Neighbouring months then share their lag choice unless their own skill clearly differs."""
    m = cfg["model"]
    kind = str(m.get("lag_choice", "month"))
    if kind not in ("month", "window"):
        raise SystemExit(f"model.lag_choice must be month or window, not {kind}")
    return dict(kind=kind, width=int(m.get("lag_window", 1)))


def lag_scores(scores: dict) -> dict:
    """Best CV score of each lag set over its mode configurations."""
    out = {}
    for (ls, My, Mc), sc in scores.items():
        if np.isfinite(sc):
            out[ls] = max(out.get(ls, -np.inf), sc)
    return out


def window_choice(scores_by_month: dict, width: int) -> dict:
    """{month: {config: score}} -> {month: config}: the lag set with the best mean of its best score over the
    month and its `width` neighbours on each side (circular over the calendar), then the best modes of the month."""
    months = sorted(scores_by_month)
    L = {m: lag_scores(sc) for m, sc in scores_by_month.items()}
    out = {}
    for m in months:
        near = [((m - 1 + d) % 12) + 1 for d in range(-width, width + 1)]
        near = [k for k in near if k in L]
        pooled = {ls: np.mean([L[k][ls] for k in near if ls in L[k]]) for ls in L[m]}
        best_ls = max(pooled, key=pooled.get)
        own = {c: sc for c, sc in scores_by_month[m].items() if c[0] == best_ls and np.isfinite(sc)}
        out[m] = max(own, key=own.get)
    return out


def max_lag(cfg: dict) -> int:
    """Longest predictor lag (months) of the configured lag sets: the path needs this many lead-in months."""
    return max(max(v) for v in cfg["model"]["lag_sets"].values())


def sustained(c: np.ndarray, k: int = 2) -> np.ndarray:
    """Sum of the coefficients over the lag blocks (..., k predictors per lag) -> (..., k): the response to an
    anomaly that holds steady from the earliest lagged month to the target month."""
    return c.reshape(*c.shape[:-1], -1, k).sum(-2)


def weight_sets(cfg: dict) -> dict[str, list[str]]:
    """Weight sets per section, main first: e.g. agriculture -> ['r16_cropland', 'r16_area']."""
    out = {}
    for sec, s in cfg["sections"].items():
        sets = [f"{s['regions']}_{s['weights']}"]
        if s.get("sensitivity_weights"):
            sets.append(f"{s['regions']}_{s['sensitivity_weights']}")
        out[sec] = sets
    return out


def all_weight_sets(cfg) -> list[str]:
    seen = []
    for v in weight_sets(cfg).values():
        seen += [w for w in v if w not in seen]
    return seen


# ------------------------------------------------------------------ fitted model
@dataclass
class Fitted:
    """A model fitted on all years, y_hat = G x_tilde, with the CV residuals used in the simulation."""
    var: str
    month: int
    lagset: str
    lags: tuple
    My: int
    Mc: int
    years: np.ndarray
    prep: E.Prep
    prepx: E.PrepX
    G: np.ndarray
    rho: np.ndarray
    explained: np.ndarray
    cv_resid: np.ndarray              # (years x cells), standardised, float32
    score: float                      # mean CV Spearman over cells of the selected configuration
    predictors: tuple = ("roni", "dmi")   # models saved before the predictors could be chosen used both

    def x_names(self):
        return I.x_names(self.lags, self.predictors)

    def predict_std(self, x_raw, t):
        return self.prepx.standardize(np.atleast_2d(x_raw), np.atleast_1d(t)) @ self.G.T

    def physical(self, x_raw, t, resid=None):
        y = self.predict_std(x_raw, t)
        if resid is not None:
            y = y + resid
        return self.prep.to_physical(y, t)


def refit(var, month, Y, X_by_lag, years, kind, cfg, resid, score, lag_sets, S, predictors=("roni", "dmi")) -> Fitted:
    ls, My, Mc = cfg
    py, Ys = E.prep_y(Y, years, [kind] * Y.shape[1])
    pxx, Xs = E.prep_x(X_by_lag[ls], years, S.get("detrend_predictors", False))
    G, d = E.cca_operator(Xs, Ys, My, Mc)
    return Fitted(var, month, ls, lag_sets[ls], My, Mc, years, py, pxx, G, d["rho"], d["explained"],
                  resid.astype(np.float32), score, tuple(predictors))


def regional_cv(Yr, Pr, years, kind, cv_window):
    """Standardise observed and CV-predicted regional series with each fold's regional transform and trend."""
    n, R = Yr.shape
    half = cv_window // 2
    obs, pred = np.empty((n, R)), np.empty((n, R))
    for k in range(n):
        tr = np.abs(years - years[k]) > half
        pr, _ = E.prep_y(Yr[tr], years[tr], [kind] * R)
        obs[k] = pr.standardize(Yr[k:k + 1], years[k:k + 1])[0]
        pred[k] = pr.standardize(Pr[k:k + 1], years[k:k + 1])[0]
    return obs, pred


def cv_month(D: Data, var: str, month: int) -> dict:
    """Cross-validation of every configuration for one variable and calendar month."""
    kind = C.PREDICTANDS[var][3]
    years, Y, X = D.month_data(var, month)
    return dict(kind=kind, years=years, Y=Y, X=X, cv=E.cv_run([Y], [kind], X, years, D.S))


def fit_one(D: Data, var: str, month: int, wsets: list[str], pack: dict | None = None, cfg=None):
    """Cross-validate, select on the cells, refit; regional CV skill for every weight set.
    `pack` (from cv_month) and `cfg` (a configuration chosen elsewhere, e.g. by window_choice) are optional."""
    pack = pack or cv_month(D, var, month)
    kind, years, Y, X, cv = (pack[k] for k in ("kind", "years", "Y", "X", "cv"))
    best, score, scores = E.select(cv)
    if cfg is None:
        cfg = best
    score = scores[cfg]
    resid = cv["obs"] - cv["pred"][cfg]
    model = refit(var, month, Y, X, years, kind, cfg, resid, score, D.lag_sets, D.S, D.predictors)
    phys = E.cv_physical(cv, cfg, 0)
    res = dict(years=years, cell_rho=E.col_spearman(cv["pred"][cfg], cv["obs"]), scores=scores, regional={},
               regional_phys={})
    for ws in wsets:
        agg = D.aggregator(ws, var, month)
        res["regional_phys"][ws] = agg(phys)              # out-of-sample regional prediction, physical units
        res["regional"][ws] = regional_cv(agg(Y), res["regional_phys"][ws], years, kind, D.S["cv_window"])
    return model, res


def nested_blocks(years: np.ndarray, month: int, first_year: int, block_len: int = 5,
                  start_month: int = 7) -> list[np.ndarray]:
    """Outer blocks of the nested CV: periods of `block_len` seasonal years that begin in `start_month`,
    counted from `first_year`. With the default July: Jul 1950-Jun 1955, Jul 1955-Jun 1960, ..., so every
    month of an ENSO season (July to June) falls in the same block, and an episode such as 1997-98 or 2015-16 is
    held out as a whole. `years` are the years of the target `month`; a target month before `start_month`
    belongs to the seasonal year that began the previous calendar year."""
    b = nested_block_ids(years, month, first_year, block_len, start_month)
    return [b == k for k in np.unique(b)]


def nested_block_ids(years: np.ndarray, month: int, first_year: int, block_len: int = 5,
                     start_month: int = 7) -> np.ndarray:
    """The outer block of each year of the target month (see nested_blocks)."""
    season = years.astype(int) - (1 if month < start_month else 0)
    return (season - int(first_year)) // block_len


def nested_settings(cfg: dict) -> dict:
    return dict(first_year=int(cfg["period"]["train"][0]), block_len=int(cfg["model"].get("nested_block_years", 5)),
                start_month=int(cfg["model"].get("nested_block_start_month", 7)))


def nested_var(D: Data, var: str, months: list[int], wsets: list[str], prob_sets: list[str]) -> dict:
    """Nested CV of every month of a variable, with the lag rule of the configuration ({month: nested_one result}).
    With lag_choice: window, the choice in each outer block pools the inner-CV skill of the neighbouring months on
    the same held-out seasons, so no held-out year informs the choice."""
    rule = lag_rule(D.cfg)
    if rule["kind"] == "month":
        return {m: nested_one(D, var, m, wsets, prob_sets) for m in months}
    nb = nested_settings(D.cfg)
    kind = C.PREDICTANDS[var][3]
    inner = {}                                        # (month, block) -> {config: inner-CV score}
    for m in months:
        years, Y, X = D.month_data(var, m)
        ids = nested_block_ids(years, m, nb["first_year"], nb["block_len"], nb["start_month"])
        for k in np.unique(ids):
            tr = ids != k
            cv = E.cv_run([Y[tr]], [kind], {ls: x[tr] for ls, x in X.items()}, years[tr], D.S)
            inner[(m, int(k))] = E.select(cv)[2]
    blocks = sorted({k for _, k in inner})
    chosen = {m: {} for m in months}
    for k in blocks:
        sc = {m: inner[(m, k)] for m in months if (m, k) in inner}
        for m, c in window_choice(sc, rule["width"]).items():
            chosen[m][k] = c
    return {m: nested_one(D, var, m, wsets, prob_sets, chosen_by_block=chosen[m]) for m in months}


def nested_one(D: Data, var: str, month: int, wsets: list[str], prob_sets: list[str], block_len: int | None = None,
               chosen_by_block: dict | None = None):
    """Nested CV: outer 5-year July-June blocks; the configuration is selected again on the remaining years.

    Also probabilistic scores on `prob_sets`: each held-out year's predictive sample is the prediction plus the
    inner-CV residual map of every training year (the same construction as the simulation). The regional
    predictions are kept in physical units too (`phys`), for the out-of-sample columns of the hist_fitted tables."""
    kind = C.PREDICTANDS[var][3]
    years, Y, X = D.month_data(var, month)
    n, q = Y.shape
    aggs = {ws: D.aggregator(ws, var, month) for ws in wsets}
    Yr = {ws: a(Y) for ws, a in aggs.items()}
    out = {ws: dict(obs=np.empty(Yr[ws].shape), pred=np.empty(Yr[ws].shape), phys=np.empty(Yr[ws].shape)) for ws in wsets}
    prob = {ws: {k: np.empty(Yr[ws].shape) for k in ("crps", "crps_clim", "covered", "width")} for ws in prob_sets}
    cell_obs, cell_pred, chosen, held = np.empty((n, q)), np.empty((n, q)), [], []
    nb = nested_settings(D.cfg)
    ids = nested_block_ids(years, month, nb["first_year"], block_len or nb["block_len"], nb["start_month"])
    for kb in np.unique(ids):
        te = ids == kb
        tr = ~te
        held.append((int(years[te][0]), int(years[te][-1])))
        if chosen_by_block is not None:               # configuration chosen outside (lag_choice: window)
            cfg = chosen_by_block[int(kb)]
            S1 = {**D.S, "my_grid": [cfg[1]], "mc_grid": [cfg[2]]}
            cv = E.cv_run([Y[tr]], [kind], {cfg[0]: X[cfg[0]][tr]}, years[tr], S1)
        else:
            cv = E.cv_run([Y[tr]], [kind], {k: x[tr] for k, x in X.items()}, years[tr], D.S)
            cfg, _, _ = E.select(cv)
        chosen.append(cfg)
        e = cv["obs"] - cv["pred"][cfg]
        py, Ys = E.prep_y(Y[tr], years[tr], [kind] * q)
        ls, My, Mc = cfg
        pxx, Xs = E.prep_x(X[ls][tr], years[tr], D.S["detrend_predictors"])
        G, _ = E.cca_operator(Xs, Ys, My, Mc)
        f = pxx.standardize(X[ls][te], years[te]) @ G.T
        cell_obs[te], cell_pred[te] = py.standardize(Y[te], years[te]), f
        phys = py.to_physical(f, years[te])
        for ws in wsets:
            R = Yr[ws].shape[1]
            pr, Ysr = E.prep_y(Yr[ws][tr], years[tr], [kind] * R)
            out[ws]["obs"][te] = pr.standardize(Yr[ws][te], years[te])
            out[ws]["phys"][te] = aggs[ws](phys)
            out[ws]["pred"][te] = pr.standardize(out[ws]["phys"][te], years[te])
            if ws in prob:
                for i, k in enumerate(np.where(te)[0]):
                    t = years[k]
                    samp = pr.standardize(aggs[ws](py.to_physical(f[i] + e, t)), np.full(len(e), t))
                    o = out[ws]["obs"][k]
                    q10, q90 = np.quantile(samp, [0.1, 0.9], axis=0)
                    prob[ws]["crps"][k] = crps_sample(samp, o)
                    prob[ws]["crps_clim"][k] = crps_sample(Ysr, o)
                    prob[ws]["covered"][k] = (o >= q10) & (o <= q90)
                    prob[ws]["width"][k] = q90 - q10
    return dict(years=years, regional=out, prob=prob, cell_rho=E.col_spearman(cell_pred, cell_obs), chosen=chosen,
                held=held)


def joint_one(D: Data, month: int, variables: list[str], ws: str):
    """Joint EOF-CCA of all variables for one target month (Eq. 8 with every variable's columns side by side)."""
    data = {v: D.month_data(v, month) for v in variables}
    common = sorted(set.intersection(*[set(d[0].astype(int)) for d in data.values()]))
    pos = {v: np.searchsorted(d[0].astype(int), common) for v, d in data.items()}
    years = np.array(common, float)
    blocks = [data[v][1][pos[v]] for v in variables]
    X = {ls: x[pos[variables[0]]] for ls, x in data[variables[0]][2].items()}
    kinds = [C.PREDICTANDS[v][3] for v in variables]
    cv = E.cv_run(blocks, kinds, X, years, D.S)
    cfg, score, _ = E.select(cv)
    rows = []
    for b, v in enumerate(variables):
        sl = E.block_slice(cv, b)
        cell_rho = np.nanmean(E.col_spearman(cv["pred"][cfg][:, sl], cv["obs"][:, sl]))
        agg = D.aggregator(ws, v, month)
        o, p = regional_cv(agg(blocks[b]), agg(E.cv_physical(cv, cfg, b)), years, kinds[b], D.S["cv_window"])
        rows.append(dict(var=v, month=month, joint_config=f"{cfg[0]} My={cfg[1]} Mc={cfg[2]}",
                         joint_cells_rho=cell_rho, joint_regional_rho=np.nanmean(E.col_spearman(p, o))))
    return rows


# ------------------------------------------------------------------ outputs that need only the fitted models
def linear_coefficients(model: Fitted, W: np.ndarray) -> np.ndarray:
    """Regional response per unit of each predictor (regions x predictors), for identity-transformed variables:
    dW/dx_j = sigma * G[:, j] / s_j at every cell, then averaged with the weights (it is linear)."""
    cell = model.prep.sigma[:, None] * model.G / model.prepx.s[None, :]
    return W @ cell


def bootstrap_coefficients(D: Data, var: str, models: dict, W: np.ndarray, B: int, seed: int):
    """Bootstrap over years (the same resampled years in every month), the configuration held fixed."""
    rng = np.random.default_rng(seed)
    kind = C.PREDICTANDS[var][3]
    md = {m: D.month_data(var, m) for m in range(1, 13) if (var, m) in models}
    all_years = np.array(sorted(set().union(*[set(d[0].astype(int)) for d in md.values()])))
    reps = {m: [] for m in md}
    for _ in range(B):
        ys = rng.choice(all_years, len(all_years), replace=True)
        for m, (years, Y, X) in md.items():
            yi = years.astype(int)
            pos = np.clip(np.searchsorted(yi, ys), 0, len(yi) - 1)
            idx = pos[yi[pos] == ys]
            mdl = models[(var, m)]
            py, Ys = E.prep_y(Y[idx], years[idx], [kind] * Y.shape[1])
            pxx, Xs = E.prep_x(X[mdl.lagset][idx], years[idx], D.S["detrend_predictors"])
            G, _ = E.cca_operator(Xs, Ys, mdl.My, mdl.Mc)
            reps[m].append(W @ (py.sigma[:, None] * G / pxx.s[None, :]))
    return {m: np.stack(v) for m, v in reps.items()}           # (B, regions, predictors)


def historical_fitted(D: Data, model: Fitted) -> tuple[np.ndarray, np.ndarray]:
    """In-sample deterministic response to the observed indices in every training year: W_hat(x_obs(Y); Y)."""
    years, _, X = D.month_data(model.var, model.month)
    y = model.predict_std(X[model.lagset], years)
    return years, model.prep.to_physical(y, years)


HIST_KINDS = ("obs", "fitted", "cv", "nested")


def hist_fitted_table(D: Data, models: dict, ws: str, variables: list[str], months: list[int],
                      oos: dict | None = None) -> pd.DataFrame:
    """Fitted next to observed, for every historical month and region, with the weights `ws`:
    columns date, code, region and, per variable, `<v>_obs` and `<v>_fitted` (regional values, physical units),
    and `<v>_cv`, `<v>_nested` when `oos` is given.

    `<v>_fitted` is the in-sample deterministic response to the observed indices, W_hat(x_obs(Y); Y):
    the model's own reading of what ENSO and the IOD did in that month, with no residual.
    `<v>_cv` and `<v>_nested` are the same response from models that did not see that year (out of sample):
      cv      leave-5-years-out: the year and the two on each side held out, transform, trend and EOF-CCA
              refitted without them; the configuration (lag set, My, Mc) is the one chosen on all years
      nested  the 5-year July-June block of the month held out (Jul 1995-Jun 2000, ...), and the configuration
              chosen again without it: nothing about the block was used
    `oos[(v, m)]` = {"cv": array, "nested": array}, regional physical values (years x regions) in the order of
    D.month_data(v, m). SPEI3 goes through the regional P - PET (mm) like everywhere else, and CWB3 (mm) is
    added next to it."""
    regions, codes = D.regions(ws)
    oos = oos or {}
    frames = []
    for v in variables:
        for m in months:
            if (v, m) not in models:
                continue
            years, phys = historical_fitted(D, models[(v, m)])
            _, Y, _ = D.month_data(v, m)
            agg = D.aggregator(ws, v, m)
            dates = pd.to_datetime(pd.DataFrame({"year": years.astype(int), "month": m, "day": 1}))
            vals = {"obs": agg(Y), "fitted": agg(phys)}
            vals.update({k: a for k, a in oos.get((v, m), {}).items() if a is not None})
            cols = {v: vals}
            if v == "SPEI3":
                cols["CWB3"] = {k: D.cwb3_from_spei3(ws, m, a) for k, a in vals.items()}
            for name, vv in cols.items():
                frames.append(pd.DataFrame({"var": name, "date": np.repeat(dates.values, len(codes)),
                                            "code": np.tile(codes, len(years)), **{k: a.reshape(-1) for k, a in vv.items()}}))
    kinds = [k for k in HIST_KINDS if any(k in f for f in frames)]
    H = pd.concat(frames).pivot_table(index=["date", "code"], columns="var", values=kinds).sort_index()
    H.columns = [f"{v}_{k}" for k, v in H.columns]
    H = H.reset_index()
    H.insert(2, "region", H["code"].map(dict(zip(codes, regions))))
    first = [c for c in H.columns if c.endswith("_obs")]
    names = dict.fromkeys(c.rsplit("_", 1)[0] for c in first)
    order = ["date", "code", "region"] + [f"{v}_{k}" for v in names for k in kinds if f"{v}_{k}" in H.columns]
    return H[order]


# ------------------------------------------------------------------ loading everything the fit needs
def load_data(cfg: dict, refresh_indices: bool | None = None, with_hourly: bool = True) -> tuple[Data, list[str], dict]:
    from .outputs import variables_present
    M = C.load_pickle(C.work(cfg, "fields_monthly.pkl"), "scripts/01_prepare_inputs.py")
    fields = dict(M["fields"])
    hp = C.work(cfg, "fields_hourly.pkl")
    hourly_fields = {}
    if with_hourly and hp.exists():
        hourly_fields = C.load_pickle(hp, "scripts/02_hourly_metrics.py")["fields"]
        fields.update(hourly_fields)          # VPD here (mean of hourly VPD) replaces the VPD of the monthly means
    if "VPD" in cfg["model"]["variables"] and "VPD" not in hourly_fields:
        print("  note: VPD is the VPD of the monthly-mean t2m and d2m (biased low): fields_hourly.pkl has no hourly VPD; "
              "run scripts/02_hourly_metrics.py for the monthly mean of hourly VPD")
    W = C.load_pickle(C.work(cfg, "weights.pkl"), "scripts/01_prepare_inputs.py")
    idx, info = I.model_indices(cfg, refresh_indices)
    P = I.predictor_frame(idx, cfg["period"]["train"][1])
    D = Data(cfg, fields, M["cwb_clim"], W, P)
    return D, variables_present(cfg, fields), dict(indices=idx, raw_dmi=info.pop("raw_dmi"), index_info=info,
                                                   land_info=M.get("land_info"))
