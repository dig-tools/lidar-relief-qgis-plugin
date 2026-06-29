"""vat.py — Visualisation for Archaeological Topography (VAT) composite.
exports: compute_vat
used_by: vat_algorithm.py
rules:
  No GDAL dependencies.
  Normalize arrays before blending.
"""

import numpy as np
from typing import Optional, Any

from .hillshade import multidirectional_hillshade
from .slope import compute_slope
from .openness import topographic_openness
from .svf import sky_view_factor
from .blend import blend_rasters


def _normalize(array: np.ndarray, invert: bool = False) -> np.ndarray:
    """Normalize array to 0-255 range. Preserves NaN locations.

    For constant input (max == min), returns a mid-grey (127.5) array
    rather than all-zero — all-zero would silently black out regions
    of the VAT composite. NaNs in the input are preserved as NaNs in
    the output so they can be masked downstream.
    """
    min_val = np.nanmin(array) if np.isfinite(array).any() else 0.0
    max_val = np.nanmax(array) if np.isfinite(array).any() else 0.0
    if max_val == min_val:
        # Constant input: mid-grey instead of zero so the blend
        # doesn't go black.
        norm = np.full_like(array, 0.5, dtype=np.float32)
    else:
        norm = (array - min_val) / (max_val - min_val)
    if invert:
        norm = 1.0 - norm
    # Preserve NaN locations — the previous code's `np.zeros_like`
    # branch turned NaN pixels into 0, destroying the nodata mask.
    nan_mask = np.isnan(array)
    if nan_mask.any():
        norm = np.where(nan_mask, np.nan, norm)
    return norm * 255.0


def compute_vat(
    array: np.ndarray,
    cellsize: float,
    svf_radius: int = 50,
    openness_radius: int = 50,
    feedback: Optional[Any] = None,
) -> np.ndarray:
    """Compute the VAT (Visualisation for Archaeological Topography) composite.

    Recipe:
    1. Base: Normalized multidirectional hillshade
    2. Blend 1: Inverted Slope, mode: multiply, opacity: 0.5
    3. Blend 2: Positive Openness, mode: overlay, opacity: 0.5
    4. Blend 3: SVF, mode: multiply, opacity: 0.5
    """
    if feedback:
        feedback.setProgressText("VAT: Computing Multidirectional Hillshade...")
    # NOTE: multidirectional_hillshade does not currently accept a
    # feedback parameter; the other sub-computations do. Progress for
    # the hillshade step is reported only via setProgressText above.
    hillshade = multidirectional_hillshade(
        array, cellsize, azimuths=[315, 45, 135, 225], altitude=45.0
    )
    base = _normalize(hillshade)

    if feedback:
        feedback.setProgressText("VAT: Computing Slope...")
    slope = compute_slope(array, cellsize, units="degrees")
    slope_norm = _normalize(slope, invert=True)

    if feedback:
        feedback.setProgressText("VAT: Computing Positive Openness...")
    openness = topographic_openness(
        array,
        cellsize,
        num_directions=16,
        search_radius=openness_radius,
        is_negative=False,
        feedback=feedback,
    )
    openness_norm = _normalize(openness)

    if feedback:
        feedback.setProgressText("VAT: Computing Sky-View Factor...")
    svf = sky_view_factor(
        array,
        cellsize,
        num_directions=16,
        search_radius=svf_radius,
        noise_level=0,
        feedback=feedback,
    )
    svf_norm = _normalize(svf)

    if feedback:
        feedback.setProgressText("VAT: Blending layers...")

    # 1. Base + Slope (Multiply, 0.5)
    blend1 = blend_rasters(
        base, slope_norm, mode="multiply", opacity=0.5, feedback=feedback
    )

    # 2. Blend1 + Openness (Overlay, 0.5)
    blend2 = blend_rasters(
        blend1, openness_norm, mode="overlay", opacity=0.5, feedback=feedback
    )

    # 3. Blend2 + SVF (Multiply, 0.5)
    vat_final = blend_rasters(
        blend2, svf_norm, mode="multiply", opacity=0.5, feedback=feedback
    )

    return vat_final
