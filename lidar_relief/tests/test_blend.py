"""test_blend.py — Tests for blending modes.
exports: (test functions)
used_by: pytest runner
"""

import numpy as np
import pytest

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

    def test_soft_light_mode(self):
        a = np.array([[128.0]], dtype=np.float32)  # 0.5
        b = np.array([[64.0]], dtype=np.float32)  # ~0.25 (darkens)

        result = blend_rasters(a, b, "soft_light")
        # b < 0.5 -> pegtop: (1 - 2*b)*a^2 + 2*a*b
        # a=0.5, b=0.25 -> (1 - 0.5)*0.25 + 2*0.5*0.25 = 0.5*0.25 + 0.25 = 0.125 + 0.25 = 0.375
        # 0.375 * 255 = 95.625
        np.testing.assert_allclose(result[0, 0], 95.6, atol=1.0)

    def test_opacity(self):
        a = np.array([[255.0]], dtype=np.float32)  # Base: white
        b = np.array([[0.0]], dtype=np.float32)  # Blend: black

        # Multiply blend gives 0.0 (black)

        # Opacity 1.0 -> Fully blended (0.0)
        res_full = blend_rasters(a, b, "multiply", opacity=1.0)
        np.testing.assert_allclose(res_full[0, 0], 0.0, atol=1.0)

        # Opacity 0.0 -> Fully base (255.0)
        res_zero = blend_rasters(a, b, "multiply", opacity=0.0)
        np.testing.assert_allclose(res_zero[0, 0], 255.0, atol=1.0)

        # Opacity 0.5 -> 50% mixed (127.5)
        res_half = blend_rasters(a, b, "multiply", opacity=0.5)
        np.testing.assert_allclose(res_half[0, 0], 127.5, atol=1.0)

    def test_overlay_mode(self):
        # Test overlay blend mode
        a = np.array([[64.0, 192.0]], dtype=np.float32)  # ~0.25, ~0.75
        b = np.array([[128.0, 128.0]], dtype=np.float32)  # ~0.5, ~0.5

        result = blend_rasters(a, b, "overlay")
        # idx 0: a < 0.5 -> 2 * 0.25 * 0.5 = 0.25 -> 63.75
        np.testing.assert_allclose(result[0, 0], 63.75, atol=1.0)
        # idx 1: a >= 0.5 -> 1 - 2 * (1 - 0.75) * (1 - 0.5) = 1 - 2 * 0.25 * 0.5 = 0.75 -> 191.25
        np.testing.assert_allclose(result[0, 1], 191.25, atol=1.0)

    def test_invalid_mode(self):
        a = np.array([[128.0]], dtype=np.float32)
        b = np.array([[128.0]], dtype=np.float32)
        with pytest.raises(ValueError, match="Unknown blend mode"):
            blend_rasters(a, b, "invalid_mode")

    def test_shape_mismatch(self):
        a = np.ones((2, 2), dtype=np.float32)
        b = np.ones((3, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="Arrays must have the same shape"):
            blend_rasters(a, b, "multiply")
