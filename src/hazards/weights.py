"""Province -> region weights shared by all hazard controls: each province's share of its
region's palay production, 2016-2025 average, by ecosystem. Fixed over time so a control
does not move with production itself. Units are the boundary polygons of
hazards.typhoon (cities folded into their province, Maguindanao as one unit)."""
import pandas as pd

from agriculture.psa_openstat import read_palay_corn
from agriculture.regions import assign_region
from hazards.typhoon import PSA_TO_POLYGON

ECOSYSTEMS = {"Irrigated Palay": "irrigated", "Rainfed Palay": "rainfed", "Palay": "total"}


def province_weights(polygons=None, years=(2016, 2025)) -> pd.DataFrame:
    df = read_palay_corn()
    df = df[(df.level == "province") & df.crop.isin(ECOSYSTEMS)
            & df.period.dt.year.between(*years)].copy()
    df["ecosystem"] = df.crop.map(ECOSYSTEMS)
    df["region_code"] = assign_region(df.geo)
    df["polygon"] = df.geo.replace(PSA_TO_POLYGON)
    if polygons is not None:
        missing = sorted(set(df.polygon) - set(polygons))
        if missing:
            raise KeyError(f"PSA provinces without a boundary polygon: {missing}")
    w = df.groupby(["ecosystem", "region_code", "polygon"]).production_t.sum().reset_index()
    w["weight"] = w.production_t / w.groupby(["ecosystem", "region_code"]).production_t.transform("sum")
    return w.drop(columns="production_t")
