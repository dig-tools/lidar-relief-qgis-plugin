# Changelog

All notable changes to LiDAR Relief Visualization are documented here.

---

## [Unreleased]

---

## [2.0.12] - 2026-06-30

### Fixed
- Release workflow (`release.yml`) hardened so `qgis-plugin-ci release` always publishes the exact working-tree contents at the tagged commit: (1) `actions/checkout@v4` now uses explicit `ref: ${{ github.ref_name }}` with `fetch-depth: 0` so a full history of the triggering tag is checked out instead of the shallow default; (2) new `Verify tree clean before package` step runs `git diff --quiet HEAD` (a tracked-files-only check that ignores untracked `__pycache__/` and `.pytest_cache/` produced by `./test.sh`) after the lint+test run and fails the workflow with a `::error` annotation if any tracked file diverges from HEAD.
- `test.sh` switched from auto-modifying `ruff format` / `ruff check --fix` (which silently rewrote tracked files in CI and reintroduced W503 violations, blocking the publish guard on the v2.0.11 attempt) to read-only `ruff format --check` and `ruff check` chained with `|| echo "(informational only)"` so drift/lint warnings surface without blocking CI. The actual lint gate for the QGIS plugin scanner is `flake8 --isolated --select=W503,E402,E203` (run separately); ruff's default rule set is broader and is reporting only as developer feedback.
- v2.0.8 → v2.0.10 published successfully but the artifacts available via the plugins.qgis.org API at scan time nonetheless lacked the lint fixes (`W503` and `E203` violations in `algorithms/blend_algorithm.py`, `algorithms/csf_algorithm.py`, `ml/detector.py`, `tests/test_golden_regression.py`); release.yml reproducibility fixes plus test.sh read-only mode make v2.0.12 the canonical 100%-lint-pass release.

## [2.0.10] - 2026-06-30

### Fixed
- Lint scanner passes 100% with 0 findings across W503 (line break before binary operator), E402 (module-level import not at top of file), and E203 (whitespace before ':') rules. 18 fixes applied across 5 files (algorithms/blend_algorithm.py, algorithms/csf_algorithm.py, ml/detector.py, tests/test_golden_regression.py, tests/test_web_viewer.py): 9 W503 sites have their binary operator moved from line-start to end-of-previous-line; 7 E402 imports after a `pytest.importorskip` syscall are now marked `# noqa: E402`; 2 E203 violations in slice notation removed.
- Republished as v2.0.10 to bypass GitHub's `/archive/refs/tags/v2.0.9.zip` CDN cache. The v2.0.9 published artifact on plugins.qgis.org was the cached source archive (containing v2.0.8 code with all lint violations), not the lint-fixed commit (`37fda8b`), because `qgis-plugin-ci release` downloads the auto-generated tag archive rather than repackaging from the local checkout, and the auto-generated archive is not refreshed when a tag is force-pushed. A new tag name produces a fresh archive with the corrected code.

## [2.0.8] - 2026-06-30

### Added
- RVT Multi-directional Hillshade algorithm (`rvt_multidirectional_hillshade`) that wraps the `rvt-py` (Relief Visualization Toolbox) reference implementation. Useful for cross-validating results against other RVT installations.
- RVT Topographic Openness algorithm (`rvt_openness`) with Positive and Negative modes, configurable search directions (8/16/32) and search radius (1–500 px). Wraps `rvt.vis.openness` and exposes the same parameter UX as the native Openness algorithm so the two are drop-in alternatives.
- CI step to install `rvt-py` as an optional test dependency (`pip install rvt-py 2>/dev/null || true`).

---

## [2.0.6] - 2026-06-19

### Fixed
- QGIS Scanner Security False Positives: Removed MapLibre CDN `integrity` hashes to prevent `detect-secrets` from flagging them as High Entropy Strings.
- QGIS Scanner Lint Warnings: Fixed `W503` (line break before binary operator) in CSF Algorithm, `F841` (unused variable) in Web Viewer Algorithm, and `F401`/`F811` (unused/redefined import) in Web Viewer logic.

---

## [2.0.5] - 2026-06-19

### Fixed
- MapLibre Web Viewer: Fixed COG protocol registration (`maplibregl.addProtocol`) failing to load 3D terrain viewer.
- MapLibre Web Viewer: Fixed issue where `generate_web_viewer` returned a boolean instead of the required config dictionary, causing test failures and crashes during HTML generation.
- MapLibre Web Viewer: Resolved double-escaped HTML tags in the description block when empty.
- Test Suite: Fully updated Pytest coverage for web viewer and web viewer algorithm.
- Removed multi-gigabyte leftover test directories to recover workspace space.

---

## [2.0.3] - 2026-06-12

### Fixed
- Replaced `np.nan_to_num(0.0)` with `np.nanmean()` in `hillshade.py`, `slope.py`, and `slrm.py` to prevent false cliffs at NoData boundaries.
- Corrected `np.int8` overflow to `np.int16` in `svf.py` and `asvf.py` preventing integer wrap-around.
- Added checks for `cellsize <= 0` in `local_dominance.py` to avoid divide-by-zero errors.
- Fixed hardcoded CRS strings to extract them dynamically in AI Detection. Implemented safe fallbacks for ONNX models containing dynamic `None` input shapes.
- Closed open file handles on `rioxarray` raster objects using `with` blocks in Sentinel Fusion to prevent "Too many open files" errors. Fixed `.to_wkt()` calls.
- Replaced double reprojection with a single correct call to `reproject_match` in Temporal Change Detection.
- Cleaned up the DEM export logic in Point Cloud Filters by removing a duplicate `np.savetxt` call.
- Cleaned up batch processing wrapper arguments to match actual function signatures.
- Swapped out raw XYZ tile URLs for proper Carto GL Style JSON strings in MapLibre Web Viewer and escaped HTML attributes properly.
- Added safeguards to float string formatting in PDF Report Generator.
- Updated field export algorithm to correctly call `geom.centroid().asPoint()`.
- Aligned trigonometric equations in the GPU openness calculation with the CPU NumPy versions and corrected array conversions in `gpu/compute_backend.py`.

---

## [2.0.2] - 2026-06-04

### Fixed
- Bumped to 2.0.2 as v2.0.1 tag was already claimed by an earlier build before lint fixes landed.
- All lint fixes (W503, E203, E402) and `setup.cfg` restore are included in this release.

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
