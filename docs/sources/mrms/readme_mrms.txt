MRMS source notes (docs/sources/mrms)

What this folder should contain:
- mrms.md  -> Full source description (products, bucket layout, filename patterns, grid, units, reading tips, contracts).
- GRIB2_TABLES/ (optional local copy or pointer) -> We keep the canonical CSV in data/refs/UserTable_MRMS_v12.2.csv.
- examples/  -> Tiny listings and example paths (S3 URIs we have verified).
- pitfalls.txt -> Any quirks we discover (unknown var names, coordinate fixes, etc.).

Canonical S3 structure (illustrative):
s3://noaa-mrms-pds/QPE_01H_Pass2/YYYY/MM/DD/MRMS_QPE_01H_Pass2_YYYYMMDD-HHMMSS.grib2.gz

Time semantics:
- 1-hour accumulations generally denote the hour ending at HH:MM:SSZ.
- Units are mm for QPE products.

Reader priority:
- xarray+cfgrib+eccodes (preferred) -> pygrib (fallback).
- Always canonicalize by filename product token (e.g., QPE_01H_Pass2).

See also:
- NSSL MRMS overview
- Operational GRIB2 tables
- MRMS support repo
