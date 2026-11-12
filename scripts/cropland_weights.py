#!/usr/bin/env python3
"""Cropland weights of the 16 regions on the ERA5 grid (Eq. 7 of the agricultural note), with the island fix.

For every ERA5 cell kept by the model and every region it overlaps, the weight is the share of the region's
cropland (km2) that lies in that cell. Cropland comes from the ESA CCI land cover (LCCS classes below); a
land-cover pixel belongs to the cell and the region that hold its centre.

Island fix. Land in ERA5 cells that the model drops (cells below the land-fraction threshold: small islands
and coastal slivers) is not lost. Each such piece is moved to the NEAREST KEPT CELL, measured between cell
centres, and still counts for its own region. Only kept cells are candidates, and the kept cells are the
cells overlapping the Philippine regions, so a cell in north Sabah or Indonesia is never chosen. The nearest cell can lie in another region (Basilan
may go to a Zamboanga cell): the cropland stays with the island's own region, and the cell then counts for both.
Equally distant cells (common on a regular grid) are broken by the lowest cell index, so the result is the same
on every machine.

Outputs (default: data/agriculture/cropland_weights/):
  cropland_weights_16regions.csv       one row per (region, kept cell): cropland and area, how much came from
                                       dropped cells, and the weights w_cropland (rows of a region sum to 1) and w_area
  island_reassignment_16regions.csv    one row per piece moved: from-cell, to-cell, distance_km, cropland, flags

  python scripts/make_regions.py                           # once: writes data/boundaries/phl_16_regions.gpkg
  python scripts/cropland_weights.py                       # from the repository root
  python scripts/cropland_weights.py --far-km 100          # flag moves longer than 100 km

Needs: numpy pandas geopandas shapely rasterio xarray netCDF4
"""
from __future__ import annotations

import argparse
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from rasterio import features
from rasterio.transform import from_origin

EQUAL_AREA = 6933                       # EASE-Grid 2.0, as process_era5_monthly.py
EARTH_R_KM = 6371.0072
# ESA CCI LCCS classes counted as cropland, and the share of the pixel that is cropland
CROPLAND_CLASSES = {10: 1.0, 11: 1.0, 12: 1.0, 20: 1.0, 30: 0.75, 40: 0.25}
ROOT = pathlib.Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ grid and overlaps
def era5_grid(era5_dir: pathlib.Path | None):
    """The ERA5 grid of the project (0.25 degrees, 22N-4N, 116E-127.5E), or that of any file in `era5_dir`."""
    if era5_dir is None:
        return np.arange(22, 3.99, -0.25), np.arange(116, 127.51, 0.25)
    ds = xr.open_dataset(sorted(era5_dir.glob("*.nc"))[0])
    return ds["latitude"].values.astype(float), ds["longitude"].values.astype(float)


def cell_polygons(lat, lon) -> gpd.GeoDataFrame:
    import shapely
    dlat, dlon = abs(np.median(np.diff(lat))), abs(np.median(np.diff(lon)))
    lon2, lat2 = np.meshgrid(lon, lat)
    boxes = shapely.box(lon2.ravel() - dlon / 2, lat2.ravel() - dlat / 2, lon2.ravel() + dlon / 2, lat2.ravel() + dlat / 2)
    return gpd.GeoDataFrame({"cell": np.arange(lat2.size)}, geometry=boxes, crs=4326)


def overlap_table(cells: gpd.GeoDataFrame, regions: gpd.GeoDataFrame) -> pd.DataFrame:
    polys = regions.to_crs(EQUAL_AREA).reset_index(drop=True)
    polys["ridx"] = np.arange(len(polys))
    inter = gpd.overlay(cells.to_crs(EQUAL_AREA), polys[["ridx", "geometry"]], how="intersection", keep_geom_type=True)
    return pd.DataFrame({"ridx": inter["ridx"].to_numpy(), "cell": inter["cell"].to_numpy(),
                         "area": inter.geometry.area.to_numpy() / 1e6})


# ------------------------------------------------------------------ cropland raster
def pixel_area_km2(lat_centres, dlon_deg, dlat_deg):
    phi = np.deg2rad(lat_centres)
    return (EARTH_R_KM ** 2) * np.deg2rad(dlon_deg) * np.deg2rad(dlat_deg) * np.cos(phi)


def read_cropland(path: pathlib.Path):
    ds = xr.open_dataset(path)
    da = ds["lccs_class"]
    if "time" in da.dims:
        da = da.isel(time=0, drop=True)
    lat_name = "lat" if "lat" in da.dims else "latitude"
    lon_name = "lon" if "lon" in da.dims else "longitude"
    da = da.sel({lat_name: slice(23, 3) if da[lat_name][0] > da[lat_name][-1] else slice(3, 23),
                 lon_name: slice(115, 129)})
    cls = np.asarray(da.values).astype(np.int16)
    cls[cls < 0] += 256                                   # byte stored as signed
    lut = np.zeros(256, np.float32)
    for k, v in CROPLAND_CLASSES.items():
        lut[k] = v
    frac = lut[np.clip(cls, 0, 255)]
    la, lo = da[lat_name].values, da[lon_name].values
    if la[0] < la[-1]:
        la, frac = la[::-1], frac[::-1]
    area = pixel_area_km2(la, abs(lo[1] - lo[0]), abs(la[1] - la[0]))
    return dict(values=frac * area[:, None], lat=la, lon=lo)


def raster_pieces(r: dict, regions: gpd.GeoDataFrame, lat, lon, chunk: int = 1500) -> pd.DataFrame:
    """Raster sum (km2 of cropland) over every (region, cell) piece, counting pixels by their centres."""
    la, lo, V = r["lat"], r["lon"], r["values"]
    dlat, dlon = abs(la[1] - la[0]), abs(lo[1] - lo[0])
    transform = from_origin(lo[0] - dlon / 2, la[0] + dlat / 2, dlon, dlat)
    shapes = [(regions.geometry.iloc[j], j) for j in range(len(regions))]
    R = features.rasterize(shapes, out_shape=V.shape, transform=transform, fill=-1, dtype="int16")
    glat0, gdlat = lat[0], lat[1] - lat[0]
    glon0, gdlon = lon[0], lon[1] - lon[0]
    ilon = np.round((lo - glon0) / gdlon).astype(int)
    okc = (ilon >= 0) & (ilon < len(lon))
    ncell = len(lat) * len(lon)
    acc = np.zeros(len(regions) * ncell)
    for r0 in range(0, V.shape[0], chunk):
        Rs, Vs = R[r0:r0 + chunk], V[r0:r0 + chunk]
        ilat = np.round((la[r0:r0 + chunk] - glat0) / gdlat).astype(int)
        okr = (ilat >= 0) & (ilat < len(lat))
        inreg = Rs >= 0
        cell = (np.clip(ilat, 0, len(lat) - 1)[:, None] * len(lon) + np.clip(ilon, 0, len(lon) - 1)[None, :])
        ok = inreg & okr[:, None] & okc[None, :]
        key = Rs[ok].astype(np.int64) * ncell + cell[ok]
        acc += np.bincount(key, weights=Vs[ok], minlength=len(acc))
    nz = np.nonzero(acc)[0]
    return pd.DataFrame({"ridx": nz // ncell, "cell": nz % ncell, "cropland": acc[nz]})


# ------------------------------------------------------------------ island fix
def nearest_cell_map(lat, lon, cells: np.ndarray) -> np.ndarray:
    """For every grid cell, the nearest of `cells` (great-circle distance between centres, km); `cells` map to
    themselves. Distances are rounded to a metre and ties go to the lowest cell index."""
    nlon = len(lon)
    phi = np.deg2rad(np.repeat(np.asarray(lat, float), nlon))
    lam = np.deg2rad(np.tile(np.asarray(lon, float), len(lat)))
    cells = np.sort(np.asarray(cells))
    phi_c, lam_c = phi[cells], lam[cells]
    best = np.empty(len(phi), dtype=np.int64)
    for i0 in range(0, len(phi), 2000):
        p0, l0 = phi[i0:i0 + 2000, None], lam[i0:i0 + 2000, None]
        h = np.sin((phi_c[None] - p0) / 2) ** 2 + np.cos(p0) * np.cos(phi_c[None]) * np.sin((lam_c[None] - l0) / 2) ** 2
        d = np.round(2 * EARTH_R_KM * np.arcsin(np.sqrt(h)), 3)
        best[i0:i0 + 2000] = cells[np.argmin(d, axis=1)]
    best[cells] = cells
    return best


def piece_moves(P: pd.DataFrame, target: np.ndarray, lat, lon, kinds: list[str]) -> pd.DataFrame:
    m = P[target[P["cell"].to_numpy()] != P["cell"].to_numpy()].rename(columns={"cell": "from_cell"}).copy()
    m["to_cell"] = target[m["from_cell"].to_numpy()]
    nlon = len(lon)
    la = np.deg2rad(np.asarray(lat, float)[np.stack([m["from_cell"] // nlon, m["to_cell"] // nlon])])
    lo = np.deg2rad(np.asarray(lon, float)[np.stack([m["from_cell"] % nlon, m["to_cell"] % nlon])])
    h = np.sin((la[1] - la[0]) / 2) ** 2 + np.cos(la[0]) * np.cos(la[1]) * np.sin((lo[1] - lo[0]) / 2) ** 2
    m["distance_km"] = 2 * EARTH_R_KM * np.arcsin(np.sqrt(h))
    return m[["ridx", "from_cell", "to_cell", "distance_km"] + kinds].reset_index(drop=True)


def reassign_pieces(P: pd.DataFrame, target: np.ndarray, kinds: list[str]) -> pd.DataFrame:
    P = P.copy()
    moved = target[P["cell"].to_numpy()] != P["cell"].to_numpy()
    for k in kinds:
        P[f"{k}_reassigned"] = np.where(moved, P[k], 0.0)
    P["cell"] = target[P["cell"].to_numpy()]
    return P.groupby(["ridx", "cell"], as_index=False)[kinds + [f"{k}_reassigned" for k in kinds]].sum()


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", type=pathlib.Path, default=ROOT / "data/boundaries/phl_16_regions.gpkg")
    ap.add_argument("--cropland", type=pathlib.Path, default=ROOT / "data/agriculture/cropland_weights/esa_cci_lc_2022_phl.nc")
    ap.add_argument("--era5-dir", type=pathlib.Path, default=None,
                    help="optional: take the grid from a file in this folder (default: the project grid, 73 x 47 cells)")
    ap.add_argument("--kept-cells", type=pathlib.Path, default=ROOT / "data/agriculture/cropland_weights/kept_cells.csv",
                    help="the ERA5 cells kept by the model (column 'cell' = row * n_longitudes + column)")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "data/agriculture/cropland_weights")
    ap.add_argument("--far-km", type=float, default=100.0, help="flag moves longer than this")
    a = ap.parse_args()

    lat, lon = era5_grid(a.era5_dir)
    kept = pd.read_csv(a.kept_cells)
    cells = np.sort(kept["cell"].to_numpy())
    chk = kept.set_index("cell")
    if not (np.allclose(lat[cells // len(lon)], chk.loc[cells, "lat"]) and np.allclose(lon[cells % len(lon)], chk.loc[cells, "lon"])):
        raise SystemExit("kept_cells.csv does not match the ERA5 grid")
    g = gpd.read_file(a.regions)[["region", "code", "geometry"]].to_crs(4326).reset_index(drop=True)
    print(f"{len(cells)} kept cells, {len(g)} regions, ERA5 grid {len(lat)} x {len(lon)}")

    ov = overlap_table(cell_polygons(lat, lon), g)
    ov = ov[ov["area"] > 1e-6]
    P = ov.groupby(["ridx", "cell"], as_index=False)["area"].sum()                       # area of each piece, km2
    pr = raster_pieces(read_cropland(a.cropland), g, lat, lon)                           # cropland of each piece, km2
    P = P.merge(pr, on=["ridx", "cell"], how="outer").fillna(0.0)
    target = nearest_cell_map(lat, lon, cells)
    kinds = ["area", "cropland"]
    moves = piece_moves(P, target, lat, lon, kinds)
    P = reassign_pieces(P, target, kinds)

    tot = P.groupby("ridx")["cropland"].sum()
    P["code"] = g["code"].to_numpy()[P["ridx"]]
    P["region"] = g["region"].to_numpy()[P["ridx"]]
    P["w_cropland"] = P["cropland"] / P["ridx"].map(tot)
    P["w_area"] = P["area"] / P["ridx"].map(P.groupby("ridx")["area"].sum())
    P["lat"], P["lon"] = lat[P["cell"] // len(lon)], lon[P["cell"] % len(lon)]
    out = P[["cell", "lat", "lon", "code", "region", "area", "area_reassigned", "cropland", "cropland_reassigned",
             "w_cropland", "w_area"]].rename(columns={"area": "area_km2", "area_reassigned": "area_reassigned_km2",
                                                      "cropland": "cropland_km2", "cropland_reassigned": "cropland_reassigned_km2"})
    out = out.sort_values(["code", "cell"])

    main_region = (P.assign(own=P["area"] - P["area_reassigned"]).sort_values("own", ascending=False)
                   .drop_duplicates("cell").set_index("cell")["code"])                   # region holding most of the cell's own area
    moves["code"] = g["code"].to_numpy()[moves["ridx"]]
    moves["region"] = g["region"].to_numpy()[moves["ridx"]]
    for c in ("from", "to"):
        moves[f"{c}_lat"], moves[f"{c}_lon"] = lat[moves[f"{c}_cell"] // len(lon)], lon[moves[f"{c}_cell"] % len(lon)]
    moves["to_cell_main_region"] = moves["to_cell"].map(main_region)
    moves["to_cell_in_other_region"] = moves["to_cell_main_region"] != moves["code"]
    moves["share_of_region_cropland"] = moves["cropland"] / moves["ridx"].map(tot)
    moves["farther_than_threshold"] = moves["distance_km"] > a.far_km
    moves = moves.rename(columns={"cropland": "cropland_km2", "area": "area_km2"})
    moves = moves[["code", "region", "from_cell", "from_lat", "from_lon", "to_cell", "to_lat", "to_lon", "distance_km",
                   "farther_than_threshold", "to_cell_main_region", "to_cell_in_other_region", "cropland_km2", "area_km2",
                   "share_of_region_cropland"]].sort_values(["code", "distance_km"], ascending=[True, False])

    a.out.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out / "cropland_weights_16regions.csv", index=False, float_format="%.9g")
    moves.to_csv(a.out / "island_reassignment_16regions.csv", index=False, float_format="%.9g")
    sums = out.groupby("code")["w_cropland"].sum()
    far = moves[moves["farther_than_threshold"] & (moves["cropland_km2"] > 0)]
    print(f"wrote {a.out}/cropland_weights_16regions.csv ({len(out)} rows; weights sum to {sums.min():.6f}-{sums.max():.6f} per region)")
    print(f"wrote {a.out}/island_reassignment_16regions.csv ({len(moves)} pieces moved, "
          f"{(moves['cropland_km2'] > 0).sum()} with cropland; {len(far)} of those farther than {a.far_km:g} km, "
          f"{far['share_of_region_cropland'].sum() if len(far) else 0:.4f} of regional cropland summed over regions)")


if __name__ == "__main__":
    main()
