"""test_e4mstp.py — Tests for e4MSTP.
exports: test_e4mstp_basic(), test_e4mstp_nan_propagation(), test_e4mstp_different_dems()
used_by: pytest runner
rules:
  Ensure all random inputs are seeded.
  Assert output correctness, NaN handling, and edge cases.
"""

import numpy as np
from lidar_relief.core.emstp import compute_e4mstp


def test_e4mstp_basic():
    # 20x20 dummy arrays
    rows, cols = 20, 20
    open_pos = np.full((rows, cols), 0.8, dtype=np.float32)
    open_neg = np.full((rows, cols), 0.7, dtype=np.float32)
    local_dom = np.full((rows, cols), 0.5, dtype=np.float32)
    slope = np.full((rows, cols), 0.1, dtype=np.float32)
    mstp = np.full((rows, cols, 3), 0.5, dtype=np.float32)
    dem = np.full((rows, cols), 10.0, dtype=np.float32)
    cellsize = 1.0

    result = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem, cellsize)

    assert result.shape == (20, 20, 3)
    assert result.dtype == np.uint8
    assert np.nanmin(result) >= 0
    assert np.nanmax(result) <= 255


def test_e4mstp_nan_propagation():
    """NaN values in DEM should map to background (0) in the final uint8 composite when they propagate."""
    rows, cols = 20, 20
    open_pos = np.full((rows, cols), 0.8, dtype=np.float32)
    open_neg = np.full((rows, cols), 0.7, dtype=np.float32)
    local_dom = np.full((rows, cols), 0.5, dtype=np.float32)
    slope = np.full((rows, cols), 0.1, dtype=np.float32)
    mstp = np.full((rows, cols, 3), 0.5, dtype=np.float32)
    dem = np.full((rows, cols), 10.0, dtype=np.float32)
    cellsize = 1.0

    # Set NaN in open_pos, which propagates texture (G and B channels) to NaN,
    # mapping them to 0 in the final composite. The R channel is Slope (S) which is non-NaN,
    # so it results in [25, 0, 0].
    open_pos[5, 5] = np.nan

    result = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem, cellsize)
    assert result.shape == (20, 20, 3)
    assert result.dtype == np.uint8
    np.testing.assert_array_equal(result[5, 5], [25, 0, 0])

    # A NaN in DEM is replaced with neutral 1.0 for SVF calculation, so it doesn't cause black pixels
    dem[5, 5] = np.nan
    open_pos[5, 5] = 0.8  # restore
    result_dem_nan = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem, cellsize)
    np.testing.assert_array_equal(result_dem_nan[5, 5], [25, 64, 64])


def test_e4mstp_different_dems():
    """Two different DEMs producing different outputs."""
    rows, cols = 20, 20
    open_pos = np.full((rows, cols), 0.8, dtype=np.float32)
    open_neg = np.full((rows, cols), 0.7, dtype=np.float32)
    local_dom = np.full((rows, cols), 0.5, dtype=np.float32)
    slope = np.full((rows, cols), 0.1, dtype=np.float32)
    mstp = np.full((rows, cols, 3), 0.5, dtype=np.float32)

    dem1 = np.full((rows, cols), 10.0, dtype=np.float32)
    rng = np.random.default_rng(42)
    dem2 = rng.random((rows, cols)).astype(np.float32) * 10.0
    cellsize = 1.0

    result1 = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem1, cellsize)
    result2 = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem2, cellsize)

    # Due to random dem2, SVF will be different, making e4mstp output different
    assert not np.array_equal(result1, result2)
