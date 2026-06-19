"""test_pdal_pipeline.py — Tests for PDAL ground classification pipelines.

exports: (test functions)
used_by: pytest runner
rules:
  Tests verify pipeline JSON construction and validation.
  Full execution tests require PDAL to be installed (skipped if not).
"""

import json
import os
import tempfile

import pytest

from lidar_relief.point_cloud.pdal_pipeline import (
    pdal_available,
    build_pipeline,
    ARCHAEOLOGY_PIPELINES,
)

_TMP_LAS = os.path.join(tempfile.gettempdir(), "test_pdal.las")
_TMP_TIF = os.path.join(tempfile.gettempdir(), "test_pdal.tif")


class TestPDALPipeline:
    """Tests for PDAL pipeline construction."""

    def test_pdal_available(self):
        """Check if PDAL is available (informational)."""
        pass

    def test_pipelines_defined(self):
        """All expected pipeline presets should exist."""
        expected = {
            "pmf_archaeology_fine",
            "pmf_archaeology_standard",
            "pmf_forested",
            "outlier_removal",
        }
        assert expected.issubset(ARCHAEOLOGY_PIPELINES.keys())

    def test_pipeline_has_required_keys(self):
        """Each pipeline should have name, description, and pipeline."""
        for name, preset in ARCHAEOLOGY_PIPELINES.items():
            assert "name" in preset, f"Pipeline '{name}' missing 'name'"
            assert "description" in preset, f"Pipeline '{name}' missing 'description'"
            assert "pipeline" in preset, f"Pipeline '{name}' missing 'pipeline'"
            assert len(preset["pipeline"]) >= 2, (
                f"Pipeline '{name}' needs at least 2 stages"
            )

    def test_build_pipeline_json(self):
        """build_pipeline should produce valid JSON with correct stages."""
        if not pdal_available():
            pytest.skip("PDAL not installed")

        pipeline_json = build_pipeline(
            las_path=_TMP_LAS,
            output_path=_TMP_TIF,
            preset="pmf_archaeology_standard",
        )
        data = json.loads(pipeline_json)
        assert "pipeline" in data
        stages = data["pipeline"]
        assert len(stages) >= 2
        assert stages[0]["filename"] == _TMP_LAS

    def test_build_with_custom_resolution(self):
        """Custom resolution should be applied to GDAL writer."""
        if not pdal_available():
            pytest.skip("PDAL not installed")

        pipeline_json = build_pipeline(
            las_path=_TMP_LAS,
            output_path=_TMP_TIF,
            preset="pmf_archaeology_fine",
            resolution=0.5,
        )
        data = json.loads(pipeline_json)
        last_stage = data["pipeline"][-1]
        if last_stage.get("type") == "writers.gdal":
            assert last_stage["resolution"] == 0.5

    def test_unknown_preset_raises(self):
        """Unknown preset should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown pipeline preset"):
            build_pipeline(
                las_path=_TMP_LAS,
                output_path=_TMP_TIF,
                preset="nonexistent",
            )

    def test_pipeline_preset_has_valid_stages(self):
        """Each pipeline stage should have a valid type."""
        for name, preset in ARCHAEOLOGY_PIPELINES.items():
            for i, stage in enumerate(preset["pipeline"]):
                assert "type" in stage, f"Pipeline '{name}' stage {i} missing 'type'"
                type_str = stage["type"]
                assert type_str.startswith(("readers.", "filters.", "writers.")), (
                    f"Pipeline '{name}' stage {i}: invalid type '{type_str}'"
                )

    def test_outlier_removal_structure(self):
        """Outlier removal pipeline should have correct structure."""
        preset = ARCHAEOLOGY_PIPELINES["outlier_removal"]
        stages = preset["pipeline"]
        assert stages[0]["type"] == "readers.las"
        assert stages[1]["type"] == "filters.outlier"
        assert stages[1]["method"] == "statistical"
        assert "mean_k" in stages[1]
        assert "multiplier" in stages[1]
