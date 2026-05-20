from __future__ import annotations

from collections import deque
from pathlib import Path
import sys

import pygame

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from warfront.config import TILE_SIZE
from warfront.entities.vehicles import TANK_STATS
from warfront.world.map_data import MAPS


SOLID = {"#", "w", "S", "t"}
KNOWN_TILES = {".", "#", "w", "S", "t", "r", "g", "C", "M", "A", "D"}
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def main() -> None:
    failures: list[str] = []
    for map_id, data in MAPS.items():
        failures.extend(validate_map(map_id, data))
    if failures:
        print("MAP VALIDATION FAILED")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)
    print(f"MAP VALIDATION OK: {len(MAPS)} maps checked")


def validate_map(map_id: str, data: dict) -> list[str]:
    failures: list[str] = []
    rows = data["rows"]
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        failures.append(f"{map_id}: row widths are inconsistent")
        return failures
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            if tile not in KNOWN_TILES:
                failures.append(f"{map_id}: unknown/blank tile {tile!r} at {(x, y)}")

    player = tuple(data["spawns"]["player"])
    passable = passable_tiles(rows)
    reachable = flood(player, passable)
    closed_passable = passable - {tuple(point) for point in data.get("doors", [])}
    closed_reachable = flood(player, closed_passable)
    if player not in reachable:
        failures.append(f"{map_id}: player spawn {player} is blocked")

    named_points: list[tuple[str, tuple[int, int]]] = []
    named_points.append(("player", player))
    named_points += [(f"enemy[{i}]", tuple(point)) for i, point in enumerate(data["spawns"]["enemies"])]
    named_points += [(f"tank[{i}]", tuple(point)) for i, point in enumerate(data["spawns"]["tanks"])]
    named_points += [(f"door[{i}]", tuple(point)) for i, point in enumerate(data.get("doors", []))]
    for kind, points in data.get("items", {}).items():
        named_points += [(f"item:{kind}[{i}]", tuple(point)) for i, point in enumerate(points)]
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            if tile == "C":
                named_points.append(("capture", (x, y)))

    spawn_point_names: dict[tuple[int, int], list[str]] = {}
    for name, point in named_points:
        if name.startswith(("player", "enemy[", "tank[")):
            spawn_point_names.setdefault(point, []).append(name)
    for point, names in spawn_point_names.items():
        if len(names) > 1:
            failures.append(f"{map_id}: overlapping spawn points at {point}: {', '.join(names)}")

    for name, point in named_points:
        if not in_bounds(point, rows):
            failures.append(f"{map_id}: {name} {point} is outside map")
            continue
        if point not in passable:
            failures.append(f"{map_id}: {name} {point} is blocked by tile {tile_at(rows, point)!r}")
        elif point not in reachable:
            failures.append(f"{map_id}: {name} {point} is isolated from player")

    tank_sizes = {stats.size for stats in TANK_STATS.values()}
    for i, point in enumerate(data["spawns"]["tanks"]):
        if not any(rect_fits(rows, point, size) for size in tank_sizes):
            failures.append(f"{map_id}: tank[{i}] {point} cannot fit any known tank collision box")
        if narrow_neighbors(rows, point) >= 3:
            failures.append(f"{map_id}: tank[{i}] {point} starts in a tight pocket")

    for i, aircraft in enumerate(data["spawns"].get("aircraft_enemies", [])):
        for key in ("entry", "exit", "target"):
            if key not in aircraft:
                failures.append(f"{map_id}: aircraft[{i}] missing {key!r}")
                continue
            point = tuple(aircraft[key])
            if not near_map(point, rows, margin=4):
                failures.append(f"{map_id}: aircraft[{i}] {key} {point} is too far outside the map")
        if aircraft.get("unit", "bomber") != "bomber":
            failures.append(f"{map_id}: aircraft[{i}] unsupported unit {aircraft.get('unit')!r}")

    if data.get("doors"):
        combat_points = [("capture", point) for point in capture_points(rows)]
        combat_points += [(f"enemy[{i}]", tuple(point)) for i, point in enumerate(data["spawns"]["enemies"])]
        combat_points += [(f"tank[{i}]", tuple(point)) for i, point in enumerate(data["spawns"]["tanks"])]
        leaks = [f"{name} {point}" for name, point in combat_points if point in closed_reachable]
        if leaks:
            failures.append(f"{map_id}: safe-room leaks before opening doors: {', '.join(leaks[:6])}")
    return failures


def passable_tiles(rows: list[str]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for y, row in enumerate(rows)
        for x, tile in enumerate(row)
        if tile not in SOLID
    }


def flood(start: tuple[int, int], passable: set[tuple[int, int]]) -> set[tuple[int, int]]:
    if start not in passable:
        return set()
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in NEIGHBORS:
            neighbor = (x + dx, y + dy)
            if neighbor in passable and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def rect_fits(rows: list[str], point: tuple[int, int], size: tuple[int, int]) -> bool:
    rect = pygame.Rect(0, 0, *size)
    rect.center = (point[0] * TILE_SIZE + TILE_SIZE // 2, point[1] * TILE_SIZE + TILE_SIZE // 2)
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            if tile in SOLID:
                solid = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                if rect.colliderect(solid):
                    return False
    return True


def narrow_neighbors(rows: list[str], point: tuple[int, int]) -> int:
    x, y = point
    blocked = 0
    for dx, dy in NEIGHBORS:
        neighbor = (x + dx, y + dy)
        if not in_bounds(neighbor, rows) or tile_at(rows, neighbor) in SOLID:
            blocked += 1
    return blocked


def in_bounds(point: tuple[int, int], rows: list[str]) -> bool:
    x, y = point
    return 0 <= y < len(rows) and 0 <= x < len(rows[y])


def near_map(point: tuple[int, int], rows: list[str], margin: int) -> bool:
    x, y = point
    return -margin <= y < len(rows) + margin and -margin <= x < len(rows[0]) + margin


def tile_at(rows: list[str], point: tuple[int, int]) -> str:
    return rows[point[1]][point[0]]


def capture_points(rows: list[str]) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y, row in enumerate(rows)
        for x, tile in enumerate(row)
        if tile == "C"
    ]


if __name__ == "__main__":
    main()
