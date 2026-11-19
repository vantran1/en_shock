"""Resumable downloader for public IEMOP market data (electricity channel, tracker G3).
Downloads only: files are saved unchanged, no processing.

Files (base https://www.iemop.ph/wp-content/uploads/downloads/data/):
- finallwap/final_lwap_YYYYMMDD.csv   load-weighted average prices, final (daily)
- RTDREG/RTDREG_YYYYMMDD.csv          RTD regional summaries (daily)
- AP/AP_YYYYMMDDHH00.zip              hourly files, only with --ap

Saved to ~/data_tmp/electricity/raw/iemop/<folder>/ (outside the repo and outside iCloud;
--out to change). Resumable: files that already exist are skipped, and each download is
written to a .part file and renamed only when complete, so an interrupted run leaves no
partial files. One request per second; network errors and server errors (5xx) are retried 3
times; 404 means "not published yet" and is logged, not retried. Every attempt is appended to
<out>/download_log.csv: file, status, bytes, time.

Run:  python3 scripts/download_iemop.py [--start 2026-08-21] [--end YYYY-MM-DD] [--ap] [--out DIR]
      (end defaults to today)
"""
import argparse
import csv
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = "https://www.iemop.ph/wp-content/uploads/downloads/data/"
DAILY = {"finallwap": "final_lwap_{d:%Y%m%d}.csv", "RTDREG": "RTDREG_{d:%Y%m%d}.csv"}
HOURLY = {"AP": "AP_{d:%Y%m%d}{h:02d}00.zip"}
OUT = Path.home() / "data_tmp" / "electricity" / "raw" / "iemop"
PAUSE_S = 1.0
RETRIES = 3
TIMEOUT_S = 60
HEADERS = {"User-Agent": "Mozilla/5.0 (research download; UNDRR El Nino project)"}


def targets(start: date, end: date, ap: bool):
    """(folder, file name) for every file in the date range."""
    d = start
    while d <= end:
        for folder, pat in DAILY.items():
            yield folder, pat.format(d=d)
        if ap:
            for folder, pat in HOURLY.items():
                for h in range(24):
                    yield folder, pat.format(d=d, h=h)
        d += timedelta(days=1)


def fetch(url: str) -> tuple[str, bytes | None]:
    """Status and content: 'ok', 'not_published' (404), 'http_<code>' or 'network_error'
    after the retries."""
    for attempt in range(1, RETRIES + 2):  # first try + 3 retries
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return "ok", r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "not_published", None
            if e.code < 500 or attempt > RETRIES:
                return f"http_{e.code}", None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt > RETRIES:
                return "network_error", None
        time.sleep(PAUSE_S * attempt)  # wait a little longer before each retry
    return "network_error", None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default="2026-08-21", help="first date, YYYY-MM-DD (default 2026-08-21)")
    ap.add_argument("--end", default=date.today().isoformat(), help="last date, YYYY-MM-DD (default today)")
    ap.add_argument("--ap", action="store_true", help="also download the hourly AP zip files")
    ap.add_argument("--out", default=str(OUT), help=f"output folder (default {OUT})")
    a = ap.parse_args()
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "download_log.csv"
    new_log = not log_path.exists()
    counts = {}
    with open(log_path, "a", newline="") as lf:
        log = csv.writer(lf)
        if new_log:
            log.writerow(["file", "status", "bytes", "time"])
        for folder, name in targets(start, end, a.ap):
            dest = out / folder / name
            rel = f"{folder}/{name}"
            if dest.exists() and dest.stat().st_size > 0:
                counts["exists"] = counts.get("exists", 0) + 1
                continue  # skipped without a request
            dest.parent.mkdir(parents=True, exist_ok=True)
            status, content = fetch(BASE + rel)
            n = 0
            if status == "ok":
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(content)
                tmp.rename(dest)
                n = len(content)
            log.writerow([rel, status, n, datetime.now().isoformat(timespec="seconds")])
            lf.flush()
            counts[status] = counts.get(status, 0) + 1
            print(f"{status:14s} {n:>10,d}  {rel}")
            time.sleep(PAUSE_S)
    print("summary:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), f"| log: {log_path}")


if __name__ == "__main__":
    main()
