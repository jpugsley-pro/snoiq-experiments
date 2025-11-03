# MRMS (Multi-Radar/Multi-Sensor) — Source Description

> Canonical reference for how we discover, read, and normalize MRMS products in this project. Pairs with the USCRN source notes and our ingestion contracts in `src/ingestion/mrms.py` and tests.

---

## 1) What MRMS Is (and why we use it)

MRMS blends multiple sensors (WSR-88D radar network, gauges, satellite, NWP, lightning, etc.) into seamless, high spatio-temporal mosaics used operationally by NWS. In SnoIQ we use MRMS for precipitation accumulations at ~1 km scale to build snowfall depth via our SLR functions and event logic.

Key background (read-first):
- Project overview (NSSL): https://www.nssl.noaa.gov/projects/mrms/
- Open data home (AWS Registry): https://registry.opendata.aws/noaa-mrms-pds/
- Operational GRIB2 tables (variables/units/naming): https://www.nssl.noaa.gov/projects/mrms/operational/tables.php
- MRMS Support repo (tables, binary docs): https://github.com/NOAA-National-Severe-Storms-Laboratory/mrms-support
  - GRIB2 tables CSVs: GRIB2_TABLES/
  - MRMS Gridded Binary Format PDF: MRMS_BINARY/docs/MRMS_Gridded_BinaryFormat.pdf

Domain & grid: nominal 0.01 deg lat/lon (~1.11 km N–S; ~1.0 to 0.6 km W–E across domain). Grid spans roughly 130–60W, up to ~55N. (See Zhang et al. 2016 BAMS for QPE domain context.)

---

## 2) Products We Care About (initial)

We start with the MultiSensor QPE accumulations (gauge-adjusted):
- QPE_01H_Pass2 — 1-hour accumulation, gauge-adjustment with longer latency (more gauges, higher quality).
- (Later) QPE_01H_Pass1, QPE_03H_Pass2, QPE_06H_Pass2, … as needed.

In our code, the canonical loader exposes name="QPE_01H_Pass2", units="mm", dims=("latitude", "longitude") and enriches attributes from the MRMS GRIB2 table when available.

Helpful cross-refs:
- Tables site (current version notes and examples)
- data/refs/UserTable_MRMS_v12.2.csv tracked in-repo for enrichment
- Tests: tests/test_ingestion_mrms.py

---

## 3) Where the Data Lives (AWS)

Public bucket (anonymous):
s3://noaa-mrms-pds/

The bucket is laid out by product family and date/time, e.g. (illustrative):
noaa-mrms-pds/
  QPE_01H_Pass2/
    20251102/
          MRMS_QPE_01H_Pass2_20251102-010000.grib2.gz
          MRMS_QPE_01H_Pass2_20251102-020000.grib2.gz
          ...

Also handy: HTML index for quick eyeballing — https://noaa-mrms-pds.s3.amazonaws.com/index.html

---

## 4) Filenames, Time Semantics, and Units

Pattern (typical):
MRMS_<ProductToken>_<YYYYMMDD>-<HHMMSS>.grib2[.gz]

- Times are UTC and generally denote the hour ending (for 1-hour accumulations).
- Units for QPE products are mm. (We convert to depth via SLR when building snowfall.)
- All operational product names are listed in the Operational MRMS GRIB2 Tables; MRMS prepends MRMS_ to the product token shown on the tables page.

---

## 5) Grid / Projection / Extents (what to assume in code)

- Geographic CRS (lat/lon) on a 0.01 deg grid.
- CONUS-wide mosaics with additional domains (e.g., Alaska, Hawaii) depending on product/version.
- Known corrections occasionally occur (e.g., Hawaii coordinate fix in v12.2). We keep grid checks in tests.

---

## 6) Reading MRMS (our canonical path)

Priority order in our environment:
1) xarray + cfgrib + eccodes (preferred)
2) Fallback: pygrib

Reality: some MRMS files expose unknown/blank parameter names. Our canonical loader therefore:
- Parses the filename token as authoritative (e.g., QPE_01H_Pass2).
- Applies table-based enrichment from data/refs/UserTable_MRMS_v12.2.csv when keys are present.
- Normalizes to a DataArray with:
  - name="QPE_01H_Pass2"
  - dims=("latitude","longitude")
  - attrs={"product_token", "filename", "source", ...}
- Returns non-negative values in mm.

See: src/ingestion/mrms.py::open_mrms_qpe and tests/test_ingestion_mrms.py

---

## 7) QC / Caveats

- Gauge latency: Pass1 vs Pass2 differ primarily by the gauge assimilation window; Pass2 waits longer -> generally more complete adjustments.
- Occasional grid/metadata quirks across versions; we pin table version in tests and record mrms_table_version in attrs.
- Compression: Many AWS objects are *.grib2.gz. We stream/decompress on the fly via fsspec.
- Hawaii v12.2 fix: Grid coordinate correction applied (ensure your reader does not assume the old half-cell offset).

---

## 8) Contract (what downstream can count on)

- Loader returns an xarray.DataArray with:
  - name matching the product token (e.g. QPE_01H_Pass2)
  - units="mm"
  - dims=("latitude","longitude")
  - monotonic increasing latitude and longitude coordinates
  - attrs include product_token, filename, source="noaa-mrms-pds", mrms_table_version (if resolvable)
- Golden file: data/golden/mrms_qpe01h_pass2_crop.nc

This matches the expectations in our Decision Sheet and README; see the repo-level contracts for ingestion and testing.

---

## 9) Example: Quickload (pseudo-code)

```python
from src.ingestion.mrms import open_mrms_qpe

arr = open_mrms_qpe("s3://noaa-mrms-pds/QPE_01H_Pass2/2025/11/02/MRMS_QPE_01H_Pass2_20251102-010000.grib2.gz")
# xarray.DataArray, name='QPE_01H_Pass2', units='mm'
```

---

## 10) Roadmap

- Add additional QPE windows (3h/6h/12h/24h/48h/72h).
- Wire a Zarr/NetCDF cache for subsetting by bbox/time range.
- Promote loader to snoiq-ingest when contracts are steady and tables are pinned.
- Consider non-QPE fields (e.g., Gauge Influence Index) as features.

---

## Appendix — Useful Links

- NSSL MRMS project site: https://www.nssl.noaa.gov/projects/mrms/
- AWS Open Data bucket listing: https://noaa-mrms-pds.s3.amazonaws.com/index.html
- Operational GRIB2 tables: https://www.nssl.noaa.gov/projects/mrms/operational/tables.php
- Support repo (tables/binary docs): https://github.com/NOAA-National-Severe-Storms-Laboratory/mrms-support
- QPE background (Zhang et al., BAMS 2016): https://training.weather.gov/wdtd/courses/MRMS/lessons/Hydro-products/Hydro-products-L2/presentation_content/external_files/Zhang2016-BAMS-QPE.pdf
