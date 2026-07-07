"""test_recipes.py — Tests for Visualization Recipes (JSON import/export).

exports: (test functions)
used_by: pytest runner
rules:
  Pure Python — no GDAL or QGIS required.
  Tests cover serialization, deserialization, validation, round-trips.
"""

import json
import pytest

from lidar_relief.recipes import (
    export_recipe,
    import_recipe,
    validate_recipe,
    recipe_to_presets,
    get_recipe_schema,
)
from lidar_relief.version import get_version


class TestRecipeExport:
    """Tests for export_recipe."""

    def test_export_minimal(self):
        """Minimal export should produce valid JSON."""
        algorithms = {"svf": {"search_radius": 10, "num_directions": 16}}
        json_str = export_recipe(algorithms=algorithms)
        data = json.loads(json_str)
        assert data["recipe_version"] == "1.0.0"
        assert data["algorithms"] == algorithms
        assert "created" in data

    def test_export_with_all_metadata(self):
        """Export with metadata should include all fields."""
        algorithms = {
            "svf": {"search_radius": 20, "num_directions": 32, "noise_level": 1},
            "slrm": {"trend_radius": 20},
        }
        json_str = export_recipe(
            algorithms=algorithms,
            name="Barrow Detection - Wiltshire",
            author="test@example.com",
            description="Optimized for round barrows on chalk downland",
            landscape_type="upland_steep",
            tags=["barrows", "chalk", "wiltshire"],
            batch_preset="upland_steep",
            output_crs="EPSG:27700",
            plugin_version=get_version(),
        )
        data = json.loads(json_str)
        assert data["name"] == "Barrow Detection - Wiltshire"
        assert data["author"] == "test@example.com"
        assert data["landscape_type"] == "upland_steep"
        assert data["tags"] == ["barrows", "chalk", "wiltshire"]
        assert data["output_crs"] == "EPSG:27700"
        assert data["plugin_version"] == get_version()

    def test_export_pretty_print(self):
        """Exported JSON should be pretty-printed."""
        json_str = export_recipe(algorithms={"svf": {"radius": 10}})
        # Pretty-printed JSON has newlines
        assert "\n" in json_str
        assert "  " in json_str


class TestRecipeImport:
    """Tests for import_recipe."""

    def test_import_valid(self):
        """Valid JSON should be imported successfully."""
        json_str = json.dumps(
            {
                "recipe_version": "1.0.0",
                "plugin_version": get_version(),
                "name": "Test Recipe",
                "algorithms": {
                    "svf": {"search_radius": 10, "num_directions": 16},
                },
            }
        )
        data = import_recipe(json_str)
        assert data["name"] == "Test Recipe"
        assert data["algorithms"]["svf"]["search_radius"] == 10

    def test_import_invalid_json(self):
        """Malformed JSON should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            import_recipe("{bad json}")

    def test_import_missing_required(self):
        """Missing required fields should raise ValueError."""
        json_str = json.dumps({"name": "No algorithms"})
        with pytest.raises(ValueError, match="Invalid recipe"):
            import_recipe(json_str)

    def test_import_bad_version_format(self):
        """Invalid version format should raise ValueError."""
        json_str = json.dumps(
            {
                "recipe_version": "bad",
                "plugin_version": "1.0.0",
                "algorithms": {"svf": {"radius": 10}},
            }
        )
        with pytest.raises(ValueError, match="Invalid recipe"):
            import_recipe(json_str)

    def test_import_unknown_algorithm(self):
        """Unknown algorithms should not cause validation errors."""
        json_str = json.dumps(
            {
                "recipe_version": "1.0.0",
                "plugin_version": "1.0.0",
                "algorithms": {
                    "future_algo": {"param": 42},
                    "svf": {"search_radius": 10},
                },
            }
        )
        # Should succeed with just a warning
        data = import_recipe(json_str)
        assert "svf" in data["algorithms"]


class TestRecipeValidation:
    """Tests for validate_recipe."""

    def test_valid_recipe_no_errors(self):
        """A valid recipe should have no errors."""
        data = {
            "recipe_version": "1.0.0",
            "plugin_version": get_version(),
            "algorithms": {
                "svf": {"search_radius": 10, "num_directions": 16},
                "hillshade": {"azimuths": "315,45", "altitude": 45.0},
            },
        }
        errors = validate_recipe(data)
        assert errors == []

    def test_missing_algorithms(self):
        """Missing algorithms field should produce an error."""
        errors = validate_recipe({"recipe_version": "1.0.0"})
        assert any("algorithms" in e for e in errors)

    def test_wrong_param_type(self):
        """Wrong parameter types should produce errors."""
        data = {
            "recipe_version": "1.0.0",
            "plugin_version": "1.0.0",
            "algorithms": {
                "svf": {"search_radius": "not_a_number"},
            },
        }
        errors = validate_recipe(data)
        assert any("search_radius" in e for e in errors)

    def test_invalid_landscape_type(self):
        """Unknown landscape_type should produce an error."""
        data = {
            "recipe_version": "1.0.0",
            "plugin_version": "1.0.0",
            "algorithms": {},
            "landscape_type": "mars_crater",
        }
        errors = validate_recipe(data)
        assert any("landscape_type" in e for e in errors)


class TestRecipeRoundTrip:
    """Tests for export → import round-trips."""

    def test_round_trip_basic(self):
        """Export then import should preserve all parameters."""
        original_algorithms = {
            "svf": {"search_radius": 15, "num_directions": 32, "noise_level": 2},
            "hillshade": {"azimuths": "315,45,135,225", "altitude": 35.0},
            "slrm": {"trend_radius": 15},
        }
        json_str = export_recipe(
            algorithms=original_algorithms,
            name="Forest Optimization",
            author="forest@example.com",
            landscape_type="forested",
            tags=["forest", "canopy"],
        )
        data = import_recipe(json_str)
        assert data["algorithms"] == original_algorithms
        assert data["name"] == "Forest Optimization"

    def test_round_trip_to_presets(self):
        """Recipe should convert to presets format."""
        json_str = export_recipe(
            algorithms={
                "svf": {"search_radius": 20, "num_directions": 16},
                "slrm": {"trend_radius": 20},
            },
            name="Flat Ag",
            landscape_type="flat_agricultural",
        )
        data = import_recipe(json_str)
        presets = recipe_to_presets(data)
        assert "svf" in presets
        assert presets["svf"]["search_radius"] == 20


class TestRecipeSchema:
    """Tests for get_recipe_schema."""

    def test_schema_exists(self):
        """Schema should be a dict with required fields."""
        schema = get_recipe_schema()
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "required" in schema
        assert "recipe_version" in schema["required"]
        assert "algorithms" in schema["required"]
