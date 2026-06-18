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
    """Normalize array to 0-1 range. Ignores NaNs."""
    min_val = np.nanmin(array)
    max_val = np.nanmax(array)
    if max_val == min_val:
        norm = np.zeros_like(array)
    else:
        norm = (array - min_val) / (max_val - min_val)
    if invert:
        norm = 1.0 - norm
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
    )
    openness_norm = _normalize(openness)


    if feedback:
        feedback.setProgressText("VAT: Computing Sky-View Factor...")
    svf = sky_view_factor(
        array, cellsize, num_directions=16, search_radius=svf_radius, noise_level=0
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
