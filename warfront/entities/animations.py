from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


Direction = str
Action = str
Faction = str


_DIRECTIONS = {"down", "up", "side"}
_SOLDIER_FACTIONS = {"allied", "axis"}
_SOLDIER_ACTION_ALIASES = {
    "dead": "downed",
    "death": "downed",
    "run": "walk",
    "shoot": "fire",
    "shooting": "fire",
    "melee_bash": "melee",
    "melee_swing": "melee",
}


# Frame indices refer to warfront/assets/generated_assets.json groups:
# allied_soldier and axis_soldier. The two sheets were cut with matching
# layout/order, so both factions share the same animation map.
_BASE_SOLDIER_ACTIONS: dict[Action, dict[Direction, list[int]] | list[int]] = {
    "idle": {
        "down": [0, 1, 15, 16],
        "up": [27, 28, 29, 120, 121],
        "side": [52, 53, 54, 55],
    },
    "walk": {
        "down": [69, 70, 71, 72, 73, 74, 75, 76],
        "up": [124, 125, 126, 127, 128, 129, 130, 131],
        "side": [36, 37, 38, 39, 40, 41, 42, 43],
    },
    # Rifle frames are ready/aiming poses without muzzle flash.
    "rifle": {
        "down": [108, 109, 110, 111, 112, 113],
        "up": [144, 145, 146, 147],
        "side": [44, 45, 46, 47, 48, 49, 50, 51],
    },
    # Fire frames intentionally contain muzzle flash and are excluded above.
    "fire": {
        "down": [84, 86, 92],
        "up": [168, 169, 170],
        "side": [82, 163],
    },
    "melee": {
        "down": [96, 97, 98, 99],
        "up": [148, 149, 150, 151],
        "side": [159, 160, 161, 162],
    },
    "carry": {
        "down": [96, 97, 98, 99, 100, 101],
        "up": [148, 149, 150, 151, 152, 153, 154, 155],
        "side": [102, 103, 104, 105, 106, 107, 159, 160, 161, 162, 164, 165, 166, 167],
    },
    "utility": {
        "down": [4, 5, 14, 18, 19, 122],
        "up": [7, 28, 29, 31, 32, 33, 34, 35],
        "side": [8, 9, 10, 11, 12, 13, 21, 22, 23, 24, 25, 26],
    },
    "downed": [174, 175, 176],
}


SOLDIER_ANIMATIONS: dict[Faction, dict[Action, dict[Direction, list[int]] | list[int]]] = {
    "allied": deepcopy(_BASE_SOLDIER_ACTIONS),
    "axis": deepcopy(_BASE_SOLDIER_ACTIONS),
}


ALLIED_ACTIONS = SOLDIER_ANIMATIONS["allied"]
AXIS_ACTIONS = SOLDIER_ANIMATIONS["axis"]


# Flattened aliases are convenient for existing code that names actions as
# idle_down, walk_side, and similar.
ALLIED_SOLDIER_ANIMS: dict[str, list[int]] = {}
AXIS_SOLDIER_ANIMS: dict[str, list[int]] = {}
for _faction, _target in (("allied", ALLIED_SOLDIER_ANIMS), ("axis", AXIS_SOLDIER_ANIMS)):
    for _action, _frames_by_direction in SOLDIER_ANIMATIONS[_faction].items():
        if isinstance(_frames_by_direction, list):
            _target[_action] = list(_frames_by_direction)
            continue
        for _direction, _frames in _frames_by_direction.items():
            _target[f"{_action}_{_direction}"] = list(_frames)


TANK_ANIMATIONS: dict[Action, dict[Direction, list[int]] | list[int]] = {
    "idle": {
        "down": [75],
        "up": [88],
        "side": [26],
    },
    "move": {
        "down": [75, 76, 77, 78, 79, 80, 81, 82],
        "up": [88, 89, 90, 91, 92, 93, 94, 95],
        "side": [26, 27, 28, 29, 30, 31, 32, 33],
    },
    "fire": {
        "down": [141, 142, 143, 144, 149, 152, 153, 154],
        "up": [137, 138],
        "side": [130, 131, 132, 133],
    },
    "wreck": [155, 156, 157, 158, 159],
}


def _load_animation_overrides() -> None:
    path = Path(__file__).resolve().parents[1] / "assets" / "animations.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return
    soldier_actions = data.get("soldier", {}).get("actions")
    tank_actions = data.get("tank", {}).get("actions")
    if isinstance(soldier_actions, dict):
        for faction in SOLDIER_ANIMATIONS:
            SOLDIER_ANIMATIONS[faction] = deepcopy(soldier_actions)
    if isinstance(tank_actions, dict):
        TANK_ANIMATIONS.clear()
        TANK_ANIMATIONS.update(deepcopy(tank_actions))


_load_animation_overrides()


def _normalise_direction(direction: str) -> str:
    value = direction.lower()
    if value in {"left", "right"}:
        return "side"
    if value not in _DIRECTIONS:
        raise KeyError(f"Unknown animation direction: {direction!r}")
    return value


def _normalise_soldier_action(action: str, direction: str | None) -> tuple[str, str | None]:
    value = action.lower()
    for suffix in ("_down", "_up", "_side", "_left", "_right"):
        if value.endswith(suffix):
            action_key = _SOLDIER_ACTION_ALIASES.get(value[: -len(suffix)], value[: -len(suffix)])
            return action_key, _normalise_direction(suffix[1:])
    return _SOLDIER_ACTION_ALIASES.get(value, value), _normalise_direction(direction) if direction is not None else None


def get_soldier_frames(faction: str, action: str, direction: str | None = None) -> list[int]:
    faction_key = faction.lower()
    if faction_key not in _SOLDIER_FACTIONS:
        raise KeyError(f"Unknown soldier faction: {faction!r}")

    action_key, direction_key = _normalise_soldier_action(action, direction)
    frames = SOLDIER_ANIMATIONS[faction_key][action_key]
    if isinstance(frames, list):
        return list(frames)
    if direction_key is None:
        raise KeyError(f"Animation action {action!r} needs a direction")
    return list(frames[direction_key])


def get_tank_frames(action: str, direction: str | None = None) -> list[int]:
    action_key, direction_key = _normalise_soldier_action(action, direction)
    frames = TANK_ANIMATIONS[action_key]
    if isinstance(frames, list):
        return list(frames)
    if direction_key is None:
        raise KeyError(f"Tank animation action {action!r} needs a direction")
    return list(frames[direction_key])
