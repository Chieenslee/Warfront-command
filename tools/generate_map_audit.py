from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from warfront.world.map_data import MAPS


SOLID_TILES = {"#", "w", "S", "t"}
KNOWN_TILES = set("#.StrtwgCMAD")

LEGEND = [
    "# = wall / hard obstacle / bullet block",
    ". = grass floor / open ground",
    "S = safe-zone wall/floor block (solid)",
    "D = safe-zone door / depot door",
    "M = med station marker",
    "A = ammo station marker",
    "r = road / dirt route / trench floor",
    "t = sandbag / trench cover (solid cover)",
    "w = water (solid, bullet block)",
    "g = bush/grass prop tile",
    "C = capture point tile",
    "P = player spawn overlay in report only",
    "E = enemy infantry spawn overlay in report only",
    "T = enemy tank spawn overlay in report only",
    "m = medkit item overlay in report only",
    "n = grenade item overlay in report only",
    "a = ammo item overlay in report only",
]


def tile_at(rows: list[str], point: tuple[int, int]) -> str | None:
    x, y = point
    if y < 0 or y >= len(rows) or x < 0 or x >= len(rows[y]):
        return None
    return rows[y][x]


def overlay_rows(data: dict) -> list[str]:
    rows = [list(row) for row in data["rows"]]
    spawns = data.get("spawns", {})
    overlays: list[tuple[tuple[int, int], str]] = []
    if "player" in spawns:
        overlays.append((spawns["player"], "P"))
    overlays.extend((point, "E") for point in spawns.get("enemies", []))
    overlays.extend((point, "T") for point in spawns.get("tanks", []))
    for kind, mark in (("medkit", "m"), ("grenade", "n"), ("ammo", "a")):
        overlays.extend((point, mark) for point in data.get("items", {}).get(kind, []))

    for (x, y), mark in overlays:
        if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
            rows[y][x] = mark
    return ["".join(row) for row in rows]


def longest_runs(rows: list[str]) -> dict[str, int]:
    max_run: dict[str, int] = {tile: 0 for tile in KNOWN_TILES}
    for row in rows:
        previous = None
        length = 0
        for tile in row + "\0":
            if tile == previous:
                length += 1
                continue
            if previous is not None:
                max_run[previous] = max(max_run.get(previous, 0), length)
            previous = tile
            length = 1
    return max_run


def validate_map(map_id: str, data: dict) -> list[str]:
    rows = data["rows"]
    widths = [len(row) for row in rows]
    width = widths[0]
    height = len(rows)
    issues: list[str] = []

    if len(set(widths)) != 1:
        issues.append(f"ROW_WIDTH_MISMATCH widths={sorted(set(widths))}")

    unknown_tiles = sorted(set("".join(rows)) - KNOWN_TILES)
    if unknown_tiles:
        issues.append(f"UNKNOWN_TILES {unknown_tiles}")

    capture_count = sum(row.count("C") for row in rows)
    if capture_count == 0:
        issues.append("NO_CAPTURE_TILE_C")
    if capture_count > 4:
        issues.append(f"MANY_CAPTURE_TILES count={capture_count}")

    spawns = data.get("spawns", {})
    spawn_points: list[tuple[str, tuple[int, int]]] = []
    if "player" not in spawns:
        issues.append("NO_PLAYER_SPAWN")
    else:
        spawn_points.append(("player", spawns["player"]))
    spawn_points.extend((f"enemy[{i}]", point) for i, point in enumerate(spawns.get("enemies", [])))
    spawn_points.extend((f"tank[{i}]", point) for i, point in enumerate(spawns.get("tanks", [])))

    seen: dict[tuple[int, int], str] = {}
    for label, point in spawn_points:
        tile = tile_at(rows, point)
        if tile is None:
            issues.append(f"{label}_OUT_OF_BOUNDS {point}")
        elif tile in SOLID_TILES:
            issues.append(f"{label}_ON_SOLID {point} tile={tile}")
        if point in seen:
            issues.append(f"SPAWN_OVERLAP {label} with {seen[point]} at {point}")
        seen[point] = label

    items = data.get("items", {})
    if not items:
        issues.append("NO_ITEM_SPAWNS")
    for kind, points in items.items():
        for index, point in enumerate(points):
            tile = tile_at(rows, point)
            if tile is None:
                issues.append(f"{kind}[{index}]_OUT_OF_BOUNDS {point}")
            elif tile in SOLID_TILES:
                issues.append(f"{kind}[{index}]_ON_SOLID {point} tile={tile}")

    if width >= 100 and height >= 70:
        counts = Counter("".join(rows))
        total = width * height
        max_run = longest_runs(rows)
        road_ratio = counts.get("r", 0) / total
        wall_ratio = counts.get("#", 0) / total
        water_ratio = counts.get("w", 0) / total
        if max_run.get("r", 0) >= width * 0.45:
            issues.append(f"REPETITIVE_LONG_ROAD_RUN max_r={max_run.get('r', 0)}")
        if max_run.get("#", 0) >= width * 0.45:
            issues.append(f"REPETITIVE_LONG_WALL_RUN max_hash={max_run.get('#', 0)}")
        if road_ratio > 0.40:
            issues.append(f"ROAD_DOMINATED ratio={road_ratio:.1%}")
        if wall_ratio > 0.45:
            issues.append(f"WALL_DOMINATED ratio={wall_ratio:.1%}")
        if water_ratio < 0.01 and "river" in map_id:
            issues.append("RIVER_THEME_WITH_TOO_LITTLE_WATER")

    return issues


def build_report() -> str:
    lines = [
        "WARFRONT MAP AUDIT - CHECKLIST 01",
        "Generated from warfront/world/map_data.py",
        "",
        "CHECKLIST",
        "[x] Export current maps as TXT with coordinate-free tile rows",
        "[x] Add symbol legend for terrain, spawns, items, doors and capture",
        "[x] Count map dimensions, terrain distribution, spawns, items",
        "[x] Detect current structural issues: repeated bands, blocked spawns/items, missing capture/items",
        "[x] Redesign the last 4 mega maps so each has a unique tactical silhouette",
        "[ ] Next step: add/verify remote damage floaters and projectile visual sync after map cleanup",
        "",
        "SYMBOL LEGEND",
    ]
    lines.extend(f"- {entry}" for entry in LEGEND)
    lines.append("")

    all_issues: list[tuple[str, str]] = []
    for map_id, data in MAPS.items():
        rows = data["rows"]
        width = len(rows[0])
        height = len(rows)
        counts = Counter("".join(rows))
        total = width * height
        issues = validate_map(map_id, data)
        all_issues.extend((map_id, issue) for issue in issues)

        lines.extend(
            [
                "=" * 100,
                f"MAP: {map_id}",
                f"Title: {data.get('title', '')}",
                f"Briefing: {data.get('briefing', '')}",
                f"Size: {width} x {height} = {total} tiles",
                (
                    "Spawns: "
                    f"player={data.get('spawns', {}).get('player')}, "
                    f"enemies={len(data.get('spawns', {}).get('enemies', []))}, "
                    f"tanks={len(data.get('spawns', {}).get('tanks', []))}"
                ),
                (
                    "Items: "
                    + ", ".join(f"{kind}={len(points)}" for kind, points in data.get("items", {}).items())
                    if data.get("items")
                    else "Items: none"
                ),
                "Tile distribution: "
                + ", ".join(
                    f"{tile}:{counts.get(tile, 0)} ({counts.get(tile, 0) / total:.1%})"
                    for tile in sorted(KNOWN_TILES)
                    if counts.get(tile, 0)
                ),
                "Issues: " + ("; ".join(issues) if issues else "none detected by static audit"),
                "TXT overlay map:",
            ]
        )
        lines.extend(overlay_rows(data))
        lines.append("")

    lines.extend(["=" * 100, "CURRENT ERROR / RISK SUMMARY"])
    if all_issues:
        lines.extend(f"- {map_id}: {issue}" for map_id, issue in all_issues)
    else:
        lines.append("- No static issues detected.")

    lines.extend(["", "DESIGN NOTES FOR LAST / MEGA MAPS"])
    for map_id, data in MAPS.items():
        if len(data["rows"][0]) >= 100 or len(data["rows"]) >= 70:
            issues = [issue for current_id, issue in all_issues if current_id == map_id]
            note = (
                "; ".join(issues)
                if issues
                else "large map exists but still needs human pass for repetition, pacing, objective placement"
            )
            lines.append(f"- {map_id}: {note}")

    return "\n".join(lines) + "\n"


def main() -> None:
    output_path = Path("warfront/MAP_AUDIT_CHECKLIST_01.txt")
    output_path.write_text(build_report(), encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
