# Fix batch_algorithm.py
with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
    text = f.read()

import re

# We will replace the whole assignments.
text = re.sub(
    r'                open_pos = \([\s\S]*?topographic_openness\([\s\S]*?is_negative=False,\n                    feedback=feedback,\n                \)\n                / 90\.0(?:  # fmt: skip)?\n            \)\.clip\(0, 1\)',
    r'                open_pos_raw = topographic_openness(\n                    block,\n                    cellsize,\n                    num_directions=p_cfg["openness_num_directions"],\n                    search_radius=p_cfg["openness_radius"],\n                    is_negative=False,\n                    feedback=feedback,\n                )\n                open_pos = (open_pos_raw / 90.0).clip(0, 1)',
    text
)

# For open_neg
text = re.sub(
    r'                open_neg = \([\s\S]*?topographic_openness\([\s\S]*?is_negative=True,\n                    feedback=feedback,\n                \)\n                / 90\.0(?:  # fmt: skip)?\n            \)\.clip\(0, 1\)',
    r'                open_neg_raw = topographic_openness(\n                    block,\n                    cellsize,\n                    num_directions=p_cfg["openness_num_directions"],\n                    search_radius=p_cfg["openness_radius"],\n                    is_negative=True,\n                    feedback=feedback,\n                )\n                open_neg = (open_neg_raw / 90.0).clip(0, 1)',
    text
)

# For local_dom
text = re.sub(
    r'                local_dom = \([\s\S]*?compute_local_dominance\([\s\S]*?feedback=feedback,\n                \)\n                / 255\.0(?:  # fmt: skip)?\n            \)\.clip\(0, 1\)',
    r'                local_dom_raw = compute_local_dominance(\n                    block,\n                    cellsize,\n                    min_rad=p_cfg["ld_min_rad"],\n                    max_rad=p_cfg["ld_max_rad"],\n                    observer_h=p_cfg["ld_observer_height"],\n                    feedback=feedback,\n                )\n                local_dom = (local_dom_raw / 255.0).clip(0, 1)',
    text
)
with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
    f.write(text)

# Fix local_dominance.py
with open("lidar_relief/core/local_dominance.py", "r") as f:
    text = f.read()

# Replace the slice block.
# We are replacing:
#            target_z = padded_dem[
#                pad_w + dy : pad_w + dy + rows, pad_w + dx : pad_w + dx + cols
#            ]
# Or any variant created by ruff/flake8 attempts.
text = re.sub(
    r'            # Slice padded DEM to get target_z\n            target_z = padded_dem\[[\s\S]*?\]',
    r'            # Slice padded DEM to get target_z\n            y1, y2 = pad_w + dy, pad_w + dy + rows\n            x1, x2 = pad_w + dx, pad_w + dx + cols\n            target_z = padded_dem[y1:y2, x1:x2]',
    text
)

with open("lidar_relief/core/local_dominance.py", "w") as f:
    f.write(text)
