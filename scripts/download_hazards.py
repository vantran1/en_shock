"""Download raw inputs for the typhoon control into data/hazards/ (never modified after).

- IBTrACS v04r01, Western Pacific basin, CSV (NOAA NCEI). About 115 MB, so it is
  gitignored; re-run this script to get it.
- Province boundaries: geoBoundaries gbOpen PHL ADM2 (2020 boundaries; source NAMRIA, PSA,
  OCHA; CC BY 3.0 IGO), simplified GeoJSON.

Run:  python scripts/download_hazards.py   (skips files that already exist)
"""
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "hazards"
FILES = {
    "ibtracs/ibtracs.WP.list.v04r01.csv":
        "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-"
        "stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv",
    "boundaries/geoBoundaries-PHL-ADM2_simplified.geojson":
        "https://github.com/wmgeolab/geoBoundaries/raw/41af8f1/releaseData/gbOpen/PHL/ADM2/"
        "geoBoundaries-PHL-ADM2_simplified.geojson",
}


def main():
    log = []
    for rel, url in FILES.items():
        dest = OUT / rel
        if dest.exists():
            print(f"exists: {rel}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {rel} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
            f.write(r.read())
        log.append(f"{date.today()}  {rel}  <-  {url}")
    if log:
        with open(OUT / "DOWNLOADS.txt", "a") as f:
            f.write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
