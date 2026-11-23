"""Labour note: employment tables of the Labor Force Survey, the mapping of industries to work environment and
intensity, and the aggregation of work capacity from regions to the DEFINE-PH sectors (Sections 5 and 8-10).

Capacities come in as arrays [..., environment (sun, shade), intensity (heavy, moderate, light), region] of the
monthly mean Hothaps capacity; everything here is linear in them, so the same functions serve single months,
quarters and whole sets of draws.
"""
from __future__ import annotations

import pathlib
import re

import numpy as np
import pandas as pd

from . import config as C
from .wbgt import ENVS, INTENSITIES

# industry key: (start of the PSA label in lower case, group)
INDUSTRIES = {
    "agriculture": ("agriculture, hunting", "agriculture"),
    "fishing": ("fishing", "agriculture"),
    "mining": ("mining", "industry"),
    "manufacturing": ("manufacturing", "industry"),
    "electricity": ("electricity", "electricity"),
    "water": ("water supply", "industry"),
    "construction": ("construction", "construction"),
    "trade": ("wholesale and retail|whosale and retail", "services"),      # "Whosale": a typo in one block of Table 11.9
    "transport": ("transportation", "services"),
    "accommodation": ("accommodation", "services"),
    "information": ("information", "services"),
    "finance": ("financial", "services"),
    "real_estate": ("real estate", "services"),
    "professional": ("professional", "services"),
    "admin_support": ("administrative", "services"),
    "public_admin": ("public administration", "services"),
    "education": ("education", "services"),
    "health": ("human health", "services"),
    "arts": ("arts", "services"),
    "other_services": ("other service", "services"),
    "households": ("activities of households", "services"),
    "extraterritorial": ("activities of extraterritorial", "services"),
}
SERVICE_KEYS = [k for k, v in INDUSTRIES.items() if v[1] == "services"]
# Table 2 of the note: environment and intensity of the groups that are not services
FIXED = {"agriculture": ("SUN", "heavy"), "electricity": ("SHD", "moderate"), "construction": ("SUN", "heavy"),
         "industry": ("SHD", "moderate")}
REGION_PATTERNS = [
    ("NCR", r"national capital"), ("CAR", r"cordillera"), ("R01", r"\bregion\s+i\b"), ("R02", r"\bregion\s+ii\b"),
    ("R03", r"\bregion\s+iii\b"), ("R04A", r"\bregion\s+iv-?a\b|calabarzon"), ("MIMAROPA", r"mimaropa"),
    ("R05", r"\bregion\s+v\b"), ("R06", r"\bregion\s+vi\b"), ("R07", r"\bregion\s+vii\b"), ("R08", r"\bregion\s+viii\b"),
    ("R09", r"\bregion\s+ix\b"), ("R10", r"\bregion\s+x\b"), ("R11", r"\bregion\s+xi\b"), ("R12", r"\bregion\s+xii\b"),
    ("R13", r"caraga|\bregion\s+xiii\b"), ("BARMM", r"bangsamoro|muslim mindanao"),
]
OCCUPATIONS = ["managers", "professionals", "technicians", "clerical", "service_sales", "skilled_agricultural", "craft",
               "operators", "elementary", "armed_forces"]
CASES = ["central", "outdoor_low", "outdoor_high", "aircon_all_indoor", "aircon_none"]


def _num(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s in ("-", ""):
        return 0.0
    if s == "*":                                   # PSA: fewer than 500 persons
        return 0.25
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return np.nan


def _industry_key(label) -> str | None:
    s = re.sub(r"\s+", " ", str(label)).strip().lower()
    for k, (start, _) in INDUSTRIES.items():
        if s.startswith(tuple(start.split("|"))):
            return k
    return None


def _region_code(label) -> str | None:
    s = re.sub(r"\s+", " ", str(label)).strip().lower()
    for code, pat in REGION_PATTERNS:
        if re.search(pat, s):
            return code
    return None


def _rows(path: pathlib.Path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True).active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def read_regional_employment(path: pathlib.Path, year="latest") -> tuple[pd.DataFrame, int]:
    """Employed persons (thousands) by region (17 codes) and industry key, from PSA Table 11.9."""
    rows = _rows(path)
    years, col = None, None
    out, cur = {}, None
    for r in rows:
        a = r[0]
        if a is None:
            continue
        if str(a).strip().lower().startswith("region and major industry"):
            years = [int(float(str(x))) for x in r[1:] if x is not None and re.fullmatch(r"\d{4}(\.0)?", str(x).strip())]
            want = max(years) if year in (None, "latest") else int(year)
            if want not in years:
                raise SystemExit(f"{path.name} has no column for {want} (years: {years})")
            col = 1 + years.index(want)
            continue
        if col is None:
            continue
        code = _region_code(a)
        key = _industry_key(a)
        if str(a).strip().lower().startswith("note"):
            break                                  # the notes mention regions too
        if code and key is None and isinstance(r[col], (int, float)):
            cur = code
            out[cur] = {"_total": _num(r[col])}
        elif str(a).strip().upper() == "PHILIPPINES":
            cur = "_PH"
            out[cur] = {"_total": _num(r[col])}
        elif key and cur:
            out[cur][key] = _num(r[col])
    want = max(years) if year in (None, "latest") else int(year)
    df = pd.DataFrame(out).T
    missing = [c for c in C.REGION_ORDER if c not in df.index]
    if missing:
        raise SystemExit(f"{path.name}: regions not found: {missing}")
    ph = df.loc["_PH"] if "_PH" in df.index else None
    E = df.loc[C.REGION_ORDER, list(INDUSTRIES)].fillna(0.0).astype(float)
    gap = (E.sum(axis=1) - df.loc[C.REGION_ORDER, "_total"].astype(float)).abs() / df.loc[C.REGION_ORDER, "_total"].astype(float)
    if (gap > 0.01).any():
        raise SystemExit(f"{path.name}: the industries of {list(gap.index[gap > 0.01])} do not add up to the regional total; "
                         "a row label was probably not recognised")
    if ph is not None and abs(E.sum().sum() - float(ph["_total"])) / float(ph["_total"]) > 0.01:
        raise SystemExit(f"{path.name}: the regions sum to {E.sum().sum():,.0f} thousand, the national row is {float(ph['_total']):,.0f}")
    return E, want


def read_occupations(path: pathlib.Path, year="latest") -> tuple[pd.DataFrame, int]:
    """Employed persons (thousands) by industry key and major occupation group, from PSA Table 11.8."""
    rows = _rows(path)
    blocks, cur = {}, None
    for r in rows:
        a = r[0]
        if a is None:
            continue
        m = re.match(r"\s*(\d{4})\s+all industries", str(a).strip().lower())
        if m:
            cur = int(m.group(1))
            blocks[cur] = {}
            continue
        key = _industry_key(a)
        if cur and key:
            blocks[cur][key] = [_num(x) for x in r[1:12]]
    want = max(blocks) if year in (None, "latest") else int(year)
    df = pd.DataFrame(blocks[want], index=["all"] + OCCUPATIONS).T
    return df.reindex(list(INDUSTRIES)).fillna(0.0), want


def read_services_table(path: pathlib.Path) -> pd.DataFrame:
    """Table 2a of the note: outdoor share, air-conditioned share and intensity of each services group."""
    t = pd.read_csv(path, comment="#").set_index("group")
    missing = [k for k in SERVICE_KEYS if k not in t.index]
    if missing:
        raise SystemExit(f"{path.name}: no row for {missing}")
    for c in ("outdoor_share", "outdoor_share_low", "outdoor_share_high", "aircon_share"):
        if not t[c].between(0, 1).all():
            raise SystemExit(f"{path.name}: {c} must lie between 0 and 1")
    bad = set(t["intensity"]) - set(INTENSITIES)
    if bad:
        raise SystemExit(f"{path.name}: intensity must be one of {INTENSITIES}, found {bad}")
    return t.loc[SERVICE_KEYS]


def case_parameters(svc: pd.DataFrame, case: str) -> tuple[np.ndarray, np.ndarray]:
    """Outdoor and air-conditioned shares of the services groups under a sensitivity case."""
    o = svc["outdoor_share"].to_numpy(float)
    a = svc["aircon_share"].to_numpy(float)
    if case == "outdoor_low":
        o = svc["outdoor_share_low"].to_numpy(float)
    elif case == "outdoor_high":
        o = svc["outdoor_share_high"].to_numpy(float)
    elif case == "aircon_all_indoor":
        a = np.ones_like(a)
    elif case == "aircon_none":
        a = np.zeros_like(a)
    elif case != "central":
        raise ValueError(case)
    return o, a


def sector_capacity(Creg: np.ndarray, emp: pd.DataFrame, svc: pd.DataFrame, case: str = "central") -> dict:
    """National capacity of each sector and subgroup from regional capacities.

    Creg: [..., env, intensity, region], regions in the order of emp.index. Returns arrays [...] for agriculture,
    electricity, construction, industry, services and other (Eqs. 10-19a, with services from Eq. 17a)."""
    e_i = {e: i for i, e in enumerate(ENVS)}
    i_i = {s: i for i, s in enumerate(INTENSITIES)}
    group = {k: v[1] for k, v in INDUSTRIES.items()}
    N = {g: emp[[k for k in emp.columns if group[k] == g]].sum(axis=1).to_numpy(float) for g in FIXED}
    out = {}
    for g, (env, inten) in FIXED.items():
        eps = N[g] / N[g].sum()                                             # Eq. 19a
        out[g] = (Creg[..., e_i[env], i_i[inten], :] * eps).sum(-1)
    o, a = case_parameters(svc, case)
    num, den = 0.0, 0.0
    for j, k in enumerate(SERVICE_KEYS):
        ii = i_i[svc.loc[k, "intensity"]]
        Ck = o[j] * Creg[..., e_i["SUN"], ii, :] + (1 - o[j]) * (a[j] + (1 - a[j]) * Creg[..., e_i["SHD"], ii, :])   # Eq. 17a
        n = emp[k].to_numpy(float)
        num = num + (Ck * n).sum(-1)
        den += n.sum()
    out["services"] = num / den
    tot = {"construction": N["construction"].sum(), "industry": N["industry"].sum(), "services": den}
    om = {k: v / sum(tot.values()) for k, v in tot.items()}                 # Eq. 14, national employment shares
    out["other"] = sum(om[k] * out[k] for k in om)                          # Eq. 18
    return out


def employment_shares(emp: pd.DataFrame) -> pd.DataFrame:
    """Employment (thousands) and shares used in the aggregation, for the documentation of a run."""
    group = {k: v[1] for k, v in INDUSTRIES.items()}
    g = emp.T.groupby(group).sum().T
    nat = g.sum()
    other = nat[["construction", "industry", "services"]]
    rows = [dict(item=f"employment_{k}", value=v, unit="thousand persons") for k, v in nat.items()]
    rows += [dict(item=f"omega_{k}", value=v / other.sum(), unit="share of the other sector") for k, v in other.items()]
    return pd.DataFrame(rows)


def quarters_of(dates: pd.DatetimeIndex) -> tuple[list[str], list[np.ndarray], np.ndarray]:
    """Complete quarters of a monthly path: labels, the positions of their months, and the days of each month
    (the weights of the quarterly mean: every day has the same number of working hours)."""
    q = pd.PeriodIndex(dates, freq="Q")
    labels, pos = [], []
    for p in q.unique():
        idx = np.where(q == p)[0]
        if len(idx) == 3:
            labels.append(str(p))
            pos.append(idx)
    return labels, pos, dates.days_in_month.to_numpy(float)
