"""World rice price: estimation of the price note's Eq. (1), its checks and the episode validation
(DEFINE-PH methodology v5, price note Sections 2.2 and 4). RONI only; the DMI enters only as a variant.

Main specification: quarterly log real export price of Thai 5% broken white rice (World Bank Pink
Sheet, deflated by the MUV index), 1960Q1-2025Q4, on the RONI of the previous 1..6 quarters with the
binomial lag profile, the log real prices of urea and crude oil, the share of the quarter under rice
export restrictions by the major exporters, quarter-of-year effects and a linear trend; timing by
profile estimation; Newey-West standard errors.

Checks named in the note (Section 2.2): year-on-year changes; the lagged price (long-run effect);
Viet Nam 5% (from 2004, the first full quarter of the series); from 1990, with a test of whether the
RONI effect differs after 1990. Further checks: DAP added (from 1967, when the series starts) next to
the main model on the same years; 4 lags; the US CPI as deflator; no export restriction control;
restrictions of all listed exporters; the DMI added.

Validation (note Section 4): each episode (1997-98, 2015-16, 2023-24) is left out in turn, from the
first quarter of its path to K quarters after it; the equation is re-estimated without it, and the
predicted El Nino effect is compared with the observed deviation of the price from the model's
non-climate part (for 2023-24 with and without the effect of the restriction indicator). And a
real-time check: 2026, after the end of the estimation sample.

Run:  python scripts/08_prices.py (both parts), or this part alone: python scripts/helpers/prices_estimate_rice.py
Writes outputs/prices/world_rice/: coefficients.csv, lag_profile.csv, profile.csv, checks.csv,
validation.csv, validation_2026.csv, estimation_data.csv, figure_price.png, summary_estimation.txt
"""
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # the en_shock repository
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from prices import world_rice as W  # noqa: E402

OUT = ROOT / "outputs" / "prices" / "world_rice"
MAIN = W.Spec()
START, END = "1960Q1", "2025Q4"


def pct(b):
    return 100 * (np.exp(b) - 1)


def row(name, d, fit, note=""):
    B, se = W.total_effect(fit)
    w = W.binomial_weights(fit.theta_R, fit.spec.K)
    mean_lag = float(w @ np.arange(fit.spec.first_lag, fit.spec.first_lag + fit.spec.K))
    ban = fit.params.get("ban", np.nan)
    r = dict(check=name, price=d.price, deflator=d.deflator, form=fit.spec.form, K=fit.spec.K,
             controls=" ".join(fit.spec.controls), sample=fit.sample, n=fit.n, theta_R=fit.theta_R,
             mean_lag_quarters=round(mean_lag, 2), B_R=B, B_R_se=se, B_R_p=W.p_value(B / se) if se > 0 else np.nan,
             effect_pct_per_unit_RONI=pct(B), effect_lo90=pct(B - 1.645 * se), effect_hi90=pct(B + 1.645 * se),
             ban_coef=ban, ban_pct=pct(ban), theta_on_grid_edge=fit.on_grid_edge, r2=fit.r2, note=note)
    if "BR_post" in fit.params:
        b, s = fit.lincom({"BR_post": 1.0})
        r.update(B_post_1990=b, B_post_1990_se=s, B_post_1990_p=W.p_value(b / s))
    if "BD" in fit.params:
        b, s = fit.lincom({"BD": 1.0})
        r.update(B_D=b, B_D_se=s, B_D_p=W.p_value(b / s), theta_D=fit.theta_D)
    return r


def checks(d_main, f_main):
    rows = [row("main", d_main, f_main, "Eq. (1): Thai 5%, MUV, K = 6, urea and oil, levels")]
    rows.append(row("year-on-year changes", d_main, W.estimate(d_main, replace(MAIN, name="yoy", form="yoy")),
                    "note 2.2; 4-quarter changes of all variables"))
    rows.append(row("lagged price", d_main, W.estimate(d_main, replace(MAIN, name="ldv", form="ldv")),
                    "note 2.2; long-run effect B / (1 - rho)"))
    dv = W.build("rice_viet5", "muv", START, END)
    rows.append(row("Viet Nam 5%", dv, W.estimate(dv, MAIN), "note 2.2; the series starts in Dec 2003"))
    d90 = d_main.subset(d_main.frame["year"] >= 1990)
    rows.append(row("from 1990", d90, W.estimate(d90, MAIN), "note 2.2"))
    rows.append(row("test: RONI effect after 1990", d_main,
                    W.estimate(d_main, replace(MAIN, name="post1990", post_year=1990)),
                    "note 2.2; B_post_1990 = change of the RONI effect from 1990 (same timing)"))
    d67 = d_main.subset(d_main.frame["year"] >= 1967)
    rows.append(row("from 1967 (main controls)", d67, W.estimate(d67, MAIN),
                    "same years as the DAP check, to separate the sample from the control"))
    rows.append(row("DAP added (from 1967)", d67, W.estimate(d67, replace(MAIN, controls=W.CONTROLS_WITH_DAP)),
                    "urea, DAP and oil, as in the note; DAP starts in Jan 1967"))
    d4 = W.build("rice_thai5", "muv", START, END, K=4)
    rows.append(row("4 lags", d4, W.estimate(d4, replace(MAIN, K=4))))
    dc = W.build("rice_thai5", "cpi", START, END)
    rows.append(row("US CPI deflator", dc, W.estimate(dc, MAIN), "added check, not in the note"))
    rows.append(row("no export restriction control", d_main,
                    W.estimate(d_main, replace(MAIN, controls=("lnurea", "lnoil")))))
    da = W.build("rice_thai5", "muv", START, END, restrictions_main_only=False)
    rows.append(row("restrictions of all exporters", da, W.estimate(da, MAIN),
                    "adds Egypt and Cambodia 2008; both fall inside India's 2007-11 ban, so identical to main"))
    rows.append(row("DMI added (variant)", d_main, W.estimate(d_main, replace(MAIN, dmi=True)),
                    "not used: RONI only, as agreed"))
    return pd.DataFrame(rows)


def climate_part(fit, d):
    """y, the regressors, the climate component and the rest of the fitted value."""
    y, X = W.design(d, fit.theta_R, fit.theta_D, fit.spec)
    cl = [c for c in X.columns if c in ("BR", "BD", "BR_post")]
    clim = X[cl].to_numpy(float) @ fit.params[cl].to_numpy()
    rest = X.drop(columns=cl).to_numpy(float) @ fit.params.drop(cl).to_numpy()
    return y, X, clim, rest


def resid_at(fit, d, quarter):
    """The non-climate residual (y - fitted) of `fit` in one quarter of `d`."""
    one = d.subset(d.frame.index == quarter)
    y, _, clim, rest = climate_part(fit, one)
    return float(y[0] - rest[0] - clim[0])


def validation(d, f_main):
    """Leave each episode out (path start to K quarters after its end), re-estimate, compare.

    observed = y - (non-climate fitted part), i.e. the climate component plus the residual. The
    residual is very persistent (long swings of the price), so the observed deviation is measured
    against the residual of the quarter before the path ("vs_pre"); the level is kept for reference."""
    rows = []
    K = MAIN.K
    roni = W.index_quarterly("roni")
    for name, (a, b) in W.EPISODE_PATHS.items():
        a, b = pd.Period(a, "Q"), pd.Period(b, "Q")
        win = np.asarray((d.frame.index >= a) & (d.frame.index <= b + K))
        f = W.estimate(d.subset(~win), MAIN)
        pre = resid_at(f, d, a - 1)
        dw = d.subset(win)
        y, X, clim, rest = climate_part(f, dw)
        ban = X["ban"].to_numpy(float) * f.params["ban"]
        _, _, clim_full, _ = climate_part(f_main, dw)
        for i, qq in enumerate(dw.frame.index):
            obs = y[i] - rest[i]
            rows.append(dict(episode=name, quarter=str(qq), step=(qq - a).n, in_path=bool(qq <= b),
                             roni=float(roni.get(qq, np.nan)), ban_share=float(dw.frame["ban"].iloc[i]),
                             predicted_pct=pct(clim[i]), observed_vs_pre_pct=pct(obs - pre),
                             observed_vs_pre_incl_ban_pct=pct(obs + ban[i] - pre),
                             observed_level_pct=pct(obs), in_sample_predicted_pct=pct(clim_full[i]),
                             theta_R_loo=f.theta_R, B_R_loo=f.params["BR"]))
    return pd.DataFrame(rows)


def validation_2026(f_main):
    """Real time: the model fitted to 2025Q4, predicting the quarters of 2026 with complete data;
    the observed deviation is measured against the residual of 2025Q4."""
    d = W.build("rice_thai5", "muv", "2025Q1", "2026Q4")
    pre = resid_at(f_main, d, pd.Period("2025Q4", "Q"))
    d = d.subset(d.frame["year"] >= 2026)
    if not len(d.frame):
        return pd.DataFrame()
    y, X, clim, rest = climate_part(f_main, d)
    roni = W.index_quarterly("roni")
    return pd.DataFrame(dict(quarter=[str(q) for q in d.frame.index],
                             roni=[float(roni.get(q, np.nan)) for q in d.frame.index],
                             predicted_pct=pct(clim), observed_vs_2025Q4_pct=pct(y - rest - pre),
                             price_usd=d.frame["price_usd"].to_numpy()))


def figure(d, f):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: figure skipped")
        return
    INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
    BLUE, RED, GREY = "#2a78d6", "#d03b3b", "#9c9b96"
    y, X, clim, rest = climate_part(f, d)
    idx = d.frame.index.to_timestamp(how="start") + pd.Timedelta(days=45)
    fig, (a, b) = plt.subplots(2, 1, figsize=(10, 6.6), sharex=True,
                               gridspec_kw=dict(height_ratios=[1.5, 1], hspace=0.12))
    ban = d.frame["ban"].to_numpy()
    for ax in (a, b):
        for i in np.flatnonzero(ban > 0):
            ax.axvspan(idx[i] - pd.Timedelta(days=45), idx[i] + pd.Timedelta(days=46), color=GREY,
                       alpha=0.3 * ban[i], lw=0)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=INK2, labelsize=8)
    base = np.exp(y[(d.frame["year"] == 2010).to_numpy()]).mean()
    a.plot(idx, np.exp(y) / base * 100, color=INK, lw=1.2, label="observed")
    a.plot(idx, np.exp(rest + clim) / base * 100, color=BLUE, lw=1, label="fitted, Eq. (1)")
    a.set_yscale("log")
    a.set_ylabel("real Thai 5% price, 2010 = 100 (log scale)", fontsize=8, color=INK2)
    a.legend(frameon=False, fontsize=8, loc="upper right")
    a.set_title("a  World rice price (Thai 5%, deflated by MUV); grey: export restrictions by major exporters",
                loc="left", fontsize=9.5, color=INK, fontweight="bold")
    b.axhline(0, color=INK2, lw=0.8)
    b.fill_between(idx, 0, pct(clim), where=clim >= 0, color=RED, lw=0, alpha=0.85, label="price higher")
    b.fill_between(idx, 0, pct(clim), where=clim < 0, color=BLUE, lw=0, alpha=0.85, label="price lower")
    b.set_ylabel("ENSO effect on the price, %", fontsize=8, color=INK2)
    b.set_title(f"b  Estimated ENSO component, B * sum_j w_j RONI(q-j)  (theta = {f.theta_R:.2f}, K = {f.spec.K})",
                loc="left", fontsize=9.5, color=INK, fontweight="bold")
    b.legend(frameon=False, fontsize=8, loc="upper left")
    fig.savefig(OUT / "figure_price.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = W.build("rice_thai5", "muv", START, END)
    f = W.estimate(d, MAIN)
    tab = pd.DataFrame({"coef": f.params, "se": f.se})
    tab["p"] = [W.p_value(c / s) if s > 0 else np.nan for c, s in zip(tab.coef, tab.se)]
    tab.loc["theta_R"] = [f.theta_R, np.nan, np.nan]
    tab.round(5).to_csv(OUT / "coefficients.csv", index_label="term")
    w = W.binomial_weights(f.theta_R, MAIN.K)
    pd.DataFrame({"lag_quarters": np.arange(MAIN.first_lag, MAIN.first_lag + MAIN.K), "weight": w,
                  "beta": f.params["BR"] * w}).round(5).to_csv(OUT / "lag_profile.csv", index=False)
    f.profile.round(6).to_csv(OUT / "profile.csv", index=False)
    ed = d.frame.copy()
    for j in range(MAIN.K):
        ed[f"roni_lag{MAIN.first_lag + j}"] = d.lagsR[:, j]
    ed.round(5).to_csv(OUT / "estimation_data.csv", index_label="quarter")
    C = checks(d, f)
    C.round(4).to_csv(OUT / "checks.csv", index=False)
    V = validation(d, f)
    V.round(3).to_csv(OUT / "validation.csv", index=False)
    V26 = validation_2026(f)
    V26.round(3).to_csv(OUT / "validation_2026.csv", index=False)
    figure(d, f)

    pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_colwidth", 40)
    B, se = W.total_effect(f)
    mean_lag = float(w @ np.arange(MAIN.first_lag, MAIN.first_lag + MAIN.K))
    lines = [f"World rice price, Eq. (1): Thai 5%, deflated by MUV, {f.sample}, n = {f.n}",
             f"controls: {', '.join(MAIN.controls)}, quarter effects, linear trend",
             f"theta_R = {f.theta_R} (mean lag {mean_lag:.2f} quarters), R2 = {f.r2:.3f}",
             f"B_R = {B:.4f} (Newey-West s.e. {se:.4f}, p = {W.p_value(B / se):.3f}): a sustained +1 RONI "
             f"raises the real price by {pct(B):.1f}% (90% interval {pct(B - 1.645 * se):.1f} to "
             f"{pct(B + 1.645 * se):.1f})",
             "", "Coefficients", tab.round(4).to_string(), "",
             "Checks (effect = % rise of the real price for a sustained +1 RONI)",
             C[["check", "sample", "n", "theta_R", "mean_lag_quarters", "effect_pct_per_unit_RONI",
                "effect_lo90", "effect_hi90", "B_R_p", "ban_pct"]].round(3).to_string(index=False)]
    post = C[C.check.str.startswith("test")].iloc[0]
    lines.append(f"\nRONI effect after 1990 minus before: {post.B_post_1990:.4f} (s.e. {post.B_post_1990_se:.4f}, "
                 f"p = {post.B_post_1990_p:.3f})")
    va = V.groupby("episode", sort=False)[["predicted_pct", "observed_vs_pre_pct", "observed_vs_pre_incl_ban_pct",
                                           "in_sample_predicted_pct"]].mean()
    lines += ["", "Validation, episode left out (mean over the path and the K quarters after it, %; observed",
              "measured against the quarter before the path)", va.round(1).to_string()]
    if len(V26):
        lines += ["", "Real-time check, 2026 (model fitted to 2025Q4)", V26.round(1).to_string(index=False)]
    txt = "\n".join(lines)
    (OUT / "summary_estimation.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
