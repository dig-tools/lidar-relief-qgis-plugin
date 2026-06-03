"""pdal_pipeline.py — PDAL-based ground classification pipelines for archaeology.

exports: pdal_available() -> bool,
         build_archaeology_pipeline(las_path, output_path, preset, **kwargs) -> str,
         run_pipeline(pipeline_json) -> dict,
         ARCHAEOLOGY_PIPELINES

used_by: algorithms/pdal_classify_algorithm.py

rules:
  Uses PDAL Python bindings for point cloud processing.
  All pipelines use a JSON configuration format.
  Archaeology presets tuned for micro-relief preservation.
"""

import json
import logging

logger = logging.getLogger(__name__)

try:
    import pdal

    _PDAL_AVAILABLE = True
except ImportError:
    _PDAL_AVAILABLE = False

# Archaeology-tuned PDAL pipeline definitions
# Each pipeline is a list of PDAL stage objects in JSON format
ARCHAEOLOGY_PIPELINES = {
    "pmf_archaeology_fine": {
        "name": "PMF — Archaeology Fine",
        "description": "Progressive Morphological Filter with very low "
        "thresholds for maximum micro-relief preservation.",
        "pipeline": [
            {"type": "readers.las"},
            {
                "type": "filters.pmf",
                "max_window_size": 20,
                "slope": 0.15,
                "max_distance": 0.5,
                "initial_distance": 0.15,
                "cell_size": 0.5,
            },
            {"type": "filters.ferry", "dimensions": "Classification=>UserData"},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "writers.gdal", "output_type": "idw", "resolution": 1.0},
        ],
    },
    "pmf_archaeology_standard": {
        "name": "PMF — Archaeology Standard",
        "description": "Balanced vegetation removal and earthwork "
        "preservation for most survey contexts.",
        "pipeline": [
            {"type": "readers.las"},
            {
                "type": "filters.pmf",
                "max_window_size": 33,
                "slope": 0.25,
                "max_distance": 1.0,
                "initial_distance": 0.3,
                "cell_size": 1.0,
            },
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "writers.gdal", "output_type": "idw", "resolution": 1.0},
        ],
    },
    "pmf_forested": {
        "name": "PMF — Forested",
        "description": "Aggressive ground detection for dense canopy. "
        "May remove subtle archaeological features.",
        "pipeline": [
            {"type": "readers.las"},
            {
                "type": "filters.pmf",
                "max_window_size": 50,
                "slope": 0.5,
                "max_distance": 2.0,
                "initial_distance": 0.5,
                "cell_size": 2.0,
            },
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "writers.gdal", "output_type": "idw", "resolution": 1.0},
        ],
    },
    "outlier_removal": {
        "name": "Statistical Outlier Removal",
        "description": "Pre-processing step: remove isolated noise "
        "points before ground filtering.",
        "pipeline": [
            {"type": "readers.las"},
            {
                "type": "filters.outlier",
                "method": "statistical",
                "mean_k": 8,
                "multiplier": 2.0,
            },
            {"type": "filters.range", "limits": "Classification[1:1]"},
            {"type": "writers.las"},
        ],
    },
}


def pdal_available() -> bool:
    """Check if PDAL Python bindings are installed."""
    return _PDAL_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError with clear instructions if PDAL missing."""
    if not _PDAL_AVAILABLE:
        raise ImportError(
            "PDAL ground classification requires the 'pdal' Python "
            "package.\n\nInstall it via the OSGeo4W Shell:\n"
            "  pip install pdal\n\n"
            "PDAL also needs to be installed on your system."
        )


def build_pipeline(
    las_path: str,
    output_path: str,
    preset: str = "pmf_archaeology_standard",
    resolution: float = 1.0,
    output_format: str = "gdal",
) -> str:
    """Build a complete PDAL pipeline JSON string for ground classification.

    Args:
        las_path: Input LAS/LAZ file path.
        output_path: Output file path (GeoTIFF or LAS).
        preset: Pipeline preset name from ARCHAEOLOGY_PIPELINES.
        resolution: Output DEM resolution (for GDAL writers).
        output_format: Output format ('gdal' for DEM, 'las' for
            classified point cloud).

    Returns:
        JSON string of the complete PDAL pipeline.
    """
    if preset not in ARCHAEOLOGY_PIPELINES:
        raise ValueError(
            f"Unknown pipeline preset '{preset}'. "
            f"Available: {list(ARCHAEOLOGY_PIPELINES.keys())}"
        )

    check_dependencies()

    preset_def = ARCHAEOLOGY_PIPELINES[preset]
    pipeline = json.loads(json.dumps(preset_def["pipeline"]))

    # Set input file
    pipeline[0]["filename"] = las_path

    # Update output
    last_stage = pipeline[-1]
    last_stage["filename"] = output_path

    # Update resolution for GDAL writers
    if output_format == "gdal" and last_stage.get("type") == "writers.gdal":
        last_stage["resolution"] = resolution

    # Update output type for last stage
    if last_stage.get("type") == "writers.las":
        last_stage["filename"] = output_path
    elif last_stage.get("type") == "writers.gdal":
        last_stage["filename"] = output_path

    return json.dumps({"pipeline": pipeline}, indent=2)


def run_pipeline(pipeline_json: str, feedback=None) -> dict:
    """Execute a PDAL pipeline and return metadata.

    Args:
        pipeline_json: JSON string of the PDAL pipeline.
        feedback: Optional progress callback.

    Returns:
        dict with pipeline metadata (point count, stages, etc.).

    Raises:
        RuntimeError: If pipeline execution fails.
    """
    check_dependencies()

    try:
        pipeline_data = json.loads(pipeline_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid pipeline JSON: {e}") from e

    if feedback:
        feedback.setProgressText("Executing PDAL pipeline...")

    try:
        pdal_pipeline = pdal.Pipeline(json.dumps(pipeline_data))
        metadata = pdal_pipeline.execute()
    except Exception as e:
        raise RuntimeError(f"PDAL pipeline failed: {e}") from e

    if feedback:
        feedback.setProgressText("PDAL pipeline complete.")

    # Extract basic metadata from the pipeline
    stage_count = len(pipeline_data.get("pipeline", []))
    point_count = metadata.get("num_points", 0) if isinstance(metadata, dict) else 0

    return {
        "point_count": point_count,
        "stage_count": stage_count,
        "preset": pipeline_data.get("pipeline", [{}])[0].get("type", "unknown"),
    }
