from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pygame

from warfront.assets.registry import ASSET_DIR


def _load_metadata() -> dict[str, list[dict]]:
    metadata_path = ASSET_DIR / "generated_assets.json"
    with metadata_path.open("r", encoding="utf-8") as file:
        return json.load(file)


class AssetLibrary:
    def __init__(self):
        self.metadata = _load_metadata()
        self._scaled_cache: dict[tuple[str, int], pygame.Surface] = {}
        self._frames_cache: dict[tuple[str, int], list[pygame.Surface]] = {}
        self.icons = {
            "hp": self.image(ASSET_DIR / "ui" / "icons" / "hp.png"),
            "ammo": self.image(ASSET_DIR / "ui" / "icons" / "ammo.png"),
            "objective": self.image(ASSET_DIR / "ui" / "icons" / "objective.png"),
            "warning": self.image(ASSET_DIR / "ui" / "icons" / "warning.png"),
            "restart": self.image(ASSET_DIR / "ui" / "icons" / "restart.png"),
        }
        pickaxe = ASSET_DIR / "ui" / "icons" / "pickaxe.png"
        if pickaxe.exists():
            self.icons["pickaxe"] = self.image(pickaxe)
        self.screens = {}
        for name in ("menu_operations_concept", "shop_weapons_concept"):
            path = ASSET_DIR / "ui" / "screens" / f"{name}.png"
            if path.exists():
                self.screens[name] = self.image(path)
        self.cursor = self.image(ASSET_DIR / "ui" / "cursor" / "crosshair.png")

    @staticmethod
    @lru_cache(maxsize=1024)
    def image(path: Path) -> pygame.Surface:
        return pygame.image.load(str(path)).convert_alpha()

    def frames(self, group: str, target_height: int) -> list[pygame.Surface]:
        cache_key = (group, target_height)
        if cache_key in self._frames_cache:
            return self._frames_cache[cache_key]

        frames = []
        for item in self.metadata[group]:
            path = ASSET_DIR / item["file"]
            frames.append(self.scaled(path, target_height))
        self._frames_cache[cache_key] = frames
        return frames

    def scaled(self, path: Path, target_height: int) -> pygame.Surface:
        cache_key = (str(path), target_height)
        if cache_key in self._scaled_cache:
            return self._scaled_cache[cache_key]

        image = self.image(path)
        scale = target_height / image.get_height()
        width = max(1, int(image.get_width() * scale))
        scaled = pygame.transform.smoothscale(image, (width, target_height))
        self._scaled_cache[cache_key] = scaled
        return scaled

    def frame(self, group: str, index: int, target_height: int) -> pygame.Surface:
        frames = self.frames(group, target_height)
        return frames[index % len(frames)]


_ASSETS: AssetLibrary | None = None


def get_assets() -> AssetLibrary:
    global _ASSETS
    if _ASSETS is None:
        _ASSETS = AssetLibrary()
    return _ASSETS
