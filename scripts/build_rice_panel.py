"""Rice data preparation (no estimation): regional quarterly irrigated and rainfed palay,
production and area, 1987Q1-2025Q4, rebuilt from PSA provincial data on fixed current
regional boundaries (Alper's reply: "the regional series should be rebuilt from
provincial data, using the same boundaries throughout").

Run:  python scripts/build_rice_panel.py

Writes
- data/processed/rice_region_quarter.csv     ecosystem x region x quarter panel
- data/processed/rice_barmm_unallocated.csv  BARMM Eight Cluster Areas (2023+, no province row)
- data/processed/province_region_map.csv     the fixed mapping
- outputs/tables/rice_*.csv                   boundary changes and data-quality checks
- outputs/figures/rice_log_production_by_region.png, rice_crop_calendar.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from agriculture.psa_openstat import read_palay_corn  # noqa: E402
from agriculture.regions import (BOUNDARY_CHANGES, CODE_OF_LABEL, REGIONS,  # noqa: E402
                                 assign_region, mapping_table)

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
for d in (PROC, TAB, FIG):
    d.mkdir(parents=True, exist_ok=True)

START, END = pd.Period("1987Q1", "Q"), pd.Period("2025Q4", "Q")
ECOSYSTEMS = {"Irrigated Palay": "irrigated", "Rainfed Palay": "rainfed", "Palay": "total"}
VALUES = ["production_t", "area_ha"]
EL_NINO = [(1997, 1998), (2015, 2016), (2023, 2024)]
BLUE, ORANGE = "#2a78d6", "#eb6834"  # validated categorical slots 1-2
INK, MUTED, BAND, GRID = "#0b0b0b", "#52514e", "#e6e5e1", "#d9d8d4"


def rebuild(prov):
    """Sum provinces into fixed regions. min_count=1: a region-quarter is missing only if
    all its provinces are; n_prov_reporting = provinces with data."""
    g = prov.groupby(["ecosystem", "region_code", "period"])
    out = g[VALUES].sum(min_count=1)
    out["n_prov_reporting"] = g["production_t"].count()
    out = out.reset_index()
    out.insert(2, "region", out["region_code"].map(REGIONS))
    return out


def unallocated(reg_pub, prov):
    """Published region total minus the provinces listed under it (should be 0)."""
    ps = prov.groupby(["ecosystem", "region_published", "period"])[VALUES].sum(min_count=1)
    rp = reg_pub.set_index(["ecosystem", "geo", "period"])[VALUES]
    ps.index = ps.index.set_names(rp.index.names)
    u = (rp - ps.reindex(rp.index)).reset_index().rename(columns={"geo": "region_published"})
    return u[(u[VALUES].abs() > 0.5).any(axis=1)].reset_index(drop=True)


def checks(df, prov, panel, unalloc):
    qc = {}
    full = pd.MultiIndex.from_product(
        [list(ECOSYSTEMS.values()), list(REGIONS), pd.period_range(START, END, freq="Q")],
        names=["ecosystem", "region_code", "period"])
    p = panel.set_index(["ecosystem", "region_code", "period"]).reindex(full).reset_index()

    # missing
    qc["missing_region_quarters"] = p[p["production_t"].isna()][
        ["ecosystem", "region_code", "period"]]
    has = prov.dropna(subset=["production_t"])
    first = has.groupby("geo")["period"].min()
    act = prov.groupby(["ecosystem", "geo", "period"])["production_t"].apply(
        lambda s: s.notna().any()).reset_index(name="has_data")
    act = act[act["period"] >= act["geo"].map(first)]
    qc["missing_province_quarters"] = act[~act["has_data"]].drop(columns="has_data")

    # duplicates: a province-quarter with data in two rows (provinces that moved region)
    dup = has[has.duplicated(["ecosystem", "geo", "period"], keep=False)]
    qc["duplicates"] = dup.sort_values(["geo", "period", "ecosystem"])[
        ["ecosystem", "geo", "region_published", "period"] + VALUES]

    # zeros and production/area inconsistencies
    p["issue"] = np.select(
        [(p.production_t == 0) & (p.area_ha == 0), (p.production_t == 0) & (p.area_ha > 0),
         (p.production_t > 0) & (p.area_ha == 0)],
        ["zero production and area", "zero production, area > 0",
         "production > 0, zero area"], "")
    qc["region_zeros"] = p[p["issue"] != ""][["ecosystem", "region_code", "period", "issue"]
                                              + VALUES]
    p["yield_t_ha"] = p.production_t / p.area_ha
    qc["yield_outliers"] = p[(p.area_ha > 500) & ~p.yield_t_ha.between(1, 7)][
        ["ecosystem", "region_code", "period"] + VALUES + ["yield_t_ha"]]

    # irrigated + rainfed = total
    w = p.pivot_table(index=["region_code", "period"], columns="ecosystem", values=VALUES,
                      dropna=False)
    gap = pd.concat([(w[(v, "irrigated")].fillna(0) + w[(v, "rainfed")].fillna(0)
                      - w[(v, "total")]).abs().rename(v) for v in VALUES], axis=1)
    qc["ecosystem_additivity"] = gap[(gap > 1).any(axis=1)].reset_index()

    # rebuilt vs PSA published regions
    reg_pub = df[df["level"] == "region"].assign(region_code=lambda d: d.geo.map(CODE_OF_LABEL))
    cmp = panel.merge(reg_pub[["ecosystem", "region_code", "period"] + VALUES],
                      on=["ecosystem", "region_code", "period"], how="outer",
                      suffixes=("_rebuilt", "_published"))
    for v in VALUES:
        cmp[f"{v}_diff"] = cmp[f"{v}_rebuilt"].fillna(0) - cmp[f"{v}_published"].fillna(0)
    cmp["differs"] = (cmp[[f"{v}_diff" for v in VALUES]].abs() > 0.5).any(axis=1)
    d = cmp[cmp["differs"]]
    summ = cmp.groupby(["ecosystem", "region_code"]).agg(
        n_quarters_differ=("differs", "sum"),
        max_abs_diff_t=("production_t_diff", lambda s: s.abs().max())).reset_index()
    span = d.groupby(["ecosystem", "region_code"])["period"].agg(["min", "max"]).reset_index()
    qc["vs_published_regions"] = summ.merge(span, how="left").rename(
        columns={"min": "first_differs", "max": "last_differs"})
    # differences must cancel within groups of regions that swapped provinces
    grp = {"VI": "VI+VII+NIR", "VII": "VI+VII+NIR", "NIR": "VI+VII+NIR",
           "IX": "IX+BARMM", "BARMM": "IX+BARMM"}
    net = (d.assign(group=d.region_code.map(grp)).dropna(subset=["group"])
           .groupby(["ecosystem", "group", "period"])["production_t_diff"].sum())
    un = unalloc.groupby(["ecosystem", "period"])["production_t"].sum()
    net = net.reset_index()
    net["minus_barmm_unallocated"] = net["production_t_diff"] + np.where(
        net["group"] == "IX+BARMM",
        un.reindex(list(zip(net.ecosystem, net.period))).fillna(0).values, 0)
    qc["swap_netting"] = (net.groupby(["ecosystem", "group"])
                          [["production_t_diff", "minus_barmm_unallocated"]]
                          .agg(lambda s: s.abs().max()).reset_index()
                          .rename(columns={"production_t_diff": "max_abs_net_diff_t",
                                           "minus_barmm_unallocated":
                                               "max_abs_net_diff_excl_unallocated_t"}))

    # national: rebuilt sum (+ unallocated) vs PHILIPPINES row
    nat = df[df["level"] == "national"].set_index(["ecosystem", "period"])[VALUES]
    tot = panel.groupby(["ecosystem", "period"])[VALUES].sum(min_count=1)
    ua = unalloc.groupby(["ecosystem", "period"])[VALUES].sum().reindex(tot.index).fillna(0)
    qc["vs_national"] = pd.concat(
        [(tot / nat - 1).abs().groupby("ecosystem").max().add_prefix("max_rel_gap_panel_"),
         ((tot + ua) / nat - 1).abs().groupby("ecosystem").max()
         .add_prefix("max_rel_gap_panel+unallocated_")], axis=1).reset_index()

    # sudden level breaks in annual totals: |change in log| > 0.4 (+49% / -33%)
    ann = (panel.assign(year=panel.period.dt.year)
           .groupby(["ecosystem", "region_code", "year"])[VALUES].sum(min_count=4)
           .reset_index())
    ann["dln_prod"] = ann.groupby(["ecosystem", "region_code"])["production_t"].transform(
        lambda s: np.log(s).diff())
    tot_a = ann[ann.ecosystem == "total"].set_index(["region_code", "year"])["dln_prod"]
    irr = ann[ann.ecosystem == "irrigated"].set_index(["region_code", "year"])["production_t"]
    tp = ann[ann.ecosystem == "total"].set_index(["region_code", "year"])["production_t"]
    share = (irr / tp).rename("irrigated_share")
    br = ann[(ann.ecosystem != "total") & (ann.dln_prod.abs() > 0.4)].copy()
    idx = list(zip(br.region_code, br.year))
    br["dln_total_palay"] = tot_a.reindex(idx).values
    br["irrigated_share_prev"] = share.reindex(list(zip(br.region_code, br.year - 1))).values
    br["irrigated_share"] = share.reindex(idx).values
    br["kind"] = np.where(br.dln_total_palay.abs() < 0.2,
                          "ecosystem series moves, total stable", "total moves too")
    qc["level_breaks"] = br.round(3)
    return qc


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(0.6)
    ax.tick_params(colors=MUTED, labelsize=7, width=0.6)
    ax.grid(axis="y", color=GRID, lw=0.5)


def plot_log_production(panel):
    fig, axes = plt.subplots(5, 4, figsize=(14, 14), sharex=True, constrained_layout=True)
    for ax, code in zip(axes.flat, REGIONS):
        for a, b in EL_NINO:
            ax.axvspan(a, b + 1, color=BAND, lw=0, zorder=0)
        for eco, col in (("irrigated", BLUE), ("rainfed", ORANGE)):
            s = panel[(panel.region_code == code) & (panel.ecosystem == eco)].sort_values("period")
            x = s.period.dt.year + (s.period.dt.quarter - 1) / 4
            ax.plot(x, np.log(s.production_t.where(s.production_t > 0)), color=col, lw=1)
        ax.set_title(code, fontsize=9, color=INK, loc="left")
        style(ax)
    for ax in axes.flat[len(REGIONS):]:
        ax.axis("off")
    leg = axes.flat[len(REGIONS)]
    leg.plot([], [], color=BLUE, lw=2, label="Irrigated palay")
    leg.plot([], [], color=ORANGE, lw=2, label="Rainfed palay")
    leg.fill_between([], [], color=BAND, label="El Niño 1997–98, 2015–16, 2023–24")
    leg.legend(loc="center left", frameon=False, fontsize=9)
    fig.supylabel("log production (t), quarterly; gaps = zero production", fontsize=9,
                  color=MUTED)
    fig.suptitle("Palay production by region and ecosystem, 1987–2025 "
                 "(fixed current boundaries)", fontsize=11, color=INK)
    fig.savefig(FIG / "rice_log_production_by_region.png", dpi=150, facecolor="white")
    plt.close(fig)


def quarter_shares(panel, years):
    p = panel[(panel.ecosystem != "total") & panel.period.dt.year.between(*years)]
    m = p.assign(q=p.period.dt.quarter).pivot_table(
        index=["ecosystem", "region_code"], columns="q", values="production_t", aggfunc="sum")
    return m.div(m.sum(axis=1), axis=0) * 100


def plot_crop_calendar(panel):
    ramp = LinearSegmentedColormap.from_list(
        "blue", ["#f4f8fd", "#b7d3f6", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
    sh = quarter_shares(panel, (1987, 2025))
    fig, axes = plt.subplots(1, 2, figsize=(9, 8), constrained_layout=True)
    for ax, eco in zip(axes, ("irrigated", "rainfed")):
        m = sh.loc[eco].reindex(list(REGIONS))
        ax.imshow(m.values, cmap=ramp, vmin=0, vmax=70, aspect="auto")
        for i in range(m.shape[0]):
            for j in range(4):
                v = m.values[i, j]
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if v > 40 else INK)
        ax.set_xticks(range(4), ["Q1\nJan–Mar", "Q2\nApr–Jun", "Q3\nJul–Sep", "Q4\nOct–Dec"],
                      fontsize=8)
        ax.set_yticks(range(len(m)), m.index, fontsize=8)
        ax.set_title(f"{eco.capitalize()} palay", fontsize=10, color=INK, loc="left")
        ax.tick_params(length=0, colors=MUTED)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.suptitle("Crop calendar: % of annual production harvested in each quarter, "
                 "1987–2025", fontsize=11, color=INK)
    fig.savefig(FIG / "rice_crop_calendar.png", dpi=150, facecolor="white")
    plt.close(fig)
    early, late = quarter_shares(panel, (1987, 1996)), quarter_shares(panel, (2016, 2025))
    drift = (late - early).round(1).add_prefix("Q")
    drift["max_abs_change_pts"] = drift.abs().max(axis=1)
    return drift.sort_values("max_abs_change_pts", ascending=False).reset_index()


def main():
    df = read_palay_corn()
    df = df[df["crop"].isin(ECOSYSTEMS) & df["period"].between(START, END)].copy()
    df["ecosystem"] = df["crop"].map(ECOSYSTEMS)
    prov = df[df["level"] == "province"].copy()
    prov["region_code"] = assign_region(prov["geo"])
    panel = rebuild(prov)
    unalloc = unallocated(df[df["level"] == "region"], prov)

    panel.to_csv(PROC / "rice_region_quarter.csv", index=False)
    unalloc.to_csv(PROC / "rice_barmm_unallocated.csv", index=False)
    mapping_table().to_csv(PROC / "province_region_map.csv", index=False)
    BOUNDARY_CHANGES.to_csv(TAB / "rice_boundary_changes.csv", index=False)

    qc = checks(df, prov, panel, unalloc)
    qc["unallocated"] = unalloc
    plot_log_production(panel)
    qc["calendar_drift"] = plot_crop_calendar(panel)
    for k, v in qc.items():
        v.to_csv(TAB / f"rice_qc_{k}.csv", index=False)

    pd.set_option("display.width", 220, "display.max_rows", 80)
    print(f"panel: {len(panel)} rows, {panel.region_code.nunique()} regions, "
          f"{panel.period.min()}–{panel.period.max()}")
    for k, v in qc.items():
        print(f"\n--- {k}: {len(v)} rows")
        print(v.head(25).to_string(index=False))


if __name__ == "__main__":
    main()
