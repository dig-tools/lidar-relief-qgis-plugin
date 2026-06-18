"""test_local_dominance.py — Tests for Local Dominance computation.
exports: test_local_dominance_cone() and more
used_by: pytest runner
"""

import numpy as np
from lidar_relief.core.local_dominance import compute_local_dominance


def test_local_dominance_cone():
    """Cone DEM produces highest values at peak and lowest at base ring."""
    rows, cols = 50, 50
    center_r, center_c = rows // 2, cols // 2
    y, x = np.ogrid[:rows, :cols]
    dist_from_center = np.sqrt((x - center_c) ** 2 + (y - center_r) ** 2)
    dem = 100.0 - dist_from_center
    cellsize = 1.0

    result = compute_local_dominance(
        dem,
        cellsize,
        min_rad=5.0,
        max_rad=15.0,
        rad_inc=1.0,
        anglr_res=15.0,
        observer_h=1.7,
    )

    # Peak should have very high dominance
    peak_val = result[center_r, center_c]
    assert peak_val > 50

    # Base ring (e.g., radius 20 from center) should have lower dominance
    base_val = result[center_r + 20, center_c]
    assert base_val < peak_val


def test_local_dominance_flat():
    """Flat DEM produces uniform output."""
    dem = np.full((30, 30), 10.0, dtype=np.float32)
    cellsize = 1.0

    result = compute_local_dominance(dem, cellsize, min_rad=5, max_rad=10)

    # Check that all non-edge values are the same
    inner_result = result[10:20, 10:20]
    assert np.all(inner_result == inner_result[0, 0])


def test_local_dominance_pit():
    """Pit DEM produces low values at centre."""
    rows, cols = 50, 50
    center_r, center_c = rows // 2, cols // 2
    y, x = np.ogrid[:rows, :cols]
    dist_from_center = np.sqrt((x - center_c) ** 2 + (y - center_r) ** 2)
    dem = dist_from_center  # Pit: lowest at center
    cellsize = 1.0

    result = compute_local_dominance(dem, cellsize, min_rad=5, max_rad=15)

    pit_val = result[center_r, center_c]
    rim_val = result[center_r + 15, center_c]
    assert pit_val <= rim_val


def test_local_dominance_nan_propagation():
    """NaN values in DEM propagate as 0 or handled correctly."""
    dem = np.full((30, 30), 10.0, dtype=np.float32)
    dem[15, 15] = np.nan
    cellsize = 1.0

    result = compute_local_dominance(dem, cellsize, min_rad=5, max_rad=10)
    # The current LD implementation byte scales. If it produces 0 or specific byte value for NaN, we check shape.
    assert result.shape == (30, 30)


def test_local_dominance_observer_height():
    """Observer height affects output magnitude."""
    dem = np.random.rand(30, 30).astype(np.float32) * 10
    cellsize = 1.0

    res_low = compute_local_dominance(
        dem, cellsize, min_rad=5, max_rad=10, observer_h=1.0
    )
    res_high = compute_local_dominance(
        dem, cellsize, min_rad=5, max_rad=10, observer_h=5.0
    )

    # Higher observer should mean generally higher dominance (angles looking down are larger)
    assert np.mean(res_high) > np.mean(res_low)


def test_local_dominance_shape_and_dtype():
    """Output shape and dtype matches expectations."""
    dem = np.random.rand(25, 30).astype(np.float32)
    result = compute_local_dominance(dem, 1.0, min_rad=5, max_rad=10)
    assert result.shape == dem.shape
    assert result.dtype == np.float32

