"""test_red_relief.py — Tests for Simple Red Relief Composite.
exports: test_red_relief_basic(), test_red_relief_nan_propagation(), test_red_relief_constant_input()
used_by: pytest runner
rules:
  Ensure all random inputs are seeded.
  Assert output correctness, NaN handling, and edge cases.
"""

import numpy as np
from lidar_relief.core.blend import simple_red_relief


def test_red_relief_basic():
    # 10x10 dummy DEM
    rng = np.random.default_rng(42)
    dem = rng.random((10, 10)).astype(np.float32) * 10.0
    dem[5, 5] = 20.0

    result = simple_red_relief(dem, cellsize=1.0, slrm_radius=3)

    # Check shape
    assert result.shape == dem.shape

    # Check values are between 0 and 255 (due to blending and normalization)
    assert np.nanmin(result) >= 0.0
    assert np.nanmax(result) <= 255.0

    # Ensure output has non-trivial standard deviation
    assert np.nanstd(result) > 0.0


def test_red_relief_nan_propagation():
    rng = np.random.default_rng(42)
    dem = rng.random((10, 10)).astype(np.float32) * 10.0
    dem[4, 4] = np.nan

    result = simple_red_relief(dem, cellsize=1.0, slrm_radius=3)

    # NaN in input should propagate to NaN in Red Relief composite at same pixel
    assert np.isnan(result[4, 4])
    assert not np.isnan(result[0, 0])


def test_red_relief_constant_input():
    # Constant inputs should map to flat zero/mid-grey layers
    dem = np.full((10, 10), 10.0, dtype=np.float32)

    result = simple_red_relief(dem, cellsize=1.0, slrm_radius=3)

    assert result.shape == dem.shape
    # Constant input maps to flat zero-variance layers -> slrm and slope are all 0 -> blended to all 0.0
    np.testing.assert_allclose(result, 0.0, atol=1.0)
