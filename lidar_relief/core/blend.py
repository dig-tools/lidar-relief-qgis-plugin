"""blend.py — Blending modes for QGIS raster visualization.
exports: blend_rasters(array_a, array_b, mode) -> ndarray
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
    feedback=None,
) -> np.ndarray:
    """Blend two raster arrays using standard blend modes.

    Args:
        array_a: Base layer (e.g. Hillshade), float32.
        array_b: Blend layer (e.g. SVF or SLRM), float32.
        mode: Blending mode ('multiply', 'screen', 'overlay').

    Returns:
        Blended float32 array in [0, 255] range.
    """
    if array_a.shape != array_b.shape:
        raise ValueError("Arrays must have the same shape to blend.")

    if feedback is not None and feedback.isCanceled():
        return np.full_like(array_a, np.nan)

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
    else:
        raise ValueError(f"Unknown blend mode: {mode}")

    # Scale back to 0-255
    blended = np.clip(result * 255.0, 0.0, 255.0).astype(np.float32)

    # Preserve NaN from either array
    nan_mask = np.isnan(array_a) | np.isnan(array_b)
    blended[nan_mask] = np.nan

    return blended
