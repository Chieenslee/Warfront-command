"""Tile-based pathfinding helpers.

This module intentionally avoids pygame so it can be reused by AI, tests, and
map tooling without booting the rendering stack.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Sequence
from heapq import heappop, heappush

Tile = tuple[int, int]
Grid = tuple[tuple[bool, ...], ...]
Passable = Callable[[Tile], bool] | Sequence[Sequence[bool]]

SOLID_TILES = frozenset({"#", "w", "S"})

_DIRECTIONS: tuple[Tile, ...] = ((1, 0), (0, 1), (-1, 0), (0, -1))


def grid_from_tilemap(tilemap) -> Grid:
    """Build a passability grid from a TileMap-like object or rows sequence.

    Grid values are indexed as ``grid[y][x]``. ``True`` means the tile is
    walkable, and any tile in ``SOLID_TILES`` is blocked.
    """

    rows = _rows_from_tilemap(tilemap)
    return tuple(tuple(tile not in SOLID_TILES for tile in row) for row in rows)


def bfs_nearest(start: Tile, goals: Iterable[Tile], passable: Passable) -> Tile | None:
    """Return the nearest reachable goal tile using breadth-first search."""

    if not _is_passable(passable, start):
        return None

    goal_set = set(goals)
    if not goal_set:
        return None
    if start in goal_set:
        return start

    frontier: deque[Tile] = deque([start])
    visited = {start}

    while frontier:
        current = frontier.popleft()
        for neighbor in _neighbors(current):
            if neighbor in visited or not _is_passable(passable, neighbor):
                continue
            if neighbor in goal_set:
                return neighbor
            visited.add(neighbor)
            frontier.append(neighbor)
    return None


def dfs_reachable(start: Tile, passable: Passable) -> set[Tile]:
    """Return every passable tile reachable from ``start`` using DFS."""

    if not _is_passable(passable, start):
        return set()

    reachable: set[Tile] = set()
    stack = [start]

    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        for neighbor in _neighbors(current):
            if neighbor not in reachable and _is_passable(passable, neighbor):
                stack.append(neighbor)
    return reachable


def astar(start: Tile, goal: Tile, passable: Passable, max_nodes: int | None = None) -> list[Tile]:
    """Return a shortest path from ``start`` to ``goal`` with A*.

    The returned path includes both endpoints. An empty list means no path was
    found or either endpoint is blocked.
    """

    if not _is_passable(passable, start) or not _is_passable(passable, goal):
        return []
    if start == goal:
        return [start]

    frontier: list[tuple[int, int, Tile]] = []
    counter = 0
    heappush(frontier, (_manhattan(start, goal), counter, start))
    came_from: dict[Tile, Tile | None] = {start: None}
    cost_so_far: dict[Tile, int] = {start: 0}

    expanded = 0
    while frontier:
        _, _, current = heappop(frontier)
        expanded += 1
        if max_nodes is not None and expanded > max_nodes:
            return []
        if current == goal:
            return _reconstruct_path(came_from, goal)

        for neighbor in _neighbors(current):
            if not _is_passable(passable, neighbor):
                continue
            new_cost = cost_so_far[current] + 1
            if neighbor in cost_so_far and new_cost >= cost_so_far[neighbor]:
                continue
            cost_so_far[neighbor] = new_cost
            came_from[neighbor] = current
            counter += 1
            priority = new_cost + _manhattan(neighbor, goal)
            heappush(frontier, (priority, counter, neighbor))

    return []


def _rows_from_tilemap(tilemap) -> Sequence[Sequence[str]]:
    if hasattr(tilemap, "rows"):
        return tilemap.rows
    if isinstance(tilemap, dict) and "rows" in tilemap:
        return tilemap["rows"]
    return tilemap


def _neighbors(tile: Tile) -> Iterable[Tile]:
    x, y = tile
    for dx, dy in _DIRECTIONS:
        yield x + dx, y + dy


def _is_passable(passable: Passable, tile: Tile) -> bool:
    if callable(passable):
        return bool(passable(tile))

    x, y = tile
    if y < 0 or x < 0:
        return False
    try:
        return bool(passable[y][x])
    except IndexError:
        return False


def _manhattan(a: Tile, b: Tile) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _reconstruct_path(came_from: dict[Tile, Tile | None], goal: Tile) -> list[Tile]:
    path = [goal]
    current = goal
    while came_from[current] is not None:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
