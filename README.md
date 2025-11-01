# Experiment Workbench

This repository is the central R&D workbench for SnoIQ. It is used for prototyping, experimentation, and validating pipelines before they are "graduated" to production-ready microservices.

## Folder Structure & Reasoning

### `/data`

* **Purpose:** To hold small, sample data files for quick, local tests.
* **Contains:** Sample `.grib2` files, `.tif` files, or small CSVs.
* **NOTE:** This folder is **NOT** for the multi-terabyte dataset. The full dataset is versioned with **DVC** and stored in our object storage (MinIO). This folder is only for files small enough to commit to Git (or be used in a quick test).

### `/notebooks`

* **Purpose:** The R&D "sandbox." This is where all interactive experimentation, data exploration, and model prototyping happens.
* **Contains:** `.ipynb` (Jupyter) files.
* **Workflow:** This folder is expected to be "messy." It's a lab notebook for trying new ideas. When a concept is proven, the clean logic is "graduated" into the `/src` folder.

### `/src`

* **Purpose:** To store clean, reusable, production-quality code.
* **Contains:** `.py` Python files, organized as a proper package.
* **Workflow:** Code here should be well-documented and unit-tested. Notebooks in `/notebooks` should import functions *from* this folder. This is the "contract" we hand off to our coding agents for final delivery.

### `/tests`

* **Purpose:** To hold the "golden tests" and unit tests for the code in `/src`.
* **Contains:** `test_*.py` files (using `pytest`).
* **Workflow:** These tests are the "contract" for our agents. When an agent refactors code in `/src`, its primary goal is to ensure all tests in this folder pass.

---

### Project Folder Structure (The "Blueprint")

```markdown
snoiq-experiments/
│
├── .pixi/                # (Ignored by Git) The local environment managed by pixi
├── .dvc/                 # (Checked into Git) DVC's internal metadata
├── .dvcignore            # (Checked into Git) Tells DVC to ignore temp files
├── .gitignore            # (Checked into Git) Ignores .pixi/, .venv/, __pycache__/
│
├── pixi.toml             # 🔵 The MASTER file for your environment (replaces requirements.txt)
├── pixi.lock             # 🔵 The lockfile that makes your environment reproducible
│
├── data/
│   │   # This folder contains sample data for testing
│   ├── raw/
│   │   └── sample_hrrr_run.grib2
│   │
│   ├── grids/
│   │   │   # This .npz file is your "source artifact"
│   │   ├── grid_latlon__model-HRRRv4.npz.dvc   <-- 1KB DVC pointer file
│   │   └── .gitignore                          <-- Ignores the actual .npz file
│   │
│   └── (Your 6TB Parquet Data Lake is NOT here. It's in MinIO, managed by DVC)
│
├── notebooks/            # 🔬 Your R&D "lab" for messy, interactive experiments
│   ├── 01-ingestion/
│   │   ├── test_grib_parsing.ipynb
│   │   └── test_homr_api.ipynb
│   │
│   ├── 02-feature-engineering/
│   │   └── test_grid_join.ipynb
│   │
│   └── 03-training/
│       └── initial_model_training.ipynb
│
├── src/                  # 📦 Your clean, reusable Python package
│   ├── __init__.py
│   │
│   ├── ingestion/
│   │   ├── hrrr.py       # <-- Your graduated, clean HRRR Prefect flow
│   │   └── uscrn.py      # <-- Your graduated, clean USCRN flow
│   │
│   ├── features/
│   │   ├── grid.py       # <-- Your `get_5x5_grid` function
│   │   └── build_features.py
│   │
│   ├── training/
│   │   └── train.py      # <-- Your graduated `mlflow` training script
│   │
│   └── models/
│       └── schema.py     # <-- Your Postgres table definitions (GridReference)
│
└── tests/                #  CONTRACT: The "golden tests" for your agent
    ├── test_ingestion.py
    └── test_features.py
```

### The Core Workflow (How You Use It)

1. Setup: You run `pixi install` once. This builds your complete environment (Python, CUDA, Pygrib, etc.).

2. R&D: You run `pixi run jupyter lab` (or just open a `.ipynb` file in VS Code). You experiment in the `notebooks/` folder.

3. Graduate: You copy/paste your working functions from the notebook into the `src/` folder.

4. Test: You write a "golden test" in the `tests/` folder to prove your `src/` code works.

5. Run Pipeline: You run your full, clean pipelines using `prefect` and `pixi`:

   * `pixi run python src/ingestion/hrrr.py` (to run the Prefect flow)

   * `pixi run python src/training/train.py` (to run the MLflow training)

6. Handoff: You give your coding agent the `src/` code and `tests/` as its "contract" to build the production repos.