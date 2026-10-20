"""Typhoon wind exposure by province and quarter, from IBTrACS tracks.

Method (standard parametric approach, as in the economics/CAT literature):
1. Tracks: IBTrACS v04r01 Western Pacific, main and provisional tracks (no spurs),
   interpolated from 3-hourly to hourly so fast storms do not skip provinces.
   Wind = USA_WIND (JTWC 1-min sustained, kt); where missing, WMO_WIND (10-min) / 0.88.
2. Wind field: modified Rankine vortex, V(r) = Vmax * r/R inside the radius of maximum
   wind R, Vmax * (R/r)^0.5 outside. R from Willoughby et al. (2006),
   R = 46.4 * exp(-0.0155 Vmax + 0.0169 |lat|) km, used for ALL years so the measure does
   not change when observed radii start to be reported (USA_RMW is ~40% complete).
   Forward-speed asymmetry and surface roughness are ignored.
3. Points: a 0.05 degree grid (~5.5 km) inside each province; each point gets the
   maximum wind of each storm.
4. Damage index per point and storm: Emanuel (2011) f = v^3 / (1 + v^3),
   v = max(V - 25.7, 0) / (74.7 - 25.7), V in m/s (thresholds as in CLIMADA's default
   tropical-cyclone impact function). f is a fraction in [0, 1).
5. Province x storm: mean of f over the province's points (= share of the province hit,
   weighted by intensity); the storm is dated to the quarter in which the province's
   mean wind peaks. Province x quarter: storms combined as 1 - prod(1 - f).
Also returned, for robustness: maximum wind (m/s, province mean of per-point maxima) and
the number of storms whose centre passed within 100 km of the province.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import contains_xy

DATA = Path(__file__).resolve().parents[2] / "data" / "hazards"
KT = 0.514444  # knots -> m/s
V_THRESH, V_HALF = 25.7, 74.7  # m/s
EARTH_R = 6371.0
BBOX = dict(lat=(0.0, 27.0), lon=(110.0, 133.0))  # Philippines plus ~500 km

# PSA province name -> boundary polygon (geoBoundaries 2020 ADM2). Cities that PSA lists
# separately take the polygon of the province they lie in.
PSA_TO_POLYGON = {
    "Bacolod City": "Negros Occidental", "Butuan City": "Agusan del Norte",
    "City of Davao": "Davao del Sur", "Zamboanga City": "Zamboanga del Sur",
    "Puerto Princesa City": "Palawan", "Cotabato (North Cotabato)": "Cotabato",
    "Davao de Oro (Compostela Valley)": "Compostela Valley",
    "Maguindanao del Norte": "Maguindanao", "Maguindanao del Sur": "Maguindanao",
    "Tawi-tawi": "Tawi-Tawi",
}
# boundary units folded into a neighbour (no separate PSA rice row)
POLYGON_MERGE = {"City of Isabela": "Basilan", "Cotabato City": "Maguindanao"}


def load_provinces() -> gpd.GeoDataFrame:
    g = gpd.read_file(DATA / "boundaries" / "geoBoundaries-PHL-ADM2_simplified.geojson")
    g = g[~g.shapeName.str.startswith("NCR")].copy()
    g["polygon"] = g.shapeName.replace(POLYGON_MERGE)
    return g.dissolve("polygon").reset_index()[["polygon", "geometry"]]


def grid_points(prov: gpd.GeoDataFrame, step: float = 0.05) -> pd.DataFrame:
    rows = []
    for name, geom in zip(prov.polygon, prov.geometry):
        x0, y0, x1, y1 = geom.bounds
        xs, ys = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
        xs, ys = xs.ravel(), ys.ravel()
        inside = contains_xy(geom, xs, ys)
        if not inside.any():  # very small island: use a representative point
            p = geom.representative_point()
            xs, ys, inside = np.array([p.x]), np.array([p.y]), np.array([True])
        rows.append(pd.DataFrame({"polygon": name, "lon": xs[inside], "lat": ys[inside]}))
    return pd.concat(rows, ignore_index=True)


def load_tracks(first_season: int = 1986) -> pd.DataFrame:
    cols = ["SID", "SEASON", "NAME", "ISO_TIME", "TRACK_TYPE", "LAT", "LON",
            "USA_WIND", "WMO_WIND"]
    t = pd.read_csv(DATA / "ibtracs" / "ibtracs.WP.list.v04r01.csv", skiprows=[1],
                    usecols=cols, low_memory=False, na_values=[" ", ""])
    t = t[(t.SEASON >= first_season) & ~t.TRACK_TYPE.str.startswith("spur")].copy()
    for c in ["LAT", "LON", "USA_WIND", "WMO_WIND"]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["vmax"] = t.USA_WIND.fillna(t.WMO_WIND / 0.88) * KT
    t["time"] = pd.to_datetime(t.ISO_TIME)
    t = t.dropna(subset=["LAT", "LON", "vmax"])
    # keep storms that enter the box at any point
    inbox = t.LAT.between(*BBOX["lat"]) & t.LON.between(*BBOX["lon"])
    t = t[t.SID.isin(t.loc[inbox, "SID"].unique())]
    out = []
    for sid, s in t.groupby("SID"):
        s = s.drop_duplicates("time").set_index("time").sort_index()
        hourly = s[["LAT", "LON", "vmax"]].resample("1h").interpolate("time")
        hourly["SID"], hourly["NAME"] = sid, s["NAME"].iloc[0]
        out.append(hourly.reset_index())
    return pd.concat(out, ignore_index=True)


def _haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl, dp = np.radians(lon2 - lon1), p2 - p1
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def rankine(vmax, lat, dist_km):
    rmax = 46.4 * np.exp(-0.0155 * vmax + 0.0169 * np.abs(lat))
    rmax = np.maximum(rmax, 5.0)
    return np.where(dist_km < rmax, vmax * dist_km / rmax, vmax * (rmax / dist_km) ** 0.5)


def emanuel(v):
    x = np.clip(v - V_THRESH, 0, None) / (V_HALF - V_THRESH)
    return x ** 3 / (1 + x ** 3)


def storm_province_exposure(tracks: pd.DataFrame, pts: pd.DataFrame,
                            near_km: float = 100.0) -> pd.DataFrame:
    """One row per storm x province with nonzero wind exposure."""
    plat, plon = pts.lat.to_numpy(), pts.lon.to_numpy()
    codes, names = pd.factorize(pts.polygon)
    n_poly = len(names)
    rows = []
    for sid, s in tracks.groupby("SID"):
        # skip time steps whose centre is > 600 km from the box around the islands
        s = s[s.LAT.between(2, 24) & s.LON.between(113, 130)]
        if s.empty:
            continue
        d = _haversine(s.LAT.to_numpy()[:, None], s.LON.to_numpy()[:, None], plat, plon)
        v = rankine(s.vmax.to_numpy()[:, None], s.LAT.to_numpy()[:, None], np.maximum(d, 0.1))
        vmax_pt = v.max(axis=0)
        f_pt = emanuel(vmax_pt)
        # province means
        cnt = np.bincount(codes, minlength=n_poly)
        f_prov = np.bincount(codes, f_pt, n_poly) / cnt
        v_prov = np.bincount(codes, vmax_pt, n_poly) / cnt
        near = np.zeros(n_poly, bool)
        near[np.unique(codes[(d.min(axis=0) < near_km)])] = True
        # time of peak province-mean wind -> quarter
        vt = np.stack([np.bincount(codes, row, n_poly) / cnt for row in v])  # T x provinces
        t_peak = s.time.to_numpy()[vt.argmax(axis=0)]
        keep = (v_prov > 10) | near  # > ~20 kt somewhere relevant
        for i in np.flatnonzero(keep):
            rows.append((sid, s.NAME.iloc[0], names[i], pd.Timestamp(t_peak[i]),
                         f_prov[i], v_prov[i], near[i]))
    out = pd.DataFrame(rows, columns=["SID", "storm", "polygon", "time_peak", "damage_index",
                                      "max_wind_ms", "centre_within_100km"])
    out["period"] = out.time_peak.dt.to_period("Q")
    return out


def province_quarter(storm_prov: pd.DataFrame) -> pd.DataFrame:
    g = storm_prov.groupby(["polygon", "period"])
    return pd.DataFrame({
        "damage_index": g.damage_index.apply(lambda f: 1 - np.prod(1 - f)),
        "max_wind_ms": g.max_wind_ms.max(),
        "n_storms_100km": g.centre_within_100km.sum(),
    }).reset_index()
