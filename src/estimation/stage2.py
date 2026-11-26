"""Stage 2 of the two-stage approach, methodology v5 Section 3.4: weather -> production.

Features (v5: "monthly values are summarised over the window"). For crop series c, region r
and harvest quarter q, with the growing-window weights w_{c,r,qtr(q),l} of the crop calendar
(lag l = months before the last month of q; data/processed/{rice,corn}_growing_window.csv):

  W_{v,r,q}      = sum_l w_l x_{v,r,m(q)-l} / sum_l w_l          window mean of variable v
  W^max / W^min  = max / min of x over the months with w_l >= 0.5 (the crop mostly in the field)

The same function builds the features from observed weather (Van's `<var>_obs`, for the
estimation) and from Stage-1 simulations (for the chain): v5 requires Stage 2 to take the
Stage-1 variables in the same units and resolution.

Regression, v5 Eq. (11), Poisson pseudo-ML (production in levels, proportional effects):

  ln y_{c,r,q} = alpha_{c,r} + s_{c,r,qtr(q)} + tau_{c,r}(t)
                 + sum_v [ beta_{c,v} W_{v,r,q} + delta_{c,v} h_v(W_{v,r,q}; W*_{c,v}) ]
                 + gamma' X_{r,q} + u                                                     (11)

  h_v = max(0, W - W*) for heat and evaporative demand (T, VPD), max(0, W* - W) for rainfall
  and soil moisture (P, SM). Thresholds W* chosen by fit (deviance) on a grid of the
  training sample's 5th, 10th, ..., 95th percentiles, one variable at a time (coordinate
  descent, two sweeps).
Region x quarter-of-year effects, smooth regional trends (restricted cubic spline, knots
on the training years, as in scripts/validate_strict.py), exposure controls X as in the
direct approach.

Machine learning (v5: "a machine-learning model such as gradient boosting"): histogram
gradient boosting with Poisson loss on the same features, with the region, seasonal, trend
and control terms of Eq. (11) as an offset. The two parts are fitted by backfitting: PPML of
the non-weather terms with the boosting prediction as offset, then boosting with the PPML
prediction as offset (Poisson deviance with an offset mu0 equals mu0 times the deviance of
y / mu0, so the boosting fits the ratio with weights mu0). Monotonic constraints on the
features whose sign is known (production falls with heat and evaporative demand, rises with
soil moisture and, from 26 Nov 2026, never falls with more rainfall or runoff: wet-side losses are
flood damage, which belongs to the CAT channel; see MONOTONE). Hyperparameters fixed in advance, not tuned (no nested tuning needed).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

MONTHLY = ["T", "VPD", "P", "SM_RZ", "SM_DEEP", "PET", "E", "SPEI3", "CWB3", "RS", "RO"]
# daily variables of v5 Table 2, from hourly ERA5 (Van, 25 Nov 2026): monthly means of the daily
# maximum and minimum temperature and of the afternoon VPD; extreme degree-days and hot days above
# 30, 32 and 35 degC; dry days (< 1 mm), longest dry spell in the month, heavy-rain days (>= 50 mm)
DAILY = ["TMAX", "TMIN", "VPDMAX", "EDD30", "EDD32", "EDD", "NHOT30", "NHOT32", "NHOT", "NDRY",
         "LDRY", "N50"]
VARS = MONTHLY + DAILY
EXTREMES = {"T_max": ("T", "max"), "VPD_max": ("VPD", "max"), "P_min": ("P", "min"),
            "SM_RZ_min": ("SM_RZ", "min"), "SPEI3_min": ("SPEI3", "min"),
            "TMAX_max": ("TMAX", "max"), "LDRY_max": ("LDRY", "max")}
MONTHLY_EXTREMES = ["T_max", "VPD_max", "P_min", "SM_RZ_min", "SPEI3_min"]
FEATURES_MONTHLY = MONTHLY + MONTHLY_EXTREMES
FEATURES = VARS + list(EXTREMES)
# direction of the hinge: 'upper' = losses beyond a high value (heat, demand), 'lower' =
# losses below a low value (water supply)
HINGE = {"T": "upper", "VPD": "upper", "PET": "upper", "T_max": "upper", "VPD_max": "upper",
         "TMAX": "upper", "TMIN": "upper", "VPDMAX": "upper", "TMAX_max": "upper",
         "EDD30": "upper", "EDD32": "upper", "EDD": "upper", "NHOT30": "upper", "NHOT32": "upper",
         "NHOT": "upper", "NDRY": "upper", "LDRY": "upper", "LDRY_max": "upper", "N50": "upper",
         "P": "lower", "SM_RZ": "lower", "SM_DEEP": "lower", "SPEI3": "lower", "CWB3": "lower",
         "E": "lower", "RO": "lower", "P_min": "lower", "SM_RZ_min": "lower",
         "SPEI3_min": "lower"}
# monotonic constraints for the boosting (+1 production rises with the feature, -1 falls,
# 0 free): heat and demand hurt, water in the soil helps; radiation and actual evaporation are
# left free (E rises with both water and heat); daily: heat (TMAX, night-time TMIN, degree-days,
# hot days, afternoon VPD) and dry spells hurt.
# Water supply (rainfall, runoff, heavy-rain days) can never lower production (+1), from 26 Nov
# 2026. Left free, the boosting learns that very wet seasons (typhoon rain, floods) lower output,
# and then counts El Nino's drier seasons as a gain from fewer floods (corn: lower runoff alone
# +15% in 1998Q1, cancelling the drought loss). Flood and typhoon damage belong to the CAT channel
# (v5 Section 3.2: controls at "no event" in both runs, no double counting), so the El Nino shock
# must not include it. MONOTONE_WATER_FREE is the earlier version, kept for the comparison.
MONOTONE_WATER_FREE = {"T": -1, "VPD": -1, "PET": -1, "T_max": -1, "VPD_max": -1, "SM_RZ": 1,
                       "SM_DEEP": 1, "SPEI3": 1, "CWB3": 1, "SM_RZ_min": 1, "SPEI3_min": 1,
                       "TMAX": -1, "TMIN": -1, "VPDMAX": -1, "TMAX_max": -1, "EDD30": -1,
                       "EDD32": -1, "EDD": -1, "NHOT30": -1, "NHOT32": -1, "NHOT": -1, "NDRY": -1,
                       "LDRY": -1, "LDRY_max": -1}
MONOTONE = {**MONOTONE_WATER_FREE, "P": 1, "P_min": 1, "RO": 1, "N50": 1}
# thresholds: every 5th percentile of the training sample, 5th to 95th (deciles until 25 Nov 2026,
# when several thresholds ended on the edge of that grid)
GRID_Q = np.round(np.arange(0.05, 0.951, 0.05), 2)
FULL_IN_FIELD = 0.5


# ---------------------------------------------------------------- features
def window_features(weather: pd.DataFrame, windows: pd.DataFrame, keys=()) -> pd.DataFrame:
    """Window summaries by region and harvest quarter.

    weather: columns date (month start), region_code, the variables of VARS, and any `keys`
    (e.g. path, draw) that identify separate weather paths.
    windows: region_code, quarter, lag, weight (one crop calendar).
    Returns keys, region_code, period ('YYYYQn'), the FEATURES; quarters whose window reaches
    a month missing from `weather` are NaN."""
    keys = list(keys)
    w = weather.copy()
    w["month"] = pd.PeriodIndex(pd.to_datetime(w["date"]), freq="M")
    w = w.set_index(keys + ["region_code", "month"])[VARS].sort_index()
    win = windows[windows.weight > 0]
    lags = sorted(win.lag.unique())
    # harvest quarters whose last month is in the weather table
    ends = w.index.to_frame(index=False)
    ends = ends[ends.month.dt.month % 3 == 0]
    ends["q"] = ends.month.dt.month // 3
    num = {v: np.zeros(len(ends)) for v in VARS}
    den = np.zeros(len(ends))
    ext = {k: np.full(len(ends), np.nan) for k in EXTREMES}
    ext_seen = np.zeros(len(ends), bool)
    missing = np.zeros(len(ends), bool)
    wl = win.set_index(["region_code", "quarter", "lag"]).weight
    for lag in lags:
        idx = pd.MultiIndex.from_frame(ends[keys + ["region_code"]].assign(month=ends.month - lag))
        x = w.reindex(idx)
        weight = wl.reindex(pd.MultiIndex.from_arrays(
            [ends.region_code, ends.q, np.full(len(ends), lag)])).fillna(0).to_numpy()
        has = weight > 0
        miss = x[VARS[0]].isna().to_numpy() & has
        missing |= miss
        for v in VARS:
            num[v] += np.where(has, weight * np.nan_to_num(x[v].to_numpy()), 0)
        den += weight
        full = weight >= FULL_IN_FIELD
        for k, (v, how) in EXTREMES.items():
            val = np.where(full, x[v].to_numpy(), np.nan)
            f = np.fmax if how == "max" else np.fmin
            ext[k] = f(ext[k], val)
        ext_seen |= full
    out = ends[keys + ["region_code"]].copy()
    out["period"] = (ends.month.dt.year.astype(str) + "Q" + ends.q.astype(str)).to_numpy()
    for v in VARS:
        out[v] = num[v] / np.where(den > 0, den, np.nan)
    for k in EXTREMES:
        out[k] = ext[k]
    out.loc[missing | (den == 0), FEATURES] = np.nan
    return out.reset_index(drop=True)


def observed_weather(hist: pd.DataFrame, suffix: str = "_obs") -> pd.DataFrame:
    """Van's hist_fitted table -> date, region_code, VARS (one of _obs, _fitted, _cv, _nested).
    Needs the version with the daily variables (dev_Van f6ddf65 or later)."""
    cols = {f"{v}{suffix}": v for v in VARS}
    return hist.rename(columns={"code": "region_code", **cols})[["date", "region_code"] + VARS]


# ---------------------------------------------------------------- hinge regression
@dataclass(frozen=True)
class Stage2Spec:
    name: str
    linear: tuple = ()                      # features entering linearly (beta)
    hinge: tuple = ()                       # features with a hinge term (delta), also linear
    post: int | None = None                 # weather effects shift from this year (test)
    thresholds: dict = field(default_factory=dict, compare=False)  # fixed W* (else chosen)


def hinge(x: np.ndarray, threshold: float, direction: str) -> np.ndarray:
    return np.clip(x - threshold, 0, None) if direction == "upper" else np.clip(threshold - x, 0, None)


def weather_design(d: pd.DataFrame, spec: Stage2Spec, thr: dict) -> pd.DataFrame:
    """Linear and hinge columns (W_<v>, H_<v>), and their post-break shifts if spec.post."""
    cols = {}
    for v in dict.fromkeys(spec.linear + spec.hinge):
        cols[f"W_{v}"] = d[v].to_numpy(float)
    for v in spec.hinge:
        cols[f"H_{v}"] = hinge(d[v].to_numpy(float), thr[v], HINGE[v])
    X = pd.DataFrame(cols, index=d.index)
    if spec.post is not None:
        post = (d["period"].str[:4].astype(int) >= spec.post).to_numpy(float)
        X = pd.concat([X, X.mul(post, axis=0).add_prefix("P_")], axis=1)
    return X


def _glm(y, X, offset=None):
    return sm.GLM(y, X, family=sm.families.Poisson(), offset=offset).fit(maxiter=200, tol=1e-9)


def fit_hinge(d: pd.DataFrame, y: np.ndarray, base: pd.DataFrame, spec: Stage2Spec,
              train: np.ndarray, sweeps: int = 2):
    """Choose the thresholds on the training rows (coordinate descent over the deciles of
    each hinge feature), then fit. Returns params (Series), the full design X (all rows),
    the thresholds and the training deviance."""
    bt = base.loc[train]
    keep = bt.columns[bt.abs().sum() > 0]
    yt = y[train]
    grid = {v: np.unique(np.quantile(d.loc[train, v], GRID_Q)) for v in spec.hinge}
    thr = {v: spec.thresholds.get(v, float(np.median(d.loc[train, v]))) for v in spec.hinge}

    def dev(t):
        X = pd.concat([weather_design(d, spec, t), base[keep]], axis=1).loc[train]
        return _glm(yt, X.to_numpy(float)).deviance

    free = [v for v in spec.hinge if v not in spec.thresholds]
    for _ in range(sweeps if free else 0):
        for v in free:
            devs = [dev({**thr, v: g}) for g in grid[v]]
            thr[v] = float(grid[v][int(np.argmin(devs))])
    X = pd.concat([weather_design(d, spec, thr), base[keep]], axis=1)
    res = _glm(yt, X.loc[train].to_numpy(float))
    params = pd.Series(res.params, index=X.columns)
    edge = {v: thr[v] in (grid[v][0], grid[v][-1]) for v in free}
    return {"params": params, "X": X, "thresholds": thr, "deviance": res.deviance,
            "on_grid_edge": edge, "k": X.shape[1]}


def predict_hinge(fit: dict, d: pd.DataFrame, base: pd.DataFrame, spec: Stage2Spec,
                  weather_only: bool = False) -> np.ndarray:
    """mu for the rows of d (features in d, non-weather design in base); weather_only=True
    returns exp(weather terms) alone (the factor that the shock of Eq. 12 compares)."""
    W = weather_design(d, spec, fit["thresholds"])
    p = fit["params"]
    eta_w = W[[c for c in W.columns if c in p.index]].to_numpy(float) @ p[[c for c in W.columns if c in p.index]].to_numpy()
    if weather_only:
        return np.exp(eta_w)
    cols = [c for c in p.index if c not in W.columns]
    return np.exp(eta_w + base[cols].to_numpy(float) @ p[cols].to_numpy())


# ---------------------------------------------------------------- gradient boosting
GBM_PARAMS = dict(loss="poisson", learning_rate=0.05, max_iter=300, max_depth=3,
                  min_samples_leaf=40, l2_regularization=1.0, early_stopping=False,
                  random_state=0)


def fit_gbm(d: pd.DataFrame, y: np.ndarray, base: pd.DataFrame, features: list[str],
            train: np.ndarray, rounds: int = 3, monotone: bool = True, constraints: dict | None = None):
    """Backfitting of the non-weather PPML terms and the boosting on the weather features.
    Returns the boosting model, the PPML params of the base terms and the column list."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    bt = base.loc[train]
    keep = bt.columns[bt.abs().sum() > 0]
    B = bt[keep].to_numpy(float)
    F = d.loc[train, features].to_numpy(float)
    yt = y[train]
    log_f = np.zeros(len(yt))
    cons = MONOTONE if constraints is None else constraints
    cst = [cons.get(v, 0) if monotone else 0 for v in features]
    gbm = None
    for _ in range(rounds):
        res = _glm(yt, B, offset=log_f)
        mu0 = np.exp(B @ res.params)
        gbm = HistGradientBoostingRegressor(monotonic_cst=cst, **GBM_PARAMS)
        gbm.fit(F, yt / mu0, sample_weight=mu0)
        f = gbm.predict(F)
        log_f = np.log(f / np.average(f, weights=mu0))  # normalise: base terms carry the level
    res = _glm(yt, B, offset=log_f)
    return {"gbm": gbm, "params": pd.Series(res.params, index=keep), "features": features,
            "norm": float(np.average(gbm.predict(F), weights=np.exp(B @ res.params)))}


def predict_gbm(fit: dict, d: pd.DataFrame, base: pd.DataFrame, weather_only: bool = False):
    f = fit["gbm"].predict(d[fit["features"]].to_numpy(float)) / fit["norm"]
    if weather_only:
        return f
    p = fit["params"]
    return f * np.exp(base[p.index].to_numpy(float) @ p.to_numpy())


def fit_base(y: np.ndarray, base: pd.DataFrame, train: np.ndarray):
    """The model without weather (region x quarter effects, trends, controls)."""
    bt = base.loc[train]
    keep = bt.columns[bt.abs().sum() > 0]
    res = _glm(y[train], bt[keep].to_numpy(float))
    return pd.Series(res.params, index=keep)


def poisson_deviance(y, mu) -> float:
    y, mu = np.asarray(y, float), np.asarray(mu, float)
    t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0.0)
    return float(2 * np.sum(t - (y - mu)))
