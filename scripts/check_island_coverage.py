"""Provinces with no ERA5 land cell (from build_weather_monthly.py): their share of their
region's production in 2021-2023, to decide how to treat them in the regional weather.
Nothing is changed in the data.

Palay and corn: share of tonnes. VR and PF: share of calorie energy (as in the indices).
Region totals are the 16 rebuilt regions (sum of their provinces).

Run after build_weather_monthly.py:  python scripts/check_island_coverage.py
Writes outputs/tables/weather_uncovered_province_shares.csv
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from agriculture.calories import factors  # noqa: E402
from agriculture.psa_openstat import read_palay_corn, read_vr_pf  # noqa: E402
from agriculture.regions import REGION_OF_PROVINCE, assign_region  # noqa: E402

TAB = ROOT / "outputs/tables"
YEARS = (2021, 2023)
# boundary-file (geoBoundaries ADM2) name -> PSA province name; None = no PSA row
ADM2_TO_PSA = {"Tawi-Tawi": "Tawi-tawi", "City of Isabela": None, "Cotabato City": None}
NO_ROW = {"City of Isabela": ("R09", "no PSA row; Region IX, on Basilan island"),
          "Cotabato City": ("BARMM", "no PSA row")}


def province_values():
    pc = read_palay_corn()
    pc = pc[pc.crop.isin(["Palay", "Corn"]) & (pc.level == "province")]
    pc = pc.assign(series=pc.crop.str.lower(), value=pc.production_t)
    f = factors()
    vp = read_vr_pf({g: list(f.index[f.group == g]) for g in ("VR", "PF")})
    vp = vp[vp.level == "province"].merge(f[["kcal_per_kg"]], left_on="crop", right_index=True)
    vp = vp.assign(series=vp.group.str.lower(), value=vp.production_t * vp.kcal_per_kg * 1e-6)
    d = pd.concat([pc, vp])
    d = d[d.period.dt.year.between(*YEARS)]
    d["region_code"] = assign_region(d.geo)
    return d.groupby(["series", "region_code", "geo"])["value"].sum().reset_index()


def main():
    uncovered = pd.read_csv(TAB / "weather_provinces_without_cells.csv").province
    v = province_values()
    reg = v.groupby(["series", "region_code"])["value"].sum()
    rows = []
    for adm2 in uncovered:
        psa = ADM2_TO_PSA.get(adm2, adm2)
        code, note = NO_ROW.get(adm2, (REGION_OF_PROVINCE.get(psa, ""), ""))
        row = {"province": adm2, "region_code": code, "note": note}
        for s in ("palay", "corn", "vr", "pf"):
            x = v[(v.series == s) & (v.geo == psa)]
            row[f"{s}_share_pct"] = (x.value.sum() / reg[(s, row["region_code"])] * 100
                                     if psa and len(x) else None)
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["region_code", "province"])
    out.round(2).to_csv(TAB / "weather_uncovered_province_shares.csv", index=False)
    pd.set_option("display.width", 200)
    print(f"share of the region's production, {YEARS[0]}-{YEARS[1]} (%; VR/PF in kcal):")
    print(out.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
