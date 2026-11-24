"""National typhoon and flood exposure by quarter, for the food price equation (price note in
methodology v5, Section 3.1, Eq. 3: "the typhoon and flood exposure controls of the agricultural
note"). Requested by Van (24 Nov 2026), who estimates Eq. 3.

Same measures as the regional controls of the direct approach (scripts/build_typhoon_exposure.py,
scripts/build_flood_exposure.py), each with its previous quarter:
- ty_share_ts / ty_share_ty / ty_share_sty: share of the country (weighted) with winds of at least
  tropical-storm / typhoon / super-typhoon strength in the quarter (PAGASA categories, 10-min
  sustained; cumulative, so ts >= ty >= sty);
- flood_share: share of the country (weighted) in provinces hit by at least one EM-DAT flood event.
A province's exposure is computed exactly as for the regional controls; the national value is the
weighted sum over provinces, with fixed weights:
- palay (rice equation): each province's share of national palay production, 2016-2025. This is
  the regional control for total palay averaged with the regions' 2016-2025 palay shares (checked).
- food (food equation, main): each province's share of national food calories, 2016-2025, from
  palay, corn, VR and PF. VR and PF in kcal as in the direct approach (FNRI factors). Corn: 3,570
  kcal/kg, PROVISIONAL (FNRI A001, as in scripts/deliver_food_shocks.py). Palay: PROVISIONAL
  3,600 kcal/kg of milled rice x 0.63 kg of milled rice per kg of palay (PSA milling recovery
  rate from January 2025, per a USDA FAS report; 0.654 before) = 2,268 kcal/kg. The 3,600 is a
  placeholder for raw milled rice with no document behind it; the FNRI value for well-milled rice
  (A019) is to be confirmed (data/TO_VERIFY.md). The sensitivity to the palay factor is reported.
- population (food equation, check): each province's share of the 2020 population (WorldPop,
  data/population/), INCLUDING Metro Manila, which the agricultural controls leave out (no
  production): its boundary units are added as one unit for the typhoon exposure, and EM-DAT
  locations naming Metro Manila are placed in it (they are dropped in the agricultural controls).
Population is fixed at 2020, as production weights are fixed at 2016-2025, so that a control does
not move with what it is meant to explain.

For the shocks, the controls are set to "no event" (zero) in both the El Nino and the neutral run.

Run:  python scripts/build_national_hazard_controls.py   (needs data/hazards/ibtracs/ and
      data/hazards/emdat/, which are not in git: scripts/download_hazards.py, EM-DAT by hand)
Writes data/processed/hazard_national_quarter.csv           weighting x quarter, 1987Q1-2025Q4
       data/processed/hazard_national_weights.csv           province weights of the three versions
       outputs/tables/hazard_national_checks.csv            checks (see main)
       outputs/figures/hazard_national_quarter.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio.mask import mask  # noqa: E402

from agriculture.psa_openstat import read_palay_corn  # noqa: E402
from agriculture.regions import assign_region  # noqa: E402
from hazards import floods  # noqa: E402
from hazards.typhoon import (CATEGORIES, DATA, POLYGON_MERGE, PSA_TO_POLYGON,  # noqa: E402
                             category_exposure, grid_points, load_tracks,
                             storm_province_exposure)
from hazards.weights import vr_pf_production  # noqa: E402

PROC, TAB, FIG = ROOT / "data/processed", ROOT / "outputs/tables", ROOT / "outputs/figures"
POP = ROOT / "data/population/phl_ppp_2020_1km_Aggregated_UNadj.tif"
NCR = "Metro Manila"
YEARS = (2016, 2025)
START, END = pd.Period("1986Q4", "Q"), pd.Period("2025Q4", "Q")
CORN_KCAL_PER_KG = 3570.0                 # provisional (scripts/deliver_food_shocks.py)
RICE_KCAL_PER_KG = 3600.0                 # provisional, milled rice; FNRI A019 to confirm
MILLING_RECOVERY = 0.63                   # PSA, from January 2025 (0.654 before)
PALAY_KCAL_PER_KG = RICE_KCAL_PER_KG * MILLING_RECOVERY
TY = [f"ty_share_{c}" for c in CATEGORIES]
MEASURES = TY + ["flood_share"]
NCR_NAMES = {"metropolitan manila", "metro manila", "metro manilla", "manila", "manilla",
             "national capital region", "ncr", "national capital region (ncr)"}


def provinces() -> gpd.GeoDataFrame:
    """The province units of the agricultural controls plus Metro Manila as one unit."""
    g = gpd.read_file(DATA / "boundaries" / "geoBoundaries-PHL-ADM2_simplified.geojson")
    g["polygon"] = np.where(g.shapeName.str.startswith("NCR"), NCR, g.shapeName.replace(POLYGON_MERGE))
    return g.dissolve("polygon").reset_index()[["polygon", "geometry"]]


def population(prov) -> pd.Series:
    """2020 population of each unit (sum of the WorldPop cells inside it)."""
    with rasterio.open(POP) as r:
        out = {}
        for name, geom in zip(prov.polygon, prov.geometry):
            a, _ = mask(r, [geom], crop=True, all_touched=False, nodata=r.nodata, filled=True)
            out[name] = float(np.where(a == r.nodata, 0, a).sum())
    return pd.Series(out, name="population")


def production_kcal() -> pd.DataFrame:
    """Province (polygon) palay and food calories, 2016-2025 totals."""
    df = read_palay_corn()
    df = df[(df.level == "province") & df.crop.isin(["Palay", "Corn"]) & df.period.dt.year.between(*YEARS)]
    pc = df.groupby(["crop", "geo"]).production_t.sum().unstack("crop").fillna(0)
    vp = vr_pf_production(YEARS)
    vp = vp[vp.ecosystem.isin(["vr", "pf"])].groupby("geo").production_t.sum()  # billion kcal
    out = pd.DataFrame({"palay_t": pc["Palay"], "corn_t": pc["Corn"]}).join(vp.rename("vrpf_bkcal"), how="outer").fillna(0)
    out["region_code"] = assign_region(pd.Series(out.index, index=out.index))
    out["polygon"] = pd.Series(out.index, index=out.index).replace(PSA_TO_POLYGON)
    return out


def food_weight(prod: pd.DataFrame, palay_kcal: float) -> pd.Series:
    kcal = (prod.palay_t * palay_kcal + prod.corn_t * CORN_KCAL_PER_KG) * 1e-6 + prod.vrpf_bkcal
    w = kcal.groupby(prod.polygon).sum()
    return w / w.sum()


def typhoon_province(prov) -> pd.DataFrame:
    pts = grid_points(prov)
    tracks = load_tracks()
    point_winds = []
    storm_province_exposure(tracks, pts, point_winds=point_winds)
    return category_exposure(point_winds, pts)


def flood_province() -> pd.DataFrame:
    """EM-DAT events by unit and quarter, with Metro Manila placed (dropped in the agricultural
    controls, where it is a place with no rice)."""
    floods.NO_RICE = set()
    floods.ALIASES.update({n: [NCR] for n in NCR_NAMES})
    ev = floods.load_events()
    pq = floods.province_quarter(ev)
    pq["hit"] = (pq.n_events > 0).astype(float)
    return pq[["polygon", "period", "hit"]], ev


def national(weights: pd.Series, ty: pd.DataFrame, fl: pd.DataFrame) -> pd.DataFrame:
    periods = pd.period_range(START, END, freq="Q")
    w = weights.rename("weight").rename_axis("polygon").reset_index()
    full = (w.merge(pd.DataFrame({"period": periods}), how="cross")
             .merge(ty, on=["polygon", "period"], how="left")
             .merge(fl, on=["polygon", "period"], how="left").fillna(0))
    full["flood_share"] = full.hit
    for m in MEASURES:
        full[m] = full[m] * full.weight
    out = full.groupby("period")[MEASURES].sum().reset_index()
    for m in MEASURES:
        out[f"{m}_lag1"] = out[m].shift(1)
    return out[out.period >= pd.Period("1987Q1", "Q")]


def main():
    prov = provinces()
    pop = population(prov)
    prod = production_kcal()
    missing = sorted(set(prod.polygon) - set(prov.polygon))
    if missing:
        raise KeyError(f"provinces without a unit: {missing}")
    palay = prod.groupby("polygon").palay_t.sum()
    weights = {"palay": palay / palay.sum(), "food": food_weight(prod, PALAY_KCAL_PER_KG),
               "population": pop / pop.sum()}
    print("computing typhoon exposure ...", flush=True)
    ty = typhoon_province(prov)
    fl, ev = flood_province()
    nat = pd.concat([national(w, ty, fl).assign(weighting=k) for k, w in weights.items()])
    nat = nat[["weighting", "period"] + [c for c in nat.columns if c not in ("weighting", "period")]]
    nat.assign(period=nat.period.astype(str)).round(6).to_csv(PROC / "hazard_national_quarter.csv", index=False)
    pd.DataFrame(weights).fillna(0).round(6).rename_axis("polygon").to_csv(PROC / "hazard_national_weights.csv")

    # checks
    checks = []
    # (1) palay version = regional total-palay controls averaged with the regions' palay shares
    reg_ty = pd.read_csv(PROC / "typhoon_region_quarter.csv")
    reg_fl = pd.read_csv(PROC / "flood_region_quarter.csv")
    reg = reg_ty[reg_ty.ecosystem == "total"].merge(
        reg_fl[reg_fl.ecosystem == "total"][["region_code", "period", "flood_share"]], on=["region_code", "period"])
    s = prod.groupby("region_code").palay_t.sum()
    reg["w"] = reg.region_code.map(s / s.sum())
    agg = reg.assign(**{m: reg[m] * reg.w for m in MEASURES}).groupby("period")[MEASURES].sum()
    mine = nat[nat.weighting == "palay"].set_index(nat[nat.weighting == "palay"].period.astype(str))[MEASURES]
    d = (mine - agg.reindex(mine.index)).abs().max()
    checks.append({"check": "palay version = regional controls x regional palay shares",
                   "value": float(d.max()), "detail": "; ".join(f"{k} {v:.2g}" for k, v in d.items())})
    # (2) population: Metro Manila share and flood events placed there
    checks.append({"check": "Metro Manila share of 2020 population", "value": float(weights["population"][NCR]),
                   "detail": f"total population {pop.sum() / 1e6:.1f} million"})
    checks.append({"check": "EM-DAT events placed in Metro Manila", "value": float(ev.units.apply(lambda u: NCR in u).sum()),
                   "detail": "dropped in the agricultural controls (no production)"})
    # (3) food weights: calorie shares of the crops, and sensitivity to the palay factor
    kc = {"palay": prod.palay_t.sum() * PALAY_KCAL_PER_KG * 1e-6, "corn": prod.corn_t.sum() * CORN_KCAL_PER_KG * 1e-6,
          "vr+pf": prod.vrpf_bkcal.sum()}
    tot = sum(kc.values())
    checks.append({"check": "food weights: calorie shares 2016-2025", "value": np.nan,
                   "detail": ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in kc.items())})
    base = nat[nat.weighting == "food"].set_index("period")[MEASURES]
    for f in (0.8, 1.2):
        alt = national(food_weight(prod, PALAY_KCAL_PER_KG * f), ty, fl).set_index("period")[MEASURES]
        checks.append({"check": f"food version with the palay factor x {f}",
                       "value": float((alt - base).abs().max().max()),
                       "detail": "max |difference|; correlation " + ", ".join(
                           f"{m} {np.corrcoef(alt[m], base[m])[0, 1]:.4f}" for m in MEASURES)})
    # (4) correlation between versions
    piv = {m: nat.pivot(index="period", columns="weighting", values=m) for m in MEASURES}
    for m in MEASURES:
        c = piv[m].corr()
        checks.append({"check": f"correlation between versions, {m}", "value": np.nan,
                       "detail": f"palay-food {c.loc['palay', 'food']:.3f}, food-population "
                                 f"{c.loc['food', 'population']:.3f}, palay-population {c.loc['palay', 'population']:.3f}"})
    ch = pd.DataFrame(checks)
    ch.to_csv(TAB / "hazard_national_checks.csv", index=False)
    pd.set_option("display.width", 220, "display.max_colwidth", 140)
    print(ch.to_string(index=False))
    print(nat.groupby("weighting")[MEASURES].agg(["mean", "max"]).round(3).to_string())
    figure(nat)


def figure(nat):
    colors = {"palay": "#2a78d6", "food": "#eb6834", "population": "#52514e"}
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.5), constrained_layout=True, sharex=True)
    for ax, m, lab in zip(axes, ["ty_share_ty", "flood_share"],
                          ["share with typhoon-strength winds", "share in provinces with a flood event"]):
        for k, c in colors.items():
            x = nat[nat.weighting == k]
            ax.plot(x.period.dt.to_timestamp(), x[m], color=c, lw=1, label=k)
        ax.set_ylabel(lab, fontsize=8, color="#52514e")
        ax.tick_params(labelsize=7, colors="#52514e")
        ax.grid(axis="y", color="#d9d8d4", lw=0.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8, ncol=3)
    fig.suptitle("National typhoon and flood exposure by quarter, 1987–2025, three weightings (for the food "
                 "price equation)", fontsize=10, color="#0b0b0b", x=0.01, ha="left")
    fig.savefig(FIG / "hazard_national_quarter.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
