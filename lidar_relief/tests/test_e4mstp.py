"""test_e4mstp.py — Tests for e4MSTP.
exports: test_e4mstp_basic() and more
used_by: pytest runner
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
    """NaN values in DEM should propagate or be handled gracefully."""
    rows, cols = 20, 20
    open_pos = np.full((rows, cols), 0.8, dtype=np.float32)
    open_neg = np.full((rows, cols), 0.7, dtype=np.float32)
    local_dom = np.full((rows, cols), 0.5, dtype=np.float32)
    slope = np.full((rows, cols), 0.1, dtype=np.float32)
    mstp = np.full((rows, cols, 3), 0.5, dtype=np.float32)
    dem = np.full((rows, cols), 10.0, dtype=np.float32)
    dem[5, 5] = np.nan
    cellsize = 1.0

    result = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem, cellsize)
    assert result.shape == (20, 20, 3)
    assert result.dtype == np.uint8


def test_e4mstp_different_dems():
    """Two different DEMs producing different outputs."""
    rows, cols = 20, 20
    open_pos = np.full((rows, cols), 0.8, dtype=np.float32)
    open_neg = np.full((rows, cols), 0.7, dtype=np.float32)
    local_dom = np.full((rows, cols), 0.5, dtype=np.float32)
    slope = np.full((rows, cols), 0.1, dtype=np.float32)
    mstp = np.full((rows, cols, 3), 0.5, dtype=np.float32)

    dem1 = np.full((rows, cols), 10.0, dtype=np.float32)
    dem2 = np.random.rand(rows, cols).astype(np.float32) * 10.0
    cellsize = 1.0

    result1 = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem1, cellsize)
    result2 = compute_e4mstp(open_pos, open_neg, local_dom, slope, mstp, dem2, cellsize)

    # Due to random dem2, SVF will be different, making e4mstp output different
    assert not np.array_equal(result1, result2)
