"""Region x quarter crop panel for the direct models (palay, corn, VR, PF). No estimation.

Sources (data/agriculture/, PSA OpenSTAT, read by agriculture.psa_openstat):
- palay and corn: production (t) and area harvested (ha) by ecosystem / corn type,
  province x quarter, 1987Q1-2026Q2;
- VR and PF: production (t) of the 13 crops of methodology v5 (bananas by variety),
  province x quarter, 2010Q1-2026Q2;
- calorie factors: fnri_calorie_factors.csv; Alper's workbook
  FNRI_calorie_factors_VR_PF_v35.xlsx (local, gitignored) for the comparison only.

Every series is rebuilt from provinces on the 16 regions of v5 (agriculture.regions,
agriculture.rebuild): NIR provinces back in VI and VII, Sulu in BARMM, the Eight Cluster
Areas in XII from 2023. Only Quarter1-4 are used (semesters and years are sums); 2026
quarters with data are kept and flagged provisional.

Run:  python scripts/build_crop_panel.py
Writes
- data/processed/crop_region_quarter.csv     long panel: series x region x quarter x variable
  columns group, series, region_code, period, variable (production_t: t; area_ha: ha;
  energy_bkcal: billion kcal; index: 2021-2023 = 100), value, provisional (2026)
- data/processed/barmm_cluster_residual.csv  Eight Cluster Areas by crop and quarter
- outputs/tables/panel_*.csv                 validation tables (report: scripts/report_panel.py)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agriculture.calories import energy, factors, indices  # noqa: E402
from agriculture.psa_openstat import read_palay_corn, read_vr_pf  # noqa: E402
from agriculture.rebuild import rebuild  # noqa: E402
from agriculture.regions import REGIONS, assign_region, code_of_published  # noqa: E402

PROC, TAB = ROOT / "data/processed", ROOT / "outputs/tables"
ALPER = ROOT / "data/agriculture/FNRI_calorie_factors_VR_PF_v35.xlsx"
PALAY_CORN = {"Irrigated Palay": "palay_irrigated", "Rainfed Palay": "palay_rainfed",
              "Palay": "palay", "White Corn": "corn_white", "Yellow Corn": "corn_yellow",
              "Corn": "corn"}
BANANAS = ["Banana Cavendish", "Banana Lakatan", "Banana Latundan", "Banana Bungulan",
           "Banana Others", "Banana Saba"]
UNITS = {"production_t": "t", "area_ha": "ha", "energy_bkcal": "billion kcal",
         "index": "2021-2023 = 100"}
VI_VII = "R06+R07"  # Alper combines VI + VII + NIR, i.e. our R06 + R07


def last_quarter_with_data(df, value):
    nat = df[df["level"] == "national"].groupby("period")[value].apply(lambda s: s.notna().any())
    return nat[nat].index.max()


def series_name(crop):
    return PALAY_CORN.get(crop) or crop.lower().replace(" [", "_").replace("]", "") \
        .replace(", ", "_").replace(" ", "_")


def national_check(df, panel, values, label):
    """Sum of the 16 rebuilt regions vs the PHILIPPINES row, per crop."""
    nat = df[df["level"] == "national"].set_index(["crop", "period"])[values]
    tot = panel.groupby(["crop", "period"])[values].sum(min_count=1)
    rel = (tot / nat - 1).abs()
    out = rel.groupby("crop").max().add_prefix("max_rel_gap_")
    out["quarters_gap_over_1e-6"] = (rel[values[0]] > 1e-6).groupby("crop").sum()
    return out.reset_index().assign(source=label)


def missing_table(panel, value):
    """Quarters with no data, per crop and region, within the crop's national data span."""
    span = panel.groupby("crop")["period"].agg(["min", "max"])
    p = panel.merge(span, left_on="crop", right_index=True)
    p = p[p["period"].between(p["min"], p["max"])]
    m = p.assign(missing=p[value].isna()).groupby(["crop", "region_code"])["missing"].sum()
    return m[m > 0].rename("quarters_missing").reset_index()


def banana_check(df):
    """Six varieties vs the 'Banana' row, for every published row (national, regions,
    provinces), quarter by quarter."""
    key = ["level", "region_published", "geo", "period"]
    v = df[df["crop"].isin(BANANAS)].groupby(key, dropna=False)["production_t"].sum(min_count=1)
    b = df[df["crop"] == "Banana"].set_index(key)["production_t"]
    gap = (v - b.reindex(v.index)).dropna()
    rel = (gap / b.reindex(gap.index)).abs()
    summ = pd.DataFrame({"rows_compared": gap.groupby("level").size(),
                         "max_abs_gap_t": gap.abs().groupby("level").max(),
                         "rows_gap_over_1t": (gap.abs() > 1).groupby("level").sum(),
                         "max_rel_gap": rel.replace(np.inf, np.nan).groupby("level").max()})
    worst = gap[gap.abs() > 1].rename("gap_t").reset_index()
    return summ.reset_index(), worst


def alper_compare(ours):
    """Our energies and indices vs Alper's 'Quarterly indices' sheet."""
    a = pd.read_excel(ALPER, sheet_name="Quarterly indices", header=4).iloc[:, :12]
    a = a[pd.to_numeric(a["Year"], errors="coerce").notna()].copy()
    lab = a["Region"].str.strip()
    a["unit"] = np.select([lab == "PHILIPPINES", lab.str.contains(r"VI \+ VII \+ NIR")],
                          ["PH", VI_VII], "")
    rest = a["unit"] == ""
    a.loc[rest, "unit"] = code_of_published(lab[rest]).values
    a["period"] = pd.PeriodIndex.from_fields(year=a["Year"].astype(int),
                                             quarter=a["Quarter"].astype(int), freq="Q")
    cols = {"vr": ("VR energy (billion kcal)", "VR index"),
            "pf": ("PF energy (billion kcal)", "PF index"),
            "vr_noroot": ("VR without root crops energy (billion kcal)", "VR index without root crops"),
            "pf_nobanana": ("PF without banana energy (billion kcal)", "PF index without banana")}
    long = []
    for s, (ce, ci) in cols.items():
        long.append(a[["unit", "period"]].assign(series=s, energy_alper=a[ce].astype(float),
                                                 index_alper=a[ci].astype(float)))
    a = pd.concat(long)
    m = ours.merge(a, on=["unit", "series", "period"], how="inner")
    m["energy_rel_diff"] = (m["energy_bkcal"] / m["energy_alper"] - 1)
    m["index_diff_pts"] = m["index"] - m["index_alper"]
    m["window"] = np.select([m.period.dt.year <= 2022, m.period.dt.year <= 2025],
                            ["2010-2022", "2023-2025"], "2026")
    summ = (m.groupby(["unit", "series", "window"])
            .agg(quarters=("period", "size"),
                 max_abs_energy_rel_diff=("energy_rel_diff", lambda s: s.abs().max()),
                 max_abs_index_diff_pts=("index_diff_pts", lambda s: s.abs().max()))
            .reset_index())
    expected = {"BARMM": "Eight Cluster Areas moved to XII from 2023; Sulu kept in BARMM in 2026",
                "R12": "Eight Cluster Areas added from 2023",
                "R09": "Sulu kept in BARMM in 2026 (PSA lists it under IX)"}
    summ["expected_difference"] = summ["unit"].map(expected).fillna("")
    last = a["period"].max()
    return summ, m, last


def vi_vii_break(pc, vp, f):
    """Annual production 2021-2025 of VI and VII as rebuilt, of the Negros provinces that
    PSA moved to NIR in 2024, and of the country; % change 2023 -> 2024. Palay and corn in
    t, VR and PF in billion kcal. A break from the NIR fold-back would show up as VI or VII
    moving very differently from the country while the Negros provinces stay put."""
    negros = {"Negros Occidental": "Negros Occidental", "Bacolod City": "Negros Occidental",
              "City of Bacolod": "Negros Occidental", "Negros Oriental": "Negros Or. + Siquijor",
              "Siquijor": "Negros Or. + Siquijor"}
    pcs = pc[pc["crop"].isin(["Palay", "Corn"])].assign(series=lambda d: d.crop.str.lower(),
                                                        value=lambda d: d.production_t)
    vps = vp.merge(f[["kcal_per_kg"]], left_on="crop", right_index=True)
    vps = vps.assign(series=vps["group"].str.lower(),
                     value=vps["production_t"] * vps["kcal_per_kg"] * 1e-6)
    d = pd.concat([pcs, vps])[["series", "level", "geo", "period", "value"]]
    d = d[d["period"].dt.year.between(2021, 2025)]
    prov = d[d["level"] == "province"].copy()
    prov["region_code"] = assign_region(prov["geo"])
    parts = [prov[prov.region_code.isin(["R06", "R07"])].assign(unit=lambda x: x.region_code),
             prov[prov.geo.isin(negros)].assign(unit=lambda x: x.geo.map(negros)),
             d[d["level"] == "national"].assign(unit="PHILIPPINES")]
    t = (pd.concat(parts).assign(year=lambda x: x.period.dt.year)
         .groupby(["series", "unit", "year"])["value"].sum(min_count=1).unstack("year"))
    t["pct_change_2023_2024"] = (t[2024] / t[2023] - 1) * 100
    return t.round(1)


def main():
    for d in (PROC, TAB):
        d.mkdir(parents=True, exist_ok=True)
    f = factors()

    # palay and corn: production and area
    pc = read_palay_corn()
    pc = pc[pc["crop"].isin(PALAY_CORN)]
    pc = pc[pc["period"] <= last_quarter_with_data(pc, "production_t")]
    pc_panel, pc_res = rebuild(pc, ["production_t", "area_ha"], ["crop"])

    # VR and PF: production of the factor-table commodities, plus 'Banana' for the check
    crops = {g: list(f.index[f["group"] == g]) for g in ("VR", "PF")}
    vp = read_vr_pf({"VR": crops["VR"], "PF": crops["PF"] + ["Banana"]})
    vp = vp[vp["period"] <= last_quarter_with_data(vp, "production_t")]
    ban_summ, ban_worst = banana_check(vp)
    vp = vp[vp["crop"] != "Banana"]
    vp_panel, vp_res = rebuild(vp, ["production_t"], ["crop"])

    # calorie energy and indices, by region, VI+VII combined, and national
    en = energy(vp_panel, f)
    by_region = indices(en.rename(columns={"region_code": "unit"}), f, ["unit"])
    en_vi = en[en["region_code"].isin(["R06", "R07"])].assign(unit=VI_VII)
    en_ph = en.assign(unit="PH")
    agg = lambda e: (e.groupby(["unit", "crop", "period"])["energy_bkcal"]  # noqa: E731
                     .sum(min_count=1).reset_index())
    extra = indices(pd.concat([agg(en_vi), agg(en_ph)]), f, ["unit"])
    idx_all = pd.concat([by_region, extra], ignore_index=True)

    # long panel
    pc_long = pc_panel.melt(id_vars=["crop", "region_code", "region", "period"],
                            value_vars=["production_t", "area_ha"], var_name="variable")
    pc_long["group"] = np.where(pc_long["crop"].str.contains("Palay"), "palay", "corn")
    vp_long = (vp_panel.merge(f[["group"]], left_on="crop", right_index=True)
               .melt(id_vars=["crop", "group", "region_code", "region", "period"],
                     value_vars=["production_t"], var_name="variable"))
    idx_long = (by_region.melt(id_vars=["unit", "series", "group", "period"],
                               value_vars=["energy_bkcal", "index"], var_name="variable")
                .rename(columns={"unit": "region_code"}))
    idx_long["region"] = idx_long["region_code"].map(REGIONS)
    out = pd.concat([pc_long.assign(series=pc_long["crop"].map(series_name)),
                     vp_long.assign(series=vp_long["crop"].map(series_name)),
                     idx_long], ignore_index=True)
    out["group"] = out["group"].str.lower()
    out["unit"] = out["variable"].map(UNITS)
    out["year"], out["quarter"] = out["period"].dt.year, out["period"].dt.quarter
    out["provisional"] = out["year"] >= 2026
    # compact columns (region labels: data/processed/province_region_map.csv; units: UNITS)
    out = out[["group", "series", "region_code", "period", "variable", "value", "provisional"]]
    out = out.sort_values(["group", "series", "variable", "region_code", "period"])
    out.to_csv(PROC / "crop_region_quarter.csv", index=False, float_format="%.6g")

    resid = pd.concat([pc_res, vp_res], ignore_index=True)
    resid["series"] = resid["crop"].map(series_name)
    resid.to_csv(PROC / "barmm_cluster_residual.csv", index=False, float_format="%.6g")

    # validation tables
    cov = (out[out.variable == "production_t"].dropna(subset=["value"])
           .groupby(["group", "series"])
           .agg(n_regions=("region_code", "nunique"), first=("period", "min"),
                last=("period", "max")).reset_index())
    cov.to_csv(TAB / "panel_coverage.csv", index=False)
    pd.concat([missing_table(pc_panel, "production_t"), missing_table(vp_panel, "production_t")]
              ).to_csv(TAB / "panel_missing.csv", index=False)
    pd.concat([national_check(pc, pc_panel, ["production_t", "area_ha"], "palay/corn"),
               national_check(vp, vp_panel, ["production_t"], "VR/PF")]
              ).to_csv(TAB / "panel_vs_national.csv", index=False)
    ann = resid[resid["applied"]].assign(year=lambda d: d.period.dt.year)
    res_y = ann.groupby(["series", "year"])["production_t"].sum().unstack("year")
    tot_b = (pd.concat([pc_panel, vp_panel]).query("region_code == 'BARMM'")
             .assign(series=lambda d: d.crop.map(series_name), year=lambda d: d.period.dt.year))
    tot_b = tot_b[tot_b.year >= 2023].groupby(["series", "year"])["production_t"].sum().unstack("year")
    res_tab = pd.concat({"residual_t": res_y, "residual_pct_of_barmm_provinces":
                         (res_y / tot_b * 100)}, axis=1).round(2)
    res_tab.to_csv(TAB / "panel_barmm_residual_by_year.csv")
    early = resid[~resid["applied"] & (resid["production_t"].abs() > 0.5)]
    early.to_csv(TAB / "panel_barmm_residual_pre2023.csv", index=False)
    ban_summ.to_csv(TAB / "panel_banana_varieties_check.csv", index=False)
    ban_worst.to_csv(TAB / "panel_banana_varieties_gaps.csv", index=False)
    summ, detail, last_alper = alper_compare(idx_all)
    summ.to_csv(TAB / "panel_vs_alper.csv", index=False)
    vi_vii_break(pc, vp, f).to_csv(TAB / "panel_vi_vii_break.csv")

    pd.set_option("display.width", 220, "display.max_rows", 200, "display.max_columns", 30)
    print(f"panel: {len(out)} rows, {out.region_code.nunique()} regions; "
          f"file {(PROC / 'crop_region_quarter.csv').stat().st_size / 1e6:.1f} MB")
    print(cov.to_string(index=False))
    print("\nbanana varieties vs Banana:\n", ban_summ.to_string(index=False))
    print("\nvs national:\n", pd.read_csv(TAB / "panel_vs_national.csv").to_string(index=False))
    print("\nBARMM residual before 2023 (not applied):", len(early), "rows")
    print("\nresidual by year (t):\n", res_y.round(0).to_string())
    print(f"\nvs Alper (his sheet ends {last_alper}):\n", summ.to_string(index=False))
    print("\nVI / VII break check:\n",
          pd.read_csv(TAB / "panel_vi_vii_break.csv").round(1).to_string(index=False))

if __name__ == "__main__":
    main()
