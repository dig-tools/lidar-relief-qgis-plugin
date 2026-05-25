"""test_blend.py — Tests for blending modes.
exports: (test functions)
used_by: pytest runner
"""

import numpy as np

from lidar_relief.core.blend import blend_rasters


class TestBlendModes:
    def test_multiply_mode(self):
        a = np.array([[255.0, 128.0], [0.0, 64.0]], dtype=np.float32)
        b = np.array([[128.0, 128.0], [255.0, 64.0]], dtype=np.float32)

        result = blend_rasters(a, b, "multiply")

        # 255 * 128 -> 1.0 * 0.5 = 0.5 -> 127.5
        np.testing.assert_allclose(result[0, 0], 128.0, atol=1.0)
        # 0 * 255 -> 0.0
        np.testing.assert_allclose(result[1, 0], 0.0, atol=1.0)

    def test_screen_mode(self):
        a = np.array([[255.0, 0.0], [0.0, 0.0]], dtype=np.float32)
        b = np.array([[0.0, 255.0], [0.0, 0.0]], dtype=np.float32)

        result = blend_rasters(a, b, "screen")

        # 255 screen 0 -> 255
        np.testing.assert_allclose(result[0, 0], 255.0, atol=1.0)
        # 0 screen 255 -> 255
        np.testing.assert_allclose(result[0, 1], 255.0, atol=1.0)
        # 0 screen 0 -> 0
        np.testing.assert_allclose(result[1, 0], 0.0, atol=1.0)

    def test_nan_preservation(self):
        a = np.array([[255.0, np.nan], [0.0, 64.0]], dtype=np.float32)
        b = np.array([[np.nan, 128.0], [255.0, 64.0]], dtype=np.float32)

        result = blend_rasters(a, b, "multiply")

        assert np.isnan(result[0, 0])
        assert np.isnan(result[0, 1])
        assert not np.isnan(result[1, 0])
