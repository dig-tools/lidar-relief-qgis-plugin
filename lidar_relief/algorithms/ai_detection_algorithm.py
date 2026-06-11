"""ai_detection_algorithm.py — QGIS Processing wrapper for AI feature detection.

exports: AiDetectionAlgorithm
used_by: provider.py → loadAlgorithms
"""

import os

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFile,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFileDestination,
    QgsProcessingOutputNumber,
    QgsProcessingException,
)

from ..ml.detector import (
    onnx_available,
    load_model,
    detect_features,
)


class AiDetectionAlgorithm(QgsProcessingAlgorithm):
    """Run AI feature detection on a raster using a user-provided ONNX model."""

    INPUT = "INPUT"
    MODEL_FILE = "MODEL_FILE"
    LABEL_FILE = "LABEL_FILE"
    CONFIDENCE = "CONFIDENCE"
    IOU_THRESHOLD = "IOU_THRESHOLD"
    TILE_SIZE = "TILE_SIZE"
    OUTPUT_VECTOR = "OUTPUT_VECTOR"
    OUTPUT_COUNT = "OUTPUT_COUNT"

    def name(self):
        return "ai_feature_detection"

    def displayName(self):
        return "AI Feature Detection (ONNX Model)"

    def group(self):
        return "LiDAR Relief — AI/ML"

    def groupId(self):
        return "lidar_relief_ml"

    def shortHelpString(self):
        return (
            "Run object detection or semantic segmentation on a raster "
            "using a user-provided ONNX model.\n\n"
            "The plugin acts as an inference engine only — you must "
            "provide a pre-trained model in ONNX format.\n\n"
            "Supported model types:\n"
            "  - Object detection (YOLO, SSD) → bounding boxes\n"
            "  - Semantic segmentation (U-Net) → class labels\n\n"
            "Training your model:\n"
            "  1. Export your trained model to ONNX format\n"
            "  2. Create a labels.json file with class names\n"
            "  3. Provide both files to this algorithm\n\n"
            "Output is a vector layer with bounding boxes and "
            "confidence scores."
        )

    def createInstance(self):
        return AiDetectionAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT, "Input raster layer"
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.MODEL_FILE,
                "ONNX model file (.onnx)",
                fileFilter="ONNX model (*.onnx)",
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.LABEL_FILE,
                "Labels JSON file (optional)",
                fileFilter="JSON (*.json)",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONFIDENCE,
                "Confidence threshold",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                minValue=0.01,
                maxValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.IOU_THRESHOLD,
                "IoU threshold (NMS)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.45,
                minValue=0.05,
                maxValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TILE_SIZE,
                "Tile size (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=640,
                minValue=128,
                maxValue=2048,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_VECTOR,
                "Output detection layer (GeoPackage)",
                fileFilter="GeoPackage (*.gpkg)",
            )
        )
        self.addOutput(
            QgsProcessingOutputNumber(
                self.OUTPUT_COUNT, "Number of detections"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        if not onnx_available():
            raise QgsProcessingException(
                "AI detection requires 'onnxruntime'.\n\n"
                "Install via OSGeo4W Shell:\n"
                "  pip install onnxruntime"
            )

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        model_path = self.parameterAsFile(parameters, self.MODEL_FILE, context)
        label_path = self.parameterAsFile(parameters, self.LABEL_FILE, context)
        confidence = self.parameterAsDouble(parameters, self.CONFIDENCE, context)
        iou = self.parameterAsDouble(parameters, self.IOU_THRESHOLD, context)
        tile_size = self.parameterAsInt(parameters, self.TILE_SIZE, context)
        output_path = self.parameterAsFileOutput(
            parameters, self.OUTPUT_VECTOR, context
        )

        if not model_path or not os.path.exists(model_path):
            raise QgsProcessingException(f"Model file not found: {model_path}")

        feedback.setProgressText("Loading ONNX model...")

        try:
            model = load_model(model_path, label_path)
        except Exception as e:
            raise QgsProcessingException(f"Failed to load model: {e}")

        feedback.pushInfo(
            f"Model: {os.path.basename(model_path)}\n"
            f"Type: {model['model_type']}\n"
            f"Labels: {model['labels'] or 'none'}"
        )

        feedback.setProgressText("Running inference...")

        try:
            result = detect_features(
                raster_path=raster.source(),
                model=model,
                confidence_threshold=confidence,
                iou_threshold=iou,
                tile_size=tile_size,
                feedback=feedback,
            )
        except Exception as e:
            raise QgsProcessingException(f"Inference failed: {e}")

        detections = result["detections"]
        count = result["detection_count"]

        feedback.pushInfo(
            f"Detections: {count}\n"
            f"Tiles processed: {result['total_tiles']}"
        )

        # Write detections to GeoPackage if any found
        if detections and output_path:
            _write_detections_gpkg(detections, output_path, raster.source())
            feedback.pushInfo(f"Output: {output_path}")

        return {
            self.OUTPUT_VECTOR: output_path or "",
            self.OUTPUT_COUNT: count,
        }


def _write_detections_gpkg(
    detections: list,
    output_path: str,
    raster_path: str,
) -> None:
    """Write detection results to a GeoPackage vector layer."""
    from osgeo import ogr, osr, gdal

    driver = ogr.GetDriverByName("GPKG")
    if os.path.exists(output_path):
        driver.DeleteDataSource(output_path)

    ds = driver.CreateDataSource(output_path)
    
    srs = osr.SpatialReference()
    raster_ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if raster_ds and raster_ds.GetProjection():
        srs.ImportFromWkt(raster_ds.GetProjection())
        raster_ds = None
    else:
        srs.ImportFromEPSG(4326)

    layer = ds.CreateLayer("detections", srs, ogr.wkbPolygon)

    # Create fields
    layer.CreateField(ogr.FieldDefn("class_name", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("confidence", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("class_id", ogr.OFTInteger))

    for det in detections:
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("class_name", det.get("class_name", "unknown"))
        feature.SetField("confidence", float(det.get("confidence", 0)))
        feature.SetField("class_id", int(det.get("class_id", 0)))

        bbox = det.get("bbox", [0, 0, 0, 0])
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(bbox[0], bbox[1])
        ring.AddPoint(bbox[2], bbox[1])
        ring.AddPoint(bbox[2], bbox[3])
        ring.AddPoint(bbox[0], bbox[3])
        ring.AddPoint(bbox[0], bbox[1])

        polygon = ogr.Geometry(ogr.wkbPolygon)
        polygon.AddGeometry(ring)
        feature.SetGeometry(polygon)
        layer.CreateFeature(feature)

    ds.FlushCache()
    ds = None
