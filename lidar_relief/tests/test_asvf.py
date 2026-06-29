"""test_asvf.py — Tests for Anisotropic Sky-View Factor algorithm.

exports: (test functions)
used_by: pytest runner
rules:
  Tests operate on pure NumPy core — no QGIS required.
  ASVF output must be in [0, 1] for all valid pixels.
  Coverage mirrors test_svf.py to ensure the ASVF algorithm
  receives the same level of testing as SVF (previously ASVF
  had zero test coverage despite being a shipped algorithm).
"""

import numpy as np

from lidar_relief.core.asvf import anisotropic_sky_view_factor


class TestAnisotropicSkyViewFactor:
    """Tests for the anisotropic_sky_view_factor function."""

    def test_flat_surface_asvf_one(self, flat_dem, cellsize):
        """A perfectly flat surface should have ASVF ≈ 1.0 everywhere.

        No surrounding terrain occludes the sky on a flat surface,
        regardless of anisotropy direction.
        """
        result = anisotropic_sky_view_factor(
            flat_dem,
            cellsize,
            num_directions=16,
            search_radius=10,
            anisotropy_dir=315.0,
            anisotropy_weight=0.5,
        )
        valid = result[~np.isnan(result)]
        np.testing.assert_allclose(valid, 1.0, atol=0.05)

    def test_output_range(self, cone_dem, cellsize):
        """ASVF values must be in [0, 1] for all valid pixels."""
        result = anisotropic_sky_view_factor(
            cone_dem,
            cellsize,
            num_directions=16,
            search_radius=10,
            anisotropy_dir=315.0,
            anisotropy_weight=0.5,
        )
        valid = result[~np.isnan(result)]
        assert np.all(valid >= 0.0), "ASVF must be >= 0"
        assert np.all(valid <= 1.0), "ASVF must be <= 1"

    def test_pit_lower_asvf(self, pit_dem, cellsize):
        """The bottom of a pit should have lower ASVF than surrounding flat terrain."""
        result = anisotropic_sky_view_factor(
            pit_dem,
            cellsize,
            num_directions=16,
            search_radius=20,
            anisotropy_dir=315.0,
            anisotropy_weight=0.5,
        )
        pit_asvf = result[50, 50]
        flat_asvf = result[5, 5]
        assert pit_asvf < flat_asvf, (
            f"Pit ASVF ({pit_asvf:.3f}) should be lower than flat ASVF ({flat_asvf:.3f})"
        )

    def test_more_directions_changes_result(self, cone_dem, cellsize):
        """More directions should produce a slightly different (more accurate) result."""
        result_8 = anisotropic_sky_view_factor(
            cone_dem, cellsize, num_directions=8, search_radius=10
        )
        result_32 = anisotropic_sky_view_factor(
            cone_dem, cellsize, num_directions=32, search_radius=10
        )
        assert np.all(result_8[~np.isnan(result_8)] >= 0.0)
        assert np.all(result_32[~np.isnan(result_32)] >= 0.0)
        valid_8 = result_8[~np.isnan(result_8)]
        valid_32 = result_32[~np.isnan(result_32)]
        assert not np.allclose(valid_8, valid_32, atol=1e-3), (
            "8 and 32 directions should give slightly different ASVF values"
        )

    def test_nodata_preserved(self, dem_with_nodata, cellsize):
        """NaN pixels in input should remain NaN in output."""
        result = anisotropic_sky_view_factor(
            dem_with_nodata, cellsize, num_directions=8, search_radius=5
        )
        input_nan = np.isnan(dem_with_nodata)
        output_nan = np.isnan(result)
        assert np.all(output_nan[input_nan]), "Input NaN pixels must be NaN in output"

    def test_shape_preserved(self, cone_dem, cellsize):
        """Output shape must match input shape."""
        result = anisotropic_sky_view_factor(
            cone_dem, cellsize, num_directions=8, search_radius=5
        )
        assert result.shape == cone_dem.shape

    def test_dtype_float32(self, flat_dem, cellsize):
        """Output must be float32."""
        result = anisotropic_sky_view_factor(
            flat_dem, cellsize, num_directions=8, search_radius=5
        )
        assert result.dtype == np.float32

    def test_anisotropy_direction_changes_result(self, cone_dem, cellsize):
        """Different anisotropy directions should produce different ASVF values.

        An anisotropy_dir of 0° weights northern directions heavily;
        90° weights eastern directions. On an asymmetric feature like
        a cone, these should produce measurably different outputs.
        """
        result_north = anisotropic_sky_view_factor(
            cone_dem,
            cellsize,
            num_directions=16,
            search_radius=10,
            anisotropy_dir=0.0,
            anisotropy_weight=0.5,
        )
        result_east = anisotropic_sky_view_factor(
            cone_dem,
            cellsize,
            num_directions=16,
            search_radius=10,
            anisotropy_dir=90.0,
            anisotropy_weight=0.5,
        )
        valid_north = result_north[~np.isnan(result_north)]
        valid_east = result_east[~np.isnan(result_east)]
        # They should differ somewhere — anisotropy direction matters.
        assert not np.allclose(valid_north, valid_east, atol=1e-3), (
            "Different anisotropy directions should produce different ASVF values"
        )

    def test_anisotropy_weight_zero_ignores_anisotropy(self, flat_dem, cellsize):
        """With anisotropy_weight=0, ASVF should behave like regular SVF on flat terrain."""
        result = anisotropic_sky_view_factor(
            flat_dem,
            cellsize,
            num_directions=16,
            search_radius=10,
            anisotropy_dir=315.0,
            anisotropy_weight=0.0,
        )
        valid = result[~np.isnan(result)]
        # With zero anisotropy weight, flat surface should still be ~1.0.
        np.testing.assert_allclose(valid, 1.0, atol=0.05)

    def test_cancellation_returns_nan(self, pit_dem, cellsize):
        """When feedback.isCanceled() is True, return a NaN array of correct shape."""

        class CancelledFeedback:
            def isCanceled(self):
                return True

            def setProgress(self, *_args, **_kwargs):
                pass

        result = anisotropic_sky_view_factor(
            pit_dem,
            cellsize,
            num_directions=16,
            search_radius=10,
            feedback=CancelledFeedback(),
        )
        assert result.shape == pit_dem.shape
        assert np.all(np.isnan(result)), (
            "Cancelled ASVF should return an all-NaN array of the input shape"
        )
