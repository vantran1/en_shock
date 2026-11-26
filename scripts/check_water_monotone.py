"""Check of the water constraint in the Stage 2 boosting (26 Nov 2026): out-of-sample skill with
rainfall, runoff and heavy-rain days constrained so that more water never lowers production
(estimation.stage2.MONOTONE) against the earlier version with them free (MONOTONE_WATER_FREE).
Why the constraint: left free, the boosting counts El Nino's drier seasons as a gain from fewer
floods, which belongs to the CAT channel (see the note at MONOTONE). A diagnostic.

Models: the chain's boosting models, response changing from 2000 (full 30 features for irrigated
and rainfed palay, compact 9 features for corn; also the other feature set for each series), on the
folds of scripts/select_stage2.py (eight 5-year blocks, three episodes).

Run:  python scripts/check_water_monotone.py [--workers 8]
Writes outputs/tables/stage2_water_monotone.csv, outputs/stage2_water_monotone.md
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import argparse  # noqa: E402
import sys  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from estimate_stage2 import BLOCKS, EPISODES, SERIES, base_design, held_mask, md, panel  # noqa: E402
from estimation.stage2 import (FEATURES, MONOTONE, MONOTONE_WATER_FREE, fit_base, fit_gbm,  # noqa: E402
                               poisson_deviance, predict_gbm)
from select_stage2 import COMPACT  # noqa: E402

TAB, OUT = ROOT / "outputs/tables", ROOT / "outputs"
SETS = {"full (30)": FEATURES, "compact (9)": COMPACT}
CONS = {"water free": MONOTONE_WATER_FREE, "water constrained": MONOTONE}


def run(job):
    series, kind, fold, a, z = job
    d, y = panel(series)
    held = held_mask(d, a, z)
    train = ~held
    base = base_design(d, train, series)
    p = fit_base(y, base, train)
    mu0 = np.exp(base[p.index].to_numpy(float) @ p.to_numpy())
    rows = []
    for sname, feats in SETS.items():
        for cname, cons in CONS.items():
            r = fit_gbm(d, y, base, feats + ["post2000"], train, constraints=cons)
            mu = predict_gbm(r, d, base)
            rows.append({"series": series, "fold_type": kind, "fold": fold, "features": sname,
                         "constraint": cname, "deviance": poisson_deviance(y[held], mu[held]),
                         "base_deviance": poisson_deviance(y[held], mu0[held])})
    print(f"{series} {kind} {fold}: done", flush=True)
    return rows


def main(workers=8):
    jobs = ([(s, "block", k, a, z) for s in SERIES for k, (a, z) in BLOCKS.items()]
            + [(s, "episode", k, a, z) for s in SERIES for k, (a, z) in EPISODES.items()])
    with ProcessPoolExecutor(workers) as ex:
        rows = pd.DataFrame([r for x in ex.map(run, jobs) for r in x])
    rows.round(5).to_csv(TAB / "stage2_water_monotone.csv", index=False)
    g = rows.groupby(["series", "features", "constraint", "fold_type"])[["deviance", "base_deviance"]].sum()
    g["skill_pct"] = (1 - g.deviance / g.base_deviance) * 100
    t = g.skill_pct.unstack(["fold_type"]).reset_index()
    s = ["# Stage 2 boosting: water variables free vs constrained (out-of-sample skill, %)\n",
         "Response changing from 2000; skill = % of the no-weather deviance removed on held-out quarters.\n",
         md(t, "{:.1f}")]
    (OUT / "stage2_water_monotone.md").write_text("\n".join(s) + "\n")
    print("\n".join(s))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    main(ap.parse_args().workers)
