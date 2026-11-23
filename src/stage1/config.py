"""Configuration, paths and the predictand table shared by all steps."""
from __future__ import annotations

import os
import pathlib
import pickle
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]   # the en_shock repository (src/stage1/config.py)
# Outputs of these sections go to outputs/<section>/; everything else (shared, skill, analysis) to outputs/shared/
SECTIONS = ("agriculture", "electricity", "labour", "prices")

# key: (long name, units, aggregation over a quarter, transform, source)
PREDICTANDS = {
    "T": ("Mean 2 m temperature", "°C", "mean", "none", "monthly"),
    "VPD": ("Vapour pressure deficit", "kPa", "mean", "none", "monthly"),
    "P": ("Total precipitation", "mm/month", "sum", "gamma", "monthly"),
    "SM_RZ": ("Root-zone soil moisture, 0-100 cm", "m³/m³", "mean", "none", "monthly"),
    "SM_DEEP": ("Deep soil moisture, 100-289 cm", "m³/m³", "mean", "none", "monthly"),
    "PET": ("Potential evaporation", "mm/month", "sum", "none", "monthly"),
    "E": ("Actual evaporation", "mm/month", "sum", "none", "monthly"),
    "SPEI3": ("Climatic water balance, 3-month P - PET, standardised", "std. units", "mean", "none", "monthly"),
    "RS": ("Surface solar radiation downwards", "MJ m⁻² day⁻¹", "mean", "none", "monthly"),
    "RO": ("Runoff", "mm/month", "sum", "gamma", "monthly"),
    "TMAX": ("Mean daily maximum temperature", "°C", "mean", "none", "hourly"),
    "TMIN": ("Mean daily minimum temperature", "°C", "mean", "none", "hourly"),
    "EDD": ("Extreme degree-days above T*", "°C·day/month", "sum", "empirical", "hourly"),
    "NHOT": ("Hot days, daily maximum above T*", "days/month", "sum", "empirical", "hourly"),
    "NDRY": ("Dry days, daily rain below 1 mm", "days/month", "sum", "empirical", "hourly"),
    "LDRY": ("Longest dry spell in the month", "days", "max", "empirical", "hourly"),
    "N50": ("Heavy-rain days, daily rain of 50 mm or more", "days/month", "sum", "empirical", "hourly"),
    "VPDMAX": ("Mean daily maximum VPD (afternoon VPD)", "kPa", "mean", "none", "hourly"),
    # labour: WBGT in working hours (scripts/06-08); fitted apart from the variables above
    "WBGTSUN_P50": ("WBGT in the sun, median of working hours", "°C", "mean", "none", "wbgt"),
    "WBGTSUN_P90": ("WBGT in the sun, 90th percentile of working hours", "°C", "mean", "none", "wbgt"),
    "WBGTSUN_DMAX": ("WBGT in the sun, mean daily maximum in working hours", "°C", "mean", "none", "wbgt"),
    "WBGTSHD_P50": ("WBGT in the shade, median of working hours", "°C", "mean", "none", "wbgt"),
    "WBGTSHD_P90": ("WBGT in the shade, 90th percentile of working hours", "°C", "mean", "none", "wbgt"),
    "WBGTSHD_DMAX": ("WBGT in the shade, mean daily maximum in working hours", "°C", "mean", "none", "wbgt"),
}
EXTRA_COLUMNS = {"CWB3": ("3-month P - PET", "mm/3 months")}   # written next to SPEI3 in the outputs

REGION_ORDER = ["NCR", "CAR", "R01", "R02", "R03", "R04A", "MIMAROPA", "R05", "R06", "R07", "R08",
                "R09", "R10", "R11", "R12", "R13", "BARMM"]


PREDICTORS = ("roni", "dmi")
# work files that depend on the predictors: a variant keeps its own; everything else (fields, weights, hourly
# WBGT) is shared with the main run
VARIANT_WORK = {"models.pkl", "fit_diagnostics.pkl", "models_wbgt.pkl"}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path=None, variant: str | None = None) -> dict:
    """The configuration, with the overrides of `variant` (an entry of `variants:` in config.yaml) merged in.

    A variant writes its outputs to outputs/shared/variants/<name>/ and its models to outputs/shared/work/variants/<name>/ (or uses
    those of the variant named in its `models_from`, or the main run's with `models_from: main`), and reads the
    shared inputs (fields, weights, path, cells) of the main run unless it has made its own."""
    path = pathlib.Path(path or os.environ.get("STAGE1_CONFIG", ROOT / "config.yaml")).resolve()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_root"] = path.parent
    cfg["_variant"] = None
    cfg["_models_from"] = None
    if variant:
        vs = cfg.get("variants") or {}
        if variant not in vs:
            raise SystemExit(f"no variant '{variant}' in {path.name} (variants: {', '.join(vs) or 'none'})")
        over = dict(vs[variant] or {})
        models_from = over.pop("models_from", None)
        cfg = _merge(cfg, over)
        cfg["_variant"] = variant
        # models_from: main = the main run's models (outputs/shared/work/), e.g. a scenario path on the RONI-alone model
        cfg["_models_from"] = None if models_from == "main" else (models_from or variant)
    predictors(cfg)
    return cfg


def predictors(cfg: dict) -> tuple:
    """Climate-mode indices the models use, in the order of the predictor columns: ('roni',) or ('roni', 'dmi')."""
    p = tuple(cfg["model"].get("predictors", PREDICTORS))
    bad = [v for v in p if v not in PREDICTORS]
    if not p or bad or len(set(p)) != len(p):
        raise SystemExit(f"model.predictors must be a list drawn from {list(PREDICTORS)}, got {list(p)}")
    return tuple(v for v in PREDICTORS if v in p)


def label(cfg: dict) -> str:
    v = cfg.get("_variant")
    return f"variant '{v}' ({' + '.join(predictors(cfg)).upper()})" if v else f"main run ({' + '.join(predictors(cfg)).upper()})"


def path(cfg: dict, key: str) -> pathlib.Path | None:
    v = cfg["paths"].get(key)
    if v in (None, "", "null"):
        return None
    p = pathlib.Path(os.path.expanduser(str(v)))
    return p if p.is_absolute() else (cfg["_root"] / p)


def work(cfg: dict, name: str) -> pathlib.Path:
    d = path(cfg, "work_dir")
    if cfg.get("_models_from") and name in VARIANT_WORK:
        d = d / "variants" / cfg["_models_from"]
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _main_out(cfg: dict, parts: tuple) -> pathlib.Path:
    """The main run's place for an output: outputs/<section>/... for the four sections (SECTIONS), and
    outputs/shared/... for everything else ("shared", "skill", "analysis")."""
    d = path(cfg, "outputs_dir")
    if parts and parts[0] in SECTIONS:
        return d.joinpath(*parts)
    if parts and parts[0] == "shared":
        parts = parts[1:]
    return d.joinpath("shared", *parts)


def out(cfg: dict, *parts: str) -> pathlib.Path:
    """Where a step writes an output: outputs/<section>/... or outputs/shared/... for the main run (see _main_out),
    and outputs/shared/variants/<name>/<part>/... for a variant (the same sub-folders as before the restructure)."""
    if cfg.get("_variant"):
        p = path(cfg, "outputs_dir").joinpath("shared", "variants", cfg["_variant"], *parts)
    else:
        p = _main_out(cfg, parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def out_in(cfg: dict, *parts: str) -> pathlib.Path:
    """An output read as an input (the path, the cells, the blocks): the variant's own copy if it made one,
    otherwise the main run's."""
    p = out(cfg, *parts)
    if cfg.get("_variant") and not p.exists():
        return _main_out(cfg, parts)
    return p


def check_models(cfg: dict, models: dict, what: str = "models.pkl") -> None:
    """Stop if the saved models were fitted with other predictors, or on other cells, than the run uses
    (the cells are those of step 1, in outputs/shared/work/weights.pkl)."""
    step = "scripts/03_fit_climate_model.py" if what == "models.pkl" else "scripts/helpers/labour_fit_wbgt.py"
    flag = f" --variant {cfg['_models_from']}" if cfg.get("_models_from") else ""
    want = predictors(cfg)
    got = {tuple(getattr(m, "predictors", PREDICTORS)) for m in models.values()}
    if got != {want}:
        raise SystemExit(f"{what} was fitted with {' + '.join(sorted(next(iter(got)))).upper()}, but the {label(cfg)} "
                         f"uses {' + '.join(want).upper()}: re-run python {step}{flag}")
    wp = work(cfg, "weights.pkl")
    if wp.exists():
        n_cells = len(load_pickle(wp, "scripts/01_prepare_inputs.py")["cells"])
        n_model = {int(m.cv_resid.shape[1]) for m in models.values()}
        if n_model != {n_cells}:
            raise SystemExit(f"{what} was fitted on {', '.join(map(str, sorted(n_model)))} cells, but step 1 now has "
                             f"{n_cells} (a new land-sea mask?): re-run python {step}{flag}")


def save(obj, p: pathlib.Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle(p: pathlib.Path, step: str):
    if not p.exists():
        raise SystemExit(f"{p} is missing: run {step} first")
    with open(p, "rb") as f:
        return pickle.load(f)


class Timer:
    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self.t0 = time.time()
        print(f"{self.label} …", flush=True)
        return self

    def __exit__(self, *exc):
        print(f"{self.label}: done in {time.time() - self.t0:.0f} s", flush=True)
