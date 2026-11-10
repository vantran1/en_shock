"""Rebuild PSA region x quarter series on the 16 fixed regions (agriculture.regions).

Same rule for every crop (palay, corn, VR, PF):
1. Province rows are summed into the 16 regions with the fixed mapping, whatever region
   PSA lists them under in a given quarter (NIR provinces -> VI/VII, Sulu -> BARMM).
2. Eight Cluster Areas: from 2023Q1 the PSA BARMM total includes 63 barangays that were
   in the Province of Cotabato (XII) and are in no province row. Their output is
   computed as the published BARMM total minus the provinces listed under BARMM, and
   added to Region XII from 2023Q1, so that BARMM and XII keep their pre-2023 boundaries
   and the 16 regions add up to the national total.
"""
import pandas as pd

from agriculture.regions import REGIONS, assign_region, code_of_published

CLUSTER_FROM = pd.Period("2023Q1", "Q")
CLUSTER_TO = "R12"


def barmm_residual(df: pd.DataFrame, values: list[str], keys: list[str]) -> pd.DataFrame:
    """Published BARMM total minus the provinces PSA lists under BARMM, by keys x period,
    for every period (non-zero residuals before 2023 are reported, not applied)."""
    pub = df["region_published"].pipe(lambda s: code_of_published(s.dropna())).reindex(df.index)
    tot = (df[(df["level"] == "region") & (pub == "BARMM")]
           .groupby(keys + ["period"])[values].sum(min_count=1))
    prov = (df[(df["level"] == "province") & (pub == "BARMM")]
            .groupby(keys + ["period"])[values].sum(min_count=1))
    r = tot.sub(prov.reindex(tot.index).fillna(0))
    r.columns = [f"{v}" for v in values]
    r = r.reset_index()
    r["applied"] = r["period"] >= CLUSTER_FROM
    return r


def rebuild(df: pd.DataFrame, values: list[str], keys: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """df: long PSA table (agriculture.psa_openstat) with columns keys + level, geo,
    region_published, period and the value columns.

    Returns (panel, residual): panel has keys, region_code, region, period, the values
    and n_prov_reporting (provinces with data); residual is barmm_residual()."""
    prov = df[df["level"] == "province"].copy()
    prov["region_code"] = assign_region(prov["geo"])
    g = prov.groupby(keys + ["region_code", "period"])
    panel = g[values].sum(min_count=1)
    panel["n_prov_reporting"] = g[values[0]].count()
    panel = panel.reset_index()

    resid = barmm_residual(df, values, keys)
    add = resid[resid["applied"]].assign(region_code=CLUSTER_TO).set_index(
        keys + ["region_code", "period"])[values]
    panel = panel.set_index(keys + ["region_code", "period"])
    idx = panel.index.intersection(add.index)
    panel.loc[idx, values] = panel.loc[idx, values].fillna(0) + add.loc[idx, values].fillna(0)
    panel = panel.reset_index()
    panel.insert(len(keys) + 1, "region", panel["region_code"].map(REGIONS))
    return panel, resid
