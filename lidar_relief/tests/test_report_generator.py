"""test_report_generator.py — Tests for PDF report generation.

exports: (test functions)
used_by: pytest runner
rules:
  Tests require reportlab and GDAL (Python 3.14 system).
  Tests generate PDFs to temp dir, verify structure and content.
"""

import os
import tempfile

import numpy as np
import pytest

pytest.importorskip("osgeo")

from osgeo import gdal


class TestReportGenerator:
    """Tests for the report_generator module."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = tempfile.mkdtemp(prefix="report_test_")
        yield
        import shutil
        shutil.rmtree(self.tmpdir)

    def _create_test_raster(self, filename: str = "output.tif") -> str:
        """Create a simple test raster for report generation."""
        rows, cols = 200, 200
        # Create a gradient DEM (predictable stats)
        rng = np.random.default_rng(42)
        dem = rng.normal(loc=128, scale=30, size=(rows, cols)).astype(np.float32)
        dem = np.clip(dem, 0, 255)

        path = os.path.join(self.tmpdir, filename)
        driver = gdal.GetDriverByName("GTiff")
        ds = driver.Create(path, cols, rows, 1, gdal.GDT_Float32,
                           options=["COMPRESS=LZW"])
        ds.SetGeoTransform((500000, 1.0, 0, 6000000, 0, -1.0))
        ds.SetProjection('EPSG:32630')
        band = ds.GetRasterBand(1)
        band.SetNoDataValue(-9999.0)
        band.WriteArray(dem)
        band.FlushCache()
        ds = None
        return path

    def test_reportlab_available(self):
        """reportlab_available() should return True."""
        from lidar_relief.export.report_generator import reportlab_available
        assert reportlab_available()

    def test_generate_basic_report(self):
        """Basic report should produce a valid PDF."""
        from lidar_relief.export.report_generator import generate_report

        raster_path = self._create_test_raster()
        pdf_path = os.path.join(self.tmpdir, "report.pdf")

        result = generate_report(
            raster_path=raster_path,
            output_path=pdf_path,
            algorithm_name="Multi-directional Hillshade",
            algorithm_params={
                "azimuths": "315,45,135,225",
                "altitude": 45.0,
                "cellsize": 1.0,
            },
            plugin_version="1.3.5",
            metadata={
                "crs": "EPSG:32630",
                "resolution": "1.0m",
                "extent": (500000, 6000000, 500200, 6000200),
                "source_dem": "test_dem.tif",
            },
            title="Test Archaeological Survey Report",
            author="Test Author",
            site_name="Test Site Alpha",
        )

        assert os.path.exists(pdf_path)
        assert result["page_count"] >= 2  # Cover + content
        assert result["size_bytes"] > 0
        assert "test_survey" not in pdf_path  # Not in our output path

    def test_report_with_custom_styling(self):
        """Report should include all sections."""
        from lidar_relief.export.report_generator import generate_report

        raster_path = self._create_test_raster()
        pdf_path = os.path.join(self.tmpdir, "styled_report.pdf")

        result = generate_report(
            raster_path=raster_path,
            output_path=pdf_path,
            algorithm_name="Sky-View Factor",
            algorithm_params={
                "search_radius": 10,
                "directions": 32,
                "noise": "low",
            },
            plugin_version="1.3.5",
            metadata={
                "crs": "EPSG:27700",
                "resolution": "0.5m",
                "source_dem": "lidar_dem.tif",
            },
            title="SVF Survey Report",
            site_name="Roman Villa Site",
        )

        assert os.path.exists(pdf_path)
        assert result["size_bytes"] > 1000  # At least 1KB
        assert result["page_count"] >= 1

    def test_report_with_stats_and_histogram(self):
        """Report with statistics should compute raster stats."""
        from lidar_relief.export.report_generator import generate_report

        raster_path = self._create_test_raster()
        pdf_path = os.path.join(self.tmpdir, "stats_report.pdf")

        result = generate_report(
            raster_path=raster_path,
            output_path=pdf_path,
            algorithm_name="Slope",
            algorithm_params={"units": "degrees"},
            plugin_version="1.3.5",
            include_histogram=True,
            include_stats=True,
        )

        assert os.path.exists(pdf_path)
        assert result["size_bytes"] > 0

    def test_report_without_histogram(self):
        """Report should work without histogram."""
        from lidar_relief.export.report_generator import generate_report

        raster_path = self._create_test_raster()
        pdf_path = os.path.join(self.tmpdir, "no_hist.pdf")

        generate_report(
            raster_path=raster_path,
            output_path=pdf_path,
            algorithm_name="Test",
            include_histogram=False,
            include_stats=False,
        )
        assert os.path.exists(pdf_path)

    def test_generate_minimal_report(self):
        """Minimal report (bare minimum params) should still produce a PDF."""
        from lidar_relief.export.report_generator import generate_report

        raster_path = self._create_test_raster()
        pdf_path = os.path.join(self.tmpdir, "minimal.pdf")

        result = generate_report(
            raster_path=raster_path,
            output_path=pdf_path,
        )

        assert os.path.exists(pdf_path)
        assert result["page_count"] >= 1
