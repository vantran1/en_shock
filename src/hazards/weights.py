"""Province -> region weights shared by all hazard controls: each province's share of its
region's production, 2016-2025 average, by crop series: palay by ecosystem (irrigated,
rainfed, total), corn (white, yellow, total) and the VR and PF calorie indices with their
variants (vr, vr_noroot, pf, pf_nobanana, pf_nocavendish), for which production is the
calorie energy of the index's crops (agriculture.calories). The series name is kept in the column
`ecosystem` of the control files, so rice rows are unchanged when corn rows are added. Fixed over time so a control
does not move with production itself. Units are the boundary polygons of
hazards.typhoon (cities folded into their province, Maguindanao as one unit)."""
import pandas as pd

from agriculture.calories import VARIANTS, energy, factors
from agriculture.psa_openstat import read_palay_corn, read_vr_pf
from agriculture.regions import assign_region
from hazards.typhoon import PSA_TO_POLYGON

ECOSYSTEMS = {"Irrigated Palay": "irrigated", "Rainfed Palay": "rainfed", "Palay": "total",
              "White Corn": "corn_white", "Yellow Corn": "corn_yellow", "Corn": "corn"}


def vr_pf_production(years=(2016, 2025)) -> pd.DataFrame:
    """Province rows of the VR and PF indices: ecosystem (= index variant), geo, period,
    production_t holding the calorie energy (billion kcal; only shares are used)."""
    f = factors()
    vp = read_vr_pf({g: list(f.index[f["group"] == g]) for g in ("VR", "PF")})
    vp = vp[(vp.level == "province") & vp.period.dt.year.between(*years)]
    en = energy(vp[["crop", "geo", "period", "production_t"]], f)
    out = []
    for name, (group, keep) in VARIANTS.items():
        crops = f.index[(f["group"] == group) & keep(f)]
        out.append(en[en.crop.isin(crops)].assign(ecosystem=name))
    en = pd.concat(out)
    return (en.groupby(["ecosystem", "geo", "period"]).energy_bkcal.sum().rename("production_t")
            .reset_index())


def province_weights(polygons=None, years=(2016, 2025)) -> pd.DataFrame:
    df = read_palay_corn()
    df = df[(df.level == "province") & df.crop.isin(ECOSYSTEMS)
            & df.period.dt.year.between(*years)].copy()
    df["ecosystem"] = df.crop.map(ECOSYSTEMS)
    df = pd.concat([df[["ecosystem", "geo", "period", "production_t"]], vr_pf_production(years)],
                   ignore_index=True)
    df["region_code"] = assign_region(df.geo)
    df["polygon"] = df.geo.replace(PSA_TO_POLYGON)
    if polygons is not None:
        missing = sorted(set(df.polygon) - set(polygons))
        if missing:
            raise KeyError(f"PSA provinces without a boundary polygon: {missing}")
    w = df.groupby(["ecosystem", "region_code", "polygon"]).production_t.sum().reset_index()
    w["weight"] = w.production_t / w.groupby(["ecosystem", "region_code"]).production_t.transform("sum")
    if w["weight"].isna().any():
        raise ValueError("a region has no production of a series in the weight years")
    return w.drop(columns="production_t")
