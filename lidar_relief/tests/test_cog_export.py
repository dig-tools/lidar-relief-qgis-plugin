"""test_cog_export.py — Tests for Cloud-Optimized GeoTIFF export.

exports: (test functions)
used_by: pytest runner
rules:
  Tests use synthetic DEMs generated with GDAL.
  Tests verify COG structure, web viewer HTML, and error handling.
  Tests do NOT require QGIS.
"""

import os
import tempfile

import numpy as np
import pytest
from osgeo import gdal

from lidar_relief.export.cog_exporter import (
    cog_is_supported,
    convert_to_cog,
    validate_cog,
)
from lidar_relief.export.web_viewer import generate_web_viewer
from lidar_relief.core.raster_utils import write_array_to_raster


@pytest.fixture
def synthetic_dem_path():
    """Create a 200×200 synthetic DEM for COG testing."""
    rows, cols = 200, 200
    dem = np.random.default_rng(42).random((rows, cols)).astype(np.float32) * 50.0
    tmpdir = tempfile.mkdtemp(prefix="cog_test_")
    path = os.path.join(tmpdir, "dem.tif")
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, cols, rows, 1, gdal.GDT_Float32,
                       options=["COMPRESS=LZW", "TILED=YES"])
    ds.SetGeoTransform((500000, 1.0, 0, 6000000, 0, -1.0))
    ds.SetProjection('EPSG:32630')
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    band.WriteArray(dem)
    band.FlushCache()
    ds = None
    yield path
    # Cleanup
    import shutil
    shutil.rmtree(tmpdir)


@pytest.fixture
def large_dem_path():
    """Create a 2000×2000 DEM for overview testing."""
    rows, cols = 2000, 2000
    cy, cx = rows // 2, cols // 2
    y, x = np.mgrid[0:rows, 0:cols]
    distance = np.sqrt((x - cx)**2 + (y - cy)**2)
    dem = np.maximum(50.0 - distance * 0.15, 0.0).astype(np.float32)
    tmpdir = tempfile.mkdtemp(prefix="cog_large_")
    path = os.path.join(tmpdir, "dem.tif")
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, cols, rows, 1, gdal.GDT_Float32,
                       options=["COMPRESS=LZW", "TILED=YES"])
    ds.SetGeoTransform((500000, 1.0, 0, 6000000, 0, -1.0))
    ds.SetProjection('EPSG:32630')
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    band.WriteArray(dem)
    band.FlushCache()
    ds = None
    yield path
    import shutil
    shutil.rmtree(tmpdir)


class TestCogExporter:
    """Tests for the convert_to_cog function."""

    def test_cog_supported_import(self):
        """cog_is_supported() should return True (rio-cogeo installed)."""
        assert cog_is_supported(), "rio-cogeo should be installed for tests"

    def test_convert_small_raster(self, synthetic_dem_path):
        """A small raster should produce a valid COG (no overviews)."""
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        result = convert_to_cog(synthetic_dem_path, cog_path, profile="deflate")
        assert result["valid"]
        assert result["profile"] == "deflate"
        assert os.path.getsize(cog_path) > 0
        # Validate structure
        validation = validate_cog(cog_path)
        assert validation["valid"]
        assert validation["tiled"] is True

    def test_convert_large_raster(self, large_dem_path):
        """A large raster should produce a COG with overviews."""
        tmpdir = os.path.dirname(large_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        result = convert_to_cog(large_dem_path, cog_path, profile="lzw")
        assert result["valid"]
        validation = validate_cog(cog_path)
        assert validation["overview_count"] >= 1

    def test_convert_with_explicit_nodata(self, synthetic_dem_path):
        """Explicit nodata override should be applied."""
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        result = convert_to_cog(
            synthetic_dem_path, cog_path, profile="deflate", nodata=0.0
        )
        assert result["valid"]

    def test_invalid_profile_fallback(self, synthetic_dem_path):
        """An unknown profile should fall back to 'deflate'."""
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        result = convert_to_cog(synthetic_dem_path, cog_path, profile="nonexistent")
        assert result["valid"]
        assert result["profile"] == "deflate"

    def test_convert_missing_input(self):
        """A missing input file should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="COG conversion failed"):
            convert_to_cog("/nonexistent/path.tif", "/tmp/out.tif")


class TestWebViewer:
    """Tests for the generate_web_viewer function."""

    def test_generates_html_and_config(self, synthetic_dem_path):
        """Web viewer should produce index.html and config.json."""
        # First convert to COG
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        convert_to_cog(synthetic_dem_path, cog_path)

        # Generate web viewer
        viewer_dir = os.path.join(tmpdir, "web_viewer")
        result = generate_web_viewer(
            cog_path=cog_path,
            output_dir=viewer_dir,
            title="Test Viewer",
        )

        assert os.path.exists(result["index_html"])
        assert os.path.exists(result["config_json"])
        assert result["center"] is not None
        assert result["zoom"] is not None

        # Check HTML content
        with open(result["index_html"]) as f:
            html = f.read()
        assert "maplibregl" in html
        assert "cog://" in html
        assert "raster-opacity" in html
        assert "Test Viewer" in html

    def test_dark_mode(self, synthetic_dem_path):
        """Dark mode should use dark base map URL."""
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        convert_to_cog(synthetic_dem_path, cog_path)

        result = generate_web_viewer(
            cog_path=cog_path,
            output_dir=os.path.join(tmpdir, "dark_viewer"),
            dark_mode=True,
        )
        with open(result["index_html"]) as f:
            html = f.read()
        assert "dark_all" in html

    def test_light_mode(self, synthetic_dem_path):
        """Light mode should use light base map URL."""
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        convert_to_cog(synthetic_dem_path, cog_path)

        result = generate_web_viewer(
            cog_path=cog_path,
            output_dir=os.path.join(tmpdir, "light_viewer"),
            dark_mode=False,
        )
        with open(result["index_html"]) as f:
            html = f.read()
        assert "light_all" in html

    def test_custom_opacity(self, synthetic_dem_path):
        """Custom opacity should be reflected in HTML."""
        tmpdir = os.path.dirname(synthetic_dem_path)
        cog_path = os.path.join(tmpdir, "output.tif")
        convert_to_cog(synthetic_dem_path, cog_path)

        result = generate_web_viewer(
            cog_path=cog_path,
            output_dir=os.path.join(tmpdir, "opacity_viewer"),
            opacity=0.5,
        )
        with open(result["index_html"]) as f:
            html = f.read()
        assert 'value="0.5"' in html
