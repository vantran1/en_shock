"""World rice price shock: price note of the DEFINE-PH methodology (v5, "El Nino and food prices"),
Section 2, Eqs. (1)-(2a).

The direct approach of the agricultural note (Eqs. A4-A6), for one quarterly series:

  ln p_q = alpha + B^R sum_{j=1..K} w_j(theta^R) RONI_{q-j} + lambda' Z_q + s_{qtr(q)} + tau t_q + e_q   (1)

  w_j(theta) = C(K-1, j-1) theta^(K-j) (1-theta)^(j-1)      (A5; theta near 1 puts the weight on lag 1)

  S_q = exp( B^R sum_j w_j(theta^R) RONI^S_{q-j} ) - 1                                                 (2)

  S^imp_q = S_q * v^RICE IMP^RICE_q / IMP^AGR_q                                                        (2a)

p is the export price of Thai 5% broken white rice (World Bank Pink Sheet) in US dollars, deflated by a
world price index: the World Bank's MUV index (manufactures unit value), the deflator of its real
commodity prices. Z holds the real prices of fertiliser (urea) and crude oil, deflated the same way, and
the share of the quarter under rice export restrictions by the major exporters
(data/prices/rice_export_restrictions.csv). s are quarter-of-year effects and t a linear trend.

Fertiliser: the Pink Sheet's DAP price starts only in January 1967, so the main specification uses urea
alone (from 1960) and adds DAP as a check from 1967 (see CONTROLS and CONTROLS_WITH_DAP). Requiring DAP
would silently start the sample in 1967 and drop the 1963 and 1965-66 El Ninos.

The timing parameter is chosen on a grid by profile estimation (A6); the lag coefficients are
B w_j(theta); standard errors are Newey-West with the bandwidth rule of src/estimation/panel.py on the
ginevra-agriculture branch (Driscoll-Kraay with a single unit). RONI only, as agreed for all channels;
the DMI enters only as a variant.

The shock holds the controls at their neutral values, so it excludes export bans; the upper estimate
adds the effect of a ban (the coefficient of the restriction indicator) in the quarters of the path.
Eq. (2a) needs the share of rice in real agricultural imports in DEFINE-PH, which comes from the model
(SOAS); the shock delivered here is S.

The lag profile, the theta grid and the error formula mirror src/estimation/direct.py and
src/estimation/panel.py on ginevra-agriculture, so that the price and the crop shocks are estimated
the same way; they are restated here for a single series rather than imported, until the branches are
merged. Only numpy and pandas are needed (no scipy or statsmodels).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PRICES = DATA / "prices"
THETA_GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)

# Pink Sheet column -> short name (matched on the start of the header, case-insensitive)
PINK = {"rice, thai 5": "rice_thai5", "rice, viet": "rice_viet5", "urea": "urea", "dap": "dap",
        "crude oil, average": "oil"}

CONTROLS = ("lnurea", "lnoil", "ban")                       # main: urea from 1960
CONTROLS_WITH_DAP = ("lnurea", "lndap", "lnoil", "ban")     # check: DAP from 1967

# Episodes replayed as paths: the quarters with RONI >= 0.5 of the three strong El Ninos, as in
# scripts/shocks_direct.py on ginevra-agriculture
EPISODE_PATHS = {"1997-98": ("1997Q2", "1998Q1"), "2015-16": ("2015Q2", "2016Q1"),
                 "2023-24": ("2023Q3", "2024Q1")}
UNIT_PATH = "unit RONI +1 (4 quarters from Q3)"


# ------------------------------------------------------------------ data
def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _monthly_index(strings) -> pd.PeriodIndex:
    return pd.DatetimeIndex(pd.to_datetime(pd.Series(strings).astype(str), format="%Y-%m")).to_period("M")


def pink_sheet_monthly(path: Path = PRICES / "CMO-Historical-Data-Monthly.xlsx") -> pd.DataFrame:
    """Monthly nominal prices (USD) from the 'Monthly Prices' sheet of the Pink Sheet, for the series
    of PINK; missing values ('...') become NaN. Read once per run."""
    return _pink_sheet_monthly(str(path)).copy()


@lru_cache(maxsize=None)
def _pink_sheet_monthly(path: str) -> pd.DataFrame:
    path = Path(path)
    raw = pd.read_excel(path, sheet_name="Monthly Prices", header=None)
    hdr = next(i for i in range(len(raw)) if any(_norm(v).startswith("rice, thai 5") for v in raw.iloc[i]))
    names = [_norm(v) for v in raw.iloc[hdr]]
    dates = raw.iloc[:, 0].astype(str).str.strip()
    rows = dates.str.fullmatch(r"\d{4}M\d{2}").to_numpy()
    out = {}
    for key, short in PINK.items():
        cols = [j for j, n in enumerate(names) if n.startswith(key)]
        if not cols:
            raise ValueError(f"no column starting with '{key}' in {path.name}")
        out[short] = pd.to_numeric(raw.loc[rows, cols[0]], errors="coerce").to_numpy(float)
    idx = _monthly_index([f"{d[:4]}-{d[5:]}" for d in dates[rows]])
    return pd.DataFrame(out, index=idx)


def muv_annual(path: Path = PRICES / "CMO-Historical-Data-Annual.xlsx") -> pd.Series:
    """The World Bank MUV index, annual, from the first sheet of the annual Pink Sheet file that has
    a column headed 'MUV' (in the September 2026 file: 'Annual Prices (Real)', 1960-2025). Read once
    per run; the usual sheet is tried first, since reading the whole book takes several seconds."""
    return _muv_annual(str(path)).copy()


@lru_cache(maxsize=None)
def _muv_annual(path: str) -> pd.Series:
    path = Path(path)
    try:
        s = _muv_from_sheet(pd.read_excel(path, sheet_name="Annual Prices (Real)", header=None),
                            "Annual Prices (Real)")
        if s is not None:
            return s
    except ValueError:  # no sheet of that name in this release
        pass
    for name, raw in pd.read_excel(path, sheet_name=None, header=None).items():
        s = _muv_from_sheet(raw, name)
        if s is not None:
            return s
    raise ValueError(f"no MUV column in {path.name}")


def _muv_from_sheet(raw: pd.DataFrame, name: str) -> pd.Series | None:
    """The column headed 'MUV...' in the first 15 rows of a sheet, by year (first column), or None."""
    for i in range(min(len(raw), 15)):
        cols = [j for j, v in enumerate(raw.iloc[i]) if "muv" in _norm(v)]
        if cols:
            yrs = pd.to_numeric(raw.iloc[i + 1:, 0], errors="coerce").to_numpy(float)
            v = pd.to_numeric(raw.iloc[i + 1:, cols[0]], errors="coerce").to_numpy(float)
            ok = np.isfinite(yrs) & np.isfinite(v)
            s = pd.Series(v[ok], index=yrs[ok].astype(int), name=f"MUV ({name})")
            return s[~s.index.duplicated()].sort_index()
    return None


def quarterly_mean(m):
    """Calendar-quarter mean of a monthly series or frame; a quarter with a missing month is NaN."""
    g = m.groupby(m.index.asfreq("Q"))
    return g.mean().where(g.count() == 3)


def deflator(kind: str, quarters: pd.PeriodIndex) -> pd.Series:
    """'muv': annual MUV, log-linearly interpolated between mid-years and extended past the last year
    at its last annual growth; 'cpi': US CPI (all items, not seasonally adjusted), quarterly mean;
    'none': 1."""
    if kind == "none":
        return pd.Series(1.0, index=quarters)
    if kind == "cpi":
        c = pd.read_csv(PRICES / "fred_CPIAUCNS.csv")
        idx = pd.DatetimeIndex(pd.to_datetime(c.iloc[:, 0])).to_period("M")
        s = pd.Series(pd.to_numeric(c.iloc[:, 1], errors="coerce").to_numpy(float), index=idx)
        return quarterly_mean(s).reindex(quarters)
    if kind == "muv":
        a = np.log(muv_annual())
        x = a.index.to_numpy(float) + 0.5                                   # mid-year
        tq = quarters.year.to_numpy(float) + (quarters.quarter.to_numpy(float) - 0.5) / 4
        v = np.interp(tq, x, a.to_numpy())
        g_end = a.iloc[-1] - a.iloc[-2]
        g_start = a.iloc[1] - a.iloc[0]
        v = np.where(tq > x[-1], a.iloc[-1] + g_end * (tq - x[-1]), v)
        v = np.where(tq < x[0], a.iloc[0] + g_start * (tq - x[0]), v)
        return pd.Series(np.exp(v), index=quarters)
    raise ValueError(kind)


def index_quarterly(name: str) -> pd.Series:
    """RONI (data/indices/roni/roni_nino34_monthly_ersst.csv, monthly relative Nino-3.4) or DMI
    (data/indices/dmi/dmi_had.csv), calendar-quarter means, as climate.indices.quarterly on ginevra-agriculture."""
    return _index_quarterly(name).copy()


@lru_cache(maxsize=None)
def _index_quarterly(name: str) -> pd.Series:
    if name == "roni":
        df = pd.read_csv(DATA / "indices" / "roni" / "roni_nino34_monthly_ersst.csv")
        s = pd.Series(pd.to_numeric(df["rel_ssta"], errors="coerce").to_numpy(float),
                      index=_monthly_index(df["month"]))
    elif name == "dmi":
        df = pd.read_csv(DATA / "indices" / "dmi" / "dmi_had.csv", skipinitialspace=True)
        df.columns = df.columns.str.strip()
        s = pd.Series(pd.to_numeric(df["DMI"], errors="coerce").to_numpy(float),
                      index=pd.DatetimeIndex(pd.to_datetime(df["Date"])).to_period("M"))
    else:
        raise ValueError(name)
    s = s.mask(s <= -9998)
    return quarterly_mean(s).rename(name)


def restrictions() -> pd.DataFrame:
    """The export restriction episodes, data/prices/rice_export_restrictions.csv (one row each)."""
    return pd.read_csv(PRICES / "rice_export_restrictions.csv")


def restriction_share(quarters: pd.PeriodIndex, main_only: bool = True) -> pd.Series:
    """Share of the days of each quarter with a rice export restriction in force (union over the
    countries in the main indicator, or over all listed countries)."""
    r = restrictions()
    if main_only:
        r = r[r["in_main_indicator"] == 1]
    days = pd.date_range(quarters.min().start_time, quarters.max().end_time.normalize(), freq="D")
    on = np.zeros(len(days), bool)
    for _, x in r.iterrows():
        on |= (days >= pd.Timestamp(x["start"])) & (days <= pd.Timestamp(x["end"]))
    s = pd.Series(on.astype(float), index=days).groupby(days.to_period("Q")).mean()
    return s.reindex(quarters).fillna(0.0).rename("ban")


def lag_matrix(x: pd.Series, quarters: pd.PeriodIndex, K: int, first_lag: int = 1) -> np.ndarray:
    """n x K matrix of x at quarters q - first_lag, ..., q - first_lag - K + 1."""
    return np.column_stack([x.reindex(quarters - j).to_numpy(float) for j in range(first_lag, first_lag + K)])


@dataclass
class Data:
    """One row per quarter: y, controls, q, t, year, and the values one and four quarters earlier
    (y_lag1, y_lag4, <control>_lag4), so that every row carries what the check forms need and rows
    can be resampled freely by the bootstrap."""
    frame: pd.DataFrame
    lagsR: np.ndarray            # n x K lags of RONI
    lagsD: np.ndarray            # n x K lags of DMI
    lagsR4: np.ndarray           # the same, four quarters earlier
    lagsD4: np.ndarray
    price: str
    deflator: str

    def subset(self, mask) -> "Data":
        m = np.asarray(mask, bool)
        return Data(self.frame[m], self.lagsR[m], self.lagsD[m], self.lagsR4[m], self.lagsD4[m],
                    self.price, self.deflator)

    def take(self, idx) -> "Data":
        return Data(self.frame.iloc[idx], self.lagsR[idx], self.lagsD[idx], self.lagsR4[idx],
                    self.lagsD4[idx], self.price, self.deflator)


def build(price: str = "rice_thai5", defl: str = "muv", start: str = "1960Q1", end: str = "2025Q4",
          K: int = 6, first_lag: int = 1, restrictions_main_only: bool = True) -> Data:
    """Quarterly estimation data: ln real price; ln real urea, DAP and oil; the export restriction
    share; quarter of the year; a linear trend (decades from 2000); the lags of RONI and DMI.
    Rows need the price, urea, oil and the RONI lags; DAP and DMI may be missing (those rows drop out
    only of the specifications that use them)."""
    q = quarterly_mean(pink_sheet_monthly())
    quarters = pd.period_range(start, end, freq="Q")
    q = q.reindex(quarters)
    d = deflator(defl, quarters)
    f = pd.DataFrame(index=quarters)
    f["price_usd"] = q[price]
    f["y"] = np.log(q[price] / d)
    f["lnurea"] = np.log(q["urea"] / d)
    f["lndap"] = np.log(q["dap"] / d)
    f["lnoil"] = np.log(q["oil"] / d)
    f["ban"] = restriction_share(quarters, restrictions_main_only)
    f["q"] = quarters.quarter
    f["year"] = quarters.year
    f["t"] = (quarters.year + (quarters.quarter - 1) / 4 - 2000) / 10
    for c in ("y", "lnurea", "lndap", "lnoil", "ban"):
        f[f"{c}_lag4"] = f[c].shift(4)
    f["y_lag1"] = f["y"].shift(1)
    roni, dmi = index_quarterly("roni"), index_quarterly("dmi")
    LR, LD = lag_matrix(roni, quarters, K, first_lag), lag_matrix(dmi, quarters, K, first_lag)
    LR4, LD4 = lag_matrix(roni, quarters, K, first_lag + 4), lag_matrix(dmi, quarters, K, first_lag + 4)
    ok = f[["y", "lnurea", "lnoil"]].notna().all(axis=1).to_numpy() & np.isfinite(LR).all(axis=1)
    return Data(f[ok], LR[ok], LD[ok], LR4[ok], LD4[ok], price, defl)


# ------------------------------------------------------------------ model
@dataclass(frozen=True)
class Spec:
    name: str = "main"
    K: int = 6
    first_lag: int = 1
    dmi: bool = False
    controls: tuple = CONTROLS
    form: str = "levels"          # 'levels' (Eq. 1), 'yoy' (4-quarter changes), 'ldv' (+ lagged price)
    post_year: int | None = None  # RONI effect allowed to shift from this year (test of the period)


def binomial_weights(theta: float, K: int) -> np.ndarray:
    j = np.arange(1, K + 1)
    return np.array([comb(K - 1, i - 1) for i in j], float) * theta ** (K - j) * (1 - theta) ** (j - 1)


def blended(lags: np.ndarray, theta: float) -> np.ndarray:
    return lags @ binomial_weights(theta, lags.shape[1])


def design(d: Data, tR: float, tD: float, spec: Spec) -> tuple[np.ndarray, pd.DataFrame]:
    """y and the regressors of Eq. (1) (or of its check forms) for given timing parameters."""
    f = d.frame
    X = pd.DataFrame(index=f.index)
    X["BR"] = blended(d.lagsR, tR)
    if spec.dmi:
        X["BD"] = blended(d.lagsD, tD)
    if spec.post_year is not None:
        X["BR_post"] = X["BR"] * (f["year"] >= spec.post_year)
    for c in spec.controls:
        X[c] = f[c]
    if spec.form == "yoy":
        # 4-quarter differences of everything; the seasonal effects and the trend become a constant
        D = pd.DataFrame(index=f.index)
        D["BR"] = X["BR"] - blended(d.lagsR4, tR)
        if spec.dmi:
            D["BD"] = X["BD"] - blended(d.lagsD4, tD)
        if spec.post_year is not None:
            D["BR_post"] = D["BR"] * (f["year"] >= spec.post_year)
        for c in spec.controls:
            D[c] = f[c] - f[f"{c}_lag4"]
        D["const"] = 1.0
        return (f["y"] - f["y_lag4"]).to_numpy(float), D
    for k in range(1, 5):
        X[f"s{k}"] = (f["q"] == k).astype(float)
    X["trend"] = f["t"]
    if spec.form == "ldv":
        X["y_lag1"] = f["y_lag1"]
    return f["y"].to_numpy(float), X


def _ols(y: np.ndarray, X: np.ndarray):
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
    e = y[ok] - X[ok] @ b
    return b, e, ok


def newey_west(X: np.ndarray, e: np.ndarray, bandwidth: int | None = None) -> np.ndarray:
    """Bartlett-weighted Newey-West covariance; bandwidth floor(4 (T/100)^(2/9)) unless given."""
    S = X * e[:, None]
    T = len(e)
    L = bandwidth if bandwidth is not None else int(np.floor(4 * (T / 100) ** (2 / 9)))
    omega = S.T @ S
    for lag in range(1, L + 1):
        g = S[lag:].T @ S[:-lag]
        omega += (1 - lag / (L + 1)) * (g + g.T)
    h = np.linalg.pinv(X.T @ X)
    return h @ omega @ h


def p_value(z: float) -> float:
    """Two-sided p-value of a standard normal statistic."""
    return math.erfc(abs(z) / math.sqrt(2)) if np.isfinite(z) else float("nan")


def profile(d: Data, spec: Spec, grid=THETA_GRID) -> pd.DataFrame:
    rows = []
    for tR in grid:
        for tD in (grid if spec.dmi else grid[:1]):
            y, X = design(d, tR, tD, spec)
            _, e, _ = _ols(y, X.to_numpy(float))
            rows.append((tR, tD, float(e @ e)))
    return pd.DataFrame(rows, columns=["theta_R", "theta_D", "ssr"])


@dataclass
class Fit:
    spec: Spec
    theta_R: float
    theta_D: float
    params: pd.Series
    cov: pd.DataFrame
    resid: np.ndarray
    n: int
    r2: float
    sample: str
    profile: pd.DataFrame = field(repr=False)
    on_grid_edge: bool = False

    @property
    def se(self) -> pd.Series:
        return pd.Series(np.sqrt(np.clip(np.diag(self.cov), 0, None)), index=self.params.index)

    def lincom(self, w: dict) -> tuple[float, float]:
        g = pd.Series(0.0, index=self.params.index)
        for k, v in w.items():
            g[k] = v
        return float(g @ self.params), float(np.sqrt(max(float(g @ self.cov @ g), 0.0)))


def estimate(d: Data, spec: Spec, grid=THETA_GRID, bandwidth: int | None = None, se: bool = True) -> Fit:
    """Profile the timing (A6), then fit Eq. (1) at the best theta, with Newey-West errors."""
    prof = profile(d, spec, grid)
    best = prof.loc[prof["ssr"].idxmin()]
    tR, tD = float(best.theta_R), float(best.theta_D)
    y, X = design(d, tR, tD, spec)
    Xv = X.to_numpy(float)
    b, e, ok = _ols(y, Xv)
    V = newey_west(Xv[ok], e, bandwidth) if se else np.full((len(b), len(b)), np.nan)
    yy = y[ok]
    r2 = 1 - float(e @ e) / float((yy - yy.mean()) @ (yy - yy.mean()))
    used = d.frame.index[ok]
    edge = tR in (grid[0], grid[-1]) or (spec.dmi and tD in (grid[0], grid[-1]))
    return Fit(spec, tR, tD if spec.dmi else float("nan"), pd.Series(b, index=X.columns),
               pd.DataFrame(V, index=X.columns, columns=X.columns), e, int(ok.sum()), r2,
               f"{used.min()}-{used.max()}", prof, bool(edge))


def total_effect(fit: Fit) -> tuple[float, float]:
    """Effect on ln p of a sustained one-unit RONI anomaly: B^R (for the lagged-price form, the
    long-run effect B^R / (1 - rho), s.e. by the delta method)."""
    if fit.spec.form != "ldv":
        return fit.lincom({"BR": 1.0})
    b, V = fit.params, fit.cov
    rho, B = b["y_lag1"], b["BR"]
    g = pd.Series(0.0, index=b.index)
    g["BR"], g["y_lag1"] = 1 / (1 - rho), B / (1 - rho) ** 2
    return float(B / (1 - rho)), float(np.sqrt(max(float(g @ V @ g), 0.0)))


# ------------------------------------------------------------------ shocks
def paths() -> dict[str, pd.DataFrame]:
    """The three episodes replayed (quarterly RONI and DMI over their quarters with RONI >= 0.5) and a
    unit path (RONI +1 for four quarters from Q3, DMI 0)."""
    idx = pd.DataFrame({"roni": index_quarterly("roni"), "dmi": index_quarterly("dmi")})
    out = {name: idx.loc[pd.Period(a, "Q"):pd.Period(b, "Q")] for name, (a, b) in EPISODE_PATHS.items()}
    out[UNIT_PATH] = pd.DataFrame({"roni": 1.0, "dmi": 0.0},
                                  index=pd.period_range("2001Q3", periods=4, freq="Q"))
    return out


def shock_path(fit: Fit, path: pd.DataFrame, upper_ban: bool = False) -> pd.DataFrame:
    """Eq. (2) for the quarters of the path and the K quarters after it (indices zero outside the
    path, controls neutral). upper_ban adds the export restriction effect (indicator = 1) in the
    quarters of the path. For the lagged-price form the deviation is carried forward through rho."""
    spec = fit.spec
    K, fl = spec.K, spec.first_lag
    qs = pd.period_range(path.index.min(), path.index.max() + K, freq="Q")
    roni = path["roni"].reindex(pd.period_range(qs.min() - (fl + K), qs.max(), freq="Q")).fillna(0.0)
    dmi = path["dmi"].reindex(roni.index).fillna(0.0)
    LR = np.column_stack([roni.reindex(qs - j).to_numpy(float) for j in range(fl, fl + K)])
    LD = np.column_stack([dmi.reindex(qs - j).to_numpy(float) for j in range(fl, fl + K)])
    b = fit.params
    x = b["BR"] * blended(LR, fit.theta_R)
    if spec.dmi:
        x = x + b["BD"] * blended(LD, fit.theta_D)
    in_path = np.asarray(qs <= path.index.max())
    if upper_ban and "ban" in b:
        x = x + b["ban"] * in_path
    if spec.form == "ldv":
        dev = np.zeros(len(qs))
        for i in range(len(qs)):
            dev[i] = x[i] + (b["y_lag1"] * dev[i - 1] if i else 0.0)
        x = dev
    return pd.DataFrame({"scenario_q": [str(q) for q in qs], "step": np.arange(len(qs)),
                         "in_path": in_path, "roni_path": path["roni"].reindex(qs).fillna(0.0).to_numpy(),
                         "S": np.exp(x) - 1})


def all_shocks(fit: Fit, path_set: dict | None = None) -> pd.DataFrame:
    rows = []
    for name, p in (path_set or paths()).items():
        s = shock_path(fit, p)
        s["S_upper_ban"] = shock_path(fit, p, upper_ban=True)["S"].to_numpy()
        s.insert(0, "path", name)
        rows.append(s)
    return pd.concat(rows, ignore_index=True)


def block_bootstrap(d: Data, spec: Spec, reps: int, block_years: int, seed: int = 1,
                    grid=THETA_GRID, path_set: dict | None = None) -> pd.DataFrame:
    """Moving-block bootstrap over calendar years (whole years; blocks of `block_years` consecutive
    years drawn with replacement), re-estimating the timing in each replication. Returns the shocks
    of every draw. block_years = 1 is the whole-year bootstrap of scripts/shocks_direct.py."""
    rng = np.random.default_rng(seed)
    path_set = path_set or paths()
    years = np.sort(d.frame["year"].unique())
    starts = np.arange(len(years) - block_years + 1)
    nb = int(np.ceil(len(years) / block_years))
    yr = d.frame["year"].to_numpy()
    rows_of = {y: np.flatnonzero(yr == y) for y in years}
    out = []
    for r in range(reps):
        pick = (rng.choice(starts, nb)[:, None] + np.arange(block_years)).ravel()[:len(years)]
        idx = np.concatenate([rows_of[years[i]] for i in pick])
        f = estimate(d.take(idx), spec, grid, se=False)
        s = all_shocks(f, path_set)
        s["rep"], s["theta_R"], s["B_R"] = r, f.theta_R, f.params["BR"]
        s["B_ban"] = f.params.get("ban", np.nan)
        out.append(s)
    return pd.concat(out, ignore_index=True)
