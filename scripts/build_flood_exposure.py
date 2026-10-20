"""Flood control for the rice model: flood occurrence by region x quarter, 1987-2025, with
the previous quarter as an extra column. Source: EM-DAT (data/hazards/emdat/, downloaded
by hand from public.emdat.be; licence does not allow redistribution, so gitignored).

Region measures (province -> region with the same production weights as the typhoon
control, hazards.weights):
- flood_share: share of the region's rice production in provinces hit by >= 1 flood event
  that quarter (0-1);
- flood_any: 1 if any province of the region was hit;
- n_flood_events: number of distinct events touching the region.

Run:  python scripts/build_flood_exposure.py
Writes data/processed/flood_events.csv, flood_region_quarter.csv,
outputs/tables/flood_unplaced_events.csv, outputs/figures/flood_exposure_by_region.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from agriculture.regions import REGIONS  # noqa: E402
from hazards.floods import load_events, province_quarter  # noqa: E402
from hazards.typhoon import load_provinces  # noqa: E402
from hazards.weights import province_weights  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
for d in (PROC, TAB, FIG):
    d.mkdir(parents=True, exist_ok=True)
START, END = pd.Period("1986Q4", "Q"), pd.Period("2025Q4", "Q")
MEASURES = ["flood_share", "flood_any", "n_flood_events"]


def main():
    ev = load_events()
    ev.assign(units=ev.units.str.join("; ")).to_csv(PROC / "flood_events.csv", index=False)
    ev[(ev.units.str.len() == 0) | (ev.unplaced != "")][
        ["DisNo", "start", "type", "subtype", "source", "location", "unplaced"]].to_csv(
        TAB / "flood_unplaced_events.csv", index=False)

    pq = province_quarter(ev)
    polys = set(load_provinces().polygon)
    unknown = sorted(set(pq.polygon) - polys)
    if unknown:
        raise KeyError(f"flood units without a polygon: {unknown}")

    # event ids per province-quarter, to count distinct events per region
    rows = [(u, q, e.DisNo) for _, e in ev.iterrows()
            for q in pd.period_range(e.start.asfreq("Q"), e.end.asfreq("Q"), freq="Q")
            for u in e.units]
    hits = pd.DataFrame(rows, columns=["polygon", "period", "DisNo"]).drop_duplicates()

    w = province_weights(polys)
    periods = pd.period_range(START, END, freq="Q")
    full = (w.merge(pd.DataFrame({"period": periods}), how="cross")
             .merge(pq, on=["polygon", "period"], how="left").fillna({"n_events": 0}))
    full["hit"] = (full.n_events > 0).astype(float)
    full["flood_share"] = full.hit * full.weight
    reg = full.groupby(["ecosystem", "region_code", "period"]).agg(
        flood_share=("flood_share", "sum"), flood_any=("hit", "max")).reset_index()
    ev_reg = (hits.merge(w[["ecosystem", "region_code", "polygon"]], on="polygon")
              .groupby(["ecosystem", "region_code", "period"]).DisNo.nunique()
              .rename("n_flood_events").reset_index())
    reg = reg.merge(ev_reg, how="left").fillna({"n_flood_events": 0})
    reg = reg.sort_values(["ecosystem", "region_code", "period"])
    for m in MEASURES:
        reg[f"{m}_lag1"] = reg.groupby(["ecosystem", "region_code"])[m].shift(1)
    reg = reg[reg.period >= pd.Period("1987Q1", "Q")]
    reg.insert(2, "region", reg.region_code.map(REGIONS))
    reg.to_csv(PROC / "flood_region_quarter.csv", index=False)

    tot = reg[reg.ecosystem == "total"]
    by_dec = (ev.assign(decade=(ev.start.dt.year // 10) * 10)
                .groupby(["decade", "type"]).size().unstack(fill_value=0))
    print(f"{len(ev)} events ({(ev.units.str.len() > 0).sum()} placed); "
          f"region-quarters with a flood: {(tot.flood_any > 0).mean():.1%}")
    print("events by decade and type:\n", by_dec)

    a = (tot.assign(year=tot.period.dt.year)
         .pivot_table(index="region_code", columns="year", values="flood_any", aggfunc="sum")
         .reindex(list(REGIONS)))
    ramp = LinearSegmentedColormap.from_list(
        "blue", ["#f4f8fd", "#b7d3f6", "#6da7ec", "#2a78d6", "#184f95"])
    fig, ax = plt.subplots(figsize=(13, 6), constrained_layout=True)
    im = ax.imshow(a.values, cmap=ramp, aspect="auto", vmin=0, vmax=4)
    ax.set_yticks(range(len(a)), a.index, fontsize=8)
    ax.set_xticks(range(0, a.shape[1], 2), a.columns[::2], fontsize=7, rotation=90)
    ax.tick_params(length=0, colors="#52514e")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.8, ticks=range(5))
    cb.set_label("quarters with a flood event (0–4)", fontsize=8, color="#52514e")
    cb.outline.set_visible(False)
    ax.set_title("Flood occurrence by region, 1987–2025 (EM-DAT floods and storm-related "
                 "floods; coastal flooding excluded)", fontsize=10, color="#0b0b0b", loc="left")
    fig.savefig(FIG / "flood_exposure_by_region.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
