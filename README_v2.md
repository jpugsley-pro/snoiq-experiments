# SnoIQ Experiments

## Overview
**SnoIQ Experiments** is the active sandbox for developing and validating the **Reanalysis Model MVP** that powers the full SnoIQ system.  
It tests ingestion, physics estimation, and ML workflows before promoting stable components into production repositories.

### Purpose
- Validate ingestion pipelines for MRMS, HRRR, CRN (HTTP), ASOS (GHCN‑Hourly), and CoCoRaHS (GHCN‑Daily).
- Prototype the Dynamic Snow‑to‑Liquid Ratio (SLR) model and Physics_Estimate_Grid.
- Develop and test the ML‑Hybrid Correction Model for residual learning.
- Evaluate event detection and narrative generation pipelines.
- Integrate **Prefect** orchestration, **DVC** artifact tracking, and **MLflow** experiment logging.
- Establish **Parquet (tabular)** + **NetCDF/Zarr (gridded)** conventions optimized for MinIO/S3.

---

## Architecture Snapshot

```
[SnoIQ Experiments]
        │
        ▼
  [snoiq-ingest]  →  Data pipelines (MRMS, HRRR, CRN, ASOS, CoCoRaHS)
        │
        ▼
  [snoiq-train]   →  ML models (SLR, Hybrid Correction, Model Registry)
        │
        ▼
  [snoiq-core]    →  Operational inference, event detection, narratives
        │
        ▼
  [snoiq-app]     →  Web portal (Amplify + Next.js, Stripe, Auth)
```

This repository feeds validated experimental code upstream into **`snoiq-ingest`** and **`snoiq-train`**, supporting continuous evolution of the full SnoIQ ecosystem.

---

## Storage Conventions

| Type | Format | Purpose |
|------|---------|---------|
| Tabular | **Parquet** | Canonical for observations, features, event tables, and evaluation metrics |
| Gridded | **NetCDF** *(default)* / **Zarr** *(optional)* | MRMS, Physics, and Final Corrected grids |

**Why Zarr (optional):**
- Cloud-native chunked I/O and HTTP/S3 **range reads**.
- Parallel read/write access for multi-worker Prefect flows.
- Append-friendly for event-based time-slice updates.

Switch dynamically via environment variable:
```bash
export GRID_FORMAT=netcdf   # default
# or
export GRID_FORMAT=zarr
```

Minimal pattern:
```python
if os.getenv("GRID_FORMAT", "netcdf") == "zarr":
    ds.to_zarr("s3://minio/grids/physics/event_20250120.zarr", mode="w")
else:
    ds.to_netcdf("data/grids/physics/event_20250120.nc")
```

DVC tip: track Zarr **directories** (`dvc add data/grids/physics/event_*.zarr/`).

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- [Pixi](https://pixi.sh/) for unified environments
- Prefect (≥2.15), DVC, MLflow, and MinIO (for local tracking)

### Setup
```bash
pixi install
make up             # starts MinIO and MLflow (local)
pixi run lab        # JupyterLab
pixi run tests      # runs pytest (PYTHONPATH=. set in task)
```

### VS Code

- Interpreter: `.pixi/envs/default/bin/python`
- Tasks: `Terminal → Run Task…` (Pixi: tests/lint/type/lab; Docker up/down; MLflow UI; Prefect UI)

---

### Common Makefile Tasks
```bash
make lab          # Launch JupyterLab
make tests        # Run pytest suite
make lint         # Format and lint with Ruff
make prefect-ui   # Start Prefect server/UI
make mlflow-ui    # Start MLflow on port 5001
```

---

## Experiment Workflow

| Stage | Description | Tools |
|--------|-------------|-------|
| Ingestion | Fetch MRMS, HRRR, CRN, ASOS, CoCoRaHS | Prefect, requests, xarray |
| Physics | Compute Physics_Estimate_Grid (QPE × SLR) | numpy, xarray |
| ML | Train Hybrid Correction model (RF/LightGBM) | scikit‑learn, MLflow |
| Evaluation | RMSE, MAE, bias, narrative quality | pytest, pandas, DuckDB |
| Versioning | Track artifacts (Parquet, NetCDF, Zarr) | DVC, MinIO |

---

## Milestones (2025 Track)

| Milestone | Goal | Output |
|------------|------|--------|
| **M1** | Extend ingestion (MRMS + CRN HTTP + CoCoRaHS GHCN‑Daily + ASOS GHCN‑Hourly) | Unified Prefect ingestion flow |
| **M2** | Implement Dynamic SLR + Physics_Estimate_Grid | Calibrated physics baseline |
| **M3** | Train and evaluate Hybrid Correction Model | Residual correction grid |
| **M4** | Prototype Event Detection + LLM Narrative pipeline | JSON-based narratives |
| **M5** | Integrate Prefect, DVC, and MLflow end-to-end | MVP Reanalysis pipeline |

---

## Directory Layout

```
.
├── data/
│   ├── parquet/         # canonical tabular artifacts (observations, features, events, evals)
│   ├── grids/           # gridded artifacts (NetCDF by default, or *.zarr/ when GRID_FORMAT=zarr)
│   ├── raw/             # source-native (grib2, nc, psv)
│   ├── refs/            # lookup tables (e.g., MRMS UserTable, landcover legends)
│   └── golden/          # test fixtures
├── src/
│   ├── ingestion/       # Prefect ingestion tasks
│   ├── physics/         # Dynamic SLR + Physics_Estimate_Grid
│   └── ml/              # ML-Hybrid correction prototypes
├── notebooks/           # exploratory notebooks
├── tests/               # pytest suite
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

---

## Pixi Environment Notes
- All dependencies and task aliases are declared in **`pyproject.toml`** under `[tool.pixi]`.  
- Use `pixi run <task>` to execute predefined commands, ensuring consistent local, Docker, and CI environments.

---

## Local Development Shortcuts
- `pixi run lab` → start JupyterLab  
- `make tests` → run all tests  
- `make prefect-ui` / `make mlflow-ui` / `make minio-ui` → launch dashboards  
- `make lint` / `make typecheck` → quality checks

---

## Services

- **MinIO:** S3-compatible local object store. Buckets: `snoiq-experiments`, `mlflow`.
- **MLflow:** UI served via Docker; Python lib version pinned in `pyproject.toml`.
- **DVC:** Remote = MinIO (`.dvc/config.local` stores creds). Avoid committing secrets.

---

## References
- SnoIQ Functional Specification v1 (Reanalysis MVP)
- MRMS v12.2, GHCN‑Daily/Hourly
- Google Dynamic World V1 (landcover)
- Prefect 2.x, DVC, MLflow, DuckDB

---

## Tips

- In notebooks, add at top:
  ```py
  import sys
  from pathlib import Path
  repo_root = Path("..").resolve().parent
  if str(repo_root) not in sys.path:
      sys.path.append(str(repo_root))
  ```
- Use `make verify` to run lint + typecheck + tests in one shot.
