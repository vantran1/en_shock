"""Calorie-weighted production indices for vegetables and root crops (VR) and perennial
fruits (PF), methodology v5 Section 3.2: "Within each index, crops are combined with fixed
calorie shares (2021-2023 average) ... because DEFINE-PH measures food in kcal".

Energy of a crop = production (t) x kcal per kg as produced; the index of a region is
its energy divided by its average quarterly energy in 2021-2023, x 100. This equals
a fixed-calorie-share index: sum_i s_i * Q_it / mean(Q_i, 2021-2023), with s_i the crop's
share of the region's energy in 2021-2023.

Factors: data/agriculture/fnri_calorie_factors.csv (FNRI PhilFCT, compiled by A. Aras,
UNDRR ROAP, 9 Nov 2026), one row per PSA commodity. kcal per kg as produced is
recomputed here as kcal_per_100g_edible x 10 x edible_portion and checked against the
file's own column.
"""
from pathlib import Path

import numpy as np
import pandas as pd

FACTORS = Path(__file__).resolve().parents[2] / "data" / "agriculture" / "fnri_calorie_factors.csv"
BASE_YEARS = (2021, 2023)
# index name -> (group, rows of the factor table to keep)
VARIANTS = {
    "vr": ("VR", lambda f: f.index.notna()),
    "vr_noroot": ("VR", lambda f: f.root_crop == 0),
    "pf": ("PF", lambda f: f.index.notna()),
    "pf_nobanana": ("PF", lambda f: f.banana == 0),
    "pf_nocavendish": ("PF", lambda f: f.index != "Banana Cavendish"),
}


def factors(tol: float = 0.05) -> pd.DataFrame:
    """Factor table with kcal_per_kg recomputed; fails if it differs from the file's column
    by more than `tol` kcal/kg (rounding)."""
    f = pd.read_csv(FACTORS).rename(columns={"index": "group"})
    f["kcal_per_kg"] = f["kcal_per_100g_edible"] * 10 * f["edible_portion"]
    gap = (f["kcal_per_kg"] - f["kcal_per_kg_as_produced"]).abs()
    if (gap > tol).any():
        raise ValueError(f"kcal per kg differs from the file:\n{f[gap > tol]}")
    if f["psa_commodity"].duplicated().any():
        raise ValueError("duplicated commodities in the factor table")
    return f.set_index("psa_commodity")


def energy(prod: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """prod: crop, region_code, period, production_t. Adds energy_bkcal (billion kcal):
    t x 1000 kg x kcal/kg / 1e9."""
    out = prod.merge(f[["group", "kcal_per_kg", "root_crop", "banana"]], left_on="crop",
                     right_index=True, how="inner", validate="m:1")
    out["energy_bkcal"] = out["production_t"] * out["kcal_per_kg"] * 1e-6
    return out


def indices(en: pd.DataFrame, f: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Energy and index of each variant by `by` (e.g. region_code) x period.

    A missing crop-quarter ('..') counts as zero energy, as in a sum of the published
    figures; n_crops_missing records how many crops of the variant were missing.
    Index is missing where the 2021-2023 base is zero (no production of the variant)."""
    rows = []
    for name, (group, keep) in VARIANTS.items():
        crops = f.index[(f["group"] == group) & keep(f)]
        e = en[en["crop"].isin(crops)]
        g = e.groupby(by + ["period"])
        d = pd.DataFrame({"energy_bkcal": g["energy_bkcal"].sum(min_count=1),
                          "n_crops_missing": g["energy_bkcal"].apply(lambda s: s.isna().sum())})
        d = d.reset_index()
        yr = d["period"].dt.year
        base = (d[yr.between(*BASE_YEARS)].groupby(by)["energy_bkcal"].mean().rename("base"))
        d = d.merge(base, left_on=by, right_index=True, how="left")
        d["index"] = np.where(d["base"] > 0, d["energy_bkcal"] / d["base"] * 100, np.nan)
        rows.append(d.assign(series=name, group=group))
    return pd.concat(rows, ignore_index=True)
