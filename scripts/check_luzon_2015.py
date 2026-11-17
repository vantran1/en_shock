"""Check of the change in 2000 of the El Nino effect on palay against the typhoon rain over
Luzon in October-December 2015 (Lando/Koppu, Nona/Melor; Van, 16 Nov 2026: stage 1 over-
predicts the 2015-16 drying almost only because of Luzon in Oct-Dec 2015). The typhoon
controls measure wind exposure, not rain, so if that rain kept the 2016 dry-season crop
going, the direct approach may read 2015-16 as a smaller El Nino effect after 2000.
PROVISIONAL; a check, not a result.

The recommended rice specification (RONI only) is estimated with and without the change in
2000 on three samples: all quarters; without the Luzon regions (CAR, I, II, III, IV-A,
MIMAROPA, V) in 2015Q4-2016Q2 (the typhoon quarters and the dry-season harvest after them);
without the Luzon regions over the whole episode 2015Q2-2016Q4. Reported: the gain in fit
from the change (deviance + k ln n, same sample), the national El Nino effect before and
from 2000 (dry-season harvest) and the t of the change. If the typhoon rain drove the
change, it should weaken without those quarters.

Run:  python scripts/check_luzon_2015.py
Writes outputs/tables/check_luzon_2015.csv
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

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

TAB = ROOT / "outputs/tables"
LUZON = [r for r, g in ISLAND.items() if g == "Luzon"]
SAMPLES = {"all quarters": None,
           "without Luzon 2015Q4-2016Q2": ("2015Q4", "2016Q2"),
           "without Luzon 2015Q2-2016Q4": ("2015Q2", "2016Q4")}


def run(job):
    eco, sample, brk = job
    spec = m.RECOMMENDED if brk else replace(m.RECOMMENDED, name="no_change", effect_break=None)
    p = m.build(eco)
    d, y = m.sample(p, "ppml", m.GROUP[eco])
    if SAMPLES[sample]:
        a, b = SAMPLES[sample]
        drop = d.region_code.isin(LUZON) & d.period.between(a, b)
        d, y = d[~drop].reset_index(drop=True), y[~drop].reset_index(drop=True)
    LR = m.index_lags("roni", d.period, spec.K, spec.first_lag)
    LD = m.index_lags("dmi", d.period, spec.K, spec.first_lag)
    base = base_design(d, m.CONTROLS, None, spec.trend)
    r = estimate(d, y, LR, LD, base, "ppml", spec)
    w = m.weights(eco)
    before, se_b = national_effect(r["fit"], r["X"], w, "RP", spec)
    out = dict(series=eco, sample=sample, change_2000=brk, n=len(d),
               ic=r["loss"] + r["k"] * np.log(len(d)), el_nino_effect=before, t_effect=before / se_b)
    if brk:
        after, _ = national_effect(r["fit"], r["X"], w, "RP", spec, post=True)
        c = "SRP_post"
        sh = r["fit"]["params"][c]
        out.update(el_nino_from_2000=after, shift=sh,
                   t_shift=sh / r["fit"]["se"][r["X"].columns.get_loc(c)])
    return out


def main():
    jobs = [(e, s, b) for e in ("irrigated", "rainfed") for s in SAMPLES for b in (False, True)]
    with ProcessPoolExecutor(6) as ex:
        t = pd.DataFrame(list(ex.map(run, jobs)))
    no = t[~t.change_2000].set_index(["series", "sample"])
    yes = t[t.change_2000].set_index(["series", "sample"])
    out = pd.DataFrame({"fit_gain_from_change": no.ic - yes.ic,
                        "effect_before_2000": yes.el_nino_effect, "effect_from_2000": yes.el_nino_from_2000,
                        "t_change": yes.t_shift, "effect_without_change": no.el_nino_effect,
                        "n": yes.n}).reset_index()
    out.assign(status="provisional").round(4).to_csv(TAB / "check_luzon_2015.csv", index=False)
    pd.set_option("display.width", 220)
    print("El Nino effect on palay, dry-season harvest, log points per +1 C sustained (Poisson, RONI only);")
    print("fit gain from the change in 2000 (positive = the change fits better).")
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
