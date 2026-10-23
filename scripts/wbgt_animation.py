#!/usr/bin/env python3
"""
Compute hourly WBGT from monthly ERA5 single-levels files (see download_era5.py)
with pywbgt and animate it, for outdoor and indoor settings.

  outdoor : Liljegren et al. (2008) - physically based, includes sun and wind
  indoor  : Bernard & Pourmoghani (1999) with ZERO solar load, so the globe
            temperature equals air temperature (no radiant heat source)

The monthly files also contain total precipitation (tp). It is an auxiliary
download for separate precipitation analyses: this script does not load it and
it never enters the WBGT calculation.

Outputs (in --outdir):
  wbgt_YYYY_MM.nc                  hourly WBGT (deg C) for both settings
  wbgt_outdoor_YYYY_MM.mp4|gif     animation, outdoor
  wbgt_indoor_YYYY_MM.mp4|gif      animation, indoor

Usage:
  python wbgt_animation.py --indir era5_wbgt --year 2024 --month 4
  python wbgt_animation.py --indir era5_wbgt --year 2024 --month 4 --max-frames 48   # quick look
  python wbgt_animation.py --indir era5_wbgt --year 2024 --month 4 --reuse           # skip recompute

Requirements:
  pip install pywbgt metpy xarray netCDF4 matplotlib numpy pandas
  ffmpeg on PATH for .mp4 (otherwise the script falls back to .gif via Pillow)

Conventions handled here:
  * valid_time is in UTC and marks the END of each hour.
  * ssrd (J m-2) in ERA5 single levels is accumulated over the single hour ENDING
    at valid_time (unlike ERA5-Land, which accumulates from 00 UTC). The hourly-mean
    flux in W m-2 is therefore simply ssrd / 3600; no differencing and no
    previous-month file are needed, and no hour is dropped.
  * pywbgt reads the timestamp as the END of the averaging window and evaluates
    the sun at the window midpoint, so valid_time is passed unchanged with
    avg=60 minutes. Instantaneous fields (t2m, d2m, sp, u10, v10) are used as
    stamped.
  * ERA5 single levels has values over the ocean as well as land, so WBGT is
    computed (and animated) for sea cells too.
  * pywbgt's default clips the 2 m wind to 2 knots (~1.03 m/s); change it with
    --min-speed (m/s) if you want calmer hours represented.
  * Wind height. pywbgt converts the 10 m wind to 2 m internally, but in version
    3.0.7 its Cython wrapper (liljegren.pyx) sets the internal day/night flag to
    "day" when the sun is up and never resets it, so night-time results depend on
    the order/chunking of the input (up to ~0.04 C; day-time results are
    unaffected). By default this script therefore applies the same Liljegren
    stability-class power law itself, with a correct flag, and passes the 2 m
    wind to pywbgt. It matches pywbgt to 6e-5 C wherever pywbgt is correct and is
    independent of chunking and thread count. Use --native-wind to reproduce
    pywbgt's own adjustment (e.g. for the pywbgt vs PyWBGT comparison).
"""
import argparse
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib import animation, cm
from matplotlib.collections import LineCollection

# The only variables that feed the WBGT calculation. tp (precipitation) is
# deliberately absent: it is in the files for other analyses and is dropped on load.
REQUIRED = ["t2m", "d2m", "sp", "u10", "v10", "ssrd"]

INK, INK2, GRID, SEA = "#222222", "#5f5f5f", "#d9d8d4", "#e9e8e4"


# ----------------------------------------------------------------------------
# Loading and preparation
# ----------------------------------------------------------------------------
def open_month(path):
    ds = xr.open_dataset(path)
    if "time" in ds.dims and "valid_time" not in ds.dims:
        ds = ds.rename({"time": "valid_time"})
    missing = [v for v in REQUIRED if v not in ds]
    if missing:
        sys.exit(f"{path.name} is missing variables {missing}; found {list(ds.data_vars)}")
    ds = ds[REQUIRED]  # keep only the WBGT inputs: tp and anything else is not loaded
    if "expver" in ds.dims:  # ERA5T/ERA5 mix: merge the two experiment versions
        ds = ds.sel(expver=ds.expver.values[0]).combine_first(ds.sel(expver=ds.expver.values[-1]))
    ds = ds.drop_vars([c for c in ("number", "expver") if c in ds.coords and c not in ds.dims])
    ds = ds.sortby("valid_time")
    return ds.sortby("latitude", ascending=False).load()


def hourly_solar(ds):
    """Hourly-mean solar flux (W m-2) for the hour ENDING at valid_time.

    ERA5 single-levels ssrd (J m-2) is already accumulated over that one hour."""
    flux = ds["ssrd"] / 3600.0
    return flux.clip(min=0.0)  # remove tiny negative values from floating-point noise


# ----------------------------------------------------------------------------
# WBGT
# ----------------------------------------------------------------------------
# Liljegren et al. (2008) wind-height adjustment, as implemented in pywbgt's C code (rural, dT = -1 C defaults).
# pywbgt 3.0.7's Cython wrapper does this internally but sets its day/night flag to "day" when the sun is up
# and never resets it at night, so night-time results depend on the order and chunking of the input
# (up to ~0.04 C here). We therefore do the adjustment here with a correct flag and pass the 2 m wind.
_STAB = np.array([[1, 1, 2, 4, 0, 5, 6, 0],
                  [1, 2, 3, 4, 0, 5, 6, 0],
                  [2, 2, 3, 4, 0, 4, 4, 0],
                  [3, 3, 4, 4, 0, 0, 0, 0],
                  [3, 4, 4, 4, 0, 0, 0, 0]])
_RURAL_EXP = np.array([0.07, 0.07, 0.10, 0.15, 0.35, 0.55])


def wind_2m(speed10, solar_adj, cza, min_speed):
    """10 m wind -> 2 m wind (m/s) with the Liljegren stability-class power law; arrays of equal shape."""
    day = cza > 0.0
    i_day = np.select([speed10 >= 6.0, speed10 >= 5.0, speed10 >= 3.0, speed10 >= 2.0], [4, 3, 2, 1], 0)
    j_day = np.select([solar_adj >= 925.0, solar_adj >= 675.0, solar_adj >= 175.0], [0, 1, 2], 3)
    i_night = np.select([speed10 >= 2.5, speed10 >= 2.0], [2, 1], 0)
    j_night = 5  # dT = -1 C (pywbgt default) -> unstable night column; dT >= 0 would be column 6
    cls = np.where(day, _STAB[i_day, j_day], _STAB[i_night, j_night])
    est = speed10 * (2.0 / 10.0) ** _RURAL_EXP[cls - 1]
    return np.maximum(est, min_speed)


def _wind_2m_grid(d, flux, speed10, min_eff):
    """2 m wind on the (time, lat, lon) grid, using pywbgt's own solar-position routine for the day/night flag."""
    from pywbgt.solar import solar_parameters

    nt, ny, nx = speed10.shape
    t = np.repeat(d["valid_time"].values, ny * nx)
    lat = np.tile(np.repeat(d["latitude"].values, nx), nt)
    lon = np.tile(np.tile(d["longitude"].values, ny), nt)
    solar_adj, cza, _ = solar_parameters(t, lat, lon, np.nan_to_num(flux.values.ravel().astype("float64")),
                                         None, 60.0)
    solar_adj = np.asarray(solar_adj).reshape(speed10.shape)
    cza = np.asarray(cza).reshape(speed10.shape)
    return wind_2m(speed10, solar_adj, cza, min_eff)


def compute_wbgt(ds, flux, min_speed, chunk_hours=168, native_wind=False):
    """Outdoor (Liljegren) and indoor (Bernard, solar = 0) WBGT in deg C.

    Only the REQUIRED variables are used; precipitation never enters the calculation.
    Hours are processed in chunks of `chunk_hours` to keep memory bounded; each
    hour is independent, so the chunking does not change the results."""
    from metpy.units import units
    from pywbgt import wbgt

    def build(d, solar, speed):
        inp = xr.Dataset({
            "solar": solar.astype("float64"),
            "pres": d["sp"].astype("float64"),
            "temp_air": d["t2m"].astype("float64"),
            "temp_dew": d["d2m"].astype("float64"),
            "speed": speed.astype("float64"),
        })
        for name, unit in (("solar", "W/m^2"), ("pres", "Pa"), ("temp_air", "K"),
                           ("temp_dew", "K"), ("speed", "m/s")):
            inp[name].attrs["units"] = unit
        inp = inp.metpy.quantify()
        inp["valid_time"].attrs["axis"] = "T"
        inp["latitude"].attrs["axis"] = "Y"
        inp["longitude"].attrs["axis"] = "X"
        return inp

    kw = {"avg": 60.0}
    min_eff = max(1.0288889 if min_speed is None else min_speed, 0.13)  # pywbgt: 2 knots by default, floor 0.13 m/s
    if min_speed is not None:
        kw["min_speed"] = units.Quantity(min_speed, "m/s")

    def celsius(da):
        da = da.reset_coords(drop=True)  # drop pywbgt's scalar 'min_speed' coordinate
        return da.metpy.convert_units("degC").metpy.dequantify().astype("float32")

    nt = ds.sizes["valid_time"]
    pieces = []
    for i0 in range(0, nt, chunk_hours):
        sl = slice(i0, min(i0 + chunk_hours, nt))
        d, f = ds.isel(valid_time=sl), flux.isel(valid_time=sl)
        print(f"  WBGT for hours {sl.start + 1}-{sl.stop} of {nt} ...")
        speed10 = np.hypot(d["u10"], d["v10"])
        if native_wind:                                               # pywbgt's built-in 10 m -> 2 m adjustment
            out = wbgt(build(d, f, speed10), method="liljegren", **kw)
        else:                                                         # corrected adjustment, then pass 2 m wind
            sp2 = speed10.copy(data=_wind_2m_grid(d, f, speed10.values, min_eff))
            out = wbgt(build(d, f, sp2), method="liljegren", zspeed=units.Quantity(2.0, "m"), **kw)
        ind = wbgt(build(d, f * 0.0, speed10), method="bernard", **kw)  # indoor: no solar load
        pieces.append(xr.Dataset({"wbgt_outdoor": celsius(out["Twbg"]),
                                  "wbgt_indoor": celsius(ind["Twbg"])}))
        del out, ind

    res = xr.concat(pieces, dim="valid_time")
    res = res.where(np.isfinite(ds["t2m"]))  # mask any no-data cells
    res["wbgt_outdoor"].attrs = {"units": "degC", "long_name": "Outdoor WBGT (Liljegren et al. 2008, pywbgt)"}
    res["wbgt_indoor"].attrs = {"units": "degC", "long_name": "Indoor WBGT (Bernard & Pourmoghani 1999, pywbgt, no solar load)"}
    res.attrs = {
        "source": "ERA5 single levels hourly (t2m, d2m, sp, u10, v10, ssrd); precipitation not used",
        "time_convention": "valid_time is UTC and marks the end of each hour",
        "solar": "ssrd (hourly accumulation) / 3600 = hourly-mean W m-2; pywbgt avg=60 min",
        "min_speed_m_s": "1.0289 (pywbgt default, 2 knots)" if min_speed is None else str(max(min_speed, 0.13)),
    }
    return res.transpose("valid_time", "latitude", "longitude")


# ----------------------------------------------------------------------------
# Animation
# ----------------------------------------------------------------------------
def tz_label(offset):
    return "PHT" if offset == 8 else f"UTC{offset:+d}"


def philippines_outline():
    """Coastline of the Philippines as a list of (N, 2) lon/lat arrays, or None if unavailable.

    Uses the Natural Earth 1:50m country polygons through regionmask. On first use
    regionmask downloads the shapefile (a few MB) and caches it, so the first run
    needs internet access; later runs work offline."""
    try:
        import regionmask
    except ImportError:
        print("note: regionmask is not installed, so the Philippines boundary is not drawn "
              "(pip install regionmask)")
        return None
    countries = None
    for version in ("natural_earth_v5_1_2", "natural_earth_v5_0_0"):
        try:
            countries = getattr(regionmask.defined_regions, version).countries_50
            break
        except Exception as exc:  # missing version or no internet on the first run
            err = exc
    if countries is None:
        print(f"note: could not load the country boundaries ({err}); drawing without the Philippines boundary")
        return None
    names = list(countries.names)
    if "Philippines" not in names:
        print("note: 'Philippines' not found in the country boundaries; drawing without it")
        return None
    poly = countries.polygons[names.index("Philippines")]
    parts = poly.geoms if hasattr(poly, "geoms") else [poly]  # MultiPolygon: one entry per island group
    return [np.asarray(p.exterior.coords) for p in parts]


def animate(res, var, title, subtitle, out_path, fps, vmin, vmax, tz_offset, max_frames, dpi, writer_name,
            outline=None):
    da = res[var]
    lat, lon = da.latitude.values, da.longitude.values
    nt = da.sizes["valid_time"] if max_frames is None else min(max_frames, da.sizes["valid_time"])
    dlat = abs(lat[1] - lat[0]) if lat.size > 1 else 0.25
    dlon = abs(lon[1] - lon[0]) if lon.size > 1 else 0.25
    extent = (lon.min() - dlon / 2, lon.max() + dlon / 2, lat.min() - dlat / 2, lat.max() + dlat / 2)

    times_utc = pd.DatetimeIndex(da.valid_time.values)
    times_loc = times_utc + pd.Timedelta(hours=tz_offset)
    mean_series = np.nanmean(da.values, axis=(1, 2))

    mid_lat = 0.5 * (extent[2] + extent[3])
    aspect = 1.0 / np.cos(np.deg2rad(mid_lat))
    w_deg, h_deg = extent[1] - extent[0], extent[3] - extent[2]
    ratio = h_deg / (w_deg * aspect)  # map height / width

    # deterministic pixel layout: header | map + colourbar | time series
    W = 720
    left, top, ts_h, gap, bottom = 78, 84, 130, 66, 52
    map_w = 520
    map_h = map_w * ratio
    if map_h > 640:  # very tall domains: cap the height, narrow the map
        map_h = 640
        map_w = map_h / ratio
    map_w, map_h = int(round(map_w)), int(round(map_h))
    H = int(round((top + map_h + gap + ts_h + bottom) / 2) * 2)  # even pixel dimensions for h264

    def rect(x, y_from_top, w, h):  # pixels -> figure fractions
        return [x / W, 1 - (y_from_top + h) / H, w / W, h / H]

    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi, facecolor="white")
    ax = fig.add_axes(rect(left, top, map_w, map_h))
    cax = fig.add_axes(rect(left + map_w + 16, top, 14, map_h))
    ts = fig.add_axes(rect(left, top + map_h + gap, map_w + 30, ts_h))

    cmap = matplotlib.colormaps["Oranges"].copy()  # one hue, light -> dark = low -> high
    cmap.set_bad(SEA)
    im = ax.imshow(da.isel(valid_time=0).values, extent=extent, origin="upper", cmap=cmap,
                   vmin=vmin, vmax=vmax, interpolation="nearest", aspect=aspect, zorder=2)
    if outline:  # Philippine coastline, drawn above the data; the axes keep the data extent
        ax.add_collection(LineCollection(outline, colors=INK, linewidths=0.6, zorder=3))
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
    ax.set_xlabel("Longitude (°E)", color=INK2, fontsize=8)
    ax.set_ylabel("Latitude (°N)", color=INK2, fontsize=8)
    ax.tick_params(colors=INK2, labelsize=8, length=2)
    ax.grid(True, color=GRID, lw=0.5)
    ax.set_axisbelow(True)  # grid stays behind the data
    for sp_ in ax.spines.values():
        sp_.set_color(GRID)

    cb = fig.colorbar(im, cax=cax)
    cb.set_label("WBGT (°C)", color=INK2, fontsize=9)
    cb.locator = matplotlib.ticker.MaxNLocator(nbins=8, integer=True)
    cb.update_ticks()
    cb.ax.tick_params(colors=INK2, labelsize=8, length=2)
    cb.outline.set_edgecolor(GRID)

    fig.text(left / W, 1 - 24 / H, title, fontsize=13, fontweight="bold", color=INK, va="center")
    fig.text(left / W, 1 - 44 / H, subtitle, fontsize=8.5, color=INK2, va="center")
    stamp = fig.text(left / W, 1 - 62 / H, "", fontsize=10, color=INK, va="center")

    xs = mdates.date2num(times_loc.to_pydatetime())
    ts.plot(xs, mean_series, color=cmap(0.78), lw=1.4)
    ts.set_xlim(xs[0], xs[-1])
    pad = 0.5
    ts.set_ylim(np.nanmin(mean_series) - pad, np.nanmax(mean_series) + pad)
    ts.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    ts.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ts.tick_params(colors=INK2, labelsize=8, length=2)
    ts.set_ylabel("Domain mean (°C)", color=INK2, fontsize=8)
    ts.grid(True, color=GRID, lw=0.5)
    for s in ("top", "right"):
        ts.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ts.spines[s].set_color(GRID)
    cursor = ts.axvline(xs[0], color=INK, lw=0.9)
    dot, = ts.plot([xs[0]], [mean_series[0]], "o", ms=5, color=cmap(0.9), mec="white", mew=1.2)

    tzl = tz_label(tz_offset)

    def update(i):
        im.set_data(da.isel(valid_time=i).values)
        t_loc, t_utc = times_loc[i], times_utc[i]
        stamp.set_text(f"Hour ending {t_loc:%a %d %b %Y, %H:%M} {tzl}  ·  {t_utc:%H:%M} UTC")
        cursor.set_xdata([xs[i], xs[i]])
        dot.set_data([xs[i]], [mean_series[i]])
        return im, stamp, cursor, dot

    anim = animation.FuncAnimation(fig, update, frames=nt, interval=1000 / fps, blit=False)
    if writer_name == "ffmpeg":
        writer = animation.FFMpegWriter(fps=fps, codec="libx264", bitrate=2400,
                                        extra_args=["-pix_fmt", "yuv420p"])
    else:
        writer = animation.PillowWriter(fps=fps)
    anim.save(str(out_path), writer=writer, dpi=dpi)
    plt.close(fig)
    print(f"wrote {out_path}  ({nt} frames)")


# ----------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Compute and animate hourly WBGT (outdoor + indoor) from ERA5 single levels.")
    p.add_argument("--indir", default="era5_wbgt", help="folder with era5_YYYY_MM.nc")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--outdir", default="wbgt_output")
    p.add_argument("--fps", type=int, default=12, help="frames per second (default 12)")
    p.add_argument("--format", choices=["mp4", "gif"], default="mp4")
    p.add_argument("--vmin", type=float, default=None, help="colour scale minimum (default: from data)")
    p.add_argument("--vmax", type=float, default=None, help="colour scale maximum (default: from data)")
    p.add_argument("--tz-offset", type=int, default=8, help="hours from UTC for the on-screen clock (Philippines: 8)")
    p.add_argument("--min-speed", type=float, default=None, help="minimum 2 m wind speed in m/s (default: pywbgt's 2 knots)")
    p.add_argument("--max-frames", type=int, default=None, help="animate only the first N hours (quick test)")
    p.add_argument("--chunk-hours", type=int, default=168,
                   help="process this many hours at a time to limit memory (default 168 = 7 days)")
    p.add_argument("--native-wind", action="store_true",
                   help="use pywbgt's built-in 10 m -> 2 m wind adjustment (night-time flag bug in 3.0.7, see header)")
    p.add_argument("--no-boundary", action="store_true",
                   help="do not draw the Philippines boundary (it needs the regionmask package)")
    p.add_argument("--dpi", type=int, default=100)
    p.add_argument("--reuse", action="store_true", help="reuse wbgt_YYYY_MM.nc if it already exists")
    args = p.parse_args()

    indir, outdir = Path(args.indir), Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    src = indir / f"era5_{args.year}_{args.month:02d}.nc"
    nc_out = outdir / f"wbgt_{args.year}_{args.month:02d}.nc"

    if args.reuse and nc_out.exists():
        print(f"reusing {nc_out}")
        res = xr.open_dataset(nc_out).load()
    else:
        if not src.exists():
            sys.exit(f"cannot find {src}. Run download_era5.py first.")
        ds = open_month(src)
        flux = hourly_solar(ds)
        res = compute_wbgt(ds, flux, args.min_speed, args.chunk_hours, args.native_wind)
        enc = {v: {"zlib": True, "complevel": 4, "dtype": "float32", "_FillValue": np.float32(np.nan)} for v in res.data_vars}
        res.to_netcdf(nc_out, encoding=enc)
        print(f"wrote {nc_out}")

    for v in ("wbgt_outdoor", "wbgt_indoor"):
        a = res[v].values
        print(f"{v:13s} min {np.nanmin(a):5.1f}  mean {np.nanmean(a):5.1f}  max {np.nanmax(a):5.1f} °C")

    # one colour scale for BOTH animations so indoor and outdoor are directly comparable
    both = np.concatenate([res["wbgt_outdoor"].values.ravel(), res["wbgt_indoor"].values.ravel()])
    both = both[np.isfinite(both)]
    vmin = args.vmin if args.vmin is not None else float(np.floor(np.percentile(both, 0.5)))
    vmax = args.vmax if args.vmax is not None else float(np.ceil(np.percentile(both, 99.9)))

    use_ffmpeg = args.format == "mp4" and shutil.which("ffmpeg") is not None
    if args.format == "mp4" and not use_ffmpeg:
        print("ffmpeg not found: writing GIF instead")
    ext = "mp4" if use_ffmpeg else "gif"
    month_label = f"{pd.Timestamp(args.year, args.month, 1):%B %Y}"
    jobs = [
        ("wbgt_outdoor", "Outdoor WBGT", "Liljegren et al. (2008) · in the sun · ERA5 inputs · land and sea"),
        ("wbgt_indoor", "Indoor WBGT", "Bernard & Pourmoghani (1999) · no solar load · ERA5 inputs · land and sea"),
    ]
    outline = None if args.no_boundary else philippines_outline()
    for var, title, sub in jobs:
        out = outdir / f"{var}_{args.year}_{args.month:02d}.{ext}"
        animate(res, var, f"{title}, {month_label}", sub, out, args.fps, vmin, vmax,
                args.tz_offset, args.max_frames, args.dpi, "ffmpeg" if use_ffmpeg else "pillow",
                outline=outline)


if __name__ == "__main__":
    main()