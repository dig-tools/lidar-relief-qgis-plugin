"""slope_algorithm.py — QGIS Processing wrapper for Slope computation.
exports: SlopeAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  all raster I/O through core.raster_utils
  computation through core.slope
  enum index maps to ['degrees', 'percent']
  check feedback.isCanceled() between major steps
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
    apply_nodata_mask,
    get_cell_size,
)
from ..core.slope import compute_slope


class SlopeAlgorithm(QgsProcessingAlgorithm):
    """Slope — terrain gradient in degrees or percent."""

    INPUT = "INPUT"
    UNITS = "UNITS"
    OUTPUT = "OUTPUT"

    _UNIT_OPTIONS = ["Degrees", "Percent"]
    _UNIT_VALUES = ["degrees", "percent"]

    # -- metadata -----------------------------------------------------------

    def name(self):
        return "slope"

    def displayName(self):
        return "Slope"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Computes terrain slope from a DEM. Output can be in "
            "degrees (0–90) or percent (0–∞). Slope highlights "
            "edges of features such as banks, scarps, and walls."
        )

    def createInstance(self):
        return SlopeAlgorithm()

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
                self.UNITS,
                "Output units",
                options=self._UNIT_OPTIONS,
                defaultValue=0,  # Degrees
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                "Slope output",
            )
        )

    # -- processing ---------------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):
        """Run slope computation.

        Rules:
            Map enum index to unit string via _UNIT_VALUES.
            Abort gracefully on cancel.
        """
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        int_unit_index = self.parameterAsEnum(parameters, self.UNITS, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        str_units = self._UNIT_VALUES[int_unit_index]

        feedback.setProgressText("Reading DEM...")
        dem_data = read_dem_to_array(source.source(), feedback)

        if feedback.isCanceled():
            return {}

        float_cellsize = get_cell_size(dem_data.geotransform)

        feedback.setProgressText(f"Computing slope ({str_units})...")
        array_result = compute_slope(dem_data.array, float_cellsize, str_units)

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
