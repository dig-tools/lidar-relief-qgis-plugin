"""conftest.py — Shared test fixtures for LiDAR Relief core algorithm tests.
exports: flat_dem, tilted_dem, cone_dem, ridge_furrow_dem, pit_dem
used_by: test_hillshade.py, test_slrm.py, test_svf.py, test_slope.py
rules:
  All fixtures return float32 NumPy arrays.
  All fixtures are 100×100 pixels for consistent testing.
  Cellsize is always 1.0 metre unless overridden.
"""

import numpy as np
import pytest

try:
    from osgeo import gdal

    gdal.UseExceptions()
except ImportError:
    pass


@pytest.fixture
def flat_dem() -> np.ndarray:
    """A perfectly flat DEM at 100m elevation.

    Expected algorithm results:
        - Hillshade: uniform illumination
        - Slope: 0 everywhere
        - SLRM: 0 everywhere
        - SVF: 1.0 everywhere
    """
    return np.full((100, 100), 100.0, dtype=np.float32)


@pytest.fixture
def tilted_dem() -> np.ndarray:
    """A plane tilted at 45 degrees toward the east (positive X).

    Elevation increases linearly from west (0m) to east (99m).

    Expected algorithm results:
        - Slope: ~45 degrees (with cellsize=1.0)
        - Hillshade: gradient from dark (shadow side) to bright (sun side)
    """
    rows, cols = 100, 100
    x = np.arange(cols, dtype=np.float32)
    return np.tile(x, (rows, 1))


@pytest.fixture
def cone_dem() -> np.ndarray:
    """A symmetric cone peaking at the centre.

    Peak elevation = 50m, base = 0m. Radius = 50 pixels.

    Expected algorithm results:
        - SVF: highest at peak, lower on slopes
        - Slope: consistent around the cone flanks
        - SLRM: positive at peak, negative at edges
    """
    rows, cols = 100, 100
    cy, cx = rows // 2, cols // 2
    y, x = np.mgrid[0:rows, 0:cols]
    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(np.float32)
    cone = np.maximum(50.0 - distance, 0.0)
    return cone


@pytest.fixture
def ridge_furrow_dem() -> np.ndarray:
    """Sinusoidal ridge-and-furrow pattern superimposed on a gentle slope.

    Simulates medieval ridge-and-furrow agricultural earthworks on a
    sloping field — a common archaeological use case for SLRM.

    The gentle slope provides the macro-topography that SLRM should remove,
    revealing the sinusoidal micro-relief.
    """
    rows, cols = 100, 100
    x = np.arange(cols, dtype=np.float32)
    y = np.arange(rows, dtype=np.float32)

    # Gentle north-south slope (macro-topography)
    slope_component = np.outer(y * 0.5, np.ones(cols))

    # Sinusoidal ridge-and-furrow (micro-relief, amplitude 0.3m, period 10px)
    ridges = 0.3 * np.sin(2 * np.pi * x / 10.0)
    ridge_component = np.tile(ridges, (rows, 1))

    return (slope_component + ridge_component).astype(np.float32)


@pytest.fixture
def pit_dem() -> np.ndarray:
    """A flat surface with a deep circular pit in the centre.

    Flat at 100m with a pit of depth 20m at the centre, radius 15px.
    Used to test SVF: the bottom of the pit should have SVF < 1.0.
    """
    rows, cols = 100, 100
    cy, cx = rows // 2, cols // 2
    y, x = np.mgrid[0:rows, 0:cols]
    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(np.float32)

    dem = np.full((rows, cols), 100.0, dtype=np.float32)
    pit_mask = distance < 15.0
    # Depth proportional to distance from centre (deepest at centre)
    dem[pit_mask] = 100.0 - 20.0 * (1.0 - distance[pit_mask] / 15.0)

    return dem


@pytest.fixture
def dem_with_nodata() -> np.ndarray:
    """A flat DEM with a strip of NaN (nodata) values.

    Tests that algorithms correctly propagate nodata through computation.
    """
    dem = np.full((100, 100), 50.0, dtype=np.float32)
    dem[45:55, :] = np.nan  # horizontal nodata strip
    return dem


@pytest.fixture
def cellsize() -> float:
    """Standard 1m cell size for test fixtures."""
    return 1.0
