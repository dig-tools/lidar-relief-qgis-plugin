"""blend.py — Blending modes for QGIS raster visualization.
exports: blend_rasters(array_a, array_b, mode) -> ndarray, simple_red_relief(array, cellsize, slrm_radius) -> ndarray
used_by: algorithms/blend_algorithm.py → blend_rasters
rules:
  Pure NumPy — no QGIS imports.
  Input arrays must be float32 in [0, 255] range or similar.
  Output is float32 scaled to [0, 255].
"""

import numpy as np


def blend_rasters(
    array_a: np.ndarray,
    array_b: np.ndarray,
    mode: str,
    opacity: float = 1.0,
    feedback=None,
) -> np.ndarray:
    """Blend two raster arrays using standard blend modes.

    Args:
        array_a: Base layer (e.g. Hillshade), float32.
        array_b: Blend layer (e.g. SVF or SLRM), float32.
        mode: Blending mode ('multiply', 'screen', 'overlay', 'soft_light').
        opacity: Blend opacity from 0.0 (fully base) to 1.0 (fully blended).

    Returns:
        Blended float32 array in [0, 255] range.
    """
    if array_a.shape != array_b.shape:
        raise ValueError("Arrays must have the same shape to blend.")

    # Normalize inputs to [0, 1] for blending maths
    # We assume standard 8-bit inputs scaled 0-255.
    # If inputs have negative values (like SLRM), we should ideally normalize them,
    # but QGIS processing wrappers should handle passing 0-255 scaled data or
    # we just clip them.

    a_norm = np.clip(array_a / 255.0, 0.0, 1.0)
    b_norm = np.clip(array_b / 255.0, 0.0, 1.0)

    if mode == "multiply":
        result = a_norm * b_norm
    elif mode == "screen":
        result = 1.0 - (1.0 - a_norm) * (1.0 - b_norm)
    elif mode == "overlay":
        # Overlay: Multiply if a < 0.5, Screen if a >= 0.5
        mask = a_norm < 0.5
        result = np.empty_like(a_norm)

        # 2 * A * B
        result[mask] = 2.0 * a_norm[mask] * b_norm[mask]

        # 1 - 2 * (1 - A) * (1 - B)
        result[~mask] = 1.0 - 2.0 * (1.0 - a_norm[~mask]) * (1.0 - b_norm[~mask])
    elif mode == "soft_light":
        # Pegtop soft light
        result = (1.0 - 2.0 * b_norm) * (a_norm**2.0) + 2.0 * b_norm * a_norm
    else:
        raise ValueError(f"Unknown blend mode: {mode}")

    # Apply opacity
    result = opacity * result + (1.0 - opacity) * a_norm

    # Scale back to 0-255
    blended = np.clip(result * 255.0, 0.0, 255.0).astype(np.float32)

    # Preserve NaN from either array
    nan_mask = np.isnan(array_a) | np.isnan(array_b)
    blended[nan_mask] = np.nan

    return blended


def simple_red_relief(
    array: np.ndarray, cellsize: float, slrm_radius: int, feedback=None
) -> np.ndarray:
    """Compute Simple Red Relief composite.

    Combines SLRM (lower layer) and Slope (upper layer, Multiply blend).
    """
    from .slrm import simple_local_relief_model
    from .slope import compute_slope

    if feedback:
        feedback.setProgressText("Simple Red Relief: Computing SLRM...")
    slrm = simple_local_relief_model(array, slrm_radius)

    if feedback:
        feedback.setProgressText("Simple Red Relief: Computing Slope...")
    slope = compute_slope(array, cellsize, units="degrees")

    if feedback:
        feedback.setProgressText("Simple Red Relief: Blending layers...")

    # Normalize SLRM to 0-255
    min_slrm = np.nanmin(slrm)
    max_slrm = np.nanmax(slrm)
    if max_slrm > min_slrm:
        slrm_norm = (slrm - min_slrm) / (max_slrm - min_slrm) * 255.0
    else:
        slrm_norm = np.zeros_like(slrm)

    # Normalize Slope to 0-255 (inverted for blend)
    min_slope = np.nanmin(slope)
    max_slope = np.nanmax(slope)
    if max_slope > min_slope:
        slope_norm = (slope - min_slope) / (max_slope - min_slope)
        slope_norm = (1.0 - slope_norm) * 255.0
    else:
        slope_norm = np.zeros_like(slope)

    return blend_rasters(
        slrm_norm, slope_norm, mode="multiply", opacity=0.5, feedback=feedback
    )
