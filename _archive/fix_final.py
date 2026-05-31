with open("lidar_relief/algorithms/batch_algorithm.py", "r") as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if "open_pos =" in line and "(" in line:
        # replace the whole block
        new_lines.append('                open_pos_raw = topographic_openness(\n')
        new_lines.append('                    block,\n')
        new_lines.append('                    cellsize,\n')
        new_lines.append('                    num_directions=p_cfg["openness_num_directions"],\n')
        new_lines.append('                    search_radius=p_cfg["openness_radius"],\n')
        new_lines.append('                    is_negative=False,\n')
        new_lines.append('                    feedback=feedback,\n')
        new_lines.append('                )\n')
        new_lines.append('                open_pos = (open_pos_raw / 90.0).clip(0, 1)\n')
        
        # skip lines until clip(0, 1)
        while ").clip(0, 1)" not in lines[i]:
            i += 1
        i += 1
        continue
    if "open_neg =" in line and "(" in line:
        # replace the whole block
        new_lines.append('                open_neg_raw = topographic_openness(\n')
        new_lines.append('                    block,\n')
        new_lines.append('                    cellsize,\n')
        new_lines.append('                    num_directions=p_cfg["openness_num_directions"],\n')
        new_lines.append('                    search_radius=p_cfg["openness_radius"],\n')
        new_lines.append('                    is_negative=True,\n')
        new_lines.append('                    feedback=feedback,\n')
        new_lines.append('                )\n')
        new_lines.append('                open_neg = (open_neg_raw / 90.0).clip(0, 1)\n')
        
        while ").clip(0, 1)" not in lines[i]:
            i += 1
        i += 1
        continue
    if "local_dom =" in line and "(" in line:
        # replace the whole block
        new_lines.append('                local_dom_raw = compute_local_dominance(\n')
        new_lines.append('                    block,\n')
        new_lines.append('                    cellsize,\n')
        new_lines.append('                    min_rad=p_cfg["ld_min_rad"],\n')
        new_lines.append('                    max_rad=p_cfg["ld_max_rad"],\n')
        new_lines.append('                    observer_h=p_cfg["ld_observer_height"],\n')
        new_lines.append('                    feedback=feedback,\n')
        new_lines.append('                )\n')
        new_lines.append('                local_dom = (local_dom_raw / 255.0).clip(0, 1)\n')
        
        while ").clip(0, 1)" not in lines[i]:
            i += 1
        i += 1
        continue
    
    new_lines.append(line)
    i += 1

with open("lidar_relief/algorithms/batch_algorithm.py", "w") as f:
    f.writelines(new_lines)

