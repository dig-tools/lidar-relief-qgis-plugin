def replace_exact(file_path, old, new):
    with open(file_path, "r") as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(file_path, "w") as f:
            f.write(content)
        print(f"Replaced in {file_path}")
    else:
        print(f"Not found in {file_path}")

batch = "lidar_relief/algorithms/batch_algorithm.py"
ld = "lidar_relief/core/local_dominance.py"

replace_exact(batch, 
"""                    feedback=feedback,
                )
                / 90.0  # fmt: skip
            ).clip(0, 1)""", 
"""                    # fmt: off
                    feedback=feedback,
                ) / 90.0
                # fmt: on
            ).clip(0, 1)""")

replace_exact(batch, 
"""                    feedback=feedback,
                )
                / 255.0  # fmt: skip
            ).clip(0, 1)""", 
"""                    # fmt: off
                    feedback=feedback,
                ) / 255.0
                # fmt: on
            ).clip(0, 1)""")

replace_exact(ld, 
"""            target_z = padded_dem[
                pad_w + dy : pad_w + dy + rows, pad_w + dx : pad_w + dx + cols
            ]""", 
"""            # fmt: off
            target_z = padded_dem[
                pad_w + dy:pad_w + dy + rows, pad_w + dx:pad_w + dx + cols
            ]
            # fmt: on""")
