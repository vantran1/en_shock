"""World rice price shock, price note Section 2.3, Eq. (2), with its range and the upper estimate.

For a climate-mode path, the shock is the relative rise of the real world rice price against the
neutral path (RONI = 0), with the controls at their neutral values, so it excludes export bans:

  S_q = exp( B^R sum_j w_j(theta^R) RONI^S_{q-j} ) - 1                                          (2)

Upper estimate (note 2.3): adds the price effect of an export ban, the coefficient of the restriction
indicator in Eq. (1), in the quarters of the path (as India's restrictions of 2022-24 coincided with
the 2023-24 El Nino). How long such a ban lasts is not set by the note; here, the quarters of the path.

Paths, as scripts/shocks_direct.py on ginevra-agriculture: the RONI of the quarters with RONI >= 0.5
of the three strong episodes (1997Q2-1998Q1, 2015Q2-2016Q1, 2023Q3-2024Q1), replayed, and a unit path
(RONI +1 for four quarters from Q3). Delivered for the quarters of the path and the K = 6 quarters
after it.

Range: moving-block bootstrap over years (blocks of 5 consecutive years, whole years), re-estimating
the timing in each replication; 5th and 95th percentiles. The price is far more persistent than the
crop series (long swings), so blocks of one year, as for the crops, would understate the range; they
are reported as a check (shocks_block1_check.csv).

Entry into DEFINE-PH (note Eq. 2a): S^imp = S x (share of rice in real agricultural imports in the
model); the share comes from DEFINE-PH (SOAS). The shock delivered here is S.

Run from the repository root:  python scripts/shocks_rice_price.py [--reps 1000] [--block-years 5]
Writes outputs/rice_price/: shocks.csv, shocks_bootstrap.csv, shocks_block1_check.csv,
figure_shocks.png, summary_shocks.txt
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from prices import world_rice as W  # noqa: E402

OUT = ROOT / "outputs" / "rice_price"
MAIN = W.Spec()
KEY = ["path", "scenario_q"]


def ranges(draws: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
    g = draws.groupby(KEY, sort=False)
    out = pd.DataFrame({f"{prefix}S_p05": g["S"].quantile(0.05), f"{prefix}S_p95": g["S"].quantile(0.95),
                        f"{prefix}S_upper_ban_p05": g["S_upper_ban"].quantile(0.05),
                        f"{prefix}S_upper_ban_p95": g["S_upper_ban"].quantile(0.95)})
    return out.reset_index()


def figure(out: pd.DataFrame):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: figure skipped")
        return
    INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
    BLUE, BAND, RED = "#2a78d6", "#b7d3f6", "#d03b3b"
    names = list(dict.fromkeys(out.path))
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.2), sharey=True, constrained_layout=True)
    for ax, name in zip(axes.flat, names):
        e = out[out.path == name]
        ax.axvspan(-0.5, e[e.in_path].step.max() + 0.5, color="#ecebe7", lw=0, zorder=0)
        ax.fill_between(e.step, e.S_p05 * 100, e.S_p95 * 100, color=BAND, lw=0, label="90% range (block bootstrap)")
        ax.plot(e.step, e.S * 100, color=BLUE, lw=2, marker="o", ms=4, label="shock, Eq. (2)")
        ax.plot(e.step, e.S_upper_ban * 100, color=RED, lw=1.2, ls="--", label="upper estimate (with an export ban)")
        ax.axhline(0, color=INK2, lw=0.8)
        labels = [f"+{v}" for v in e.step] if name == W.UNIT_PATH else list(e.scenario_q)
        ax.set_xticks(e.step, labels, fontsize=8, rotation=45)
        ax.set_title(name, fontsize=10, color=INK, loc="left")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=8, colors=INK2)
        ax.grid(axis="y", color=GRID, lw=0.5)
    for ax in axes[:, 0]:
        ax.set_ylabel("rise of the real world rice price (%)", fontsize=8, color=INK2)
    axes[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("PROVISIONAL. World rice price shock (Thai 5%, RONI only, price note Eq. 2); "
                 "shaded: quarters of the path", fontsize=10, color=INK)
    fig.savefig(OUT / "figure_shocks.png", dpi=160, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--block-years", type=int, default=5)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    d = W.build("rice_thai5", "muv", "1960Q1", "2025Q4")
    f = W.estimate(d, MAIN)
    path_set = W.paths()
    central = W.all_shocks(f, path_set)
    draws = W.block_bootstrap(d, MAIN, a.reps, a.block_years, seed=1, path_set=path_set)
    draws.round(6).to_csv(OUT / "shocks_bootstrap.csv", index=False)
    out = central.merge(ranges(draws), on=KEY, how="left")
    out = out[["path", "scenario_q", "step", "in_path", "roni_path", "S", "S_p05", "S_p95",
               "S_upper_ban", "S_upper_ban_p05", "S_upper_ban_p95"]]
    note = f"Thai 5%, MUV-deflated, RONI only, K = {MAIN.K}, urea and oil controls, {f.sample}; provisional"
    out.assign(reps=a.reps, block_years=a.block_years, spec_note=note).round(5).to_csv(OUT / "shocks.csv", index=False)

    chk = W.block_bootstrap(d, MAIN, min(a.reps, 500), 1, seed=2, path_set=path_set)
    out.merge(ranges(chk, "block1_"), on=KEY)[["path", "scenario_q", "S", "S_p05", "S_p95", "block1_S_p05",
                                               "block1_S_p95"]].round(5).to_csv(OUT / "shocks_block1_check.csv",
                                                                                index=False)
    figure(out)

    pd.set_option("display.width", 220, "display.max_rows", 200)
    show = out.copy()
    for c in ("S", "S_p05", "S_p95", "S_upper_ban", "S_upper_ban_p05", "S_upper_ban_p95"):
        show[c] = (show[c] * 100).round(1)
    peaks = []
    for name, e in out.groupby("path", sort=False):
        i = e.S.idxmax()
        s = draws[(draws.path == name) & (draws.scenario_q == e.loc[i, "scenario_q"])].S
        peaks.append(dict(path=name, peak_quarter=e.loc[i, "scenario_q"], peak_S_pct=100 * e.loc[i, "S"],
                          peak_p05=100 * e.loc[i, "S_p05"], peak_p95=100 * e.loc[i, "S_p95"],
                          mean_S_pct_path_plus_K=100 * e.S.mean(), draws_with_rise_at_peak_pct=100 * (s > 0).mean()))
    th = draws.groupby("rep").theta_R.first()
    ban = f.params.get("ban", np.nan)
    lines = [f"World rice price shock (Eq. 2): {note}",
             f"theta_R = {f.theta_R}, B_R = {f.params['BR']:.4f}, ban coefficient = {ban:.4f} "
             f"(+{100 * (np.exp(ban) - 1):.1f}% for a quarter fully under restrictions)",
             f"bootstrap: {a.reps} reps, moving blocks of {a.block_years} years; theta_R in the draws: "
             f"median {th.median():.2f}, 5-95% {th.quantile(0.05):.2f}-{th.quantile(0.95):.2f}",
             "", "Shock by path and quarter, % (S = main, excludes export bans; S_upper_ban adds a ban in the "
             "quarters of the path)", show.to_string(index=False), "",
             "Peak, and mean over the path and the K quarters after it (%)",
             pd.DataFrame(peaks).round(1).to_string(index=False), "",
             "Into DEFINE-PH (note Eq. 2a): multiply S by the share of rice in real agricultural imports in the model."]
    txt = "\n".join(lines)
    (OUT / "summary_shocks.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
