#!/usr/bin/env python3
"""Which index carries the lagged signal, RONI or DMI? Plain CV of lag sets that lag only one index.

Same machinery and years as analysis/lag_analysis.py. Writes outputs/analysis/lags/mechanism.csv.
  python analysis/lag_mechanism.py
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import config as C  # noqa: E402
from stage1 import engine as E  # noqa: E402
from stage1 import fit as F  # noqa: E402

FIRST_YEAR = 1951
SETS = {                                    # lags of RONI, lags of DMI
    "sync": ((0,), (0,)),
    "sync+lag1": ((0, 1), (0, 1)),
    "sync+lag3": ((0, 3), (0, 3)),
    "RONI lag3 only": ((0, 3), (0,)),
    "DMI lag3 only": ((0,), (0, 3)),
    "sync+lag4": ((0, 4), (0, 4)),
    "RONI lag4 only": ((0, 4), (0,)),
    "DMI lag4 only": ((0,), (0, 4)),
    "sync+lag6": ((0, 6), (0, 6)),
    "RONI lag6 only": ((0, 6), (0,)),
    "DMI lag6 only": ((0,), (0, 6)),
}


def design(P, month, lr, ld):
    cur = P.index[P.index.month == month]
    cols = [P["roni"].shift(L).loc[cur].rename(f"roni_{L}") for L in lr] + \
           [P["dmi"].shift(L).loc[cur].rename(f"dmi_{L}") for L in ld]
    return pd.concat(cols, axis=1).set_axis(cur.year, axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    cfg = C.load(a.config)
    D, variables, _ = F.load_data(cfg, refresh_indices=False)
    rows = []
    for var in variables:
        kind = C.PREDICTANDS[var][3]
        for m in range(1, 13):
            years, Y, _ = D.month_data(var, m)
            keep = years >= FIRST_YEAR
            years, Y = years[keep], Y[keep]
            X = {k: design(D.P, m, lr, ld).reindex(years.astype(int)).to_numpy() for k, (lr, ld) in SETS.items()}
            ok = np.all([np.isfinite(x).all(1) for x in X.values()], axis=0)
            years, Y, X = years[ok], Y[ok], {k: x[ok] for k, x in X.items()}
            cv = E.cv_run([Y], [kind], X, years, D.S)
            _, _, sc = E.select(cv)
            agg = D.aggregator("r16_cropland", var, m)
            for k in SETS:
                g = max((g for g in sc if g[0] == k), key=sc.get)
                o, p = F.regional_cv(agg(Y), agg(E.cv_physical(cv, g, 0)), years, kind, D.S["cv_window"])
                rows.append(dict(var=var, month=m, lagset=k, cells_rho=sc[g],
                                 r16_cropland_rho=float(np.nanmean(E.col_spearman(p, o)))))
        print(f"  {var} done", flush=True)
    out = C.out(cfg, "analysis", "lags", "mechanism.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
