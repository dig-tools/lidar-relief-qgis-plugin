"""compute_backend.py — GPU-accelerated compute backends with transparent fallback.

exports: get_backend() -> str,
         cupy_available() -> bool,
         to_array_backend(array, backend) -> Array,
         asnumpy(array) -> np.ndarray,
         compute_svf_gpu(dem, cellsize, **kwargs) -> np.ndarray,
         compute_openness_gpu(dem, cellsize, **kwargs) -> np.ndarray

used_by: core/svf.py (optional acceleration),
         core/openness.py (optional acceleration)

rules:
  Dynamic dispatch: CuPy if NVIDIA GPU available, else NumPy.
  All GPU implementations produce bit-identical results to NumPy.
  No CUDA-specific code in the main algorithm cores.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Try importing CuPy
try:
    import cupy as cp

    _CUDA_AVAILABLE = cp.is_available()
except ImportError:
    _CUDA_AVAILABLE = False
    cp = None


# Backend registry
_BACKENDS = {"numpy": np}


def cupy_available() -> bool:
    """Check if CuPy is installed and CUDA is available."""
    return _CUDA_AVAILABLE


def get_backend(prefer_cuda: bool = True) -> str:
    """Return the preferred compute backend ('cupy' or 'numpy').

    Args:
        prefer_cuda: If True and CuPy is available, return 'cupy'.

    Returns:
        'cupy' if CUDA is available and preferred, else 'numpy'.
    """
    if prefer_cuda and _CUDA_AVAILABLE:
        return "cupy"
    return "numpy"


def to_array_backend(
    array: np.ndarray,
    backend: str = "numpy",
) -> np.ndarray:
    """Transfer a NumPy array to the specified backend.

    Args:
        array: NumPy array on CPU.
        backend: 'cupy' or 'numpy'.

    Returns:
        Array on the target backend.
    """
    if backend == "cupy" and _CUDA_AVAILABLE:
        return cp.asarray(array)
    return array


def asnumpy(array) -> np.ndarray:
    """Convert any backend array to NumPy.

    Args:
        array: NumPy or CuPy array.

    Returns:
        NumPy array on CPU.
    """
    if _CUDA_AVAILABLE and isinstance(array, cp.ndarray):
        return cp.asnumpy(array)
    return np.asarray(array)


def _shift_array_gpu(
    arr: "cp.ndarray",
    shift_y: int,
    shift_x: int,
    fill_value: float = 0.0,
) -> "cp.ndarray":
    """CuPy-native array shift (parallel to array_utils._shift_array)."""
    result = cp.full_like(arr, fill_value)
    if shift_y == 0 and shift_x == 0:
        return arr.copy()

    src_y_start = max(0, -shift_y)
    src_x_start = max(0, -shift_x)
    dst_y_start = max(0, shift_y)
    dst_x_start = max(0, shift_x)

    src_y_end = arr.shape[0] + min(0, shift_y)
    src_x_end = arr.shape[1] + min(0, shift_x)

    h = src_y_end - src_y_start
    w = src_x_end - src_x_start
    if h > 0 and w > 0:
        result[dst_y_start:dst_y_start + h, dst_x_start:dst_x_start + w] = (  # noqa: E203
            arr[src_y_start:src_y_start + h, src_x_start:src_x_start + w]  # noqa: E203
        )

    return result


def _compute_horizon_gpu(
    dem: "cp.ndarray",
    dx: int,
    dy: int,
    cellsize: float,
    max_steps: int,
    init_val: float = 0.0,
) -> "cp.ndarray":
    """Compute the horizon angle in a given direction using CuPy.

    Parallel to the NumPy version in core/svf.py.
    """
    rows, cols = dem.shape
    horizon = cp.full((rows, cols), init_val, dtype=cp.float64)

    distance = cp.sqrt(
        cp.float64(dx * cellsize) ** 2 + cp.float64(dy * cellsize) ** 2
    )

    for step in range(1, max_steps + 1):
        shifted = _shift_array_gpu(dem, dy * step, dx * step, fill_value=cp.nan)
        dz = shifted - dem

        sin_angle = cp.where(
            ~cp.isnan(shifted) & ~cp.isnan(dem),
            dz / cp.sqrt(dz ** 2 + distance ** 2 * step ** 2),
            init_val,
        )

        horizon = cp.maximum(horizon, sin_angle)

    return horizon


def compute_svf_gpu(
    dem: np.ndarray,
    cellsize: float,
    num_directions: int = 16,
    search_radius: int = 10,
) -> np.ndarray:
    """Compute Sky-View Factor using GPU acceleration.

    Args:
        dem: 2D float32 NumPy array.
        cellsize: Cell size in map units.
        num_directions: Number of azimuth directions.
        search_radius: Search radius in pixels.

    Returns:
        2D float32 NumPy array (SVF values, 0–1).
    """
    if not _CUDA_AVAILABLE:
        logger.warning("CUDA not available, falling back to NumPy SVF")
        from ..core.svf import sky_view_factor
        return sky_view_factor(dem, cellsize, num_directions, search_radius)

    # Transfer to GPU
    d_dem = cp.asarray(dem, dtype=cp.float32)
    nan_mask = cp.isnan(d_dem)
    d_dem[nan_mask] = cp.nanmean(d_dem)
    
    rows, cols = d_dem.shape
    svf_accum = cp.zeros((rows, cols), dtype=cp.float64)

    # Directions
    angles = cp.linspace(0, 2 * cp.pi, num_directions, endpoint=False)
    dx = cp.round(cp.cos(angles)).astype(cp.int32)
    dy = cp.round(cp.sin(angles)).astype(cp.int32)

    for i in range(num_directions):
        horizon = _compute_horizon_gpu(
            d_dem, int(dx[i]), int(dy[i]), cellsize, search_radius, init_val=0.0
        )
        horizon = cp.maximum(horizon, 0.0)
        svf_accum += 1.0 - horizon

    svf = svf_accum / num_directions
    svf = cp.clip(svf, 0.0, 1.0).astype(cp.float32)
    svf[nan_mask] = cp.nan

    return cp.asnumpy(svf)


def compute_openness_gpu(
    dem: np.ndarray,
    cellsize: float,
    num_directions: int = 16,
    search_radius: int = 10,
    is_negative: bool = False,
) -> np.ndarray:
    """Compute Topographic Openness using GPU acceleration.

    Args:
        dem: 2D float32 NumPy array.
        cellsize: Cell size in map units.
        num_directions: Number of azimuth directions.
        search_radius: Search radius in pixels.
        is_negative: If True, compute negative openness.

    Returns:
        2D float32 NumPy array (degrees).
    """
    if not _CUDA_AVAILABLE:
        logger.warning("CUDA not available, falling back to NumPy Openness")
        from ..core.openness import topographic_openness
        return topographic_openness(
            dem, cellsize, num_directions, search_radius, is_negative
        )

    # Transfer to GPU
    if is_negative:
        dem_copy = -dem
    else:
        dem_copy = dem

    d_dem = cp.asarray(dem_copy, dtype=cp.float32)
    nan_mask = cp.isnan(d_dem)
    d_dem[nan_mask] = cp.nanmean(d_dem)

    rows, cols = d_dem.shape
    openness_accum = cp.zeros((rows, cols), dtype=cp.float64)

    angles = cp.linspace(0, 2 * cp.pi, num_directions, endpoint=False)
    dx = cp.round(cp.cos(angles)).astype(cp.int32)
    dy = cp.round(cp.sin(angles)).astype(cp.int32)

    for i in range(num_directions):
        horizon = _compute_horizon_gpu(
            d_dem, int(dx[i]), int(dy[i]), cellsize, search_radius, init_val=-1.0
        )
        openness_accum += cp.pi / 2.0 - cp.arcsin(horizon)

    result = openness_accum / num_directions
    result_deg = cp.degrees(result).astype(cp.float32)
    result_deg[nan_mask] = cp.nan

    return cp.asnumpy(result_deg)
