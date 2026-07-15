# LiDAR Relief Visualization Plugin — Development Roadmap

*Last updated: 15 July 2026. Informed by the reports retained in
`docs/research-papers/`; see `Synthesis_Research_Findings_v2.0.md` for the
cross-paper synthesis.*

---

## Current state: v2.0.21

The original v1–v2 roadmap has been delivered. The plugin now provides 29 QGIS
Processing algorithms spanning terrain visualization, TRI and slope analysis,
batch workflows, point-cloud preparation, temporal comparison, sensor fusion,
field and web publishing, reporting, recipes, optional ONNX inference, and GPU
acceleration. It is validated on QGIS 3.34 and QGIS 4.2 through unit, packaging,
minimal-runtime, and desktop-loader tests.

| Roadmap area | Status in 2.0.21 |
|---|---|
| v1.1 composites, SVF noise handling, presets, styling | Complete |
| v1.2 Local Dominance and ASVF | Complete |
| v1.3 e4MSTP, PCA, ML-ready export | Complete |
| v2 foundation: COG/web, field packages, PDF, recipes, CSF | Complete |
| v2 expansion: temporal analysis, sensor fusion, PDAL | Complete |
| Optional ONNX inference and CuPy acceleration | Complete, dependency-gated |
| Full-waveform LiDAR processing | Research only; not implemented |

The detailed sections below preserve the rationale and mathematical design of
the completed roadmap. Statements such as “planned” describe the historical
decision point, not the current release.

## Historical baseline: v1.0 (complete)

The following algorithms are fully implemented, tested, and published to the QGIS Plugin Repository:

| Algorithm | Core File | Notes |
|---|---|---|
| Multi-directional Hillshade | `core/hillshade.py` | Multi-azimuth blend, configurable azimuths and altitude |
| Simple Local Relief Model (SLRM) | `core/slrm.py` | scipy fallback to NumPy box filter |
| Sky-View Factor (SVF) | `core/svf.py` | Vectorised, configurable directions and search radius |
| Topographic Openness (Pos/Neg) | `core/openness.py` | Single algorithm, `is_negative` flag |
| Multi-Scale Topographic Position (MSTP) | `core/mstp.py` | Integral image O(1) computation, RGB output |
| Slope | `core/slope.py` | Degrees and percent |
| Blend Visualizations | `core/blend.py` | Multiply, Screen, Overlay modes |
| Batch Relief Visualization | `algorithms/batch_algorithm.py` | Runs multiple algorithms on one DEM in a single pass |

**Architecture:** Pure NumPy/GDAL core with thin QGIS algorithm wrappers. Tiled GDAL processing for large DEMs. Full progress/cancellation support throughout.

---

## Research Findings: Algorithm Priority Assessment

The 2025 deep research report assessed the state of the art across the published literature and benchmarked implementations. Key findings relevant to this roadmap:

- **VAT** is now the de facto standard base map in European heritage management — described as "unquestionably the most robust, universally applicable algorithm developed and standardized in the last decade." All ingredients are already in the plugin.
- **Simple Red Relief** is the correct patent-free implementation of RRIM. **The original RRIM (Chiba et al. 2008) is patented — do not implement RRIM directly.** Simple Red Relief (SLRM + Slope + Multiply blend) is functionally equivalent and unencumbered.
- **Local Dominance** is "unmatched for isolating near-invisible, leveled anomalies in European agricultural contexts" — primary target audience use case.
- **SVF noise reduction** is the key gap vs. RVT (the reference implementation). RVT implements a configurable `svf_noise` parameter that prevents blown-out valley bottoms — current plugin lacks this. SAGA GIS also lacks this, producing "blown-out" saturated outputs where valley bottoms are rendered as homogeneous black, destroying archaeological detail.
- **e4MSTP** is the final, patent-free evolution of the MSTP family — fuses multi-radius SVF + Openness + Slope + Local Dominance + MSTP. High utility for flat terrain (northern Germany, alluvial plains, agricultural landscapes).
- **Algorithms confirmed as academic curiosities** (do not implement): Enhanced Prismatic Openness (superseded by VAT; "vivid saturation and highly unnatural color matrices"), e2MSTP (uses patented RRIM — patent risk), e3MSTP (superseded by e4MSTP).

### Competitive Landscape

| Feature | This Plugin | RVT | SAGA | Whitebox | GRASS |
|---|---|---|---|---|---|
| SVF noise removal | ✓ shipped | ✓ (4 levels) | ✗ | ✗ | ✗ |
| ASVF | ✓ shipped | ✓ (native) | Limited | ✗ | ✗ |
| VAT composite | ✓ shipped | ✓ | Manual | Manual | Manual |
| e4MSTP | ✓ shipped | ✓ | ✗ | ✗ | ✗ |
| Geomorphons | Deferred | ✗ | ✗ | ✗ | ✓ |
| Integrated blending | ✓ | ✓ | ✗ | ✗ | ✗ |
| Native QGIS integration | ✓ | ✗ | Plugin | Plugin | Plugin |

### Archaeological Feature → Algorithm Mapping

Research identifies optimal algorithm selection by feature type:

| Feature Type | Best Algorithms | Key Parameters |
|---|---|---|
| Medieval ridge-and-furrow | Pos/Neg Openness, Multi-Hillshade | R: ~5–10m, divergent colour ramp |
| Prehistoric barrows/mounds | SLRM, Local Dominance | SLRM R: match barrow diameter (5–20m); LD: h_o=1.7m |
| Roman road agger | MSTP + Positive Openness, PCA | MSTP multi-scale for macro context |
| Enclosure ditches/moats | SVF, Negative Openness | SVF R: 10–20m, 16–32 dirs, inverted greyscale |
| Charcoal kilns | SVF, e4MSTP | SVF R: 5–10m (tight footprint) |
| Maya plazuelas (tropical) | SLRM, VAT, Simple Red Relief | SLRM to remove karst geology |
| Agrarian terraces | e4MSTP, geomorphon classification | Flat terrain: large radii |
| Stone walls | Positive Openness | R: 5m (convex ridge detection) |
| Hollow ways | Local Dominance, Neg Openness | LD detects subtle concavities |

### Regional Workflow Paradigms

**European Workflow (microtopography):**
1. SLRM (R: 15–20m) → macro detrending
2. Local Dominance → volumetric peak extraction
3. PCA of 16-dir hillshades → anisotropic delineation
4. VAT → standardised base map

**Mesoamerican / Asia-Pacific Workflow (monumentality):**
1. Simple Red Relief + MSTP → macro urban mapping
2. TPI + SLRM → volumetric architecture separation
3. Negative Openness (inverted greyscale) → hydrological/defensive tracing

---

## Delivered version roadmap

### v1.1 — Composites, Noise, and Usability (complete)
*Priority: High. All v1.1 additions use existing algorithm components.*

#### New: VAT (Visualization for Archaeological Topography)
- Composite of Hillshade + Slope + Positive Openness + SVF in a specific weighted blend.
- The European heritage management standard. Replaces single-source hillshade in formal publications.
- Geographically resilient: works correctly from flat alluvial plains to steep upland karst.
- Implementation: new `core/vat.py` combining existing core functions with documented RVT blend weights.

#### New: Simple Red Relief (Patent-Free RRIM)
- Lower layer: SLRM with trend radius 12–20m, colour ramp: cyan (depressions) → grey (flat) → pale yellow (convexities).
- Upper layer: Slope raster (0–50°, white to vivid red), blended using Multiply mode over SLRM.
- Functionally indistinguishable from the patented RRIM. Primary visualisation for tropical/Mesoamerican surveys and macro-scale landscape triage.
- Implementation: extend `core/blend.py` with a dedicated `simple_red_relief()` function. This is a composite rendering technique using the existing SLRM and Slope core algorithms, not a standalone core algorithm.

#### Improvement: SVF Noise Reduction Parameter
- Add `noise_level` parameter to `core/svf.py`: `0=none, 1=low, 2=medium, 3=high`.
- Applies a noise-removal matrix within the SVF array calculation prior to final rendering.
- Closes the primary gap between this plugin and RVT in the SVF implementation.
- Prevents blown-out valley bottoms in DEMs with inherent point-cloud noise or complex topography.
- This is the single most important differentiator vs SAGA GIS, which lacks noise removal entirely.

#### Improvement: Trigonometric Optimisation Backport
- Apply the identity `sin(arctan(dz/dist)) = dz / sqrt(dz² + dist²)` to SVF and Openness inner loops.
- Eliminates `np.arctan` calls in the hot path — "vastly improves CPU throughput" per research benchmarks.
- This optimisation should also be carried forward to LD and ASVF implementations in v1.2.

#### New: Parameter Presets by Archaeological Context
- Dropdown in Batch algorithm UI: `Flat / Agricultural`, `Forested / Dense Canopy`, `Upland / Steep`, `Coastal / Estuarine`.
- Applies research-validated default parameters to all algorithms simultaneously.

*Research-validated parameter values per context:*

| Algorithm | Flat / Agricultural | Forested | Upland / Steep | Coastal |
|---|---|---|---|---|
| SVF | Radius: 10–20m, Dirs: 16–32, Noise: Low | Radius: 10m, Dirs: 16, Noise: High | Radius: 5m, Dirs: 16, Noise: Medium | Radius: 10–15m, Dirs: 32, Noise: Low |
| Openness | Radius: 10–15m, Dirs: 16 | Radius: 5m, Dirs: 16 | Radius: 3–5m, Dirs: 16 | Radius: 10m, Dirs: 32 |
| SLRM | Trend radius: 20m | Trend radius: 10–15m | Trend radius: 5–10m | Trend radius: 25m |
| MSTP | Micro: 5–25px, Meso: 25–250px, Broad: 250–2500px | Micro: 3–21px, Meso: 23–203px, Broad: 223–2023px | Micro: 3–15px, Meso: 15–100px, Broad: 100–1000px | Micro: 5–30px, Meso: 30–300px, Broad: 300–3000px |
| Local Dominance | Min/Max Rad: 10–20px, Observer: 1.7m | Min/Max Rad: 5–15px, Observer: 1.5m | Min/Max Rad: 5–10px, Observer: 1.0m | Min/Max Rad: 15–30px, Observer: 2.0m |

#### Improvement: Auto-Styling on Output
- Automatically apply a recommended QGIS colour ramp to output layers on load.
- SVF: diverging blue-white ramp. SLRM: cyan-grey-yellow diverging. Slope: white-red. Openness: grey linear.
- Output loads looking correct immediately rather than as a grey blob.
- **Use Standard Deviation stretching** (clip at 2–3σ) rather than simple linear min-max — extreme outliers (quarries, road embankments) collapse the optical range and destroy subtle archaeological detail.

#### Improvement: Automatic Output Naming
- Auto-generate output filenames from algorithm name + key parameters.
- Example: `dem_svf_r10_d16.tif`, `dem_slrm_r20.tif`, `dem_mstp_l5_m50_b500.tif`.

---

### v1.2 — New Algorithms (complete)
*Priority: Medium-High.*

#### New: Local Dominance (LD)
- Computes the average steepness of the angle at which an observer at a defined height above a pixel looks down upon surrounding terrain.
- High values = locally elevated pixels (mound peaks, ridge crests). Low values = depressions (ditches, pits).
- Distinguished from SLRM in that it uses angular relationships rather than absolute elevation residuals — retains more impression of macro landscape form.
- Primary use: detecting near-invisible leveled barrows, eroded field boundaries, and hollow ways in European agricultural contexts.
- Parameters: `min_radius` (pixels), `max_radius` (pixels), `observer_height` (m, default 1.7m).
- Implementation: new `core/local_dominance.py`.

*Mathematical specification (from research):*
- Observer elevation: `Z_obs(i,j) = Z(i,j) + h_o`
- For each neighbour pixel in annulus [min_rad, max_rad]: `alpha = arctan((Z_obs - Z_target) / dist)`
- Final: `LD(i,j) = mean(alpha)` over all valid pixels in annulus.
- Positive alpha = observer looks down (elevated pixel); Negative alpha = depression.
- Uses identical horizon-scanning pattern as SVF (ray tracing with array shifts).
- Apply trig optimisation: `sin(arctan(dz/d)) = dz / sqrt(dz² + d²)`.
- Edge handling: `np.pad(dem, pad_width=max_radius, mode='edge')`.
- Byte-scale normalisation: `ld_norm = (ld - 0.5) / (1.8 - 0.5)` then clip to [0, 255]. Min=0.5 maximises contrast for concave features; upper bound 1.8 exceeds theoretical max (~π/2 ≈ 1.57) to prevent dynamic range flattening.

#### New: Anisotropic Sky-View Factor (ASVF)
- Extends existing SVF with directional weighting via a cosine function.
- Simulates an anisotropic sky dome where illumination is brighter from a specific azimuth.
- Occupies the middle ground between diffuse SVF and harsh hillshade — retains shadow penetration while adding directional contrast.
- Parameters: `azimuth` (degrees, default 315°), `anisotropy_level` (exponent, default 1), `min_weight` (float, default 0.1).
- Implementation: extend `core/svf.py` with an `anisotropic=True` parameter and azimuth/exponent inputs.

*Mathematical specification (from research):*
- Weight function: `W(φ_k) = w_min + (1 - w_min) × ((1 + cos(φ_k - φ_pref)) / 2) ^ p_exp`
- Modified SVF: `ASVF = Σ(W_k × (1 - max_sin_γ_k)) / Σ(W_k)`
- Geographic azimuth to math radians: `φ_pref = radians(90.0 - asvf_dir)`.
- Output remains [0, 1], fully normalised by weight sum.
- Apply trig optimisation: `sin(arctan(dz/dist)) = dz / sqrt(dz² + dist²)`.

---

### v1.3 — Advanced Composites and ML Integration (complete)
*Priority: Medium.*

#### New: e4MSTP
- The final patent-free evolution of the enhanced MSTP family (Kokalj, 2025).
- Fuses: red-toned Slope + Positive Openness + Negative Openness + Local Dominance + dual-radius SVF with distinct histogram stretches + standard MSTP.
- Described as "unparalleled for complex, multi-period landscapes on flat terrain" — directly relevant to northern European agricultural archaeology.
- Abandons all patented RRIM components. Patent-free.
- Implementation: new `core/emstp.py` orchestrating existing core algorithms.

*Composite build order (from research, 4-step process):*

**Step 1 — Morphological Base (RGB):**
```
texture = O+ × O- × L  (element-wise multiply, normalised)
R = S (slope)
G = texture × (1 - S)
B = texture × (1 - S)
base = RGB(R, G, B)  → red morphological base
```

**Step 2 — Combined SVF Texture:**
```
SVF_S (small radius, ~10px): linear stretch 0.7 → 1.0
SVF_L (large radius, ~50px): linear stretch 0.9 → 1.0
combined_svf = (SVF_L × 1.0 + SVF_S × 0.5) / 1.5
```

**Step 3 — SVF Shadows (Multiply blend, 25% opacity):**
```
multiplied = base × combined_svf
step3 = 0.25 × multiplied + 0.75 × base
```

**Step 4 — Overlay MSTP (90% opacity):**
```
overlaid = overlay_blend(step3, M)
e4mstp = 0.90 × overlaid + 0.10 × step3
```

*Blend mode mathematics:*
- Multiply: `C = base × active`
- Overlay: `C = 2×base×active if base < 0.5, else 1 - 2×(1-base)×(1-active)`
- Opacity: `C_final = α × blend_result + (1-α) × base`

*Output:* float32 during processing → uint8 RGB GeoTIFF for export.

*Optional luminosity greyscale mode (for fieldwork/digitising where colour fatigue is a concern):*
```
L = 0.299×R + 0.587×G + 0.114×B
```

#### New: PCA Compositing
- Computes 16–32 directional hillshades across the compass rose.
- Runs Principal Component Analysis across the raster stack.
- Assigns PC1/PC2/PC3 to Red/Green/Blue output channels.
- Captures directional features (ridge-and-furrow, Roman roads, plough marks) that omnidirectional methods miss.
- Heavily used in European prospection, particularly Italy and UK.

#### New: ML-Ready RGB Export
- Generates the canonical machine-learning input composite defined in the literature.
- Red → Slope, Green → Positive Openness, Blue → SVF.
- Alternative channel mapping: MSTP scales (Red → Broad, Green → Meso, Blue → Micro) for multi-scale analysis.
- Properly scaled, normalised uint8 output formatted for direct input to CNN detection pipelines.
- Distinguishing feature: no other QGIS plugin currently offers a dedicated ML-preparation export mode.
- **Critical**: never feed raw DEMs to CNNs — macro-topographic slopes overwhelm the network. Always use pre-processed composites.

*Benchmarked ML architectures for downstream consumption:*

| Architecture | Best For | Detection Type |
|---|---|---|
| U-Net / ResUnet | Celtic fields, terraces, stone walls | Semantic segmentation (high precision) |
| Mask R-CNN | Barrows, charcoal kilns, Maya platforms | Instance segmentation (bounding boxes + masks) |
| YOLO | Discrete isolated objects | Fast object detection |
| DeepLab V3+ | Continuous features: reservoirs, field systems | Pixel-wise classification |

*ML training guidance:*
- Synthetic training data: procedurally generate 3D models of archaeological features and insert into real LiDAR backgrounds.
- Transfer learning: pre-trained on ResNet-50 or SatCLIP, fine-tuned on LiDAR composites.
- IoU > 0.5 = standard threshold for true positive. Models should be tuned for recall over precision (false positives acceptable; missed sites are not).
- Major bottleneck: scarcity of ground-truthed training datasets.

---

## v2.0 delivered roadmap — From Visualization to Discovery

*Informed by two independent deep research papers commissioned from the
`08_beyond_roadmap_features.txt` research prompt. Full synthesis:
`docs/research-papers/Synthesis_Research_Findings_v2.0.md`.*

The plugin must evolve from a passive visualization engine into an
active prospection platform. The v2.0 strategy closes the loop:
**Desktop analysis → Field validation → Published report → Shareable
web map**.

### Phase 1 — Low-Risk Foundation (complete)

Pure-Python dependencies only. Zero binary dependency risk on OSGeo4W.

| Feature | What | Library |
|---------|------|---------|
| **COG Web Export** | Convert any algorithm output to Cloud-Optimized GeoTIFF + auto-generate MapLibre GL JS interactive viewer for static hosting (GitHub Pages, S3) | `rio-cogeo` + `rasterio` |
| **Field Survey Export** | Export detected anomaly points as GeoPackage with structured schema (anomaly_id, method, confidence, status) for QField / Mergin Maps | QGIS Python API (built-in) |
| **Automated PDF Report** | CIfA-compliant report: processing parameters, CRS metadata, histogram statistics, locator map | `reportlab` (pure Python) |
| **Visualization Recipes** | Import/export all algorithm parameters as shareable JSON files — community-driven preset sharing beyond the 4 built-in landscape presets | Python `json` (stdlib) |
| **Point Cloud CSF Filter** | Cloth Simulation Filter for archaeology-optimized ground extraction directly from LAS/LAZ files. Older deterministic filters (TIN, MCC) preserve micro-relief better than modern AI filters | `cloth-simulation-filter` |

### Phase 2 — Medium-Risk Expansion (complete)

New library dependencies but backed by mature, well-supported projects.

| Feature | What | Library |
|---------|------|---------|
| **Multi-temporal Change Detection** | Load two DEMs, compute probabilistic DEM of Difference (DoD) with Level of Detection (LoD) masking using propagated RMSE. Exploit UK EA repeat surveys and other national programs | `xarray` + `rioxarray` |
| **Multi-Sensor Fusion** | Co-register Sentinel-2 multispectral imagery with LiDAR relief. Blend recipes combining topographic (SVF, LD) and spectral (NDVI, Color Infrared) layers | `rasterio` + `rioxarray` |
| **Archaeology-Tuned Ground Classification** | PDAL-based pipeline for LAS/LAZ ground filtering with parameters explicitly tuned to retain subtle earthworks that standard filters classify as noise | `pdal` Python bindings |

### Phase 3 — Optional and research capabilities

Strategically important but carry engineering or hardware risks.

| Feature | What | Risk |
|---------|------|------|
| **AI/ML ONNX Inference** | Optional module: user-provided `.onnx` model → vector detection layer. YOLO for discrete anomalies (barrows, kilns), U-Net for continuous features (terraces, walls). Plugin acts as inference engine only — no training | Model distribution rights, false-positive rates, binary size |
| **GPU CuPy Acceleration** | Dynamic hardware dispatch: CuPy if NVIDIA GPU present, else NumPy CPU fallback. 100–270× potential speedup on SVF/Openness ray-casting | CUDA versioning, PCIe transfer overhead, AMD/Apple Silicon exclusion |
| **Full-Waveform LiDAR** | Exploit echo width and continuous amplitude from full-waveform sensors for superior canopy penetration in forested archaeology | Research-stage, limited open-source tooling |

### Historical resource-constrained priorities

1. **COG Web Export** — share visualizations with stakeholders who
   lack GIS. Highest single-impact feature for public engagement.
2. **GeoPackage Field Export** — close the loop between desktop
   detection and ground-truthing. Team prospection platform.
3. **Automated PDF Reporting** — CIfA-compliant reports. Required for
   commercial archaeology contracts and heritage agency submissions.

All three are low-risk, use stable libraries, and deliver immediate
professional value.

---

---

## Patent & Licensing Summary

| Component | Status | Notes |
|---|---|---|
| RRIM (Chiba et al. 2008) | **PATENTED — do not implement** | Simple Red Relief is the patent-free analogue |
| e2MSTP | **Patent risk** — uses RRIM internally | Do not implement |
| e3MSTP | Superseded | Uses CRIM to avoid patent but superseded by e4MSTP |
| e4MSTP | **Patent-free ✓** | Safe for open-source |
| Simple Red Relief | **Patent-free ✓** | Functionally equivalent to RRIM |
| RVT Python library | **Apache 2.0** | Permits derivative works; include copyright notice |
| QGIS Plugin Repository | **GPL v2 required** | Apache 2.0 and MIT are compatible |

---

## Implementation Notes

- All new algorithms must follow the established architecture: pure NumPy core in `core/`, thin QGIS wrapper in `algorithms/`.
- For Phase 1 features (COG export, reporting, recipes): add as optional pipeline components in a new `export/` or `publish/` module. These are not core algorithms and should not be mixed with `core/`.
- For Phase 2 features (temporal, fusion, PDAL): add as optional dependencies with graceful fallback if libraries are not installed. Use conditional imports and clear error messages ("Install `xarray` via OSGeo4W Shell: `pip install xarray`").
- The RVT Python library (Apache 2.0, github.com/EarthObservation/RVT_py) is the reference implementation for all new algorithms — consult it for mathematical verification but implement independently to maintain the plugin's zero-dependency architecture.
- Do not introduce heavy ML frameworks (PyTorch, TensorFlow) as hard dependencies. ONNX Runtime with OpenVINO is acceptable as an optional install for Phase 3.
- E2E tests must remain green after each addition.

### Performance Optimisation

- **Trigonometric identity**: use `sin(arctan(dz/d)) = dz / sqrt(dz² + d²)` in all horizon-scanning inner loops (SVF, ASVF, Openness, LD). Avoids expensive `np.arctan` calls.
- **Memory budget**: peak memory overhead must not exceed 4× original DEM size. Use iterative in-place accumulation (`+=`) with broadcasting rather than massive 3D stacks.
- **Array slicing**: use `padded_dem[dy:dy+rows, dx:dx+cols]` instead of `numpy.lib.stride_tricks.as_strided` — standard slicing is more cache-friendly for radial/annulus processing.
- **Tiled processing**: read large DEMs in chunks (e.g., 1024×1024 pixels) with overlapping buffer equal to `r_max` to avoid seam-line artifacts. Execute algorithm on padded block, write only interior result.
- **Integral images (MSTP)**: summed-area table allows O(1) window mean/std computation regardless of window size — only 4 array lookups per window. Essential for macro-scale radii up to 3000px.

### Colour Ramp Best Practices

- **Never use simple linear min-max stretches** — extreme outliers (quarries, road embankments) collapse the optical range.
- Use **Standard Deviation stretching** (clip at 2–3σ) to focus on subtle archaeological deviations.
- Barrow detection: symmetric colour stretch with saturated-to-desaturated heat ramp.
- Ditch detection: high-contrast inverted greyscale (low SVF → black).
- Ridge-and-furrow: divergent ramp (crests = red, troughs = blue).
