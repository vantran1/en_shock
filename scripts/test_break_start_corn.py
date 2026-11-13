"""Where should the Region VI corn break dummy start? (Negros Occidental measurement break;
src/estimation/setup.py). PROVISIONAL; a diagnostic for choosing the start, not a result.

Total corn, recommended specification (estimate_direct.py), Poisson. The model is
estimated with no dummy and with the dummy starting in each quarter from 2022Q1 to 2025Q2
(timing re-estimated each time); the start with the lowest deviance is the one the data
prefer (the usual way of dating a level break). Region VI's own El Nino effect is
estimated mainly from the earlier episodes, so the dummy only has to explain what goes
beyond the El Nino loss the model expects in 2023Q3-2024Q2. Also reported: Region VI's
El Nino effect and the national El Nino effect for each start, and the check sample
without Region VI corn from 2023Q3.

Run:  python scripts/test_break_start_corn.py [--trend region]
Writes outputs/tables/corn_break_start_test.csv; with --trend region (v5's linear regional
trends instead of the spline, to see whether the spline absorbs the break)
outputs/tables/corn_break_start_test_linear_trend.csv
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import argparse  # noqa: E402
import sys  # noqa: E402
from dataclasses import replace  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd  # noqa: E402

import estimate_direct as m  # noqa: E402
from estimation.direct import base_design, estimate, national_effect  # noqa: E402
from estimation.setup import break_dummies, sample as break_sample  # noqa: E402

TAB = ROOT / "outputs/tables"
SPEC = m.RECOMMENDED
STARTS = ["none"] + [str(q) for q in pd.period_range("2022Q1", "2025Q2", freq="Q")] + ["check"]


def run(job):
    start, spec = job
    p = m.build("corn")
    if start == "check":
        p = break_sample(p, "corn", "end_before_break").reset_index(drop=True)
    d, y = m.sample(p, "ppml", "corn")
    LR, LD = m.index_lags("roni", d.period), m.index_lags("dmi", d.period)
    extra = None if start == "check" else break_dummies(d, "corn", start=start)
    base = base_design(d, m.CONTROLS, extra, spec.trend)
    r = estimate(d, y, LR, LD, base, "ppml", spec)
    res, X = r["fit"], r["X"]
    se = pd.Series(res["se"], index=X.columns)
    w = m.weights("corn")
    nat_now, nat_now_se = national_effect(res, X, w, "RP", spec, post=True)
    vi_before = res["params"].get("BRP_R06")
    vi_now = vi_before + res["params"].get("SRP_post", 0.0)
    row = dict(start=start, n=len(d), deviance=r["loss"], theta_R=r["theta_R"], theta_D=r["theta_D"],
               vi_elnino_before_2000=vi_before, vi_elnino_from_2000=vi_now,
               national_elnino_from_2000=nat_now, t_national=nat_now / nat_now_se)
    if "break_r06_corn" in X.columns:
        row["dummy"] = res["params"]["break_r06_corn"]
        row["t_dummy"] = row["dummy"] / se["break_r06_corn"]
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trend", default=SPEC.trend, choices=["region_spline", "region"])
    trend = ap.parse_args().trend
    spec = replace(SPEC, trend=trend)
    sfx = "" if trend == SPEC.trend else "_linear_trend"
    with ProcessPoolExecutor(8) as ex:
        t = pd.DataFrame(list(ex.map(run, [(s_, spec) for s_ in STARTS])))
    full = t[t.start != "check"]
    t["deviance_minus_best"] = t.deviance - full.deviance.min()
    t.loc[t.start == "check", "deviance_minus_best"] = float("nan")  # different sample
    t.assign(trend=trend, status=m.STATUS).round(4).to_csv(TAB / f"corn_break_start_test{sfx}.csv",
                                                           index=False)
    pd.set_option("display.width", 220)
    print(t.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
