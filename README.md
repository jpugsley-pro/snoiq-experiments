# Experiment Workbench

This is the central R&D workbench for SnoIQ. Prototype in notebooks, then “graduate” clean logic into `src/` with tests. The **single project manifest** is `pyproject.toml` (Pixi workspace + tasks + tooling). 

## Quick Start

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

## Folder Structure & Reasoning

### `/data`

- **Purpose:** Small, sample files for quick local tests.
- **Contains:** Tiny `.grib2`, `.nc`, `.csv`, and golden fixtures checked into Git.
- **Not here:** Large datasets (HRRR, MRMS archives, etc.) — use DVC + MinIO/S3.

### `/notebooks`

- **Purpose:** Messy R&D sandbox for exploration and prototyping.
- **Workflow:** When a concept is proven, “graduate” clean functions into `/src` and add tests.

### `/src` (package)

- **Purpose:** Clean, reusable, tested code (importable via `from src.*`).
- **Highlights (current):**
  - `ingestion/mrms.py` → `open_mrms_qpe()` (canonical MRMS QPE loader)
  - `ingestion/uscrn.py` → `open_uscrn_hourly()` (fixture-based CRNH02 parser)
  - `physics/snow.py` → SLR temp ramp + conversions

### `/tests`

- **Purpose:** Golden tests + unit tests that define contracts.
- **Current:**
  - `test_ingestion.py` (MRMS contract)
  - `test_ingestions_uscrn.py` (USCRN fixture contract)
- **How imports work:** `pyproject.toml` sets the tests task to `PYTHONPATH=.`, so `from src.*` resolves without extra hacks.

---

## Project Blueprint (Aspirational Map)

```text
snoiq-experiments/
├── .pixi/                 # (ignored) Pixi env files
├── .dvc/                  # (tracked) DVC metadata; secrets in .dvc/config.local only
├── .vscode/               # VS Code config for interpreter + tasks
│
├── pyproject.toml         # 🔵 Single manifest (Pixi workspace + tasks + tooling)
├── pixi.lock              # 🔵 Reproducible lockfile
│
├── data/
│   ├── raw/
│   │   └── mrms/…         # tiny sample GRIB2 files for tests
│   ├── refs/
│   │   └── UserTable_MRMS_v12.2.csv
│   └── golden/
│       ├── mrms_qpe01h_pass2_crop.nc
│       └── uscrn_hourly_sample.txt
│
├── notebooks/
│   └── 01-ingestion/
│       └── mrms.ipynb
│
├── src/
│   ├── ingestion/
│   │   ├── mrms.py        # canonical MRMS loader (cfgrib→fallback to pygrib)
│   │   └── uscrn.py       # defensive CRNH02 parser (fixture-driven)
│   └── physics/
│       └── snow.py        # SLR (v0), conversions
│
└── tests/
    ├── test_ingestion.py
    └── test_ingestions_uscrn.py
```

---

## Services

- **MinIO:** S3-compatible local object store. Buckets: `snoiq-experiments`, `mlflow`.
- **MLflow:** UI served via Docker; Python lib version pinned in `pyproject.toml`.
- **DVC:** Remote = MinIO (`.dvc/config.local` stores creds). Avoid committing secrets.

---

## Known Contracts (what tests assert)

- **MRMS QPE (1h Pass2):**
  - `open_mrms_qpe(path)` → `xarray.DataArray`
  - `name="QPE_01H_Pass2"`, `units="mm"`
  - dims = `("latitude","longitude")`, non-negative values
  - attrs include `product_token`, `filename`, `source`, optional MRMS table enrichment

- **USCRN Hourly Fixture:**
  - `open_uscrn_hourly(path)` → `polars.DataFrame`
  - Columns: `wban`, `timestamp_utc`, `t_air_c`, `precip_mm`, `qc_flags`
  - Timestamps match `T\d{2}:00:00Z`

---

## Next Steps (Milestones)

- **M3 — SLR Prototype:** v1 vertical-profile proxy (Kuchera-style); tests with synthetic profiles.
- **M4 — Event Segmentation:** Adaptive 3–6h dry-gap; tests on synthetic sequences.
- **M5 — Feature Assembly:** Join MRMS, CRN, topography/landcover → training parquet; schema + record count tests.
- **M6 — MLflow Baseline:** Train/log baseline model to MinIO-backed MLflow.
- **M7 — Promotion Gate:** Split into repos; carry golden tests in CI.

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
