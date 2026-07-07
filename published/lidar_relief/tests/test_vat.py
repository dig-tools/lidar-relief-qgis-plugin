"""test_vat.py — Tests for VAT Composite.
exports: test_vat_basic(), test_vat_nan_propagation(), test_vat_constant_input()
used_by: pytest runner
rules:
  Ensure all random inputs are seeded.
  Assert output correctness, NaN handling, and edge cases.
"""

import numpy as np
from lidar_relief.core.vat import compute_vat


def test_vat_basic():
    # 10x10 dummy DEM with variation
    rng = np.random.default_rng(42)
    dem = rng.random((10, 10)).astype(np.float32) * 10.0
    dem[5, 5] = 20.0

    vat_result = compute_vat(dem, cellsize=1.0, svf_radius=2, openness_radius=2)

    # Check shape
    assert vat_result.shape == dem.shape

    # Check values are between 0 and 255 (due to blending and normalization)
    assert np.nanmin(vat_result) >= 0.0
    assert np.nanmax(vat_result) <= 255.0

    # Ensure output has non-trivial standard deviation
    assert np.nanstd(vat_result) > 0.0


def test_vat_nan_propagation():
    rng = np.random.default_rng(42)
    dem = rng.random((10, 10)).astype(np.float32) * 10.0
    dem[3, 3] = np.nan

    vat_result = compute_vat(dem, cellsize=1.0, svf_radius=2, openness_radius=2)

    # NaN in input should propagate to NaN in VAT composite at same pixel
    assert np.isnan(vat_result[3, 3])
    assert not np.isnan(vat_result[0, 0])


def test_vat_constant_input():
    # Constant inputs should be handled gracefully
    dem = np.full((10, 10), 10.0, dtype=np.float32)

    vat_result = compute_vat(dem, cellsize=1.0, svf_radius=2, openness_radius=2)

    assert vat_result.shape == dem.shape
    # Constant input maps to 71.71875 mathematically based on normalizations and nested blend modes
    np.testing.assert_allclose(vat_result, 71.71875, atol=1.0)
