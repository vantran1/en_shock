"""Two tests of the DMI in the direct approach (write-up section 4). PROVISIONAL;
diagnostics, not results.

1. Blocked nested cross-validation (--part blocks), the same rule as Van's stage-1 test: a
   driver is kept only if it improves out-of-sample prediction. The years are split into
   5-year blocks aligned with Van's (1985-89, 1990-94, ..., 2020-25; VR and PF 2010-14,
   2015-19, 2020-25). Each block is held out in turn, with the 4 quarters after it (their
   lags contain the block's RONI and DMI), and the model is estimated on the rest: timing
   parameters chosen by profile estimation on the training rows only, trends set on the
   training years (restricted cubic splines, as in validate_strict.py). Every held-out
   quarter of the block is then predicted. Each crop's recommended specification
   (rice: El Nino effect shifting from 2000), with and without the DMI. Score: mean squared
   error of log production (log actual - log predicted) over all held-out region-quarters,
   and the Poisson deviance; MSE reduction from adding the DMI, % (positive = the DMI
   helps), overall and by block.

2. Typhoon channel (--part controls): the one plausible way a positive IOD could raise
   production is fewer or weaker typhoons. The DMI effect of the recommended specification
   (estimated with the typhoon and flood controls) is compared with the same model without
   the typhoon controls and without any hazard controls; and the hazard exposure itself is
   regressed on RONI and DMI (same lags, region x quarter effects): does a positive IOD go
   with less typhoon exposure in these data?

Run:  python scripts/test_dmi.py --part blocks|controls
Writes outputs/tables/dmi_blocked_cv.csv, dmi_blocked_cv_summary.csv, dmi_controls.csv,
dmi_typhoon_exposure.csv
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import argparse  # noqa: E402
import sys  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import estimate_direct as m  # noqa: E402
import validate_strict as vs  # noqa: E402
from estimation.direct import (Spec, base_design, climate_design, estimate,  # noqa: E402
                               national_effect)
from estimation.setup import break_dummies  # noqa: E402

TAB = ROOT / "outputs/tables"
SERIES = {"irrigated": "rice", "rainfed": "rice", "corn": "corn", "vr": "vr", "pf": "pf"}
BUFFER = 4


def spec_for(eco):
    """The crop's recommended specification with the trend set on the training years."""
    return replace(m.RECOMMENDED_BY_CROP[SERIES[eco]], trend="rcs")


def blocks(years):
    first = years.min()
    starts = list(range(1985, 2021, 5))
    out = []
    for a in starts:
        b = 2025 if a == 2020 else a + 4
        if b >= first:
            out.append((max(a, first), b))
    return out


def run_block(job):
    eco, dmi, (a, b) = job
    spec = replace(spec_for(eco), dmi=dmi)
    p = m.build(eco)
    d, yser = m.sample(p, "ppml", m.GROUP[eco])
    y = yser.to_numpy(float)
    LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
    LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
    per = pd.PeriodIndex(d.period, freq="Q")
    yr = per.year.to_numpy()
    test = (yr >= a) & (yr <= b)
    held = test | ((per > pd.Period(f"{b}Q4", "Q")) & (per <= pd.Period(f"{b}Q4", "Q") + BUFFER))
    train = ~np.asarray(held)
    base = vs.base_design(d, train, spec, break_dummies(d, m.GROUP[eco]))
    params, X, tR, tD, _ = vs.fit_fold(d, y, LR, LD, base, train, spec)
    Xv = X.reindex(columns=params.index, fill_value=0.0)
    mu = np.exp(Xv.to_numpy(float) @ params.to_numpy())
    t = test & (y > 0)
    e = np.log(y[t]) - np.log(mu[t])
    yt, mt = y[test], mu[test]
    dev = 2 * np.sum(np.where(yt > 0, yt * np.log(np.where(yt > 0, yt, 1) / mt), 0) - (yt - mt))
    return dict(series=eco, dmi=dmi, block=f"{a}-{b}", n=int(t.sum()), sse_log=float((e ** 2).sum()),
                deviance=float(dev), theta_R=tR, theta_D=tD if dmi else np.nan)


def part_blocks():
    jobs = []
    for eco in SERIES:
        yrs = pd.PeriodIndex(m.build(eco).period, freq="Q").year
        for blk in blocks(yrs):
            for dmi in (True, False):
                jobs.append((eco, dmi, blk))
    with ProcessPoolExecutor(8) as ex:
        t = pd.DataFrame(list(ex.map(run_block, jobs)))
    t.assign(status="provisional").round(5).to_csv(TAB / "dmi_blocked_cv.csv", index=False)
    rows = []
    for eco, g in t.groupby("series", sort=False):
        w = g.pivot_table(index="block", columns="dmi", values=["sse_log", "deviance", "n"])
        mse_with = w[("sse_log", True)].sum() / w[("n", True)].sum()
        mse_without = w[("sse_log", False)].sum() / w[("n", False)].sum()
        by_block = (1 - w[("sse_log", True)] / w[("sse_log", False)]) * 100
        # interval: bootstrap over blocks
        rng = np.random.default_rng(0)
        bs = []
        for _ in range(2000):
            k = rng.integers(0, len(w), len(w))
            bs.append((1 - w[("sse_log", True)].iloc[k].sum() / w[("sse_log", False)].iloc[k].sum()) * 100)
        rows.append({"series": eco, "blocks": len(w), "mse_log_with_dmi": mse_with,
                     "mse_log_without_dmi": mse_without,
                     "mse_reduction_with_dmi_pct": (1 - mse_with / mse_without) * 100,
                     "p05": np.percentile(bs, 5), "p95": np.percentile(bs, 95),
                     "deviance_reduction_with_dmi_pct":
                         (1 - w[("deviance", True)].sum() / w[("deviance", False)].sum()) * 100,
                     "blocks_better_with_dmi": int((by_block > 0).sum()),
                     "by_block_pct": "; ".join(f"{k}: {v:+.1f}" for k, v in by_block.items())})
    s = pd.DataFrame(rows)
    s.assign(status="provisional").round(3).to_csv(TAB / "dmi_blocked_cv_summary.csv", index=False)
    pd.set_option("display.width", 250, "display.max_colwidth", 200)
    print(s.round(2).to_string(index=False))


def part_controls():
    rows, expo = [], []
    variants = {"all controls (recommended)": m.CONTROLS,
                "no typhoon controls": [c for c in m.CONTROLS if not c.startswith("ty_")],
                "no hazard controls": ["eq", "eruption", "pinatubo_1991"]}
    for eco, crop in SERIES.items():
        spec = m.with_dmi(m.RECOMMENDED_BY_CROP[crop])
        p = m.build(eco)
        d, y = m.sample(p, "ppml", m.GROUP[eco])
        LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
        LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
        w = m.weights(eco)
        for name, ctl in variants.items():
            base = base_design(d, ctl, break_dummies(d, m.GROUP[eco]), spec.trend)
            r = estimate(d, y, LR, LD, base, "ppml", spec)
            est, se = national_effect(r["fit"], r["X"], w, "D", spec)
            ridx = "RP" if spec.split else "R"
            eR, seR = national_effect(r["fit"], r["X"], w, ridx, spec)
            rows.append({"series": eco, "controls": name, "dmi_effect": est, "t_dmi": est / se,
                         "theta_D": r["theta_D"], "el_nino_effect": eR, "t_el_nino": eR / seR})
        # does the DMI predict typhoon exposure? same lags and timing as the production model
        # (theta from the recommended fit), region x quarter effects, DK s.e.
        r0 = estimate(d, y, LR, LD, base_design(d, m.CONTROLS, break_dummies(d, m.GROUP[eco]),
                                                spec.trend), "ppml", spec)
        from estimation.direct import blended
        from estimation.panel import fit
        zR, zD = blended(LR, r0["theta_R"]), blended(LD, r0["theta_D"])
        fe = pd.get_dummies(d.region_code + "_q" + d.q.astype(str), dtype=float)
        for c in ("ty_share_ts", "ty_share_ty", "flood_share"):
            X = pd.concat([pd.DataFrame({"roni": zR, "dmi": zD}, index=d.index), fe], axis=1)
            f = fit(d[c], X, d.period, "ols")
            se = pd.Series(f["se"], index=X.columns)
            expo.append({"series": eco, "exposure": c, "mean": d[c].mean(),
                         "dmi_coef": f["params"]["dmi"], "t_dmi": f["params"]["dmi"] / se["dmi"],
                         "roni_coef": f["params"]["roni"], "t_roni": f["params"]["roni"] / se["roni"]})
    t = pd.DataFrame(rows)
    t.assign(status="provisional").round(4).to_csv(TAB / "dmi_controls.csv", index=False)
    e = pd.DataFrame(expo)
    e.assign(status="provisional").round(4).to_csv(TAB / "dmi_typhoon_exposure.csv", index=False)
    pd.set_option("display.width", 250)
    print(t.round(3).to_string(index=False))
    print(e.round(4).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["blocks", "controls"], required=True)
    a = ap.parse_args()
    part_blocks() if a.part == "blocks" else part_controls()
