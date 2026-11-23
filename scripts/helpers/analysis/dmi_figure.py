#!/usr/bin/env python3
"""One-page figure of the DMI analysis (run scripts/helpers/analysis/dmi_analysis.py first):

  a  MSE reduction from adding the DMI to the RONI, by variable and quarter (nested CV, 16 regions, cropland)
  b  national effect on rainfall of +1 SD of the DMI holding the RONI fixed, next to +1 SD of the RONI
  c  correlation of RONI and DMI by calendar month

  python scripts/helpers/analysis/dmi_figure.py          # writes outputs/shared/analysis/dmi/dmi_summary.png
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "src"))
from stage1 import config as C  # noqa: E402

INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
DIV = LinearSegmentedColormap.from_list("div", ["#b8322f", "#e34948", "#f0efec", "#2a78d6", "#1a4f99"])
ORDER = ["P", "SPEI3", "SM_RZ", "SM_DEEP", "RO", "E", "PET", "T", "VPD", "RS"]
LONG = {"P": "rainfall", "SPEI3": "SPEI-3", "SM_RZ": "root-zone soil moisture", "SM_DEEP": "deep soil moisture",
        "RO": "runoff", "E": "evaporation", "PET": "potential evaporation", "T": "temperature",
        "VPD": "vapour pressure deficit", "RS": "solar radiation"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--weights", default="r16_cropland")
    a = ap.parse_args()
    cfg = C.load(a.config)
    d = C.out(cfg, "analysis", "dmi", "x").parent
    SUM = pd.read_csv(d / "skill_summary.csv")
    EF = pd.read_csv(d / "dmi_effect_holding_roni.csv")
    CR = pd.read_csv(d / "correlation_roni_dmi.csv")

    plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 9.5, "axes.titleweight": "bold",
                         "axes.titlelocation": "left", "figure.facecolor": SURF, "axes.facecolor": SURF})
    fig = plt.figure(figsize=(11.5, 4.6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 1], wspace=0.42)

    # a: skill
    ax = fig.add_subplot(gs[0])
    s = SUM[SUM["weights"] == a.weights]
    vs = [v for v in ORDER if v in set(s["var"])]
    qs = ["Q1", "Q2", "Q3", "Q4", "year"]
    M = s.pivot(index="var", columns="quarter", values="mse_reduction_pct").reindex(index=vs, columns=qs)
    H = s.pivot(index="var", columns="quarter", values="dmi_helps").reindex(index=vs, columns=qs)
    lim = max(4.0, np.nanmax(np.abs(M.values)))
    ax.imshow(M.values, cmap=DIV, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for i in range(len(vs)):
        for j in range(len(qs)):
            v, h = M.values[i, j], H.values[i, j]
            mark = "*" if h in ("yes", "worse") else ""
            ax.text(j, i, f"{v:+.1f}{mark}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(v) > 0.6 * lim else INK, fontweight="bold" if mark else "normal")
    ax.set_xticks(range(len(qs)), ["JFM", "AMJ", "JAS", "OND", "year"])
    ax.set_yticks(range(len(vs)), [LONG[v] for v in vs])
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("a  Does adding the DMI to the RONI improve\n    the hindcasts? MSE reduction, %")
    ax.text(0, -0.09, "Nested cross-validation, 16 regions (cropland).\nBlue = better with the DMI, red = worse;\n"
            "* = 90 % block-bootstrap interval excludes 0.", transform=ax.transAxes, fontsize=7, color=INK2, va="top")

    # b: sign
    ax = fig.add_subplot(gs[1])
    e = EF[(EF["weights"] == a.weights) & (EF["code"] == "PH") & (EF["var"] == "P") & (EF["period"] == "1950-2025")].set_index("quarter")
    q = ["Q1", "Q2", "Q3", "Q4"]
    x = np.arange(4)
    sd = e.loc[q, "dmi_per_sd_pct"]
    lo, hi = e.loc[q, "dmi_per_sd_lo_pct"], e.loc[q, "dmi_per_sd_hi_pct"]
    ax.axhline(0, color=INK2, lw=0.8)
    ax.errorbar(x - 0.12, sd, yerr=[sd - lo, hi - sd], fmt="o", ms=7, color=BLUE, ecolor=BLUE, elinewidth=2, capsize=0,
                label="+1 SD of DMI (RONI held fixed)")
    ax.plot(x + 0.12, e.loc[q, "roni_per_sd_pct"], "s", ms=7, color=ORANGE, label="+1 SD of RONI (DMI held fixed)")
    if "model_dmi_per_sd_pct" in e:
        ax.plot(x - 0.12, e.loc[q, "model_dmi_per_sd_pct"], "_", ms=14, mew=2, color=INK, label="Stage 1 model, +1 SD of DMI")
    for i, qq in enumerate(q):
        p = e.loc[qq, "dmi_p"]
        ax.annotate(f"p={p:.2f}", (x[i] - 0.12, hi.iloc[i]), xytext=(0, 4), textcoords="offset points", ha="center",
                    fontsize=7, color=INK2)
    ax.set_xticks(x, ["JFM", "AMJ", "JAS", "OND"])
    ax.set_ylabel("national rainfall, % of the 1991–2020 mean")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_ylim(-46, 9)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax.set_title("b  Rainfall with a positive IOD,\n    holding the RONI fixed")
    ax.text(0, -0.09, "OLS on quarterly means with a linear trend,\n1950–2025, cropland-weighted national mean;\n"
            "bars = 90 % interval of the DMI effect.", transform=ax.transAxes, fontsize=7, color=INK2, va="top")

    # c: correlation
    ax = fig.add_subplot(gs[2])
    c = CR[CR["kind"] == "month"]
    periods = list(dict.fromkeys(c["period"]))
    full = c[c["period"] == periods[0]]
    rec = c[c["period"] == periods[1]]
    xm = np.arange(12)
    ax.bar(xm, full["r"], width=0.62, color=BLUE, label=periods[0])
    ax.plot(xm, rec["r"], "o", ms=6, color=INK, mfc=SURF, mew=1.6, label=periods[1])
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(xm, [m[0] for m in full["season"]])
    ax.set_ylabel("correlation of monthly RONI and DMI")
    ax.set_ylim(-0.4, 0.8)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax.set_title("c  How much RONI and DMI move together")
    ax.text(0, -0.09, "Both indices as centred 3-month means.\nr = 0.5 gives a variance inflation factor\nof 1.33; r = 0.63 gives 1.66.",
            transform=ax.transAxes, fontsize=7, color=INK2, va="top")

    out = d / "dmi_summary.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
