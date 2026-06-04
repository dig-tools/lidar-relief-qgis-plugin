"""test_gpu.py — Tests for GPU acceleration backends.

exports: (test functions)
used_by: pytest runner
rules:
  Tests verify fallback behavior when CuPy is unavailable.
  Numerical equivalence tests require CUDA (skipped if not available).
"""

import numpy as np
import pytest

from lidar_relief.gpu.compute_backend import (
    cupy_available,
    get_backend,
    to_array_backend,
    asnumpy,
)


class TestGPUCompute:
    """Tests for GPU acceleration backend."""

    def test_cupy_availability(self):
        """Check CuPy availability (informational)."""
        # Just verify it doesn't crash
        available = cupy_available()
        assert isinstance(available, bool)

    def test_get_backend(self):
        """get_backend should always return a valid backend."""
        backend = get_backend()
        assert backend in ("cupy", "numpy")

    def test_get_backend_no_prefer(self):
        """Prefer_cuda=False should always return numpy."""
        backend = get_backend(prefer_cuda=False)
        assert backend == "numpy"

    def test_to_array_numpy(self):
        """to_array_backend with numpy should return original array."""
        arr = np.array([1.0, 2.0, 3.0])
        result = to_array_backend(arr, "numpy")
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, arr)

    def test_asnumpy_numpy(self):
        """asnumpy on NumPy array should return identity."""
        arr = np.array([1.0, 2.0, 3.0])
        result = asnumpy(arr)
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_equal(result, arr)

    @pytest.mark.skipif(not cupy_available(), reason="CUDA not available")
    def test_svf_gpu_numerical_equivalence(self):
        """GPU SVF should match NumPy SVF within tolerance."""
        from lidar_relief.gpu.compute_backend import compute_svf_gpu
        from lidar_relief.core.svf import sky_view_factor

        np.random.seed(42)
        dem = np.random.random((50, 50)).astype(np.float32) * 50.0

        # Add a cone feature for meaningful SVF variation
        cy, cx = 25, 25
        y, x = np.mgrid[0:50, 0:50]
        cone = np.maximum(10.0 - np.sqrt((x - cx)**2 + (y - cy)**2) * 0.5, 0)
        dem += cone

        # Compute on both backends
        svf_numpy = sky_view_factor(dem, 1.0, num_directions=8, search_radius=10)
        svf_gpu = compute_svf_gpu(dem, 1.0, num_directions=8, search_radius=10)

        # Should be numerically close
        valid = ~np.isnan(svf_numpy) & ~np.isnan(svf_gpu)
        if valid.any():
            max_diff = np.max(np.abs(svf_numpy[valid] - svf_gpu[valid]))
            assert max_diff < 1e-4, f"Max diff: {max_diff}"

    @pytest.mark.skipif(not cupy_available(), reason="CUDA not available")
    def test_openness_gpu_numerical_equivalence(self):
        """GPU Openness should match NumPy Openness within tolerance."""
        from lidar_relief.gpu.compute_backend import compute_openness_gpu
        from lidar_relief.core.openness import topographic_openness

        np.random.seed(42)
        dem = np.random.random((30, 30)).astype(np.float32) * 50.0

        # Compute on both backends
        open_numpy = topographic_openness(
            dem, 1.0, num_directions=8, search_radius=5
        )
        open_gpu = compute_openness_gpu(
            dem, 1.0, num_directions=8, search_radius=5
        )

        valid = ~np.isnan(open_numpy) & ~np.isnan(open_gpu)
        if valid.any():
            max_diff = np.max(np.abs(open_numpy[valid] - open_gpu[valid]))
            assert max_diff < 1e-4, f"Max diff: {max_diff}"
