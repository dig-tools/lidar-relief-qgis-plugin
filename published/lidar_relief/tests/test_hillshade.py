"""test_hillshade.py — Tests for multi-directional hillshade algorithm.
exports: (test functions)
used_by: pytest runner
rules:
  Tests operate on pure NumPy core — no QGIS required.
  All assertions use np.testing for floating-point comparison.
"""

import numpy as np

from lidar_relief.core.hillshade import multidirectional_hillshade


class TestMultidirectionalHillshade:
    """Tests for the multidirectional_hillshade function."""

    def test_flat_surface_uniform(self, flat_dem, cellsize):
        """A flat surface should produce uniform illumination.

        On a flat surface, slope = 0 everywhere, so hillshade = cos(zenith)
        for all azimuths. The blended result should be uniform.
        """
        result = multidirectional_hillshade(flat_dem, cellsize)
        assert result.shape == flat_dem.shape

        # Exclude any NaN
        valid = result[~np.isnan(result)]
        assert len(valid) > 0

        # All valid pixels should have the same value
        np.testing.assert_allclose(valid, valid[0], atol=0.5)

    def test_output_range(self, tilted_dem, cellsize):
        """Output should be in range [0, 255]."""
        result = multidirectional_hillshade(tilted_dem, cellsize)
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 255.0)

    def test_tilted_surface_has_gradient(self, tilted_dem, cellsize):
        """A tilted surface should show variation in hillshade.

        The east-tilted plane should not be uniform — different azimuths
        illuminate it differently.
        """
        result = multidirectional_hillshade(tilted_dem, cellsize)
        valid = result[~np.isnan(result)]
        assert np.std(valid) > 0.1, "Tilted DEM should produce non-uniform hillshade"

    def test_custom_azimuths(self, tilted_dem, cellsize):
        """Custom azimuths should produce a valid result."""
        result = multidirectional_hillshade(
            tilted_dem, cellsize, azimuths=[315.0], altitude=45.0
        )
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0)
        assert np.all(valid <= 255.0)

    def test_altitude_extremes(self, flat_dem, cellsize):
        """Altitude at 90° (directly overhead) should give max illumination on flat."""
        result_overhead = multidirectional_hillshade(flat_dem, cellsize, altitude=90.0)
        result_low = multidirectional_hillshade(flat_dem, cellsize, altitude=10.0)

        valid_overhead = result_overhead[~np.isnan(result_overhead)]
        valid_low = result_low[~np.isnan(result_low)]

        # Overhead sun on flat surface = max illumination
        assert np.mean(valid_overhead) > np.mean(valid_low)

    def test_nodata_preserved(self, dem_with_nodata, cellsize):
        """NaN pixels in input should remain NaN in output."""
        result = multidirectional_hillshade(dem_with_nodata, cellsize)
        input_nan = np.isnan(dem_with_nodata)
        output_nan = np.isnan(result)
        assert np.all(output_nan[input_nan]), "Input NaN pixels must be NaN in output"

    def test_shape_preserved(self, cone_dem, cellsize):
        """Output shape must match input shape."""
        result = multidirectional_hillshade(cone_dem, cellsize)
        assert result.shape == cone_dem.shape

    def test_dtype_float32(self, flat_dem, cellsize):
        """Output must be float32."""
        result = multidirectional_hillshade(flat_dem, cellsize)
        assert result.dtype == np.float32
