"""test_mstp.py — Tests for Multi-Scale Topographic Position algorithm.
exports: (test functions)
used_by: pytest runner
"""

import numpy as np

from lidar_relief.core.mstp import (
    multi_scale_topographic_position,
    _window_stats,
    _compute_integral_images,
)


class TestMSTP:
    def test_window_stats_correctness(self):
        """Test integral image stats against slow numpy slice stats."""
        dem = np.random.rand(20, 20).astype(np.float32)
        i_sum, i_sq, _, _ = _compute_integral_images(dem)

        radius = 2
        mean_fast, std_fast = _window_stats(i_sum, i_sq, radius)

        # Check pixel (5, 5)
        # radius=2 means window is from [3:8, 3:8] (exclusive end)
        window = dem[5 - radius : 5 + radius + 1, 5 - radius : 5 + radius + 1]
        mean_slow = np.mean(window)
        std_slow = np.std(window)

        np.testing.assert_allclose(mean_fast[5, 5], mean_slow, atol=1e-5)
        np.testing.assert_allclose(std_fast[5, 5], std_slow, atol=1e-5)

    def test_flat_surface_mid_gray(self, flat_dem):
        """Flat surface should result in mid-gray (127) for all channels."""
        rgb = multi_scale_topographic_position(flat_dem, 2, 5, 10)

        # Valid area (exclude edges where padding might affect variance slightly)
        interior = rgb[5:95, 5:95]

        # Check Red channel
        np.testing.assert_allclose(interior[..., 0], 127, atol=1)
        # Check Green channel
        np.testing.assert_allclose(interior[..., 1], 127, atol=1)
        # Check Blue channel
        np.testing.assert_allclose(interior[..., 2], 127, atol=1)

    def test_shape_and_dtype(self, cone_dem):
        rgb = multi_scale_topographic_position(cone_dem, 5, 10, 20)
        assert rgb.shape == (100, 100, 3)
        assert rgb.dtype == np.uint8

    def test_nodata_is_zero(self, dem_with_nodata):
        rgb = multi_scale_topographic_position(dem_with_nodata, 2, 5, 10)
        input_nan = np.isnan(dem_with_nodata)

        # All channels should be 0 where input is NaN
        assert np.all(rgb[input_nan, 0] == 0)
        assert np.all(rgb[input_nan, 1] == 0)
        assert np.all(rgb[input_nan, 2] == 0)
