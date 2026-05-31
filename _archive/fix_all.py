import re

# Fix batch_algorithm.py
with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
    text = f.read()
text = re.sub(
    r'(\s+)(feedback=feedback,)\s*\)\s*/\s*(90\.0|255\.0)\s*# fmt: skip',
    r'\1# fmt: off\n\1\2\n\1) / \3\n\1# fmt: on',
    text
)
with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
    f.write(text)

# Fix local_dominance.py
with open("lidar_relief/core/local_dominance.py", "r") as f:
    text = f.read()
text = re.sub(
    r'target_z\s*=\s*padded_dem\[(.*?)\]',
    lambda m: "target_z = padded_dem[\n            # fmt: off\n            " + m.group(1).strip().replace(" : ", ":") + "\n            # fmt: on\n        ]",
    text,
    flags=re.DOTALL
)
with open("lidar_relief/core/local_dominance.py", "w") as f:
    f.write(text)
