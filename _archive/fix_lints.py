import re

def fix_batch():
    with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
        content = f.read()
    
    # We want to replace:
    #                     )
    #                     / 90.0
    #                 ).clip(0, 1)
    
    # Just replace all instances of ")\n                    / 90.0" with ") / 90.0  # fmt: skip"
    content = re.sub(r'\)\n                    / 90\.0', ') / 90.0  # fmt: skip', content)
    
    with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
        f.write(content)

def fix_ld():
    with open("lidar_relief/core/local_dominance.py", "r") as f:
        content = f.read()
    
    # E203 at line 46: res_y = min(y_start + max_rad + 1, grid_shape[0]) - max(y_start - max_rad, 0)
    # wait, where is the colon?
    # Let's run flake8 to see exactly what E203 is complaining about.
    pass

fix_batch()
