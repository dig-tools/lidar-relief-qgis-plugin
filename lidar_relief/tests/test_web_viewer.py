import os
import pytest

# Web viewer tests require rasterio to build the test fixture COG.
# Without this guard the entire module would crash during collection
# if rasterio isn't installed (rather than skipping cleanly).
pytest.importorskip("rasterio")

from lidar_relief.export.cog_exporter import validate_cog
from lidar_relief.export.web_viewer import generate_web_viewer
import rasterio
from rasterio.transform import from_origin
import numpy as np


@pytest.fixture
def dummy_cog(tmp_path):
    """Creates a minimal dummy COG for testing."""
    cog_path = tmp_path / "dummy_cog.tif"
    data = np.zeros((10, 10), dtype=np.uint8)
    transform = from_origin(415500.0, 131700.0, 1.0, 1.0)

    with rasterio.open(
        cog_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=data.dtype,
        crs="EPSG:27700",
        transform=transform,
        tiled=True,
        blockxsize=256,
        blockysize=256,
        compress="lzw",
    ) as dst:
        dst.write(data, 1)
        # Write some overviews to simulate a COG
        dst.build_overviews([2, 4], rasterio.enums.Resampling.average)
        dst.update_tags(ns="rio_overview", resampling="average")

    return str(cog_path)


def test_validate_cog(dummy_cog):
    """Test COG validation on a valid file."""
    result = validate_cog(dummy_cog)
    assert result.get("valid") is True


def test_validate_cog_invalid(tmp_path):
    """Test COG validation on an invalid file."""
    invalid_path = tmp_path / "invalid.tif"
    # Create a simple non-tiled GTiff
    data = np.zeros((10, 10), dtype=np.uint8)
    transform = from_origin(415500.0, 131700.0, 1.0, 1.0)
    with rasterio.open(
        invalid_path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype=data.dtype,
        crs="EPSG:27700",
        transform=transform,
    ) as dst:
        dst.write(data, 1)

    result = validate_cog(str(invalid_path))
    assert result.get("valid") is False
    assert result.get("tiled") is False


def test_generate_web_viewer(dummy_cog, tmp_path):
    """Test generating the web viewer HTML and config."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Generate viewer
    result = generate_web_viewer(
        cog_path=dummy_cog,
        output_dir=str(output_dir),
        title="Test Viewer",
        description="Test Description",
        zoom=10.0,
        dark_mode=True,
        opacity=0.8,
    )

    html_path = result["index_html"]
    config_path = result["config_json"]

    assert os.path.exists(html_path)
    assert os.path.exists(config_path)

    # Check HTML contents
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        assert "Test Viewer" in html
        assert "Test Description" in html
        assert "dummy_cog.tif" in html
        assert "maplibregl.addProtocol('cog'" in html
