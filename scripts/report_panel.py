"""Write outputs/panel_validation.md from the tables of the panel scripts.

Run after build_crop_panel.py, build_weather_monthly.py and build_geophysical_controls.py:
    python scripts/report_panel.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TAB, PROC = ROOT / "outputs/tables", ROOT / "data/processed"
OUT = ROOT / "outputs/panel_validation.md"


def md(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    """Markdown table without extra dependencies."""
    def cell(v):
        if isinstance(v, float):
            return "" if pd.isna(v) else floatfmt.format(v)
        return str(v)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = ["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep] + rows)


def main():
    t = {f.stem.removeprefix("panel_").removeprefix("geophysical_"): pd.read_csv(f)
         for f in TAB.glob("panel_*.csv")}
    quakes = pd.read_csv(TAB / "geophysical_earthquakes.csv")
    erupt = pd.read_csv(TAB / "geophysical_eruptions.csv")
    cells = pd.read_csv(TAB / "weather_cells_per_region.csv")
    weather = pd.read_csv(PROC / "weather_region_month.csv", usecols=["region_code", "month"])
    s = []
    w = s.append

    w("# Region x quarter panel: validation report\n")
    w("Built by `scripts/build_crop_panel.py`, `scripts/build_weather_monthly.py`, "
      "`scripts/build_geophysical_controls.py`; this report by `scripts/report_panel.py`. "
      "Rules follow methodology v5 (16 regions, pre-2024 structure). No model is estimated.\n")

    w("## 1. Regions and coverage\n")
    cov = t["coverage"]
    w(f"Every series has **{cov.n_regions.min()} regions** " if cov.n_regions.nunique() == 1 else f"Regions per series: {cov.n_regions.min()}–{cov.n_regions.max()} "
      "(NIR provinces back in VI and VII, Sulu in BARMM, no NCR). Palay and corn run "
      f"{cov[cov.group.isin(['palay', 'corn'])]['first'].min()}–"
      f"{cov[cov.group.isin(['palay', 'corn'])]['last'].max()}, VR and PF "
      f"{cov[cov.group.isin(['vr', 'pf'])]['first'].min()}–"
      f"{cov[cov.group.isin(['vr', 'pf'])]['last'].max()}; 2026 quarters are flagged "
      "`provisional`.\n")
    w(md(cov))
    w("")

    w("## 2. Missing values\n")
    w("Region-quarters where every province of the region is '..' (within the crop's span). "
      "All other region-quarters have data. These are regions that do not grow the crop "
      "(e.g. Cavendish banana in Luzon); in the calorie indices they count as zero.\n")
    w(md(t["missing"]) if len(t["missing"]) else "None.")
    w("")

    w("## 3. National totals\n")
    nat = t["vs_national"]
    w("Sum of the 16 rebuilt regions against the PHILIPPINES row of the PSA tables, every "
      f"quarter. Largest relative gap: {nat.max_rel_gap_production_t.max():.1e} (rounding of "
      "the published figures), so the regions add up to the national total, including the "
      "Eight Cluster Areas (section 4).\n")
    w(md(nat, "{:.1e}"))
    w("")

    w("## 4. BARMM and the Eight Cluster Areas\n")
    w("From 2023Q1 PSA's BARMM total includes the Eight Cluster Areas (63 barangays of the "
      "Province of Cotabato, Region XII until 2022), which are in no province row. Their "
      "output, BARMM total minus the BARMM provinces, is added to Region XII from 2023Q1, so "
      "both regions keep their pre-2023 boundaries. Before 2023 the residual is "
      f"{'zero for every crop' if len(t['barmm_residual_pre2023']) == 0 else 'non-zero in some quarters (see table)'}."
      " Residual by crop and year (t, and % of the BARMM provinces; 2026 = Q1–Q2):\n")
    r = pd.read_csv(TAB / "panel_barmm_residual_by_year.csv", header=[0, 1], index_col=0)
    r.columns = [f"{'t' if a == 'residual_t' else '%'} {b}" for a, b in r.columns]
    r = r[r.filter(like="t ").abs().max(axis=1) >= 0.5].reset_index()
    w(md(r))
    w("\nThe residual is mainly palay and corn (the cluster areas are lowland farmland). "
      "Maguindanao del Norte and del Sur are parts of the Maguindanao row in the VR table "
      "from 2025 and are dropped there to avoid counting them twice (in the fruit table the "
      "Maguindanao row is empty from 2025 and the two halves are used).\n")

    w("## 5. Negros Island Region: VI and VII across 2023–2024\n")
    w("Annual production (palay and corn in t, VR and PF in billion kcal) of VI and VII as "
      "rebuilt, of the provinces PSA moved to NIR, and of the country. The Negros provinces "
      "are present in every year, so adding them back leaves no gap. The 2024 falls in VI "
      "and VII come from their own provinces (VI palay: Iloilo -22%) in the 2024 El Niño "
      "year. One series to ask PSA about: Negros Occidental corn halves in 2024 "
      "(-49%) and falls again in 2025, the year it starts being reported under NIR.\n")
    w(md(t["vi_vii_break"], "{:,.1f}"))
    w("")

    w("## 6. Banana varieties\n")
    w("The six varieties add up to the 'Banana' row in every published row and quarter:\n")
    w(md(t["banana_varieties_check"], "{:.2g}"))
    w("")

    w("## 7. Calorie indices compared with Alper's workbook\n")
    a = t["vs_alper"]
    piv = a.pivot_table(index=["unit", "series"], columns="window",
                        values="max_abs_index_diff_pts").reset_index()
    same = sorted(set(a.unit) - set(piv[(piv[["2010-2022", "2023-2025", "2026"]] > 0.05)
                                        .any(axis=1)].unit))
    w("Sheet 'Quarterly indices' of FNRI_calorie_factors_VR_PF_v35.xlsx (A. Aras, built "
      "from PSA's regional table). Alper combines VI + VII + NIR into one unit, compared "
      "with our R06 + R07. His sheet has no 'PF without Cavendish' (our extra check) and "
      "runs to 2026Q3, one quarter beyond our files. kcal per kg is recomputed from the "
      "factor file and matches its own column.\n")
    w(f"**Identical** (largest index difference < 0.05 points): {', '.join(same)}.\n")
    w("**Different, as expected from the boundary rules**: BARMM and XII from 2023 (Eight "
      "Cluster Areas moved from BARMM to XII here, in BARMM in Alper's regional table), and "
      "IX and BARMM in 2026 (Sulu kept in BARMM here, under IX in PSA's 2026 table). "
      "Largest absolute index difference (points), by window:\n")
    diff = piv[~piv.unit.isin(same)]
    w(md(diff, "{:.3f}"))
    w("")

    w("## 8. Weather (ERA5 monthly)\n")
    w(f"`weather_region_month.csv`: {weather.region_code.nunique()} regions x "
      f"{weather.month.nunique()} months ({weather.month.min()} to {weather.month.max()}). "
      f"{cells.cells.sum()} ERA5 cells with land fraction > 0.5; "
      f"{cells.nearest.sum()} of them have their centre just outside the simplified "
      f"coastline and go to the nearest region (at most {cells.max_distance_km.max():.0f} km). "
      "See `outputs/figures/era5_land_sea_mask.png`.\n")
    w(md(cells, "{:.1f}"))
    noc = pd.read_csv(TAB / "weather_provinces_without_cells.csv").province
    w("\nCaveats:\n"
      "- Provinces with no ERA5 cell (land fraction > 0.5) at 0.25°, so not represented in "
      f"their region's weather: {', '.join(noc)}. BARMM's weather comes from mainland "
      "Mindanao (Lanao del Sur, Maguindanao) only.\n"
      "- Cells are weighted by area; v5 Eq. 7 weights by cropland area, whose source "
      "(ESA WorldCover or CCI) is to be confirmed.\n"
      "- RH and VPD are computed from the monthly means of t2m and d2m (v5 Table 2). Because "
      "saturation vapour pressure is convex, this slightly understates the monthly mean of "
      "daily VPD; the hourly-based variables of Table 2 will correct this.\n"
      "- ERA5 potential evaporation is known to be unreliable over land; for the climatic "
      "water balance an FAO-56 estimate from t2m, d2m and ssrd is preferable.\n")

    w("## 9. Earthquakes\n")
    k = quakes[quakes.kept]
    drop = quakes[~quakes.kept].reason_dropped.value_counts()
    w(f"USGS ComCat, M >= 6.5, 1987–2025: {len(quakes)} events; {len(k)} kept, dropped "
      + ", ".join(f"{v} {i}" for i, v in drop.items())
      + ". Kept events are assigned to the nearest region (distance 0 = epicentre on land); "
      "time in Philippine Time. Markers: `eq` (event quarter), `eq_next` (event quarter "
      "and the next).\n")
    k = k.assign(date=k.time_pht.str[:10])[["date", "period", "mag", "depth",
                                             "dist_land_km", "region_code", "place"]]
    w(md(k, "{:.1f}"))
    w("")

    w("## 10. Volcanic eruptions\n")
    w("GVP eruption list joined to the volcano list; Philippines, VEI >= 3, start year >= "
      f"1987: **{len(erupt)} eruptions**. Region = the volcano's own region; Kanlaon to VI "
      "(check version `eruption_kanlaon_vi_vii` gives it to VI and VII). Pinatubo 1991 has "
      "its own marker `pinatubo_1991`. Kanlaon October 2024 is VEI 2 in this file (VEI 3 in "
      "the current GVP database), so it is not included.\n")
    w(md(erupt[["Volcano Name", "VEI", "start", "end", "first_quarter", "last_quarter",
                "region_of_coordinates", "region_code", "region_code_check"]], "{:.0f}"))
    w("")

    w("## 11. Changes to earlier outputs\n")
    w("The rice panel (`rice_region_quarter.csv`), the typhoon and flood controls and "
      "`province_region_map.csv` were rebuilt on the same 16 regions (codes as in Van's "
      "boundary file: R01–R13, R04A, CAR, MIMAROPA, BARMM). `rice_barmm_unallocated.csv` is "
      "replaced by `barmm_cluster_residual.csv` (all crops). The first rice estimation "
      "(`outputs/tables/rice_direct_*`) still uses the old 17 regions and has to be re-run.\n")

    OUT.write_text("\n".join(s))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
