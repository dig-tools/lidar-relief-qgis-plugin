"""mstp.py — Multi-Scale Topographic Position (MSTP) computation.
exports: multi_scale_topographic_position(dem, local_radius, meso_radius, broad_radius) -> ndarray
used_by: algorithms/mstp_algorithm.py → multi_scale_topographic_position
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Uses Integral Image (Summed Area Table) for O(1) local mean/stddev computation.
  Output is a 3D uint8 array (rows, cols, 3) representing RGB channels.
"""

import numpy as np


def _compute_integral_images(dem: np.ndarray):
    """Compute integral images for sum and sum-of-squares.

    NaN values are replaced with the global mean.
    """
    nan_mask = np.isnan(dem)
    dem_mean = np.nanmean(dem)

    filled_dem = dem.copy()
    filled_dem[nan_mask] = dem_mean

    # Use float64 for integral images to prevent catastrophic precision loss
    # when summing large arrays.
    filled_dem_64 = filled_dem.astype(np.float64)
    dem_sq_64 = filled_dem_64**2

    i_sum = np.cumsum(np.cumsum(filled_dem_64, axis=0), axis=1)
    i_sq = np.cumsum(np.cumsum(dem_sq_64, axis=0), axis=1)

    return i_sum, i_sq, filled_dem, nan_mask


def _window_stats(
    i_sum: np.ndarray, i_sq: np.ndarray, radius: int
) -> tuple[np.ndarray, np.ndarray]:
    """Compute local mean and standard deviation using integral images.

    Returns:
        mean_array, std_array (float32)
    """
    rows, cols = i_sum.shape

    # Pad integral images with zeros at top and left to handle boundary conditions
    pad_sum = np.pad(i_sum, ((1, 0), (1, 0)), mode="constant", constant_values=0)
    pad_sq = np.pad(i_sq, ((1, 0), (1, 0)), mode="constant", constant_values=0)

    # Use 1D arrays and broadcast to avoid creating large 2D grids in memory
    x = np.arange(cols)
    y = np.arange(rows)[:, np.newaxis]

    x1 = np.maximum(x - radius, 0)
    y1 = np.maximum(y - radius, 0)
    x2 = np.minimum(x + radius, cols - 1) + 1  # +1 because padded array is shifted by 1
    y2 = np.minimum(y + radius, rows - 1) + 1

    # Area of each window (handles edge clipping automatically)
    area = (x2 - x1) * (y2 - y1)

    # Summed Area Table lookup:
    # Sum = I(x2, y2) - I(x2, y1) - I(x1, y2) + I(x1, y1)
    sum_win = pad_sum[y2, x2] - pad_sum[y2, x1] - pad_sum[y1, x2] + pad_sum[y1, x1]

    sq_win = pad_sq[y2, x2] - pad_sq[y2, x1] - pad_sq[y1, x2] + pad_sq[y1, x1]

    mean = sum_win / area

    # Variance = E[X^2] - (E[X])^2
    variance = (sq_win / area) - (mean**2)
    # Clamp negative variances caused by floating point inaccuracies
    variance = np.maximum(variance, 0.0)

    std = np.sqrt(variance)

    return mean.astype(np.float32), std.astype(np.float32)


def multi_scale_topographic_position(
    dem: np.ndarray,
    local_radius: int = 5,
    meso_radius: int = 50,
    broad_radius: int = 500,
    lightness: float = 1.0,
    feedback=None,
) -> np.ndarray:
    """Compute Multi-Scale Topographic Position (MSTP).

    Calculates Deviation from Mean Elevation (DEV) at three scales:
    DEV = (Z - Z_mean) / Z_std

    Scales are mapped to RGB channels:
    - Broad scale  -> Red
    - Meso scale   -> Green
    - Local scale  -> Blue

    Args:
        dem: 2D float32 elevation array.
        local_radius: Radius in pixels for local scale (Blue).
        meso_radius: Radius in pixels for meso scale (Green).
        broad_radius: Radius in pixels for broad scale (Red).
        lightness: Multiplier for final brightness.

    Returns:
        3D uint8 array of shape (rows, cols, 3) representing RGB channels.
    """
    if feedback is not None:
        feedback.setProgressText("Computing integral images...")
    i_sum, i_sq, filled_dem, nan_mask = _compute_integral_images(dem)

    def compute_dev(radius: int):
        mean_z, std_z = _window_stats(i_sum, i_sq, radius)
        # If std_z is below 0.001, treat it as flat area (DEV = 0) to avoid micro-noise amplification
        is_flat = std_z < 0.001
        std_z_safe = np.where(is_flat, 1.0, std_z)
        dev = (filled_dem - mean_z) / std_z_safe
        dev[is_flat] = 0.0
        return dev

    if feedback is not None and feedback.isCanceled():
        return np.zeros((dem.shape[0], dem.shape[1], 3), dtype=np.uint8)

    if feedback is not None:
        feedback.setProgressText(f"Computing Broad scale (Red, r={broad_radius})...")
    broad_dev = compute_dev(broad_radius)

    if feedback is not None:
        feedback.setProgressText(f"Computing Meso scale (Green, r={meso_radius})...")
    meso_dev = compute_dev(meso_radius)

    if feedback is not None:
        feedback.setProgressText(f"Computing Local scale (Blue, r={local_radius})...")
    local_dev = compute_dev(local_radius)

    # Scale DEV into 0-255 RGB range.
    # Typical DEV ranges from -2.0 to +2.0 (like z-scores).
    # We map 0 to 127 (mid-gray for flat).

    def scale_to_uint8(dev: np.ndarray) -> np.ndarray:
        # Scale: DEV of ±2.0 mapped to roughly ±100, then shifted by 127
        # lightness amplifies the contrast
        scaled = 127 + (dev * 50.0 * lightness)
        clipped = np.clip(scaled, 0, 255).astype(np.uint8)
        # Apply nan mask (set to 0)
        clipped[nan_mask] = 0
        return clipped

    r = scale_to_uint8(broad_dev)
    g = scale_to_uint8(meso_dev)
    b = scale_to_uint8(local_dev)

    rgb = np.dstack((r, g, b))
    return rgb


def compute_mstp(
    dem: np.ndarray,
    local_r: int = 5,
    meso_r: int = 50,
    broad_r: int = 500,
    feedback=None,
) -> np.ndarray:
    """Compute MSTP RGB composite (wrapper for multi_scale_topographic_position).

    Used by batch_algorithm.py for the e4MSTP pipeline, which needs the
    raw MSTP composite before running the edge-enhancement step.

    Returns:
        3D uint8 RGB array of shape (rows, cols, 3).
    """
    return multi_scale_topographic_position(
        dem,
        local_radius=local_r,
        meso_radius=meso_r,
        broad_radius=broad_r,
        feedback=feedback,
    )
