# SnoIQ Experiments — Decision Sheet (v2)

## 1. Mission and Scope
The **SnoIQ Experiments** repository validates SnoIQ’s **Reanalysis Model MVP**, following the Functional Specification v1.
Validated modules promote into:
- **snoiq-ingest** → ingestion & enrichment
- **snoiq-train** → training & model registry
- **snoiq-core** → operational inference & reporting
- **snoiq-app** → SaaS web interface

---

## 2. Toolchain Decisions

| Layer | Tool | Purpose |
|------|------|---------|
| Python | **Python 3.13+** | Main programming language |
| Package Management | **Pixi** | Dependency and build management |
| Runtime | WSL2 / Docker | Consistent cross-platform environment |
| Environment | **Pixi** | Reproducible workspace; see `pyproject.toml` `[tool.pixi]` |
| Core Libraries | **xarray**, **cfgrib** + **eccodes**, **pygrib**, **rasterio**, **rioxarray**, **geopandas** | GRIB/NetCDF/Zarr I/O, geospatial processing |
| Orchestration | **Prefect 2.x** | Flow orchestration for ingestion/physics/ML |
| Data Versioning | **DVC** + **MinIO** | Versioned artifacts in object storage |
| ML Tracking | **MLflow** | Experiment runs, metrics, and model registry |
| Analytics | **DuckDB** | Fast SQL over Parquet (zero ETL) |
| Storage (tabular) | **Parquet** | Canonical for observations/features/events/evals |
| Storage (grids) | **NetCDF (default)** / **Zarr (optional)** | Arrays; Zarr for S3/MinIO chunked I/O |
| Quality | **ruff**, **mypy**, **pytest** | Linting, type checking, unit tests |
| Notebooks | **JupyterLab** via Pixi kernel | Ad-hoc experiments and prototyping |
| VS Code | `.vscode/` configs | Standardized IDE experience |

**Build & Environment:** Managed via **Pixi workspace**, ensuring task parity between local, container, and CI environments.

---

## 3. Data Architecture Decisions

| Dataset | Access | Stored As |
|--------|--------|-----------|
| MRMS (QPE, SPT, T/Tw) | AWS Open Data | NetCDF (or Zarr) |
| HRRRv4 profiles | AWS Open Data | NetCDF (or Zarr) |
| CRN | HTTP (CRNH02) | Parquet |
| ASOS | GHCN‑Hourly (PSV) | Parquet |
| CoCoRaHS | GHCN‑Daily | Parquet |
| Landcover (Dynamic World) | Earth Engine | Parquet |

**Rationale:** Parquet ↔ DuckDB enables fast in-memory analytics. NetCDF serves as the default grid format, with optional Zarr for scalable, cloud-native I/O using `xarray`, `fsspec`, and async drivers for MinIO/S3.

Runtime toggle:
```bash
export GRID_FORMAT=netcdf   # default
# export GRID_FORMAT=zarr
```

---

## 4. Modeling & Algorithmic Decisions

### 4.1 Precipitation Typing
- Base: MRMS v12.2 **SPT** + SnoIQ T/Tw thresholds, QPE gating.
- Experimental: **spectral‑bin** classifier for marginal regimes.
- Validation: ASOS present‑weather confusion matrices; CoCoRaHS transitions.

### 4.2 Dynamic Snow‑to‑Liquid Ratio (SLR)
- Regression on HRRR vertical profiles (T, RH, wind); 5:1–30:1 limits; validated on CRN depth change.

### 4.3 ML‑Hybrid Correction Model
- Residual target `(truth − physics)`; RF (champion), LightGBM (challenger).
- Weighted ground truths: CRN 1.0, CoCoRaHS 0.9, ASOS 0.8.
- Physics-guided disaggregation for CoCoRaHS 24‑h totals.

### 4.4 Event Detection & Narratives
- Hazard = frozen phase + measurable QPE; ≤3h merge, >6h break.
- Event Condenser → JSON → LLM narrative prompt.

---

## 5. Promotion Policy

| Stage | Criteria | Target Repo |
|------|-----------|-------------|
| Ingestion | ≥90% tests; idempotent Prefect flow | `snoiq-ingest` |
| Physics/SLR | RMSE < 5% vs CRN | `snoiq-ingest` |
| ML‑Hybrid | MAE < 1.0" vs truth | `snoiq-train` |
| Event/Narrative | Schema‑valid JSON; QA spot‑check | `snoiq-core` |

---

## 6. Milestones (2025 Alignment)

| Milestone | Description | Status |
|---------:|-------------|--------|
| **M1** | Extend ingestion (MRMS, CRN HTTP, CoCoRaHS GHCN‑Daily, ASOS GHCN‑Hourly) | In Progress |
| **M2** | Implement Dynamic SLR + Physics_Estimate_Grid (NetCDF/Zarr) | Pending |
| **M3** | Train ML‑Hybrid model + evaluate | Pending |
| **M4** | Event/Narrative pipeline | Pending |
| **M5** | Prefect‑orchestrated end‑to‑end MVP | Pending |

---

## 7. Directory & Storage Layout

```
data/
  parquet/         # canonical tabular outputs
    observations/  # crn.parquet, asos.parquet, cocorahs.parquet
    features/      # ml_features_train.parquet, *_val.parquet
    events/        # event_hour.parquet, event_meta.parquet
    evals/         # metrics_by_region.parquet
  grids/
    mrms/          # mrms_qpe_*.nc  (or *.zarr/ when GRID_FORMAT=zarr)
    physics/       # physics_grid_*.nc (or *.zarr/ ...)
    final/         # final_corrected_*.nc (or *.zarr/ ...)
```

**Implementation Notes:**
- Prefect tasks write Parquet for tabular data and NetCDF/Zarr for grids.  
- DVC tracks all artifact directories for reproducibility.  
- DuckDB reads Parquet directly for lightweight analytics.

*End of Decision Sheet (v2).*