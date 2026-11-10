"""Regional monthly weather from ERA5 monthly single levels (methodology v5 Table 2, the
monthly-reanalysis rows). Kept monthly: region x month, 1950-01 to 2025-12; no quarterly
aggregation here.

Inputs
- ERA5 .nc files OUTSIDE the repo: folder from config/paths.toml (era5_monthly_dir) or
  --era5-dir; read by climate.era5 (units converted there).
- data/era5/era5_land_sea_mask_0.25deg_phl.nc; data/boundaries/phl_16_regions.gpkg (Van).

Method: land cells (land fraction > 0.5) assigned to Van's 16 regions; area-weighted
regional means (cropland weights of v5 Eq. 7 to come). Derived per cell before averaging:
relative humidity, VPD (from monthly-mean t2m and d2m, which slightly understates the
mean of daily VPD) and root-zone soil moisture (swvl1-3, thickness-weighted).

Run:  python scripts/build_weather_monthly.py [--era5-dir PATH]
Writes
- data/processed/weather_region_month.csv  one row per region x month, one column per variable
- data/processed/era5_region_cells.csv     the cells used and their weights
- outputs/tables/weather_cells_per_region.csv
- outputs/tables/weather_provinces_without_cells.csv  provinces (geoBoundaries ADM2) with no
  land cell centre, i.e. not represented in their region's weather
- outputs/figures/era5_land_sea_mask.png   land fraction, region outlines, cells used
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from climate.era5 import (LAND_MIN, REGIONS_FILE, era5_dir, land_sea_mask, load,  # noqa: E402
                          region_weights, regional_mean, rh_pct, root_zone, vpd_kpa)

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
# output column -> (ERA5 variable, unit after conversion)
COLUMNS = {
    "t2m_c": ("2m_temperature", "deg C"),
    "d2m_c": ("2m_dewpoint_temperature", "deg C"),
    "tp_mm": ("total_precipitation", "mm/month"),
    "e_mm": ("evaporation", "mm/month (positive = evaporation)"),
    "pev_mm": ("potential_evaporation", "mm/month (positive = evaporation)"),
    "ro_mm": ("runoff", "mm/month"),
    "ssrd_mj": ("surface_solar_radiation_downwards", "MJ m-2 day-1"),
    "swvl1": ("volumetric_soil_water_layer_1", "m3 m-3, 0-7 cm"),
    "swvl2": ("volumetric_soil_water_layer_2", "m3 m-3, 7-28 cm"),
    "swvl3": ("volumetric_soil_water_layer_3", "m3 m-3, 28-100 cm"),
    "swvl4": ("volumetric_soil_water_layer_4", "m3 m-3, 100-289 cm"),
}
DERIVED = {"swvl_rz": "m3 m-3, 0-100 cm (thickness-weighted swvl1-3)",
           "rh_pct": "%, from monthly-mean t2m and d2m",
           "vpd_kpa": "kPa, es(t2m) - es(d2m), monthly means"}
INK, MUTED = "#0b0b0b", "#52514e"


def plot_mask(w):
    lsm = land_sea_mask()
    reg = gpd.read_file(REGIONS_FILE)
    ramp = LinearSegmentedColormap.from_list("land", ["#f4f8fd", "#b7d3f6", "#6da7ec", "#2a78d6"])
    fig, ax = plt.subplots(figsize=(7, 9.5), constrained_layout=True)
    step = 0.125
    im = ax.imshow(lsm.values, cmap=ramp, vmin=0, vmax=1, origin="upper",
                   extent=[float(lsm.longitude.min()) - step, float(lsm.longitude.max()) + step,
                           float(lsm.latitude.min()) - step, float(lsm.latitude.max()) + step])
    reg.boundary.plot(ax=ax, color=INK, lw=0.5)
    for kind, mk in (("inside", "o"), ("nearest", "x")):
        c = w[w.assigned == kind]
        ax.scatter(c.longitude, c.latitude, s=9, marker=mk, color="#eb6834", lw=0.8,
                   label=f"cell used ({kind} a region polygon)" if kind == "inside"
                   else "cell used (nearest region, centre off the outline)")
    for lab, (x, y) in {"Luzon": (121.2, 17.8), "Visayas": (123.4, 11.1),
                        "Mindanao": (125.0, 7.6)}.items():
        ax.text(x, y, lab, fontsize=10, color=INK, ha="center", weight="bold")
    cb = fig.colorbar(im, ax=ax, shrink=0.5)
    cb.set_label("ERA5 land fraction (lsm)", fontsize=8, color=MUTED)
    cb.outline.set_visible(False)
    ax.legend(loc="upper right", fontsize=7, frameon=False)
    ax.set_title(f"ERA5 land-sea mask, 0.25°, and the {len(w)} land cells (lsm > {LAND_MIN}) "
                 "used for the 16 regions", fontsize=9, color=INK, loc="left")
    ax.tick_params(labelsize=7, colors=MUTED)
    fig.savefig(FIG / "era5_land_sea_mask.png", dpi=150, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--era5-dir", help="folder of the ERA5 .nc files (overrides config/paths.toml)")
    args = ap.parse_args()
    d = era5_dir(args.era5_dir)
    for p in (PROC, TAB, FIG):
        p.mkdir(parents=True, exist_ok=True)

    w = region_weights()
    w.round(6).to_csv(PROC / "era5_region_cells.csv", index=False)
    cells = (w.groupby("region_code").agg(cells=("lsm", "size"),
                                          nearest=("assigned", lambda s: (s == "nearest").sum()),
                                          max_distance_km=("distance_km", "max"))
             .reset_index())
    cells.to_csv(TAB / "weather_cells_per_region.csv", index=False)
    pts = gpd.GeoDataFrame(w, geometry=gpd.points_from_xy(w.longitude, w.latitude), crs=4326)
    prov = gpd.read_file(ROOT / "data/hazards/boundaries/geoBoundaries-PHL-ADM2_simplified.geojson")
    prov = prov[~prov.shapeName.str.startswith("NCR")][["shapeName", "geometry"]]
    n = gpd.sjoin(prov, pts, predicate="contains", how="left").groupby("shapeName")["index_right"].count()
    pd.DataFrame({"province": sorted(n[n == 0].index)}).to_csv(
        TAB / "weather_provinces_without_cells.csv", index=False)
    plot_mask(w)

    fields = {c: load(v, d) for c, (v, _) in COLUMNS.items()}
    fields["swvl_rz"] = root_zone(fields["swvl1"], fields["swvl2"], fields["swvl3"])
    fields["rh_pct"] = rh_pct(fields["t2m_c"], fields["d2m_c"])
    fields["vpd_kpa"] = vpd_kpa(fields["t2m_c"], fields["d2m_c"])
    parts = []
    for c, da in fields.items():
        m = regional_mean(da, w)
        parts.append(m.stack().rename(c))
    out = pd.concat(parts, axis=1)
    out.index = out.index.set_names(["month", "region_code"])
    out = out.reset_index()
    out["month"] = out["month"].dt.strftime("%Y-%m")
    out = out.sort_values(["region_code", "month"])[["region_code", "month"] + list(fields)]
    if out[list(fields)].isna().any().any():
        raise ValueError("missing values in the regional weather")
    out.to_csv(PROC / "weather_region_month.csv", index=False, float_format="%.5g")

    pd.set_option("display.width", 200)
    print(f"{len(w)} land cells; {(w.assigned == 'nearest').sum()} assigned to the nearest "
          f"region (max {w.distance_km.max():.1f} km)")
    print(cells.to_string(index=False))
    print(f"\nweather: {len(out)} rows ({out.region_code.nunique()} regions x "
          f"{out.month.nunique()} months), "
          f"{(PROC / 'weather_region_month.csv').stat().st_size / 1e6:.1f} MB")
    clim = out.assign(year=out.month.str[:4].astype(int)).query("1991 <= year <= 2020")
    ann = clim.groupby(["region_code", "year"]).agg(tp_mm=("tp_mm", "sum"), t2m_c=("t2m_c", "mean"),
                                                    vpd_kpa=("vpd_kpa", "mean"),
                                                    rh_pct=("rh_pct", "mean"),
                                                    swvl_rz=("swvl_rz", "mean"))
    print("\n1991-2020 annual means by region (sanity check):")
    print(ann.groupby("region_code").mean().round(2).to_string())


if __name__ == "__main__":
    main()
