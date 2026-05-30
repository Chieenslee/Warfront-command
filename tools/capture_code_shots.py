import os
import ast
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import ImageFormatter

TARGETS = {
    "AStar_Pathfinding": {
        "file": "warfront/world/pathfinding.py",
        "funcs": ["astar", "_manhattan"]
    },
    "BFS_DFS_Fallback": {
        "file": "warfront/world/pathfinding.py",
        "funcs": ["bfs_nearest", "dfs_reachable"]
    },
    "AI_Target_Scoring": {
        "file": "warfront/entities/soldier.py",
        "funcs": ["get_nearest_target"]
    },
    "AI_Dodge_Bullets": {
        "file": "warfront/entities/soldier.py",
        "funcs": ["update_bot"]
    },
    "VIP_Item_Usage": {
        "file": "warfront/main.py",
        "funcs": ["_pvp_bot_profile", "_update_offline_pvp_bot_items"]
    },
    "Vehicle_AI": {
        "file": "warfront/main.py",
        "funcs": ["update_enemy_vehicles", "update_ally_vehicles"]
    },
    "Network_Sync": {
        "file": "warfront/main.py",
        "funcs": ["_sync_host", "_sync_client"]
    },
    "Map_Validation": {
        "file": "tools/validate_maps.py",
        "funcs": ["validate_map"]
    }
}

class FunctionExtractor(ast.NodeVisitor):
    def __init__(self, funcs_to_find):
        self.funcs_to_find = funcs_to_find
        self.found = {}
        self.source_lines = []

    def visit_FunctionDef(self, node):
        if node.name in self.funcs_to_find:
            start = node.lineno - 1
            end = node.end_lineno
            self.found[node.name] = "\n".join(self.source_lines[start:end])
        self.generic_visit(node)

def extract_code(filepath, funcs):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

    lines = source.splitlines()
    tree = ast.parse(source)

    extractor = FunctionExtractor([f.split('.')[-1] for f in funcs])
    extractor.source_lines = lines
    extractor.visit(tree)

    result = []
    for f in funcs:
        fname = f.split('.')[-1]
        if fname in extractor.found:
            code = extractor.found[fname]
            code_lines = code.splitlines()
            if len(code_lines) > 55:
                code = "\n".join(code_lines[:50]) + "\n    # ... (code truncated for presentation)\n" + "\n".join(code_lines[-3:])
            result.append(code)
    return "\n\n".join(result)

def main():
    os.makedirs("presentation/code_shots", exist_ok=True)
    try:
        formatter = ImageFormatter(
            font_name="Consolas",
            font_size=20,
            style="monokai",
            line_numbers=True
        )
    except Exception as e:
        print("Could not initialize ImageFormatter, maybe missing PIL?", e)
        return

    for shot_name, info in TARGETS.items():
        print(f"Generating {shot_name}...")
        code_str = extract_code(info["file"], info["funcs"])
        if not code_str:
            print(f"  -> Could not extract {info['funcs']} from {info['file']}")
            continue

        out_path = f"presentation/code_shots/{shot_name}.png"
        try:
            with open(out_path, "wb") as out_f:
                out_f.write(highlight(code_str, PythonLexer(), formatter))
            print(f"  -> Saved {out_path}")
        except Exception as e:
            print(f"  -> Failed to generate image for {shot_name}: {e}")

if __name__ == "__main__":
    main()
