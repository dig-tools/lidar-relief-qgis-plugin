"""test_vat.py — Tests for VAT Composite.
exports: test_vat_basic()
used_by: pytest runner
"""

import numpy as np
from lidar_relief.core.vat import compute_vat


def test_vat_basic():
    # 10x10 dummy DEM
    dem = np.zeros((10, 10), dtype=np.float32)
    # Add some variation so it's not completely flat (to avoid divide by zero if not handled)
    dem[5, 5] = 10.0

    vat_result = compute_vat(dem, cellsize=1.0, svf_radius=2, openness_radius=2)

    # Check shape
    assert vat_result.shape == dem.shape

    # Check values are between 0 and 255 (due to blending and normalization)
    assert np.nanmin(vat_result) >= 0.0
    assert np.nanmax(vat_result) <= 255.0
