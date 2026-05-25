"""blend_algorithm.py — QGIS Processing wrapper for Raster Blending.
exports: BlendAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  all raster I/O through core.raster_utils
"""

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterRasterDestination,
)

from ..core.raster_utils import (
    read_dem_to_array,
    write_array_to_raster,
)
from ..core.blend import blend_rasters
import numpy as np


class BlendAlgorithm(QgsProcessingAlgorithm):
    """Blends two raster layers."""

    INPUT_A = "INPUT_A"
    INPUT_B = "INPUT_B"
    BLEND_MODE = "BLEND_MODE"
    OUTPUT = "OUTPUT"

    def name(self):
        return "blend_rasters"

    def displayName(self):
        return "Blend Visualizations"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Blends two visualization rasters (e.g., Hillshade and SVF) "
            "using standard blending modes like Multiply, Screen, or Overlay."
        )

    def createInstance(self):
        return BlendAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_A,
                "Base Layer (e.g. Hillshade)",
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_B,
                "Blend Layer (e.g. SVF, SLRM)",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.BLEND_MODE,
                "Blend Mode",
                options=["Multiply", "Screen", "Overlay"],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Blended output",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source_a = self.parameterAsRasterLayer(parameters, self.INPUT_A, context)
        source_b = self.parameterAsRasterLayer(parameters, self.INPUT_B, context)
        mode_idx = self.parameterAsEnum(parameters, self.BLEND_MODE, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        mode_str = ["multiply", "screen", "overlay"][mode_idx]

        feedback.setProgressText("Reading Base Layer...")
        data_a = read_dem_to_array(source_a.source(), feedback)

        feedback.setProgressText("Reading Blend Layer...")
        data_b = read_dem_to_array(source_b.source(), feedback)

        if feedback.isCanceled():
            return {}

        if data_a.array.shape != data_b.array.shape:
            feedback.reportError("Input rasters must have the same dimensions.")
            return {}

        # Scale inputs if they are not 0-255 (e.g. SVF is 0-1, SLRM is negative/positive)
        # SVF is typically [0, 1]. Multiply by 255.
        arr_b = data_b.array
        if np.nanmax(arr_b) <= 1.0 and np.nanmin(arr_b) >= 0.0:
            arr_b = arr_b * 255.0

        # SLRM could be -5 to 5. We should stretch to 0-255 if it has negative values.
        if np.nanmin(arr_b) < 0:
            min_val = np.nanmin(arr_b)
            max_val = np.nanmax(arr_b)
            if max_val > min_val:
                arr_b = (arr_b - min_val) / (max_val - min_val) * 255.0
            else:
                arr_b = np.full_like(arr_b, 127.0)

        arr_a = data_a.array
        if np.nanmax(arr_a) <= 1.0 and np.nanmin(arr_a) >= 0.0:
            arr_a = arr_a * 255.0

        feedback.setProgressText(f"Blending layers using {mode_str}...")
        blended = blend_rasters(arr_a, arr_b, mode_str, feedback)

        if feedback.isCanceled():
            return {}

        feedback.setProgressText("Writing output...")
        write_array_to_raster(
            blended,
            output_path,
            data_a.geotransform,
            data_a.projection,
            data_a.nodata,
        )

        return {self.OUTPUT: output_path}
