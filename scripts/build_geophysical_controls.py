"""Earthquake and eruption markers by region x quarter, 1987Q1-2026Q2 (see
src/hazards/geophysical.py for the rules).

Run:  python scripts/build_geophysical_controls.py
Writes
- data/processed/geophysical_region_quarter.csv   eq, eq_next, eruption,
  eruption_kanlaon_vi_vii, pinatubo_1991 by region x quarter
- outputs/tables/geophysical_earthquakes.csv       every USGS event, kept or dropped, with region
- outputs/tables/geophysical_eruptions.csv         the eruptions used, with region and quarters
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from agriculture.regions import REGIONS  # noqa: E402
from hazards.geophysical import earthquakes, eruptions, region_quarter  # noqa: E402

PROC, TAB = ROOT / "data/processed", ROOT / "outputs/tables"
PERIODS = pd.period_range("1987Q1", "2026Q2", freq="Q")


def main():
    q = earthquakes()
    e = eruptions()
    q.round(3).to_csv(TAB / "geophysical_earthquakes.csv", index=False)
    e.to_csv(TAB / "geophysical_eruptions.csv", index=False)
    rq = region_quarter(q, e, list(REGIONS), PERIODS)
    rq.to_csv(PROC / "geophysical_region_quarter.csv", index=False)

    pd.set_option("display.width", 220, "display.max_rows", 100)
    print(f"earthquakes: {len(q)} events, {q.kept.sum()} kept; dropped: "
          f"{q[~q.kept].reason_dropped.value_counts().to_dict()}")
    print(q[q.kept][["time_pht", "mag", "depth", "dist_land_km", "region_code", "place"]]
          .round(1).to_string(index=False))
    print(f"\neruptions: {len(e)}")
    print(e.to_string(index=False))
    print("\nregion-quarters flagged:", rq.drop(columns=["region_code", "period"]).sum().to_dict())


if __name__ == "__main__":
    main()
