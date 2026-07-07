"""test_svf.py — Tests for Sky-View Factor algorithm.
exports: (test functions)
used_by: pytest runner
rules:
  Tests operate on pure NumPy core — no QGIS required.
  SVF output must be in [0, 1] for all valid pixels.
"""

import numpy as np

from lidar_relief.core.svf import sky_view_factor


class TestSkyViewFactor:
    """Tests for the sky_view_factor function."""

    def test_flat_surface_svf_one(self, flat_dem, cellsize):
        """A perfectly flat surface should have SVF ≈ 1.0 everywhere.

        No surrounding terrain occludes the sky on a flat surface.
        """
        result = sky_view_factor(
            flat_dem, cellsize, num_directions=16, search_radius=10
        )
        valid = result[~np.isnan(result)]

        # Should be very close to 1.0
        np.testing.assert_allclose(valid, 1.0, atol=0.05)

    def test_output_range(self, cone_dem, cellsize):
        """SVF values must be in [0, 1] for all valid pixels."""
        result = sky_view_factor(
            cone_dem, cellsize, num_directions=16, search_radius=10
        )
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0), "SVF must be >= 0"
        assert np.all(valid <= 1.0), "SVF must be <= 1"

    def test_pit_lower_svf(self, pit_dem, cellsize):
        """The bottom of a pit should have lower SVF than surrounding flat terrain.

        The pit walls occlude part of the sky hemisphere.
        """
        result = sky_view_factor(pit_dem, cellsize, num_directions=16, search_radius=20)

        # Centre of pit
        pit_svf = result[50, 50]

        # Far corner (flat terrain, unaffected by pit)
        flat_svf = result[5, 5]

        assert pit_svf < flat_svf, (
            f"Pit SVF ({pit_svf:.3f}) should be lower than flat SVF ({flat_svf:.3f})"
        )

    def test_more_directions_changes_result(self, cone_dem, cellsize):
        """More directions should produce a slightly different (more accurate) result."""
        result_8 = sky_view_factor(
            cone_dem, cellsize, num_directions=8, search_radius=10
        )
        result_32 = sky_view_factor(
            cone_dem, cellsize, num_directions=32, search_radius=10
        )

        # Both should be valid
        assert np.all(result_8[~np.isnan(result_8)] >= 0.0)
        assert np.all(result_32[~np.isnan(result_32)] >= 0.0)

        # They should differ (more directions captures more horizon detail)
        valid_8 = result_8[~np.isnan(result_8)]
        valid_32 = result_32[~np.isnan(result_32)]
        # Not asserting which is larger — just that they differ
        assert not np.allclose(valid_8, valid_32, atol=1e-3), (
            "8 and 32 directions should give slightly different SVF values"
        )

    def test_nodata_preserved(self, dem_with_nodata, cellsize):
        """NaN pixels in input should remain NaN in output."""
        result = sky_view_factor(
            dem_with_nodata, cellsize, num_directions=8, search_radius=5
        )
        input_nan = np.isnan(dem_with_nodata)
        output_nan = np.isnan(result)
        assert np.all(output_nan[input_nan]), "Input NaN pixels must be NaN in output"

    def test_shape_preserved(self, cone_dem, cellsize):
        """Output shape must match input shape."""
        result = sky_view_factor(cone_dem, cellsize, num_directions=8, search_radius=5)
        assert result.shape == cone_dem.shape

    def test_dtype_float32(self, flat_dem, cellsize):
        """Output must be float32."""
        result = sky_view_factor(flat_dem, cellsize, num_directions=8, search_radius=5)
        assert result.dtype == np.float32

    def test_search_radius_effect(self, pit_dem, cellsize):
        """Larger search radius should detect more distant horizon occlusion."""
        result_short = sky_view_factor(
            pit_dem, cellsize, num_directions=16, search_radius=5
        )
        result_long = sky_view_factor(
            pit_dem, cellsize, num_directions=16, search_radius=20
        )

        # Both should be valid SVF
        assert np.all(result_short[~np.isnan(result_short)] >= 0.0)
        assert np.all(result_long[~np.isnan(result_long)] >= 0.0)

        # With longer search radius, the pit walls are more fully captured
        # so pit SVF should be lower with longer radius
        pit_svf_short = result_short[50, 50]
        pit_svf_long = result_long[50, 50]

        assert pit_svf_long <= pit_svf_short + 0.01, (
            "Longer search radius should detect more occlusion in pit"
        )
