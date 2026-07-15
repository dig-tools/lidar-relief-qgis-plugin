"""svf_algorithm.py — QGIS Processing wrapper for Sky-View Factor.
exports: SvfAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  all raster I/O through core.raster_utils
  computation through core.svf
  enum index maps to [8, 16, 32] directions
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
    process_in_tiles,
)
from ..core.svf import sky_view_factor
from ..styling import ReliefLayerPostProcessor


class SvfAlgorithm(QgsProcessingAlgorithm):
    """Sky-View Factor — portion of sky visible from each cell."""

    INPUT = "INPUT"
    NUM_DIRECTIONS = "NUM_DIRECTIONS"
    SEARCH_RADIUS = "SEARCH_RADIUS"
    NOISE_LEVEL = "NOISE_LEVEL"
    OUTPUT = "OUTPUT"

    _DIRECTION_OPTIONS = ["8 (fast)", "16 (standard)", "32 (quality)"]
    _DIRECTION_VALUES = [8, 16, 32]

    # -- metadata -----------------------------------------------------------

    def name(self):
        return "sky_view_factor"

    def displayName(self):
        return "Sky-View Factor (SVF)"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Computes the Sky-View Factor for each cell — the proportion "
            "of the sky hemisphere visible from that point. Values range "
            "from 0 (completely obstructed) to 1 (flat open terrain). "
            "SVF excels at revealing subtle concave features such as "
            "ditches and hollow ways."
        )

    def createInstance(self):
        return SvfAlgorithm()

    # -- parameters ---------------------------------------------------------

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Input DEM",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.NUM_DIRECTIONS,
                "Number of azimuth directions",
                options=self._DIRECTION_OPTIONS,
                defaultValue=1,  # index 1 → 16 (standard)
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEARCH_RADIUS,
                "Search radius (pixels)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=10,
                minValue=1,
                maxValue=100,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.NOISE_LEVEL,
                "Noise removal look-ahead",
                options=["None", "Low", "Medium", "High"],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "SVF output",
            )
        )

    # -- processing ---------------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):
        """Run Sky-View Factor computation.

        Rules:
            Map enum index to actual direction count via _DIRECTION_VALUES.
            Abort gracefully on cancel.
        """
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        int_dir_index = self.parameterAsEnum(parameters, self.NUM_DIRECTIONS, context)
        int_search_radius = self.parameterAsInt(parameters, self.SEARCH_RADIUS, context)
        int_noise_level = self.parameterAsEnum(parameters, self.NOISE_LEVEL, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        int_num_directions = self._DIRECTION_VALUES[int_dir_index]

        feedback.setProgressText(
            f"Computing Sky-View Factor ({int_num_directions} directions) in tiles..."
        )

        process_in_tiles(
            source_path=source.source(),
            output_path=output_path,
            algorithm_func=sky_view_factor,
            halo_size=int_search_radius,
            tile_size=2048,
            feedback=feedback,
            num_directions=int_num_directions,
            search_radius=int_search_radius,
            noise_level=int_noise_level,
        )

        if feedback.isCanceled():
            return {}

        if context.willLoadLayerOnCompletion(output_path):
            details = context.layerToLoadOnCompletionDetails(output_path)
            details.setPostProcessor(
                ReliefLayerPostProcessor(self.displayName(), stretch_type="stddev")
            )

        return {self.OUTPUT: output_path}
