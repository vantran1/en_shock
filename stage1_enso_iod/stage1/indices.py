"""RONI and DMI: download (NOAA CPC and PSL), cache, and the predictor table of the model."""
from __future__ import annotations

import re
import urllib.request

import numpy as np
import pandas as pd

from . import config as C

SEASON_CENTRE = {s: i + 1 for i, s in enumerate(
    ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"])}


def _fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (UNDRR DEFINE-PH Stage-1)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_roni_ascii(text: str) -> pd.Series:
    """CPC RONI.ascii.txt: 3-month means labelled by their centre month."""
    recs = []
    for line in text.splitlines():
        tok = line.split()
        if len(tok) >= 3 and tok[0].upper() in SEASON_CENTRE and re.fullmatch(r"\d{4}", tok[1]):
            val = float(tok[-1])
            recs.append((int(tok[1]), SEASON_CENTRE[tok[0].upper()], np.nan if val < -90 else val))
    idx = pd.to_datetime([f"{y}-{m:02d}-01" for y, m, _ in recs])
    return pd.Series([v for *_, v in recs], index=idx, name="roni").sort_index()


def parse_psl_standard(text: str, name: str) -> pd.Series:
    """NOAA PSL standard monthly format (first line: first and last year; then year + 12 values)."""
    lines = [l for l in text.splitlines() if l.strip()]
    y0, y1 = (int(v) for v in lines[0].split()[:2])
    recs = []
    for line in lines[1:]:
        tok = line.split()
        if len(tok) == 13 and re.fullmatch(r"\d{4}", tok[0]) and y0 <= int(tok[0]) <= y1:
            recs += [(int(tok[0]), m, float(v)) for m, v in enumerate(tok[1:], 1)]
    s = pd.Series([v for *_, v in recs], name=name, index=pd.to_datetime([f"{y}-{m:02d}-01" for y, m, _ in recs]))
    return s.where(s > -999).sort_index()


def load_raw(cfg: dict, kind: str, refresh: bool | None = None) -> pd.Series:
    """Monthly RONI (CPC, already a centred 3-month mean) or raw monthly DMI (PSL HadISST), with a cache."""
    cache = C.path(cfg, "indices_dir") / f"{kind}_monthly.csv"
    refresh = cfg["indices"].get("refresh", True) if refresh is None else refresh
    if refresh or not cache.exists():
        try:
            url = cfg["indices"]["roni_url" if kind == "roni" else "dmi_url"]
            text = _fetch_text(url)
            s = parse_roni_ascii(text) if kind == "roni" else parse_psl_standard(text, "dmi")
            if s.dropna().empty:
                raise ValueError("no values parsed")
            cache.parent.mkdir(parents=True, exist_ok=True)
            s.rename_axis("date").to_csv(cache)
        except Exception as exc:  # noqa: BLE001
            if not cache.exists():
                raise SystemExit(f"Could not download {kind.upper()} ({exc}) and there is no cache at {cache}")
            print(f"  {kind.upper()}: download failed ({type(exc).__name__}); using the cached copy")
    s = pd.read_csv(cache, index_col=0, parse_dates=True).iloc[:, 0].rename(kind)
    return s.sort_index()


def model_indices(cfg: dict, refresh: bool | None = None) -> tuple[pd.DataFrame, dict]:
    """The predictor series as the model uses them: RONI, and DMI smoothed to a centred 3-month mean."""
    roni = load_raw(cfg, "roni", refresh)
    dmi_raw = load_raw(cfg, "dmi", refresh)
    dmi = dmi_raw.rolling(3, center=True, min_periods=3).mean() if cfg["indices"].get("smooth_dmi", True) else dmi_raw
    df = pd.DataFrame({"roni": roni, "dmi": dmi}).sort_index()
    info = {"roni_last": f"{roni.dropna().index.max():%Y-%m}", "dmi_raw_last": f"{dmi_raw.dropna().index.max():%Y-%m}",
            "dmi_smoothed_last": f"{dmi.dropna().index.max():%Y-%m}"}
    return df, {"raw_dmi": dmi_raw, **info}


def predictor_frame(indices: pd.DataFrame, end_year: int) -> pd.DataFrame:
    """Monthly predictors (roni, dmi) on a regular monthly index from 1949 to the end of `end_year` + 1."""
    full = pd.date_range("1949-01-01", f"{end_year + 1}-12-01", freq="MS")
    return indices[["roni", "dmi"]].reindex(full)


def x_names(lags, predictors=("roni", "dmi")) -> list[str]:
    """Column names of the predictor matrix: the predictors for lag 0 (roni, dmi), then roni_lagL, dmi_lagL for
    each lag L; with predictors=('roni',) only the RONI columns."""
    return [f"{v}{'' if L == 0 else f'_lag{L}'}" for L in lags for v in predictors]


def design(P: pd.DataFrame, month: int, lags, predictors=("roni", "dmi")) -> pd.DataFrame:
    """Predictor matrix for one target month: rows are years; for each lag L, the predictors (RONI, and DMI if
    used) L months before the target month (L = 0: the target month itself). Years without every value are NaN."""
    cur = P.index[P.index.month == month]
    Q = P[list(predictors)]
    blocks = [Q.shift(L).loc[cur] for L in lags]
    return pd.concat(blocks, axis=1).set_axis(x_names(lags, predictors), axis=1).set_axis(cur.year, axis=0)
