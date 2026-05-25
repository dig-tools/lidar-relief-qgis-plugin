"""test_openness.py — Tests for Topographic Openness algorithm.
exports: (test functions)
used_by: pytest runner
rules:
  Tests operate on pure NumPy core — no QGIS required.
"""

import numpy as np

from lidar_relief.core.openness import topographic_openness


class TestTopographicOpenness:
    def test_flat_surface_90_degrees(self, flat_dem, cellsize):
        """A flat surface has a 90° zenith angle (openness)."""
        result = topographic_openness(flat_dem, cellsize, 8, 10, False)
        valid = result[~np.isnan(result)]
        np.testing.assert_allclose(valid, 90.0, atol=2.0)

    def test_cone_positive_openness(self, cone_dem, cellsize):
        """Peak of cone should have high positive openness (> 90)."""
        result = topographic_openness(cone_dem, cellsize, 16, 20, False)

        # Center peak
        peak_openness = result[50, 50]
        # Base/edge (flat)
        base_openness = result[5, 5]

        assert peak_openness > 90.0, "Cone peak should be > 90° (convex)"
        assert peak_openness > base_openness

    def test_pit_negative_openness(self, pit_dem, cellsize):
        """Pit bottom should have high negative openness (> 90)."""
        # Negative openness evaluates the 'downward' hemisphere
        result = topographic_openness(pit_dem, cellsize, 16, 20, True)

        # Center of pit
        pit_openness = result[50, 50]
        # Flat edge
        flat_openness = result[5, 5]

        assert pit_openness > 90.0, (
            "Pit bottom should have high negative openness (concave)"
        )
        assert pit_openness > flat_openness

    def test_nodata_preserved(self, dem_with_nodata, cellsize):
        result = topographic_openness(dem_with_nodata, cellsize, 8, 5)
        input_nan = np.isnan(dem_with_nodata)
        output_nan = np.isnan(result)
        assert np.all(output_nan[input_nan])
