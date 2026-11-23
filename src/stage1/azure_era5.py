"""Hourly ERA5 files in Azure Blob storage: list them, copy them to a local folder, open them with xarray.

The files are the monthly era5_YYYY_MM.nc (t2m, d2m, sp, u10, v10, ssrd, tp; hourly, time in UTC) uploaded with
era5_azure_upload.sh to the blobs <prefix>/<YYYY>/era5_YYYY_MM.nc of the container (prefix "hourly").

Local copies. A month is downloaded once, into a flat folder with the same file names as paths.hourly_pattern
(era5_YYYY_MM.nc), so that folder can serve as paths.era5_hourly_dir for steps 2 and 6. The folder is
paths.era5_hourly_dir when that is set, otherwise data/shared/era5/hourly/ (ignored by git). A download goes to
<name>.part, is checked against the size and MD5 that Azure holds, and only then gets its final name, so an
interrupted download never looks like a finished file. A local file that differs from Azure's copy is never
replaced unless asked (refresh=True), and is reported instead.

Access. The "Blob Container SAS URL", taken from, in this order: the argument sas_url; the environment variable
ERA5_SAS_URL; the file ~/.config/undrr/era5_sas_url (written with mode 600 by
`python scripts/helpers/sync_era5_hourly.py set-token`); a hidden prompt. It needs read (r) and list (l) permission. It is
never printed, logged or written anywhere else, and error messages never contain it.

  from stage1 import azure_era5 as AZ
  ds = AZ.open_era5("1955-01", "1959-12")                   # one Dataset: valid_time (UTC) x latitude x longitude
  ds = AZ.open_era5("1956", variables=["t2m", "d2m"])       # a whole year, two variables
  store = AZ.Store()                                        # to reuse one listing for several calls
  store.months(); store.missing(1950, 2025); store.sync("1970", "1989"); store.fetch(1955, 1)

The transfer uses only the standard library. Opening needs xarray with h5netcdf or netCDF4; with dask installed,
long periods are opened lazily (one chunk per month), otherwise they are read into memory.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import http.client
import importlib.util
import os
import pathlib
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]   # the en_shock repository
TOKEN_FILE = pathlib.Path.home() / ".config" / "undrr" / "era5_sas_url"
DEFAULT_PREFIX = "hourly"
DEFAULT_LOCAL_DIR = ROOT / "data" / "shared" / "era5" / "hourly"
FILE_PATTERN = "era5_{year}_{month:02d}.nc"
_CHUNK = 1 << 20
_RETRY_CODES = (408, 429, 500, 502, 503, 504)
_NET_ERRORS = (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError, socket.timeout)


class AzureAccessError(RuntimeError):
    """Azure refused a request. The message never contains the token."""


class AzureUnreachable(AzureAccessError):
    """Azure could not be reached (no network, DNS, timeout)."""


class AzureIntegrityError(RuntimeError):
    """A download did not match Azure's size or MD5, or a local file differs from Azure's copy."""


# ----------------------------------------------------------------------------------------------- the token
def _clean(url: str) -> str:
    u = (url or "").strip()
    if len(u) >= 2 and u[0] == u[-1] and u[0] in "\"'":
        u = u[1:-1].strip()
    return u


def _validate(url: str) -> str:
    u = _clean(url)
    if re.search(r"\s", u):
        raise ValueError("the SAS URL contains spaces: paste only the 'Blob Container SAS URL' line")
    if not u.startswith("https://") and not (u.startswith("http://") and os.environ.get("ERA5_ALLOW_HTTP") == "1"):
        raise ValueError("the SAS URL must start with https://")
    if "?" not in u or "sig=" not in u.split("?", 1)[1]:
        raise ValueError("this is not a Blob Container SAS URL "
                         "(expected https://<account>.blob.core.windows.net/<container>?...&sig=...)")
    return u


def load_sas_url(sas_url: str | None = None, prompt: bool = True) -> tuple[str, str]:
    """(SAS URL, where it came from). See the module docstring for the order."""
    if sas_url:
        return _validate(sas_url), "the sas_url argument"
    env = os.environ.get("ERA5_SAS_URL", "").strip()
    if env:
        return _validate(env), "the ERA5_SAS_URL environment variable"
    if TOKEN_FILE.exists():
        if TOKEN_FILE.stat().st_mode & 0o077:
            warnings.warn(f"{TOKEN_FILE} can be read by other users of this computer; run: chmod 600 {TOKEN_FILE}",
                          stacklevel=3)
        return _validate(TOKEN_FILE.read_text(encoding="utf-8")), str(TOKEN_FILE).replace(str(pathlib.Path.home()), "~")
    if prompt:
        try:
            return _validate(getpass.getpass("Paste Blob SAS URL: ")), "the prompt"
        except (EOFError, KeyboardInterrupt):
            pass
    raise AzureAccessError("no SAS URL: run `python scripts/helpers/sync_era5_hourly.py set-token` once, "
                           "or set the ERA5_SAS_URL environment variable")


def save_sas_url(sas_url: str) -> pathlib.Path:
    """Write the SAS URL to TOKEN_FILE, readable only by you (mode 600)."""
    u = _validate(sas_url)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(TOKEN_FILE.parent, 0o700)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(u + "\n")
    os.chmod(TOKEN_FILE, 0o600)
    return TOKEN_FILE


def _expiry(se: str) -> datetime | None:
    if not se:
        return None
    s = se.replace("Z", "+00:00")
    if "T" not in s:
        s += "T00:00:00+00:00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ----------------------------------------------------------------------------------------------- months
def _month(spec, end: bool) -> pd.Timestamp:
    if isinstance(spec, tuple) and len(spec) == 2:
        return pd.Timestamp(int(spec[0]), int(spec[1]), 1)
    if isinstance(spec, (int,)) and not isinstance(spec, bool):
        return pd.Timestamp(spec, 12 if end else 1, 1)
    if isinstance(spec, (pd.Timestamp, datetime)):
        return pd.Timestamp(spec.year, spec.month, 1)
    s = str(spec).strip()
    if re.fullmatch(r"\d{4}", s):
        return pd.Timestamp(int(s), 12 if end else 1, 1)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
    raise ValueError(f"a month is YYYY-MM (or YYYY for a whole year), not {spec!r}")


def month_range(first, last=None) -> pd.DatetimeIndex:
    """Month starts from first to last. '1955' means 1955-01 as first and 1955-12 as last."""
    a = _month(first, end=False)
    b = _month(first if last is None else last, end=True)
    if b < a:
        raise ValueError(f"{b:%Y-%m} is before {a:%Y-%m}")
    return pd.date_range(a, b, freq="MS")


def _fmt_months(ts) -> str:
    """Compact list: 1956-12, 1960-01..1969-12, ..."""
    ts = sorted(pd.Timestamp(t) for t in ts)
    out, i = [], 0
    while i < len(ts):
        j = i
        while j + 1 < len(ts) and ts[j + 1] == ts[j] + pd.DateOffset(months=1):
            j += 1
        out.append(f"{ts[i]:%Y-%m}" if i == j else f"{ts[i]:%Y-%m}..{ts[j]:%Y-%m}")
        i = j + 1
    return ", ".join(out)


def default_local_dir() -> pathlib.Path:
    """paths.era5_hourly_dir of config.yaml when it is set, otherwise data/shared/era5/hourly."""
    try:
        from . import config as C
        p = C.path(C.load(), "era5_hourly_dir")
        if p is not None:
            return p
    except Exception:  # noqa: BLE001  (no config, no yaml: use the default)
        pass
    return DEFAULT_LOCAL_DIR


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) == 0:        # e.g. a python.org build on macOS without certificates
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
    return ctx


def _describe(code: int, body: bytes, where: str, source: str) -> str:
    c = msg = detail = None
    try:
        root = ET.fromstring(body)
        c = root.findtext("Code")
        msg = (root.findtext("Message") or "").strip().splitlines()[0] if root.findtext("Message") else None
        detail = (root.findtext("AuthenticationErrorDetail") or "").strip() or None
    except ET.ParseError:
        pass
    text = f"Azure refused the request to {where} (HTTP {code}{', ' + c if c else ''})"
    if msg:
        text += f": {msg}"
    if detail:
        text += f"\n  Azure detail: {' '.join(detail.split())[:300]}"
    if code in (401, 403):
        text += (f"\n  The SAS URL (from {source}) was rejected: it may have expired, been revoked or regenerated, "
                 "or been altered when pasted. Save a fresh one with `python scripts/helpers/sync_era5_hourly.py set-token`"
                 + (" (ERA5_SAS_URL is set and takes precedence over the saved one)" if "ERA5_SAS_URL" in source else "")
                 + ".")
    elif code == 404 and c == "ContainerNotFound":
        text += "\n  The container in the SAS URL does not exist."
    return text


# ----------------------------------------------------------------------------------------------- the store
@dataclass(frozen=True)
class Blob:
    name: str            # e.g. hourly/1955/era5_1955_01.nc
    year: int
    month: int
    size: int
    md5: str | None      # base64 MD5 that Azure holds for the blob (None if it holds none)

    @property
    def filename(self) -> str:
        return FILE_PATTERN.format(year=self.year, month=self.month)


class Store:
    """The hourly ERA5 blobs of one container, and their local copies."""

    def __init__(self, sas_url: str | None = None, prefix: str = DEFAULT_PREFIX, local_dir=None,
                 timeout: float = 120, prompt: bool = True):
        url, self.token_source = load_sas_url(sas_url, prompt=prompt)
        base, _, token = url.partition("?")
        self._base, self._token = base.rstrip("/"), token
        p = urllib.parse.urlparse(self._base)
        self.location = f"{p.hostname}{p.path}"
        q = urllib.parse.parse_qs(token)
        self.permissions = q.get("sp", [""])[0]
        self.expires = _expiry(q.get("se", [""])[0])
        if self.permissions and not ("r" in self.permissions and "l" in self.permissions):
            warnings.warn(f"the SAS token has permissions '{self.permissions}': reading needs r and l", stacklevel=2)
        if self.expires and self.expires < datetime.now(timezone.utc):
            warnings.warn(f"the SAS token expired on {self.expires:%Y-%m-%d %H:%M} UTC", stacklevel=2)
        self.prefix = prefix.strip("/")
        self.local_dir = pathlib.Path(os.path.expanduser(str(local_dir))) if local_dir else default_local_dir()
        if not self.local_dir.is_absolute():
            self.local_dir = ROOT / self.local_dir
        self.timeout = timeout
        self._ctx = _ssl_context()
        self._index: dict[tuple[int, int], Blob] | None = None
        self._print_lock = threading.Lock()

    def __repr__(self) -> str:
        return f"Store('{self.location}/{self.prefix}/', local_dir='{self.local_dir}')"

    # ------------------------------------------------------------------------------------ HTTP
    def _url(self, blob_name: str | None = None, query: str = "") -> str:
        u = self._base + ("/" + urllib.parse.quote(blob_name, safe="/") if blob_name else "")
        return u + "?" + self._token + ("&" + query if query else "")

    def _open(self, url: str, what: str):
        """urlopen with retries; errors are re-raised without the URL (which holds the token)."""
        req = urllib.request.Request(url, method="GET")
        for attempt in range(1, 5):
            try:
                return urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx)
            except urllib.error.HTTPError as e:
                code, body = e.code, e.read()[:8000]
                e.close()
                if code in _RETRY_CODES and attempt < 4:
                    time.sleep(2 * attempt)
                    continue
                raise AzureAccessError(_describe(code, body, what, self.token_source)) from None
            except _NET_ERRORS as e:
                if attempt < 4:
                    time.sleep(2 * attempt)
                    continue
                reason = getattr(e, "reason", None) or e.__class__.__name__
                raise AzureUnreachable(f"cannot reach {self.location} ({reason})") from None
        raise AssertionError("unreachable")

    # ------------------------------------------------------------------------------------ listing
    def blobs(self, refresh: bool = False) -> dict[tuple[int, int], Blob]:
        """{(year, month): Blob} for every era5_YYYY_MM.nc under the prefix. Listed once per Store."""
        if self._index is not None and not refresh:
            return self._index
        rx = re.compile(rf"^{re.escape(self.prefix)}/(\d{{4}})/era5_(\d{{4}})_(\d{{2}})\.nc$")
        idx, marker = {}, ""
        while True:
            q = f"restype=container&comp=list&maxresults=5000&prefix={urllib.parse.quote(self.prefix + '/', safe='')}"
            if marker:
                q += "&marker=" + urllib.parse.quote(marker, safe="")
            with self._open(self._url(query=q), f"{self.location} (listing)") as r:
                root = ET.fromstring(r.read())
            for b in root.iter("Blob"):
                m = rx.match(b.findtext("Name") or "")
                if not m or m.group(1) != m.group(2) or not 1 <= int(m.group(3)) <= 12:
                    continue
                props = b.find("Properties")
                size = int(props.findtext("Content-Length") or -1) if props is not None else -1
                md5 = ((props.findtext("Content-MD5") or "").strip() or None) if props is not None else None
                y, mo = int(m.group(2)), int(m.group(3))
                idx[(y, mo)] = Blob(m.group(0), y, mo, size, md5)
            marker = (root.findtext("NextMarker") or "").strip()
            if not marker:
                break
        self._index = dict(sorted(idx.items()))
        return self._index

    def months(self) -> pd.DatetimeIndex:
        """The months in Azure."""
        return pd.DatetimeIndex([pd.Timestamp(y, m, 1) for (y, m) in self.blobs()])

    def missing(self, first, last=None) -> pd.DatetimeIndex:
        """The months from first to last that are not in Azure."""
        have = self.blobs()
        return pd.DatetimeIndex([t for t in month_range(first, last) if (t.year, t.month) not in have])

    # ------------------------------------------------------------------------------------ local copies
    def local_path(self, year: int, month: int) -> pathlib.Path:
        return self.local_dir / FILE_PATTERN.format(year=year, month=month)

    def local_months(self) -> pd.DatetimeIndex:
        """The months with a local copy (whether or not it matches Azure)."""
        rx = re.compile(r"^era5_(\d{4})_(\d{2})\.nc$")
        out = []
        if self.local_dir.exists():
            for f in self.local_dir.iterdir():
                m = rx.match(f.name)
                if m and 1 <= int(m.group(2)) <= 12:
                    out.append(pd.Timestamp(int(m.group(1)), int(m.group(2)), 1))
        return pd.DatetimeIndex(sorted(out))

    def _state(self, blob: Blob) -> str:
        """'current', 'absent' or 'differs' for the local copy of a blob."""
        p = self.local_path(blob.year, blob.month)
        if not p.exists():
            return "absent"
        return "current" if p.stat().st_size == blob.size else "differs"

    def _download(self, blob: Blob) -> pathlib.Path:
        path = self.local_path(blob.year, blob.month)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        problem = ""
        for attempt in range(1, 4):
            ok = False
            try:
                h, n = _md5(), 0
                try:
                    with self._open(self._url(blob.name), blob.name) as r, open(part, "wb") as f:
                        header_md5 = r.headers.get("Content-MD5")
                        while True:
                            chunk = r.read(_CHUNK)
                            if not chunk:
                                break
                            f.write(chunk)
                            h.update(chunk)
                            n += len(chunk)
                except _NET_ERRORS as e:
                    problem = f"connection lost ({getattr(e, 'reason', None) or e.__class__.__name__})"
                    time.sleep(3 * attempt)
                    continue
                want = blob.md5 or header_md5
                got = base64.b64encode(h.digest()).decode()
                if n != blob.size:
                    problem = f"received {n} bytes, Azure lists {blob.size}"
                elif want and got != want:
                    problem = "MD5 does not match the one Azure holds"
                else:
                    os.replace(part, path)
                    ok = True
                    return path
            finally:
                if not ok:
                    part.unlink(missing_ok=True)
        raise AzureIntegrityError(f"{blob.filename}: {problem} (3 attempts; nothing was kept)")

    def fetch(self, year: int, month: int, refresh: bool = False) -> pathlib.Path:
        """Local path of one month, downloaded first if it is not here yet (refresh=True: download it again)."""
        path = self.local_path(year, month)
        try:
            blob = self.blobs().get((year, month))
        except AzureUnreachable as e:
            if path.exists():
                warnings.warn(f"{e}: using the local {path.name} without checking it against Azure", stacklevel=2)
                return path
            raise
        if blob is None:
            if path.exists():
                warnings.warn(f"{path.name} is not in Azure; using the local copy", stacklevel=2)
                return path
            raise FileNotFoundError(f"{year}-{month:02d} is not in Azure ({self.location}/{self.prefix}/{year}/)")
        state = self._state(blob)
        if state == "current" and not refresh:
            return path
        if state == "differs" and not refresh:
            raise AzureIntegrityError(
                f"{path} differs from Azure's copy ({path.stat().st_size} bytes here, {blob.size} in Azure) and was "
                "left alone. Replace it with fetch(..., refresh=True) or `sync --refresh`, or move it away first.")
        return self._download(blob)

    def _say(self, verbose: bool, text: str) -> None:
        if verbose:
            with self._print_lock:
                print(text, flush=True)

    def _fetch_many(self, blobs: list[Blob], workers: int, verbose: bool) -> tuple[list[Blob], dict[str, str]]:
        done, failed = [], {}
        if not blobs:
            return done, failed
        total_mb = sum(b.size for b in blobs) / 1e6
        self._say(verbose, f"Downloading {len(blobs)} month(s), {total_mb:,.0f} MB, from {self.location} "
                           f"to {self.local_dir} ...")
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {ex.submit(self._download, b): b for b in blobs}
            for i, fut in enumerate(as_completed(futs), 1):
                b = futs[fut]
                try:
                    fut.result()
                    done.append(b)
                    self._say(verbose, f"  [{i}/{len(blobs)}] {b.filename}  {b.size / 1e6:.1f} MB  ok")
                except (AzureAccessError, AzureIntegrityError, OSError) as e:
                    failed[b.filename] = str(e)
                    self._say(verbose, f"  [{i}/{len(blobs)}] {b.filename}  FAILED: {e}")
        mb = sum(b.size for b in done) / 1e6
        self._say(verbose, f"  {len(done)} downloaded ({mb:,.0f} MB in {time.time() - t0:.0f} s), {len(failed)} failed")
        return done, failed

    def sync(self, first=None, last=None, workers: int = 4, refresh: bool = False, verbose: bool = True) -> dict:
        """Copy the months from first to last (default: every month in Azure) that are not here yet.

        A local file that differs from Azure's copy is reported and left alone; refresh=True replaces it.
        Returns a summary dict: downloaded, present, differs, failed, missing_in_azure.
        """
        idx = self.blobs(refresh=True)
        if first is None:
            wanted, absent_in_azure = list(idx.values()), []
        else:
            months = month_range(first, last)
            wanted = [idx[(t.year, t.month)] for t in months if (t.year, t.month) in idx]
            absent_in_azure = [t for t in months if (t.year, t.month) not in idx]
        states = {b: self._state(b) for b in wanted}
        todo = [b for b in wanted if states[b] == "absent" or (refresh and states[b] == "differs")]
        differs = [b for b in wanted if states[b] == "differs" and not refresh]
        present = sum(1 for b in wanted if states[b] == "current")
        if verbose:
            print(f"{len(wanted)} month(s) in Azure for this period; {present} already here, {len(todo)} to download"
                  + (f", {len(differs)} differ from Azure" if differs else ""))
        for b in differs:
            self._say(verbose, f"  DIFFERS {b.filename}: the local file is not Azure's version; left alone "
                               "(use --refresh to replace it)")
        done, failed = self._fetch_many(todo, workers, verbose)
        if absent_in_azure and verbose:
            print(f"Not in Azure: {_fmt_months(absent_in_azure)}")
        return {"downloaded": [b.filename for b in done], "present": present,
                "differs": [b.filename for b in differs], "failed": failed,
                "missing_in_azure": [f"{t:%Y-%m}" for t in absent_in_azure]}

    # ------------------------------------------------------------------------------------ opening
    def paths(self, first, last=None, allow_missing: bool = False, workers: int = 4,
              verbose: bool = True) -> list[pathlib.Path]:
        """Local paths of the months from first to last, downloading those that are not here yet."""
        months = month_range(first, last)
        try:
            idx = self.blobs()
        except AzureUnreachable as e:
            idx = None
            warnings.warn(f"{e}: using the local copies only, unchecked", stacklevel=2)
        out, gaps, todo = {}, [], []
        for t in months:
            key, local = (t.year, t.month), self.local_path(t.year, t.month)
            blob = idx.get(key) if idx is not None else None
            if blob is not None:
                state = self._state(blob)
                if state == "differs":
                    raise AzureIntegrityError(
                        f"{local} differs from Azure's copy ({local.stat().st_size} bytes here, {blob.size} in Azure). "
                        "Replace it with Store().fetch(year, month, refresh=True), or move it away.")
                if state == "absent":
                    todo.append(blob)
                out[t] = local
            elif local.exists():
                if idx is not None:
                    warnings.warn(f"{local.name} is not in Azure; using the local copy", stacklevel=2)
                out[t] = local
            else:
                gaps.append(t)
        if gaps and not allow_missing:
            where = "not in Azure" if idx is not None else "not here, and Azure cannot be reached to get them"
            raise FileNotFoundError(f"{len(gaps)} of {len(months)} months are {where}: {_fmt_months(gaps)}. "
                                    "Pass allow_missing=True to use the others.")
        if gaps:
            warnings.warn(f"{len(gaps)} months are missing and left out: {_fmt_months(gaps)}", stacklevel=2)
        done, failed = self._fetch_many(todo, workers, verbose)
        if failed:
            raise AzureIntegrityError(f"{len(failed)} download(s) failed: " + "; ".join(failed.values()))
        return [out[t] for t in sorted(out)]

    def open(self, first, last=None, variables=None, allow_missing: bool = False, workers: int = 4,
             verbose: bool = True):
        """The months from first to last as one xarray Dataset along valid_time (UTC), downloading as needed.

        variables: e.g. ["t2m", "d2m"] (default: all). Missing months raise FileNotFoundError unless
        allow_missing=True, in which case they are left out (the time axis then has a gap).
        """
        paths = self.paths(first, last, allow_missing=allow_missing, workers=workers, verbose=verbose)
        if not paths:
            raise FileNotFoundError("no months to open")
        return open_files(paths, variables=variables)


def _md5():
    try:
        return hashlib.md5(usedforsecurity=False)
    except TypeError:
        return hashlib.md5()


def _engine_for(path: pathlib.Path):
    """The first engine that opens the file (h5netcdf, then netCDF4, then xarray's default), as stage1.era5.open_any."""
    import xarray as xr

    errors = []
    for engine in ("h5netcdf", "netcdf4", None):
        try:
            with xr.open_dataset(path, engine=engine) as ds:
                return engine, ("valid_time" if "valid_time" in ds.dims else "time"), list(ds.data_vars)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{engine or 'default'}: {e.__class__.__name__}: {e}")
    raise OSError(f"cannot open {path} (install h5netcdf + h5py, or netCDF4):\n  " + "\n  ".join(errors))


def open_files(paths, variables=None):
    """Open local era5_YYYY_MM.nc files as one Dataset along their time axis (lazily when dask is installed)."""
    import xarray as xr

    paths = [pathlib.Path(p) for p in paths]
    engine, tdim, names = _engine_for(paths[0])
    drop = None
    if variables is not None:
        variables = [variables] if isinstance(variables, str) else list(variables)
        unknown = [v for v in variables if v not in names]
        if unknown:
            raise KeyError(f"{', '.join(unknown)} not in the files (they have {', '.join(names)})")
        drop = [v for v in names if v not in variables]
    if len(paths) == 1:
        ds = xr.open_dataset(paths[0], engine=engine, drop_variables=drop)
    elif importlib.util.find_spec("dask") is not None:
        ds = xr.open_mfdataset(paths, engine=engine, combine="nested", concat_dim=tdim, data_vars="minimal",
                               coords="minimal", compat="override", drop_variables=drop, chunks={})
    else:
        if len(paths) > 24:
            n_vars = len(variables) if variables is not None else len(names)
            gb = len(paths) * 744 * 69 * 45 * 4 * n_vars / 1e9
            warnings.warn(f"dask is not installed, so all {len(paths)} months are read into memory (about {gb:.1f} GB). "
                          "`pip install dask` opens them lazily instead.", stacklevel=3)
        parts = []
        for p in paths:
            with xr.open_dataset(p, engine=engine, drop_variables=drop) as d:
                parts.append(d.load())
        ds = xr.concat(parts, dim=tdim, data_vars="minimal", coords="minimal", compat="override")
    t = ds.indexes[tdim]
    if not (t.is_monotonic_increasing and t.is_unique):
        warnings.warn(f"{tdim} is not strictly increasing across the files: check for overlapping months", stacklevel=3)
    return ds


def open_era5(first, last=None, variables=None, allow_missing: bool = False, workers: int = 4, verbose: bool = True,
              **store_kwargs):
    """One call: Store(**store_kwargs).open(...). store_kwargs: sas_url, prefix, local_dir, timeout. See Store.open."""
    return Store(**store_kwargs).open(first, last, variables=variables, allow_missing=allow_missing,
                                      workers=workers, verbose=verbose)


if __name__ == "__main__":
    sys.exit("This is a module. Use scripts/helpers/sync_era5_hourly.py, or `from stage1 import azure_era5` in Python.")
