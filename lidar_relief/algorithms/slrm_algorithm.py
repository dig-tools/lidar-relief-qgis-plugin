"""slrm_algorithm.py — QGIS Processing wrapper for Simple Local Relief Model.
exports: SlrmAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  all raster I/O through core.raster_utils
  computation through core.slrm
  check feedback.isCanceled() between major steps
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
    apply_nodata_mask,
)
from ..core.slrm import simple_local_relief_model


class SlrmAlgorithm(QgsProcessingAlgorithm):
    """Simple Local Relief Model — removes large-scale topography."""

    INPUT = "INPUT"
    RADIUS = "RADIUS"
    OUTPUT = "OUTPUT"

    # -- metadata -----------------------------------------------------------

    def name(self):
        return "simple_local_relief_model"

    def displayName(self):
        return "Simple Local Relief Model (SLRM)"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Computes a Simple Local Relief Model by subtracting a "
            "smoothed (low-pass) version of the DEM from the original. "
            "This highlights micro-relief features such as ditches, "
            "banks, and ridge-and-furrow while suppressing broad "
            "topographic trends."
        )

    def createInstance(self):
        return SlrmAlgorithm()

    # -- parameters ---------------------------------------------------------

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Input DEM",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RADIUS,
                "Smoothing radius (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=20,
                minValue=2,
                maxValue=500,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "SLRM output",
            )
        )

    # -- processing ---------------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):
        """Run Simple Local Relief Model.

        Rules:
            Abort gracefully on cancel.
        """
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        int_radius = self.parameterAsInt(parameters, self.RADIUS, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.setProgressText("Reading DEM...")
        dem_data = read_dem_to_array(source.source(), feedback)

        if feedback.isCanceled():
            return {}

        feedback.setProgressText("Computing Simple Local Relief Model...")
        array_result = simple_local_relief_model(dem_data.array, int_radius)

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
