"""Typhoon control for the rice model: wind exposure by region x quarter, 1987-2025,
with the previous quarter as an extra column (a storm can hit a crop harvested later).

Province exposure (src/hazards/typhoon.py) is averaged to the 17 fixed regions with
weights = each province's share of the region's palay production, averaged over
2016-2025 (fixed over time, so the control does not move with production itself).
Separate weights for irrigated, rainfed and total palay.

Run:  python scripts/download_hazards.py   (once)
      python scripts/build_typhoon_exposure.py
Writes data/processed/typhoon_storm_province.csv, typhoon_region_quarter.csv,
outputs/tables/typhoon_top_events.csv, outputs/figures/typhoon_exposure_by_region.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from agriculture.regions import REGIONS  # noqa: E402
from hazards.typhoon import (grid_points, load_provinces, load_tracks,  # noqa: E402
                             province_quarter, storm_province_exposure)
from hazards.weights import province_weights  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
for d in (PROC, TAB, FIG):
    d.mkdir(parents=True, exist_ok=True)
START, END = pd.Period("1986Q4", "Q"), pd.Period("2025Q4", "Q")
MEASURES = ["damage_index", "max_wind_ms", "n_storms_100km"]


def main():
    prov = load_provinces()
    pts = grid_points(prov)
    tracks = load_tracks()
    print(f"{len(pts)} grid points in {prov.polygon.nunique()} provinces; "
          f"{tracks.SID.nunique()} storms near the Philippines since 1986")

    sp = storm_province_exposure(tracks, pts)
    sp.to_csv(PROC / "typhoon_storm_province.csv", index=False)
    pq = province_quarter(sp)

    w = province_weights(set(prov.polygon))
    periods = pd.period_range(START, END, freq="Q")
    full = (w.merge(pd.DataFrame({"period": periods}), how="cross")
             .merge(pq, on=["polygon", "period"], how="left").fillna({m: 0 for m in MEASURES}))
    for m in MEASURES:
        full[m] = full[m] * full.weight
    reg = full.groupby(["ecosystem", "region_code", "period"])[MEASURES].sum().reset_index()
    reg = reg.sort_values(["ecosystem", "region_code", "period"])
    for m in MEASURES:
        reg[f"{m}_lag1"] = reg.groupby(["ecosystem", "region_code"])[m].shift(1)
    reg = reg[reg.period >= pd.Period("1987Q1", "Q")]
    reg.insert(2, "region", reg.region_code.map(REGIONS))
    reg.to_csv(PROC / "typhoon_region_quarter.csv", index=False)

    # validation: strongest region-quarters and the storms behind them
    tot = reg[reg.ecosystem == "total"].nlargest(25, "damage_index")
    sp_r = sp.merge(w[w.ecosystem == "total"], on="polygon")
    sp_r["contrib"] = sp_r.damage_index * sp_r.weight
    top_storm = (sp_r.sort_values("contrib").groupby(["region_code", "period"]).tail(1)
                 [["region_code", "period", "storm", "SID"]])
    top = tot.merge(top_storm, on=["region_code", "period"], how="left")[
        ["region_code", "period", "storm", "SID", "damage_index", "max_wind_ms", "n_storms_100km"]]
    top.round(3).to_csv(TAB / "typhoon_top_events.csv", index=False)
    pd.set_option("display.width", 200)
    print(top.round(3).to_string(index=False))

    # figure: annual exposure (sum of quarterly damage index, total-palay weights)
    a = (reg[reg.ecosystem == "total"].assign(year=lambda d: d.period.dt.year)
         .pivot_table(index="region_code", columns="year", values="damage_index", aggfunc="sum")
         .reindex(list(REGIONS)))
    ramp = LinearSegmentedColormap.from_list(
        "blue", ["#f4f8fd", "#b7d3f6", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
    fig, ax = plt.subplots(figsize=(13, 6), constrained_layout=True)
    im = ax.imshow(a.values, cmap=ramp, aspect="auto", vmin=0, vmax=np.nanpercentile(a.values, 99))
    ax.set_yticks(range(len(a)), a.index, fontsize=8)
    ax.set_xticks(range(0, a.shape[1], 2), a.columns[::2], fontsize=7, rotation=90)
    ax.tick_params(length=0, colors="#52514e")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label("typhoon damage index (sum of quarters)", fontsize=8, color="#52514e")
    cb.outline.set_visible(False)
    ax.set_title("Typhoon wind exposure of rice areas by region, 1987–2025 "
                 "(IBTrACS, Rankine wind field, Emanuel damage function)",
                 fontsize=10, color="#0b0b0b", loc="left")
    fig.savefig(FIG / "typhoon_exposure_by_region.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
