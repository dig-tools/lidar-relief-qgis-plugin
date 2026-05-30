"""test_red_relief.py — Tests for Simple Red Relief Composite.
exports: test_red_relief_basic()
used_by: pytest runner
"""

import numpy as np
from lidar_relief.core.blend import simple_red_relief


def test_red_relief_basic():
    # 10x10 dummy DEM
    dem = np.zeros((10, 10), dtype=np.float32)
    dem[5, 5] = 10.0

    result = simple_red_relief(dem, cellsize=1.0, slrm_radius=3)

    # Check shape
    assert result.shape == dem.shape

    # Check values are between 0 and 255 (due to blending and normalization)
    assert np.nanmin(result) >= 0.0
    assert np.nanmax(result) <= 255.0
