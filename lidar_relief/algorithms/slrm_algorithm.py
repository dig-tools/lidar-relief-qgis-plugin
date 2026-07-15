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
    process_in_tiles,
)
from ..core.slrm import simple_local_relief_model
from ..styling import ReliefLayerPostProcessor


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
                type=QgsProcessingParameterNumber.Type.Integer,
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

        feedback.setProgressText("Computing Simple Local Relief Model in tiles...")

        def slrm_wrapper(block, cellsize, radius):
            return simple_local_relief_model(block, radius)

        process_in_tiles(
            source_path=source.source(),
            output_path=output_path,
            algorithm_func=slrm_wrapper,
            halo_size=int_radius,
            tile_size=2048,
            feedback=feedback,
            radius=int_radius,
        )

        if feedback.isCanceled():
            return {}

        if context.willLoadLayerOnCompletion(output_path):
            details = context.layerToLoadOnCompletionDetails(output_path)
            details.setPostProcessor(
                ReliefLayerPostProcessor(self.displayName(), stretch_type="stddev")
            )

        return {self.OUTPUT: output_path}
