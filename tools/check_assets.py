from __future__ import annotations

import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from warfront.assets import registry


REQUIRED_GROUPS = {
    "characters": registry.CHARACTERS,
    "vehicles": registry.VEHICLES,
    "aircraft": registry.AIRCRAFT,
    "maps": registry.MAPS,
    "props": registry.PROPS,
}

OPTIONAL_ASSET_TYPES = [
    "audio/sfx",
    "audio/music",
    "ui/icons",
    "ui/cursor",
    "cut_sprites/characters",
    "cut_sprites/vehicles",
    "cut_sprites/aircraft",
    "cut_sprites/props",
    "cut_sprites/effects",
    "tilemaps/tileset",
]


def main() -> int:
    pygame.init()
    missing = []
    print("Required asset sheets:")
    for group_name, assets in REQUIRED_GROUPS.items():
        for asset_name, path in assets.items():
            if not path.exists():
                missing.append(f"{group_name}:{asset_name} -> {path}")
                print(f"  MISSING {group_name}/{asset_name}: {path}")
                continue
            image = pygame.image.load(str(path))
            print(f"  OK {group_name}/{asset_name}: {image.get_width()}x{image.get_height()}")

    print("\nOptional production assets still needed:")
    for asset_type in OPTIONAL_ASSET_TYPES:
        path = registry.ASSET_DIR / asset_type
        if not path.exists():
            status = "MISSING"
        elif any(item.is_file() for item in path.rglob("*")):
            status = "OK"
        else:
            status = "EMPTY"
        print(f"  {status} {asset_type}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
