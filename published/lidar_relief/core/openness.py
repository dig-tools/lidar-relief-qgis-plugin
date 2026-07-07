"""openness.py — Topographic Openness computation for terrain analysis.
exports: topographic_openness(dem, cellsize, num_directions, search_radius, is_negative) -> ndarray
used_by: algorithms/openness_algorithm.py → topographic_openness
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Output is float32 in range [0, 180] (usually [0, 90]).
  Uses the same supersampled horizon scan as SVF (see core/svf.py) so
  that horizon pixels on diagonal azimuths are correctly sampled.
"""

import numpy as np
from .array_utils import _shift_array
from .svf import _build_horizon_samples


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

    # Pre-compute the horizon sample points (same supersampling approach as SVF)
    horizon_samples = _build_horizon_samples(num_directions, search_radius)

    # Accumulate openness angles (in radians)
    openness_sum = np.zeros((rows, cols), dtype=np.float32)

    for dir_idx, row_shifts, col_shifts, dists in horizon_samples:
        if feedback is not None and feedback.isCanceled():
            return np.full_like(dem, np.nan)

        # Start at -1.0, which corresponds to -pi/2 (straight down)
        max_sin = np.full((rows, cols), -1.0, dtype=np.float32)

        for row_shift, col_shift, dist_units in zip(row_shifts, col_shifts, dists):
            actual_dist = dist_units * cellsize
            if actual_dist == 0:
                continue

            shifted = _shift_array(dem_filled, row_shift, col_shift, dem_mean)

            delta_z = shifted - dem_filled
            hypot_3d = np.hypot(delta_z, actual_dist)
            # Avoid division by zero; also clamp to avoid NaN from arcsin later
            hypot_3d = np.where(hypot_3d == 0, 1.0, hypot_3d)
            sin_angle = delta_z / hypot_3d

            max_sin = np.maximum(max_sin, sin_angle)

        # Clamp to [-1, 1] before arcsin to avoid NaN from floating-point drift
        max_sin = np.clip(max_sin, -1.0, 1.0)
        max_angle = np.arcsin(max_sin)
        # Openness for this direction is zenith angle (pi/2 - max_angle)
        openness_sum += np.pi / 2.0 - max_angle

        if feedback is not None:
            feedback.setProgress(int((dir_idx + 1) / num_directions * 100))

    # Mean openness in radians
    mean_openness_rad = openness_sum / num_directions

    # Convert to degrees
    openness_deg = np.degrees(mean_openness_rad).astype(np.float32)

    # Restore NaN
    openness_deg[nan_mask] = np.nan

    return openness_deg
