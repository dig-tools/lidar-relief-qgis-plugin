"""detector.py — ONNX model inference for AI feature detection.

exports: onnx_available() -> bool,
         load_model(model_path, label_path) -> dict,
         detect_features(raster_path, model, **kwargs) -> dict,
         preprocess_tile(tile, input_size) -> np.ndarray,
         postprocess_detections(outputs, confidence_threshold, labels, ...) -> list

used_by: algorithms/ai_detection_algorithm.py

rules:
  User provides their own ONNX model — no training in plugin.
  Plugin acts as inference engine only.
  Lightweight dependency: onnxruntime + numpy.
  Tiled processing for large rasters.
"""

import json
import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort

    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False

# Supported model types and their expected output formats
SUPPORTED_MODEL_TYPES = {
    "object_detection": {
        "description": "Bounding box detection (YOLO, SSD, etc.)",
        "expected_outputs": ["num_dets", "det_boxes", "det_scores", "det_classes"],
        "postprocess": "yolo",
    },
    "semantic_segmentation": {
        "description": "Pixel-wise classification (U-Net, DeepLab, etc.)",
        "expected_outputs": ["label_map"],
        "postprocess": "segmentation",
    },
}


def onnx_available() -> bool:
    """Check if onnxruntime is installed."""
    return _ONNX_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError if onnxruntime missing."""
    if not _ONNX_AVAILABLE:
        raise ImportError(
            "AI feature detection requires 'onnxruntime'.\n\n"
            "Install via OSGeo4W Shell:\n"
            "  pip install onnxruntime\n\n"
            "For faster CPU inference with Intel CPUs:\n"
            "  pip install onnxruntime-openvino"
        )


def load_model(
    model_path: str,
    label_path: Optional[str] = None,
) -> dict:
    """Load an ONNX model and its label map.

    Args:
        model_path: Path to the .onnx model file.
        label_path: Optional path to labels.json file.

    Returns:
        dict with:
            - 'session': ONNX Runtime InferenceSession
            - 'input_name': str
            - 'input_shape': tuple (batch, channels, height, width)
            - 'output_names': list of str
            - 'labels': list of class names (empty if no label file)
            - 'model_type': str ('object_detection' or 'semantic_segmentation')
    """
    check_dependencies()

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    # Load labels
    labels = []
    if label_path and os.path.exists(label_path):
        try:
            with open(label_path) as f:
                label_data = json.load(f)
                if isinstance(label_data, list):
                    labels = label_data
                elif isinstance(label_data, dict):
                    # Support {0: "barrow", 1: "ditch"} format
                    labels = [label_data[str(i)] for i in range(len(label_data))]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load labels: %s", e)

    # Create inference session
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.enable_cpu_mem_arena = True

    session = ort.InferenceSession(
        model_path, sess_options,
        providers=["CPUExecutionProvider"],
    )

    # Get model metadata
    input_info = session.get_inputs()[0]
    input_name = input_info.name
    input_shape = input_info.shape  # (N, C, H, W)

    output_names = [o.name for o in session.get_outputs()]

    # Detect model type from output signature
    model_type = "object_detection"  # Default
    for o_name in output_names:
        if "label_map" in o_name:
            model_type = "semantic_segmentation"
            break

    logger.info(
        "Loaded ONNX model: %s, type=%s, inputs=%s, outputs=%s",
        os.path.basename(model_path),
        model_type,
        input_shape,
        output_names,
    )

    return {
        "session": session,
        "input_name": input_name,
        "input_shape": input_shape,
        "output_names": output_names,
        "labels": labels,
        "model_type": model_type,
    }


def preprocess_tile(
    tile: np.ndarray,
    input_size: tuple[int, int],
) -> np.ndarray:
    """Preprocess a raster tile for model inference.

    Args:
        tile: 2D (H, W) or 3D (H, W, C) numpy array.
        input_size: Model input size (height, width).

    Returns:
        Preprocessed array of shape (1, C, H, W) as float32.
    """
    # Handle single-band → 3-channel by stacking
    if tile.ndim == 2:
        tile = np.stack([tile] * 3, axis=-1)
    elif tile.ndim == 3 and tile.shape[2] == 1:
        tile = np.repeat(tile, 3, axis=2)

    # Resize to input size using simple numpy interpolation
    h, w = input_size
    src_h, src_w = tile.shape[:2]

    # Create coordinate grids
    y_ratio = src_h / h
    x_ratio = src_w / w
    y_coords = np.clip(
        np.floor(np.arange(h) * y_ratio).astype(np.int32), 0, src_h - 1
    )
    x_coords = np.clip(
        np.floor(np.arange(w) * x_ratio).astype(np.int32), 0, src_w - 1
    )

    tile_resized = tile[y_coords[:, np.newaxis], x_coords[np.newaxis, :]]

    # Normalize to [0, 1]
    tile_float = tile_resized.astype(np.float32)
    if tile_float.max() > 1.0:
        tile_float /= 255.0

    # Convert to (C, H, W) format and add batch dimension
    tile_nhwc = np.transpose(tile_float, (2, 0, 1))  # (C, H, W)
    tile_batch = np.expand_dims(tile_nhwc, axis=0)   # (1, C, H, W)

    return tile_batch


def detect_features(
    raster_path: str,
    model: dict,
    confidence_threshold: float = 0.5,
    iou_threshold: float = 0.45,
    tile_size: int = 640,
    overlap: int = 32,
    feedback=None,
) -> dict:
    """Run object detection on a raster using the loaded model.

    Processes the raster in tiles to handle large images, then merges
    overlapping detections using NMS.

    Args:
        raster_path: Path to the raster file to analyze.
        model: Model dict from load_model().
        confidence_threshold: Minimum confidence for detections.
        iou_threshold: IoU threshold for NMS.
        tile_size: Tile size in pixels for processing.
        overlap: Overlap between adjacent tiles.
        feedback: Optional progress callback.

    Returns:
        dict with:
            - 'detections': list of dicts with 'bbox', 'confidence',
              'class_id', 'class_name'
            - 'detection_count': int
            - 'total_tiles': int
    """
    check_dependencies()

    try:
        from osgeo import gdal
    except ImportError:
        raise RuntimeError("GDAL is required for raster I/O.")

    session = model["session"]
    input_name = model["input_name"]
    input_shape = model["input_shape"]
    output_names = model["output_names"]
    labels = model["labels"]
    model_type = model["model_type"]

    # Expected input size from model (H, W)
    _, _, model_h, model_w = input_shape
    if isinstance(model_h, int) and isinstance(model_w, int):
        model_input_size = (model_h, model_w)
    else:
        logger.info("Dynamic input shape %s, using tile_size %sx%s", input_shape, tile_size, tile_size)
        model_input_size = (tile_size, tile_size)

    # Open raster
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Cannot open raster: {raster_path}")

    raster_x = ds.RasterXSize
    raster_y = ds.RasterYSize

    all_detections = []
    tiles_processed = 0

    stride = tile_size - overlap
    n_tiles_x = max(1, (raster_x - overlap + stride - 1) // stride)
    n_tiles_y = max(1, (raster_y - overlap + stride - 1) // stride)
    total_tiles = n_tiles_x * n_tiles_y

    for ty in range(n_tiles_y):
        for tx in range(n_tiles_x):
            if feedback and feedback.isCanceled():
                ds = None
                return {"detections": all_detections,
                        "detection_count": len(all_detections),
                        "total_tiles": tiles_processed}

            # Compute tile window
            x_off = tx * stride
            y_off = ty * stride
            x_size = min(tile_size, raster_x - x_off)
            y_size = min(tile_size, raster_y - y_off)

            # Read tile
            tile_data = ds.ReadAsArray(x_off, y_off, x_size, y_size)
            if tile_data is None:
                continue

            # Handle band dimension
            if tile_data.ndim == 3:
                tile_array = np.transpose(tile_data, (1, 2, 0))  # (H, W, C)
            else:
                tile_array = tile_data  # (H, W)

            # Preprocess
            input_tensor = preprocess_tile(tile_array, model_input_size)

            # Run inference
            outputs = session.run(output_names, {input_name: input_tensor})

            # Postprocess
            if model_type == "object_detection":
                detections = _postprocess_yolo(
                    outputs, confidence_threshold, iou_threshold,
                    labels, x_off, y_off, tile_size, tile_array.shape,
                    model_input_size,
                )
                all_detections.extend(detections)

            tiles_processed += 1
            if feedback:
                feedback.setProgress(int(100 * tiles_processed / total_tiles))

    ds = None

    # Apply global NMS across all tiles
    if model_type == "object_detection" and len(all_detections) > 1:
        all_detections = _apply_nms(all_detections, iou_threshold)

    return {
        "detections": all_detections,
        "detection_count": len(all_detections),
        "total_tiles": total_tiles,
    }


def _postprocess_yolo(
    outputs: list,
    confidence_threshold: float,
    iou_threshold: float,
    labels: list,
    x_off: int,
    y_off: int,
    tile_size: int,
    tile_shape: tuple,
    model_input_size: tuple,
) -> list:
    """Postprocess YOLO model outputs to detection dicts.

    Handles different YOLO output formats (v5/v8/v11).
    """
    detections = []

    # Try standard YOLO output format
    try:
        # YOLOv8/v11: single output tensor (1, N, 6) — [x1, y1, x2, y2, conf, class]
        if len(outputs) == 1 and outputs[0].ndim == 3:
            out = outputs[0][0]  # (N, 6)
            for det in out:
                x1, y1, x2, y2, conf, cls_id = det
                if conf >= confidence_threshold:
                    detections.append(_make_detection(
                        x1, y1, x2, y2, float(conf), int(cls_id),
                        labels, x_off, y_off, tile_size, tile_shape,
                        model_input_size,
                    ))

        # YOLOv5: (1, N, 85) — [x_center, y_center, w, h, obj_conf, ...class_scores]
        elif len(outputs) == 1 and outputs[0].shape[-1] == 85:
            out = outputs[0][0]
            for det in out:
                scores = det[5:]
                cls_id = int(np.argmax(scores))
                conf = float(det[4] * scores[cls_id])
                if conf >= confidence_threshold:
                    cx, cy, w, h = det[0:4]
                    x1 = cx - w / 2
                    y1 = cy - h / 2
                    x2 = cx + w / 2
                    y2 = cy + h / 2
                    detections.append(_make_detection(
                        x1, y1, x2, y2, conf, cls_id,
                        labels, x_off, y_off, tile_size, tile_shape,
                        model_input_size,
                    ))

        # Multi-output: num_dets + boxes + scores + classes
        elif len(outputs) >= 4:
            num = int(outputs[0][0]) if outputs[0].ndim > 0 else 0
            boxes = outputs[1][0] if outputs[1].ndim > 1 else outputs[1]
            scores = outputs[2][0] if outputs[2].ndim > 1 else outputs[2]
            classes = outputs[3][0] if outputs[3].ndim > 1 else outputs[3]

            for i in range(min(num, len(boxes))):
                conf = float(scores[i])
                if conf >= confidence_threshold:
                    x1, y1, x2, y2 = boxes[i]
                    cls_id = int(classes[i])
                    detections.append(_make_detection(
                        x1, y1, x2, y2, conf, cls_id,
                        labels, x_off, y_off, tile_size, tile_shape,
                        model_input_size,
                    ))

    except Exception as e:
        logger.warning("Postprocessing error: %s", e)

    return detections


def _make_detection(
    x1, y1, x2, y2, confidence, class_id, labels,
    x_off, y_off, tile_size, tile_shape, model_input_size,
) -> dict:
    """Create a detection dict with proper coordinate scaling."""
    # Scale from model input size back to tile size
    mh, mw = model_input_size
    th, tw = tile_shape[:2]

    scale_x = tw / mw
    scale_y = th / mh

    # Map to tile coordinates
    tx1 = float(x1) * scale_x + x_off
    ty1 = float(y1) * scale_y + y_off
    tx2 = float(x2) * scale_x + x_off
    ty2 = float(y2) * scale_y + y_off

    class_name = str(labels[class_id]) if class_id < len(labels) else f"class_{class_id}"

    return {
        "bbox": [round(tx1, 2), round(ty1, 2), round(tx2, 2), round(ty2, 2)],
        "confidence": round(confidence, 4),
        "class_id": class_id,
        "class_name": class_name,
        "tile_offset": (x_off, y_off),
    }


def _apply_nms(detections: list, iou_threshold: float) -> list:
    """Apply Non-Maximum Suppression to remove duplicate detections.

    Args:
        detections: List of detection dicts.
        iou_threshold: IoU threshold for suppression.

    Returns:
        Filtered list of detections.
    """
    if not detections:
        return []

    # Group by class
    by_class = {}
    for det in detections:
        cls_id = det["class_id"]
        if cls_id not in by_class:
            by_class[cls_id] = []
        by_class[cls_id].append(det)

    result = []
    for cls_id, class_dets in by_class.items():
        # Sort by confidence descending
        class_dets.sort(key=lambda d: d["confidence"], reverse=True)

        keep = []
        while class_dets:
            best = class_dets.pop(0)
            keep.append(best)
            # Remove overlapping
            bbox = best["bbox"]
            class_dets = [
                d for d in class_dets
                if _compute_iou(bbox, d["bbox"]) < iou_threshold
            ]
        result.extend(keep)

    return result


def _compute_iou(bbox1: list, bbox2: list) -> float:
    """Compute Intersection over Union between two bounding boxes."""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])

    if x2 < x1 or y2 < y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0
