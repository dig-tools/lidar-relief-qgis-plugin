# Changelog

All notable changes to LiDAR Relief Visualization are documented here.

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
