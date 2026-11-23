#!/usr/bin/env python3
"""Tables and figures of the lag analysis (run scripts/helpers/analysis/lag_analysis.py first).

  python scripts/helpers/analysis/lag_summary.py
Writes outputs/shared/analysis/lags/summary_*.csv and lag_*.png.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import matplotlib
import numpy as np
import pandas as pd
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "src"))
from stage1 import config as C  # noqa: E402

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SK = {"cells_rho": "cells", "r16_cropland_rho": "16 regions, cropland", "r17_population_rho": "17 regions, population"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = C.load(a.config)
    d = C.out(cfg, "analysis", "lags", "plain.csv").parent
    P = pd.read_csv(d / "plain.csv")
    N = pd.read_csv(d / "nested.csv")
    Ch = pd.read_csv(d / "nested_choices.csv")
    order = list(dict.fromkeys(P["lagset"]))
    vorder = list(dict.fromkeys(P["var"]))

    # plain: each lag set on its own
    t1 = P.groupby("lagset", sort=False)[list(SK)].mean()
    best = P.loc[P.groupby(["var", "month"])["cells_rho"].idxmax()]
    t1["n_best"] = best["lagset"].value_counts().reindex(t1.index).fillna(0).astype(int)
    t1.to_csv(d / "summary_plain_by_lagset.csv")
    pv = P.pivot_table(index="var", columns="lagset", values="r16_cropland_rho", sort=False)[order].reindex(vorder)
    pv.to_csv(d / "summary_plain_by_var_r16_cropland.csv")

    # nested: menus
    rows = []
    for m in ("cumulative", "sync+one lag", "seasonal", "all"):
        x = N[N["menu"] == m].set_index(["var", "month"])
        c = N[N["menu"] == "current"].set_index(["var", "month"])
        for k in SK:
            dlt = (x[k] - c[k]).dropna()
            w = stats.wilcoxon(dlt) if (dlt != 0).any() else None
            rows.append(dict(menu=m, skill=SK[k], current=c[k].mean(), menu_skill=x[k].mean(), mean_delta=dlt.mean(),
                             median_delta=dlt.median(), share_better=(dlt > 0).mean(), share_better_by_002=(dlt > 0.02).mean(),
                             share_worse_by_002=(dlt < -0.02).mean(), wilcoxon_p=w.pvalue if w else np.nan, n=len(dlt)))
    t2 = pd.DataFrame(rows)
    t2.to_csv(d / "summary_nested_menus.csv", index=False)
    nv = N.pivot_table(index="var", columns="menu", values=list(SK), sort=False)
    nv.to_csv(d / "summary_nested_by_var.csv")
    nm = N.pivot_table(index="month", columns="menu", values="r16_cropland_rho")
    nm.to_csv(d / "summary_nested_by_month_r16_cropland.csv")
    ch = Ch[Ch["menu"] == "all"]["lagset"].value_counts(normalize=True).reindex(order).fillna(0)
    ch.to_csv(d / "summary_nested_choice_share_all.csv")

    # figures
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    xs = np.arange(len(order))
    for k, mk in (("cells_rho", "o"), ("r16_cropland_rho", "s")):
        ax.plot(xs, t1.loc[order, k], marker=mk, lw=1, label=SK[k])
    ax.axhline(t1.loc["sync+lag1", "r16_cropland_rho"], color="grey", lw=0.6, ls=":")
    ax.set_xticks(xs, order, rotation=55, ha="right", fontsize=8)
    ax.set_ylabel("mean CV Spearman (all variables and months)")
    ax.set_title("Each lag set on its own (plain CV, best My/Mc per lag set)", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="y", lw=0.3)
    fig.tight_layout()
    fig.savefig(d / "lag_plain_by_lagset.png")
    plt.close(fig)

    rec = "seasonal"
    x = N[N["menu"] == rec].pivot_table(index="var", columns="month", values="r16_cropland_rho").reindex(vorder)
    c = N[N["menu"] == "current"].pivot_table(index="var", columns="month", values="r16_cropland_rho").reindex(vorder)
    D = x - c
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), dpi=150)
    im = axs[0].imshow(c.values, cmap="viridis", vmin=0, vmax=0.7, aspect="auto")
    axs[0].set_title("Nested CV skill now (sync, sync+lag1)\n16 regions, cropland weights", fontsize=10)
    fig.colorbar(im, ax=axs[0], shrink=0.85)
    lim = 0.2
    im2 = axs[1].imshow(D.values, cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto")
    axs[1].set_title("Change with menu {sync, sync+lag1, sync+lag3, sync+lag6}", fontsize=10)
    fig.colorbar(im2, ax=axs[1], shrink=0.85)
    for axx in axs:
        axx.set_xticks(range(12), MON, fontsize=8)
        axx.set_yticks(range(len(vorder)), vorder, fontsize=8)
    for i in range(D.shape[0]):
        for j in range(D.shape[1]):
            v = D.values[i, j]
            axs[1].text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=6, color="white" if abs(v) > 0.12 else "black")
    fig.tight_layout()
    fig.savefig(d / "lag_nested_delta.png")
    plt.close(fig)

    menus = [("current", "now: sync, sync+lag1", "#555555", "-"), ("cumulative", "sync+lag1..k (k up to 6)", "#c47a00", ":"),
             ("seasonal", "sync, sync+lag1, +lag3, +lag6", "#1f6fb4", "-"), ("sync+one lag", "sync + any one lag 1-6", "#5aa469", "--")]
    fig, axs = plt.subplots(1, 2, figsize=(12, 4), dpi=150, gridspec_kw=dict(width_ratios=[1.25, 1]))
    for m, lab, col, ls in menus:
        y = N[N["menu"] == m].groupby("month")["r16_cropland_rho"].mean()
        axs[0].plot(range(12), y.values, ls, color=col, marker="o", ms=3, lw=1.4, label=lab)
    axs[0].set_xticks(range(12), MON, fontsize=8)
    axs[0].set_ylabel("nested CV Spearman, mean over variables")
    axs[0].set_title("Honest skill by target month (16 regions, cropland)", fontsize=10)
    axs[0].axhline(0, color="k", lw=0.4)
    axs[0].legend(fontsize=7.5, frameon=False)
    axs[0].grid(axis="y", lw=0.3)
    cs = Ch[Ch["menu"] == rec]
    tab = pd.crosstab(cs["month"], cs["lagset"], normalize="index")[["sync", "sync+lag1", "sync+lag3", "sync+lag6"]]
    bottom = np.zeros(12)
    for k, col in zip(tab.columns, ["#bbbbbb", "#8fb8de", "#1f6fb4", "#0b3d6b"]):
        axs[1].bar(range(12), tab[k].values, bottom=bottom, color=col, label=k, width=0.75)
        bottom += tab[k].values
    axs[1].set_xticks(range(12), MON, fontsize=8)
    axs[1].set_ylabel("share of variables x outer folds")
    axs[1].set_title("Lag set chosen with the seasonal menu", fontsize=10)
    axs[1].legend(fontsize=7.5, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout()
    fig.savefig(d / "lag_by_month.png")
    plt.close(fig)

    pd.set_option("display.width", 200)
    print("Plain CV, mean over variable-months:\n", t1.round(3).to_string())
    print("\nNested CV, menus vs current:\n", t2.round(3).to_string())
    print("\nNested CV by variable (16 regions, cropland):\n",
          N.pivot_table(index="var", columns="menu", values="r16_cropland_rho", sort=False).reindex(vorder).round(3).to_string())
    print("\nNested by month (16 regions, cropland):\n", nm.round(3).to_string())
    print("\nLag sets chosen by the 'all' menu (share of outer folds):\n", ch.round(3).to_string())


if __name__ == "__main__":
    main()
