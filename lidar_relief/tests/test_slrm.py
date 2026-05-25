"""test_slrm.py — Tests for Simple Local Relief Model algorithm.
exports: (test functions)
used_by: pytest runner
rules:
  Tests operate on pure NumPy core — no QGIS required.
  SLRM should remove macro-topography and preserve micro-relief.
"""

import numpy as np
import pytest

from lidar_relief.core.slrm import simple_local_relief_model


class TestSimpleLocalReliefModel:
    """Tests for the simple_local_relief_model function."""

    def test_flat_surface_near_zero(self, flat_dem):
        """A flat surface has no trend to remove — SLRM should be ≈0 everywhere."""
        result = simple_local_relief_model(flat_dem, radius=20)
        valid = result[~np.isnan(result)]
        np.testing.assert_allclose(valid, 0.0, atol=1e-3)

    def test_linear_trend_removed(self, tilted_dem):
        """SLRM should remove a linear trend, leaving residuals ≈0.

        A tilted plane is purely macro-topography with no micro-relief.
        After detrending, the interior should be near zero.
        """
        result = simple_local_relief_model(tilted_dem, radius=20)
        valid = result[~np.isnan(result)]

        # Interior pixels (away from edges affected by boundary handling)
        interior = result[25:75, 25:75]
        interior_valid = interior[~np.isnan(interior)]

        # Should be approximately zero (some edge effects expected)
        assert np.abs(np.mean(interior_valid)) < 2.0, \
            "Linear trend should be mostly removed in the interior"

    def test_ridge_furrow_preserved(self, ridge_furrow_dem):
        """Micro-relief (ridges) should survive after removing the macro-slope.

        The ridge-and-furrow fixture has a gentle slope (macro) plus a sinusoidal
        pattern (micro). After SLRM, the sinusoidal signal should remain.
        """
        result = simple_local_relief_model(ridge_furrow_dem, radius=20)

        # Check that the interior has oscillating residuals
        interior = result[25:75, 25:75]
        interior_valid = interior[~np.isnan(interior)]

        # Standard deviation should be non-trivial (the ridges survived)
        assert np.std(interior_valid) > 0.05, \
            "Micro-relief (ridges) should survive SLRM detrending"

        # The residuals should oscillate around zero
        assert np.abs(np.mean(interior_valid)) < 1.0, \
            "SLRM residuals should centre around zero"

    def test_radius_effect(self, ridge_furrow_dem):
        """Larger radius should preserve larger-scale features."""
        result_small = simple_local_relief_model(ridge_furrow_dem, radius=5)
        result_large = simple_local_relief_model(ridge_furrow_dem, radius=40)

        # With very small radius, even the ridges get smoothed out
        # With large radius, more trend is removed but ridges are fully preserved
        std_small = np.nanstd(result_small[25:75, 25:75])
        std_large = np.nanstd(result_large[25:75, 25:75])

        # Both should have some signal
        assert std_small > 0.0
        assert std_large > 0.0

    def test_nodata_preserved(self, dem_with_nodata):
        """NaN pixels in input should remain NaN in output."""
        result = simple_local_relief_model(dem_with_nodata, radius=10)
        input_nan = np.isnan(dem_with_nodata)
        output_nan = np.isnan(result)
        assert np.all(output_nan[input_nan]), "Input NaN pixels must be NaN in output"

    def test_shape_preserved(self, cone_dem):
        """Output shape must match input shape."""
        result = simple_local_relief_model(cone_dem, radius=15)
        assert result.shape == cone_dem.shape

    def test_dtype_float32(self, flat_dem):
        """Output must be float32."""
        result = simple_local_relief_model(flat_dem, radius=10)
        assert result.dtype == np.float32

    def test_cone_positive_peak_negative_edge(self, cone_dem):
        """Cone peak should be positive (above local mean), edges negative."""
        result = simple_local_relief_model(cone_dem, radius=20)

        # Peak region
        peak_value = result[50, 50]
        assert peak_value > 0, "Cone peak should be positive in SLRM"

        # Edge region (far from cone, where terrain is flat at 0)
        edge_value = result[5, 5]
        assert edge_value <= 0, "Cone edge (flat base) should be ≤0 in SLRM"
