"""The climate-mode path x^S of the scenario (monthly RONI and DMI) and the historical blocks Y_b."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import c3s
from . import config as C


def build_path(cfg: dict, idx: pd.DataFrame, raw_dmi: pd.Series, forecast_start=None):
    """Path from `start` to the end of the forecast, with lead-in months before `start` for the lagged
    predictors (as many as the longest lag of config model.lag_sets). Months before the forecast start use the observed indices where they exist; the months
    between the last observation and the forecast use the members' centred 3-month means with the observed
    lead-in; any remaining gap is interpolated. Every value carries its source.

    With path.lead_in: zero (csv paths only) the lead-in months are zeros instead of the observed indices, so that
    an idealised scenario does not carry the ENSO state of the months before its table into its first months.

    With path.tail (C3S paths only; a csv path is used as it is) the forecast is extended by a linear decay of
    RONI and DMI to zero and then zero months: see add_tail."""
    pc = cfg["path"]
    members, used, meta, tail_source, tail_meta = None, [], {}, {}, None
    zero_lead = str(pc.get("lead_in", "observed")) == "zero"
    if zero_lead and pc.get("source", "c3s") != "csv":
        raise SystemExit("path.lead_in: zero is for csv paths (scenarios); a forecast path starts from the observations")
    if pc.get("source", "c3s") == "csv":
        f = C.ROOT / pc["csv"] if not str(pc["csv"]).startswith("/") else pc["csv"]
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        start = d.index.min()
        central = d[["roni", "dmi"]]
        fc_start = start
        meta.update(source=f"csv: {f}")
    else:
        spec = forecast_start or pc.get("forecast_start")
        y, m = c3s.parse_month(spec, c3s.default_start())
        if spec in (None, "auto"):
            have = c3s.latest_available(C.path(cfg, "c3s_dir"))
            if have is None:
                raise SystemExit(f"No C3S files in {C.path(cfg, 'c3s_dir')}. Run scripts/00_download_inputs.py --c3s first.")
            if have != (y, m):
                print(f"  using the latest downloaded forecast, issued {have[0]}-{have[1]:02d}")
            y, m = have
        fc_start = pd.Timestamp(y, m, 1)
        members, used = c3s.members(C.path(cfg, "c3s_dir"), pc["systems"], y, m, idx["roni"].dropna(), raw_dmi.dropna(),
                                    int(pc.get("per_system", 10)))
        central = c3s.central_path(members, pc.get("central", "median"))
        tail = pc.get("tail") or {}
        central, tail_source, tail_meta = add_tail(central, int(tail.get("decay_months") or 0),
                                                   int(tail.get("zero_months") or 0))
        sy, sm = c3s.parse_month(pc.get("start"), (y, 1))
        start = pd.Timestamp(sy, sm, 1)
        meta.update(source="C3S seasonal-postprocessed-single-levels (SST anomaly), multi-system",
                    forecast_start=f"{fc_start:%Y-%m}", systems=used, central=pc.get("central", "median"))
    end = central.dropna(how="all").index.max()
    n_lead = max(max(v) for v in cfg["model"]["lag_sets"].values())
    dates = pd.date_range(start - pd.DateOffset(months=n_lead), end, freq="MS")
    rows = []
    for t in dates:
        r = {"date": t}
        for v in ("roni", "dmi"):
            obs = idx[v].get(t, np.nan)
            if zero_lead and t < start:
                r[v], r[f"{v}_source"] = 0.0, "zero lead-in"
            elif t < fc_start and np.isfinite(obs):
                r[v], r[f"{v}_source"] = float(obs), "observed"
            elif t in central.index and np.isfinite(central.loc[t, v]):
                r[v] = float(central.loc[t, v])
                if t in tail_source:
                    r[f"{v}_source"] = tail_source[t]
                elif members is None:
                    r[f"{v}_source"] = "path file"
                else:
                    r[f"{v}_source"] = "forecast" if t >= fc_start else "forecast with observed lead-in"
            else:
                r[v], r[f"{v}_source"] = np.nan, "interpolated"
            if members is not None and t in central.index:
                r[f"{v}_q10"], r[f"{v}_q90"] = central.loc[t, f"{v}_q10"], central.loc[t, f"{v}_q90"]
        rows.append(r)
    path = pd.DataFrame(rows).set_index("date")
    for v in ("roni", "dmi"):
        if path[v].isna().any():
            path[v] = path[v].interpolate(limit_area="inside")
            if path[v].isna().any():
                raise SystemExit(f"{v.upper()} path has months that cannot be filled: "
                                 f"{path.index[path[v].isna()].strftime('%Y-%m').tolist()}. The path needs "
                                 f"{n_lead} months before its start for the lagged predictors: observed, or rows "
                                 "of the path file.")
    if members is not None:
        path["n_members"] = central["n_members"].reindex(path.index)
    path["lead_in"] = path.index < start
    meta.update(start=f"{start:%Y-%m}", end=f"{end:%Y-%m}", months=int((~path["lead_in"]).sum()), lead_in_months=n_lead,
                lead_in_values="zero" if zero_lead else "observed", tail=tail_meta)
    return path, members, meta


def add_tail(central: pd.DataFrame, decay_months: int, zero_months: int):
    """Extend the central forecast after its last month: RONI and DMI fall linearly from their last forecast
    values to 0, which is reached in the decay_months-th month after it, and then stay 0, for zero_months months
    in all counting that one. The tail has no ensemble spread (q10, q90 and n_members are NaN).

    E.g. the November 2026 forecast ends in April 2027 at RONI 1.61; decay_months 3, zero_months 12 give May 1.07,
    June 0.54 and 0 from July 2027 to June 2028. Returns the extended table, the source label of each tail month and
    a summary (None without a tail)."""
    if decay_months <= 0 and zero_months <= 0:
        return central, {}, None
    if decay_months < 1 or zero_months < 1:
        raise SystemExit("path.tail needs decay_months >= 1 (1 = zero from the next month) and zero_months >= 1, "
                         f"got decay_months={decay_months}, zero_months={zero_months}")
    last = central[["roni", "dmi"]].dropna(how="any").index.max()
    central = central.loc[:last].copy()
    start = {v: float(central.loc[last, v]) for v in ("roni", "dmi")}
    n = decay_months - 1 + zero_months
    dates = pd.date_range(last + pd.DateOffset(months=1), periods=n, freq="MS")
    rows, source = [], {}
    for k, t in enumerate(dates, start=1):
        f = max(0.0, 1.0 - k / decay_months)
        rows.append({"date": t, **{v: start[v] * f if f > 0 else 0.0 for v in ("roni", "dmi")}})
        source[t] = "decay to zero (path.tail)" if f > 0 else "zero (path.tail)"
    ext = pd.DataFrame(rows).set_index("date").reindex(columns=central.columns)
    out = pd.concat([central, ext])
    out.index.name = central.index.name
    meta = dict(decay_months=decay_months, zero_months=zero_months, last_forecast_month=f"{last:%Y-%m}",
                from_roni=round(start["roni"], 4), from_dmi=round(start["dmi"], 4),
                first_zero_month=f"{last + pd.DateOffset(months=decay_months):%Y-%m}", end=f"{dates[-1]:%Y-%m}")
    return out, source, meta


def blocks(models: dict, path_dates: pd.DatetimeIndex, variables: list[str]) -> pd.DataFrame:
    """Historical blocks: draw b replays the residuals of the same calendar months shifted by a whole number of
    years, so a path of several years uses consecutive historical years (Section 3.5). Only shifts for which
    every month of the path has a CV residual for every variable are kept."""
    Y0 = path_dates[0].year
    years = {k: set(m.years.astype(int)) for k, m in models.items()}
    lo = min(min(v) for v in years.values())
    hi = max(max(v) for v in years.values())
    rows = []
    for yb in range(lo, hi + 1):
        delta = Y0 - yb
        ok = all((d.year - delta) in years[(v, d.month)] for v in variables for d in path_dates)
        if ok:
            rows.append({"block_year": yb, "shift_years": delta})
    if not rows:
        raise SystemExit("No historical block covers the whole path; shorten the path")
    b = pd.DataFrame(rows)
    b.insert(0, "draw", np.arange(len(b)))
    return b
