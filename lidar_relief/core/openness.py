"""openness.py — Topographic Openness computation for terrain analysis.
exports: topographic_openness(dem, cellsize, num_directions, search_radius, is_negative) -> ndarray
used_by: algorithms/openness_algorithm.py → topographic_openness
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Output is float32 in range [0, 180] (usually [0, 90]).
  All operations MUST be vectorised.
  No per-pixel Python loops.
"""

import numpy as np
from .array_utils import _shift_array


def topographic_openness(
    dem: np.ndarray,
    cellsize: float,
    num_directions: int = 16,
    search_radius: int = 10,
    is_negative: bool = False,
    feedback=None,
) -> np.ndarray:
    """Compute Topographic Openness (Positive or Negative) for each pixel.

    Positive Openness highlights convex features (mounds, ridges) by computing
    the mean zenith angle of the horizon.
    Negative Openness highlights concave features (ditches, pits) by computing
    the mean nadir angle. It is equivalent to computing positive openness on
    an inverted DEM.

    Args:
        dem: 2D float32 elevation array (nodata as np.nan).
        cellsize: Pixel size in map units.
        num_directions: Number of azimuth directions (8, 16, or 32).
        search_radius: Maximum search distance in pixels.
        is_negative: If True, compute Negative Openness instead.
        feedback: Optional QGIS feedback object for progress/cancellation.

    Returns:
        Float32 array of Openness values in degrees.
    """
    rows, cols = dem.shape

    # For negative openness, invert the DEM
    if is_negative:
        working_dem = -dem
    else:
        working_dem = dem

    # Fill NaN with the array mean for shifted lookups
    nan_mask = np.isnan(working_dem)
    dem_mean = np.nanmean(working_dem)
    dem_filled = working_dem.copy()
    dem_filled[nan_mask] = dem_mean

    # Generate evenly-spaced azimuth angles
    azimuths_rad = np.linspace(0, 2 * np.pi, num_directions, endpoint=False)

    # Pre-compute direction vectors
    dir_rows = -np.cos(azimuths_rad)
    dir_cols = np.sin(azimuths_rad)

    # Accumulate openness angles (in radians)
    openness_sum = np.zeros((rows, cols), dtype=np.float32)

    total_steps = num_directions
    for dir_idx in range(num_directions):
        if feedback is not None and feedback.isCanceled():
            return np.full_like(dem, np.nan)

        dr = dir_rows[dir_idx]
        dc = dir_cols[dir_idx]

        # Start at -1.0, which corresponds to -pi/2 (straight down)
        max_sin = np.full((rows, cols), -1.0, dtype=np.float32)

        for dist in range(1, search_radius + 1):
            row_offset = dr * dist
            col_offset = dc * dist

            row_shift = int(round(row_offset))
            col_shift = int(round(col_offset))

            if row_shift == 0 and col_shift == 0:
                continue

            shifted = _shift_array(dem_filled, row_shift, col_shift, dem_mean)
            actual_dist = np.sqrt(
                (row_shift * cellsize) ** 2 + (col_shift * cellsize) ** 2
            )

            delta_z = shifted - dem_filled
            hypot_3d = np.hypot(delta_z, actual_dist)
            sin_angle = delta_z / hypot_3d

            max_sin = np.maximum(max_sin, sin_angle)

        max_angle = np.arcsin(max_sin)
        # Openness for this direction is zenith angle (pi/2 - max_angle)
        # Zenith angle = 0 if straight up, pi/2 if horizontal, >pi/2 if below horizontal
        openness_sum += np.pi / 2.0 - max_angle

        if feedback is not None:
            feedback.setProgress(int((dir_idx + 1) / total_steps * 100))

    # Mean openness in radians
    mean_openness_rad = openness_sum / num_directions

    # Convert to degrees
    openness_deg = np.degrees(mean_openness_rad).astype(np.float32)

    # Restore NaN
    openness_deg[nan_mask] = np.nan

    return openness_deg
