# snoiq-experiments • Decision Sheet, Setup, and Promotion Playbook

> Single source of truth for our environment, experiment workflow, promotion gates, and the future split into repos — **now aligned to pyproject-based Pixi, MRMS canonical loader, USCRN fixture, and MinIO/DVC credential hygiene**.

---

## 0) Mission & Scope

- Lock the **toolchain** so experiments are reproducible.
- Run **small, scoped experiments** in notebooks and graduate stable pieces into `src/` behind tests.
- Answer implementation choices **empirically** (GRIB readers, Parquet vs DB, DVC/MinIO, HOMR station metadata, etc.).
- Keep the path open to a future **multi-repo** split (`snoiq-ingest`, `snoiq-train`, `snoiq-core`, `snoiq-app`).

---

## 1) Decision Sheet v1 (Locked)

### A) Environment & Tooling

- **Manifest:** `pyproject.toml` (Pixi workspace + tasks + tooling). `pixi.toml` retired.
- **Runtime/env:** Pixi on WSL2 Ubuntu. Repo under `/home/*` for fast I/O.
- **Python:** 3.13.x (Pixi-managed).
- **Core libs:** `xarray`, `cfgrib` + `eccodes` (primary), `pygrib` (fallback), `rasterio`, `rioxarray`, `geopandas`.
- **Data mgmt:** `dvc` + `dvc-s3` with local **MinIO** remote (no AWS CLI required).
- **Ad-hoc SQL over Parquet:** **DuckDB** (SQLite optional; Postgres deferred).
- **ML + Ops:** `scikit-learn`, `xgboost`, `mlflow` (Python lib **3.5.1**), `prefect`.
- **Quality:** `ruff`, `mypy`, `pytest` (+ `pytest-cov` later).
- **Tasks:** Pixi tasks (via `pyproject.toml`) + Makefile wrappers.
- **Notebooks:** JupyterLab via Pixi kernel (VS Code friendly).
- **VS Code:** `.vscode/{extensions,settings,tasks}.json` committed.

### B) Data/IO Strategy (Experiments)

- **GRIB ingest:** Prefer `xarray`+`cfgrib`+`eccodes`; keep `pygrib` fallback. Expect **`unknown`** var names in some MRMS files → we canonicalize by filename token.
- **Arrays:** Xarray → Zarr/NetCDF (n-dim); **GeoTIFF** for map exports only.
- **Tables:** Parquet on disk; **DuckDB** for fast local queries/joins.
- **Station truth:** Start with **USCRN hourly**; expand to **ASOS (GHCNh)** and **CoCoRaHS**.
- **Artifacts:** Version small artifacts via **DVC** to **MinIO** (S3-compatible) in dev; mirror to AWS S3 in prod.

### C) Repo Strategy (Now vs Later)

- **Now:** Stay in `snoiq-experiments` with clean `src/` boundaries + tests.
- **Later:** Split to four repos. Share common utilities via `snoiq-common` wheel. Use `git subtree`/`filter-repo` to migrate history.

### D) Promotion Policy (Notebook → src)

Promote when it:
1) solves a repeated need, **and**
2) has a **unit test** with tiny fixture/synthetic data, **and**
3) is documented (type hints + docstring).

Tag docstrings with `@status experimental|provisional|stable`. If evolving, land under `src/experiments/` with a short README.

### E) Event Semantics (Initial)

- Base **dry-gap = 3h** (parametric). We’ll test adaptive rules and adjust.
- SLR v0: **temperature-ramp** (near-surface proxy).  
- SLR v1: **vertical-profile proxy** (Kuchera-style) in M3.

---

## 2) Environment & Services Setup

### Pixi (single manifest)

- All deps/tasks live in **`pyproject.toml`** (see repo).  
- Tests task sets `PYTHONPATH=.` so `from src.*` works without hacks.

### Docker Compose (local services)

```yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    ports: ["9000:9000", "9001:9001"]
    volumes: ["./.minio:/data"]

  mlflow:
    image: ghcr.io/mlflow/mlflow:v3.5.1
    command: mlflow server --host 0.0.0.0 --port 5001       --backend-store-uri sqlite:///mlflow.db       --default-artifact-root s3://mlflow/
    environment:
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000
      AWS_ACCESS_KEY_ID: minio
      AWS_SECRET_ACCESS_KEY: minio12345
    ports: ["5001:5001"]
    depends_on: ["minio"]
```

> Create buckets `mlflow` and `snoiq-experiments` in the MinIO console (`http://localhost:9001`).

### DVC + MinIO (no AWS CLI needed)

```bash
dvc init
dvc remote add -d minio s3://snoiq-experiments
dvc remote modify minio endpointurl http://127.0.0.1:9000
dvc remote modify --local minio access_key_id minio
dvc remote modify --local minio secret_access_key minio12345
dvc remote modify minio use_ssl false
```

> Use `.dvc/config.local` for creds. Do **not** commit secrets.

### Makefile QoL

```make
.PHONY: up down lab test lint type verify
up: ; docker compose up -d
down: ; docker compose down -v
lab: ; pixi run lab
test: ; pixi run tests
lint: ; pixi run lint
type: ; pixi run typecheck
verify: ; pixi run lint && pixi run typecheck && pixi run tests
```

### .gitignore keys

- Ignore: `.pixi/`, `.minio/`, `.dvc/{cache,tmp}/`, `mlflow.db`, `mlruns/`, notebooks checkpoints, large data patterns.
- Allow: `data/golden/`, `data/raw/mrms/` tiny samples.

---

## 3) MRMS Realities & Canonical Loader

**Reality:** Some MRMS GRIB2 expose **`unknown`** fields via `cfgrib` **and** `pygrib`.  
**Solution:** Parse the filename token (authoritative), standardize the variable name/attrs, clean, and harmonize dims.

- Canonical loader: `src/ingestion/mrms.py::open_mrms_qpe`
- Output contract:
  - `name="QPE_01H_Pass2"`, `units="mm"`
  - dims = `("latitude","longitude")`
  - attrs include `product_token`, `filename`, `source`
  - optional enrichment from `data/refs/UserTable_MRMS_v12.2.csv` (family match)

- Golden crop written: `data/golden/mrms_qpe01h_pass2_crop.nc`

---

## 4) USCRN Hourly (Fixture First)

- Parser: `src/ingestion/uscrn.py::open_uscrn_hourly` (defensive subset of CRNH02)
- Golden fixture: `data/golden/uscrn_hourly_sample.txt`
- Test: `tests/test_ingestions_uscrn.py`
- Contract: columns `wban`, `timestamp_utc`, `t_air_c`, `precip_mm`, `qc_flags` (Polars DF)

> We’ll tighten slice offsets when a real CRNH02 sample lands in `data/raw/uscrn/`.

---

## 5) Snow Depth (SLR v0)

- Module: `src/physics/snow.py`
- Functions:
  - `slr_temp_ramp(t2m_c)` → SLR factor
  - `snowfall_depth_mm(qpe_mm, t2m_c)` → depth (mm)
  - `to_inches(mm)` → inches

---

## 6) Adaptive Event Segmentation (Design Stub)

Heuristic v0 (deterministic, testable):
- Base gap = 3h
- Extend to 6h if upstream precip persists (MRMS nowcast or HRRR 0–3h > 50%)
- If `T ≤ 0°C` and pressure trend favors persistence: +1–2h grace

Unit-test with synthetic sequences first.

---

## 7) DuckDB Quick Patterns

```sql
INSTALL parquet; LOAD parquet;
SELECT platform, COUNT(*) FROM 'data/derived/stations.parquet' GROUP BY 1;
```

Python:
```py
import duckdb
con = duckdb.connect()
con.execute("SELECT COUNT(*) FROM read_parquet('data/derived/*.parquet')").fetchall()
```

---

## 8) DVC Artifact Example

```bash
dd if=/dev/urandom of=data/grids/dummy.bin bs=1K count=8
dvc add data/grids/dummy.bin
git add data/grids/dummy.bin.dvc .gitignore
git commit -m "Track tiny dummy artifact with DVC"
make up && dvc push
```

---

## 9) How This Maps to the Future Split

- `src/ingestion/*` → **snoiq-ingest** (fetch/format, parquet writers, later DB & Prefect flows)
- `src/physics/*`, `src/features/*`, `src/training/*` → **snoiq-train**
- `src/core/*` → **snoiq-core** (inference, narratives, API)
- `src/app/*` → **snoiq-app** (UI)

Shared code becomes `snoiq-common` (versioned wheel). Steps: freeze APIs with tests → split history → publish `snoiq-common` → pin downstream.

---

## Milestone Chain (Experiments → Promotion)

- **M1 — MRMS Ingestion** ✅
  - Canonical loader `open_mrms_qpe`
  - Units=mm, dims=(latitude, longitude), name=QPE_01H_Pass2
  - UserTable v12.2 enrichment
  - Golden crop + test

- **M2 — USCRN Hourly Ingestion** ✅ (fixture + test in place; real file offsets TBD)
  - Parse CRNH02 hourly → Polars DF → Parquet (later)
  - Golden sample + test

- **M3 — SLR Prototype** ⏳
  - v0 temp ramp (done)
  - v1 vertical-profile proxy (Kuchera-style)
  - Unit tests with synthetic profiles

- **M4 — Event Segmentation** ⏳
  - Adaptive 3–6h dry-gap (parametric)
  - Unit tests on synthetic sequences

- **M5 — Feature Assembly** ⏳
  - Join MRMS, CRN, terrain/landcover → training parquet
  - Schema + record count tests

- **M6 — MLflow Baseline** ⏳
  - Train baseline
  - Artifacts + metrics logged to MinIO-backed MLflow

- **M7 — Promotion Gate** ⏳
  - Split repos; carry golden tests in CI
