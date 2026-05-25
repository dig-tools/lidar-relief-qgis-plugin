"""batch_algorithm.py — QGIS Processing wrapper for batch multi-algorithm run.
exports: BatchAlgorithm
used_by: provider.py → loadAlgorithms
rules:
  read DEM once, run each enabled algorithm sequentially
  all raster I/O through core.raster_utils
  use default params for each algorithm in batch mode
  check feedback.isCanceled() between major steps
  report progress as percentage across enabled algorithms
"""

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)

from ..core.raster_utils import (
    read_dem_to_array,
    write_array_to_raster,
    apply_nodata_mask,
    get_cell_size,
)
from ..core.hillshade import multidirectional_hillshade
from ..core.slrm import simple_local_relief_model
from ..core.svf import sky_view_factor
from ..core.slope import compute_slope


class BatchAlgorithm(QgsProcessingAlgorithm):
    """Run multiple LiDAR relief algorithms on the same DEM in one step."""

    INPUT = "INPUT"
    RUN_HILLSHADE = "RUN_HILLSHADE"
    RUN_SLRM = "RUN_SLRM"
    RUN_SVF = "RUN_SVF"
    RUN_SLOPE = "RUN_SLOPE"
    HILLSHADE_OUTPUT = "HILLSHADE_OUTPUT"
    SLRM_OUTPUT = "SLRM_OUTPUT"
    SVF_OUTPUT = "SVF_OUTPUT"
    SLOPE_OUTPUT = "SLOPE_OUTPUT"

    # -- metadata -----------------------------------------------------------

    def name(self):
        return "batch_relief"

    def displayName(self):
        return "Batch Relief Visualisation"

    def group(self):
        return "LiDAR Relief"

    def groupId(self):
        return "lidar_relief"

    def shortHelpString(self):
        return (
            "Runs multiple relief visualisation algorithms on the same "
            "DEM in a single step. The DEM is read once and each "
            "selected algorithm is executed with default parameters. "
            "Disable any algorithms you do not need via the checkboxes."
        )

    def createInstance(self):
        return BatchAlgorithm()

    # -- parameters ---------------------------------------------------------

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                "Input DEM",
            )
        )

        # Toggle switches
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.RUN_HILLSHADE,
                "Run Multi-directional Hillshade",
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.RUN_SLRM,
                "Run Simple Local Relief Model",
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.RUN_SVF,
                "Run Sky-View Factor",
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.RUN_SLOPE,
                "Run Slope",
                defaultValue=True,
            )
        )

        # Optional outputs
        hillshade_param = QgsProcessingParameterRasterDestination(
            self.HILLSHADE_OUTPUT,
            "Hillshade output",
            optional=True,
            createByDefault=True,
        )
        self.addParameter(hillshade_param)

        slrm_param = QgsProcessingParameterRasterDestination(
            self.SLRM_OUTPUT,
            "SLRM output",
            optional=True,
            createByDefault=True,
        )
        self.addParameter(slrm_param)

        svf_param = QgsProcessingParameterRasterDestination(
            self.SVF_OUTPUT,
            "SVF output",
            optional=True,
            createByDefault=True,
        )
        self.addParameter(svf_param)

        slope_param = QgsProcessingParameterRasterDestination(
            self.SLOPE_OUTPUT,
            "Slope output",
            optional=True,
            createByDefault=True,
        )
        self.addParameter(slope_param)

    # -- processing ---------------------------------------------------------

    def processAlgorithm(self, parameters, context, feedback):
        """Run enabled algorithms sequentially on a single DEM read.

        Rules:
            Read DEM once.
            Track progress as percentage of enabled algorithms completed.
            Use default algorithm params: azimuths 315,45,135,225,270,360;
            altitude 45; SLRM radius 20; SVF 16 dirs, radius 10;
            slope degrees.
        """
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        bool_hillshade = self.parameterAsBool(parameters, self.RUN_HILLSHADE, context)
        bool_slrm = self.parameterAsBool(parameters, self.RUN_SLRM, context)
        bool_svf = self.parameterAsBool(parameters, self.RUN_SVF, context)
        bool_slope = self.parameterAsBool(parameters, self.RUN_SLOPE, context)

        dict_results = {}

        # Build task list for progress tracking
        list_tasks = []
        if bool_hillshade:
            list_tasks.append("hillshade")
        if bool_slrm:
            list_tasks.append("slrm")
        if bool_svf:
            list_tasks.append("svf")
        if bool_slope:
            list_tasks.append("slope")

        if not list_tasks:
            feedback.reportError("No algorithms selected — nothing to do.")
            return {}

        int_total = len(list_tasks)
        int_done = 0

        # Read DEM once
        feedback.setProgressText("Reading DEM...")
        dem_data = read_dem_to_array(source.source(), feedback)

        if feedback.isCanceled():
            return {}

        float_cellsize = get_cell_size(dem_data.geotransform)

        # -- Hillshade -------------------------------------------------------
        if bool_hillshade:
            if feedback.isCanceled():
                return dict_results

            feedback.setProgressText("Computing multi-directional hillshade...")
            array_hs = multidirectional_hillshade(
                dem_data.array,
                float_cellsize,
                [315.0, 45.0, 135.0, 225.0, 270.0, 360.0],
                45.0,
            )
            array_hs = apply_nodata_mask(dem_data.array, array_hs, dem_data.nodata_mask)
            hs_path = self.parameterAsOutputLayer(
                parameters, self.HILLSHADE_OUTPUT, context
            )
            write_array_to_raster(
                array_hs,
                hs_path,
                dem_data.geotransform,
                dem_data.projection,
                dem_data.nodata,
            )
            dict_results[self.HILLSHADE_OUTPUT] = hs_path
            int_done += 1
            feedback.setProgress(int(100 * int_done / int_total))

        # -- SLRM ------------------------------------------------------------
        if bool_slrm:
            if feedback.isCanceled():
                return dict_results

            feedback.setProgressText("Computing Simple Local Relief Model...")
            array_slrm = simple_local_relief_model(dem_data.array, 20)
            array_slrm = apply_nodata_mask(
                dem_data.array, array_slrm, dem_data.nodata_mask
            )
            slrm_path = self.parameterAsOutputLayer(
                parameters, self.SLRM_OUTPUT, context
            )
            write_array_to_raster(
                array_slrm,
                slrm_path,
                dem_data.geotransform,
                dem_data.projection,
                dem_data.nodata,
            )
            dict_results[self.SLRM_OUTPUT] = slrm_path
            int_done += 1
            feedback.setProgress(int(100 * int_done / int_total))

        # -- SVF --------------------------------------------------------------
        if bool_svf:
            if feedback.isCanceled():
                return dict_results

            feedback.setProgressText("Computing Sky-View Factor (16 directions)...")
            array_svf = sky_view_factor(dem_data.array, float_cellsize, 16, 10)
            array_svf = apply_nodata_mask(
                dem_data.array, array_svf, dem_data.nodata_mask
            )
            svf_path = self.parameterAsOutputLayer(parameters, self.SVF_OUTPUT, context)
            write_array_to_raster(
                array_svf,
                svf_path,
                dem_data.geotransform,
                dem_data.projection,
                dem_data.nodata,
            )
            dict_results[self.SVF_OUTPUT] = svf_path
            int_done += 1
            feedback.setProgress(int(100 * int_done / int_total))

        # -- Slope ------------------------------------------------------------
        if bool_slope:
            if feedback.isCanceled():
                return dict_results

            feedback.setProgressText("Computing slope (degrees)...")
            array_slope = compute_slope(dem_data.array, float_cellsize, "degrees")
            array_slope = apply_nodata_mask(
                dem_data.array, array_slope, dem_data.nodata_mask
            )
            slope_path = self.parameterAsOutputLayer(
                parameters, self.SLOPE_OUTPUT, context
            )
            write_array_to_raster(
                array_slope,
                slope_path,
                dem_data.geotransform,
                dem_data.projection,
                dem_data.nodata,
            )
            dict_results[self.SLOPE_OUTPUT] = slope_path
            int_done += 1
            feedback.setProgress(int(100 * int_done / int_total))

        return dict_results
