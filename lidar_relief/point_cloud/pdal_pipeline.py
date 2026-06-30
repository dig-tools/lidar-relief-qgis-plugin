"""pdal_pipeline.py — PDAL-based ground classification pipelines for archaeology.

exports: pdal_available() -> bool,
         build_pipeline(las_path, output_path, preset, **kwargs) -> str,
         run_pipeline(pipeline_json) -> dict,
         ARCHAEOLOGY_PIPELINES

used_by: algorithms/pdal_classify_algorithm.py

rules:
  Uses PDAL Python bindings for point cloud processing.
  All pipelines use a JSON configuration format.
  Archaeology presets tuned for micro-relief preservation.
  run_pipeline rejects any stage not in _ALLOWED_PDAL_STAGES — this
  prevents command-injection via filters.shell/filters.exec when
  pipelines are loaded from untrusted recipe files.
"""

import copy
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

    Note:
        Does NOT require PDAL to be installed — pipeline construction
        is pure JSON manipulation. PDAL is only needed by run_pipeline.
        The previous version called check_dependencies() here, which
        prevented JSON-only testing and pre-validation workflows.
    """
    if preset not in ARCHAEOLOGY_PIPELINES:
        raise ValueError(
            f"Unknown pipeline preset '{preset}'. "
            f"Available: {list(ARCHAEOLOGY_PIPELINES.keys())}"
        )

    preset_def = ARCHAEOLOGY_PIPELINES[preset]
    # Use deepcopy instead of json.loads(json.dumps(...)) for clarity
    # and speed (no string serialisation round-trip).
    pipeline = copy.deepcopy(preset_def["pipeline"])

    # Set input file on the reader stage.
    pipeline[0]["filename"] = las_path

    # Configure the writer (last stage) — set output path and, for
    # GDAL writers, the requested resolution. The previous code set
    # `last_stage["filename"]` redundantly three times; we set it once.
    last_stage = pipeline[-1]
    writer_type = last_stage.get("type", "")
    if writer_type in ("writers.gdal", "writers.las", "writers.laz"):
        last_stage["filename"] = output_path
    if writer_type == "writers.gdal" and output_format == "gdal":
        last_stage["resolution"] = resolution

    return json.dumps({"pipeline": pipeline}, indent=2)


# Stages allowed in user-supplied PDAL pipelines. Anything else is
# rejected to prevent command-injection via filters.shell / filters.exec
# when recipes are shared between users. Add new stages here ONLY after
# reviewing their parameters for shell/command execution.
_ALLOWED_PDAL_STAGES = frozenset(
    {
        "readers.las",
        "readers.laz",
        "readers.copc",
        "readers.pcd",
        "readers.optech",
        "writers.las",
        "writers.laz",
        "writers.gdal",
        "writers.copc",
        "filters.pmf",
        "filters.smrf",
        "filters.outlier",
        "filters.range",
        "filters.ferry",
        "filters.assign",
        "filters.reprojection",
        "filters.transformation",
        "filters.crop",
        "filters.merge",
        "filters.splitter",
        "filters.sample",
        "filters.voxelcentroid",
        "filters.cluster",
        "filters.hag_nn",
        "filters.hag_delaunay",
        "filters.elm",
        "filters.returns",
        "filters.stats",
        "filters.expression",
    }
)


def _validate_pipeline_stages(pipeline_data: dict) -> None:
    """Reject PDAL pipelines that contain stages outside the allowlist.

    PDAL supports ``filters.shell`` and ``filters.exec`` which execute
    arbitrary commands — accepting pipelines from untrusted recipe files
    would be a code-execution vector. We allow only well-known readers,
    writers, and safe filters.
    """
    stages = pipeline_data.get("pipeline", [])
    if not isinstance(stages, list):
        raise ValueError("PDAL pipeline JSON must have a 'pipeline' list")
    for i, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValueError(f"Pipeline stage {i} is not a JSON object")
        stage_type = stage.get("type", "")
        if not stage_type:
            raise ValueError(f"Pipeline stage {i} has no 'type' field")
        if stage_type not in _ALLOWED_PDAL_STAGES:
            raise ValueError(
                f"PDAL stage type {stage_type!r} is not in the allowlist. "
                f"Refusing to execute potentially unsafe pipeline. "
                f"Allowed stages: {sorted(_ALLOWED_PDAL_STAGES)}"
            )


def run_pipeline(pipeline_json: str, feedback=None) -> dict:
    """Execute a PDAL pipeline and return metadata.

    Args:
        pipeline_json: JSON string of the PDAL pipeline.
        feedback: Optional progress callback.

    Returns:
        dict with pipeline metadata (point count, stages, etc.).

    Raises:
        ValueError: If the pipeline JSON is invalid or contains a
            disallowed stage (e.g. filters.shell, filters.exec).
        RuntimeError: If pipeline execution fails.
    """
    check_dependencies()

    try:
        pipeline_data = json.loads(pipeline_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid pipeline JSON: {e}") from e

    # Security check: reject pipelines containing stages outside the
    # allowlist. This prevents command-injection via shared recipes.
    _validate_pipeline_stages(pipeline_data)

    if feedback:
        feedback.setProgressText("Executing PDAL pipeline...")

    try:
        pdal_pipeline = pdal.Pipeline(json.dumps(pipeline_data))
        # Modern PDAL (>=2.4) returns an int point count from execute(),
        # NOT a dict. Older versions returned None. The metadata dict is
        # accessed via the .metadata property. The previous code assumed
        # execute() returned a dict and silently reported 0 points.
        point_count = pdal_pipeline.execute()
        metadata = pdal_pipeline.metadata
    except Exception as e:
        raise RuntimeError(f"PDAL pipeline failed: {e}") from e

    if feedback:
        feedback.setProgressText("PDAL pipeline complete.")

    # Extract basic metadata from the pipeline
    stage_count = len(pipeline_data.get("pipeline", []))
    # point_count may be an int (modern PDAL) or a dict (older bindings).
    if isinstance(point_count, int):
        processed_points = point_count
    elif isinstance(point_count, dict):
        processed_points = point_count.get("num_points", 0)
    else:
        processed_points = 0

    # Try to extract a more detailed point count from metadata.
    if isinstance(metadata, dict):
        stages_meta = metadata.get("metadata", {}).get("stages", {})
        for stage_name, stage_meta in stages_meta.items():
            if "point_count" in stage_meta:
                processed_points = int(stage_meta["point_count"])
                break

    return {
        "point_count": processed_points,
        "stage_count": stage_count,
        # Return the actual preset name (last reader stage's filename is
        # not a preset; the preset is set by build_pipeline at the call site).
        # We retain backwards compatibility by returning the first stage type.
        "first_stage_type": pipeline_data.get("pipeline", [{}])[0].get(
            "type", "unknown"
        ),
    }
