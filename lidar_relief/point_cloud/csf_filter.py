"""csf_filter.py — Cloth Simulation Filter for archaeology-tuned ground extraction.

exports: csf_available() -> bool,
         filter_point_cloud(xyz_array, **params) -> tuple,
         filter_las_file(las_path, output_dem_path, **params) -> dict,
         ARCHAEOLOGY_PRESETS

used_by: algorithms/csf_algorithm.py

rules:
  Uses cloth-simulation-filter (CSF) C++ library via Python bindings.
  Provides archaeology-specific presets that preserve micro-relief.
  Pure Python dependency — no GDAL needed for the filter itself.
"""

import logging
import os
import tempfile
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from CSF import CSF, VecInt, VecFloat, VecVecFloat

    _CSF_AVAILABLE = True
except ImportError:
    _CSF_AVAILABLE = False

# Archaeology-tuned parameter presets
# Based on research: older deterministic filters (CSF, PMF, MCC)
# outperform modern AI filters at preserving archaeological micro-relief
ARCHAEOLOGY_PRESETS = {
    "archaeology_fine": {
        "cloth_resolution": 0.5,
        "class_threshold": 0.5,
        "rigidness": 1,
        "time_step": 0.65,
        "b_slope_smooth": False,
        "description": "Maximum micro-relief preservation. Use for subtle "
        "earthworks on flat terrain.",
    },
    "archaeology_standard": {
        "cloth_resolution": 1.0,
        "class_threshold": 0.8,
        "rigidness": 2,
        "time_step": 0.65,
        "b_slope_smooth": True,
        "description": "Balance of vegetation removal and earthwork "
        "preservation. Suitable for most surveys.",
    },
    "forested": {
        "cloth_resolution": 2.0,
        "class_threshold": 1.2,
        "rigidness": 3,
        "time_step": 0.50,
        "b_slope_smooth": True,
        "description": "Aggressive ground detection for dense canopy. "
        "May remove subtle features.",
    },
    "urban": {
        "cloth_resolution": 1.0,
        "class_threshold": 0.5,
        "rigidness": 1,
        "time_step": 0.65,
        "b_slope_smooth": True,
        "description": "Standard filtering for built-up areas with "
        "sharp building edges.",
    },
}

DEFAULT_PRESET = "archaeology_standard"


def csf_available() -> bool:
    """Check if the CSF library is installed and importable."""
    return _CSF_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError with clear instructions if CSF missing."""
    if not _CSF_AVAILABLE:
        raise ImportError(
            "CSF (Cloth Simulation Filter) is required for point "
            "cloud ground filtering.\n\n"
            "Install it via the OSGeo4W Shell:\n"
            "  pip install cloth-simulation-filter\n\n"
            "Or via your system terminal:\n"
            "  pip install cloth-simulation-filter"
        )


def _numpy_to_csf_points(xyz: np.ndarray) -> "VecVecFloat":
    """Convert a NumPy XYZ array to CSF's VecVecFloat format.

    Args:
        xyz: (N, 3) float32/float64 array of XYZ points.

    Returns:
        VecVecFloat suitable for CSF.setPointCloud().
    """
    pts = VecVecFloat()
    for row in xyz:
        pt = VecFloat()
        pt.push_back(float(row[0]))
        pt.push_back(float(row[1]))
        pt.push_back(float(row[2]))
        pts.push_back(pt)
    return pts


def filter_point_cloud(
    xyz: np.ndarray,
    cloth_resolution: float = 1.0,
    class_threshold: float = 0.8,
    rigidness: int = 2,
    time_step: float = 0.65,
    b_slope_smooth: bool = True,
    iterations: int = 500,
) -> tuple[np.ndarray, np.ndarray]:
    """Run CSF ground filtering on a point cloud.

    Args:
        xyz: (N, 3) float32 NumPy array of XYZ point coordinates.
        cloth_resolution: Grid resolution of the cloth (metres).
            Smaller = finer detail, higher memory.
        class_threshold: Classification threshold. Lower = more
            aggressive ground detection.
        rigidness: Cloth rigidness (1–3). 1 = flexible (follows
            terrain), 3 = stiff (filters more).
        time_step: Simulation time step (0.3–1.0). Lower = more
            accurate but slower.
        b_slope_smooth: Enable slope post-processing smoothing.
        iterations: Maximum simulation iterations.

    Returns:
        (ground_xyz, offground_xyz) — filtered point cloud arrays.
    """
    check_dependencies()

    if xyz.ndim != 2 or xyz.shape[1] < 3:
        raise ValueError(f"Expected (N, 3) array, got {xyz.shape}")

    if len(xyz) == 0:
        return np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.float32)

    # Build CSF point cloud
    pts = _numpy_to_csf_points(xyz)

    # Configure CSF
    csf = CSF()
    csf.params.cloth_resolution = float(cloth_resolution)
    csf.params.class_threshold = float(class_threshold)
    csf.params.rigidness = int(rigidness)
    csf.params.time_step = float(time_step)
    if hasattr(csf.params, "bSloopSmooth"):
        csf.params.bSloopSmooth = bool(b_slope_smooth)
    else:
        csf.params.bSlopeSmooth = bool(b_slope_smooth)

    if hasattr(csf.params, "interations"):
        csf.params.interations = int(iterations)
    else:
        csf.params.iterations = int(iterations)

    # Run
    csf.setPointCloud(pts)
    ground_indices = VecInt()
    offground_indices = VecInt()
    csf.do_filtering(ground_indices, offground_indices)

    # Convert results to numpy arrays
    g_idx = list(ground_indices)
    og_idx = list(offground_indices)

    ground_xyz = xyz[g_idx] if len(g_idx) > 0 else np.empty((0, 3), dtype=xyz.dtype)
    offground_xyz = (
        xyz[og_idx] if len(og_idx) > 0 else np.empty((0, 3), dtype=xyz.dtype)
    )

    return ground_xyz, offground_xyz


def filter_las_file(
    las_path: str,
    output_dem_path: str,
    preset: str = DEFAULT_PRESET,
    cellsize: float = 1.0,
    ground_only: bool = True,
    crs: Optional[str] = None,
    feedback=None,
) -> dict:
    """Read a LAS/LAZ file, run CSF ground filtering, write a DEM.

    This is the primary entry point for the QGIS Processing algorithm.

    Args:
        las_path: Path to the input LAS/LAZ file.
        output_dem_path: Path for the output DEM GeoTIFF.
        preset: Parameter preset name from ARCHAEOLOGY_PRESETS.
        cellsize: Output DEM cell size in map units.
        ground_only: If True, output only ground points as DEM.
            If False, output a binary ground/non-ground classification.
        crs: CRS to tag the output DEM with, as an authority string
            (e.g. ``'EPSG:27700'``) or WKT. If ``None`` (the default),
            the CRS is read from the LAS file header. If the file has
            no CRS either, a ``ValueError`` is raised — silently
            assuming WGS84 led to misplaced DEMs in the field.
        feedback: Optional progress callback.

    Returns:
        dict with processing statistics.

    Raises:
        ImportError: If CSF or laspy/PDAL is not installed.
        RuntimeError: If processing fails.
        ValueError: If no CRS can be determined for the output DEM.
    """
    check_dependencies()

    # Try to read point cloud from LAS/LAZ
    xyz, detected_crs = _read_las_points(las_path, feedback)

    # Resolve output CRS: explicit arg wins, else detected from file, else fail
    resolved_crs = crs or detected_crs
    if resolved_crs is None:
        raise ValueError(
            f"No CRS available for '{las_path}'. The LAS file header has no "
            f"coordinate system information, and no explicit CRS was supplied. "
            f"Either:\n"
            f"  - Re-export the LAS file with embedded CRS (recommended), or\n"
            f"  - Pass an explicit crs= argument (e.g. crs='EPSG:27700').\n"
            f"Previously this plugin silently assumed EPSG:4326 (WGS84), "
            f"which produced misplaced DEMs for projected point clouds."
        )
    if crs is None and detected_crs is not None:
        logger.info("Using CRS detected from LAS file: %s", resolved_crs)
        if feedback:
            feedback.setProgressText(f"Using CRS from LAS file: {resolved_crs}")

    if feedback:
        feedback.setProgressText(
            f"Read {len(xyz)} points from {os.path.basename(las_path)}"
        )

    if len(xyz) == 0:
        raise RuntimeError(f"No valid points found in {las_path}")

    # Get preset parameters
    if preset in ARCHAEOLOGY_PRESETS:
        params = ARCHAEOLOGY_PRESETS[preset].copy()
        params.pop("description", None)
    else:
        params = ARCHAEOLOGY_PRESETS[DEFAULT_PRESET].copy()
        params.pop("description", None)
        logger.warning("Unknown preset '%s', using '%s'", preset, DEFAULT_PRESET)

    if feedback:
        feedback.setProgressText(f"Running CSF ground filtering ({preset})...")

    ground_xyz, offground_xyz = filter_point_cloud(xyz, **params)

    if feedback:
        feedback.setProgressText(
            f"Classified: {len(ground_xyz)} ground, {len(offground_xyz)} non-ground"
        )

    if len(ground_xyz) < 10:
        raise RuntimeError(
            f"Only {len(ground_xyz)} ground points detected. "
            f"Try a less aggressive preset."
        )

    # Generate DEM from ground points
    dem_path = _points_to_dem(
        ground_xyz,
        output_dem_path,
        cellsize=cellsize,
        crs=resolved_crs,
        feedback=feedback,
    )

    return {
        "dem_path": dem_path,
        "total_points": len(xyz),
        "ground_points": len(ground_xyz),
        "offground_points": len(offground_xyz),
        "preset": preset,
        "cellsize": cellsize,
        "crs": resolved_crs,
    }


def _read_las_points(las_path: str, feedback=None):
    """Read XYZ points (and CRS) from a LAS/LAZ file.

    Tries laspy first, then PDAL, then falls back to simple text parse.

    Args:
        las_path: Path to LAS/LAZ file.

    Returns:
        Tuple ``(xyz, crs)`` where ``xyz`` is an (N, 3) float64 NumPy array
        and ``crs`` is a CRS authority string like ``'EPSG:27700'``, or
        ``None`` if the file has no CRS information.

    Raises:
        RuntimeError: If no reader is available.
    """
    # Try laspy
    try:
        import laspy

        las = laspy.read(las_path)
        xyz = np.column_stack(
            [
                las.x,
                las.y,
                las.z,
            ]
        ).astype(np.float64)
        crs = _crs_to_authid(las.header.parse_crs(prefer_wkt=True))
        logger.info("Read %d points via laspy (crs=%s)", len(xyz), crs)
        return xyz, crs
    except ImportError:
        pass
    except Exception as e:
        logger.warning("laspy failed: %s, trying PDAL...", e)

    # Try PDAL
    try:
        import pdal

        pipeline = pdal.Pipeline()
        pipeline |= pdal.Reader.las(filename=las_path)
        pipeline |= pdal.Filter.ferry(dimensions="Intensity=>Ignored")
        pipeline.execute()
        arrays = pipeline.arrays
        if arrays:
            arr = arrays[0]
            xyz = np.column_stack([arr["X"], arr["Y"], arr["Z"]]).astype(np.float64)
            crs = _crs_from_pdal_metadata(pipeline.metadata)
            logger.info("Read %d points via PDAL (crs=%s)", len(xyz), crs)
            return xyz, crs
    except ImportError:
        pass
    except Exception as e:
        logger.warning("PDAL failed: %s", e)

    raise RuntimeError(
        "Cannot read LAS/LAZ files. Install 'laspy' or 'pdal' Python "
        "packages:\n"
        "  pip install laspy\n"
        "  pip install pdal"
    )


def _crs_to_authid(crs) -> Optional[str]:
    """Convert a pyproj.CRS (or anything with .to_epsg()) to 'EPSG:NNNN'.

    Returns None if no EPSG code can be derived. Falls back to WKT if the
    CRS object exposes it but has no EPSG code — callers can pass that
    string straight to GDAL's outputSRS, which accepts WKT.
    """
    if crs is None:
        return None
    try:
        epsg = crs.to_epsg()
        if epsg is not None:
            return f"EPSG:{epsg}"
    except AttributeError:
        pass
    # Fall back to WKT if available
    try:
        wkt = crs.to_wkt()
        if wkt:
            return wkt
    except AttributeError:
        pass
    except (
        Exception
    ) as e:  # pragma: no cover — pyproj can raise pyproj.exceptions.CRSError
        logger.debug("Could not convert CRS to WKT: %s", e)
    return None


def _crs_from_pdal_metadata(metadata) -> Optional[str]:
    """Extract a CRS string from a PDAL pipeline metadata tree.

    PDAL stores the inferred CRS under metadata > 'stages' >
    'readers.las' > 'srs' > various keys (compoundwkt, wkt, proj4, id).
    Returns an 'EPSG:NNNN' string if found, else None.
    """
    try:
        stages = metadata.get("metadata", {}).get("stages", {})
        reader = stages.get("readers.las", {})
        srs = reader.get("srs", {})
        # Prefer explicit EPSG id, then WKT, then proj4
        srs_id = srs.get("id")
        if srs_id and str(srs_id).isdigit():
            return f"EPSG:{srs_id}"
        wkt = srs.get("compoundwkt") or srs.get("wkt")
        if wkt:
            return wkt
        proj4 = srs.get("proj4")
        if proj4:
            return proj4
    except (AttributeError, KeyError, TypeError):
        pass
    return None


def _points_to_dem(
    xyz: np.ndarray,
    output_path: str,
    cellsize: float = 1.0,
    crs: Optional[str] = None,
    feedback=None,
) -> str:
    """Rasterize XYZ ground points to a DEM GeoTIFF.

    Uses GDAL's grid API for inverse-distance weighting interpolation.

    Args:
        xyz: (N, 3) float64 NumPy array (X, Y, Z).
        output_path: Output GeoTIFF path.
        cellsize: Output cell size.
        crs: CRS to tag the output DEM with, as an 'EPSG:NNNN' string
            or WKT. **Required** — pass ``None`` only if you have
            already validated the source has no CRS and explicitly want
            GDAL to write a CRS-less raster. Previously this defaulted
            to ``'EPSG:4326'`` which silently tagged every output DEM
            as WGS84 (the v2.0.4 changelog claimed this was fixed, but
            the default argument remained EPSG:4326).
        feedback: Optional progress callback.

    Returns:
        Path to the output DEM.
    """
    try:
        from osgeo import gdal
    except ImportError:
        raise RuntimeError("GDAL is required for DEM generation but not available.")

    if crs is None:
        # Refuse to silently produce a CRS-less DEM. The caller
        # (filter_las_file) already validates this and provides a CRS
        # from the LAS header — but defend in depth.
        raise ValueError(
            "_points_to_dem requires an explicit CRS. Pass crs='EPSG:NNNN' "
            "or a WKT string. Refusing to write a DEM with no coordinate "
            "system — it would be silently misaligned with other data."
        )

    if feedback:
        feedback.setProgressText("Generating DEM from ground points...")

    # Write points to temporary XYZ file for GDAL grid
    tmp_xyz_fd, tmp_xyz_path = tempfile.mkstemp(suffix=".xyz")
    os.close(tmp_xyz_fd)
    try:
        np.savetxt(tmp_xyz_path, xyz, fmt="%.3f %.3f %.3f")

        # Compute extent
        x_min, x_max = xyz[:, 0].min(), xyz[:, 0].max()
        y_min, y_max = xyz[:, 1].min(), xyz[:, 1].max()

        # Add half-cell padding
        x_min -= cellsize / 2
        x_max += cellsize / 2
        y_min -= cellsize / 2
        y_max += cellsize / 2

        cols = int((x_max - x_min) / cellsize) + 1
        rows = int((y_max - y_min) / cellsize) + 1

        # Use GDAL grid with IDW interpolation
        grid_options = gdal.GridOptions(
            format="GTiff",
            width=cols,
            height=rows,
            outputBounds=(x_min, y_min, x_max, y_max),
            outputSRS=crs,
            algorithm="invdist:power=2:smoothing=1.0",
            zfield=2,
        )

        gdal.Grid(output_path, tmp_xyz_path, options=grid_options)

    finally:
        if os.path.exists(tmp_xyz_path):
            os.unlink(tmp_xyz_path)

    return output_path
