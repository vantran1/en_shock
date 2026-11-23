#!/usr/bin/env python3
"""Draft of Table 2a of the labour note: the outdoor share of each services group, from the occupation mix of
PSA Table 11.8 and stated assumptions on which occupations work outdoors.

    outdoor share of a group = sum over occupations of (share of the occupation in the group)
                               x (assumed share of that occupation working outdoors)

The occupation groups are too broad to identify outdoor jobs directly (the note says so), so the numbers in
OUTDOOR below are ASSUMPTIONS to be reviewed, not data. Edit them here and re-run, or edit the CSV directly.

  python scripts/helpers/analysis/draft_services_table.py            # writes data/labour/services_assumptions.csv
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import labour as L  # noqa: E402

# assumed share working outdoors, by occupation: default, then what differs in a group
DEFAULT = dict(managers=0.0, professionals=0.0, technicians=0.0, clerical=0.0, service_sales=0.10,
               skilled_agricultural=1.0, craft=0.50, operators=0.50, elementary=0.25, armed_forces=0.50)
OUTDOOR = {
    "trade": dict(service_sales=0.25, elementary=0.50),          # street and market vendors; hawkers, porters
    "transport": dict(operators=1.00, elementary=0.75),          # drivers of jeepneys, tricycles, motorcycles; porters
    "accommodation": dict(service_sales=0.10),                   # street food vendors
    "admin_support": dict(service_sales=0.50),                   # security guards
    "public_admin": dict(service_sales=0.50, elementary=0.50),   # police, traffic and barangay staff; street sweepers
    "other_services": dict(craft=0.25),
}
INTENSITY = dict(trade="moderate", transport="moderate", accommodation="moderate", information="light", finance="light",
                 real_estate="light", professional="light", admin_support="moderate", public_admin="light",
                 education="light", health="moderate", arts="moderate", other_services="moderate", households="moderate",
                 extraterritorial="light")
AIRCON = dict(information=1.0, finance=1.0)                      # the note's central case: only these two groups
RANGE = dict(trade=(0.5, 1.5), transport=(0.5, 1.5))             # low and high outdoor share, as multiples of central
LABEL = dict(trade="Wholesale and retail trade", transport="Transportation and storage",
             accommodation="Accommodation and food service", information="Information and communication",
             finance="Financial and insurance activities", real_estate="Real estate activities",
             professional="Professional, scientific and technical activities",
             admin_support="Administrative and support service activities",
             public_admin="Public administration and defence", education="Education",
             health="Human health and social work", arts="Arts, entertainment and recreation",
             other_services="Other service activities", households="Activities of households as employers",
             extraterritorial="Extraterritorial organizations")


def main():
    cfg = C.load()
    occ, year = L.read_occupations(C.path(cfg, "labour_dir") / cfg["labour"]["occupation_table"], cfg["labour"].get("occupation_year", "latest"))
    rows = []
    for k in L.SERVICE_KEYS:
        p = {**DEFAULT, **OUTDOOR.get(k, {})}
        tot = occ.loc[k, L.OCCUPATIONS].sum()
        share = occ.loc[k, L.OCCUPATIONS] / tot if tot > 0 else occ.loc[k, L.OCCUPATIONS] * 0
        o = float(sum(share[c] * p[c] for c in L.OCCUPATIONS))
        lo, hi = RANGE.get(k, (1.0, 1.0))
        main_occ = share.sort_values(ascending=False).head(3)
        basis = "; ".join(f"{c} {100 * s:.0f}% (outdoors {100 * p[c]:.0f}%)" for c, s in main_occ.items())
        rows.append(dict(group=k, psic_major_group=LABEL[k], employment_thousand=round(float(occ.loc[k, "all"]), 1),
                         outdoor_share=round(o, 3), outdoor_share_low=round(o * lo, 3), outdoor_share_high=round(min(1.0, o * hi), 3),
                         aircon_share=AIRCON.get(k, 0.0), intensity=INTENSITY[k],
                         basis=f"ASSUMPTION from PSA Table 11.8 ({year}): {basis}" if tot > 0 else "ASSUMPTION; no employment recorded"))
    out = C.path(cfg, "labour_dir") / "services_assumptions.csv"
    head = ("# Table 2a of the labour note. DRAFT ASSUMPTIONS, to be reviewed: outdoor_share is the share of the group's workers\n"
            "# who work outdoors (in the sun); aircon_share is the share of its INDOOR workers in air-conditioned workplaces\n"
            "# (no heat loss); intensity is the Hothaps curve (heavy, moderate, light). outdoor_share_low/high are used in the\n"
            "# sensitivity cases. Made by scripts/helpers/analysis/draft_services_table.py; the pipeline reads only this file, so edit it freely.\n")
    out.write_text(head + pd.DataFrame(rows).to_csv(index=False))
    print(pd.DataFrame(rows).drop(columns="basis").to_string(index=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
