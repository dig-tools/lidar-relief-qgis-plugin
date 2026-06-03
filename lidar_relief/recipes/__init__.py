"""recipes — Visualization Recipe import/export for parameter sharing.

exports: RecipeFormat, export_recipe(params, **metadata) -> str,
         import_recipe(json_str) -> dict, validate_recipe(data) -> list,
         get_recipe_schema() -> dict

used_by: algorithms/recipe_io_algorithm.py, batch_algorithm dialog,
         user community for sharing optimized presets

rules:
  Pure Python stdlib — no external dependencies.
  JSON-based serialization for human readability and GitHub Gist sharing.
  Semver-based schema versioning for forward compatibility.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Current recipe schema version
RECIPE_VERSION = "1.0.0"

# Algorithms known to the plugin with their parameter definitions
ALGORITHM_DEFINITIONS = {
    "hillshade": {
        "display_name": "Multi-directional Hillshade",
        "params": {
            "azimuths": {"type": "string", "default": "315,45,135,225,270,360"},
            "altitude": {"type": "float", "default": 45.0, "min": 0, "max": 90},
        },
    },
    "slrm": {
        "display_name": "Simple Local Relief Model",
        "params": {
            "trend_radius": {"type": "int", "default": 20, "min": 1, "max": 500},
        },
    },
    "svf": {
        "display_name": "Sky-View Factor",
        "params": {
            "search_radius": {"type": "int", "default": 10, "min": 1, "max": 200},
            "num_directions": {
                "type": "int", "default": 16, "min": 4, "max": 64
            },
            "noise_level": {"type": "int", "default": 0, "min": 0, "max": 3},
        },
    },
    "slope": {
        "display_name": "Slope",
        "params": {
            "units": {"type": "string", "default": "degrees"},
        },
    },
    "openness": {
        "display_name": "Topographic Openness",
        "params": {
            "search_radius": {"type": "int", "default": 10, "min": 1, "max": 200},
            "num_directions": {"type": "int", "default": 16, "min": 4, "max": 64},
        },
    },
    "mstp": {
        "display_name": "Multi-Scale Topographic Position",
        "params": {
            "local_radius": {"type": "int", "default": 5, "min": 1, "max": 100},
            "meso_radius": {"type": "int", "default": 50, "min": 1, "max": 1000},
            "broad_radius": {"type": "int", "default": 500, "min": 1, "max": 5000},
        },
    },
    "local_dominance": {
        "display_name": "Local Dominance",
        "params": {
            "min_radius": {"type": "int", "default": 5, "min": 1, "max": 100},
            "max_radius": {"type": "int", "default": 20, "min": 1, "max": 500},
            "observer_height": {"type": "float", "default": 1.7, "min": 0.1},
        },
    },
    "asvf": {
        "display_name": "Anisotropic Sky-View Factor",
        "params": {
            "search_radius": {"type": "int", "default": 10, "min": 1, "max": 200},
            "num_directions": {"type": "int", "default": 16, "min": 4, "max": 64},
            "azimuth": {"type": "float", "default": 315.0, "min": 0, "max": 360},
            "anisotropy": {"type": "float", "default": 1.0, "min": 0.1},
        },
    },
    "e4mstp": {
        "display_name": "Enhanced 4-Scale Topographic Position",
        "params": {},
    },
    "pca": {
        "display_name": "PCA RGB Composite",
        "params": {
            "num_directions": {"type": "int", "default": 16, "min": 4, "max": 64},
        },
    },
    "vat": {
        "display_name": "VAT Composite",
        "params": {},
    },
    "red_relief": {
        "display_name": "Simple Red Relief",
        "params": {},
    },
    "blend": {
        "display_name": "Blend Visualizations",
        "params": {
            "mode": {"type": "string", "default": "multiply"},
        },
    },
}

# Terrain contexts matching presets.py
TERRAIN_CONTEXTS = [
    "flat_agricultural",
    "forested",
    "upland_steep",
    "coastal",
    "custom",
]

# Recipe JSON schema (as a dict for documentation and validation)
RECIPE_SCHEMA = {
    "type": "object",
    "required": ["recipe_version", "plugin_version", "algorithms"],
    "properties": {
        "recipe_version": {"type": "string", "description": "Schema version"},
        "plugin_version": {"type": "string", "description": "Plugin version used"},
        "name": {"type": "string", "description": "Human-readable recipe name"},
        "author": {"type": "string", "description": "Recipe author"},
        "description": {"type": "string", "description": "Usage context description"},
        "landscape_type": {
            "type": "string",
            "enum": TERRAIN_CONTEXTS,
            "description": "Terrain context",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Searchable tags",
        },
        "algorithms": {
            "type": "object",
            "description": "Algorithm parameters keyed by algorithm name",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                },
                "additionalProperties": {"type": ["number", "string", "boolean"]},
            },
        },
        "batch_preset": {
            "type": "string",
            "enum": [*TERRAIN_CONTEXTS, ""],
            "description": "Batch mode preset",
        },
        "output_crs": {"type": "string", "description": "Output CRS authority ID"},
        "created": {"type": "string", "description": "ISO 8601 creation timestamp"},
        "updated": {"type": "string", "description": "ISO 8601 update timestamp"},
    },
}


def get_recipe_schema() -> dict:
    """Return the recipe JSON schema for documentation/validation."""
    return RECIPE_SCHEMA


def export_recipe(
    algorithms: dict[str, dict],
    name: str = "",
    author: str = "",
    description: str = "",
    landscape_type: str = "custom",
    tags: Optional[list[str]] = None,
    batch_preset: str = "",
    output_crs: str = "",
    plugin_version: str = "",
) -> str:
    """Serialize algorithm parameters to a JSON recipe string.

    Args:
        algorithms: Dict mapping algorithm name -> parameter dict.
            e.g. {"svf": {"search_radius": 10, "num_directions": 32}}
        name: Human-readable name for this recipe.
        author: Creator name or handle.
        description: Free-text context description.
        landscape_type: One of TERRAIN_CONTEXTS.
        tags: List of searchable tag strings.
        batch_preset: Batch mode preset name.
        output_crs: Output CRS authority ID (e.g. "EPSG:27700").
        plugin_version: Plugin version used to create this recipe.

    Returns:
        Pretty-printed JSON string.
    """
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    recipe = {
        "recipe_version": RECIPE_VERSION,
        "plugin_version": plugin_version,
        "name": name,
        "author": author,
        "description": description,
        "landscape_type": landscape_type,
        "tags": tags or [],
        "algorithms": algorithms,
        "batch_preset": batch_preset,
        "output_crs": output_crs,
        "created": now,
        "updated": now,
    }

    return json.dumps(recipe, indent=2, ensure_ascii=False)


def import_recipe(json_str: str) -> dict:
    """Parse a JSON recipe string and return the parameter dictionary.

    Args:
        json_str: JSON string conforming to the recipe schema.

    Returns:
        Dict with keys: 'algorithms', 'name', 'author', 'description',
        'landscape_type', 'tags', 'batch_preset', 'output_crs',
        'plugin_version', 'recipe_version'.

    Raises:
        ValueError: If the JSON is malformed or invalid.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in recipe: {e}") from e

    # Validate
    errors = validate_recipe(data)
    if errors:
        raise ValueError("Invalid recipe:\n" + "\n".join(f"  - {e}" for e in errors))

    return data


def validate_recipe(data: dict) -> list[str]:
    """Validate a parsed recipe dict against the schema.

    Args:
        data: Parsed recipe dictionary.

    Returns:
        List of validation error strings. Empty list = valid.
    """
    errors = []

    if not isinstance(data, dict):
        return ["Recipe must be a JSON object"]

    # Check required fields
    for field in ["recipe_version", "algorithms"]:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if "recipe_version" in data:
        version = str(data["recipe_version"])
        if not re.match(r"^\d+\.\d+\.\d+$", version):
            errors.append(
                f"Invalid recipe_version '{version}': "
                f"expected semver (e.g. '1.0.0')"
            )

    # Validate algorithms section
    algorithms = data.get("algorithms", {})
    if not isinstance(algorithms, dict):
        errors.append("'algorithms' must be a JSON object")
    else:
        for alg_name, alg_params in algorithms.items():
            if alg_name not in ALGORITHM_DEFINITIONS:
                # Unknown algorithm — warn but don't reject
                logger.warning("Recipe contains unknown algorithm '%s'", alg_name)
                continue

            if not isinstance(alg_params, dict):
                errors.append(f"Parameters for '{alg_name}' must be a JSON object")
                continue

            # Validate parameter types/ranges
            definitions = ALGORITHM_DEFINITIONS.get(alg_name, {}).get("params", {})
            for param_name, param_value in alg_params.items():
                if param_name == "enabled":
                    if not isinstance(param_value, bool):
                        errors.append(
                            f"'{alg_name}.enabled' must be boolean"
                        )
                    continue

                param_def = definitions.get(param_name)
                if param_def is None:
                    # Unknown param — ignore (forward compat)
                    continue

                expected_type = param_def["type"]
                if expected_type == "int":
                    if not isinstance(param_value, int):
                        errors.append(
                            f"'{alg_name}.{param_name}' must be integer, "
                            f"got {type(param_value).__name__}"
                        )
                elif expected_type == "float":
                    if not isinstance(param_value, (int, float)):
                        errors.append(
                            f"'{alg_name}.{param_name}' must be number, "
                            f"got {type(param_value).__name__}"
                        )
                elif expected_type == "string":
                    if not isinstance(param_value, str):
                        errors.append(
                            f"'{alg_name}.{param_name}' must be string, "
                            f"got {type(param_value).__name__}"
                        )

    # Validate landscape_type
    lt = data.get("landscape_type", "")
    if lt and lt not in TERRAIN_CONTEXTS + [""]:
        errors.append(
            f"Unknown landscape_type '{lt}'. "
            f"Valid: {TERRAIN_CONTEXTS}"
        )

    return errors


def recipe_to_presets(recipe_data: dict) -> dict:
    """Convert a recipe dict into the presets format used by core/presets.py.

    Args:
        recipe_data: Dict returned by import_recipe().

    Returns:
        Dict in PRESETS format suitable for get_preset().
    """
    presets = {}
    for alg_name, alg_params in recipe_data.get("algorithms", {}).items():
        if alg_name == "batch_preset":
            continue
        # Convert algorithm params, dropping non-param fields
        params = {
            k: v for k, v in alg_params.items()
            if k != "enabled" and not k.startswith("_")
        }
        if params:
            presets[alg_name] = params
    return presets
