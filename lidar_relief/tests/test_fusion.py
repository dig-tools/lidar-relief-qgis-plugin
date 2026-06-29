"""test_fusion.py — Tests for multi-sensor fusion (LiDAR + Sentinel-2).

exports: (test functions)
used_by: pytest runner
rules:
  Tests use synthetic DEMs and simulated spectral bands.
  Requires rasterio/rioxarray.
"""

import os
import tempfile

import numpy as np
import pytest

pytest.importorskip("osgeo")
# Fusion module additionally requires rasterio + rioxarray — skip the
# entire module if either is missing (the previous code only checked
# osgeo, which caused test_fusion_available to do `assert fusion_available()`
# and fail with a confusing ImportError when rasterio wasn't installed).
pytest.importorskip("rasterio")
pytest.importorskip("rioxarray")

from osgeo import gdal  # noqa: E402


@pytest.fixture(autouse=True)
def setup():
    tmpdir = tempfile.mkdtemp(prefix="fusion_test_")
    yield tmpdir
    import shutil

    shutil.rmtree(tmpdir)


def _create_raster(
    path: str,
    data: np.ndarray,
    gt=(500000, 1.0, 0, 6000000, 0, -1.0),
    crs="EPSG:32630",
    dtype=gdal.GDT_Float32,
):
    """Write a single-band raster from a numpy array."""
    rows, cols = data.shape
    ds = gdal.GetDriverByName("GTiff").Create(
        path,
        cols,
        rows,
        1,
        dtype,
        options=["COMPRESS=LZW", "TILED=YES"],
    )
    ds.SetGeoTransform(gt)
    ds.SetProjection(crs)
    band = ds.GetRasterBand(1)
    band.WriteArray(data)
    band.FlushCache()
    ds = None


class TestFusion:
    """Tests for multi-sensor fusion."""

    def test_fusion_available(self):
        """Fusion libraries should be available."""
        from lidar_relief.fusion.sentinel_fusion import fusion_available

        if not fusion_available():
            pytest.skip("rasterio/rioxarray not installed")
        assert fusion_available()

    def test_co_register(self, setup):
        """Co-registration should produce matching dimensions."""
        from lidar_relief.fusion.sentinel_fusion import co_register_bands

        # Reference: 100x100 LiDAR relief
        ref = np.random.default_rng(42).random((100, 100)).astype(np.float32)
        ref_path = os.path.join(setup, "lidar.tif")
        _create_raster(ref_path, ref)

        # Target: 50x50 S2 band (different resolution)
        s2 = np.random.default_rng(99).random((50, 50)).astype(np.float32)
        s2_path = os.path.join(setup, "s2_band.tif")
        _create_raster(s2_path, s2, gt=(500000, 2.0, 0, 6000000, 0, -2.0))

        aligned_path = os.path.join(setup, "aligned.tif")
        result = co_register_bands(ref_path, s2_path, aligned_path)

        assert os.path.exists(aligned_path)
        assert result["width"] == 100
        assert result["height"] == 100

    def test_fusion_recipe_exists(self, setup):
        """Fusion recipes should be importable."""
        from lidar_relief.fusion.sentinel_fusion import FUSION_RECIPES

        assert len(FUSION_RECIPES) >= 3
        assert "terrain_cir" in FUSION_RECIPES
        assert "crop_marks" in FUSION_RECIPES

    def test_apply_fusion(self, setup):
        """Applying a fusion recipe should produce an RGB output."""
        from lidar_relief.fusion.sentinel_fusion import (
            apply_fusion_recipe,
            FUSION_RECIPES,
        )

        rows = cols = 100
        # Create LiDAR relief
        lidar = np.random.default_rng(42).random((rows, cols)).astype(np.float32) * 255
        lidar_path = os.path.join(setup, "lidar.tif")
        _create_raster(lidar_path, lidar)

        # Create simulated S2 bands
        s2_paths = {}
        for band in FUSION_RECIPES["terrain_cir"]["s2_bands"]:
            data = (
                np.random.default_rng(abs(hash(band)) + 1)
                .random((rows, cols))
                .astype(np.float32)
            )
            path = os.path.join(setup, f"s2_{band}.tif")
            _create_raster(path, data)
            s2_paths[band] = path

        output_path = os.path.join(setup, "fusion.tif")
        result = apply_fusion_recipe(lidar_path, s2_paths, "terrain_cir", output_path)

        assert os.path.exists(output_path)
        assert result["recipe"] == "terrain_cir"
        assert result["blend_mode"] == "luminance_overlay"

        # Verify RGB output (3 bands, uint8)
        ds = gdal.Open(output_path)
        assert ds.RasterCount == 3
        band = ds.GetRasterBand(1)
        data = band.ReadAsArray()
        assert data.dtype == np.uint8

    def test_unknown_recipe(self, setup):
        """Unknown recipe should raise ValueError."""
        from lidar_relief.fusion.sentinel_fusion import apply_fusion_recipe

        with pytest.raises(ValueError, match="Unknown fusion recipe"):
            out_path = os.path.join(setup, "out.tif")
            apply_fusion_recipe("nonexistent.tif", {}, "fake_recipe", out_path)

    def test_missing_band(self, setup):
        """Missing required bands should raise ValueError."""
        from lidar_relief.fusion.sentinel_fusion import apply_fusion_recipe

        lidar = np.ones((50, 50), dtype=np.float32)
        lidar_path = os.path.join(setup, "lidar.tif")
        _create_raster(lidar_path, lidar)

        with pytest.raises(ValueError, match="Missing band"):
            out_path = os.path.join(setup, "out2.tif")
            apply_fusion_recipe(lidar_path, {}, "terrain_cir", out_path)
