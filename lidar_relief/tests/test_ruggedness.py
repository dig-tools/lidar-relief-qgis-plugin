"""Tests for Terrain Ruggedness Index."""

import numpy as np
import pytest

from lidar_relief.core.ruggedness import compute_ruggedness


def test_flat_dem_has_zero_ruggedness():
    dem = np.full((5, 5), 12.0, dtype=np.float32)
    result = compute_ruggedness(dem, cellsize=1.0)
    np.testing.assert_array_equal(result, np.zeros((5, 5), dtype=np.float32))


def test_central_peak_matches_riley_definition():
    dem = np.zeros((3, 3), dtype=np.float32)
    dem[1, 1] = 2.0
    result = compute_ruggedness(dem, cellsize=1.0)
    assert result[1, 1] == pytest.approx(np.sqrt(8 * 2.0**2))


def test_nodata_is_preserved_without_edge_halo():
    dem = np.ones((3, 3), dtype=np.float32)
    dem[0, 0] = np.nan
    result = compute_ruggedness(dem, cellsize=1.0)
    assert np.isnan(result[0, 0])
    assert result[0, 1] == 0.0


def test_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="positive"):
        compute_ruggedness(np.ones((2, 2)), cellsize=0)
    with pytest.raises(ValueError, match="2D"):
        compute_ruggedness(np.ones((2, 2, 2)), cellsize=1)
