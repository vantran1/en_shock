#!/usr/bin/env python3
"""Download the inputs that are not in en_shock: run this on your laptop (it needs the internet and the CDS).

  python scripts/00_download_inputs.py --all            # everything below
  python scripts/00_download_inputs.py --c3s            # only the latest C3S forecast (each month)
  python scripts/00_download_inputs.py --cropland --cropland-year 2022

What is downloaded (into data/inputs/):
  --lsm         ERA5 land-sea mask (CDS reanalysis-era5-single-levels, one time step, Philippine box)
  --cropland    ESA CCI / C3S land cover, 300 m (CDS satellite-land-cover), requested for the Philippine box
                only (23-3 N, 115-129 E) with the CDS area option; the script keeps lccs_class (~30 MB).
  --population  WorldPop 2020, 1 km, UN-adjusted population counts for the Philippines (~1 MB)
  --c3s         C3S multi-system seasonal forecast of SST anomalies (CDS seasonal-postprocessed-single-levels),
                one file per system, over the 21S-21N band of all longitudes (not just the Philippines: RONI
                and DMI need Nino-3.4, the tropical mean and the Indian Ocean boxes). ECMWF is released on the 5th and the other systems on the 10th (12 UTC).

The CDS needs your key in ~/.cdsapirc (as for the ERA5 downloads) and, once, the licence of each dataset
accepted on its CDS page: "Land cover classification gridded maps" (satellite-land-cover) and "Seasonal
forecast ... post-processed" (seasonal-postprocessed-single-levels).
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import c3s  # noqa: E402
from stage1 import config as C  # noqa: E402

WORLDPOP_URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/PHL/"
                "phl_ppp_2020_1km_Aggregated_UNadj.tif")
BOX = [22, 116, 4, 127.5]                       # N, W, S, E: the en_shock ERA5 box
CROP = dict(lat=(23.0, 3.0), lon=(115.0, 129.0))
CROP_AREA = [CROP["lat"][0], CROP["lon"][0], CROP["lat"][1], CROP["lon"][1]]   # N, W, S, E for the CDS request


def lsm(cfg, force=False):
    target = C.path(cfg, "land_sea_mask")
    if target.exists() and not force:
        print(f"land-sea mask: {target} exists")
        return
    import cdsapi
    target.parent.mkdir(parents=True, exist_ok=True)
    print("land-sea mask: requesting from the CDS …", flush=True)
    cdsapi.Client().retrieve("reanalysis-era5-single-levels", {
        "product_type": ["reanalysis"], "variable": ["land_sea_mask"], "year": ["2020"], "month": ["01"],
        "day": ["01"], "time": ["00:00"], "area": BOX, "data_format": "netcdf", "download_format": "unarchived",
    }, str(target))
    print(f"land-sea mask: wrote {target}")


def _extract_nc(archive: pathlib.Path, folder: pathlib.Path) -> pathlib.Path:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            name = [n for n in z.namelist() if n.endswith(".nc")][0]
            z.extract(name, folder)
            return folder / name
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            m = [m for m in t.getmembers() if m.name.endswith(".nc")][0]
            t.extract(m, folder)
            return folder / m.name
    return archive


def cropland(cfg, year: int, force=False):
    target = C.path(cfg, "cropland")
    if year != 2022 and target.name == "esa_cci_lc_2022_phl.nc":
        target = target.with_name(f"esa_cci_lc_{year}_phl.nc")
        print(f"note: set paths.cropland in config.yaml to {target.relative_to(C.ROOT)} to use this year")
    if target.exists() and not force:
        print(f"cropland: {target} exists")
        return
    import cdsapi
    import xarray as xr
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(dir=target.parent))
    archive = tmp / f"satellite_land_cover_{year}.download"
    version = "v2_1_1" if year >= 2016 else "v2_0_7cds"
    print(f"cropland: requesting the {year} land-cover map ({version}) for the Philippine box {CROP_AREA} "
          f"(N, W, S, E) from the CDS …", flush=True)
    cdsapi.Client().retrieve("satellite-land-cover", {"variable": "all", "year": [str(year)], "version": [version],
                                                      "area": CROP_AREA}, str(archive))
    nc = _extract_nc(archive, tmp)
    # the CDS subset should already be the box; selecting again keeps only lccs_class and trims any edge pixels
    with xr.open_dataset(nc, mask_and_scale=False) as ds:
        desc = float(ds["lat"][0]) > float(ds["lat"][-1])
        lat = slice(*CROP["lat"]) if desc else slice(*CROP["lat"][::-1])
        da = ds["lccs_class"].sel(lat=lat, lon=slice(*CROP["lon"])).load()
    if da.size == 0:
        raise SystemExit(f"cropland: {nc.name} has no pixels in the Philippine box; the CDS subset failed")
    da.attrs.update(source=f"{nc.name} (CDS satellite-land-cover {version}, area {CROP_AREA})")
    da.to_dataset().to_netcdf(target, encoding={"lccs_class": {"zlib": True, "complevel": 4}})
    print(f"cropland: wrote {target} ({target.stat().st_size / 1e6:.0f} MB)")
    shutil.rmtree(tmp, ignore_errors=True)


def population(cfg, force=False):
    target = C.path(cfg, "population")
    if target.exists() and not force:
        print(f"population: {target} exists")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"population: downloading {WORLDPOP_URL} …", flush=True)
    req = urllib.request.Request(WORLDPOP_URL, headers={"User-Agent": "Mozilla/5.0 (UNDRR DEFINE-PH Stage-1)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(target, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"population: wrote {target} ({target.stat().st_size / 1e6:.1f} MB)")


def forecasts(cfg, start=None, force=False):
    y, m = c3s.parse_month(start or cfg["path"].get("forecast_start"), c3s.default_start())
    folder = C.path(cfg, "c3s_dir")
    folder.mkdir(parents=True, exist_ok=True)
    print(f"C3S forecast issued {y}-{m:02d}:")
    for s in cfg["path"]["systems"]:
        f = folder / c3s.file_name(s, y, m)
        if f.exists() and not force:
            print(f"  {s['label']}: {f.name} exists")
            continue
        try:
            print(f"  {s['label']}: requesting …", flush=True)
            c3s.download(s["centre"], s["system"], y, m, f)
            print(f"  {s['label']}: wrote {f.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {s['label']}: FAILED ({type(exc).__name__}: {str(exc)[:300]}); the path is built without it")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--lsm", action="store_true")
    ap.add_argument("--cropland", action="store_true")
    ap.add_argument("--cropland-year", type=int, default=2022)
    ap.add_argument("--population", action="store_true")
    ap.add_argument("--c3s", action="store_true")
    ap.add_argument("--c3s-start", help="forecast issue month YYYY-MM (default: this month from the 11th)")
    ap.add_argument("--force", action="store_true", help="download again even if the file exists")
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    if not any([a.all, a.lsm, a.cropland, a.population, a.c3s]):
        ap.print_help()
        return
    if a.all or a.lsm:
        lsm(cfg, a.force)
    if a.all or a.population:
        population(cfg, a.force)
    if a.all or a.c3s:
        forecasts(cfg, a.c3s_start, a.force)
    if a.all or a.cropland:
        cropland(cfg, a.cropland_year, a.force)


if __name__ == "__main__":
    main()
