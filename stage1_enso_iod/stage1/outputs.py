"""Writing the tables handed to the agricultural, electricity and labour sections."""
from __future__ import annotations

import json
import datetime as dt

import numpy as np
import pandas as pd

from . import config as C
from .regions import grid_of, majority_region

FLOAT = "%.6g"


def write_csv(df: pd.DataFrame, p, **kw):
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False, float_format=FLOAT, date_format="%Y-%m-%d", **kw)
    print(f"  wrote {p.relative_to(p.parents[2]) if len(p.parents) > 2 else p} ({len(df):,} rows)")


def update_metadata(cfg: dict, step: str, info: dict):
    p = C.out(cfg, "shared", "run_metadata.json")
    meta = json.loads(p.read_text()) if p.exists() else {}
    meta[step] = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **info}
    p.write_text(json.dumps(meta, indent=2, default=str))


def regional_observed(fields: dict, W: np.ndarray, variables: list[str], cwb_reg_clim, clim_years) -> dict:
    """Observed regional series with the cell weights W: dict var -> DataFrame (months x regions)."""
    out = {}
    for v in variables:
        if v == "SPEI3":
            c3 = fields["CWB3"] @ W.T
            ref = c3.loc[f"{clim_years[0]}":f"{clim_years[1]}"]
            mu, sd = ref.groupby(ref.index.month).mean(), ref.groupby(ref.index.month).std()
            out["SPEI3"] = (c3 - mu.reindex(c3.index.month).values) / sd.reindex(c3.index.month).values
            out["CWB3"] = c3
        else:
            out[v] = fields[v] @ W.T
    return out


def long_table(reg: dict, regions, codes, extra: dict | None = None) -> pd.DataFrame:
    first = next(iter(reg.values()))
    n, R = first.shape
    df = pd.DataFrame({"date": np.repeat(first.index.values, R), "code": np.tile(codes, n), "region": np.tile(regions, n)})
    for k, v in (extra or {}).items():
        df[k] = df["code"].map(v)
    for k, a in reg.items():
        df[k] = np.asarray(a.values).reshape(-1)
    return df


def variables_present(cfg: dict, fields: dict) -> list[str]:
    vs = [v for v in cfg["model"]["variables"] if v in fields]
    vs += [v for v in cfg["model"].get("hourly_variables", []) if v in fields]
    return vs


def export_observed(cfg: dict, fields: dict, weights: dict):
    """Observed regional monthly tables (the estimation data of Stage 2) for every section's weights."""
    from .fit import weight_sets
    variables = variables_present(cfg, fields)
    clim = cfg["period"]["clim"]
    grid = grid_of(cfg)
    done = set()
    for sec, sets in weight_sets(cfg).items():
        for ws in sets:
            rs, kind = ws.split("_", 1)
            s = weights["sets"][rs]
            reg = regional_observed(fields, s["W"][kind], variables, None, clim)
            extra = {"grid": grid} if rs == "r17" else None
            df = long_table(reg, s["regions"], s["codes"], extra)
            df.insert(1, "weights", s["flags"][kind]["source"] + (" [FALLBACK]" if s["flags"][kind]["fallback"] else ""))
            folder = "agriculture" if rs == "r16" else "shared"
            name = f"observed_monthly_{rs.replace('r', '')}regions_{kind}.csv"
            if (folder, name) in done:
                continue
            done.add((folder, name))
            write_csv(df, C.out(cfg, folder, name))
    units = {**{k: v[1] for k, v in C.PREDICTANDS.items()}, **{k: v[1] for k, v in C.EXTRA_COLUMNS.items()}}
    names = {**{k: v[0] for k, v in C.PREDICTANDS.items()}, **{k: v[0] for k, v in C.EXTRA_COLUMNS.items()}}
    cols = variables + (["CWB3"] if "SPEI3" in variables else [])
    write_csv(pd.DataFrame({"column": cols, "long_name": [names[c] for c in cols], "units": [units[c] for c in cols],
                            "source": [C.PREDICTANDS.get(c, ("", "", "", "", "monthly"))[4] for c in cols]}),
              C.out(cfg, "shared", "variables.csv"))


def export_weights(cfg: dict, weights: dict):
    lat, lon, cells = weights["lat"], weights["lon"], weights["cells"]
    clat, clon = lat[cells // len(lon)], lon[cells % len(lon)]
    grid = grid_of(cfg)
    rows = []
    for rs, s in weights["sets"].items():
        for kind, f in s["flags"].items():
            cov = s["coverage"][kind] if kind in s["coverage"] else pd.Series(np.nan, index=s["codes"])
            mov = s["reassigned"][kind] if kind in s.get("reassigned", {}) else pd.Series(np.nan, index=s["codes"])
            for c in s["codes"]:
                rows.append(dict(region_set=rs, weights=kind, code=c, source=f["source"], fallback=f["fallback"],
                                 share_captured_by_land_cells=cov.get(c, np.nan),
                                 share_reassigned_to_nearest_cell=mov.get(c, np.nan)))
    write_csv(pd.DataFrame(rows), C.out(cfg, "shared", "weights_coverage.csv"))

    p16 = weights["pieces"]["r16"]["pieces"]
    p17 = weights["pieces"]["r17"]["pieces"]
    s16, s17 = weights["sets"]["r16"], weights["sets"]["r17"]
    cells_df = pd.DataFrame({"cell": cells, "lat": clat, "lon": clon,
                             "region16_majority_area": majority_region(p16, cells, s16["codes"], "area"),
                             "region17_majority_population": majority_region(
                                 p17, cells, s17["codes"], "population" if "population" in p17 else "area")})
    cells_df["grid"] = cells_df["region17_majority_population"].map(grid)
    write_csv(cells_df, C.out(cfg, "shared", "cells.csv"))

    # island fix: every piece moved from a dropped cell to its nearest model cell, with the distance
    far = float(cfg["weights"].get("far_km", 100))
    for rs, s_, pcs, fname in (("r16", s16, p16, "agriculture/island_reassignment_16regions.csv"),
                               ("r17", s17, p17, "shared/island_reassignment_17regions.csv")):
        mv = weights["pieces"][rs]["moves"].copy()
        sec, name = fname.split("/")
        tot = {k: pcs.groupby("ridx")[k].sum() for k in ("cropland", "population", "area") if k in pcs}
        mv["code"] = np.array(s_["codes"])[mv["ridx"]]
        mv["region"] = np.array(s_["regions"])[mv["ridx"]]
        mv["from_lat"], mv["from_lon"] = lat[mv["from_cell"] // len(lon)], lon[mv["from_cell"] % len(lon)]
        mv["to_lat"], mv["to_lon"] = lat[mv["to_cell"] // len(lon)], lon[mv["to_cell"] % len(lon)]
        own = cells_df.set_index("cell")["region16_majority_area" if rs == "r16" else "region17_majority_population"]
        mv["to_cell_main_region"] = mv["to_cell"].map(own)
        mv["to_cell_in_other_region"] = mv["to_cell_main_region"] != mv["code"]
        for k in tot:
            mv[f"share_of_region_{k}"] = mv[k] / mv["ridx"].map(tot[k]).replace(0, np.nan)
        mv["farther_than_threshold"] = mv["distance_km"] > far
        mv = mv.rename(columns={k: f"{k}_km2" if k in ("area", "cropland") else k for k in ("area", "cropland")})
        cols = ["code", "region", "from_cell", "from_lat", "from_lon", "to_cell", "to_lat", "to_lon", "distance_km",
                "farther_than_threshold", "to_cell_main_region", "to_cell_in_other_region"] + \
               [c for c in ("cropland_km2", "area_km2", "population") if c in mv] + \
               [c for c in mv if c.startswith("share_of_region_")]
        write_csv(mv[cols].sort_values(["code", "distance_km"], ascending=[True, False]), C.out(cfg, sec, name))

    # agriculture: pieces of the 16 regions
    a = p16.copy()
    a["code"] = np.array(s16["codes"])[a["ridx"]]
    a = a[a["cell"].isin(cells)]
    for kind in ("cropland", "area"):
        W = s16["W"][kind]
        pos = pd.Series(np.arange(len(cells)), index=cells)
        a[f"w_{kind}"] = W[a["ridx"].to_numpy(), pos[a["cell"]].to_numpy()]
    a["lat"], a["lon"] = lat[a["cell"] // len(lon)], lon[a["cell"] % len(lon)]
    keep = ["cell", "lat", "lon", "code"] + [c for c in ("area", "area_reassigned", "cropland", "cropland_reassigned")
                                             if c in a] + ["w_cropland", "w_area"]
    write_csv(a[keep].rename(columns={"area": "area_km2", "area_reassigned": "area_reassigned_km2",
                                      "cropland": "cropland_km2", "cropland_reassigned": "cropland_reassigned_km2"})
              .sort_values(["code", "cell"]),
              C.out(cfg, "agriculture", "cell_weights_16regions.csv"))

    # electricity and labour: pieces of the 17 regions, with grid weights (Eq. 2 of the electricity note)
    e = p17.copy()
    e["code"] = np.array(s17["codes"])[e["ridx"]]
    e = e[e["cell"].isin(cells)]
    e["grid"] = e["code"].map(grid)
    popcol = "population" if "population" in e else "area"
    W = s17["W"]["population"]
    pos = pd.Series(np.arange(len(cells)), index=cells)
    e["w_population_in_region"] = W[e["ridx"].to_numpy(), pos[e["cell"]].to_numpy()]
    e["w_area_in_region"] = s17["W"]["area"][e["ridx"].to_numpy(), pos[e["cell"]].to_numpy()]
    mim = cfg["sections"]["electricity"].get("mimaropa_in_luzon_grid", False)
    for col, incl in (("w_population_in_grid", mim), ("w_population_in_grid_incl_mimaropa", True),
                      ("w_population_in_grid_excl_mimaropa", False)):
        sub = e if incl else e[e["code"] != "MIMAROPA"]
        tot = sub.groupby("grid")[popcol].sum()
        e[col] = np.where(e.index.isin(sub.index), e[popcol] / e["grid"].map(tot), 0.0)
    e["lat"], e["lon"] = lat[e["cell"] // len(lon)], lon[e["cell"] % len(lon)]
    cols = ["cell", "lat", "lon", "code", "grid", "area", "area_reassigned"] + \
           [c for c in ("population", "population_reassigned") if c in e] + \
           ["w_population_in_region", "w_area_in_region", "w_population_in_grid",
            "w_population_in_grid_incl_mimaropa", "w_population_in_grid_excl_mimaropa"]
    out = e[cols].rename(columns={"area": "area_km2", "area_reassigned": "area_reassigned_km2"}) \
        .sort_values(["grid", "code", "cell"])
    write_csv(out, C.out(cfg, "electricity", "cell_weights_17regions.csv"))
    write_csv(out, C.out(cfg, "labour", "cell_weights_17regions.csv"))

    # region -> grid
    g = s17["geometry"]
    reg = pd.DataFrame({"code": s17["codes"], "region": s17["regions"], "grid": [grid.get(c) for c in s17["codes"]]})
    reg["area_km2"] = g.to_crs(6933).area.to_numpy() / 1e6
    if "population" in p17:
        reg["population_in_land_cells"] = p17.groupby("ridx")["population"].sum().reindex(range(len(reg))).to_numpy()
    reg["in_grid_weights"] = np.where(reg["code"] == "MIMAROPA", mim, True)
    reg["note"] = np.where(reg["code"] == "MIMAROPA",
                           "Mindoro, Palawan, Marinduque and Romblon are not connected to the Luzon grid "
                           "(Batangas-Mindoro cable due 2028); see config sections.electricity.mimaropa_in_luzon_grid", "")
    write_csv(reg, C.out(cfg, "electricity", "region_grid_map.csv"))
