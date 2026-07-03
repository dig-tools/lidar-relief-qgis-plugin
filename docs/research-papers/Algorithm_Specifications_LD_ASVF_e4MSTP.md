# Mathematical and Algorithmic Specifications: Local Dominance, ASVF, e4MSTP

*Source: Deep Research Report — May 2026*
*Reference implementation: Relief Visualization Toolbox (RVT), EarthObservation/RVT_py, Apache 2.0 License*

---

## 1. Local Dominance (LD)

### Mathematical Definition
For focal pixel at (i,j) with elevation Z(i,j), observer height h_o above terrain:

- Observer elevation: Z_obs(i,j) = Z(i,j) + h_o
- For each neighbour pixel (i',j') within search annulus [min_rad, max_rad]:
  - Euclidean distance: dist = sqrt((row_shift * cellsize)² + (col_shift * cellsize)²)
  - Elevation difference: delta_z = Z_obs(i,j) - Z(i',j')
  - Declination angle: alpha = arctan(delta_z / dist)
- Final LD value: mean(alpha) over all valid pixels in annulus

Positive alpha = observer looks DOWN (focal pixel is elevated). Negative alpha = focal pixel is in a depression.

### RVT Reference Parameters
| Parameter    | Default | Notes |
|---|---|---|
| min_rad      | 10.0    | Pixels. Bypasses noise in immediate neighbourhood |
| max_rad      | 20.0    | Pixels |
| rad_inc      | 1.0     | Pixels per step along ray |
| anglr_res    | 15.0    | Degrees between rays (24 directions) |
| observer_h   | 1.7     | Metres (human eye level) |
| ve_factor    | 1.0     | Vertical exaggeration |
| min_bytscl   | 0.5     | Lower clamp for 8-bit normalisation (radians) |
| max_bytscl   | 1.8     | Upper clamp for 8-bit normalisation (radians) |

### Context-Dependent Parameters
- Flat/Agricultural: min_rad=10, max_rad=20, observer_h=1.7
- Forested: min_rad=5, max_rad=15, observer_h=1.5
- Upland/Steep: min_rad=5, max_rad=10, observer_h=1.0
- Coastal: min_rad=15, max_rad=30, observer_h=2.0

### NumPy Implementation Pattern
Uses same horizon-scanning pattern as SVF — ray tracing with array shifts.
See: /lidar_relief/core/svf.py for the established pattern to follow.
Key difference: evaluate arctan(delta_z / dist) where delta_z = dem_obs - target_z
(observer is ABOVE the DEM surface, not at it).

---

## 2. Anisotropic Sky-View Factor (ASVF)

### Mathematical Definition
Standard SVF formula with directional weighting added per azimuth direction phi_k:

**Weight function:**
W(phi_k) = min_weight + (1 - min_weight) * ((1 + cos(phi_k - phi_pref)) / 2) ^ p_exp

Where:
- phi_pref = preferred azimuth (default 315°, NW)
- p_exp = anisotropy exponent (1 = low/broad, 2 = high/focused)
- min_weight = ambient floor (default 0.1) — prevents complete occlusion

**Modified integration:**
ASVF = sum(W_k * (1 - max_sin_gamma_k)) / sum(W_k)

Output remains in [0, 1] — fully normalised by weight sum.

### RVT Reference Parameters
| Parameter    | Default | Notes |
|---|---|---|
| svf_n_dir    | 16      | Azimuthal search directions |
| svf_r_max    | 10      | Max search radius in pixels |
| asvf_level   | 1       | 1=p_exp of 1 (broad), 2=p_exp of 2 (focused) |
| asvf_dir     | 315.0   | Preferred azimuth in geographic degrees |
| min_weight   | 0.1     | Ambient floor |
| svf_noise    | 0       | Noise removal (0=none) |

### Implementation Note
In the inner loop, use the trigonometric optimisation from the report:
sin(arctan(dz/dist)) = dz / sqrt(dz² + dist²)
This avoids np.arctan in the inner loop for significant CPU speedup.

---

## 3. e4MSTP Composite Stack

### Input Layers Required
| Layer | Method | Key Parameters |
|---|---|---|
| S  | Slope gradient | Standard degrees |
| O+ | Positive Openness | Typical search radius ~10px |
| O- | Negative Openness | Typical search radius ~10px |
| L  | Local Dominance | min_rad=10, max_rad=20, h_o=1.7 |
| SVF_S | SVF small radius | r~10px, stretch 0.7→1.0 |
| SVF_L | SVF large radius | r~50px, stretch 0.9→1.0 |
| M  | MSTP | Standard micro/meso/broad scales |

### Histogram Stretching for SVF Layers
- SVF_S (small): linear stretch, clip below 0.7→0, above 1.0→1.0
- SVF_L (large): linear stretch, clip below 0.9→0, above 1.0→1.0

### Blend Modes (mathematics)
- Multiply: C = base * active
- Overlay: C = 2*base*active if base < 0.5, else 1 - 2*(1-base)*(1-active)
- Opacity transfer: C_final = alpha * blend_result + (1-alpha) * base

### Complete Composite Build Order

**Step 1 — Morphological Base (red-toned slope + openness/dominance)**
```
texture = O+ * O- * L   (element-wise multiply, normalised)
R = S (red channel = slope)
G = texture * (1 - S)
B = texture * (1 - S)
base = RGB(R, G, B)  → red morphological base
```

**Step 2 — Combined SVF texture**
```
combined_svf = SVF_L * 1.0 + SVF_S * 0.5  (Normal blend at 100% and 50%)
combined_svf = combined_svf / 1.5           (normalise)
```

**Step 3 — Apply SVF shadows (Multiply, 25% opacity)**
```
multiplied = base * combined_svf
step3 = 0.25 * multiplied + 0.75 * base
```

**Step 4 — Overlay MSTP (90% opacity)**
```
overlaid = overlay_blend(step3, M)
e4mstp = 0.90 * overlaid + 0.10 * step3
```

### Output Format
- Processing: maintain float32, normalised [0, 1]
- Final export: uint8 RGB GeoTIFF (multiply by 255, cast to uint8)

### Luminosity Greyscale Option
For fieldwork/digitising where colour fatigue is a concern:
```
L = 0.299*R + 0.587*G + 0.114*B
```
Strips chrominance, retains structural edge data.

---

## Implementation Notes for Plugin

1. All three algorithms follow the established architecture: pure NumPy core in core/, thin QGIS wrapper in algorithms/
2. Local Dominance is a NEW core file: core/local_dominance.py
3. ASVF extends existing core/svf.py with anisotropic=True parameter path
4. e4MSTP is a NEW composite: core/emstp.py (orchestrates existing core functions)
5. All three should be added to the Batch algorithm checkbox list
6. The sin/arctan optimisation in ASVF (dz/sqrt(dz²+dist²)) should also be applied to SVF and Openness for consistency
