# SnoIQ Functional Specification Document (v1)

## 1. Overview

### Purpose
Defines the **functional specifications** for the **SnoIQ System**, comprising:
- **Predictive Model (Part I):** Real-time snowfall prediction (*deferred until after Winter 2026/2027; see §3.6*).
- **Reanalysis Model (Part II):** Post-event snowfall reconstruction using MRMS, CRN, ASOS, and CoCoRaHS data.

### Objectives
- Develop and test the Reanalysis Model during **Winter 2025/2026**.
- Deploy a full operational system by **Winter 2026/2027**.
- Maintain compatibility with **HRRRv4** and migrate to **RRFSv2** in ~FY27.

### System Goals
- Physically consistent snowfall estimation (QPE × SLR).
- Terrain-aware, bias-corrected results.
- Transparent, explainable, and defensible methodology.
- Modular architecture designed for RRFSv2 integration.

---

## 2. System Architecture

### Components
- **Data Ingestion Layer:** Collects MRMS, HRRR, CRN (HTTP), CoCoRaHS (GHCN-Daily), ASOS (GHCN-Hourly).
- **Physics Engine:** Generates Physics_Estimate_Grid.
- **ML Reanalysis Engine:** Learns residual correction.
- **Predictive Engine:** **Deferred**; forecast inference begins **after Winter 2026/2027** once a full season of reanalysis exists (see §3.6).
- **Event Engine:** Detects and merges hazardous events.
- **Narrative Engine:** Creates structured JSON → LLM narratives.
- **Reporting Layer:** Generates defensible snowfall reports.

### Data Flow
1. MRMS → Precip Type (SPT), QPE, Surface Temps
2. HRRR/RAP → Soundings & SLR inputs
3. Stations → Ground truth totals (CRN, ASOS, CoCoRaHS)
4. Fuse into Physics_Estimate_Grid
5. Apply ML residual model → Final_Corrected_Grid
6. Detect events → Generate narrative → Report

---

## 3. Functional Modules

### 3.1 Data Ingestion Layer
**Sources:**
- MRMS: `PrecipFlag_00.00`, `MultiSensor_QPE_01H_Pass2_00.00`, `Model_SurfaceTemp_00.00`, `Model_WetBulbTemp_00.00`
- HRRRv4: AWS Open Data (analysis grids, profiles)
- CRN: **HTTP** (CRNH02 hourly over HTTPS endpoints)
- ASOS: GHCN-Hourly (PSV format)
- CoCoRaHS: **GHCN-Daily** integration (daily snowfall/liquid totals)

**Functions:**
- Hourly and daily ingestion with checkpointing.
- Validation (checksum, timestamp sanity).
- Grid mapping (station lat/lon → grid indices).

**Outputs:**
- Time-indexed, validated records in PostgreSQL.

---

### 3.2 Precipitation Type Classification (MRMS SPT Integration)
**Inputs:**
| Field | MRMS Product | Purpose |
|-------|---------------|----------|
| `PrecipFlag_00.00` | SPT | Base precip type |
| `MultiSensor_QPE_01H_Pass2_00.00` | QPE | Measurable precip gate |
| `Model_SurfaceTemp_00.00` | Surface Temp (°C) | Frozen-phase refinement |
| `Model_WetBulbTemp_00.00` | Wet-bulb Temp (°C) | Phase threshold |

**Logic:**
- Use MRMS `PrecipFlag` as the foundation.
- Apply temperature-phase thresholds:
  - Snow (SN): Tw ≤ -0.5°C and T ≤ 0°C
  - Sleet (IP): -0.5 ≤ Tw ≤ 0.2°C and -1 ≤ T ≤ 1°C
  - Freezing Rain (FZRA): Tw ≤ -0.1°C and T > 0°C
  - Rain (RA): T > 1.5°C and Tw > 0.5°C
  - Hail (H): Preserve radar flag

**Outputs:** `phase_snoiq` (SN, IP, FZRA, RA, H), `hazard_flag` (bool)

**Validation:** Confusion matrices vs. ASOS present weather codes.

**Design Note — Spectral-Bin Classifier Concept (Optional):**
To further reduce boundary jitter near 0°C, we may layer a probabilistic, spectral-bin style classifier on top of deterministic thresholds. The idea is to build a small set of bins across (T, Tw) and relevant MRMS signal-quality/meta fields (e.g., PF confidence), estimate per-bin conditional probabilities for {SN, IP, FZRA, RA} from historical truth (ASOS present-weather + CoCoRaHS timing), and then blend deterministic output with these probabilities via a calibrated logistic or isotonic mapping. This preserves backward-compatibility while enabling softer transitions in marginal regimes.

---

### 3.3 Dynamic Snow-to-Liquid Ratio (SLR) Computation
**Purpose:** Calculate grid-based hourly SLR for snow conversion.

**Inputs:** HRRR/RAP soundings → T, Td, RH, wind.

**Method:**
- Regression-based approach per Roebber (2013):
  \[ SLR = a + bT_{dgz} + cRH_{dgz} + dW_s + eT_{surf} \]
- Capped between 5:1–30:1.
- Validation: ΔSnowDepth (CRN) vs. accumulated snow.

**Outputs:** Hourly SLR grid (1 km × hourly).

---

### 3.4 Physics_Estimate_Grid Generation
**Formula:**
`Hourly_Snowfall = MRMS_QPE_Pass2 × Dynamic_SLR`

**Details:**
- MRMS 1 km resolution.
- Output in cm/hr, summed by event.
- Forms baseline for ML residual training.

---

### 3.5 ML Hybrid Correction Model
**Goal:** Predict residual errors between physics-first grid and observations.

**Target:** `y = GroundTruth_Total − Physics_Estimate_Grid_Total`

**Model:** Random Forest (champion), LightGBM/XGBoost (challenger)

**Features:**
- First-Guess: total snow, QPE, mean SLR.
- Microclimate: elevation, slope, aspect, landcover, distance_to_water.
- Dynamic: mean 850 mb temp, duration, wind.

#### 3.5.1 Ground Truth Data Hierarchy

The ML-Hybrid Correction Model integrates multiple observation sources to balance **temporal fidelity**, **spatial density**, and **data quality**:

| Source | Temporal Resolution | Spatial Density | Weight | Purpose |
|---------|--------------------|-----------------|--------|----------|
| **CRN (U.S. Climate Reference Network)** | Hourly | Sparse | 1.0 | High-quality “anchor” dataset for model calibration. Provides trusted benchmark snowfall and SWE. |
| **ASOS (Automated Surface Observing System)** | Hourly | Moderate | 0.8 | Intermediate dataset bridging CRN and CoCoRaHS, offering hourly reports near urban areas. Useful for bias-learning in mixed-phase or transition regions. |
| **CoCoRaHS (Community Collaborative Rain, Hail & Snow Network)** | Daily | Dense | 0.9 | Fills spatial gaps with daily totals. Temporally disaggregated using the weighted-physics method. Critical for localized bias learning. |

**Integration Workflow**
1. Each ground-truth observation is spatially mapped to its corresponding 1 km grid cell via the precomputed `station_lookup` table.  
2. CRN and ASOS hourly data are directly aligned with the Physics_Estimate_Grid timestamps.  
3. CoCoRaHS daily totals are downscaled to hourly using the “physics-guided disaggregation” algorithm (Section 3.5.2).  
4. All samples are combined into a unified training dataset with weighted loss functions reflecting data confidence (e.g., CRN > CoCoRaHS > ASOS).  
5. Outlier filtering and precipitation-type consistency checks (from Section 3.2) ensure data integrity before training.

**Rationale**
This blended truth hierarchy allows the ML model to learn both the *physical error patterns* from CRN and the *spatial heterogeneity* from CoCoRaHS, while ASOS enhances *temporal realism* in mixed-phase and transition zones (urban and airport regions).  
It dramatically increases hourly training coverage without degrading model trustworthiness.

#### 3.5.2 Physics‑Guided Disaggregation (CoCoRaHS)
**Input:** 24‑h CoCoRaHS total and colocated hourly Physics_Estimate_Grid series.

**Algorithm:**
1. Sum physics hourly snowfall at the station’s grid cell to get `Physics_24h_Sum`.
2. Compute hourly weights `w_h = physics_h / Physics_24h_Sum`.
3. Distribute error: `y_h = (Truth_24h − Physics_24h_Sum) × w_h`.
4. Label per hour: residual target `y_h` at that timestamp/location.

**Outcome:** Converts daily totals into 24 hourly labels aligned with physics timing, unlocking dense training without temporal aliasing.

---

### 3.6 Predictive Model (Forecast Mode)
**Status & Timing:** Deferred until **after Winter 2026/2027**, once a full season of Reanalysis data (Final_Corrected_Grid) is available for training. Forecast operations will begin post-retraining on that first complete dataset.

**Planned Inputs:** HRRR (and later RRFSv2) forecast grids + static features.  
**Planned Output:** Hourly and cumulative snowfall forecast.  
**Planned Retraining:** Post-winter retraining using newly accumulated Final_Corrected_Grid targets.

---

### 3.7 Event Detection & Segmentation
**Logic:**
- Hazard if frozen precip + QPE > 0.
- Merge events with ≤3 h lull.
- Terminate if >6 h break or >1 mm pure rain.

**Outputs:** Event table with start, end, duration, phase sequence.

**Edge Cases:**
- Overlapping synoptic/lake-effect events.
- Multi-day events crossing UTC boundaries.

---

### 3.8 Event Condenser & LLM Narrative Generation
**Inputs:** Hourly event data (QPE, SLR, phase).

**JSON Example:**
```json
{
  "event_start": "2025-01-20T02:00:00Z",
  "event_end": "2025-01-20T18:00:00Z",
  "total_snowfall": 10.2,
  "key_phases": [
    {"time": "02:00", "type": "light snow"},
    {"time": "06:00", "type": "sleet"},
    {"time": "08:00", "type": "heavy snow"}
  ]
}
```
**LLM Prompt:** Summarize storm evolution and transitions professionally for facilities managers.

---

### 3.9 Defensible Report Generation
**Tiers:**
1. Automated Reanalysis – totals + LLM narrative.
2. Forensic Reanalysis – adds Physics_Estimate_Grid and XAI breakdown.
3. Expert Witness – CCM-reviewed, affidavit included.

**Explainable AI:** Permutation Feature Importance identifies major correction drivers.

---

### 3.10 Directional Line‑of‑Attack Features (New)
**Objective:** Improve narratives and ML residual skill by capturing **storm approach direction** and upwind context for each location.

**Method (Neighborhood Feature Extraction):**
- For each grid cell (i,j) and hour t within the Hazardous Period, compute features over a **3×3** (and optionally **5×5**) neighborhood centered at (i,j):
  - Upwind mean QPE and snowfall (based on storm motion vector \(\vec{V}_{storm}\) estimated from cross‑correlation of successive MRMS reflectivity/QPE frames).
  - Upwind vs. downwind gradient of QPE and snowfall (directional finite differences along \(\vec{V}_{storm}\)).
  - Anisotropy metrics (ratio of along‑track to cross‑track variance of snowfall/QPE).
- Aggregate hourly to event‑level descriptors (e.g., max upwind gradient, mean along‑track accumulation).

**Outputs:**
- `dir_attack_vector` (u,v components per event)
- `upwind_mean_qpe`, `upwind_mean_snow`
- `alongtrack_grad`, `crosstrack_grad`, `anisotropy_ratio`

**Use Cases:**
- **Narratives:** “Heavy snowbands approached from the WSW; peak intensities aligned along the storm track.”
- **ML Features:** Adds spatial‑context cues that help correct systematic banding biases and lake‑effect alignment errors.

---

## 4. Landcover & Static Feature Integration
**Static Data Source (Updated):** Google Dynamic World V1 (10 m; global 2015‑present).

**Implementation:**
- Compute **modal class** (mode) or **top-1 probability** per 1 km cell.
- Apply **confidence filter** (≥ 0.6 probability).
- Aggregate temporally (e.g., 3-year composite or last full winter season).
- Fallback to NLCD 2019 where Dynamic World gaps exist.

**Feature Names:**
- `dw_landcover_mode`
- `dw_landcover_top1prob`

**Purpose:** Provide finer-resolution, seasonally adaptive land-cover inputs for microclimate bias correction (e.g., urban heat island, canopy retention).

---

## 5. HRRRv4 → RRFSv2 Transition Plan
**2025–2027:** Use HRRRv4 as baseline.  
**2027+:** Integrate RRFSv2 (MPAS-based core).

**Implementation:**
- Abstract model access behind provider API:
```python
def get_profile(model, lat, lon, t):
    if model == 'HRRR': return hrrr_profile(lat, lon, t)
    if model == 'RRFS': return rrfs_profile(lat, lon, t)
```
- Validate mapping of HRRR→RRFS fields (TMP, RH, REFC, QPF).
- Retrain SLR and ML models for new variable schema.

---

## 6. Non-Functional Requirements
| Category | Specification |
|-----------|----------------|
| Performance | <10 min/hour ingestion latency |
| Scalability | Regional parallel processing |
| Reliability | ≥ 99.9% uptime; checkpointed workflows |
| Traceability | Raw → ML lineage preserved |
| Security | Read-only data access; IAM-restricted |
| Auditability | Versioned model/config registry |
| Retraining | Seasonal; post-winter cycle |

---

## 7. Appendices
- MRMS variable registry (SPT, QPE, Temps).
- Station source weighting schema (CRN 1.0, CoCoRaHS 0.9, ASOS 0.8).
- Database schema summary (event_hour, station_lookup, physics_grid).
- Evaluation metrics: RMSE, MAE, bias.
- Model metadata registry (version, hyperparameters).
- Config files: `threshold.json`, `region-overrides.yaml`.

*End of SnoIQ Functional Specification Document (v1).*
