# LiDAR Relief Plugin v2.0 — Full Implementation Plan

*Scope: All 11 features across 3 phases, plus architectural upgrades.*

> **Status — completed:** This document is the historical implementation plan
> for work now delivered in v2.0. The current release is v2.0.21 with 29
> registered algorithms. It is retained for architectural rationale and
> traceability; it is not an active task list. Full-waveform LiDAR remains a
> research note rather than a production processing feature.

──────────────────────────────────────────────────────────────────────

## Architecture Overview

```
lidar_relief/
├── core/                    # Existing: NumPy algorithm cores
├── algorithms/              # Existing: QGIS Processing wrappers
├── export/                  # NEW: Output pipeline
│   ├── cog_exporter.py      #   Cloud-Optimized GeoTIFF
│   ├── web_viewer.py        #   MapLibre HTML generator
│   ├── field_packager.py    #   GeoPackage + offline tiles
│   └── report_generator.py  #   CIfA-compliant PDF
├── recipes/                 # NEW: Visualization recipe system
│   ├── schema.py            #   JSON schema definitions
│   └── io.py                #   Import/export functions
├── point_cloud/             # NEW: Point cloud processing
│   ├── csf_filter.py        #   Cloth Simulation Filter
│   └── pdal_pipeline.py     #   PDAL ground classification
├── temporal/                # NEW: Multi-temporal analysis
│   └── dem_difference.py    #   Probabilistic DoD
├── fusion/                  # NEW: Multi-sensor fusion
│   └── sentinel_fusion.py   #   Sentinel-2 co-registration + blend
├── ml/                      # NEW: Machine learning inference
│   └── detector.py          #   ONNX inference wrapper
└── gpu/                     # NEW: GPU acceleration
    └── compute_backend.py   #   CuPy/NumPy dynamic dispatch
```

**Dependency strategy:** All new libraries are optional imports with
graceful fallbacks and clear error messages pointing users to the
correct `pip install` command for their OSGeo4W environment.

──────────────────────────────────────────────────────────────────────

## Phase 1 — Low-Risk Foundation

### 1.1 COG Web Export (3-5 days)

**Goal:** Any algorithm output → Cloud-Optimized GeoTIFF + interactive
MapLibre GL JS HTML viewer that can be uploaded to GitHub Pages,
S3, or any static host.

**Files:**
- `lidar_relief/export/__init__.py`
- `lidar_relief/export/cog_exporter.py` — wraps `rio cogeo create`
- `lidar_relief/export/web_viewer.py` — generates `index.html` with
  MapLibre GL JS + COG protocol
- `lidar_relief/algorithms/cog_export_algorithm.py` — QGIS Processing
  algorithm wrapper

**Dependencies:** `rio-cogeo`, `rasterio` (optional)

**Tests:**
- Test COG validity (tiled, overviews, byte offsets)
- Test HTML generation contains expected MapLibre boilerplate
- Test error handling when deps missing

**Edge cases:**
- DEMs with non-standard CRS (warn, reproject to EPSG:3857)
- Very large outputs (>500MB COG): warn about hosting costs
- Rasters with nodata: ensure nodata is preserved correctly
- Multi-band outputs (MSTP, PCA, e4MSTP, VAT): ensure all bands
  survive COG conversion

### 1.2 Field Survey Export (3-5 days)

**Goal:** Export anomaly detection points as GeoPackage with structured
archaeological schema, packaged alongside offline raster tiles for
QField / Mergin Maps field validation.

**Files:**
- `lidar_relief/export/field_packager.py`
- `lidar_relief/algorithms/field_export_algorithm.py`

**Dependencies:** QGIS Python API only (QgsVectorLayer, GeoPackage
driver built into GDAL)

**GeoPackage schema:**
```sql
CREATE TABLE anomalies (
  fid INTEGER PRIMARY KEY AUTOINCREMENT,
  anomaly_id TEXT NOT NULL,
  detection_method TEXT,    -- 'svf', 'hillshade', 'manual', etc.
  confidence REAL,          -- 0.0 to 1.0
  feature_type TEXT,        -- 'barrow', 'ditch', 'platform', 'unknown'
  field_status TEXT,        -- 'pending', 'confirmed', 'rejected'
  observer TEXT,
  photo_path TEXT,
  notes TEXT,
  timestamp TEXT,
  geometry GEOMETRY
);
```

**Tests:**
- Verify GeoPackage created with correct schema
- Verify QField can open the output
- Verify attribute domain constraints

### 1.3 Automated PDF Report (5-7 days)

**Goal:** Generate CIfA-compliant PDF reports containing:
- Input DEM metadata (CRS, resolution, extent, source)
- Algorithm parameters (full serialization)
- Histogram statistics with percentile bands
- Locator map and main visualization
- Processing timestamp and plugin version

**Files:**
- `lidar_relief/export/report_generator.py`
- `lidar_relief/algorithms/pdf_report_algorithm.py`
- `lidar_relief/export/templates/` — ReportLab drawing templates

**Dependencies:** `reportlab` (pure Python, OSGeo4W-compatible)

**Tests:**
- Verify PDF generated with correct page structure
- Verify metadata fields present
- Verify histogram image embedded
- Verify multi-page output for large reports

### 1.4 Visualization Recipes (3-5 days)

**Goal:** Serialize/deserialize all processing parameters as a
human-readable JSON file that can be shared via GitHub Gist,
attached to publications, or imported by another user.

**JSON schema:**
```json
{
  "recipe_version": "1.0",
  "plugin_version": "1.3.5",
  "name": "Barrow detection - Wiltshire chalk",
  "author": "user@example.com",
  "description": "Optimized for round barrows on chalk downland",
  "landscape_type": "upland_steep",
  "algorithms": {
    "svf": { "radius": 10, "directions": 32, "noise": "low" },
    "slrm": { "trend_radius": 20 },
    "hillshade": { "azimuths": [315, 45, 135, 225], "altitude": 35 }
  },
  "batch_preset": "upland_steep",
  "output_crs": "EPSG:27700",
  "tags": ["barrows", "chalk", "wiltshire"]
}
```

**Files:**
- `lidar_relief/recipes/__init__.py`
- `lidar_relief/recipes/schema.py` — JSON schema definitions and
  validation using Python `json` + `dataclasses`
- `lidar_relief/recipes/io.py` — import from file/URL, export to file,
  load into algorithm parameters
- Integration into Batch algorithm dialog (import/export buttons)

**Dependencies:** None (stdlib only)

**Tests:**
- Round-trip: export → re-import preserves all parameters
- Validation rejects malformed JSON
- Version migration from recipe v1.0 to future schemas
- Import from URL (GitHub Gist raw URL)

### 1.5 Point Cloud CSF Filter (5-7 days)

**Goal:** Generate archaeology-optimized DEMs directly from LAS/LAZ
files using the Cloth Simulation Filter, with parameter presets tuned
to preserve subtle earthworks.

**Files:**
- `lidar_relief/point_cloud/__init__.py`
- `lidar_relief/point_cloud/csf_filter.py`
- `lidar_relief/algorithms/csf_algorithm.py`

**Dependencies:** `cloth-simulation-filter` (optional)

**Parameters:**
- `cloth_resolution` (default: 0.5) — grid size in m
- `classification_threshold` (default: 0.5) — steep slope factor
- `max_window_size` (default: 10) — max window for steep slopes
- `preset` dropdown: `Archaeology (subtle)`, `Forest`, `Urban`,
  `Default`
- Archaeology preset uses low threshold to retain micro-relief

**Tests:**
- Verify with synthetic point cloud (flat + bumps)
- Verify with real LAS file if available
- Verify DEM output has correct CRS and extent
- Verify nodata handling

──────────────────────────────────────────────────────────────────────

## Phase 2 — Medium-Risk Expansion

### 2.1 Multi-temporal Change Detection (7-10 days)

**Goal:** Compute probabilistic DEM of Difference (DoD) between two
temporally separated DEMs of the same area, with Level of Detection
(LoD) masking to filter noise.

**Algorithm:**
```
DoD = DEM_new - DEM_old
σ_propagated = sqrt(σ_old² + σ_new²)
LoD = z × σ_propagated  (where z = 1.96 for 95% confidence)
significant_change = |DoD| > LoD
```

**Files:**
- `lidar_relief/temporal/__init__.py`
- `lidar_relief/temporal/dem_difference.py` — core computation
- `lidar_relief/temporal/alignment.py` — co-registration check,
  pixel-perfect alignment verification
- `lidar_relief/algorithms/temporal_difference_algorithm.py`

**Dependencies:** `xarray`, `rioxarray` (optional)

**Outputs:**
- DoD raster (signed float, units = metres)
- Significance mask (byte: 0 = no change, 1 = negative change,
  2 = positive change)
- Optional: volume change report (cubic metres of cut/fill)

**Tests:**
- Known-change synthetic DEMs (add/remove a mound)
- Verify LoD correctly masks noise below threshold
- Verify CRS mismatch detection and reprojection
- Multi-threaded processing for large rasters

### 2.2 Multi-Sensor Fusion (7-10 days)

**Goal:** Automatically co-register Sentinel-2 multispectral imagery
with LiDAR relief and provide fusion blend recipes combining
topographic and spectral information.

**Files:**
- `lidar_relief/fusion/__init__.py`
- `lidar_relief/fusion/sentinel_fusion.py` — download, co-register,
  resample
- `lidar_relief/fusion/blend_recipes.py` — fusion blend presets
- `lidar_relief/algorithms/fusion_algorithm.py`

**Dependencies:** `rasterio`, `rioxarray`, `requests` (for STAC API)

**Fusion recipes:**
| Name | LiDAR Layer | Satellite Bands | Blend |
|------|-------------|-----------------|-------|
| Terrain + Veg | SVF (hillshade) | B8,NIR,B4 (CIR) | SVF as luminance, CIR as colour |
| Crop Marks | LD (concavity) | B4,B3,B2 (true) | 50% overlay |
| Erosion Risk | Slope | B11,SWIR | Multiplied with opacity |

**Tests:**
- Verify co-registration with known transform
- Verify band math correctness
- Test error handling for missing bands

### 2.3 PDAL Ground Classification (7-10 days)

**Goal:** Execute PDAL-based ground filtering pipelines with parameters
tuned for archaeological preservation, producing DEMs ready for
visualization.

**Files:**
- `lidar_relief/point_cloud/pdal_pipeline.py`
- `lidar_relief/point_cloud/ground_filters.py` — archaeology-tuned
  filter configurations
- `lidar_relief/algorithms/pdal_classify_algorithm.py`

**Dependencies:** `pdal` Python bindings (optional)

**Archaeology-tuned presets:**
- `archaeology_fine` — very low thresholds, maximum micro-relief
  preservation, based on LAStools `archaeology -fine`
- `archaeology_standard` — balance of vegetation removal and
  earthwork preservation
- `forested` — aggressive ground detection for dense canopy

**Filters used:**
- Progressive Morphological Filter (PMF)
- Cloth Simulation Filter (CSF) — reuse from Phase 1
- Statistical Outlier Removal (SOR) — minimal, to preserve edges

**Tests:**
- Verify pipeline JSON is valid PDAL spec
- Test with synthetic point cloud data
- Error handling for corrupt LAS files

──────────────────────────────────────────────────────────────────────

## Phase 3 — High-Risk / Experimental

### 3.1 AI/ML ONNX Inference (10-14 days)

**Goal:** Optional module that loads a user-provided ONNX model and
runs inference on plugin visualizations, producing vector detection
layers (bounding boxes or segmentation polygons).

**Files:**
- `lidar_relief/ml/__init__.py`
- `lidar_relief/ml/detector.py` — model loading, preprocessing,
  inference, postprocessing
- `lidar_relief/ml/preprocessing.py` — convert rasters to model-
  appropriate tensors (tiling, normalization)
- `lidar_relief/ml/postprocessing.py` — NMS, confidence thresholding,
  polygon extraction
- `lidar_relief/ml/model_registry.py` — known model formats and
  label maps
- `lidar_relief/algorithms/ai_detection_algorithm.py`

**Dependencies:** `onnxruntime` or `onnxruntime-openvino` (optional)

**Supported model types:**
- Object detection (YOLOv5/v8/v11): returns bounding boxes
- Semantic segmentation (U-Net): returns pixel-wise class labels
- Instance segmentation (Mask R-CNN): returns polygons per instance

**User workflow:**
1. User trains model externally (PyTorch, ultralytics, etc.)
2. Exports to ONNX format
3. Provides `.onnx` file + `labels.json` to plugin
4. Plugin runs inference on any open raster
5. Returns vector layer with confidence scores

**Tests:**
- Mock ONNX model with known outputs
- Verify preprocessing produces correct tensor shapes
- Verify post-processing filters by confidence threshold
- Test error handling for missing/broken model files

### 3.2 GPU CuPy Acceleration (10-14 days)

**Goal:** Provide GPU-accelerated backends for the computationally
intensive horizon-scanning algorithms (SVF, ASVF, Openness, Local
Dominance) with transparent fallback to NumPy.

**Files:**
- `lidar_relief/gpu/__init__.py`
- `lidar_relief/gpu/compute_backend.py` — dynamic dispatch:
  detect CuPy + CUDA, route accordingly
- `lidar_relief/gpu/svf_gpu.py` — CuPy-native SVF implementation
- `lidar_relief/gpu/openness_gpu.py` — CuPy-native Openness
- `lidar_relief/gpu/asvf_gpu.py` — CuPy-native ASVF
- `lidar_relief/gpu/local_dominance_gpu.py` — CuPy-native LD

**Dependencies:** `cupy-cuda12x` (optional, NVIDIA only)

**Architecture:**
```python
def get_compute_backend():
    """Return 'cupy' if CUDA available, else 'numpy'."""
    try:
        import cupy
        if cupy.is_available():
            return 'cupy'
    except ImportError:
        pass
    return 'numpy'
```

**Benchmarks (from research):**
- SVF 32-direction: ~270× speedup on GPU
- Openness: ~100× speedup
- Main bottleneck: PCIe transfer of large DEMs to GPU memory
- Tile size optimization: 1024×1024 blocks for best throughput

**Tests:**
- Exact numerical equivalence between CuPy and NumPy paths
- Memory boundary checks (padded arrays on GPU)
- Graceful fallback when CuPy unavailable
- Benchmark comparison (optional, informational)

### 3.3 Full-Waveform LiDAR (research phase)

**Goal:** Understand the landscape and provide basic tooling for
full-waveform LiDAR data processing, deferring deep integration
until the ecosystem matures.

**Files:**
- `lidar_relief/point_cloud/full_waveform.md` — research notes
- `lidar_relief/point_cloud/waveform_reader.py` — basic readers
  if open specifications are available

This is primarily a research task — document available open-source
libraries, data formats, and published methods. Implement basic
readers only if the data format specification is openly published.

──────────────────────────────────────────────────────────────────────

## Integration and Cross-Cutting Work

### Integration into Batch Algorithm

The Batch algorithm dialog should gain:
- [ ] Recipe import/export buttons
- [ ] "Export as COG" checkbox per algorithm output
- [ ] "Generate PDF report" checkbox
- [ ] "Package for field survey" checkbox

### Plugin Dependencies Management

New `lidar_relief/dependencies.py` module:
```python
# Centralized dependency checking with user-friendly messages
DEPENDENCIES = {
    'rio-cogeo': {
        'import': 'rio_cogeo',
        'pip': 'rio-cogeo',
        'purpose': 'Cloud-Optimized GeoTIFF export',
    },
    'reportlab': {
        'import': 'reportlab',
        'pip': 'reportlab',
        'purpose': 'PDF report generation',
    },
    # ... etc
}

def check_dependency(name: str) -> bool:
    """Check if optional dependency is available, return True/False."""

def require_dependency(name: str) -> None:
    """Check dependency or raise ImportError with install instructions."""
```

### Testing Strategy

| Phase | Test type | Coverage target |
|-------|-----------|----------------|
| All | Unit tests (pytest) | Core logic: 100% |
| 1.1, 1.3 | File format validation | COG validity, PDF structure |
| 1.2 | GeoPackage schema check | Schema conformance |
| 1.4 | Round-trip serialization | Param preservation |
| 1.5, 2.3 | Synthetic point cloud | Pipeline correctness |
| 2.1 | Synthetic time-series | DoD accuracy |
| 2.2 | Synthetic band math | Fusion correctness |
| 3.1 | Mock model inference | Pipeline integrity |
| 3.2 | Numerical equivalence | CuPy == NumPy |

### Documentation

Each major feature needs:
- Docstring with `exports:`, `used_by:`, `rules:` (project convention)
- Entry in README.md feature table
- Entry in CHANGELOG.md on release

──────────────────────────────────────────────────────────────────────

## Estimated Timeline

| Phase | Features | Est. time | Lines added |
|-------|----------|-----------|-------------|
| 1.1 | COG Web Export | 3-5 days | ~400 |
| 1.2 | Field Survey Export | 3-5 days | ~350 |
| 1.3 | PDF Report | 5-7 days | ~600 |
| 1.4 | Viz Recipes | 3-5 days | ~300 |
| 1.5 | CSF Filter | 5-7 days | ~400 |
| 2.1 | Temporal dDEM | 7-10 days | ~500 |
| 2.2 | Sentinel-2 Fusion | 7-10 days | ~600 |
| 2.3 | PDAL Pipeline | 7-10 days | ~500 |
| 3.1 | ONNX Inference | 10-14 days | ~700 |
| 3.2 | CuPy Acceleration | 10-14 days | ~800 |
| 3.3 | Full-waveform research | 3-5 days | ~100 + doc |
| | **Total** | **~65-95 days** | **~5,250** |

Note: This roughly doubles the codebase (currently ~4,700 lines). Each
day assumes focused work with AI assistance.

──────────────────────────────────────────────────────────────────────

## Historical starting point

This plan began at commit `1a80682`, when v1.3.5 was the current release.
Implementation subsequently landed on the default branch and culminated in the
v2 series. For current installation, behavior, and support information, use
the repository README, USER_GUIDE, CHANGELOG, and official QGIS listing.
