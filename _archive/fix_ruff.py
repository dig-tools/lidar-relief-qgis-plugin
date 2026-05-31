with open("lidar_relief/core/local_dominance.py", "r") as f:
    lines = f.read().splitlines()

# We need to surround the slice with fmt: off
content = []
for line in lines:
    if "target_z = padded_dem[" in line:
        content.append("            # fmt: off")
        content.append("            target_z = padded_dem[pad_w + dy:pad_w + dy + rows, pad_w + dx:pad_w + dx + cols]")
        content.append("            # fmt: on")
    elif "pad_w + dx : pad_w + dx + cols" in line:
        continue
    elif "]" in line and "target_z" not in line and len(content) > 0 and content[-1] == "            # fmt: on":
        # we might have left a stray closing bracket.
        pass
    else:
        content.append(line)

# Let's just do an exact string replace to be safer.
