"""RONI and DMI parts of the direct-approach shocks (central estimate, no bootstrap), for
the episode paths of scripts/shocks_direct.py. PROVISIONAL; a diagnostic for the DMI
question (write-up section 4), not a deliverable.

For each crop's recommended specification with the DMI (the variant; Poisson, full sample), the shock of each path is
computed three times: with the path's RONI and DMI (the shock of shocks_direct.py), with the
DMI set to zero (RONI part) and with RONI set to zero (DMI part). The shock is 1 - exp(sum
of the climate terms), so the two parts add up to the total only approximately.
This is not the shock of a model estimated without the DMI (that model has a different
RONI effect, Table 8 of the write-up); it shows how much of each episode's shock the
estimated DMI effect contributes.

Run:  python scripts/shocks_decompose.py
Writes outputs/tables/shocks_decomposition.csv (total loss over the path and the quarters
after it, % of one year's neutral production, by crop, series, path and part)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd  # noqa: E402

import shocks_direct as sd  # noqa: E402
from estimation.direct import THETA_GRID  # noqa: E402

TAB = ROOT / "outputs/tables"


def main():
    rows = []
    base = {k: v for k, v in sd.paths().items() if not k.startswith("unit")}
    parts = {"RONI and DMI": base,
             "RONI only (DMI = 0)": {k: v.assign(dmi=0.0) for k, v in base.items()},
             "DMI only (RONI = 0)": {k: v.assign(roni=0.0) for k, v in base.items()}}
    for crop, conf in sd.CONF.items():
        spec = sd.m.with_dmi(sd.m.RECOMMENDED_BY_CROP[crop])  # the variant with the DMI
        data = {e: sd.prepare(e, spec) for e in conf["series"]}
        fits = {e: sd.fit_params(*data[e], "ppml", THETA_GRID, spec) for e in conf["series"]}
        for part, ps in parts.items():
            nat, _ = sd.shocks(fits, data, crop, spec, ps)
            tot = nat.groupby(["path", "crop"]).S_D.sum() / 4 * 100
            rows.append(tot.rename("total_loss_pct_of_annual").reset_index().assign(group=crop, part=part))
        print(crop, "done")
    out = pd.concat(rows, ignore_index=True)
    out = out[["group", "crop", "path", "part", "total_loss_pct_of_annual"]]
    out.assign(status="provisional").round(2).to_csv(TAB / "shocks_decomposition.csv", index=False)
    w = out.pivot_table(index=["group", "crop", "path"], columns="part",
                        values="total_loss_pct_of_annual").round(1)
    pd.set_option("display.width", 200)
    print(w[list(parts)].to_string())


if __name__ == "__main__":
    main()
