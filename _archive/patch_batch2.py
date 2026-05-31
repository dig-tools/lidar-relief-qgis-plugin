import re

with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
    content = f.read()

# 1. Add new keys to BatchAlgorithm class
keys_to_add = """
    SVF_NUM_DIRECTIONS = "SVF_NUM_DIRECTIONS"
    OPENNESS_NUM_DIRECTIONS = "OPENNESS_NUM_DIRECTIONS"
    LD_OBSERVER_HEIGHT = "LD_OBSERVER_HEIGHT"
"""
content = content.replace('    SVF_RADIUS = "SVF_RADIUS"', keys_to_add.strip('\n') + '\n    SVF_RADIUS = "SVF_RADIUS"')

# 2. Add parameters to initAlgorithm
params_to_add = """
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SVF_NUM_DIRECTIONS, "SVF Directions", type=QgsProcessingParameterNumber.Integer, defaultValue=16
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.OPENNESS_NUM_DIRECTIONS, "Openness Directions", type=QgsProcessingParameterNumber.Integer, defaultValue=16
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.LD_OBSERVER_HEIGHT, "Local Dominance Observer Height (m)", type=QgsProcessingParameterNumber.Double, defaultValue=1.7
            )
        )
"""
content = content.replace('            QgsProcessingParameterNumber(\n                self.SVF_RADIUS,', params_to_add.strip('\n') + '\n        self.addParameter(\n            QgsProcessingParameterNumber(\n                self.SVF_RADIUS,')

# 3. Update p_cfg in processAlgorithm
new_p_cfg_manual = """
        p_cfg = {
            "svf_num_directions": self.parameterAsInt(parameters, self.SVF_NUM_DIRECTIONS, context),
            "openness_num_directions": self.parameterAsInt(parameters, self.OPENNESS_NUM_DIRECTIONS, context),
            "ld_observer_height": self.parameterAsDouble(parameters, self.LD_OBSERVER_HEIGHT, context),
            "svf_radius": self.parameterAsInt(parameters, self.SVF_RADIUS, context),
"""
content = re.sub(r'        p_cfg = \{\n            "svf_radius": self\.parameterAsInt\(parameters, self\.SVF_RADIUS, context\),', new_p_cfg_manual.strip('\n'), content)

new_p_cfg_override = """
            p_cfg["ld_min_rad"] = preset["local_dominance"]["min_rad"]
            p_cfg["ld_max_rad"] = preset["local_dominance"]["max_rad"]
            p_cfg["svf_num_directions"] = preset["svf"]["num_directions"]
            p_cfg["openness_num_directions"] = preset["openness"]["num_directions"]
            p_cfg["ld_observer_height"] = preset["local_dominance"]["observer_height"]
"""
content = re.sub(r'            p_cfg\["ld_min_rad"\] = preset\["local_dominance"\]\["min_rad"\]\n            p_cfg\["ld_max_rad"\] = preset\["local_dominance"\]\["max_rad"\]', new_p_cfg_override.strip('\n'), content)

# 4. Pass parameters through to algorithm calls (topographic_openness, compute_local_dominance, sky_view_factor)

# svf calls
content = re.sub(r'num_directions=16,(\s*)search_radius=p_cfg\["svf_radius"\]', 
                 r'num_directions=p_cfg["svf_num_directions"],\g<1>search_radius=p_cfg["svf_radius"]', content)
content = re.sub(r'search_radius=p_cfg\["svf_radius"\],\s*noise_level=p_cfg\["svf_noise"\]',
                 r'num_directions=p_cfg["svf_num_directions"], search_radius=p_cfg["svf_radius"], noise_level=p_cfg["svf_noise"]', content)
content = re.sub(r'search_radius=p_cfg\["svf_radius"\] \* 3,\s*noise_level=p_cfg\["svf_noise"\]',
                 r'num_directions=p_cfg["svf_num_directions"], search_radius=p_cfg["svf_radius"] * 3, noise_level=p_cfg["svf_noise"]', content)
content = re.sub(r'search_radius=radius,\s*anisotropy_dir=',
                 r'num_directions=p_cfg["svf_num_directions"], search_radius=radius, anisotropy_dir=', content)

# openness calls
content = re.sub(r'num_directions=16,(\s*)search_radius=p_cfg\["openness_radius"\]', 
                 r'num_directions=p_cfg["openness_num_directions"],\g<1>search_radius=p_cfg["openness_radius"]', content)
                 
# local dominance calls
content = re.sub(r'max_rad=p_cfg\["ld_max_rad"\],(\s*)feedback=feedback',
                 r'max_rad=p_cfg["ld_max_rad"], observer_h=p_cfg["ld_observer_height"],\g<1>feedback=feedback', content)


with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
    f.write(content)

