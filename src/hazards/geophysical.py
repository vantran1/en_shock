"""Earthquake and eruption event markers by region and quarter (methodology v5, controls
X_rq: "event markers for major earthquakes and volcanic eruptions"). Exposure markers,
not damage, like the typhoon and flood controls.

Earthquakes: data/hazards/earthquakes/usgs_earthquakes_m6.5_1987-2025.csv (USGS ComCat,
M >= 6.5). Events deeper than 300 km are dropped (felt weakly at the surface); events
whose epicentre is within 100 km of land are kept and assigned to the nearest of the 16
regions (distance 0 if the epicentre is on land). Dated in Philippine Time (UTC+8).

Eruptions: GVP eruption list (sheet "Eruption List", header on the second row) joined to
the GVP volcano list on "Volcano Number" for country and coordinates; Philippines,
VEI >= 3, start year >= 1987. Each eruption marks the quarters from its start to its
end month in the region of the volcano: Pinatubo III, Mayon V, Taal IV-A, Kanlaon VI
(the 2024 ash fell mainly on Negros Occidental); a check version gives Kanlaon to both
VI and VII. Pinatubo 1991 (VEI 6) has its own marker.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
QUAKES = ROOT / "data/hazards/earthquakes/usgs_earthquakes_m6.5_1987-2025.csv"
ERUPTIONS = ROOT / "data/hazards/volcanoes/gvp_eruption_list_holocene_20260424.xlsx"
VOLCANOES = ROOT / "data/hazards/volcanoes/gvp_volcano_list_holocene_v5.4.0.xlsx"
REGIONS_FILE = ROOT / "data/boundaries/phl_16_regions.gpkg"
MAX_DEPTH_KM, MAX_DIST_KM = 300.0, 100.0
MIN_VEI, FIRST_YEAR = 3, 1987
METRIC_CRS = 32651  # UTM 51N
VOLCANO_REGION = {"Pinatubo": ["R03"], "Mayon": ["R05"], "Taal": ["R04A"], "Kanlaon": ["R06"]}
VOLCANO_REGION_CHECK = {**VOLCANO_REGION, "Kanlaon": ["R06", "R07"]}


def regions() -> gpd.GeoDataFrame:
    return gpd.read_file(REGIONS_FILE)[["code", "geometry"]].rename(columns={"code": "region_code"})


def earthquakes() -> pd.DataFrame:
    """All events with depth, distance to land and assigned region; `kept` marks the ones
    used (depth <= 300 km and within 100 km of land)."""
    q = pd.read_csv(QUAKES)
    q["time_pht"] = pd.to_datetime(q["time"], utc=True).dt.tz_convert("Asia/Manila").dt.tz_localize(None)
    pts = gpd.GeoDataFrame(q, geometry=gpd.points_from_xy(q.longitude, q.latitude), crs=4326)
    near = gpd.sjoin_nearest(pts.to_crs(METRIC_CRS), regions().to_crs(METRIC_CRS),
                             how="left", distance_col="dist_land_km")
    near = near[~near.index.duplicated()]
    q["region_code"] = near["region_code"]
    q["dist_land_km"] = near["dist_land_km"] / 1000
    q["period"] = q["time_pht"].dt.to_period("Q")
    q["kept"] = (q["depth"] <= MAX_DEPTH_KM) & (q["dist_land_km"] <= MAX_DIST_KM)
    q["reason_dropped"] = np.select(
        [q["depth"] > MAX_DEPTH_KM, q["dist_land_km"] > MAX_DIST_KM],
        [f"deeper than {MAX_DEPTH_KM:.0f} km", f"more than {MAX_DIST_KM:.0f} km from land"], "")
    return q[["time_pht", "period", "latitude", "longitude", "depth", "mag", "place",
              "dist_land_km", "region_code", "kept", "reason_dropped", "id"]]


def eruptions() -> pd.DataFrame:
    e = pd.read_excel(ERUPTIONS, sheet_name="Eruption List", header=1)
    v = pd.read_excel(VOLCANOES, header=1)[["Volcano Number", "Country", "Latitude", "Longitude"]]
    m = e.merge(v, on="Volcano Number", how="left", validate="m:1")
    m = m[(m["Country"] == "Philippines") & (m["VEI"] >= MIN_VEI) & (m["Start Year"] >= FIRST_YEAR)]
    m = m.copy()
    start = pd.PeriodIndex.from_fields(year=m["Start Year"].astype(int),
                                       month=m["Start Month"].astype(int), freq="M")
    end_y = m["End Year"].fillna(m["Start Year"]).astype(int)
    end_m = m["End Month"].fillna(m["Start Month"]).astype(int)
    end = pd.PeriodIndex.from_fields(year=end_y, month=end_m, freq="M")
    m["start"], m["end"] = start.astype(str), end.astype(str)
    m["first_quarter"], m["last_quarter"] = start.asfreq("Q"), end.asfreq("Q")
    pts = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.Longitude, m.Latitude), crs=4326)
    near = gpd.sjoin_nearest(pts.to_crs(METRIC_CRS), regions().to_crs(METRIC_CRS),
                             how="left", distance_col="d")
    m["region_of_coordinates"] = near.loc[~near.index.duplicated(), "region_code"]
    m["region_code"] = m["Volcano Name"].map(lambda n: "+".join(VOLCANO_REGION[n]))
    m["region_code_check"] = m["Volcano Name"].map(lambda n: "+".join(VOLCANO_REGION_CHECK[n]))
    m["pinatubo_1991"] = (m["Volcano Name"] == "Pinatubo") & (m["Start Year"] == 1991)
    return m[["Volcano Name", "Volcano Number", "VEI", "start", "end", "first_quarter",
              "last_quarter", "Latitude", "Longitude", "region_of_coordinates", "region_code",
              "region_code_check", "pinatubo_1991"]].sort_values("start").reset_index(drop=True)


def region_quarter(quakes: pd.DataFrame, erupt: pd.DataFrame, codes, periods) -> pd.DataFrame:
    """Dummies by region x quarter:
    eq           1 in the quarter of a kept earthquake;
    eq_next      1 in that quarter or the following one;
    eruption     1 in the quarters of an eruption (VEI >= 3), Pinatubo 1991 excluded;
    eruption_kanlaon_vi_vii   same, with Kanlaon in both VI and VII (check);
    pinatubo_1991             1 in the quarters of the 1991 Pinatubo eruption (Region III)."""
    idx = pd.MultiIndex.from_product([codes, periods], names=["region_code", "period"])
    out = pd.DataFrame(0, index=idx, columns=["eq", "eq_next", "eruption",
                                              "eruption_kanlaon_vi_vii", "pinatubo_1991"])
    for _, r in quakes[quakes["kept"]].iterrows():
        for k, col in ((0, "eq"), (0, "eq_next"), (1, "eq_next")):
            key = (r.region_code, r.period + k)
            if key in out.index:
                out.loc[key, col] = 1
    for _, r in erupt.iterrows():
        qs = pd.period_range(r.first_quarter, r.last_quarter, freq="Q")
        cols = [("pinatubo_1991", r.region_code)] if r.pinatubo_1991 else \
            [("eruption", r.region_code), ("eruption_kanlaon_vi_vii", r.region_code_check)]
        for col, regs in cols:
            for reg in regs.split("+"):
                for q in qs:
                    if (reg, q) in out.index:
                        out.loc[(reg, q), col] = 1
    return out.reset_index()
