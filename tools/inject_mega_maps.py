import os
import sys

def main():
    with open("tools/mega_maps_output.py", "r", encoding="utf-8") as f:
        mega_maps_code = f.read()
        
    with open("warfront/world/map_data.py", "r", encoding="utf-8") as f:
        map_data_code = f.read()
        
    # Extract inner
    mega_inner = mega_maps_code.replace("MEGA_MAPS = {", "").rstrip().rstrip("}")
    
    # Find the start of old mega maps
    start_index = map_data_code.find('    "jungle_outpost_mega": {')
    if start_index != -1:
        # We will replace from start_index to the end of the dict
        # The dict ends at }\n\nDEFAULT_MAP_ID
        end_index = map_data_code.find('}\n\nDEFAULT_MAP_ID')
        if end_index != -1:
            new_map_data = map_data_code[:start_index] + mega_inner + "\n" + map_data_code[end_index:]
            with open("warfront/world/map_data.py", "w", encoding="utf-8") as f:
                f.write(new_map_data)
            print("Successfully replaced mega maps in map_data.py")
        else:
            print("Could not find end of MAPS dict.")
    else:
        print("Could not find old mega maps.")

if __name__ == "__main__":
    main()
