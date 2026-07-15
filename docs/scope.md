# PROJECT 19 — LiDAR Relief Visualization Plugin for QGIS

> **Document status:** Original project brief, updated 15 July 2026. The MVP
> and v2 roadmap described below have been delivered. The current v2.0.21
> plugin contains 29 Processing algorithms and supports QGIS 3 and QGIS 4.
> This brief is retained to document the original problem and design intent.

## Overview

A native QGIS plugin that generates all standard LiDAR-derived relief visualization filters — Simple Local Relief Model (SLRM), Sky-View Factor (SVF), Hillshade, Slope, Openness, and Multi-scale Topographic Position (MSTP) — directly from a loaded Digital Elevation Model (DEM) layer, without requiring the user to export to standalone tools like the Relief Visualization Toolbox (RVT) or SAGA GIS. The current workflow requires bouncing large DEM files between three separate applications. This plugin makes it a single click.

## Target users

- Landscape archaeologists prospecting for buried features using LiDAR
- Heritage managers analysing historic landscapes
- Aerial survey archaeologists processing drone-derived DEMs
- Environmental archaeologists mapping ancient land use
- Students learning landscape prospection techniques

## Delivered MVP scope (v1)

- Plugin integrates into QGIS 3.x Processing Toolbox
- Algorithm 1: Multi-directional Hillshade (standard + multi-azimuth)
- Algorithm 2: Simple Local Relief Model (SLRM) — removes large-scale topography to highlight micro-relief
- Algorithm 3: Sky-View Factor (SVF) — shows how much of the sky hemisphere is visible from each point
- Algorithm 4: Slope (degrees and percent)
- Progress bars for each algorithm
- Output directly as new raster layers in the QGIS layer panel
- Batch mode: run multiple algorithms on the same DEM in one click
- Works offline, no external dependencies beyond QGIS's bundled libraries (NumPy, GDAL)

## Delivered v2 scope

- Advanced terrain visualization: Openness, MSTP, Local Dominance, ASVF,
  e4MSTP, VAT, Simple Red Relief, PCA, RVT reference methods, and TRI.
- Batch processing, landscape presets, automatic styling, visualization
  recipes, and ML-ready exports.
- CSF and PDAL point-cloud preparation, multi-temporal change detection, and
  LiDAR/Sentinel-2 fusion.
- COG and interactive web export, QField survey packaging, PDF reporting,
  optional ONNX inference, and optional CuPy acceleration.
- QGIS 3.34 and QGIS 4.2 runtime validation, plus minimal-dependency CI.

## Tech stack recommendation

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python | QGIS Processing plugins are Python |
| Framework | QGIS Plugin API (QgsProcessingAlgorithm) | Native integration into QGIS Processing |
| Raster processing | NumPy + GDAL (bundled with QGIS) | No external dependencies needed |
| UI | Qt Designer forms within QGIS | Standard QGIS plugin UI approach |
| Distribution | QGIS Plugin Repository | Official channel, in-app install |

## Architecture notes

- Each visualization algorithm is a **QgsProcessingAlgorithm subclass** with standard QGIS inputs (raster layer, parameters) and outputs (new raster layer). This gives free integration with the QGIS Processing Toolbox, Modeler, and batch processing.
- Implement algorithms as **pure NumPy functions** that take a 2D elevation array and parameters and return a 2D output array. Keep QGIS-specific code in a thin wrapper layer. This makes the algorithms testable independently of QGIS.
- **SLRM algorithm**: subtract a heavily Gaussian-smoothed version of the DEM from the original DEM. The sigma of the Gaussian controls the scale of features enhanced. Expose this as a user parameter.
- **SVF algorithm**: for each pixel, sample the horizon elevation angle at N azimuths (e.g., 16 or 32 directions) over a search radius. SVF = 1 - mean(sin(horizon angles)). More directions = more accurate but slower. This is the computationally expensive algorithm — use vectorised NumPy operations and offer a "fast mode" with fewer directions.
- Use **GDAL's raster I/O** to handle projection, nodata values, and output file writing correctly. Never use raw file operations for raster I/O.

## Core algorithms (pseudocode)

```python
def slrm(dem_array, sigma_pixels=20):
    smoothed = gaussian_filter(dem_array, sigma=sigma_pixels)
    return dem_array - smoothed

def sky_view_factor(dem_array, cellsize, search_radius_m, num_directions=16):
    # For each cell, compute horizon angle in each direction
    # SVF = 1 - mean(sin(horizon_angle)) for all directions
    ...

def multidirectional_hillshade(dem_array, cellsize, azimuths=[315,45,135,225], altitude=45):
    # Blend hillshades from multiple azimuths
    ...
```

## Existing resources to leverage

- **Relief Visualization Toolbox (RVT)** — the definitive reference implementation in Python: https://iaps.zrc-sazu.si/en/rvt — **this is open source, study it extensively**
- **RVT GitHub** — https://github.com/EarthObservation/RVT_py — port the core algorithms
- **QGIS Plugin Developer Cookbook** — https://docs.qgis.org/3.28/en/docs/pyqgis_developer_cookbook/
- **QGIS Processing Provider tutorial** — how to structure a Processing plugin
- **SAGA GIS ta_lighting module** — reference for horizon scanning algorithm

## Technical risks

- **Performance on large DEMs** — landscape LiDAR DEMs can be 5,000×5,000 to 50,000×50,000 pixels. The SVF algorithm in particular is O(n × pixels) where n is the number of azimuth directions. Must run in a background thread and support cancellation. Consider offering tiled processing for very large DEMs.
- **Memory management** — a 50K×50K float32 DEM is 10GB in memory. Use GDAL's block reading to process large DEMs in tiles.
- **Edge effects** — all neighbourhood algorithms produce artefacts at raster edges. Apply appropriate padding or clearly mark edge pixels as no-data.

---

## Deep Research Prompt — Project 19

> I am building a QGIS plugin for LiDAR-derived archaeological relief visualisations. I need research:
>
> 1. **Relief Visualization Toolbox (RVT)**: Provide a detailed technical description of RVT and its algorithms. What visualization types does it implement? What are the mathematical definitions of SLRM, SVF, Openness, MSTP, and Local Dominance? Where is the RVT Python source code? Is it MIT or similarly permissive licensed for derivative works?
>
> 2. **QGIS Processing plugin development**: How does the QGIS 3.x Processing plugin API work? What are the key classes (QgsProcessingAlgorithm, QgsProcessingProvider, QgsProcessingParameterRasterLayer)? What is the recommended project structure for a QGIS Processing plugin? How is a plugin submitted to the QGIS Plugin Repository?
>
> 3. **SVF algorithm implementation**: What is the exact mathematical definition of Sky-View Factor for topographic analysis? How is it computed from a gridded DEM? What is the horizon scanning algorithm? What approximations are used to make it computationally tractable in NumPy? Are there any GPU-accelerated implementations?
>
> 4. **Archaeological LiDAR use cases**: What specific archaeological feature types are best detected by which visualisation algorithms? For example: which algorithm best reveals medieval ridge-and-furrow, Roman road agger, prehistoric enclosure ditches, or tropical site vegetation patterns? What colour ramps are recommended for each use case?
>
> 5. **QGIS raster processing with NumPy/GDAL**: What is the recommended pattern for reading a QGIS raster layer into a NumPy array, processing it, and writing the result back as a new QGIS layer? How should nodata values and coordinate reference systems be handled?
>
> 6. **MSTP algorithm**: What is Multi-scale Topographic Position (MSTP) and how is it computed? What scale ranges are recommended for archaeological prospection in different landscape types?

---
---
