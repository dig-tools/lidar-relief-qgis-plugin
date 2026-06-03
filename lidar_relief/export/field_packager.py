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
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


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
    """
    from osgeo import ogr, osr

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
        field_defn = ogr.FieldDefn(field_name, field_type_map.get(
            field_info["type"], ogr.OFTString
        ))
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
        project_name: Name for the QGIS project and package.
        crs: CRS string for the project (auto-detected if None).
        include_raster_copy: If True, copy raster into package.

    Returns:
        dict with paths to generated files.
    """
    import shutil
    from osgeo import ogr, osr

    os.makedirs(output_dir, exist_ok=True)

    gpkg_path = os.path.join(output_dir, f"{project_name.lower().replace(' ', '_')}.gpkg")
    qgs_path = os.path.join(output_dir, f"{project_name.lower().replace(' ', '_')}.qgs")

    # Copy raster if requested
    if include_raster_copy:
        raster_ext = os.path.splitext(raster_path)[1] or ".tif"
        packaged_raster = os.path.join(output_dir, f"relief{raster_ext}")
        shutil.copy2(raster_path, packaged_raster)
        raster_ref = packaged_raster
    else:
        raster_ref = raster_path

    # Create GeoPackage with anomaly points
    driver = ogr.GetDriverByName("GPKG")
    if os.path.exists(gpkg_path):
        driver.DeleteDataSource(gpkg_path)

    ds = driver.CreateDataSource(gpkg_path)
    if ds is None:
        raise RuntimeError(f"Failed to create GeoPackage: {gpkg_path}")

    # Use WGS84 for field GPS compatibility
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    layer = ds.CreateLayer("anomalies", srs, ogr.wkbPoint)

    # Create fields
    for field_name, field_info in ANOMALY_SCHEMA.items():
        field_type_map = {
            "TEXT": ogr.OFTString,
            "REAL": ogr.OFTReal,
            "INTEGER": ogr.OFTInteger,
        }
        field_defn = ogr.FieldDefn(field_name, field_type_map.get(
            field_info["type"], ogr.OFTString
        ))
        layer.CreateField(field_defn)

    # Add features
    for i, pt in enumerate(anomaly_points):
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("anomaly_id", pt.get("anomaly_id", f"ANOM-{i+1:04d}"))
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

    # Create QGIS project file
    _create_qgis_project(
        qgs_path, raster_ref, gpkg_path, project_name, crs
    )

    return {
        "gpkg": gpkg_path,
        "qgs": qgs_path,
        "raster": raster_ref if include_raster_copy else raster_path,
        "anomaly_count": len(anomaly_points),
    }


def _create_qgis_project(
    qgs_path: str,
    raster_path: str,
    gpkg_path: str,
    project_name: str,
    crs: Optional[str] = None,
) -> None:
    """Create a minimal QGIS project file for field survey.

    The .qgs XML project opens directly in QField with:
      - The relief visualization raster loaded
      - The anomaly GeoPackage layer loaded with field-validation form
      - Dark theme map canvas
      - Coordinate display in WGS84
    """
    from xml.etree import ElementTree as ET

    # Build a minimal QGIS project XML
    # This is schema-compatible with QGIS 3.x / 4.x project files
    doc = ET.Element("qgis", projectname=project_name, version="3.40.0")

    # Map canvas settings
    canvas = ET.SubElement(doc, "mapcanvas")
    ET.SubElement(canvas, "units").text = "degrees"
    ET.SubElement(canvas, "extent", xmin="-180", ymin="-90",
                  xmax="180", ymax="90")

    # Project CRS
    map_crs = ET.SubElement(doc, "mapcrs")
    ET.SubElement(map_crs, "spatialrefsys")
    crs_authid = crs if crs else "EPSG:4326"
    ET.SubElement(map_crs.find("spatialrefsys"), "authid").text = crs_authid

    # Raster layer
    raster_maplayer = ET.SubElement(doc, "maplayer",
                                    type="raster",
                                    minimumScale="-1",
                                    maximumScale="-1")
    ET.SubElement(raster_maplayer, "id").text = "relief_visualization"
    ET.SubElement(raster_maplayer, "name").text = "Relief Visualization"
    ET.SubElement(raster_maplayer, "type").text = "raster"
    ET.SubElement(raster_maplayer, "datasource").text = raster_path

    # Vector layer with field form
    vector_maplayer = ET.SubElement(doc, "maplayer",
                                    type="vector",
                                    minimumScale="-1",
                                    maximumScale="-1")
    ET.SubElement(vector_maplayer, "id").text = "anomalies"
    ET.SubElement(vector_maplayer, "name").text = "Anomalies"
    ET.SubElement(vector_maplayer, "type").text = "vector"
    ET.SubElement(vector_maplayer, "datasource").text = (
        f"dbname='{gpkg_path}' table=\"anomalies\" (geometry)"
    )

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
            for val in ["barrow", "ditch", "platform", "enclosure",
                        "ridge_and_furrow", "kiln", "wall",
                        "hollow_way", "unknown"]:
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
