#!/usr/bin/env python3
"""Compare the rules for choosing the predictor lags (model.lag_choice, model.lag_candidates).

Fit the variants first (each about 10-30 minutes; the main fit is the fixed lag set sync+lag6, the default since
27 Nov 2026; the month-by-month menu that was the default before is the variant lags_menu):
    for v in lags_fixed0 lags_fixed1 lags_fixed3 lags_fixed36 lags_menu lags_menu_old lags_sync_or6 lags_window; do
        python scripts/03_fit_climate_model.py --variant $v
    done
then
    python scripts/helpers/analysis/lag_rules.py
and for RONI + DMI the variants roni_dmi_<rule> (and roni_dmi), then
    python scripts/helpers/analysis/lag_rules.py --predictors roni dmi     # -> outputs/shared/analysis/lag_rules/roni_dmi/

Compares fixed lag sets (the same in every month, so the CV chooses only the EOF and CCA modes) with menus of lag
sets (the CV chooses one for each variable and month, as the main fit did before 27 Nov 2026): the selection-honest (nested-CV) skill
by variable and by month, the lag sets chosen for temperature, how often the lag set changes between neighbouring
months, how often the temperature effect is ~0 in the six months after the El Nino of a scenario path ends, and the
deterministic effect of the 1997-98 scenario path on temperature and rainfall (mean of the 16 regions, cropland
weights). Writes outputs/shared/analysis/lag_rules/ (summary.txt and the tables behind it).
Every variant in RULES must be fitted first: python scripts/03_fit_climate_model.py --variant <name>."""
from __future__ import annotations

import argparse
import io
import pathlib
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "src"))
from stage1 import config as C  # noqa: E402
from stage1 import fit as F  # noqa: E402

LABELS = {"fixed0": "fixed sync", "fixed1": "fixed sync+lag1", "fixed3": "fixed sync+lag3", "main": "fixed sync+lag6 (main)",
          "fixed36": "fixed sync+lag3+lag6", "menu_old": "menu: sync, sync+lag1", "sync_or6": "menu: sync, sync+lag6",
          "menu": "menu: sync, +lag1, +lag3, +lag6 (main before 27 Nov 2026)", "window": "the same menu, shared with neighbours"}


def rules(predictors) -> dict:
    """{variant: label}: RONI alone (lags_<rule>, the main fit) or RONI + DMI (roni_dmi_<rule>, roni_dmi)."""
    dmi = "dmi" in predictors
    out = {}
    for k, lab in LABELS.items():
        if k == "main":
            out["roni_dmi" if dmi else None] = lab
        else:
            out[("roni_dmi_" if dmi else "lags_") + k] = lab
    return out
SCENARIOS = ("1997-98", "2015-16", "2023-24", "unit")


def load_models(cfg):
    p = C.work(cfg, "models.pkl")
    if not p.exists():
        return None
    M = pickle.load(open(p, "rb"))
    return M["models"] if isinstance(M, dict) and "models" in M else M


def scenario_effect(models, var, D, path, ws="r16_cropland", t_star=2026) -> pd.Series:
    """Deterministic scenario-minus-neutral effect for each month of a path, mean over the regions of ws. The
    inputs are ordered as in indices.design: for each lag, the model's predictors (RONI, and DMI if used)."""
    P = path.set_index("date")
    out = {}
    for t in P.index[~P["lead_in"].astype(bool)]:
        m = models[(var, t.month)]
        x = np.array([[P[p].get(t - pd.DateOffset(months=L), 0.0) for L in m.lags for p in m.predictors]])
        d = m.physical(x, np.array([t_star])) - m.physical(np.zeros_like(x), np.array([t_star]))
        out[t] = float(np.mean(D.aggregator(ws, var, t.month)(d)))
    return pd.Series(out)


def dropouts(models, D, ws, cfg, model_dir: str, months_after: int = 6, tol: float = 0.02) -> tuple[int, int]:
    """Months with a temperature effect below `tol` °C (mean of the regions) in the `months_after` months after the
    last non-zero RONI of each scenario path: (such months, months looked at)."""
    n = tot = 0
    for s in SCENARIOS:
        f = C.path(cfg, "outputs_dir") / "shared" / "scenarios" / s / model_dir / "path.csv"
        if not f.exists():
            continue
        path = pd.read_csv(f, parse_dates=["date"])
        e = scenario_effect(models, "T", D, path, ws)
        nz = path.loc[(path["roni"] != 0) & ~path["lead_in"].astype(bool), "date"]
        after = e[(e.index > nz.max())].iloc[:months_after]
        n += int((after.abs() < tol).sum())
        tot += len(after)
    return n, tot


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--weights", default="r16_cropland")
    ap.add_argument("--scenario", default="1997-98")
    ap.add_argument("--predictors", nargs="+", default=["roni"], help="roni (default) or roni dmi")
    a = ap.parse_args(argv)
    RULES = rules(a.predictors)
    model_dir = "_".join(a.predictors)                # the scenario hand-off folder of the model (roni, roni_dmi)
    cfg = C.load(a.config, next(iter(RULES)))
    D, _, _ = F.load_data(cfg, refresh_indices=False)
    path = pd.read_csv(C.path(cfg, "outputs_dir") / "shared" / "scenarios" / a.scenario / model_dir / "path.csv",
                       parse_dates=["date"])
    out = C.path(cfg, "outputs_dir") / "shared" / "analysis" / "lag_rules" / ("" if model_dir == "roni" else model_dir)
    out.mkdir(parents=True, exist_ok=True)
    summ, bymonth, lagsT, effT, effP, changes, drop = [], {}, {}, {}, {}, {}, {}
    for v, name in RULES.items():
        cv = C.load(a.config, v)
        models = load_models(cv)
        sk = C.out(cv, "skill", f"skill_{a.weights}.csv")
        if models is None or not sk.exists():
            print(f"{name}: not fitted (python scripts/03_fit_climate_model.py --variant {v})")
            continue
        s = pd.read_csv(C.out(cv, "skill", "skill_summary.csv"))
        s = s[s["weights"] == a.weights].assign(rule=name)
        summ.append(s[["rule", "var", "rho_cv", "rho_nested", "pct_significant", "crpss"]])
        k = pd.read_csv(sk)
        bymonth[name] = k[k["cv"] == "nested"].groupby(["var", "month"])["spearman"].mean()
        mc = pd.read_csv(C.out(cv, "shared", "model_configs.csv"))
        piv = mc.pivot(index="var", columns="month", values="lagset")
        changes[name] = int(sum((piv[m] != piv[m % 12 + 1]).sum() for m in range(1, 13)))
        lagsT[name] = piv.loc["T"]
        effT[name] = scenario_effect(models, "T", D, path, a.weights)
        effP[name] = scenario_effect(models, "P", D, path, a.weights)
        drop[name] = dropouts(models, D, a.weights, cfg, model_dir)
    if not summ:
        raise SystemExit("nothing fitted")
    S = pd.concat(summ)
    by_var = S.pivot(index="var", columns="rule", values="rho_nested")[list(bymonth)]
    totals = S.groupby("rule")[["rho_cv", "rho_nested", "pct_significant", "crpss"]].mean().loc[list(bymonth)]
    totals["lag changes between neighbouring months"] = pd.Series(changes)
    totals["T effect ~0 in the 6 months after El Nino"] = pd.Series({k: f"{n} of {t}" for k, (n, t) in drop.items()})
    BM = pd.DataFrame({k: s.unstack().mean() for k, s in bymonth.items()}).T
    TM = pd.DataFrame({k: s["T"] for k, s in bymonth.items()}).T
    ET, EP = pd.DataFrame(effT).T, pd.DataFrame(effP).T
    ET.columns = EP.columns = [f"{c:%Y-%m}" for c in ET.columns]
    for df, f in ((S, "skill_by_variable.csv"), (BM, "skill_by_month.csv"), (ET, f"T_effect_{a.scenario}.csv"),
                  (EP, f"P_effect_{a.scenario}.csv")):
        df.to_csv(out / f)
    buf = io.StringIO()
    w = lambda *x: print(*x, file=buf)  # noqa: E731
    w(f"Lag rules compared, predictors {' + '.join(p.upper() for p in a.predictors)} ({a.weights}; nested CV = "
      "selection-honest skill)\n")
    w("Mean over the variables:")
    w(totals.round(3).to_string())
    w("(the last column: months with |T effect| < 0.02 °C in the six months after the El Nino of each scenario path ends;"
      " a model whose months look back less far than that shows zeros there)")
    w("\nNested-CV rho by variable:")
    w(by_var.round(3).to_string())
    w("\nNested-CV rho by month, mean over the variables:")
    w(BM.round(3).to_string())
    w("\nTemperature, nested-CV rho by month:")
    w(TM.round(2).to_string())
    w("\nTemperature lag set by month:")
    w(pd.DataFrame(lagsT).T.to_string())
    yrs = [c for c in ET.columns if c[:4] in (a.scenario[:4], str(int(a.scenario[:4]) + 1))]
    w(f"\n{a.scenario} scenario, deterministic temperature effect (°C), mean of the regions:")
    w(ET[yrs].round(2).to_string())
    w(f"\n{a.scenario} scenario, deterministic rainfall effect (mm/month), mean of the regions:")
    w(EP[yrs].round(0).to_string())
    (out / "summary.txt").write_text(buf.getvalue())
    print(buf.getvalue())
    print(f"wrote {out}/")


if __name__ == "__main__":
    main()
