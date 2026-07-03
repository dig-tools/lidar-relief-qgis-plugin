"""test_rvt.py — Tests for the rvt-py core wrapper.
exports: (test functions)
used_by: pytest runner

The whole module is skipped if rvt-py isn't importable — these tests
exercise the wrapper directly so they don't need GDAL/QGIS.
"""

import numpy as np
import pytest

from lidar_relief.core.rvt_vis import (
    has_rvt,
    rvt_multidirectional_hillshade,
    rvt_single_hillshade,
    rvt_openness,
    RVTNotAvailable,
)


pytestmark = pytest.mark.skipif(
    not has_rvt(),
    reason="rvt-py not installed (pip install rvt-py)",
)


class TestRvtMultidirectionalHillshade:
    def test_output_shape_matches_input(self, flat_dem):
        result = rvt_multidirectional_hillshade(flat_dem, cellsize=1.0, nr_directions=8)
        assert result.shape == flat_dem.shape + (8,)

    def test_output_dtype_float32(self, flat_dem):
        result = rvt_multidirectional_hillshade(flat_dem, cellsize=1.0, nr_directions=8)
        assert result.dtype == np.float32

    def test_flat_surface_is_bright(self, flat_dem):
        # A flat surface lit from a 35° altitude should produce a near-uniform,
        # bright result — well above 0.5 on average for [0, 1] cosine hillshade.
        result = rvt_multidirectional_hillshade(
            flat_dem, cellsize=1.0, nr_directions=16
        )
        valid = result[~np.isnan(result)]
        assert valid.size > 0
        assert np.mean(valid) > 0.5

    def test_tilted_surface_has_variation(self, tilted_dem):
        result = rvt_multidirectional_hillshade(
            tilted_dem, cellsize=1.0, nr_directions=16
        )
        valid = result[~np.isnan(result)]
        assert valid.size > 0
        # Tilted DEM should not be uniform — at least some standard deviation.
        assert np.std(valid) > 0.01

    def test_output_range_zero_to_one(self, tilted_dem):
        result = rvt_multidirectional_hillshade(
            tilted_dem, cellsize=1.0, nr_directions=8
        )
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_nan_in_is_nan_out(self, dem_with_nodata):
        result = rvt_multidirectional_hillshade(
            dem_with_nodata, cellsize=1.0, nr_directions=8
        )
        input_nan = np.isnan(dem_with_nodata)
        # Every input NaN pixel must remain NaN in all direction bands.
        assert np.all(np.isnan(result[input_nan]))
        # No NaN may appear where the input had data
        assert not np.any(np.isnan(result[~input_nan]))

    def test_validates_nr_directions_lower_bound(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_multidirectional_hillshade(flat_dem, cellsize=1.0, nr_directions=2)

    def test_validates_nr_directions_upper_bound(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_multidirectional_hillshade(flat_dem, cellsize=1.0, nr_directions=128)

    def test_validates_cellsize_positive(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_multidirectional_hillshade(flat_dem, cellsize=0.0, nr_directions=8)

    def test_supports_various_direction_counts(self, flat_dem):
        for n in (4, 8, 16, 32, 64):
            result = rvt_multidirectional_hillshade(
                flat_dem, cellsize=1.0, nr_directions=n
            )
            assert result.shape == flat_dem.shape + (n,)
            assert result.dtype == np.float32


class TestRvtSingleHillshade:
    def test_single_returns_same_shape(self, tilted_dem):
        result = rvt_single_hillshade(
            tilted_dem, cellsize=1.0, azimuth_deg=315.0, altitude_deg=45.0
        )
        assert result.shape == tilted_dem.shape

    def test_single_output_range(self, tilted_dem):
        result = rvt_single_hillshade(
            tilted_dem, cellsize=1.0, azimuth_deg=315.0, altitude_deg=45.0
        )
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 1.0)

    def test_single_nan_propagation(self, dem_with_nodata):
        result = rvt_single_hillshade(
            dem_with_nodata, cellsize=1.0, azimuth_deg=315.0, altitude_deg=45.0
        )
        input_nan = np.isnan(dem_with_nodata)
        assert np.all(np.isnan(result)[input_nan])
        assert not np.any(np.isnan(result)[~input_nan])

    def test_validates_cellsize_positive(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_single_hillshade(flat_dem, cellsize=-1.0)


class TestRvtNotAvailableError:
    def test_error_message_contains_install_command(self):
        err = RVTNotAvailable()
        assert "pip install rvt-py" in str(err)


class TestRvtOpenness:
    def test_output_shape_matches_input(self, flat_dem):
        result = rvt_openness(flat_dem, cellsize=1.0, search_radius=10)
        assert result.shape == flat_dem.shape

    def test_output_dtype_float32(self, flat_dem):
        result = rvt_openness(flat_dem, cellsize=1.0, search_radius=10)
        assert result.dtype == np.float32

    def test_flat_surface_is_90_degrees(self, flat_dem):
        # A perfectly horizontal surface has 90° openness (zenith angle)
        # to match the Yokoyama topographic openness contract.
        result = rvt_openness(
            flat_dem, cellsize=1.0, search_radius=20, num_directions=16
        )
        valid = result[~np.isnan(result)]
        assert valid.size > 0
        np.testing.assert_allclose(valid, 90.0, atol=5.0)

    def test_positive_openness_in_zero_to_one_hundred_eighty(self, tilted_dem):
        result = rvt_openness(
            tilted_dem,
            cellsize=1.0,
            search_radius=20,
            num_directions=16,
            is_negative=False,
        )
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 180.0)

    def test_tilted_surface_has_variation(self, tilted_dem):
        result = rvt_openness(tilted_dem, cellsize=1.0, search_radius=20)
        valid = result[~np.isnan(result)]
        # Tilted DEM has different openness per cell (surface faces different
        # directions), so std-dev should be meaningful.
        assert np.std(valid) > 1.0

    def test_nan_in_is_nan_out(self, dem_with_nodata):
        result = rvt_openness(dem_with_nodata, cellsize=1.0, search_radius=10)
        input_nan = np.isnan(dem_with_nodata)
        assert np.all(np.isnan(result)[input_nan])
        # No NaN may appear where the input had data
        assert not np.any(np.isnan(result)[~input_nan])

    def test_validates_cellsize_positive(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_openness(flat_dem, cellsize=0.0)

    def test_validates_radius_lower_bound(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_openness(flat_dem, cellsize=1.0, search_radius=0)

    def test_validates_radius_upper_bound(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_openness(flat_dem, cellsize=1.0, search_radius=501)

    def test_validates_num_directions_bounds(self, flat_dem):
        with pytest.raises(ValueError):
            rvt_openness(flat_dem, cellsize=1.0, num_directions=2)
        with pytest.raises(ValueError):
            rvt_openness(flat_dem, cellsize=1.0, num_directions=128)

    def test_supports_various_direction_counts(self, flat_dem):
        for n in (4, 8, 16, 32, 64):
            result = rvt_openness(
                flat_dem, cellsize=1.0, num_directions=n, search_radius=10
            )
            assert result.shape == flat_dem.shape
            assert result.dtype == np.float32
