"""Region sets, ERA5 land cells and the cell weights of each section (Eq. 7 of the agricultural note,
Eq. 2 of the electricity note, Section 8 of the labour note).

A *piece* is the part of an ERA5 cell that lies inside one region. Each piece gets an area (exact polygon
overlap), a cropland area and a population (sums over the pixels of the land-cover and population rasters
whose centres fall in it). Within a region, weights are the pieces' shares.
"""
from __future__ import annotations


import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from . import config as C

EQUAL_AREA = 6933            # EASE-Grid 2.0 (equal area), as process_era5_monthly.py
EARTH_R_KM = 6371.0072


# ------------------------------------------------------------------ region sets
def region_sets(cfg: dict) -> dict[str, gpd.GeoDataFrame]:
    """r16: the 16 regions of the agricultural note (pre-2024, no NCR); r17: the same plus NCR."""
    r16 = gpd.read_file(C.path(cfg, "regions16"))[["region", "code", "geometry"]].to_crs(4326)
    adm1 = gpd.read_file(C.path(cfg, "adm1")).to_crs(4326)
    ncr = adm1[adm1["shapeName"].str.upper().isin(["NCR", "NATIONAL CAPITAL REGION", "METRO MANILA"])]
    if len(ncr) != 1:
        raise SystemExit("NCR not found in the ADM1 file (shapeName 'NCR')")
    ncr = gpd.GeoDataFrame({"region": ["NATIONAL CAPITAL REGION (NCR)"], "code": ["NCR"]},
                           geometry=[shapely.union_all(ncr.geometry.values)], crs=4326)
    order = {c: i for i, c in enumerate(C.REGION_ORDER)}
    out = {}
    for name, g in (("r16", r16), ("r17", pd.concat([r16, ncr], ignore_index=True))):
        g = gpd.GeoDataFrame(g, crs=4326)
        g["_o"] = g["code"].map(order)
        if g["_o"].isna().any():
            raise SystemExit(f"unknown region codes: {g.loc[g['_o'].isna(), 'code'].tolist()}")
        out[name] = g.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    return out


# ------------------------------------------------------------------ cells
def cell_polygons(lat: np.ndarray, lon: np.ndarray) -> gpd.GeoDataFrame:
    dlat, dlon = abs(np.median(np.diff(lat))), abs(np.median(np.diff(lon)))
    lon2, lat2 = np.meshgrid(lon, lat)
    boxes = shapely.box(lon2.ravel() - dlon / 2, lat2.ravel() - dlat / 2, lon2.ravel() + dlon / 2, lat2.ravel() + dlat / 2)
    return gpd.GeoDataFrame({"cell": np.arange(lat2.size)}, geometry=boxes, crs=4326)


def overlap_table(cells: gpd.GeoDataFrame, regions: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per (region, cell) that intersect, with the intersection area in km²."""
    polys = regions.to_crs(EQUAL_AREA).reset_index(drop=True)
    polys["ridx"] = np.arange(len(polys))
    inter = gpd.overlay(cells.to_crs(EQUAL_AREA), polys[["ridx", "geometry"]], how="intersection", keep_geom_type=True)
    return pd.DataFrame({"ridx": inter["ridx"].to_numpy(), "cell": inter["cell"].to_numpy(),
                         "area": inter.geometry.area.to_numpy() / 1e6})


def boundary_land_fraction(cfg: dict, lat, lon) -> np.ndarray:
    """Share of each cell inside the Philippine land polygons (ADM1, all regions), as process_era5_monthly.py."""
    cells = cell_polygons(lat, lon)
    land = gpd.read_file(C.path(cfg, "adm1"))
    ov = overlap_table(cells, land).groupby("cell")["area"].sum()
    area = cells.to_crs(EQUAL_AREA).area.to_numpy() / 1e6
    frac = np.zeros(len(cells))
    frac[ov.index.to_numpy()] = ov.to_numpy() / area[ov.index.to_numpy()]
    return frac


def land_mask(cfg: dict, lat, lon, swvl_root: np.ndarray) -> tuple[np.ndarray, str, dict]:
    """Cells kept by the model (Section 3.3.2: ERA5 land fraction of at least 0.5).

    With the ERA5 land-sea mask file (paths.land_sea_mask): mask >= threshold. Without it the step stops, unless
    land.allow_fallback is true: then at least half the cell inside the land polygons (as process_era5_monthly.py)
    and not a sea point of ERA5 (root-zone soil water above the proxy level in some month; ERA5 sea points have
    soil water of about zero). The fallback is only an approximation: on the 2020 mask it keeps 35 cells that ERA5
    treats as sea and misses 17 land cells. The CDS interpolates soil water to the 0.25-degree grid without regard
    to the coast, so soil water alone cannot stand in for the mask."""
    thr, proxy = cfg["land"]["lsm_threshold"], cfg["land"]["soil_water_proxy"]
    frac = boundary_land_fraction(cfg, lat, lon)
    fallback = (frac >= thr) & (np.nanmax(swvl_root, axis=0) >= proxy)
    p = C.path(cfg, "land_sea_mask")
    if p is not None and p.exists():
        from .era5 import open_any
        ds = open_any(p)
        var = "lsm" if "lsm" in ds else [v for v in ds.data_vars if ds[v].ndim >= 2][0]
        da = ds[var]
        for d in list(da.dims):
            if d not in ("latitude", "longitude"):
                da = da.isel({d: 0}, drop=True)
        da = da.sel(latitude=np.asarray(lat), longitude=np.asarray(lon), method="nearest", tolerance=1e-3)
        lsm = np.asarray(da.values).reshape(len(lat), len(lon)).ravel()
        soil = np.nanmax(swvl_root, axis=0) >= proxy
        near = frac > 0
        mask = (lsm >= thr) & soil                 # a cell with no soil water is a sea point of the land model
        info = {"source": f"ERA5 land-sea mask >= {thr} ({p.name}), excluding cells without soil water",
                "cells_kept": int((mask & near).sum()),
                "cells_dropped_for_no_soil_water": int(((lsm >= thr) & ~soil & near).sum()),
                "cells_differing_from_fallback_rule": int((mask != fallback)[near].sum())}
        return mask, "lsm", info
    if not cfg["land"].get("allow_fallback", False):
        raise SystemExit(f"The ERA5 land-sea mask is missing ({p}). The model keeps the cells with an ERA5 land fraction "
                         f">= {thr} (v5, Section 3.3.2), which needs this file: copy era5_land_sea_mask_0.25deg_phl.nc "
                         "from the en_shock repository (data/era5/) to that path, or download it with "
                         "python scripts/00_download_inputs.py --lsm. (Set land.allow_fallback: true to use the "
                         "approximate rule from the region polygons instead.)")
    return fallback, "fallback", {"source": f"no land-sea mask file ({p}): boundary land fraction >= {thr} and "
                                            f"root-zone soil water >= {proxy} in some month", "cells_kept": int(fallback.sum())}


# ------------------------------------------------------------------ rasters
def read_cropland(cfg: dict):
    """Cropland fraction per pixel from the cropped ESA CCI / C3S land-cover file (or None)."""
    p = C.path(cfg, "cropland")
    if p is None or not p.exists():
        return None
    from .era5 import open_any
    ds = open_any(p)
    da = ds["lccs_class"]
    if "time" in da.dims:
        da = da.isel(time=0, drop=True)
    lat_name = "lat" if "lat" in da.dims else "latitude"
    lon_name = "lon" if "lon" in da.dims else "longitude"
    da = da.sel({lat_name: slice(23, 3) if da[lat_name][0] > da[lat_name][-1] else slice(3, 23),
                 lon_name: slice(115, 129)})
    cls = np.asarray(da.values).astype(np.int16)
    cls[cls < 0] += 256                                   # byte stored as signed
    frac_map = {int(k): float(v) for k, v in cfg["weights"]["cropland_classes"].items()}
    lut = np.zeros(256, np.float32)
    for k, v in frac_map.items():
        lut[k] = v
    frac = lut[np.clip(cls, 0, 255)]
    la, lo = da[lat_name].values, da[lon_name].values
    if la[0] < la[-1]:
        la, frac = la[::-1], frac[::-1]
    area = pixel_area_km2(la, abs(lo[1] - lo[0]), abs(la[1] - la[0]))
    return dict(values=frac * area[:, None], lat=la, lon=lo, label=f"cropland km² ({p.name})")


def read_population(cfg: dict):
    """Population per pixel from a GeoTIFF in geographic coordinates (WorldPop), or None."""
    p = C.path(cfg, "population")
    if p is None or not p.exists():
        return None
    import rasterio
    with rasterio.open(p) as src:
        if src.crs is not None and src.crs.to_epsg() not in (4326, None):
            raise SystemExit(f"{p.name}: expected a raster in EPSG:4326 (WorldPop); got {src.crs}")
        v = src.read(1, masked=True).filled(0).astype(np.float64)
        t = src.transform
    v[~np.isfinite(v) | (v < 0)] = 0
    lon = t.c + (np.arange(v.shape[1]) + 0.5) * t.a
    lat = t.f + (np.arange(v.shape[0]) + 0.5) * t.e
    return dict(values=v, lat=lat, lon=lon, label=f"population ({p.name})")


def pixel_area_km2(lat_centres, dlon_deg, dlat_deg):
    phi = np.deg2rad(lat_centres)
    return (EARTH_R_KM ** 2) * np.deg2rad(dlon_deg) * np.deg2rad(dlat_deg) * np.cos(phi)


def raster_pieces(r: dict, regions: gpd.GeoDataFrame, lat, lon, land: np.ndarray, burn_last: str | None = "NCR",
                  chunk: int = 1500) -> tuple[pd.DataFrame, np.ndarray]:
    """Sum of a raster over every (region, cell) piece, counting pixels by their centres.

    Returns the pieces (ridx, cell, value) over land cells, and each region's total over all its pixels
    (to report how much of the region's cropland or population the land cells capture)."""
    from rasterio import features
    from rasterio.transform import from_origin
    la, lo, V = r["lat"], r["lon"], r["values"]
    dlat, dlon = abs(la[1] - la[0]), abs(lo[1] - lo[0])
    transform = from_origin(lo[0] - dlon / 2, la[0] + dlat / 2, dlon, dlat)
    order = list(range(len(regions)))
    if burn_last is not None and burn_last in set(regions["code"]):
        i = int(np.where(regions["code"].to_numpy() == burn_last)[0][0])
        order = [j for j in order if j != i] + [i]                # NCR wins where polygons from two sources overlap
    shapes = [(regions.geometry.iloc[j], j) for j in order]
    R = features.rasterize(shapes, out_shape=V.shape, transform=transform, fill=-1, dtype="int16")
    glat0, gdlat = lat[0], lat[1] - lat[0]
    glon0, gdlon = lon[0], lon[1] - lon[0]
    ilon = np.round((lo - glon0) / gdlon).astype(int)
    okc = (ilon >= 0) & (ilon < len(lon))
    ncell = len(lat) * len(lon)
    acc = np.zeros(len(regions) * ncell)
    tot = np.zeros(len(regions))
    for r0 in range(0, V.shape[0], chunk):
        Rs, Vs = R[r0:r0 + chunk], V[r0:r0 + chunk]
        ilat = np.round((la[r0:r0 + chunk] - glat0) / gdlat).astype(int)
        okr = (ilat >= 0) & (ilat < len(lat))
        inreg = Rs >= 0
        tot += np.bincount(Rs[inreg], weights=Vs[inreg], minlength=len(regions))
        cell = (np.clip(ilat, 0, len(lat) - 1)[:, None] * len(lon) + np.clip(ilon, 0, len(lon) - 1)[None, :])
        ok = inreg & okr[:, None] & okc[None, :]
        ok &= land[cell]
        key = Rs[ok].astype(np.int64) * ncell + cell[ok]
        acc += np.bincount(key, weights=Vs[ok], minlength=len(acc))
    nz = np.nonzero(acc)[0]
    return pd.DataFrame({"ridx": nz // ncell, "cell": nz % ncell, "value": acc[nz]}), tot


# ------------------------------------------------------------------ weights
def weight_matrix(pieces: pd.DataFrame, cells: np.ndarray, n_regions: int, col: str) -> np.ndarray:
    """Regions x cells, rows summing to one."""
    pos = pd.Series(np.arange(len(cells)), index=cells)
    p = pieces[pieces["cell"].isin(cells) & (pieces[col] > 0)]
    W = np.zeros((n_regions, len(cells)))
    np.add.at(W, (p["ridx"].to_numpy(), pos[p["cell"]].to_numpy()), p[col].to_numpy())
    s = W.sum(1, keepdims=True)
    return np.divide(W, s, out=np.zeros_like(W), where=s > 0)


def nearest_cell_map(lat, lon, cells: np.ndarray) -> np.ndarray:
    """For every grid cell, the nearest of `cells` (great-circle distance between centres, km); `cells` map to
    themselves. On a regular grid several cells can be exactly equally far; distances are rounded to a metre
    and the tie goes to the lowest cell index (the northernmost, then westernmost), so the result does not
    depend on the machine."""
    nlon = len(lon)
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    phi = np.deg2rad(np.repeat(lat, nlon))
    lam = np.deg2rad(np.tile(lon, len(lat)))
    cells = np.sort(np.asarray(cells))
    phi_c, lam_c = phi[cells], lam[cells]
    best = np.empty(len(phi), dtype=np.int64)
    for i0 in range(0, len(phi), 2000):
        p0, l0 = phi[i0:i0 + 2000, None], lam[i0:i0 + 2000, None]
        h = np.sin((phi_c[None] - p0) / 2) ** 2 + np.cos(p0) * np.cos(phi_c[None]) * np.sin((lam_c[None] - l0) / 2) ** 2
        d = np.round(2 * EARTH_R_KM * np.arcsin(np.sqrt(h)), 3)
        best[i0:i0 + 2000] = cells[np.argmin(d, axis=1)]          # argmin returns the first of equal distances
    best[cells] = cells
    return best


def piece_moves(P: pd.DataFrame, target: np.ndarray, lat, lon, kinds: list[str]) -> pd.DataFrame:
    """The pieces in cells the model drops (islands and coastal slivers): the cell they come from, the model
    cell they are moved to, the great-circle distance between the two cell centres (km) and what they carry."""
    m = P[target[P["cell"].to_numpy()] != P["cell"].to_numpy()].rename(columns={"cell": "from_cell"}).copy()
    m["to_cell"] = target[m["from_cell"].to_numpy()]
    nlon = len(lon)
    la = np.deg2rad(np.asarray(lat, float)[np.stack([m["from_cell"] // nlon, m["to_cell"] // nlon])])
    lo = np.deg2rad(np.asarray(lon, float)[np.stack([m["from_cell"] % nlon, m["to_cell"] % nlon])])
    h = np.sin((la[1] - la[0]) / 2) ** 2 + np.cos(la[0]) * np.cos(la[1]) * np.sin((lo[1] - lo[0]) / 2) ** 2
    m["distance_km"] = 2 * EARTH_R_KM * np.arcsin(np.sqrt(h))
    return m[["ridx", "from_cell", "to_cell", "distance_km"] + kinds].reset_index(drop=True)


def reassign_pieces(P: pd.DataFrame, target: np.ndarray, kinds: list[str]) -> pd.DataFrame:
    """Move every piece to target[cell] (the nearest model cell), keeping its region. `<kind>_reassigned`
    holds the part of `<kind>` that came from cells the model drops."""
    P = P.copy()
    moved = target[P["cell"].to_numpy()] != P["cell"].to_numpy()
    for k in kinds:
        P[f"{k}_reassigned"] = np.where(moved, P[k], 0.0)
    P["cell"] = target[P["cell"].to_numpy()]
    return P.groupby(["ridx", "cell"], as_index=False)[kinds + [f"{k}_reassigned" for k in kinds]].sum()


def build_weights(cfg: dict, lat, lon, land: np.ndarray) -> dict:
    """Cells used by the model and the weight matrices of every region set and weight kind.

    The model cells are the land cells that overlap a region. Land in cells the model drops (mostly small
    islands in cells below the land-fraction threshold) is not lost: each such piece is moved, with its area,
    cropland and population, to the nearest model cell, and still counts for its own region."""
    sets = region_sets(cfg)
    cells_gdf = cell_polygons(lat, lon)
    crop, pop = read_cropland(cfg), read_population(cfg)
    out = {"lat": lat, "lon": lon, "sets": {}, "pieces": {}}
    union = set()
    for name, g in sets.items():
        ov = overlap_table(cells_gdf, g)
        ov = ov[ov["area"] > 1e-6]
        union |= set(ov.loc[land[ov["cell"].to_numpy()], "cell"].tolist())
        out["pieces"][name] = {"regions": g, "overlap": ov}
    cells = np.array(sorted(union))
    out["cells"] = cells
    # candidates are model cells only, so land outside the regions (e.g. Sabah, in the ERA5 box) is never a target
    target = nearest_cell_map(lat, lon, cells)
    everywhere = np.ones(len(lat) * len(lon), dtype=bool)
    for name, d in out["pieces"].items():
        g, ov = d["regions"], d["overlap"]
        P = ov.groupby(["ridx", "cell"], as_index=False)["area"].sum()
        totals = {"area": g.to_crs(EQUAL_AREA).area.to_numpy() / 1e6}
        sources = {"area": "polygon overlap area"}
        kinds = ["area"]
        for kind, r in (("cropland", crop), ("population", pop)):
            if r is None:
                continue
            pr, tot = raster_pieces(r, g, lat, lon, everywhere)
            P = P.merge(pr.rename(columns={"value": kind}), on=["ridx", "cell"], how="outer").fillna(0.0)
            totals[kind] = tot
            sources[kind] = r["label"]
            kinds.append(kind)
        d["moves"] = piece_moves(P, target, lat, lon, kinds)
        P = reassign_pieces(P, target, kinds)
        d["pieces"] = P
        mats, flags, coverage, reassigned = {}, {}, {}, {}
        for kind in ("area", "cropland", "population"):
            use = kind if kind in P.columns else cfg["weights"].get("fallback", "area")
            W = weight_matrix(P, cells, len(g), use)
            empty = W.sum(1) == 0
            if empty.any() and use != "area":                       # a region with none of this weight: use area
                Wa = weight_matrix(P, cells, len(g), "area")
                W[empty] = Wa[empty]
            mats[kind] = W
            flags[kind] = {"source": sources.get(use, use), "fallback": use != kind,
                           "regions_on_area": g["code"][empty].tolist() if use != "area" else []}
            if use in totals:
                den = np.where(totals[use] > 0, totals[use], np.nan)
                by = P.groupby("ridx")[[use, f"{use}_reassigned"]].sum().reindex(range(len(g))).fillna(0)
                # share in the region's own land cells (as before reassignment), and share moved to a nearest cell
                coverage[kind] = pd.Series((by[use] - by[f"{use}_reassigned"]).to_numpy() / den,
                                           index=g["code"].to_numpy())
                reassigned[kind] = pd.Series(by[f"{use}_reassigned"].to_numpy() / den, index=g["code"].to_numpy())
        out["sets"][name] = dict(regions=g["region"].tolist(), codes=g["code"].tolist(), W=mats, flags=flags,
                                 coverage=pd.DataFrame(coverage), reassigned=pd.DataFrame(reassigned), geometry=g)
    return out


def majority_region(W_raw: pd.DataFrame, cells: np.ndarray, codes: list[str], col: str) -> np.ndarray:
    """Code of the region holding most of each cell's own `col` (area, cropland or population); land moved in
    from dropped cells does not count, so a nearby island cannot relabel a cell."""
    pos = pd.Series(np.arange(len(cells)), index=cells)
    p = W_raw[W_raw["cell"].isin(cells)]
    own = p[col] - p[f"{col}_reassigned"] if f"{col}_reassigned" in p else p[col]
    M = np.zeros((len(codes), len(cells)))
    np.add.at(M, (p["ridx"].to_numpy(), pos[p["cell"]].to_numpy()), own.to_numpy())
    best = M.argmax(0)
    lab = np.array(codes, dtype=object)[best]
    lab[M.max(0) <= 0] = None
    return lab


def grid_of(cfg: dict) -> dict[str, str]:
    return {code: g for g, codes in cfg["grids"].items() for code in codes}
