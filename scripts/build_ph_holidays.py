"""Philippine national public holidays 2013-2026 from the Python `holidays` package (country PH),
for the public-holiday indicator of the electricity price and demand equations (methodology v5,
Eqs. 5 and 7). No manual additions.

The package has two categories for the Philippines: 'public' (regular holidays and special
non-working days together) and 'workday' (special working days, excluded here). It does not
label regular versus special, so `type` is set from the names: the regular holidays fixed by law
(Administrative Code as amended by RA 9492 and RA 9849: New Year's Day, Maundy Thursday, Good
Friday, Day of Valor, Labor Day, Independence Day, National Heroes Day, Bonifacio Day, Christmas
Day, Rizal Day, Eid al-Fitr, Eid al-Adha) are 'regular'; every other public holiday is
'special_non_working'. A date carrying two holidays (e.g. "Day of Valor; Maundy Thursday") is
regular if any of them is.

Checked against the proclamations (base proclamation for the year plus the later ones: election
days, Eid'l Fitr, Eid'l Adha, added special days; LawPhil yearly indexes of proclamations, keeping
only those that apply throughout the country) for 2013-2020 and 2024; not checked for 2021-2023
and 2025-2026. The corrections are the OVERRIDES below, applied after the package; a date for
which no proclamation could be found would be kept at the package's date and flagged
verified=False (none so far).

Run:  python scripts/build_ph_holidays.py
Writes data/electricity/ph_holidays_2013_2026.csv (date, name, type)
"""
from pathlib import Path

import holidays
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/electricity/ph_holidays_2013_2026.csv"
YEARS = range(2013, 2027)
REGULAR = {"New Year's Day", "Maundy Thursday", "Good Friday", "Day of Valor", "Labor Day",
           "Independence Day", "National Heroes Day", "Bonifacio Day", "Christmas Day",
           "Rizal Day", "Eid al-Fitr", "Eid al-Adha"}


# ---------------------------------------------------------------------------------------------
# OVERRIDES: corrections to the package, from the proclamations (LawPhil, checked 19 Nov 2026).
# action: add (date missing from the package), drop (date in the package but in no national
# proclamation), move (package date `from_date` -> proclaimed `date`).
# ---------------------------------------------------------------------------------------------
OVERRIDES = [
    dict(action="drop", date="2013-02-10", name="Chinese New Year", type="special_non_working",
         source="Not in Proc. 459 s.2012 (holidays for 2013); no national proclamation in the "
                "LawPhil 2012-2013 indexes", verified=True),
    dict(action="add", date="2013-05-13", name="Elections special (non-working) day",
         type="special_non_working", source="Proc. 571 s.2013 (national and local elections)", verified=True),
    dict(action="add", date="2013-10-28", name="Barangay elections special (non-working) day",
         type="special_non_working", source="Proc. 656 s.2013", verified=True),
    dict(action="add", date="2016-05-09", name="Elections special (non-working) day",
         type="special_non_working", source="Proc. 1254 s.2016 (national and local elections)", verified=True),
    dict(action="move", from_date="2016-07-07", date="2016-07-06", name="Eid al-Fitr", type="regular",
         source="Proc. 6 s.2016", verified=True),
    dict(action="move", from_date="2016-09-10", date="2016-09-12", name="Eid al-Adha", type="regular",
         source="Proc. 56 s.2016", verified=True),
    dict(action="add", date="2016-12-26", name="Additional special (non-working) day",
         type="special_non_working", source="Proc. 117 s.2016", verified=True),
    dict(action="add", date="2017-02-25", name="EDSA People Power Revolution Anniversary",
         type="special_non_working", source="Proc. 50 s.2016 (holidays for 2017)", verified=True),
    dict(action="move", from_date="2017-09-02", date="2017-09-01", name="Eid al-Adha", type="regular",
         source="Proc. 297 s.2017", verified=True),
]


def apply_overrides(d):
    for o in OVERRIDES:
        if o["action"] in ("drop", "move"):
            old = o["date"] if o["action"] == "drop" else o["from_date"]
            if old not in set(d.date):
                raise ValueError(f"override {o}: {old} is not in the package list")
            d = d[d.date != old]
        if o["action"] in ("add", "move"):
            if o["date"] in set(d.date):
                raise ValueError(f"override {o}: {o['date']} is already in the list")
            d = pd.concat([d, pd.DataFrame([{k: o[k] for k in ("date", "name", "type")}])])
    return d.sort_values("date").reset_index(drop=True)


def kind(name):
    parts = [p.strip() for p in name.split(";")]
    return "regular" if any(p in REGULAR for p in parts) else "special_non_working"


def main():
    h = holidays.country_holidays("PH", years=YEARS, categories=("public",))
    d = pd.DataFrame(sorted(h.items()), columns=["date", "name"])
    d["type"] = d["name"].map(kind)
    d["date"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d")
    d = apply_overrides(d)
    if d.date.duplicated().any():
        raise ValueError("duplicated dates")
    d.to_csv(OUT, index=False)
    print(f"holidays {holidays.__version__}: {len(d)} dates, "
          f"{(d.type == 'regular').sum()} regular, {(d.type != 'regular').sum()} special non-working -> {OUT}")
    print(f"overrides applied: {len(OVERRIDES)}; unverified: {sum(not o['verified'] for o in OVERRIDES)}")


if __name__ == "__main__":
    main()
