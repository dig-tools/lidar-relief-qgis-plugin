"""test_csf_filter.py — Tests for Cloth Simulation Filter ground extraction.

exports: (test functions)
used_by: pytest runner
rules:
  Tests require CSF library (cloth-simulation-filter).
  Tests build synthetic point clouds with known ground structure.
  CSF results are verified by count, not exact indices (non-deterministic).
"""

import numpy as np
import pytest

pytest.importorskip("CSF")

from lidar_relief.point_cloud.csf_filter import (  # noqa: E402
    csf_available,
    filter_point_cloud,
    ARCHAEOLOGY_PRESETS,
)


class TestCSFFilter:
    """Tests for the CSF ground filter."""

    def test_csf_available(self):
        """CSF library should be available."""
        assert csf_available()

    def test_filter_flat_ground(self):
        """All points on a flat surface should be classified as ground."""
        np.random.seed(42)
        n = 200
        xyz = np.random.uniform(0, 10, (n, 3)).astype(np.float64)
        xyz[:, 2] = 100.0  # Flat at 100m
        xyz[:, 2] += np.random.normal(0, 0.01, n)  # Tiny noise

        ground, offground = filter_point_cloud(
            xyz,
            cloth_resolution=0.5,
            class_threshold=0.5,
            rigidness=1,
            b_slope_smooth=False,
        )

        # Most points should be ground on flat terrain
        assert len(ground) > len(xyz) * 0.8
        assert len(offground) < len(xyz) * 0.2

    def test_filter_with_mound(self):
        """Points on a mound should be partially classified as off-ground."""
        np.random.seed(42)
        n = 500
        x = np.random.uniform(0, 10, n)
        y = np.random.uniform(0, 10, n)
        z = np.zeros(n)
        # Add a raised mound
        mask = (x - 5) ** 2 + (y - 5) ** 2 < 4
        z[mask] = 2.0 * np.exp(-((x[mask] - 5) ** 2 + (y[mask] - 5) ** 2))
        z += np.random.normal(0, 0.02, n)

        xyz = np.column_stack([x, y, z]).astype(np.float64)

        ground, offground = filter_point_cloud(
            xyz,
            cloth_resolution=0.5,
            class_threshold=0.5,
            rigidness=1,
            b_slope_smooth=False,
            time_step=0.65,
        )

        # Should have both ground and non-ground
        assert len(ground) > 0
        assert len(offground) > 0
        assert len(ground) + len(offground) == n

    def test_empty_point_cloud(self):
        """Empty point cloud should return empty arrays."""
        xyz = np.empty((0, 3), dtype=np.float64)
        ground, offground = filter_point_cloud(
            xyz, cloth_resolution=0.5, class_threshold=0.5
        )
        assert len(ground) == 0
        assert len(offground) == 0

    def test_presets_exist(self):
        """All expected presets should be defined."""
        expected = {"archaeology_fine", "archaeology_standard", "forested", "urban"}
        assert expected.issubset(ARCHAEOLOGY_PRESETS.keys())

    def test_preset_has_required_params(self):
        """Each preset should have the required CSF parameters."""
        required = {"cloth_resolution", "class_threshold", "rigidness"}
        for name, params in ARCHAEOLOGY_PRESETS.items():
            for key in required:
                assert key in params, f"Preset '{name}' missing '{key}'"

    def test_invalid_array_shape(self):
        """Non-(N,3) array should raise ValueError."""
        with pytest.raises(ValueError, match="Expected"):
            filter_point_cloud(np.zeros((100, 2)))

    def test_filter_deterministic(self):
        """Same inputs should produce approximately similar results.

        CSF is a physical simulation with floating-point accumulation
        that may vary slightly across runs. We check approximate agreement.
        """
        np.random.seed(42)
        xyz = np.random.uniform(0, 10, (100, 3)).astype(np.float64)
        xyz[:, 2] = np.random.normal(50, 0.5, 100)

        g1, og1 = filter_point_cloud(xyz, class_threshold=0.8)
        g2, og2 = filter_point_cloud(xyz.copy(), class_threshold=0.8)

        # Should classify similarly (within 20% of each other)
        assert abs(len(g1) - len(g2)) <= max(5, len(g1) * 0.2)
