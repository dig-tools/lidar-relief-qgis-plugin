"""slrm.py — Simple Local Relief Model (SLRM) algorithm.
exports: simple_local_relief_model(dem, radius) -> ndarray
used_by: algorithms/slrm_algorithm.py → simple_local_relief_model
         algorithms/batch_algorithm.py → simple_local_relief_model
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Output is float32 detrended surface: 0 = local mean, positive = above, negative = below.
  Try scipy.ndimage.uniform_filter first; fall back to iterated box filter if unavailable.
"""

import numpy as np

# Attempt scipy import — QGIS bundles it on most platforms
try:
    from scipy.ndimage import uniform_filter
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


def _box_filter_1d(array: np.ndarray, size: int, axis: int) -> np.ndarray:
    """Apply a 1D box (mean) filter along an axis using cumulative sums.

    This is the fallback when scipy is not available.

    Args:
        array: Input array.
        size: Filter kernel size (odd integer).
        axis: Axis along which to filter.

    Returns:
        Smoothed array with same shape.

    Rules:
        Uses cumulative sum for O(n) complexity regardless of kernel size.
        Edge handling: reflect padding to reduce boundary artifacts.
    """
    half = size // 2
    padded = np.pad(array, [(half, half) if i == axis else (0, 0)
                            for i in range(array.ndim)], mode="reflect")

    cumsum = np.cumsum(padded, axis=axis)

    # Build slicing for the cumsum difference
    slc_end = [slice(None)] * array.ndim
    slc_start = [slice(None)] * array.ndim
    slc_end[axis] = slice(size, None)
    slc_start[axis] = slice(None, -size)

    result = (cumsum[tuple(slc_end)] - cumsum[tuple(slc_start)]) / size
    return result


def _mean_filter_fallback(array: np.ndarray, radius: int) -> np.ndarray:
    """Approximate circular mean filter using separable box filters.

    Applies a box filter of size (2*radius+1) along each axis sequentially.
    This is a good approximation of a circular mean for detrending purposes.

    Args:
        array: 2D input array.
        radius: Filter radius in pixels.

    Returns:
        Smoothed array.

    Rules:
        Three passes of box filter approximate a Gaussian (Van Vliet, 1998).
        We use a single pass since SLRM only needs trend removal, not precision.
    """
    size = 2 * radius + 1
    result = _box_filter_1d(array, size, axis=0)
    result = _box_filter_1d(result, size, axis=1)
    return result


def simple_local_relief_model(
    dem: np.ndarray,
    radius: int = 20,
) -> np.ndarray:
    """Compute Simple Local Relief Model (SLRM).

    SLRM removes large-scale topographic trends to isolate micro-relief features:
        SLRM(x, y) = DEM(x, y) − mean_filter(DEM, radius)(x, y)

    Positive values indicate features raised above the local mean (embankments,
    walls, mounds). Negative values indicate depressions (ditches, pits, moats).

    Args:
        dem: 2D float32 elevation array (nodata as np.nan).
        radius: Smoothing radius in pixels. Controls the scale of features
                enhanced — larger radius preserves larger features.

    Returns:
        Float32 array of detrended elevation residuals.
        0 = local mean ground level.

    Rules:
        NaN pixels must be temporarily filled for the smoothing operation,
        then restored as NaN in the output.
        Uses scipy.ndimage.uniform_filter if available; otherwise falls back
        to cumulative-sum box filter.
    """
    # Fill NaN with local mean estimate (0.0 is acceptable for trend removal)
    nan_mask = np.isnan(dem)
    dem_filled = dem.copy()
    dem_filled[nan_mask] = 0.0

    # Compute smoothed surface
    kernel_size = 2 * radius + 1

    if _HAS_SCIPY:
        smoothed = uniform_filter(dem_filled, size=kernel_size, mode="reflect")
    else:
        smoothed = _mean_filter_fallback(dem_filled, radius)

    smoothed = smoothed.astype(np.float32)

    # SLRM = original - smoothed
    result = dem - smoothed

    # Restore NaN
    result[nan_mask] = np.nan

    return result
