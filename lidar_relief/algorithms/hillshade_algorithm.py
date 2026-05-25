"""hillshade_algorithm.py — QGIS Processing wrapper for multi-directional hillshade.
exports: HillshadeAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  all raster I/O through core.raster_utils
  computation through core.hillshade
  check feedback.isCanceled() between major steps
"""

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterRasterDestination,
)

from ..core.raster_utils import (
    read_dem_to_array,
    write_array_to_raster,
    apply_nodata_mask,
    get_cell_size,
)
from ..core.hillshade import multidirectional_hillshade


class HillshadeAlgorithm(QgsProcessingAlgorithm):
    """Multi-directional hillshade from a DEM raster layer."""

    INPUT = 'INPUT'
    AZIMUTHS = 'AZIMUTHS'
    ALTITUDE = 'ALTITUDE'
    OUTPUT = 'OUTPUT'

    # -- metadata -----------------------------------------------------------

    def name(self):
        return 'multidirectional_hillshade'

    def displayName(self):
        return 'Multi-directional Hillshade'

    def group(self):
        return 'LiDAR Relief'

    def groupId(self):
        return 'lidar_relief'

    def shortHelpString(self):
        return (
            'Generates a multi-directional hillshade by blending '
            'hillshades from several sun azimuth angles. Useful for '
            'revealing subtle topographic features that a single-'
            'direction hillshade would miss.'
        )

    def createInstance(self):
        return HillshadeAlgorithm()

    # -- parameters ---------------------------------------------------------

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                'Input DEM',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.AZIMUTHS,
                'Sun azimuth angles (comma-separated degrees)',
                defaultValue='315,45,135,225,270,360',
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ALTITUDE,
                'Sun altitude (degrees)',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=45.0,
                minValue=0.0,
                maxValue=90.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                'Hillshade output',
            )
        )

    # -- processing ---------------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):
        """Run multi-directional hillshade.

        Rules:
            Parse AZIMUTHS as comma-separated floats.
            Abort gracefully on cancel.
        """
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        azimuths_str = self.parameterAsString(parameters, self.AZIMUTHS, context)
        float_altitude = self.parameterAsDouble(parameters, self.ALTITUDE, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        # Parse azimuths
        list_float_azimuths = [
            float(a.strip()) for a in azimuths_str.split(',') if a.strip()
        ]

        feedback.setProgressText('Reading DEM...')
        dem_data = read_dem_to_array(source.source(), feedback)

        if feedback.isCanceled():
            return {}

        float_cellsize = get_cell_size(dem_data.geotransform)

        feedback.setProgressText('Computing multi-directional hillshade...')
        array_result = multidirectional_hillshade(
            dem_data.array,
            float_cellsize,
            list_float_azimuths,
            float_altitude,
        )

        if feedback.isCanceled():
            return {}

        feedback.setProgressText('Writing output...')
        array_result = apply_nodata_mask(dem_data.array, array_result, dem_data.nodata_mask)
        write_array_to_raster(
            array_result,
            output_path,
            dem_data.geotransform,
            dem_data.projection,
            dem_data.nodata,
        )

        return {self.OUTPUT: output_path}
