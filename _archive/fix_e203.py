import re
def fix_file(path):
    with open(path, "r") as f:
        content = f.read()
    
    # We replace " :" with ":" only for the E203 cases where ruff wants spaces around slice colons.
    # We just need to add `# fmt: skip` to those specific lines.
    # In test_mstp.py:
    # array[start : end : step]
    content = re.sub(r'(\[.*?)\s+:\s+(.*?\])', r'\1:\2  # fmt: skip', content)
    
    with open(path, "w") as f:
        f.write(content)

fix_file("lidar_relief/core/local_dominance.py")
fix_file("lidar_relief/tests/test_mstp.py")
