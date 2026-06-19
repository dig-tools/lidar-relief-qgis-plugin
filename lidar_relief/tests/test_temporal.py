"""test_temporal.py — Tests for multi-temporal DEM difference.

exports: (test functions)
used_by: pytest runner
rules:
  Tests use synthetic DEM pairs with known changes.
  Requires xarray and rioxarray.
"""

import os
import tempfile

import numpy as np
import pytest

pytest.importorskip("osgeo")

from osgeo import gdal  # noqa: E402


@pytest.fixture(autouse=True)
def setup():
    tmpdir = tempfile.mkdtemp(prefix="temporal_test_")
    yield tmpdir
    import shutil

    shutil.rmtree(tmpdir)


def _create_dem(path: str, values: np.ndarray, gt=(500000, 1.0, 0, 6000000, 0, -1.0)):
    """Write a DEM GeoTIFF from a numpy array."""
    rows, cols = values.shape
    ds = gdal.GetDriverByName("GTiff").Create(
        path,
        cols,
        rows,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=LZW", "TILED=YES"],
    )
    ds.SetGeoTransform(gt)
    ds.SetProjection("EPSG:32630")
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    band.WriteArray(values)
    band.FlushCache()
    ds = None


class TestTemporalDifference:
    """Tests for multi-temporal change detection."""

    def test_xarray_available(self):
        """xarray should be available."""
        from lidar_relief.temporal.dem_difference import xarray_available

        assert xarray_available()

    def test_identical_dems_no_change(self, setup):
        """Identical DEMs should produce no significant change."""
        tmpdir = setup
        dem = np.ones((100, 100), dtype=np.float32) * 100.0
        old_path = os.path.join(tmpdir, "old.tif")
        new_path = os.path.join(tmpdir, "new.tif")
        _create_dem(old_path, dem)
        _create_dem(new_path, dem)

        from lidar_relief.temporal.dem_difference import compute_dod

        result = compute_dod(
            old_path,
            new_path,
            tmpdir,
            rmse_old=0.1,
            rmse_new=0.1,
        )

        assert result["significant_pixels"] < result["total_pixels"] * 0.05
        assert abs(result["volume_report"]["net_volume_m3"]) < 1.0

    def test_known_mound_added(self, setup):
        """Adding a mound should be detected as fill."""
        tmpdir = setup
        rows = cols = 100
        old_dem = np.ones((rows, cols), dtype=np.float32) * 50.0

        # Add a mound in the new DEM
        new_dem = old_dem.copy()
        cy, cx = rows // 2, cols // 2
        y, x = np.mgrid[0:rows, 0:cols]
        mask = (x - cx) ** 2 + (y - cy) ** 2 < 100
        new_dem[mask] += 2.0  # 2m high mound

        old_path = os.path.join(tmpdir, "old.tif")
        new_path = os.path.join(tmpdir, "new.tif")
        _create_dem(old_path, old_dem)
        _create_dem(new_path, new_dem)

        from lidar_relief.temporal.dem_difference import compute_dod

        result = compute_dod(
            old_path,
            new_path,
            tmpdir,
            rmse_old=0.05,
            rmse_new=0.05,  # Low noise — mound should be significant
        )

        assert result["positive_change_pixels"] > 0
        assert result["volume_report"]["fill_volume_m3"] > 0

    def test_known_pit_dug(self, setup):
        """Digging a pit should be detected as cut."""
        tmpdir = setup
        rows = cols = 100
        old_dem = np.ones((rows, cols), dtype=np.float32) * 50.0

        # Dig a pit in the new DEM
        new_dem = old_dem.copy()
        cy, cx = rows // 2, cols // 2
        y, x = np.mgrid[0:rows, 0:cols]
        mask = (x - cx) ** 2 + (y - cy) ** 2 < 100
        new_dem[mask] -= 1.5  # 1.5m deep pit

        old_path = os.path.join(tmpdir, "old.tif")
        new_path = os.path.join(tmpdir, "new.tif")
        _create_dem(old_path, old_dem)
        _create_dem(new_path, new_dem)

        from lidar_relief.temporal.dem_difference import compute_dod

        result = compute_dod(
            old_path,
            new_path,
            tmpdir,
            rmse_old=0.05,
            rmse_new=0.05,
        )

        assert result["negative_change_pixels"] > 0
        assert result["volume_report"]["cut_volume_m3"] > 0

    def test_output_files_exist(self, setup):
        """Output rasters should be written to disk."""
        tmpdir = setup
        dem = np.ones((50, 50), dtype=np.float32) * 100.0
        old_path = os.path.join(tmpdir, "old.tif")
        new_path = os.path.join(tmpdir, "new.tif")
        _create_dem(old_path, dem)
        _create_dem(
            new_path, dem + np.random.normal(0, 0.01, (50, 50)).astype(np.float32)
        )

        from lidar_relief.temporal.dem_difference import compute_dod

        result = compute_dod(old_path, new_path, tmpdir, rmse_old=0.1, rmse_new=0.1)

        assert os.path.exists(result["dod_path"]), "DoD raster missing"
        assert os.path.exists(result["mask_path"]), "Mask raster missing"

    def test_volume_report_structure(self, setup):
        """Volume report should contain expected keys."""
        tmpdir = setup
        dem = np.ones((50, 50), dtype=np.float32) * 100.0
        old_path = os.path.join(tmpdir, "old.tif")
        new_path = os.path.join(tmpdir, "new.tif")
        _create_dem(old_path, dem)
        _create_dem(new_path, dem)

        from lidar_relief.temporal.dem_difference import compute_dod

        result = compute_dod(old_path, new_path, tmpdir)
        vr = result["volume_report"]

        for key in [
            "cut_volume_m3",
            "fill_volume_m3",
            "net_volume_m3",
            "propagated_error_m",
            "lod_threshold_m",
        ]:
            assert key in vr, f"Missing key: {key}"
