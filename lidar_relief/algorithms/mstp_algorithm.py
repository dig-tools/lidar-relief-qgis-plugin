"""mstp_algorithm.py — QGIS Processing wrapper for Multi-Scale Topographic Position.
exports: MstpAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  output is a multiband raster (3 bands, Byte)
"""

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
)

from ..core.raster_utils import (
    read_dem_to_array,
    write_array_to_raster,
)
from ..core.mstp import multi_scale_topographic_position


class MstpAlgorithm(QgsProcessingAlgorithm):
    """Multi-Scale Topographic Position from a DEM."""

    INPUT = "INPUT"
    LOCAL_RADIUS = "LOCAL_RADIUS"
    MESO_RADIUS = "MESO_RADIUS"
    BROAD_RADIUS = "BROAD_RADIUS"
    LIGHTNESS = "LIGHTNESS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "mstp"

    def displayName(self):
        return "Multi-Scale Topographic Position (MSTP)"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Generates an RGB composite of Topographic Position at three scales. "
            "Broad scale (Red) highlights large landforms. "
            "Meso scale (Green) highlights medium features. "
            "Local scale (Blue) highlights micro-topography like walls and ditches."
        )

    def createInstance(self):
        return MstpAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Input DEM",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LOCAL_RADIUS,
                "Local Scale Radius (pixels) -> Blue",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MESO_RADIUS,
                "Meso Scale Radius (pixels) -> Green",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=50,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.BROAD_RADIUS,
                "Broad Scale Radius (pixels) -> Red",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=500,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LIGHTNESS,
                "Lightness/Contrast Multiplier",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "MSTP (RGB) output",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        local_r = self.parameterAsInt(parameters, self.LOCAL_RADIUS, context)
        meso_r = self.parameterAsInt(parameters, self.MESO_RADIUS, context)
        broad_r = self.parameterAsInt(parameters, self.BROAD_RADIUS, context)
        lightness = self.parameterAsDouble(parameters, self.LIGHTNESS, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.setProgressText("Reading DEM...")
        dem_data = read_dem_to_array(source.source(), feedback)
        if feedback.isCanceled():
            return {}

        feedback.setProgressText("Computing MSTP...")
        rgb_result = multi_scale_topographic_position(
            dem_data.array,
            local_r,
            meso_r,
            broad_r,
            lightness,
            feedback,
        )

        if feedback.isCanceled():
            return {}

        feedback.setProgressText("Writing RGB output...")
        # Note: write_array_to_raster in raster_utils.py needs to handle 3D arrays
        # (It already does, we just pass the array and it loops over bands if len(shape)==3)
        write_array_to_raster(
            rgb_result,
            output_path,
            dem_data.geotransform,
            dem_data.projection,
            0,  # nodata value for uint8
        )

        return {self.OUTPUT: output_path}
