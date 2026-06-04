# Changelog

All notable changes to LiDAR Relief Visualization are documented here.

---

## [2.0.1] - 2026-06-04

### Fixed
- Bumped version to align with plugins.qgis.org submission.
- Fixed flake8 W503, E203, E402 lint warnings in `fusion_algorithm.py`, `compute_backend.py`, and `test_csf_filter.py`.
- Restored `setup.cfg` with flake8 ignore rules for W503 and E203.
- Fixed `NameError: name 'VecVecFloat' is not defined` in `point_cloud/csf_filter.py`
  when loading the plugin without the `cloth-simulation-filter` package installed.
  The return type annotation `-> VecVecFloat` was evaluated at module import time;
  changed to a string literal for lazy evaluation so the plugin loads correctly
  regardless of optional dependencies.

---

## [2.0.0] - 2026-06-04

### Added — Export Pipeline (LiDAR Relief — Export group)

- **Cloud-Optimized GeoTIFF (COG) Export**: Convert any algorithm output to a
  cloud-optimized GeoTIFF with internal tiling, overviews, and DEFLATE/LZW/ZSTD
  compression. Optionally generates an interactive MapLibre GL JS web viewer
  with opacity controls, coordinate display, dark/light themes, and share-link
  copying. Suitable for direct upload to GitHub Pages or any static host.
  (`export/cog_exporter.py`, `export/web_viewer.py`; algorithm: `cog_export`)

- **Field Survey Export**: Package relief rasters and anomaly detection points
  into a GeoPackage with structured archaeological schema (anomaly_id,
  detection_method, confidence, feature_type, field_status) plus a QGIS project
  file that opens directly in QField/Mergin Maps for mobile ground-truthing.
  (`export/field_packager.py`; algorithm: `field_survey_export`)

- **PDF Report Generator**: Generate CIfA-compliant PDF reports with title page,
  full algorithm parameter documentation, input DEM metadata (CRS, resolution,
  extent), band statistics with percentiles, histogram chart, and certification
  section. Uses ReportLab (pure Python, OSGeo4W-safe).
  (`export/report_generator.py`; algorithm: `pdf_report`)

- **Visualization Recipes**: Import/export all algorithm parameters as
  shareable JSON files with versioned schema, validation, type checking, and
  metadata fields (name, author, tags, landscape type). Enables community
  sharing of optimized parameter presets beyond the 4 built-in landscape
  presets. (`recipes/__init__.py`; algorithms: `recipe_export`, `recipe_import`)

### Added — Point Cloud Processing (LiDAR Relief — Point Cloud group)

- **CSF Ground Filter (LAS/LAZ → DEM)**: Archaeology-tuned ground extraction
  using the Cloth Simulation Filter (CSF) with 4 presets: Archaeology Fine
  (maximum micro-relief preservation), Archaeology Standard (balanced),
  Forested (aggressive canopy), and Urban. Supports laspy and PDAL readers.
  (`point_cloud/csf_filter.py`; algorithm: `csf_ground_filter`)

- **PDAL Ground Classification Pipelines**: JSON-based pipeline builder for
  Progressive Morphological Filter (PMF) ground classification with
  archaeology-optimized parameters. Presets for fine, standard, and forested
  terrain, plus statistical outlier removal.
  (`point_cloud/pdal_pipeline.py`; 4 pipeline presets)

### Added — Multi-temporal Analysis (LiDAR Relief — Temporal group)

- **Multi-temporal Change Detection**: Compute a probabilistic DEM of
  Difference (DoD) between two temporally separated DEMs with propagated
  RMSE-based Level of Detection (LoD) masking. Outputs include signed DoD
  raster, significance mask (erosion/deposition), and cut/fill volume report.
  (`temporal/dem_difference.py`; algorithm: `temporal_difference`)

### Added — Multi-Sensor Fusion (LiDAR Relief — Fusion group)

- **Multi-Sensor Fusion**: Co-register Sentinel-2 multispectral bands with
  LiDAR relief and apply blend recipes combining topographic and spectral
  information. Four recipes: Terrain+CIR (SVF + Colour Infrared), Crop Mark
  Enhancement (Local Dominance + true colour), Erosion Risk (Slope + SWIR),
  and Bare Earth Composite (SLRM + SWIR). Blend modes: luminance overlay,
  overlay, multiply, screen.
  (`fusion/sentinel_fusion.py`; algorithm: `multi_sensor_fusion`)

### Added — AI/ML Inference (LiDAR Relief — AI/ML group)

- **AI Feature Detection**: Load user-provided ONNX models for object
  detection (YOLO) or semantic segmentation (U-Net) on plugin visualizations.
  Features tiled processing for large rasters, Non-Maximum Suppression,
  confidence filtering, and GeoPackage export of bounding box detections.
  Pure NumPy preprocessing — no OpenCV dependency at inference time.
  (`ml/detector.py`; algorithm: `ai_feature_detection`)

### Added — GPU Acceleration

- **CuPy Compute Backend**: Transparent GPU acceleration for computationally
  intensive horizon-scanning algorithms (SVF, Openness). Automatically detects
  CUDA availability and dispatches to CuPy with graceful NumPy fallback. Uses
  the trigonometric identity `sin(arctan(dz/d)) = dz / sqrt(dz² + d²)` for GPU-
  optimized horizon scanning. (`gpu/compute_backend.py`)

### Fixed
- Fixed missing `compute_mstp` wrapper function in `core/mstp.py` that caused an
  `ImportError` when running the e4MSTP algorithm via Batch mode.

---

## [1.3.5] - 2026-06-04

### Fixed
- Fixed missing `compute_mstp` wrapper function in `core/mstp.py` that caused an
  `ImportError` when running the e4MSTP algorithm via Batch mode.

---

## [1.3.4] - 2026-05-31

### Changed
- Bumped version to clear broken 1.3.3 release tag.
- Updated changelog to document all algorithms added since initial release.
- Added `package.sh` helper script for correct local ZIP packaging.
- Removed leftover development scripts from project root.

---

## [1.3.3] - 2026-05-31

### Fixed
- Corrected plugin ZIP structure: files are now correctly nested under a `lidar_relief/` parent directory as required by the QGIS Plugin Manager. Previous releases had files at the archive root, causing installation to fail.

---

## [1.3.0] - 2026-05-26

### Added
- Enhanced 4-Scale Topographic Position (e4MSTP) composite visualisation (Kokalj 2025 method).
- PCA RGB Composite algorithm combining SVF, Openness, Slope, and Local Dominance into a single colour output.
- ML-Ready Export (VRT Stack) tool for machine learning and multi-band analysis workflows.

---

## [1.2.0] - 2026-05-26

### Added
- Topographic Openness algorithm (positive and negative modes).
- Multi-Scale Topographic Position (MSTP) algorithm.
- VAT Composite algorithm.
- Anisotropic Sky-View Factor (ASVF) with configurable illumination direction and weight.
- Simple Red Relief and Blend algorithms.
- Local Dominance algorithm.
- Landscape Scale Presets for the Batch algorithm: Flat/Agricultural, Forested, Upland/Steep, and Coastal — parameters derived from peer-reviewed LiDAR visualisation literature.

---

## [1.1.0] - 2026-05-26

### Added
- Tile-based processing engine (`process_in_tiles`) for memory-efficient handling of large DEMs.
- Automatic layer styling post-processor applied to all algorithm outputs.

### Changed
- Refactored all algorithms to share a common raster I/O utility layer.

---

## [1.0.13] - 2026-05-25

### Fixed
- Added `contents: write` permissions to the GitHub Actions release workflow.

---

## [1.0.12] - 2026-05-25

### Fixed
- Added `--release-tag` flag to `qgis-plugin-ci` publish command to fix GitHub Release lookup.

---

## [1.0.11] - 2026-05-25

### Fixed
- Corrected `.qgis-plugin-ci` GitHub repository configuration parameter names.

---

## [1.0.10] - 2026-05-25

### Fixed
- Added GitHub org/repo configuration to `.qgis-plugin-ci`.

---

## [1.0.9] - 2026-05-25

### Fixed
- Corrected `.qgis-plugin-ci` formatting to valid YAML.

---

## [1.0.8] - 2026-05-25

### Fixed
- Fixed `ImportError` catching logic in the `scipy` fallback path.

---

## [1.0.7] - 2026-05-25

### Fixed
- Fixed numpy fallback broadcast shape error in SLRM Gaussian filtering.

---

## [1.0.6] - 2026-05-25

### Fixed
- Fixed GitHub Actions release workflow failing due to missing OSGEO credentials.

---

## [1.0.5] - 2026-05-25

### Changed
- Removed unused `docs/` folder from version tracking.
- Fixed README ZIP installation instructions.

---

## [1.0.4] - 2026-05-25

### Changed
- Removed `experimental` flag so the plugin is visible to all users by default in the QGIS Plugin Manager.

---

## [1.0.3] - 2026-05-25

### Fixed
- Bypassed mutually exclusive `W503`/`W504` flake8 lint rules using `any()`.

---

## [1.0.2] - 2026-05-25

### Fixed
- Resolved remaining PEP8 `W503` warnings for the QGIS linter.
- Standardised file permissions across the package.

---

## [1.0.1] - 2026-05-25

### Fixed
- Fixed PEP8 formatting issues (W291, W293, W503) and removed unused imports (F401).
- Updated plugin homepage, repository, and tracker metadata links.
- Included `LICENSE` file in the QGIS package.
- Updated QGIS compatibility range to 3.0–4.99.

---

## [1.0.0] - 2026-05-25

### Added
- Initial release.
- Multi-directional Hillshade algorithm.
- Simple Local Relief Model (SLRM) algorithm.
- Sky-View Factor (SVF) algorithm.
- Slope algorithm (degrees and percent).
- Batch mode for running multiple algorithms on the same DEM in one pass.
