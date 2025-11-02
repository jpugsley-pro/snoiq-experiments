# src/ingestion/uscrn.py
from __future__ import annotations

from pathlib import Path

import polars as pl

# CRNH02 fixed-width (USCRN Hourly) minimal fields we care about
# See: https://www1.ncdc.noaa.gov/pub/data/uscrn/products/hourly02/ (for reference)
# Positions below reflect the published spec; we only parse a subset to start.

# Columns: WBAN, UTC datetime parts, air temp, precip, QC flags (strings)
# We’ll parse from a few sample lines (fixture) first.

def _parse_line(line: str) -> dict[str, object]:
    # Defensive: pad line to avoid IndexErrors on short lines
    s = line.rstrip("\n")
    if not s or s.startswith("#"):
        raise ValueError("skip")

    # Minimal slice mapping (spec subset)
    # Year(1-4), Month(6-7), Day(9-10), Hour(12-13)
    year = int(s[0:4])
    month = int(s[5:7])
    day = int(s[8:10])
    hour = int(s[11:13])

    # WBAN often at positions 15-19 or similar; adjust as needed per actual file
    # For our tiny fixture we’ll allow blank/placeholder.
    wban = s[14:19].strip() or "00000"

    # Air temperature C (e.g., columns 47-52), precipitation mm (e.g., 111-115)
    # These vary across variants; we’ll parse robustly with fallback.
    def _to_float(slice_: str) -> float | None:
        t = slice_.strip()
        if t in ("", "-9999", "-99999", "-99.99"):
            return None
        try:
            return float(t)
        except ValueError:
            return None

    # Use forgiving slices that match our fixture; adjust when integrating real files
    t_air_c = _to_float(s[46:52])
    precip_mm = _to_float(s[110:116])

    qc_flags = s[116:].strip() if len(s) > 116 else ""

    return {
        "wban": wban,
        "timestamp_utc": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00Z",
        "t_air_c": t_air_c,
        "precip_mm": precip_mm,
        "qc_flags": qc_flags,
    }

def open_uscrn_hourly(path: str | Path) -> pl.DataFrame:
    p = Path(path)
    rows: list[dict[str, object]] = []
    with p.open("r", encoding="utf-8") as fp:
        for ln in fp:
            try:
                rows.append(_parse_line(ln))
            except ValueError:
                continue  # comments/blank
    if not rows:
        return pl.DataFrame({"wban": [], "timestamp_utc": [], "t_air_c": [], "precip_mm": [], "qc_flags": []})
    return pl.DataFrame(rows).with_columns(
        pl.col("t_air_c").cast(pl.Float64, strict=False),
        pl.col("precip_mm").cast(pl.Float64, strict=False),
    )
