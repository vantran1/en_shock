"""Does the change in 2000 of the El Nino effect on palay survive a control for typhoon rainfall?

Alper (27 Nov 2026): keep the rice upper bound (estimate without the Luzon quarters of late 2015,
scripts/check_luzon_2015.py, write-up Table 4a) and, as an alternative to dropping those quarters,
test a control for typhoon rainfall. The wind-exposure controls do not measure rain; the typhoon
rain over Luzon in Oct-Dec 2015 made the 2016 dry-season drought milder than its RONI implies.

The recommended rice specification (RONI only) is estimated with and without the change in 2000:
- current:            the controls of the direct approach (wind exposure, floods, geophysical);
- typhoon rain:       + typhoon rain in the quarter and the previous quarter (100 mm units;
                        data/processed/typhoon_rain_region_quarter.csv, scripts/build_typhoon_rain.py);
- typhoon rain share: + the share of the quarter's rain from cyclones, same lags (sensitivity);
- without Luzon:      current controls, Luzon regions dropped in 2015Q4-2016Q2 (the upper bound).
All variants use the same quarters (those with the typhoon rain series). Reported: the gain in fit
from the change, the national El Nino effect before and from 2000 (dry-season harvest), the t of the
change, and the typhoon-rain coefficients. If the 2015 rain drove the change, it should weaken with
the control, as it does without the Luzon quarters.

Caution: El Nino itself changes typhoons (fewer, tracks shifted), so holding typhoon rain fixed
removes part of the true El Nino effect (the reason v5 keeps hazard controls out of Stage 1). The
test says whether the 2015 rain explains the change in 2000; it is not by itself a better central
estimate. PROVISIONAL; a check, not a result.

Run:  python scripts/check_typhoon_rain.py [--tc-file <csv>] [--out <csv>]
Writes outputs/tables/check_typhoon_rain.csv
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
from estimation.direct import ISLAND, base_design, estimate, national_effect  # noqa: E402

PROC, TAB = ROOT / "data/processed", ROOT / "outputs/tables"
LUZON = [r for r, g in ISLAND.items() if g == "Luzon"]
RAIN = ["tc_rain_100mm", "tc_rain_100mm_lag1"]
SHARE = ["tc_rain_share", "tc_rain_share_lag1"]
VARIANTS = {"current": ([], None), "typhoon rain": (RAIN, None), "typhoon rain share": (SHARE, None),
            "without Luzon 2015Q4-2016Q2": ([], ("2015Q4", "2016Q2"))}


def panel(eco, tc_file):
    tc = pd.read_csv(tc_file)
    tc = tc.assign(tc_rain_100mm=tc.tc_rain_mm / 100, tc_rain_100mm_lag1=tc.tc_rain_mm_lag1 / 100)
    p = m.build(eco).merge(tc[["region_code", "period"] + RAIN + SHARE], on=["region_code", "period"],
                           how="left", validate="1:1")
    return p.dropna(subset=RAIN + SHARE).reset_index(drop=True)  # same quarters in every variant


def run(job):
    eco, variant, brk, tc_file = job
    extra, drop_q = VARIANTS[variant]
    spec = m.RECOMMENDED if brk else replace(m.RECOMMENDED, name="no_change", effect_break=None)
    d, y = m.sample(panel(eco, tc_file), "ppml", m.GROUP[eco])
    if drop_q:
        drop = d.region_code.isin(LUZON) & d.period.between(*drop_q)
        d, y = d[~drop].reset_index(drop=True), y[~drop].reset_index(drop=True)
    LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
    LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
    base = base_design(d, m.CONTROLS + extra, None, spec.trend)
    r = estimate(d, y, LR, LD, base, "ppml", spec)
    w = m.weights(eco)
    before, se_b = national_effect(r["fit"], r["X"], w, "RP", spec)
    out = dict(series=eco, variant=variant, change_2000=brk, n=len(d),
               ic=r["loss"] + r["k"] * np.log(len(d)), el_nino_effect=before, t_effect=before / se_b)
    for c in extra:
        i = r["X"].columns.get_loc(c)
        out[f"coef_{c.replace('tc_rain_100mm', 'rain').replace('tc_rain_share', 'share')}"] = r["fit"]["params"][c]
        out[f"t_{c.replace('tc_rain_100mm', 'rain').replace('tc_rain_share', 'share')}"] = (
            r["fit"]["params"][c] / r["fit"]["se"][i])
    if brk:
        after, _ = national_effect(r["fit"], r["X"], w, "RP", spec, post=True)
        c = "SRP_post"
        sh = r["fit"]["params"][c]
        out.update(el_nino_from_2000=after, shift=sh,
                   t_shift=sh / r["fit"]["se"][r["X"].columns.get_loc(c)])
    return out


def main(tc_file=PROC / "typhoon_rain_region_quarter.csv", out_file=TAB / "check_typhoon_rain.csv"):
    jobs = [(e, v, b, tc_file) for e in ("irrigated", "rainfed") for v in VARIANTS for b in (False, True)]
    with ProcessPoolExecutor(6) as ex:
        t = pd.DataFrame(list(ex.map(run, jobs)))
    no = t[~t.change_2000].set_index(["series", "variant"])
    yes = t[t.change_2000].set_index(["series", "variant"])
    coefs = yes.filter(regex="^(coef|t)_(rain|share)")
    out = pd.DataFrame({"fit_gain_from_change": no.ic - yes.ic,
                        "effect_before_2000": yes.el_nino_effect, "effect_from_2000": yes.el_nino_from_2000,
                        "t_change": yes.t_shift, "effect_without_change": no.el_nino_effect,
                        "n": yes.n}).join(coefs).reset_index()
    out.assign(status="provisional").round(4).to_csv(out_file, index=False)
    pd.set_option("display.width", 240)
    print("El Nino effect on palay, dry-season harvest, log points per +1 C sustained (Poisson, RONI only);")
    print("fit gain from the change in 2000 (positive = the change fits better).")
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tc-file", default=str(PROC / "typhoon_rain_region_quarter.csv"))
    ap.add_argument("--out", default=str(TAB / "check_typhoon_rain.csv"))
    a = ap.parse_args()
    main(a.tc_file, a.out)
