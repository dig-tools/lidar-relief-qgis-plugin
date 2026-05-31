import re

# Fix batch_algorithm.py
with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
    text = f.read()

# For batch_algorithm, we want to replace the whole `open_pos = ...`, `open_neg = ...`, `local_dom = ...`
# Let's just do a regex replace on the specific blocks.
# Block 1: open_pos
text = re.sub(
    r'(                open_pos = \(\n                    topographic_openness\([\s\S]*?\n                    \)\n                    / 90\.0\n                \)\.clip\(0, 1\))',
    r'                # fmt: off\n\1\n                # fmt: on',
    text
)
# Block 2: open_neg
text = re.sub(
    r'(                open_neg = \(\n                    topographic_openness\([\s\S]*?\n                    \)\n                    / 90\.0\n                \)\.clip\(0, 1\))',
    r'                # fmt: off\n\1\n                # fmt: on',
    text
)
# Block 3: local_dom
text = re.sub(
    r'(                local_dom = \(\n                    compute_local_dominance\([\s\S]*?\n                    \)\n                    / 255\.0\n                \)\.clip\(0, 1\))',
    r'                # fmt: off\n\1\n                # fmt: on',
    text
)

# Now, we also need to manually change the formatting inside those blocks so that Flake8 doesn't complain.
# W503: change "\n                    / 90.0" to " / 90.0" on the previous line.
text = re.sub(
    r'\)\n                    / 90\.0\n                \)\.clip\(0, 1\)',
    r') / 90.0\n                ).clip(0, 1)',
    text
)
text = re.sub(
    r'\)\n                    / 255\.0\n                \)\.clip\(0, 1\)',
    r') / 255.0\n                ).clip(0, 1)',
    text
)

with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
    f.write(text)

# Fix local_dominance.py
with open("lidar_relief/core/local_dominance.py", "r") as f:
    text = f.read()

text = re.sub(
    r'(            # Slice padded DEM to get target_z\n            target_z = padded_dem\[\n                pad_w \+ dy : pad_w \+ dy \+ rows, pad_w \+ dx : pad_w \+ dx \+ cols\n            \])',
    r'            # fmt: off\n            # Slice padded DEM to get target_z\n            target_z = padded_dem[\n                pad_w + dy:pad_w + dy + rows, pad_w + dx:pad_w + dx + cols\n            ]\n            # fmt: on',
    text
)

with open("lidar_relief/core/local_dominance.py", "w") as f:
    f.write(text)
