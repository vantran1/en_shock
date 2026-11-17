"""1997-98 check of the VR and PF shocks against FAOSTAT national annual production
(methodology v5 Section 3.6: "the 1997-98 episode is checked against the national annual
production data of FAOSTAT ... by verifying that the quarterly shocks add up to sensible
annual losses"). PROVISIONAL; a check, not a result.

Data: FAOSTAT Production_Crops_Livestock, Asia bulk file (data/faostat/, downloaded from
https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Asia.zip on 17 Nov
2026; release of 23 Dec 2025), Philippines, production (t), official figures (flag A) for
all items used in 1994-2001.

FAOSTAT items for the 13 PSA crops of the indices:
- VR: cassava (125), sweet potatoes (122), potatoes (116), cabbages (358), eggplants (399),
  tomatoes (388), onions dry (403); mung bean -> "Beans, dry" (176, proxy); bitter gourd has
  no item and is left out (negligible in kcal).
- PF: bananas (486; one series until 2014, cooking bananas separate from 2015), pineapples
  (574), mangoes (571), calamansi -> "Other citrus fruit, n.e.c." (512, proxy).
Calories: FNRI factors as in the indices (data/agriculture/fnri_calorie_factors.csv);
bananas at the average of the PSA varieties weighted by their 2010-2012 national production.

Observed: deviation of the 1998 calorie index (and of 1997) from a log-linear trend fitted on
1990-2005 without 1997-1999, %. Model: the shock of the replayed 1997-98 path in calendar
1998 (and 1997), as a share of the year's production: the mean of the quarterly shocks
scaled for DEFINE-PH (Eq. 13b), from outputs/tables/shocks_{vr,pf}.csv (RONI only), with
the 5-95% range of the bootstrap draws. The model replays the path under today's conditions
(today's crop mix and regions), so the comparison is about orders of magnitude, not a test.

Source check: in 2010-2024, the years both cover, FAOSTAT is compared item by item with PSA's
national production (data/processed/crop_region_quarter.csv): every item, the two proxies
included, equals PSA (ratio 1.000; mango 1.02, since the item includes guavas and
mangosteens), and all figures are flagged official. FAOSTAT passes on PSA's figures.

Run:  python scripts/check_faostat_vrpf.py
Writes outputs/tables/faostat_check_vrpf.csv, outputs/tables/faostat_vrpf_annual.csv,
outputs/tables/faostat_vs_psa_2010_2024.csv
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from agriculture.calories import factors  # noqa: E402

FAO = ROOT / "data/faostat/Production_Crops_Livestock_E_Asia.zip"
TAB = ROOT / "outputs/tables"
PROC = ROOT / "data/processed"
# FAOSTAT item code -> (index, PSA commodity whose calorie factor is used)
ITEMS = {125: ("vr", "Cassava, fresh tubers"), 122: ("vr", "Camote [Sweet potato]"),
         116: ("vr", "Potato"), 358: ("vr", "Cabbage"), 399: ("vr", "Eggplant"),
         388: ("vr", "Tomato"), 403: ("vr", "Onion, mature bulb"), 176: ("vr", "Mongo [Mungbean]"),
         486: ("pf", "bananas"), 574: ("pf", "Pineapple"), 571: ("pf", "Mango"),
         512: ("pf", "Calamansi")}
ROOT_ITEMS = {125, 122}
YEARS = range(1990, 2006)
EXCLUDE = (1997, 1998, 1999)


def banana_kcal(f):
    """kcal/kg of bananas: PSA varieties weighted by 2010-2012 national production."""
    c = pd.read_csv(PROC / "crop_region_quarter.csv")
    c = c[(c.series.str.startswith("banana_")) & (c.variable == "production_t")
          & c.period.str[:4].astype(int).between(2010, 2012)]
    w = c.groupby("series").value.sum()
    k = f.loc[f.index.str.startswith("Banana"), "kcal_per_kg"]
    k.index = k.index.str.lower().str.replace(" ", "_")
    return float((w * k.reindex(w.index)).sum() / w.sum())


def fao_annual():
    z = zipfile.ZipFile(FAO)
    d = pd.read_csv(z.open("Production_Crops_Livestock_E_Asia.csv"), encoding="latin-1")
    d = d[(d.Area == "Philippines") & (d.Element == "Production") & d["Item Code"].isin(ITEMS)]
    ycols = [f"Y{y}" for y in YEARS]
    flags = d[[f"{c}F" for c in ycols]]
    if (flags != "A").to_numpy().any():
        print("note: some values are not official figures:\n", d.loc[(flags != "A").any(axis=1), "Item"].tolist())
    long = d.melt(id_vars=["Item Code", "Item"], value_vars=ycols, var_name="year", value_name="t")
    long["year"] = long.year.str[1:].astype(int)
    return long


# FAOSTAT item -> PSA series of data/processed/crop_region_quarter.csv (summed), for the
# comparison in the years both cover; bananas: FAOSTAT splits off "Plantains and cooking
# bananas" (489) from 2015, so 486 + 489 is compared with all PSA varieties
PSA_MATCH = {176: ["mongo_mungbean"], 512: ["calamansi"], 571: ["mango"], 574: ["pineapple"],
             125: ["cassava_fresh_tubers"], 122: ["camote_sweet_potato"], 116: ["potato"],
             358: ["cabbage"], 399: ["eggplant"], 388: ["tomato"], 403: ["onion_mature_bulb"],
             486: "banana_all"}
OVERLAP = range(2010, 2025)


def fao_vs_psa():
    """FAOSTAT / PSA national production by item and year, 2010-2024: does FAOSTAT pass on
    PSA's figures, and are the two proxies (mung bean, calamansi) the same series?"""
    z = zipfile.ZipFile(FAO)
    d = pd.read_csv(z.open("Production_Crops_Livestock_E_Asia.csv"), encoding="latin-1")
    d = d[(d.Area == "Philippines") & (d.Element == "Production")]
    c = pd.read_csv(PROC / "crop_region_quarter.csv")
    c = c[(c.variable == "production_t") & (c.period.str[:4].astype(int).isin(OVERLAP))]
    psa = c.groupby(["series", c.period.str[:4].astype(int)]).value.sum().unstack(0)
    psa["banana_all"] = psa[[x for x in psa if x.startswith("banana_")]].sum(axis=1)
    rows = []
    for code, ps in PSA_MATCH.items():
        r = d[d["Item Code"] == code]
        fao = pd.Series({y: r[f"Y{y}"].iloc[0] for y in OVERLAP})
        if code == 486:  # add cooking bananas, reported separately from 2015
            pl = d[d["Item Code"] == 489]
            fao = fao + pd.Series({y: pl[f"Y{y}"].iloc[0] for y in OVERLAP}).fillna(0)
        p = psa[ps] if isinstance(ps, str) else psa[ps].sum(axis=1)
        ratio = fao / p.reindex(OVERLAP)
        flags = sorted(set(r[[f"Y{y}F" for y in OVERLAP]].iloc[0].astype(str)))
        rows.append({"fao_item": r.Item.iloc[0] + (" + plantains and cooking bananas" if code == 486 else ""),
                     "psa_series": ps if isinstance(ps, str) else "+".join(ps),
                     "ratio_min": ratio.min(), "ratio_max": ratio.max(), "flags": "".join(flags)})
    return pd.DataFrame(rows)


def model_year(crop, year):
    """Shock of the replayed 1997-98 path in a calendar year: mean of S_D over its quarters
    (central and bootstrap 5-95%), % of the year's production."""
    s = pd.read_csv(TAB / f"shocks_{crop}.csv")
    s = s[(s.path == "1997-98") & (s.crop == crop) & s.scenario_q.str.startswith(str(year))]
    b = pd.read_csv(TAB / f"shocks_{crop}_bootstrap.csv")
    b = b[(b.path == "1997-98") & (b.crop == crop) & b.scenario_q.astype(str).str.startswith(str(year))]
    # quarters of the year outside the path and its aftermath have no shock (S_D = 0)
    cen = s.S_D.sum() / 4 * 100
    draws = b.groupby("rep").S_D.sum() / 4 * 100
    return cen, draws.quantile(0.05), draws.quantile(0.95)


def main():
    f = factors()
    kcal = {name: f.loc[name, "kcal_per_kg"] for _, name in ITEMS.values() if name != "bananas"}
    kcal["bananas"] = banana_kcal(f)
    a = fao_annual()
    a["index"] = a["Item Code"].map(lambda c: ITEMS[c][0])
    a["kcal_per_kg"] = a["Item Code"].map(lambda c: kcal[ITEMS[c][1]])
    a["bkcal"] = a.t * a.kcal_per_kg * 1e-6
    a.round(3).to_csv(TAB / "faostat_vrpf_annual.csv", index=False)

    series = {"vr": a[a["index"] == "vr"], "vr_noroot": a[(a["index"] == "vr") & ~a["Item Code"].isin(ROOT_ITEMS)],
              "pf": a[a["index"] == "pf"], "pf_nobanana": a[(a["index"] == "pf") & (a["Item Code"] != 486)]}
    rows = []
    for name, x in series.items():
        e = x.groupby("year").bkcal.sum()
        fit = e[~e.index.isin(EXCLUDE)]
        b = np.polyfit(fit.index, np.log(fit.values), 1)
        dev = (np.log(e) - np.polyval(b, e.index)) * 100
        resid_sd = float(dev[~dev.index.isin(EXCLUDE)].std(ddof=2))
        r = {"series": name, "obs_dev_1997_pct": dev[1997], "obs_dev_1998_pct": dev[1998],
             "obs_dev_1999_pct": dev[1999], "trend_resid_sd_pct": resid_sd,
             "obs_1998_vs_1996_97_pct": (e[1998] / e[[1996, 1997]].mean() - 1) * 100}
        if name in ("vr", "pf"):
            for y in (1997, 1998):
                c, lo, hi = model_year(name, y)
                r[f"model_loss_{y}_pct"], r[f"model_{y}_p05"], r[f"model_{y}_p95"] = c, lo, hi
        rows.append(r)
    t = pd.DataFrame(rows)
    t.assign(status="provisional").round(2).to_csv(TAB / "faostat_check_vrpf.csv", index=False)
    pd.set_option("display.width", 250)
    print("Observed: deviation from the 1990-2005 log-linear trend (without 1997-99), %; "
          "a loss is a negative deviation.\nModel: loss in the calendar year from the replayed "
          "1997-98 path, % (RONI only).")
    print(t.round(1).to_string(index=False))
    cmp = fao_vs_psa()
    cmp.assign(status="provisional").round(4).to_csv(TAB / "faostat_vs_psa_2010_2024.csv", index=False)
    print("\nFAOSTAT / PSA national production, 2010-2024 (1 = identical):\n",
          cmp.round(3).to_string(index=False))
    crops = a[a.year.isin([1996, 1997, 1998, 1999])].pivot_table(index="Item", columns="year", values="t")
    crops["1998 vs 1996-97, %"] = (crops[1998] / crops[[1996, 1997]].mean(axis=1) - 1) * 100
    print("\nCrops (t):\n", crops.round(1).to_string())


if __name__ == "__main__":
    main()
