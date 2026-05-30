from __future__ import annotations

from collections import deque
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "warfront" / "ban thiet ke lai map .txt"
MAP_DATA_PATH = ROOT / "warfront" / "world" / "map_data.py"

TARGET_MAPS = [
    "jungle_outpost_mega",
    "trench_line_mega",
    "river_bridge_mega",
    "armored_front_mega",
]

OVERLAY_TO_ITEM = {
    "m": "medkit",
    "n": "grenade",
    "a": "ammo",
}
OVERLAY_TO_BASE = {
    "P": ".",
    "E": ".",
    "T": "r",
    "m": ".",
    "n": ".",
    "a": ".",
}
SOLID_TILES = {"#", "w", "S", "t"}


def extract_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    matches = list(re.finditer(r"^MAP: ([A-Za-z0-9_]+)\s*$", text, re.MULTILINE))
    for index, match in enumerate(matches):
        map_id = match.group(1)
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[map_id] = text[start:end].splitlines()
    return sections


def parse_field(lines: list[str], field: str) -> str:
    prefix = f"{field}: "
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def parse_size(lines: list[str]) -> tuple[int, int] | None:
    size = parse_field(lines, "Size")
    match = re.match(r"(\d+)\s*x\s*(\d+)", size)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def normalize_row(row: str, width: int) -> str:
    if len(row) == width:
        return row
    if len(row) > width:
        return row[:width]
    return row + "." * (width - len(row))


def parse_overlay(map_id: str, lines: list[str]) -> list[str]:
    try:
        start = lines.index("TXT overlay map:") + 1
    except ValueError as exc:
        raise ValueError("missing TXT overlay map marker") from exc

    rows: list[str] = []
    allowed = set("#.StrtwgCMADPETmna")
    for line in lines[start:]:
        if not line:
            break
        if not set(line) <= allowed:
            break
        rows.append(line)

    if not rows:
        raise ValueError("empty overlay map")
    size = parse_size(lines)
    if size:
        width, height = size
        rows = [normalize_row(row, width) for row in rows[:height]]
        if len(rows) != height:
            raise ValueError(f"{map_id}: expected {height} rows, got {len(rows)}")

    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError(f"{map_id}: row width mismatch: {sorted(widths)}")
    return rows


def connected_rects(rows: list[str], tiles: set[str]) -> list[dict]:
    width = len(rows[0])
    height = len(rows)
    seen: set[tuple[int, int]] = set()
    rects: list[dict] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in seen or rows[y][x] not in tiles:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            points: list[tuple[int, int]] = []
            while queue:
                px, py = queue.popleft()
                points.append((px, py))
                for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if (nx, ny) in seen or rows[ny][nx] not in tiles:
                        continue
                    seen.add((nx, ny))
                    queue.append((nx, ny))
            min_x = min(point[0] for point in points)
            max_x = max(point[0] for point in points)
            min_y = min(point[1] for point in points)
            max_y = max(point[1] for point in points)
            rects.append(
                {
                    "name": f"safe_zone_{len(rects) + 1}",
                    "rect": (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1),
                }
            )
    return rects


def capture_points(rows: list[str]) -> list[dict]:
    points = [(x, y) for y, row in enumerate(rows) for x, tile in enumerate(row) if tile == "C"]
    if not points:
        return []
    tile = (
        round(sum(point[0] for point in points) / len(points)),
        round(sum(point[1] for point in points) / len(points)),
    )
    return [{"id": "command_point", "tile": tile, "radius": 2}]


def keep_single_capture_cluster(rows: list[str]) -> list[str]:
    points = [(x, y) for y, row in enumerate(rows) for x, tile in enumerate(row) if tile == "C"]
    if not points:
        return rows

    center_x = round(sum(point[0] for point in points) / len(points))
    center_y = round(sum(point[1] for point in points) / len(points))
    cluster = set(
        sorted(
            points,
            key=lambda point: (abs(point[0] - center_x) + abs(point[1] - center_y), point[1], point[0]),
        )[:4]
    )

    cleaned: list[str] = []
    for y, row in enumerate(rows):
        chars = list(row)
        for x, tile in enumerate(chars):
            if tile == "C":
                chars[x] = "C" if (x, y) in cluster else "."
        cleaned.append("".join(chars))
    return cleaned


def break_long_road_runs(rows: list[str]) -> list[str]:
    if not rows:
        return rows
    width = len(rows[0])
    max_run = max(12, int(width * 0.35))
    broken: list[str] = []

    for y, row in enumerate(rows):
        chars = list(row)
        run_start: int | None = None
        for x in range(width + 1):
            is_road = x < width and chars[x] == "r"
            if is_road and run_start is None:
                run_start = x
            if (not is_road or x == width) and run_start is not None:
                run_end = x
                run_length = run_end - run_start
                if run_length > max_run:
                    for bx in range(run_start + max_run, run_end, max_run):
                        # Keep the tile passable but visually break full-width roads.
                        if (bx + y) % 2:
                            chars[bx] = "g"
                        else:
                            chars[bx] = "."
                run_start = None
        broken.append("".join(chars))
    return broken


def parse_design_map(map_id: str, lines: list[str]) -> dict:
    overlay_rows = parse_overlay(map_id, lines)
    spawns = {"player": None, "enemies": [], "tanks": []}
    items = {"medkit": [], "grenade": [], "ammo": []}
    terrain_rows: list[str] = []

    for y, row in enumerate(overlay_rows):
        terrain = []
        for x, tile in enumerate(row):
            if tile == "P":
                spawns["player"] = (x, y)
            elif tile == "E":
                spawns["enemies"].append((x, y))
            elif tile == "T":
                spawns["tanks"].append((x, y))
            elif tile in OVERLAY_TO_ITEM:
                items[OVERLAY_TO_ITEM[tile]].append((x, y))
            terrain.append(OVERLAY_TO_BASE.get(tile, tile))
        terrain_rows.append("".join(terrain))

    if spawns["player"] is None:
        raise ValueError(f"{map_id}: missing player spawn P in overlay")

    terrain_rows = keep_single_capture_cluster(terrain_rows)
    terrain_rows = break_long_road_runs(terrain_rows)

    return {
        "title": parse_field(lines, "Title"),
        "briefing": parse_field(lines, "Briefing"),
        "rows": terrain_rows,
        "spawns": spawns,
        "items": {kind: points for kind, points in items.items() if points},
        "doors": [(x, y) for y, row in enumerate(terrain_rows) for x, tile in enumerate(row) if tile == "D"],
        "safe_zones": connected_rects(terrain_rows, {"S", "D"}),
        "capture_points": capture_points(terrain_rows),
    }


def format_value(value, indent: int = 0) -> str:
    space = " " * indent
    next_space = " " * (indent + 4)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, tuple):
        return "(" + ", ".join(format_value(item, 0) for item in value) + ")"
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(item, str) for item in value):
            return "[\n" + "".join(f"{next_space}{item!r},\n" for item in value) + f"{space}]"
        return "[\n" + "".join(f"{next_space}{format_value(item, indent + 4)},\n" for item in value) + f"{space}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        body = []
        for key, item in value.items():
            body.append(f"{next_space}{key!r}: {format_value(item, indent + 4)},")
        return "{\n" + "\n".join(body) + f"\n{space}}}"
    return repr(value)


def format_map_block(map_id: str, data: dict) -> str:
    ordered = {
        "title": data["title"],
        "briefing": data["briefing"],
        "rows": data["rows"],
        "spawns": data["spawns"],
    }
    if data["safe_zones"]:
        ordered["safe_zones"] = data["safe_zones"]
    if data["doors"]:
        ordered["doors"] = data["doors"]
    if data["capture_points"]:
        ordered["capture_points"] = data["capture_points"]
    ordered["items"] = data["items"]

    lines = [f'    "{map_id}": {{']
    for key, value in ordered.items():
        lines.append(f'        "{key}": {format_value(value, 8)},')
    lines.append("    },")
    return "\n".join(lines)


def replace_map_blocks(source: str, replacements: dict[str, str]) -> str:
    positions = []
    for map_id in TARGET_MAPS:
        match = re.search(rf'^    "{re.escape(map_id)}": \{{', source, re.MULTILINE)
        if not match:
            raise ValueError(f"missing map block: {map_id}")
        positions.append((map_id, match.start()))

    output = source
    for index in range(len(positions) - 1, -1, -1):
        map_id, start = positions[index]
        if index + 1 < len(positions):
            end = positions[index + 1][1]
        else:
            end_match = re.search(r"^}\s*\n\nDEFAULT_MAP_ID", output[start:], re.MULTILINE)
            if not end_match:
                raise ValueError("could not locate end of final map block")
            end = start + end_match.start()
        output = output[:start] + replacements[map_id] + "\n\n" + output[end:]
    return output


def validate_passable(data: dict) -> None:
    rows = data["rows"]
    points: list[tuple[str, tuple[int, int]]] = [("player", data["spawns"]["player"])]
    points.extend((f"enemy[{i}]", point) for i, point in enumerate(data["spawns"]["enemies"]))
    points.extend((f"tank[{i}]", point) for i, point in enumerate(data["spawns"]["tanks"]))
    for kind, item_points in data["items"].items():
        points.extend((f"{kind}[{i}]", point) for i, point in enumerate(item_points))

    for label, (x, y) in points:
        if y < 0 or y >= len(rows) or x < 0 or x >= len(rows[y]):
            raise ValueError(f"{label} out of bounds at {(x, y)}")
        if rows[y][x] in SOLID_TILES:
            raise ValueError(f"{label} on solid tile {rows[y][x]!r} at {(x, y)}")


def main() -> None:
    design_text = DESIGN_PATH.read_text(encoding="utf-8-sig")
    sections = extract_sections(design_text)
    replacements: dict[str, str] = {}

    for map_id in TARGET_MAPS:
        if map_id not in sections:
            raise ValueError(f"missing design section: {map_id}")
        data = parse_design_map(map_id, sections[map_id])
        validate_passable(data)
        replacements[map_id] = format_map_block(map_id, data)

    source = MAP_DATA_PATH.read_text(encoding="utf-8")
    MAP_DATA_PATH.write_text(replace_map_blocks(source, replacements), encoding="utf-8")
    print("updated map_data.py from ban thiet ke lai map .txt")


if __name__ == "__main__":
    main()
