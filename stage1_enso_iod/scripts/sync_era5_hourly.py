#!/usr/bin/env python3
"""Hourly ERA5 from Azure Blob storage: save the access token, see what is there, copy it here.

The files are the monthly era5_YYYY_MM.nc uploaded with era5_azure_upload.sh (blobs hourly/YYYY/era5_YYYY_MM.nc).
They are copied to paths.era5_hourly_dir when that is set in config.yaml, otherwise to data/inputs/era5_hourly/
(ignored by git). Steps 2 and 6 read them once paths.era5_hourly_dir points to that folder.

  python scripts/sync_era5_hourly.py set-token                      # once: paste the Blob Container SAS URL (hidden)
  python scripts/sync_era5_hourly.py list                           # months in Azure and here, gaps per year
  python scripts/sync_era5_hourly.py sync                           # copy every month that is not here yet
  python scripts/sync_era5_hourly.py sync --months 1955-01 1959-12  # only these months

In Python (notebooks, analysis scripts), with the project folder on sys.path:
  from stage1 import azure_era5 as AZ
  ds = AZ.open_era5("1955-01", "1959-12", variables=["t2m", "d2m"])   # downloads what is missing, then opens

The token is kept in ~/.config/undrr/era5_sas_url (readable only by you), or taken from the ERA5_SAS_URL
environment variable, which takes precedence. A read + list token (sp=rl) is enough for everything here.
"""
from __future__ import annotations

import argparse
import getpass
import pathlib
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from stage1 import azure_era5 as AZ  # noqa: E402


def _rel(p: pathlib.Path) -> str:
    try:
        return str(p.resolve().relative_to(AZ.ROOT))
    except ValueError:
        return str(p)


def _token_line(store: AZ.Store) -> str:
    exp = f"expires {store.expires:%Y-%m-%d}" if store.expires else "no expiry given"
    return f"token from {store.token_source}: permissions '{store.permissions or '?'}', {exp}"


def _config():
    try:
        from stage1 import config as C
        return C, C.load()
    except Exception:  # noqa: BLE001
        return None, None


def _hint(store: AZ.Store) -> None:
    C, cfg = _config()
    current = C.path(cfg, "era5_hourly_dir") if cfg else None
    if current is None or current.resolve() != store.local_dir.resolve():
        print(f"\nSteps 2 and 6 read these files once config.yaml has  paths.era5_hourly_dir: {_rel(store.local_dir)}\n"
              "(set it when every month of the training period is here: missing months become NaN in step 2).")


def cmd_set_token(a) -> int:
    url = getpass.getpass("Paste Blob SAS URL (input hidden): ")
    try:
        AZ._validate(url)
    except ValueError as e:
        print(f"Not saved: {e}")
        return 2
    try:
        store = AZ.Store(sas_url=url, prefix=a.prefix, local_dir=a.dest)
        n = len(store.blobs())
    except AZ.AzureAccessError as e:
        print(f"Not saved, Azure did not accept it:\n{e}")
        return 1
    path = AZ.save_sas_url(url)
    print(f"Saved to {str(path).replace(str(pathlib.Path.home()), '~')} (readable only by you). "
          f"Azure accepted it: {n} months under {store.location}/{store.prefix}/.")
    print(_token_line(store).replace("token from the sas_url argument", "token"))
    if any(c in store.permissions for c in "wdc"):
        print("Note: this token can also write or delete. For reading, a read + list token (sp=rl) is safer to keep "
              "on disk; ask the storage owner for one.")
    import os
    if os.environ.get("ERA5_SAS_URL"):
        print("Note: ERA5_SAS_URL is set in this shell and takes precedence over the saved token.")
    return 0


def cmd_list(a) -> int:
    store = AZ.Store(prefix=a.prefix, local_dir=a.dest)
    blobs = store.blobs()
    az = {pd.Timestamp(y, m, 1): b for (y, m), b in blobs.items()}
    local = set(store.local_months())
    print(f"Azure: {store.location}/{store.prefix}/   ({_token_line(store)})")
    print(f"Here:  {_rel(store.local_dir)}\n")
    years = sorted({t.year for t in az} | {t.year for t in local})
    if not years:
        print("Nothing in Azure or here yet.")
        return 0
    print("year   Azure   here   not in Azure      here, differs from Azure")
    n_diff = 0
    for y in years:
        months = pd.date_range(f"{y}-01-01", f"{y}-12-01", freq="MS")
        in_az = [t for t in months if t in az]
        here = [t for t in months if t in local]
        gaps = [t.month for t in months if t not in az]
        diff = [t.month for t in in_az if t in local and store._state(az[t]) == "differs"]
        n_diff += len(diff)
        print(f"{y}  {len(in_az):3d}/12  {len(here):3d}/12   {','.join(map(str, gaps)) or '-':16s}  "
              f"{','.join(map(str, diff)) or '-'}")
    size = sum(b.size for b in blobs.values()) / 1e9
    print(f"\n{len(az)} months in Azure ({size:.1f} GB); {len(local & set(az))} of them here"
          + (f", {n_diff} differ from Azure (sync --refresh replaces them)" if n_diff else "") + ".")
    _, cfg = _config()
    if cfg and cfg.get("period", {}).get("train"):
        y0, y1 = cfg["period"]["train"]
        gaps = [t for t in pd.date_range(f"{y0}-01-01", f"{y1}-12-01", freq="MS") if t not in az]
        if gaps:
            print(f"Training period {y0}-{y1}: {len(gaps)} months are not in Azure yet: {AZ._fmt_months(gaps)}")
        else:
            print(f"Training period {y0}-{y1}: every month is in Azure.")
    return 0


def cmd_sync(a) -> int:
    store = AZ.Store(prefix=a.prefix, local_dir=a.dest)
    print(f"Azure: {store.location}/{store.prefix}/  ->  {_rel(store.local_dir)}")
    first, last = (a.months if a.months else (None, None))
    res = store.sync(first, last, workers=a.workers, refresh=a.refresh)
    if res["failed"]:
        print(f"\n{len(res['failed'])} month(s) failed; run the same command again to retry them.")
    _hint(store)
    return 1 if res["failed"] or res["differs"] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", help="local folder (default: paths.era5_hourly_dir, else data/inputs/era5_hourly)")
    ap.add_argument("--prefix", default=AZ.DEFAULT_PREFIX, help="folder in the container (default: hourly)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("set-token", help="save the Blob Container SAS URL (hidden prompt) after testing it")
    sub.add_parser("list", help="months in Azure and here")
    s = sub.add_parser("sync", help="copy the months that are not here yet")
    s.add_argument("--months", nargs=2, metavar=("FIRST", "LAST"), help="YYYY-MM YYYY-MM (or YYYY YYYY)")
    s.add_argument("--workers", type=int, default=4, help="parallel downloads (default 4)")
    s.add_argument("--refresh", action="store_true", help="also replace local files that differ from Azure's copy")
    a = ap.parse_args(argv)
    try:
        return {"set-token": cmd_set_token, "list": cmd_list, "sync": cmd_sync}[a.cmd](a)
    except (AZ.AzureAccessError, AZ.AzureIntegrityError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Finished months are kept; run the same command again to continue.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
