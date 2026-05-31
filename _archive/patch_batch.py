import re

with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
    content = f.read()

# 1. Update imports
content = content.replace("from ..core.presets import get_preset_config", "from ..core.presets import PRESETS, get_preset")

# 2. Add keys to BatchAlgorithm class
keys_str = """
    SVF_RADIUS = "SVF_RADIUS"
    SVF_NOISE = "SVF_NOISE"
    OPENNESS_RADIUS = "OPENNESS_RADIUS"
    SLRM_RADIUS = "SLRM_RADIUS"
    LD_MIN_RAD = "LD_MIN_RAD"
    LD_MAX_RAD = "LD_MAX_RAD"
    MSTP_LOCAL = "MSTP_LOCAL"
    MSTP_MESO = "MSTP_MESO"
    MSTP_BROAD = "MSTP_BROAD"

    _PRESET_OPTIONS = ["Manual", "Flat / Agricultural", "Forested", "Upland / Steep", "Coastal"]
    _PRESET_KEYS = [None, "flat_agricultural", "forested", "upland_steep", "coastal"]
"""
content = re.sub(r'    _PRESET_OPTIONS = \["Archaeology", "Geomorphology"\]', keys_str.strip('\n'), content)

# 3. Add parameters to initAlgorithm
params_str = """
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SVF_RADIUS, "SVF Search Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=10
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SVF_NOISE, "SVF Noise Level", type=QgsProcessingParameterNumber.Integer, defaultValue=0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.OPENNESS_RADIUS, "Openness Search Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=15
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SLRM_RADIUS, "SLRM Trend Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=20
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LD_MIN_RAD, "Local Dominance Min Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=10
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LD_MAX_RAD, "Local Dominance Max Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=20
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MSTP_LOCAL, "MSTP Local Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=3
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MSTP_MESO, "MSTP Meso Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=20
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MSTP_BROAD, "MSTP Broad Radius (px)", type=QgsProcessingParameterNumber.Integer, defaultValue=100
            )
        )
"""

content = content.replace("defaultValue=1,  # Meso default\n            )\n        )", "defaultValue=1,  # Meso default\n            )\n        )\n" + params_str)

# We also need to import QgsProcessingParameterNumber
content = content.replace("QgsProcessingParameterBoolean,", "QgsProcessingParameterBoolean,\n    QgsProcessingParameterNumber,")

# 4. Update processAlgorithm
process_algo_new = """
        preset_idx = self.parameterAsEnum(parameters, self.PRESET, context)
        preset_key = self._PRESET_KEYS[preset_idx]
        
        # Read manual parameters first
        p_cfg = {
            "svf_radius": self.parameterAsInt(parameters, self.SVF_RADIUS, context),
            "svf_noise": self.parameterAsInt(parameters, self.SVF_NOISE, context),
            "openness_radius": self.parameterAsInt(parameters, self.OPENNESS_RADIUS, context),
            "slrm_radius": self.parameterAsInt(parameters, self.SLRM_RADIUS, context),
            "ld_min_rad": self.parameterAsInt(parameters, self.LD_MIN_RAD, context),
            "ld_max_rad": self.parameterAsInt(parameters, self.LD_MAX_RAD, context),
            "mstp_local": self.parameterAsInt(parameters, self.MSTP_LOCAL, context),
            "mstp_meso": self.parameterAsInt(parameters, self.MSTP_MESO, context),
            "mstp_broad": self.parameterAsInt(parameters, self.MSTP_BROAD, context),
        }
        
        # Override with preset if not manual
        if preset_key is not None:
            preset = get_preset(preset_key)
            p_cfg["svf_radius"] = preset["svf"]["search_radius"]
            p_cfg["svf_noise"] = preset["svf"]["noise_level"]
            p_cfg["openness_radius"] = preset["openness"]["search_radius"]
            p_cfg["slrm_radius"] = preset["slrm"]["trend_radius"]
            p_cfg["ld_min_rad"] = preset["local_dominance"]["min_rad"]
            p_cfg["ld_max_rad"] = preset["local_dominance"]["max_rad"]
"""

old_process = """
        preset_idx = self.parameterAsEnum(parameters, self.PRESET, context)

        preset_name = self._PRESET_OPTIONS[preset_idx]
        cellsize_x = source.rasterUnitsPerPixelX()
        cellsize_y = source.rasterUnitsPerPixelY()
        cellsize = (cellsize_x + cellsize_y) / 2.0
        p_cfg = get_preset_config(preset_name, cellsize)
"""

content = content.replace(old_process.strip(), process_algo_new.strip())

with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
    f.write(content)
