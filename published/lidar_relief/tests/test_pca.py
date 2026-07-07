"""test_pca.py — Tests for PCA Composite.
exports: test_pca_basic(), test_pca_nan_propagation(), test_pca_constant_input()
used_by: pytest runner
rules:
  Ensure all random inputs are seeded.
  Assert output correctness, NaN handling, and edge cases.
"""

import numpy as np
from lidar_relief.core.pca import compute_pca_composite


def test_pca_basic():
    rng = np.random.default_rng(42)
    svf = rng.random((20, 20)).astype(np.float32)
    openness = rng.random((20, 20)).astype(np.float32)
    slope = rng.random((20, 20)).astype(np.float32)
    ld = rng.random((20, 20)).astype(np.float32)

    result = compute_pca_composite(svf, openness, slope, ld)

    # Check shape (3 channels)
    assert result.shape == (20, 20, 3)

    # Check values are between 0 and 255
    assert np.nanmin(result) >= 0.0
    assert np.nanmax(result) <= 255.0

    # Ensure PCA outputs are non-trivial (not all constant gray unless inputs are constant)
    assert np.std(result) > 0.0


def test_pca_nan_propagation():
    rng = np.random.default_rng(42)
    svf = rng.random((20, 20)).astype(np.float32)
    openness = rng.random((20, 20)).astype(np.float32)
    slope = rng.random((20, 20)).astype(np.float32)
    ld = rng.random((20, 20)).astype(np.float32)

    svf[5, 5] = np.nan

    result = compute_pca_composite(svf, openness, slope, ld)

    # NaN in input should propagate to NaNs in all channels at that pixel
    assert np.isnan(result[5, 5]).all()
    # Non-nan pixels should remain non-nan
    assert not np.isnan(result[0, 0]).any()


def test_pca_constant_input():
    # Constant inputs (std is 0) should not crash and should return standard gray outputs
    svf = np.ones((20, 20), dtype=np.float32)
    openness = np.ones((20, 20), dtype=np.float32)
    slope = np.ones((20, 20), dtype=np.float32)
    ld = np.ones((20, 20), dtype=np.float32)

    result = compute_pca_composite(svf, openness, slope, ld)

    assert result.shape == (20, 20, 3)
    # The output is standard gray or empty because covariance is zero
    assert np.allclose(result, 0.0)
