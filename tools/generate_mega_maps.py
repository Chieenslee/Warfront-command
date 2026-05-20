import sys
import os
import ast

def scale_map(map_data, scale=4):
    new_map = {}
    new_map["title"] = "MEGA: " + map_data["title"]
    new_map["briefing"] = map_data["briefing"]
    
    # Scale rows
    new_rows = []
    for row in map_data["rows"]:
        scaled_row = ""
        for char in row:
            if char in ('M', 'A'):
                # For interactables, just put one and pad with ground
                # Wait, it's easier to just duplicate them and let the game have a 4x4 block of medics, 
                # but maybe that breaks the game?
                # Actually, multiple Medics just overlap. It's fine.
                scaled_row += char * scale
            else:
                scaled_row += char * scale
        for _ in range(scale):
            new_rows.append(scaled_row)
            
    # Fix Doors: D is a door in the S wall. If we just duplicate it, it's a 4x4 door block.
    # That works! A 4x4 door is just a wider door.
            
    new_map["rows"] = new_rows
    
    # Scale spawns
    new_spawns = {}
    for key, val in map_data.get("spawns", {}).items():
        if isinstance(val, tuple):
            new_spawns[key] = (val[0]*scale + scale//2, val[1]*scale + scale//2)
        elif isinstance(val, list) and len(val) > 0 and isinstance(val[0], tuple):
            new_spawns[key] = [(x*scale + scale//2, y*scale + scale//2) for (x, y) in val]
        elif isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
            # Aircraft enemies
            new_ac = []
            for ac in val:
                nac = dict(ac)
                nac["entry"] = (ac["entry"][0]*scale, ac["entry"][1]*scale)
                nac["exit"] = (ac["exit"][0]*scale, ac["exit"][1]*scale)
                nac["target"] = (ac["target"][0]*scale, ac["target"][1]*scale)
                new_ac.append(nac)
            new_spawns[key] = new_ac
            
    new_map["spawns"] = new_spawns
    
    # Scale items
    new_items = {}
    for key, val in map_data.get("items", {}).items():
        new_items[key] = [(x*scale + scale//2, y*scale + scale//2) for (x, y) in val]
    new_map["items"] = new_items
    
    # Scale safe_zones
    if "safe_zones" in map_data:
        new_sz = []
        for sz in map_data["safe_zones"]:
            nsz = dict(sz)
            rect = sz["rect"]
            nsz["rect"] = (rect[0]*scale, rect[1]*scale, rect[2]*scale, rect[3]*scale)
            new_sz.append(nsz)
        new_map["safe_zones"] = new_sz
        
    if "doors" in map_data:
        new_map["doors"] = [(x*scale + scale//2, y*scale + scale//2) for (x,y) in map_data["doors"]]
        
    if "capture_points" in map_data:
        new_cp = []
        for cp in map_data["capture_points"]:
            ncp = dict(cp)
            ncp["tile"] = (cp["tile"][0]*scale + scale//2, cp["tile"][1]*scale + scale//2)
            ncp["radius"] = cp["radius"] * scale
            new_cp.append(ncp)
        new_map["capture_points"] = new_cp
        
    if "boss_wave" in map_data:
        bw = dict(map_data["boss_wave"])
        if "trigger_radius_tile" in bw:
            bw["trigger_radius_tile"] = (bw["trigger_radius_tile"][0]*scale + scale//2, bw["trigger_radius_tile"][1]*scale + scale//2)
        if "boss_spawn" in bw:
            bw["boss_spawn"] = (bw["boss_spawn"][0]*scale + scale//2, bw["boss_spawn"][1]*scale + scale//2)
        if "adds_spawns" in bw:
            bw["adds_spawns"] = [(x*scale + scale//2, y*scale + scale//2) for (x, y) in bw["adds_spawns"]]
        new_map["boss_wave"] = bw
        
    return new_map

def main():
    sys.path.insert(0, os.path.abspath('.'))
    from warfront.world.map_data import MAPS
    
    mega_maps = {}
    for map_id, map_data in MAPS.items():
        if not map_id.endswith("_mega"):
            mega_maps[map_id + "_mega"] = scale_map(map_data, 4)
            
    # Write to a new file to be appended manually
    with open("tools/mega_maps_output.py", "w", encoding="utf-8") as f:
        f.write("MEGA_MAPS = {\n")
        for map_id, map_data in mega_maps.items():
            f.write(f'    "{map_id}": {{\n')
            for k, v in map_data.items():
                if k == "rows":
                    f.write(f'        "{k}": [\n')
                    for row in v:
                        f.write(f'            "{row}",\n')
                    f.write(f'        ],\n')
                elif isinstance(v, dict) or isinstance(v, list) or isinstance(v, tuple):
                    f.write(f'        "{k}": {repr(v)},\n')
                else:
                    f.write(f'        "{k}": {repr(v)},\n')
            f.write(f'    }},\n')
        f.write("}\n")

if __name__ == "__main__":
    main()
