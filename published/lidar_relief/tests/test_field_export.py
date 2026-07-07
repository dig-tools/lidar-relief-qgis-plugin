"""test_field_export.py — Tests for Field Survey Export (GeoPackage + QField).

exports: (test functions)
used_by: pytest runner
rules:
  Tests use GDAL to create/verify GeoPackage structure.
  Tests do NOT require QGIS.
"""

import os
import tempfile

import pytest

pytest.importorskip("osgeo")

from osgeo import ogr  # noqa: E402


class TestFieldPackager:
    """Tests for the field_packager module."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.tmpdir = tempfile.mkdtemp(prefix="field_test_")
        yield
        import shutil

        shutil.rmtree(self.tmpdir)

    def _geopackage_has_layer(self, path: str, layer_name: str) -> bool:
        """Check if a GeoPackage contains a specific layer."""
        ds = ogr.Open(path)
        if ds is None:
            return False
        layer = ds.GetLayerByName(layer_name)
        exists = layer is not None
        ds = None
        return exists

    def _geopackage_has_fields(
        self, path: str, layer_name: str, expected_fields: list
    ) -> dict:
        """Check if a GeoPackage layer has the expected fields."""
        ds = ogr.Open(path)
        layer = ds.GetLayerByName(layer_name)
        if layer is None:
            ds = None
            return {}

        layer_defn = layer.GetLayerDefn()
        actual_fields = {}
        for i in range(layer_defn.GetFieldCount()):
            fdef = layer_defn.GetFieldDefn(i)
            actual_fields[fdef.GetName()] = fdef.GetTypeName()

        ds = None
        return actual_fields

    def test_create_anomaly_template(self):
        """Creating an anomaly template should produce a valid GeoPackage."""
        from lidar_relief.export.field_packager import create_anomaly_template

        gpkg_path = os.path.join(self.tmpdir, "template.gpkg")
        result = create_anomaly_template(gpkg_path)

        assert result == gpkg_path
        assert os.path.exists(gpkg_path)
        assert self._geopackage_has_layer(gpkg_path, "anomalies")

    def test_template_has_all_schema_fields(self):
        """The anomaly template should have all expected schema fields."""
        from lidar_relief.export.field_packager import (
            create_anomaly_template,
            ANOMALY_SCHEMA,
        )

        gpkg_path = os.path.join(self.tmpdir, "template.gpkg")
        create_anomaly_template(gpkg_path)

        fields = self._geopackage_has_fields(
            gpkg_path, "anomalies", list(ANOMALY_SCHEMA.keys())
        )
        for field_name in ANOMALY_SCHEMA:
            assert field_name in fields, f"Missing field: {field_name}"

    def test_package_with_points(self):
        """Packaging with anomaly points should create valid outputs."""
        from lidar_relief.export.field_packager import package_for_qfield

        # Create a dummy raster file
        raster_path = os.path.join(self.tmpdir, "relief.tif")
        with open(raster_path, "w") as f:
            f.write("dummy")

        anomaly_points = [
            {
                "x": -1.5,
                "y": 52.0,
                "anomaly_id": "ANOM-001",
                "detection_method": "svf",
                "confidence": 0.85,
                "feature_type": "barrow",
            },
            {
                "x": -1.51,
                "y": 52.01,
                "anomaly_id": "ANOM-002",
                "detection_method": "hillshade",
                "confidence": 0.7,
                "feature_type": "ditch",
            },
        ]

        output_dir = os.path.join(self.tmpdir, "survey_package")
        result = package_for_qfield(
            raster_path=raster_path,
            anomaly_points=anomaly_points,
            output_dir=output_dir,
            project_name="Test Survey",
        )

        assert os.path.exists(result["gpkg"])
        assert os.path.exists(result["qgs"])
        assert os.path.exists(result["raster"])
        assert result["anomaly_count"] == 2

    def test_package_empty_points(self):
        """Packaging with empty points should still create template."""
        from lidar_relief.export.field_packager import package_for_qfield

        raster_path = os.path.join(self.tmpdir, "relief.tif")
        with open(raster_path, "w") as f:
            f.write("dummy")

        output_dir = os.path.join(self.tmpdir, "empty_survey")
        result = package_for_qfield(
            raster_path=raster_path,
            anomaly_points=[],
            output_dir=output_dir,
            project_name="Empty Survey",
        )

        assert os.path.exists(result["gpkg"])
        assert os.path.exists(result["qgs"])
        assert result["anomaly_count"] == 0

    def test_package_qgs_project_xml(self):
        """The QGS project file should contain expected XML elements."""
        from lidar_relief.export.field_packager import package_for_qfield

        raster_path = os.path.join(self.tmpdir, "relief.tif")
        with open(raster_path, "w") as f:
            f.write("dummy")

        output_dir = os.path.join(self.tmpdir, "xml_test")
        result = package_for_qfield(
            raster_path=raster_path,
            anomaly_points=[],
            output_dir=output_dir,
            project_name="XML Test",
        )

        with open(result["qgs"]) as f:
            content = f.read()

        assert "<qgis" in content
        assert "relief_visualization" in content
        assert "anomalies" in content
        assert "fieldStatus" in content or "field_status" in content
