# Full-Waveform LiDAR for Archaeology — Research Notes

*Generated: June 2026. Phase 3.3 of the LiDAR Relief Plugin v2.0 roadmap.*

---

## Summary

Full-waveform (FW) LiDAR systems record the entire continuous backscattered
echo of the laser pulse, rather than extracting discrete returns. This
provides richer structural information, particularly for:

- **Forest canopy penetration** — FW systems can distinguish between
  understory vegetation and ground returns in dense woodland
- **Echo width analysis** — The width of the returning waveform correlates
  with surface roughness, potentially distinguishing archaeological
  earthworks from natural terrain
- **Multi-target resolution** — FW can resolve closely spaced surfaces
  (e.g., low walls beneath canopy) that discrete-return systems miss

---

## Current State of Open-Source Tooling

### Libraries evaluated

| Library | FW Support | Python Bindings | Status |
|---------|-----------|-----------------|--------|
| **PDAL** | Limited — reads FW data but most filters return discrete points | Yes | Mature but limited FW-specific algorithms |
| **laspy** | Reads LAS 1.4 (which can store waveform data) | Yes | Can read waveform packets but no analysis tools |
| **OPALS** (Full-waveform) | Yes — dedicated FW processing | C++ only | Not Python-integratable |
| **LibRADAR** | Research-grade | C++ only | No Python bindings |

### Key finding

**There is currently no mature open-source Python library that specifically
exploits full-waveform LiDAR data for archaeological or topographic
analysis.** The primary barrier is data availability — most heritage-sector
LiDAR is delivered as discrete-return LAS/LAZ, with full-waveform data
requiring specific sensors (Riegl, Leica ALS) and proprietary processing.

---

## Recommended Approach for the Plugin

### Phase 1: Data format support (if FW data is available)

- Extend `point_cloud/csf_filter.py` to read waveform packet data from
  LAS 1.4 files via laspy
- Provide basic waveform visualization as an additional raster channel

### Phase 2: Echo-width analysis (research collaboration needed)

- Compute echo width (pulse width at half maximum) from waveform samples
- Overlay as a semi-transparent raster to identify areas of anomalous
  surface roughness
- Requires calibration data from known archaeological sites

### Phase 3: Machine learning on waveforms (long-term)

- Use raw waveform samples as multi-channel input to the ONNX inference
  engine (Phase 3.1)
- Requires labelled training dataset of archaeological vs. natural
  waveform signatures

---

## Data Sources

| Source | Coverage | Waveform Type | Access |
|--------|----------|--------------|--------|
| UK Environment Agency | England (national) | Discrete return only | Open |
| USGS 3DEP | USA (national) | Discrete return only | Open |
| Riegl ALS surveys | Project-specific | Full waveform | Proprietary |
| Leica ALS surveys | Project-specific | Full waveform | Proprietary |

## Recommendation

**Defer full-waveform integration to v2.2+.** The open-source ecosystem
is not mature enough for production integration. Instead, focus on:

1. Ensuring the plugin can ingest any GDAL-readable DEM (already works)
2. Improving archaeology-tuned ground filtering in the CSF/PDAL modules
   (Phase 1.5, 2.3)
3. Establishing partnerships with researchers who have access to FW data
   for validation studies

When the ecosystem matures (e.g., PDAL adds FW-specific filters), this
module can be added without architectural changes — the `point_cloud/`
package was designed for this.
