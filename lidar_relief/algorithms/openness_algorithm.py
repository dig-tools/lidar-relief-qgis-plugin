"""openness_algorithm.py — QGIS Processing wrapper for Topographic Openness.
exports: OpennessAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  all raster I/O through core.raster_utils
  check feedback.isCanceled() between major steps
"""

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
)

from ..core.raster_utils import (
    read_dem_to_array,
    write_array_to_raster,
    apply_nodata_mask,
    get_cell_size,
)
from ..core.openness import topographic_openness


class OpennessAlgorithm(QgsProcessingAlgorithm):
    """Topographic Openness from a DEM raster layer."""

    INPUT = "INPUT"
    OPENNESS_TYPE = "OPENNESS_TYPE"
    NUM_DIRECTIONS = "NUM_DIRECTIONS"
    SEARCH_RADIUS = "SEARCH_RADIUS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "topographic_openness"

    def displayName(self):
        return "Topographic Openness"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Generates Topographic Openness (Positive or Negative). "
            "Positive Openness highlights convex features like mounds and ridges. "
            "Negative Openness highlights concave features like pits and ditches."
        )

    def createInstance(self):
        return OpennessAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Input DEM",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OPENNESS_TYPE,
                "Openness Type",
                options=["Positive (Convex)", "Negative (Concave)"],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.NUM_DIRECTIONS,
                "Search Directions",
                options=["8 (fast)", "16 (standard)", "32 (quality)"],
                defaultValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEARCH_RADIUS,
                "Search Radius (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=20,
                minValue=1,
                maxValue=500,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Openness output",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        type_idx = self.parameterAsEnum(parameters, self.OPENNESS_TYPE, context)
        dir_idx = self.parameterAsEnum(parameters, self.NUM_DIRECTIONS, context)
        radius = self.parameterAsInt(parameters, self.SEARCH_RADIUS, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        is_negative = type_idx == 1
        num_dirs = [8, 16, 32][dir_idx]

        feedback.setProgressText("Reading DEM...")
        dem_data = read_dem_to_array(source.source(), feedback)
        if feedback.isCanceled():
            return {}
        float_cellsize = get_cell_size(dem_data.geotransform)

        feedback.setProgressText(f"Computing Openness ({num_dirs} dirs, r={radius})...")
        array_result = topographic_openness(
            dem_data.array,
            float_cellsize,
            num_dirs,
            radius,
            is_negative,
            feedback,
        )

        if feedback.isCanceled():
            return {}

        feedback.setProgressText("Writing output...")
        array_result = apply_nodata_mask(
            dem_data.array, array_result, dem_data.nodata_mask
        )
        write_array_to_raster(
            array_result,
            output_path,
            dem_data.geotransform,
            dem_data.projection,
            dem_data.nodata,
        )

        return {self.OUTPUT: output_path}
