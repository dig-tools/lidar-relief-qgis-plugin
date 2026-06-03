# LiDAR Relief Plugin User Guide — v2.0

## Introduction
The LiDAR Relief QGIS Plugin provides archaeologically optimized terrain
visualization tools. It allows you to process Digital Elevation Models (DEMs)
into highly readable formats to identify subtle micro-topography such as
ancient ditches, walls, mounds, and paths.

**v2.0 expands the plugin from a pure visualization tool into a complete
prospection platform**, adding point cloud processing, multi-temporal change
detection, multi-sensor fusion, AI feature detection, and professional
export/publishing capabilities.

---

## Algorithm Reference

### Relief Visualization (15 algorithms)

| Algorithm | Description | Best For |
|-----------|-------------|----------|
| **Multi-directional Hillshade** | Blends illumination from 4+ sun azimuths | General prospection, ridge-and-furrow |
| **Simple Local Relief Model (SLRM)** | Removes macro-topography using trend radius | Barrows, mounds, platforms |
| **Sky-View Factor (SVF)** | Diffuse illumination simulation | General prospection, ditches |
| **Anisotropic SVF (ASVF)** | Directionally weighted SVF | Linear features perpendicular to light |
| **Topographic Openness** | Positive = ridges, Negative = valleys | Stone walls (positive), ditches (negative) |
| **Local Dominance** | Horizon-scanning ray trace | Subtle barrows, hollow ways |
| **Multi-Scale TP (MSTP)** | DEV at Broad/Meso/Local → RGB | Complex multi-period landscapes |
| **Enhanced 4-MSTP (e4MSTP)** | 4-step composite (LD+Openness+Slope+SVF+MSTP) | Flat terrain, alluvial plains |
| **VAT Composite** | Hillshade + Slope + Openness blend | European heritage base maps |
| **Simple Red Relief** | Patent-free RRIM analogue | Tropical/Mesoamerican surveys |
| **PCA Composite** | PCA of 16+ directional hillshades | Ridge-and-furrow, Roman roads |
| **Slope** | Degrees and percent | Terrain analysis |
| **Blend Visualizations** | Multiply, Screen, Overlay modes | Custom composites |
| **Batch Relief Visualisation** | Multi-algorithm single-pass | Survey workflow efficiency |
| **ML-Ready VRT Export** | Normalized multi-band composites | CNN/LiDAR training datasets |

---

### Export & Publishing (NEW)

#### Export to Cloud-Optimized GeoTIFF (COG)

Converts any algorithm output to a cloud-optimized GeoTIFF with internal
tiling and overviews. Optionally generates an interactive MapLibre GL JS
web viewer that can be uploaded to GitHub Pages, Netlify, S3, or any static
host.

**Workflow:**
1. Run any relief algorithm (e.g., SVF)
2. Run **Export to Cloud-Optimized GeoTIFF (COG)** on the output
3. Select a compression profile (DEFLATE, LZW, ZSTD, or raw)
4. Check "Generate interactive web viewer"
5. Upload both the `.tif` and the viewer folder to a web host

**Requirements:** `rio-cogeo` Python package (`pip install rio-cogeo`)

#### Package for Field Survey (QField/Mergin)

Packages relief rasters and anomaly detection points into a GeoPackage with
structured archaeological schema, plus a QGIS project file that opens directly
in QField on mobile devices.

**GeoPackage schema fields:**
- `anomaly_id` — Unique identifier
- `detection_method` — How the anomaly was detected (svf, hillshade, manual, etc.)
- `confidence` — Detection confidence 0.0–1.0
- `feature_type` — Interpreted type (barrow, ditch, platform, etc.)
- `field_status` — Validation status (pending, confirmed, rejected, uncertain)
- `observer`, `photo_path`, `notes`, `timestamp`

**Workflow:**
1. Create anomaly points (either manually or from AI detection)
2. Run **Package for Field Survey (QField/Mergin)**
3. Copy the output directory to your mobile device
4. Open the `.qgs` file in QField
5. Navigate to each anomaly and update the field_status

#### Generate PDF Report

Creates a CIfA-compliant PDF report documenting:
- Title page with site/project metadata
- Full algorithm parameter documentation
- Input DEM metadata (CRS, resolution, extent)
- Band statistics with percentile values (P5, P25, P50, P75, P95)
- Histogram chart
- Certification section

**Requirements:** `reportlab` Python package (`pip install reportlab`)

#### Visualization Recipes

Export any set of algorithm parameters as a JSON recipe file that can be
shared via GitHub Gist, attached to publications, or imported by other
users. Recipes include versioned schema, type validation, and metadata
(name, author, description, tags, landscape type).

**Example use case:**
1. Optimize SVF parameters for barrow detection on chalk downland
2. Export as `barrow_chalk.json`
3. Share with colleagues or publish alongside your paper
4. Anyone can import your recipe and reproduce your exact visualization

---

### Point Cloud Processing (NEW)

#### CSF Ground Filter (LAS/LAZ → DEM)

Generate a DEM directly from raw LiDAR point clouds using the Cloth
Simulation Filter (CSF), with presets specifically tuned for archaeology.

**Presets:**

| Preset | Description | Use Case |
|--------|-------------|----------|
| Archaeology Fine | Maximum micro-relief preservation | Subtle earthworks on flat terrain |
| Archaeology Standard | Balanced vegetation removal | Most surveys |
| Forested | Aggressive ground detection | Dense canopy |
| Urban | Standard filtering | Built-up areas |

**Requirements:** `cloth-simulation-filter` Python package
(`pip install cloth-simulation-filter`) + `laspy` for LAS/LAZ reading
(`pip install laspy`)

---

### Multi-temporal Change Detection (NEW)

Compute a probabilistic DEM of Difference (DoD) between two temporally
separated DEMs to detect landscape change.

**How it works:**
1. Load two DEMs: older (baseline) and newer (repeat survey)
2. Co-register to identical grid (reproject if needed)
3. Compute: `DoD = DEM_new - DEM_old`
4. Propagate vertical error: `σ = sqrt(RMSE_old² + RMSE_new²)`
5. Apply Level of Detection: changes below `1.96 × σ` are masked as noise

**Outputs:**
- Signed DoD raster (metres) — positive = deposition/fill,
  negative = erosion/cut
- Significance mask (0=no change, 1=erosion, 2=deposition)
- Volume report with cut/fill totals

**Requirements:** `xarray` and `rioxarray`
(`pip install xarray rioxarray`)

---

### Multi-Sensor Fusion (NEW)

Co-register Sentinel-2 multispectral bands with LiDAR relief and apply
blend recipes.

**Recipes:**

| Recipe | LiDAR Layer | Satellite Bands | Effect |
|--------|-------------|-----------------|--------|
| Terrain + CIR | SVF (luminance) | B8, B4, B3 (CIR) | Topography + vegetation |
| Crop Mark Enhancement | Local Dominance | B4, B3, B2 (true colour) | Buried features |
| Erosion Risk | Slope | B11, B8, B4 (SWIR+NIR) | Soil moisture + slope |
| Bare Earth Composite | SLRM | B11, B12, B4 | Vegetation-free prospection |

**Requirements:** `rasterio` and `rioxarray`
(`pip install rasterio rioxarray`)

---

### AI Feature Detection (NEW)

Run object detection or semantic segmentation on plugin visualizations
using your own pre-trained ONNX model.

**Supported model types:**
- **Object detection (YOLOv5/v8/v11)**: Returns bounding boxes
- **Semantic segmentation (U-Net)**: Returns pixel-wise class labels
- **Instance segmentation (Mask R-CNN)**: Returns polygons

**Workflow:**
1. Train a model externally (PyTorch, Ultralytics, etc.)
2. Export to ONNX format
3. Create a `labels.json` file with class names
4. In QGIS, run **AI Feature Detection (ONNX Model)**
5. Detection results are written as a GeoPackage vector layer

**Requirements:** `onnxruntime` (`pip install onnxruntime`)

---

## Batch Processing

The **Batch Relief Visualisation** tool runs multiple algorithms in a single
pass. Choose from 4 research-validated terrain presets or use manual settings:

- **Flat / Agricultural**: Optimized for ploughed-out features in low-relief
  terrain. SVF radius 10–20m, SLRM radius 20m, LD observer height 1.7m.
- **Forested**: Dense canopy where ground points are sparse. SVF radius 10m,
  SLRM radius 10–15m, LD observer height 1.5m.
- **Upland / Steep**: Prevents steep slopes from overpowering micro-relief.
  SVF radius 5m, SLRM radius 5–10m.
- **Coastal**: Broad search radii for dune/estuarine modifications.
  SVF radius 10–15m, SLRM radius 25m, LD observer height 2.0m.

---

## Best Practices

1. **CRS**: Ensure your DEM is projected in a metric CRS (UTM or local grid),
   not geographic (degrees in latitude/longitude).
2. **Start with Batch**: Use the Batch tool with a matching terrain preset.
3. **Iterate**: If features are too faint, increase search radii. If too noisy,
   decrease them.
4. **SVF Noise**: Enable noise reduction for DEMs with point-cloud noise
   or complex topography.
5. **e4MSTP**: Prepare for longer processing — it computes 7 underlying
   algorithms.
6. **Export**: Use COG export for sharing with non-GIS stakeholders.
7. **Field validation**: Use the Field Survey Export for ground-truthing.
8. **Reproducibility**: Export a Visualization Recipe alongside any
   published results.
9. **AI models**: The plugin is an inference engine only — train models
   externally in PyTorch/Ultralytics and export to ONNX.

---

## Optional Dependencies

| Feature | Package | Install command |
|---------|---------|----------------|
| COG Export | `rio-cogeo` | `pip install rio-cogeo` |
| PDF Reports | `reportlab` | `pip install reportlab` |
| CSF Ground Filter | `cloth-simulation-filter` | `pip install cloth-simulation-filter` |
| Temporal Analysis | `xarray`, `rioxarray` | `pip install xarray rioxarray` |
| Multi-Sensor Fusion | `rasterio`, `rioxarray` | `pip install rasterio rioxarray` |
| AI Detection | `onnxruntime` | `pip install onnxruntime` |
| GPU Acceleration | `cupy-cuda12x` | `pip install cupy-cuda12x` |
| LAS/LAZ input | `laspy` or `pdal` | `pip install laspy` |

All features degrade gracefully with clear error messages if a dependency
is missing.
