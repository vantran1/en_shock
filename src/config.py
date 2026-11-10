"""Local paths that are not in the repo, read from config/paths.toml (gitignored;
template config/paths.example.toml). The single place where these paths are read."""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "paths.toml"


def local_path(key: str, must_exist: bool = True) -> Path:
    if not CONFIG.exists():
        raise FileNotFoundError(f"{CONFIG} not found: copy config/paths.example.toml to "
                                "config/paths.toml and set the paths for this machine.")
    with open(CONFIG, "rb") as f:
        value = tomllib.load(f).get(key)
    if not value:
        raise KeyError(f"{key} is not set in {CONFIG}")
    p = Path(value).expanduser()
    if must_exist and not p.exists():
        raise FileNotFoundError(f"{key} = {p} does not exist")
    return p
