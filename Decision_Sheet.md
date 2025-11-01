# snoiq-experiments • Decision Sheet, Setup, and Promotion Playbook

> Single source of truth for our environment, experiment workflow, promotion gates, and the future split into repos.

---

## 0) Mission & Scope

* Lock the **toolchain** so experiments are reproducible.
* Run **small, scoped experiments** in notebooks and graduate stable pieces into `src/` behind tests.
* Answer implementation choices **empirically** (GRIB readers, Parquet vs DB, DVC/MinIO, HOMR station metadata, etc.).
* Keep the path open to a future **multi-repo** split (`snoiq-ingest`, `snoiq-train`, `snoiq-core`, `snoiq-app`).

---

## 1) Decision Sheet v1 (Locked)

### A) Environment & Tooling

* **Runtime/env:** Pixi (WSL2 Ubuntu). Repo under `/home/*` for fast I/O.
* **Python:** 3.13.x (Pixi-managed).
* **Core libs:** `xarray`, `cfgrib`+`eccodes` (primary), `pygrib` (fallback), `rasterio`, `rioxarray`, `geopandas`.
* **Data mgmt:** `dvc` + `dvc-s3` with local **MinIO** remote.
* **Ad-hoc SQL over Parquet:** **DuckDB** (keep SQLite handy; defer Postgres until needed).
* **ML + Ops:** `scikit-learn`, `xgboost`, `mlflow`, `prefect`.
* **Quality:** `ruff`, `mypy`, `pytest` (+ `pytest-cov` later).
* **Tasks:** Makefile + `pixi tasks`.
* **Notebooks:** JupyterLab via Pixi kernel (VS Code friendly).

### B) Data/IO Strategy (Experiments)

* **GRIB ingest:** Prefer `xarray`+`cfgrib` (engine), ensure `eccodes` + `eccodes-definitions` installed; keep `pygrib` available.
* **Arrays:** Xarray → Zarr/NetCDF for n-dim; **GeoTIFF** only for map exports.
* **Tables:** Parquet on disk; **DuckDB** for queries, joins, windowing.
* **Station truth:** Prioritize **USCRN hourly** for initial verification; bring **ASOS (GHCNh)** and **CoCoRaHS** as we expand.
* **Artifacts:** Version via **DVC** to **MinIO** (S3-compatible).

### C) Repo Strategy (Now vs Later)

* **Now:** Stay in `snoiq-experiments` with clean `src/` boundaries and tests.
* **Later:** Split to four repos. Share common utilities via `snoiq-common` wheel (versioned). Use `git subtree`/`filter-repo` to migrate history.

### D) Promotion Policy (Notebook → src)

* Promote a function when it:

  1. Solves a repeated need, **and**
  2. Has a **unit test** with tiny fixture or synthetic data, **and**
  3. Is documented (type hints + docstring).
* Add `@status experimental|provisional|stable` in docstrings.
* If still evolving, land under `src/experiments/` and include a short README.

### E) Storm Event Semantics (Initial)

* Start with **3-hour dry-gap** merge (parameterized). We will test adaptive rules (see §6) and adjust.
* SLR v0: **temperature-ramp** (near-surface proxy). SLR v1: **ERA5 profiles** (Kuchera-style proxy) in M3.

---

## 2) Environment & Services Setup

### `pixi.toml` essentials (add/confirm)

```toml
[project]
name = "snoiq-experiments"
version = "0.1.0"
description = "R&D workbench for SnoIQ"
authors = ["Jess <you@example.com>"]
channels = ["conda-forge"]
platforms = ["linux-64"]

[tasks]
lab = "jupyter lab"
tests = "pytest -q"
lint = "ruff check src tests"
typecheck = "mypy src"
prefect-ui = "prefect server start"
mlflow-ui = "mlflow ui --host 0.0.0.0 --port 5001"

[dependencies]
python = "3.13.*"
numpy = "*"
pandas = "*"
polars = "*"
xarray = "*"
cfgrib = "*"
eccodes = "*"
netcdf4 = "*"
zarr = "*"
fsspec = "*"
aiohttp = "*"
rasterio = "*"
rioxarray = "*"
pyproj = "*"
shapely = "*"
geopandas = "*"
pygrib = "*"        # fallback engine
scikit-learn = "*"
xgboost = "*"
pydantic = ">=2"
ruff = "*"
mypy = "*"
pytest = "*"
pytest-cov = "*"
ipykernel = "*"
jupyterlab = "*"
duckdb = "*"
dvc = "*"
dvc-s3 = "*"
boto3 = "*"
minio = "*"
prefect = ">=3"
mlflow = "*"
tenacity = "*"
tqdm = "*"
rich = "*"
python-dotenv = "*"
```

> Notes
>
> * Ensure `eccodes` and `cfgrib` install together; on conda-forge this pulls the right binary + definitions.
> * If `cfgrib` complains about indexes, pass `backend_kwargs={"indexpath": ""}` when opening files.

### `docker-compose.yml` (local services)

```yaml
version: "3.9"
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
    image: ghcr.io/mlflow/mlflow:v2.16.0
    command: mlflow server --host 0.0.0.0 --port 5001 --backend-store-uri sqlite:///mlflow.db --default-artifact-root s3://mlflow/
    environment:
      MLFLOW_S3_ENDPOINT_URL: http://minio:9000
      AWS_ACCESS_KEY_ID: minio
      AWS_SECRET_ACCESS_KEY: minio12345
    ports: ["5001:5001"]
    depends_on: ["minio"]
```

### DVC + MinIO bootstrap

```bash
dvc init
aws configure set default.s3.signature_version s3v4
# add remote
dvc remote add -d minio s3://snoiq-experiments
dvc remote modify minio endpointurl http://127.0.0.1:9000
dvc remote modify minio access_key_id minio
dvc remote modify minio secret_access_key minio12345
```

### Makefile QoL

```makefile
.PHONY: up down test lint type lab nb
up: ; docker compose up -d
down: ; docker compose down -v
lab: ; pixi run lab
test: ; pixi run tests
lint: ; pixi run lint
type: ; pixi run typecheck
```

---

## 3) Minimal Modules to Unblock Notebooks

### `src/ingestion/mrms.py`

```python
from __future__ import annotations
from pathlib import Path
import xarray as xr

MRMS_QPE_VAR_1H = "GaugeCorrQPE01H"  # adjust per product

_DEF_BACKEND = {"indexpath": ""}  # avoid on-disk index files


def open_grib(path: str | Path) -> xr.Dataset:
    """Open a GRIB2 file with xarray/cfgrib and normalize coords.
    Falls back to pygrib via xarray if needed (user can switch engine explicitly).
    """
    try:
        ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs=_DEF_BACKEND)
    except Exception as e:
        raise RuntimeError(
            f"Failed to open {path} via cfgrib. Ensure eccodes is installed. Error: {e}"
        )
    rename = {k: v for k, v in {"latitude": "lat", "longitude": "lon"}.items() if k in ds.coords}
    if rename:
        ds = ds.rename(rename)
    return ds


def extract_qpe_1h(ds: xr.Dataset, var: str = MRMS_QPE_VAR_1H) -> xr.DataArray:
    if var not in ds:
        raise KeyError(f"Variable '{var}' not found. Available: {list(ds.data_vars)}")
    da = ds[var].assign_attrs(long_name="MRMS 1h Gauge-Corrected QPE")
    return da
```

### `src/features/sample.py`

```python
from __future__ import annotations
import numpy as np
import xarray as xr
from typing import Tuple


def _idx_5x5(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> Tuple[slice, slice]:
    i = (np.abs(lats - lat)).argmin()
    j = (np.abs(lons - lon)).argmin()
    return slice(max(i - 2, 0), i + 3), slice(max(j - 2, 0), j + 3)


def sample_5x5(da: xr.DataArray, lat: float, lon: float) -> xr.DataArray:
    """Return 5×5 neighborhood around (lat, lon) for both 1D and 2D lat/lon coords."""
    lat_c, lon_c = da.coords.get("lat"), da.coords.get("lon")
    if lat_c is None or lon_c is None:
        raise ValueError("DataArray must have 'lat' and 'lon' coordinates.")
    if lat_c.ndim == 1 and lon_c.ndim == 1:
        i_sl, j_sl = _idx_5x5(lat, lon, lat_c.values, lon_c.values)
        return da.isel(lat=i_sl, lon=j_sl)
    dist = (lat_c - lat) ** 2 + (lon_c - lon) ** 2
    ii, jj = np.unravel_index(dist.argmin(), dist.shape)
    return da.isel(lat=slice(max(ii - 2, 0), ii + 3), lon=slice(max(jj - 2, 0), jj + 3))
```

### `src/physics/snow.py`

```python
from __future__ import annotations
import numpy as np
import xarray as xr

# @status provisional
# Units: QPE in millimeters (typical MRMS); outputs in millimeters unless noted.


def slr_temp_ramp(t2m_c: xr.DataArray | float) -> xr.DataArray:
    """SLR v0: simple temperature-based ramp.
    - >= 0°C → 8:1
    - -12°C → 18:1 (linear between)
    - <= -18°C → cap at 22:1
    """
    t = xr.DataArray(t2m_c) if not isinstance(t2m_c, xr.DataArray) else t2m_c
    slr = xr.where(t >= 0.0, 8.0, 8.0 + (-(t) / 12.0) * (18.0 - 8.0))
    slr = xr.where(t <= -18.0, 22.0, slr)
    return slr


def snowfall_depth_mm(qpe_mm: xr.DataArray, t2m_c: xr.DataArray | float) -> xr.DataArray:
    """Compute snowfall depth from liquid QPE (mm) and near-surface temp (°C).
    Returns millimeters of snow depth (convert to inches by /25.4).
    """
    slr = slr_temp_ramp(t2m_c)
    return qpe_mm * slr


def to_inches(mm: xr.DataArray | float) -> xr.DataArray:
    return (xr.DataArray(mm) if not isinstance(mm, xr.DataArray) else mm) / 25.4
```

---

## 4) Golden Tests (Tiny, fast)

### `tests/test_ingestion.py`

```python
from pathlib import Path
import pytest
from src.ingestion.mrms import open_grib, extract_qpe_1h

SAMPLE = Path("data/raw/mrms/sample_qpe.grib2")

@pytest.mark.skipif(not SAMPLE.exists(), reason="Need MRMS sample in data/raw/mrms/")
def test_open_and_extract_qpe():
    ds = open_grib(SAMPLE)
    assert ds.dims
    da = extract_qpe_1h(ds)
    assert da.ndim in (2, 3)
```

### `tests/test_features.py`

```python
import numpy as np
import xarray as xr
from src.features.sample import sample_5x5

def test_sample_5x5_regular_grid():
    lat = np.linspace(50, 40, 101)
    lon = np.linspace(-90, -80, 101)
    data = xr.DataArray(np.random.rand(101, 101), coords={"lat": lat, "lon": lon}, dims=("lat", "lon"))
    win = sample_5x5(data, lat=45.0, lon=-85.0)
    assert win.shape == (5, 5)
```

### `tests/test_snow.py`

```python
import numpy as np
import xarray as xr
from src.physics.snow import slr_temp_ramp, snowfall_depth_mm, to_inches

def test_slr_ramp_monotonic():
    t = xr.DataArray(np.array([2.0, 0.0, -6.0, -12.0, -20.0]))
    slr = slr_temp_ramp(t)
    assert slr.shape == t.shape
    assert slr.max() <= 22.1 and slr.min() >= 8.0

def test_depth_units():
    qpe = xr.DataArray(10.0)  # 10 mm liquid
    t = xr.DataArray(-10.0)
    snow_mm = snowfall_depth_mm(qpe, t)
    snow_in = to_inches(snow_mm)
    assert float(snow_in) > 0.0
```

---

## 5) Notebook Pattern (M1)

Create `notebooks/01-ingestion/mrms_totals.ipynb` that:

1. Loads `data/raw/mrms/sample_qpe.grib2` with `open_grib` → `extract_qpe_1h`.
2. Sums hours to storm total.
3. Uses a tiny CSV of USCRN hourly (lat,lon,t2m_c,total_liq_mm) to compute point totals.
4. Computes MAE/MAPE between estimated snow (inches) and observed snow (inches).
5. Prints metrics.

**Example cell (sketch):**

```python
from pathlib import Path
import pandas as pd
from src.ingestion.mrms import open_grib, extract_qpe_1h
from src.physics.snow import snowfall_depth_mm, to_inches

p = Path("data/raw/mrms/sample_qpe.grib2")
ds = open_grib(p)
qpe = extract_qpe_1h(ds)  # mm
storm_liq = qpe.sum(dim="time") if "time" in qpe.dims else qpe

stations = pd.read_csv("data/golden/uscrn_points.csv")  # lat,lon,t2m_c,obs_snow_in

estimates = []
for _, r in stations.iterrows():
    # naive nearest index; refine later with bilinear if needed
    q = storm_liq.sel(lat=r.lat, lon=r.lon, method="nearest")
    snow_mm = snowfall_depth_mm(q, r.t2m_c)
    snow_in = float(to_inches(snow_mm))
    estimates.append(snow_in)

stations["est_snow_in"] = estimates
stations["abs_err"] = (stations.est_snow_in - stations.obs_snow_in).abs()
print("MAE (in)", stations.abs_err.mean())
print("MAPE (%)", (stations.abs_err / stations.obs_snow_in.replace(0, float('nan'))).mean() * 100)
```

---

## 6) Adaptive Event Segmentation (beyond a static dry-gap)

**Goal:** Avoid splitting one synoptic event due to short lulls, and avoid merging genuinely separate systems.

### Heuristic v0 (implementable in a day)

* Start with base **gap = 3h**.
* If **upstream within 100 km** (bearing of mean wind) shows active precip in MRMS **or** short-range forecast (HRRR 0–3h) shows >50% chance of precip, **extend** allowable gap to **6h**.
* If surface temp remains **≤ 0°C** and pressure tendency indicates ongoing system (e.g., falling then steady), allow **+1–2h** grace.

This uses only fields we already touch (MRMS grids, a simple wind vector proxy, and t2m). It’s deterministic and easy to unit test. We’ll refine later with optical-flow echo tracking.

---

## 7) DuckDB Quick Patterns

**Read Parquet + query:**

```sql
INSTALL parquet; LOAD parquet;
SELECT platform, COUNT(*) FROM 'data/derived/stations.parquet' GROUP BY 1;
```

**Python API:**

```python
import duckdb
con = duckdb.connect()
con.execute("SELECT COUNT(*) FROM read_parquet('data/derived/*.parquet')").fetchall()
```

---

## 8) DVC Artifact Example

```bash
# track a small grid artifact
python scripts/make_dummy_grid.py  # writes data/grids/hrrr_v4_latlon.npz

dvc add data/grids/hrrr_v4_latlon.npz
git add data/grids/hrrr_v4_latlon.npz.dvc .gitignore
git commit -m "Track HRRRv4 lat/lon grid via DVC"
# push to MinIO
make up  # ensure minio is running
dvc push
```

---

## 9) How This Supports the Future Multi‑Repo Split

**Current boundaries** map 1:1 to future repos:

* `src/ingestion/*` → **snoiq-ingest**: data fetchers (MRMS/ERA5/HOMR), formatters, writers (Parquet), and later DB upserts (Postgres), plus Prefect flows.
* `src/physics/*`, `src/features/*`, `src/training/*` → **snoiq-train**: SLR functions, features, label builders, training loops (MLflow), model registry and artifact export.
* `src/core/*` (to be added later) → **snoiq-core**: inference wrappers, API IO contracts, GPT narrative generator.
* `src/app/*` (N/A here) → **snoiq-app** UI-only.

**Shared code** becomes `snoiq-common` with versioning. Migration steps when ready:

1. Freeze APIs with tests.
2. `git subtree split` each subdir to new repos.
3. Publish `snoiq-common` to a private index; pin versions in downstream repos.
4. CI in each repo runs the same golden tests.

This lets us keep today’s velocity (single workbench) and achieve tomorrow’s isolation without rework.

---

## 10) Next Actions (Checklist)

* [ ] Paste `pixi.toml`, `docker-compose.yml`, `Makefile` updates.
* [ ] `pixi install` → `make up` → `dvc init` and configure MinIO remote.
* [ ] Drop **tiny** MRMS sample at `data/raw/mrms/sample_qpe.grib2` and a 3–5 row `data/golden/uscrn_points.csv`.
* [ ] Add the three modules and tests from §3–4. `make test` should pass (skips if sample missing).
* [ ] Create `notebooks/01-ingestion/mrms_totals.ipynb` using the pattern in §5.
* [ ] (Optional) Implement Adaptive Event Segmentation v0 as a pure function in `src/ingestion/events.py` with unit tests.

When all boxes are checked, M0 + M1 are essentially done and we proceed to M2 (HOMR/Parquet/DuckDB bake-off) and M3 (ERA5 profiles → SLR v1).
