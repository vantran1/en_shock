#!/usr/bin/env python3
"""
make_regions.py
==================

Build the boundary file with the 16 Philippine regions used in the PSA corn
statistics, named exactly as in those tables.

Source: geoBoundaries gbOpen PHL ADM1 (regions) and ADM2 (provinces), simplified
geometry, which geoBoundaries derived from the NAMRIA / PSA / OCHA administrative
boundaries (2020 vintage, CC BY 3.0 IGO). Downloaded from the geoBoundaries
GitHub repository, or read from local copies with --adm1 / --adm2.

What the script does to the 17 source regions
---------------------------------------------
* drops the National Capital Region (NCR): it has no corn series;
* keeps Negros Occidental in Region VI and Negros Oriental and Siquijor in
  Region VII. The source predates the Negros Island Region (Republic Act 12000,
  2024), so nothing needs undoing; the corn series has no separate NIR;
* moves Cotabato City from Region XII to BARMM, which it joined after the
  2019 plebiscite (the 2020 source still has it in Region XII);
* renames the regions to the PSA labels, e.g. "REGION VI (WESTERN VISAYAS)".

Sulu: the Supreme Court has ruled that Sulu is not part of BARMM. The long
corn series for BARMM includes Sulu for most years, so Sulu stays in BARMM by
default. --sulu separate makes it its own unit, --sulu exclude leaves it out.

Not represented: the 63 barangays of Cotabato province that joined BARMM in
2019 (the Special Geographic Area). They are small relative to the 0.25 degree
ERA5 grid (about 28 km) and stay in Region XII.

ERA5 grid check
---------------
The boundaries do not depend on the climate data, but the ERA5 single-levels grid
(0.25 degrees) is coarser than the ERA5-Land grid (0.1 degrees) used before, and
ERA5 also has values over the sea. After building the regions the script counts
how many ERA5 grid-cell centres fall inside each region and warns about regions
with very few, because a regional average over one or two cells is fragile and
island-heavy regions (BARMM's island provinces, MIMAROPA) may need an
area-weighted or nearest-cell approach in the processing step. Change the
resolution with --grid-res, or switch the check off with --grid-res 0.

Usage
-----
    python make_regions.py                       # download + build
    python make_regions.py --adm1 a1.geojson --adm2 a2.geojson
    python make_regions.py --sulu separate
    python make_regions.py --grid-res 0         # skip the ERA5 grid check

Output: data/boundaries/phl_16_regions.gpkg (columns region, code,
source_name, area_km2) and a JSON sidecar with the sources, checksums and the
ERA5 grid-cell count per region.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

BASE = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/PHL"
URLS = {
    "ADM1": f"{BASE}/ADM1/geoBoundaries-PHL-ADM1_simplified.geojson",
    "ADM2": f"{BASE}/ADM2/geoBoundaries-PHL-ADM2_simplified.geojson",
}
# checksums of the files this script was written and checked against (2026-10-21)
EXPECTED_SHA256 = {
    "ADM1": "8eeef6a9a525a81a647dcaac85e1337b990fc527c4a0e9c70556d5b0905be087",
    "ADM2": "fa77b9f17db2e419acaae714a935f7812be4409e2983675d34020e8426a3e189",
}

# geoBoundaries ADM1 name -> (PSA label as in the corn statistics, short code)
REGIONS = {
    "ARMM": ("BANGSAMORO AUTONOMOUS REGION IN MUSLIM MINDANAO (BARMM)", "BARMM"),
    "CAR": ("CORDILLERA ADMINISTRATIVE REGION (CAR)", "CAR"),
    "Ilocos Region": ("REGION I (ILOCOS REGION)", "R01"),
    "Cagayan Valley": ("REGION II (CAGAYAN VALLEY)", "R02"),
    "Central Luzon": ("REGION III (CENTRAL LUZON)", "R03"),
    "Calabarzon": ("REGION IV-A (CALABARZON)", "R04A"),
    "Mimaropa": ("MIMAROPA REGION", "MIMAROPA"),
    "Bicol Region": ("REGION V (BICOL REGION)", "R05"),
    "Western Visayas": ("REGION VI (WESTERN VISAYAS)", "R06"),
    "Central Visayas": ("REGION VII (CENTRAL VISAYAS)", "R07"),
    "Eastern Visayas": ("REGION VIII (EASTERN VISAYAS)", "R08"),
    "Zamboanga Peninsula": ("REGION IX (ZAMBOANGA PENINSULA)", "R09"),
    "Northern Mindanao": ("REGION X (NORTHERN MINDANAO)", "R10"),
    "Davao Region": ("REGION XI (DAVAO REGION)", "R11"),
    "Soccsksargen": ("REGION XII (SOCCSKSARGEN)", "R12"),
    "Caraga": ("REGION XIII (CARAGA)", "R13"),
}
DROP = {"NCR"}
EQUAL_AREA = 6933
ERA5_RES = 0.25      # degrees, ERA5 single-levels grid (ERA5-Land was 0.1)
MIN_CELLS = 5        # warn when a region has fewer grid-cell centres than this


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(level: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / Path(URLS[level]).name
    if not dest.exists():
        print(f"downloading {URLS[level]}")
        req = urllib.request.Request(URLS[level], headers={"User-Agent": "era5-enso region builder"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if data[:20].startswith(b"version https://git-lfs"):
            raise SystemExit(f"got a Git LFS pointer instead of the file from {URLS[level]}")
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
    return dest


def build(adm1: gpd.GeoDataFrame, adm2: gpd.GeoDataFrame, sulu: str = "barmm") -> tuple[gpd.GeoDataFrame, list[str]]:
    """Return the region table and notes. Geometry operations are done in an equal-area CRS."""
    notes = []
    a1 = adm1.to_crs(EQUAL_AREA).set_index("shapeName")
    a2 = adm2.to_crs(EQUAL_AREA).set_index("shapeName")
    missing = (set(REGIONS) | DROP) - set(a1.index)
    if missing:
        raise SystemExit(f"region names not found in the ADM1 source: {sorted(missing)}; columns/names changed?")
    extra = set(a1.index) - set(REGIONS) - DROP
    if extra:
        raise SystemExit(f"unexpected regions in the ADM1 source (new boundaries?): {sorted(extra)}")
    geoms = {n: a1.geometry[n] for n in REGIONS}

    # Cotabato City -> BARMM (only the part inside Region XII, so the regions stay a partition)
    cc = a2.geometry.get("Cotabato City")
    if cc is None:
        notes.append("Cotabato City not found in ADM2; left as in the source")
    else:
        part = cc.intersection(geoms["Soccsksargen"])
        geoms["Soccsksargen"] = geoms["Soccsksargen"].difference(part)
        geoms["ARMM"] = geoms["ARMM"].union(part)
        notes.append(f"Cotabato City ({part.area / 1e6:.0f} km2) moved from Region XII to BARMM")

    rows = [(REGIONS[n][0], REGIONS[n][1], n, g) for n, g in geoms.items()]
    if sulu != "barmm":
        s = a2.geometry.get("Sulu")
        if s is None:
            raise SystemExit("Sulu not found in ADM2")
        s = s.intersection(geoms["ARMM"])
        i = next(k for k, r in enumerate(rows) if r[1] == "BARMM")
        rows[i] = (*rows[i][:3], rows[i][3].difference(s))
        if sulu == "separate":
            rows.append(("SULU", "SULU", "Sulu (ADM2)", s))
        notes.append(f"Sulu ({s.area / 1e6:.0f} km2) " + ("made a separate unit" if sulu == "separate" else "left out"))
    else:
        notes.append("Sulu kept in BARMM (as in most years of the BARMM corn series)")
    notes.append("NCR dropped (no corn series)")

    out = gpd.GeoDataFrame(pd.DataFrame(rows, columns=["region", "code", "source_name", "geometry"]),
                           geometry="geometry", crs=EQUAL_AREA)
    out["geometry"] = out.geometry.make_valid()
    out["area_km2"] = (out.geometry.area / 1e6).round(1)
    overlap = sum(out.geometry.area) - out.geometry.union_all().area
    notes.append(f"{len(out)} units, total {out.area_km2.sum():,.0f} km2, overlap between units {overlap / 1e6:.2f} km2")
    return out.sort_values("region").reset_index(drop=True).to_crs(4326), notes


def grid_coverage(regions: gpd.GeoDataFrame, res: float = ERA5_RES) -> pd.Series:
    """Number of ERA5 grid-cell centres inside each region (regions in lon/lat).

    ERA5 grid points sit on multiples of `res` degrees. Because the polygons are
    land only, a centre inside a region is a cell whose centre is on that region's land."""
    minx, miny, maxx, maxy = regions.total_bounds
    lons = np.arange(np.floor(minx / res) * res, maxx + res, res)
    lats = np.arange(np.floor(miny / res) * res, maxy + res, res)
    lon, lat = np.meshgrid(lons, lats)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon.ravel(), lat.ravel()), crs=4326)
    joined = gpd.sjoin(pts, regions[["code", "geometry"]], predicate="within", how="inner")
    return joined.groupby("code").size().reindex(regions["code"], fill_value=0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--adm1", type=Path, help="local geoBoundaries PHL ADM1 file (default: download)")
    p.add_argument("--adm2", type=Path, help="local geoBoundaries PHL ADM2 file (default: download)")
    p.add_argument("--cache", type=Path, default=Path("data/boundaries/source"))
    p.add_argument("--out", type=Path, default=Path("data/boundaries/phl_16_regions.gpkg"))
    p.add_argument("--sulu", choices=("barmm", "separate", "exclude"), default="barmm")
    p.add_argument("--grid-res", type=float, default=ERA5_RES,
                   help=f"ERA5 grid spacing in degrees for the grid-cell check (default {ERA5_RES}; 0 skips it)")
    args = p.parse_args(argv)

    paths = {"ADM1": args.adm1 or fetch("ADM1", args.cache), "ADM2": args.adm2 or fetch("ADM2", args.cache)}
    sums = {k: sha256(v) for k, v in paths.items()}
    for k in paths:
        if sums[k] != EXPECTED_SHA256[k]:
            print(f"NOTE: {k} source differs from the version this script was checked against "
                  f"(geoBoundaries may have updated it); check the summary below.")
    adm1, adm2 = gpd.read_file(paths["ADM1"]), gpd.read_file(paths["ADM2"])
    regions, notes = build(adm1, adm2, args.sulu)

    cells = None
    if args.grid_res > 0:
        cells = grid_coverage(regions, args.grid_res)
        few = [c for c, n in cells.items() if n < MIN_CELLS]
        notes.append(f"ERA5 grid ({args.grid_res} deg) cell centres per region: min {cells.min()}, "
                     f"median {int(cells.median())}, max {cells.max()}")
        if few:
            notes.append(f"WARNING: fewer than {MIN_CELLS} grid-cell centres in {', '.join(few)}; "
                         "regional means there rest on very few cells")
        regions = regions.merge(cells.rename("era5_cells"), left_on="code", right_index=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    regions.to_file(args.out, driver="GPKG", layer="regions")
    meta = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": {k: {"file": str(paths[k]), "url": URLS[k], "sha256": sums[k]} for k in paths},
            "license": "geoBoundaries gbOpen PHL: CC BY 3.0 IGO (NAMRIA, PSA, OCHA Philippines)",
            "sulu": args.sulu, "grid_res_deg": args.grid_res,
            "era5_cells_per_region": None if cells is None else {k: int(v) for k, v in cells.items()},
            "notes": notes}
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print("\n".join(notes))
    cols = ["code", "region", "area_km2"] + (["era5_cells"] if cells is not None else [])
    print(regions[cols].to_string(index=False))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())