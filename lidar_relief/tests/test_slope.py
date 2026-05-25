"""test_slope.py — Tests for slope computation algorithm.
exports: (test functions)
used_by: pytest runner
rules:
  Tests operate on pure NumPy core — no QGIS required.
  Slope values are non-negative for all valid pixels.
"""

import numpy as np
import pytest

from lidar_relief.core.slope import compute_slope


class TestComputeSlope:
    """Tests for the compute_slope function."""

    def test_flat_surface_zero_slope(self, flat_dem, cellsize):
        """A flat surface should have slope ≈ 0 everywhere."""
        result = compute_slope(flat_dem, cellsize, units="degrees")
        valid = result[~np.isnan(result)]
        np.testing.assert_allclose(valid, 0.0, atol=1e-5)

    def test_45_degree_tilted_plane(self, tilted_dem, cellsize):
        """A plane with 1:1 slope (rise=run) should give ≈45° slope.

        The tilted_dem fixture goes from 0 to 99 over 100 pixels with
        cellsize=1.0, so dz/dx = 1.0, giving arctan(1.0) = 45°.
        """
        result = compute_slope(tilted_dem, cellsize, units="degrees")

        # Interior pixels (avoid edge effects from padding)
        interior = result[10:90, 10:90]
        valid = interior[~np.isnan(interior)]

        np.testing.assert_allclose(valid, 45.0, atol=1.0)

    def test_45_degree_as_percent(self, tilted_dem, cellsize):
        """A 45° slope should be 100% in percent units."""
        result = compute_slope(tilted_dem, cellsize, units="percent")

        interior = result[10:90, 10:90]
        valid = interior[~np.isnan(interior)]

        np.testing.assert_allclose(valid, 100.0, atol=2.0)

    def test_slope_non_negative(self, cone_dem, cellsize):
        """Slope must be non-negative for all valid pixels."""
        result_deg = compute_slope(cone_dem, cellsize, units="degrees")
        result_pct = compute_slope(cone_dem, cellsize, units="percent")

        valid_deg = result_deg[~np.isnan(result_deg)]
        valid_pct = result_pct[~np.isnan(result_pct)]

        assert np.all(valid_deg >= 0.0), "Slope (degrees) must be non-negative"
        assert np.all(valid_pct >= 0.0), "Slope (percent) must be non-negative"

    def test_invalid_units_raises(self, flat_dem, cellsize):
        """Invalid units string should raise ValueError."""
        with pytest.raises(ValueError, match="units must be"):
            compute_slope(flat_dem, cellsize, units="radians")

    def test_nodata_preserved(self, dem_with_nodata, cellsize):
        """NaN pixels in input should remain NaN in output."""
        result = compute_slope(dem_with_nodata, cellsize, units="degrees")
        input_nan = np.isnan(dem_with_nodata)
        output_nan = np.isnan(result)
        assert np.all(output_nan[input_nan]), "Input NaN pixels must be NaN in output"

    def test_shape_preserved(self, cone_dem, cellsize):
        """Output shape must match input shape."""
        result = compute_slope(cone_dem, cellsize, units="degrees")
        assert result.shape == cone_dem.shape

    def test_dtype_float32(self, flat_dem, cellsize):
        """Output must be float32."""
        result = compute_slope(flat_dem, cellsize, units="degrees")
        assert result.dtype == np.float32

    def test_cone_slope_symmetry(self, cone_dem, cellsize):
        """A symmetric cone should have roughly symmetric slope values."""
        result = compute_slope(cone_dem, cellsize, units="degrees")

        # Compare north and south flanks (equidistant from centre)
        north_slope = result[30, 50]
        south_slope = result[70, 50]

        np.testing.assert_allclose(north_slope, south_slope, atol=1.0)

    def test_degrees_vs_percent_consistency(self, cone_dem, cellsize):
        """tan(slope_degrees) * 100 should equal slope_percent."""
        degrees = compute_slope(cone_dem, cellsize, units="degrees")
        percent = compute_slope(cone_dem, cellsize, units="percent")

        # Check at a non-zero slope point
        deg_val = degrees[35, 50]
        pct_val = percent[35, 50]

        if not np.isnan(deg_val) and deg_val > 0:
            expected_pct = np.tan(np.deg2rad(deg_val)) * 100.0
            np.testing.assert_allclose(pct_val, expected_pct, atol=0.5)
