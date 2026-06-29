"""field_packager.py — Package rasters and anomaly data for field survey.

exports: FieldPackager
         create_anomaly_template(output_path) -> str
         package_for_qfield(raster_path, anomaly_layer, output_dir, **kwargs) -> dict

used_by: algorithms/field_export_algorithm.py
         batch pipeline for automated field workflow

rules:
  Uses only QGIS Python API and GDAL (built-in).
  GeoPackage is the primary output format (single file, robust schema).
  Structured attribute schema follows archaeological survey conventions.
"""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# Regex for safe project names — letters, digits, spaces, hyphens,
# underscores, dots only. Anything else is replaced with `_`.
# This prevents path traversal via `../` and SQL-injection via `'; DROP`.
_SAFE_PROJECT_NAME_RE = re.compile(r"[^A-Za-z0-9 _\-.]")


# ── Anomaly data model ──────────────────────────────────────────────


@dataclass
class AnomalyRecord:
    """A single anomaly record for field survey validation.

    This schema follows standard archaeological remote sensing survey
    conventions and is designed for direct import into QField.
    """

    anomaly_id: str
    detection_method: str = "manual"
    confidence: float = 0.5
    feature_type: str = "unknown"
    field_status: str = "pending"
    observer: str = ""
    photo_path: str = ""
    notes: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


ANOMALY_SCHEMA = {
    "anomaly_id": {
        "type": "TEXT",
        "notnull": True,
        "description": "Unique identifier for this anomaly",
    },
    "detection_method": {
        "type": "TEXT",
        "notnull": True,
        "description": "How the anomaly was detected "
        "(svf, hillshade, slrm, openness, mstp, manual, ai)",
    },
    "confidence": {
        "type": "REAL",
        "notnull": True,
        "description": "Detection confidence 0.0–1.0",
    },
    "feature_type": {
        "type": "TEXT",
        "notnull": True,
        "description": "Interpreted feature type "
        "(barrow, ditch, platform, enclosure, ridge_and_furrow, "
        "kiln, wall, hollow_way, unknown)",
    },
    "field_status": {
        "type": "TEXT",
        "notnull": True,
        "description": "Field validation status "
        "(pending, confirmed, rejected, uncertain)",
    },
    "observer": {
        "type": "TEXT",
        "description": "Name or initials of field observer",
    },
    "photo_path": {
        "type": "TEXT",
        "description": "Path to field photograph on device",
    },
    "notes": {
        "type": "TEXT",
        "description": "Free-text field notes",
    },
    "timestamp": {
        "type": "TEXT",
        "notnull": True,
        "description": "ISO 8601 timestamp of detection or last update",
    },
}


# ── Core functions ──────────────────────────────────────────────────


def _sanitize_project_name(project_name: str) -> str:
    """Return a filesystem-safe slug derived from ``project_name``.

    Replaces any character that isn't a letter, digit, space, hyphen,
    underscore, or dot with ``_``. Strips leading dots and path
    separators to prevent path traversal (``../../``) and rejects names
    that resolve to empty after sanitisation.
    """
    if not project_name or not isinstance(project_name, str):
        return "untitled"
    slug = _SAFE_PROJECT_NAME_RE.sub("_", project_name).strip()
    # Strip leading dots / separators that could escape the output dir.
    slug = slug.lstrip("._/\\")
    # Collapse whitespace to single underscores for filename stability.
    slug = re.sub(r"\s+", "_", slug)
    return slug or "untitled"


def create_anomaly_template(output_path: str) -> str:
    """Create an empty GeoPackage with the standard anomaly schema.

    This generates a template that users can pre-load before field
    work, then populate anomaly points in QField.

    Args:
        output_path: Path for the output .gpkg file.

    Returns:
        Path to the created GeoPackage.

    Raises:
        RuntimeError: If GeoPackage creation fails.
        ValueError: If ``output_path`` would escape its parent directory
            (path traversal attempt).
    """
    from osgeo import ogr, osr

    # Refuse to overwrite an existing file silently.
    if os.path.exists(output_path):
        raise ValueError(
            f"Output file already exists: {output_path}. "
            f"Delete it first or choose a different output path."
        )

    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(output_path)
    if ds is None:
        raise RuntimeError(f"Failed to create GeoPackage: {output_path}")

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    layer = ds.CreateLayer("anomalies", srs, ogr.wkbPoint)

    # Add fields matching the schema
    for field_name, field_info in ANOMALY_SCHEMA.items():
        field_type_map = {
            "TEXT": ogr.OFTString,
            "REAL": ogr.OFTReal,
            "INTEGER": ogr.OFTInteger,
        }
        field_defn = ogr.FieldDefn(
            field_name, field_type_map.get(field_info["type"], ogr.OFTString)
        )
        layer.CreateField(field_defn)

    ds.FlushCache()
    ds = None

    logger.info("Created anomaly template: %s", output_path)
    return output_path


def package_for_qfield(
    raster_path: str,
    anomaly_points: list[dict],
    output_dir: str,
    project_name: str = "LiDAR Relief Survey",
    crs: Optional[str] = None,
    include_raster_copy: bool = True,
) -> dict:
    """Package raster visualizations and anomaly points for QField.

    Creates a complete survey package:
      - survey.gpkg       — Anomaly points with structured schema
      - survey.qgs         — QGIS project file (opens directly in QField)
      - relief.tif/cog.tif — Raster visualization (copy or reference)

    Args:
        raster_path: Path to the relief visualization raster.
        anomaly_points: List of dicts with 'x', 'y', and anomaly fields.
        output_dir: Directory to write the package into.
        project_name: Name for the QGIS project and package. Sanitised
            to a filesystem-safe slug before being used in filenames.
        crs: CRS string for the project (auto-detected from the raster
            if None — no longer hardcoded to EPSG:4326).
        include_raster_copy: If True, copy raster into package.

    Returns:
        dict with paths to generated files.
    """
    import shutil
    from osgeo import gdal, ogr, osr

    os.makedirs(output_dir, exist_ok=True)

    # Sanitise the project name BEFORE using it to build file paths.
    # This prevents path traversal via project_name='../../etc/passwd'.
    safe_name = _sanitize_project_name(project_name)
    if safe_name != project_name:
        logger.info(
            "Sanitised project name %r → %r for filesystem safety.",
            project_name,
            safe_name,
        )

    gpkg_path = os.path.join(output_dir, f"{safe_name}.gpkg")
    qgs_path = os.path.join(output_dir, f"{safe_name}.qgs")

    # Refuse to silently destroy existing files.
    for existing in (gpkg_path, qgs_path):
        if os.path.exists(existing):
            raise ValueError(
                f"Output file already exists: {existing}. "
                f"Delete it first or choose a different project name."
            )

    # Auto-detect CRS from the source raster if the caller didn't
    # override it. Previously this was hardcoded to EPSG:4326 which
    # silently misplaced anomaly points when the raster was in a
    # projected CRS (e.g. EPSG:27700 British National Grid).
    if crs is None:
        # Use try/finally to guarantee the GDAL dataset is closed even
        # if ImportFromWkt or GetAuthorityCode raises — otherwise the
        # raster file handle leaks (and on Windows the file is locked).
        raster_ds = None
        try:
            raster_ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
            if raster_ds:
                raster_wkt = raster_ds.GetProjection()
                if raster_wkt:
                    detected_srs = osr.SpatialReference()
                    detected_srs.ImportFromWkt(raster_wkt)
                    auto_authid = detected_srs.GetAuthorityCode(None)
                    if auto_authid:
                        crs = f"EPSG:{auto_authid}"
                    else:
                        crs = raster_wkt
        except Exception as e:
            logger.warning("Could not auto-detect raster CRS: %s", e)
        finally:
            # Always release the GDAL dataset to free the file handle.
            raster_ds = None
    if crs is None:
        # Last-resort fallback: WGS84, but warn loudly.
        logger.warning(
            "No CRS detected for raster %s — falling back to EPSG:4326 "
            "for anomaly layer. Anomaly points may be misplaced if the "
            "raster is in a local CRS.",
            raster_path,
        )
        crs = "EPSG:4326"

    # Compute raster extent for the QGS project's mapcanvas so QField
    # opens zoomed to the data, not to the whole world.
    raster_extent = None
    raster_ds = None
    try:
        raster_ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
        if raster_ds:
            gt = raster_ds.GetGeoTransform()
            x_size = raster_ds.RasterXSize
            y_size = raster_ds.RasterYSize
            if gt and len(gt) >= 6:
                x_min = gt[0]
                y_max = gt[3]
                x_max = gt[0] + x_size * gt[1]
                y_min = gt[3] + y_size * gt[5]
                raster_extent = (x_min, y_min, x_max, y_max)
    except Exception as e:
        logger.warning("Could not read raster extent: %s", e)
    finally:
        raster_ds = None

    # Copy raster if requested
    if include_raster_copy:
        raster_ext = os.path.splitext(raster_path)[1] or ".tif"
        packaged_raster = os.path.join(output_dir, f"relief{raster_ext}")
        if os.path.exists(packaged_raster):
            raise ValueError(
                f"Output raster already exists: {packaged_raster}. "
                f"Delete it first or choose a different output directory."
            )
        shutil.copy2(raster_path, packaged_raster)
        raster_ref = packaged_raster
    else:
        raster_ref = raster_path

    # Create GeoPackage with anomaly points
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(gpkg_path)
    if ds is None:
        raise RuntimeError(f"Failed to create GeoPackage: {gpkg_path}")

    # Use the detected CRS rather than hardcoded WGS84.
    srs = osr.SpatialReference()
    if crs.startswith("EPSG:"):
        srs.ImportFromEPSG(int(crs.split(":")[1]))
    else:
        # Treat as WKT.
        srs.ImportFromWkt(crs)
    layer = ds.CreateLayer("anomalies", srs, ogr.wkbPoint)

    # Create fields
    for field_name, field_info in ANOMALY_SCHEMA.items():
        field_type_map = {
            "TEXT": ogr.OFTString,
            "REAL": ogr.OFTReal,
            "INTEGER": ogr.OFTInteger,
        }
        field_defn = ogr.FieldDefn(
            field_name, field_type_map.get(field_info["type"], ogr.OFTString)
        )
        layer.CreateField(field_defn)

    # Add features
    for i, pt in enumerate(anomaly_points):
        anom_idx = i + 1
        # Validate anomaly point has required x/y coordinates.
        if "x" not in pt or "y" not in pt:
            logger.warning(
                "Skipping anomaly point %d: missing 'x' or 'y' coordinate.",
                anom_idx,
            )
            continue
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("anomaly_id", pt.get("anomaly_id", f"ANOM-{anom_idx:04d}"))
        feature.SetField("detection_method", pt.get("detection_method", "manual"))
        feature.SetField("confidence", float(pt.get("confidence", 0.5)))
        feature.SetField("feature_type", pt.get("feature_type", "unknown"))
        feature.SetField("field_status", pt.get("field_status", "pending"))
        feature.SetField("observer", pt.get("observer", ""))
        feature.SetField("photo_path", pt.get("photo_path", ""))
        feature.SetField("notes", pt.get("notes", ""))
        feature.SetField("timestamp", pt.get("timestamp", datetime.now().isoformat()))

        # Create point geometry
        point = ogr.Geometry(ogr.wkbPoint)
        point.AddPoint(float(pt["x"]), float(pt["y"]))
        feature.SetGeometry(point)
        layer.CreateFeature(feature)

    ds.FlushCache()
    ds = None

    rel_raster_ref = (
        os.path.basename(raster_ref)
        if include_raster_copy
        else os.path.relpath(raster_ref, output_dir)
    )
    rel_gpkg_path = os.path.basename(gpkg_path)

    # Create QGIS project file
    _create_qgis_project(
        qgs_path,
        rel_raster_ref,
        rel_gpkg_path,
        project_name,  # Pass the original name (XML-escaped inside)
        crs,
        extent=raster_extent,
    )

    return {
        "gpkg": gpkg_path,
        "qgs": qgs_path,
        "raster": raster_ref if include_raster_copy else raster_path,
        "anomaly_count": len(anomaly_points),
        "crs": crs,
    }


def _create_qgis_project(
    qgs_path: str,
    raster_path: str,
    gpkg_path: str,
    project_name: str,
    crs: Optional[str] = None,
    extent: Optional[tuple[float, float, float, float]] = None,
) -> None:
    """Create a minimal QGIS project file for field survey.

    The .qgs XML project opens directly in QField with:
      - The relief visualization raster loaded
      - The anomaly GeoPackage layer loaded with field-validation form
      - Dark theme map canvas
      - Coordinate display in WGS84
      - Map canvas zoomed to the raster extent (not the whole world)

    All user-supplied strings are XML-escaped to prevent injection.
    """
    from xml.etree import ElementTree as ET

    # Determine the canvas extent. Previously hardcoded to (-180,-90,180,90)
    # which caused QField to open zoomed out to the whole world.
    if extent is not None and len(extent) == 4:
        x_min, y_min, x_max, y_max = extent
    else:
        # Sensible default for WGS84 if no extent available.
        x_min, y_min, x_max, y_max = -180.0, -90.0, 180.0, 90.0

    # Determine CRS authid to display
    crs_authid = crs if crs else "EPSG:4326"
    # Determine map units based on whether CRS is geographic or projected
    if crs_authid.startswith("EPSG:4326"):
        units = "degrees"
    else:
        units = "meters"

    # Note: ElementTree automatically escapes attribute values during
    # serialization, so we pass project_name directly. The previous code
    # manually escaped it via _xml_escape_attr, which caused
    # double-escaping (e.g. "&" became "&amp;amp;").

    # Build a minimal QGIS project XML
    # This is schema-compatible with QGIS 3.x / 4.x project files
    doc = ET.Element("qgis", projectname=project_name, version="3.40.0")

    # Map canvas settings
    canvas = ET.SubElement(doc, "mapcanvas")
    ET.SubElement(canvas, "units").text = units
    ET.SubElement(
        canvas,
        "extent",
        xmin=f"{x_min:.10g}",
        ymin=f"{y_min:.10g}",
        xmax=f"{x_max:.10g}",
        ymax=f"{y_max:.10g}",
    )

    # Project CRS
    map_crs = ET.SubElement(doc, "mapcrs")
    ET.SubElement(map_crs, "spatialrefsys")
    ET.SubElement(map_crs.find("spatialrefsys"), "authid").text = crs_authid

    # Raster layer
    raster_maplayer = ET.SubElement(
        doc, "maplayer", type="raster", minimumScale="-1", maximumScale="-1"
    )
    ET.SubElement(raster_maplayer, "id").text = "relief_visualization"
    ET.SubElement(raster_maplayer, "name").text = "Relief Visualization"
    ET.SubElement(raster_maplayer, "type").text = "raster"
    ET.SubElement(raster_maplayer, "datasource").text = raster_path

    # Vector layer with field form
    vector_maplayer = ET.SubElement(
        doc, "maplayer", type="vector", minimumScale="-1", maximumScale="-1"
    )
    ET.SubElement(vector_maplayer, "id").text = "anomalies"
    ET.SubElement(vector_maplayer, "name").text = "Anomalies"
    ET.SubElement(vector_maplayer, "type").text = "vector"
    # Use ElementTree's text= (which auto-escapes) for the datasource
    # rather than string-replace on single quotes only — the previous
    # implementation was vulnerable to characters like `;`, `--`, `/*`,
    # and newlines that can break OGR's URI parser.
    datasource_elem = ET.SubElement(vector_maplayer, "datasource")
    datasource_elem.text = f"dbname='{gpkg_path}' table=\"anomalies\" (geometry)"

    # Field configuration (for QField digitising form)
    edit_types = ET.SubElement(vector_maplayer, "fieldConfiguration")
    for field_name in ANOMALY_SCHEMA:
        fld = ET.SubElement(edit_types, "field", name=field_name)
        if field_name == "field_status":
            # Dropdown with predefined values
            ET.SubElement(fld, "editType").text = "ValueMap"
            value_map = ET.SubElement(fld, "valueMap")
            for val in ["pending", "confirmed", "rejected", "uncertain"]:
                ET.SubElement(value_map, "value", key=val).text = val
        elif field_name == "feature_type":
            ET.SubElement(fld, "editType").text = "ValueMap"
            value_map = ET.SubElement(fld, "valueMap")
            for val in [
                "barrow",
                "ditch",
                "platform",
                "enclosure",
                "ridge_and_furrow",
                "kiln",
                "wall",
                "hollow_way",
                "unknown",
            ]:
                ET.SubElement(value_map, "value", key=val).text = val
        elif field_name == "confidence":
            ET.SubElement(fld, "editType").text = "Range"
            ET.SubElement(fld, "range", min="0", max="1", step="0.1")
        elif field_name == "photo_path":
            ET.SubElement(fld, "editType").text = "ExternalResource"
        else:
            ET.SubElement(fld, "editType").text = "TextEdit"

    # Prettify XML using safe ElementTree indentation
    ET.indent(doc, space="  ")
    pretty_xml = ET.tostring(doc, encoding="utf-8", xml_declaration=False)

    with open(qgs_path, "wb") as f:
        f.write(pretty_xml)

    logger.info("Created QGIS project: %s", qgs_path)
