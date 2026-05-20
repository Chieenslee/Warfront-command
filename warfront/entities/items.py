from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame

from warfront.assets.registry import ASSET_DIR
from warfront.assets.loader import get_assets


ITEM_MEDKIT = "medkit"
ITEM_GRENADE = "grenade"
ITEM_AMMO = "ammo"
ITEM_KINDS = {ITEM_MEDKIT, ITEM_GRENADE, ITEM_AMMO}

ITEM_ICON_PATHS = {
    ITEM_MEDKIT: ASSET_DIR / "ui" / "icons" / "hp.png",
    ITEM_AMMO: ASSET_DIR / "ui" / "icons" / "ammo.png",
}

ITEM_PROP_FRAMES = {
    ITEM_MEDKIT: 65,
    ITEM_GRENADE: 114,
    ITEM_AMMO: 88,
}

ITEM_COLORS = {
    ITEM_MEDKIT: (78, 176, 91),
    ITEM_GRENADE: (101, 119, 77),
    ITEM_AMMO: (221, 169, 79),
}


_ICON_CACHE: dict[tuple[str, int], pygame.Surface | None] = {}


def normalize_item_kind(kind: str) -> str:
    normalized = str(kind).strip().lower()
    aliases = {
        "health": ITEM_MEDKIT,
        "hp": ITEM_MEDKIT,
        "grenades": ITEM_GRENADE,
        "frag": ITEM_GRENADE,
        "bullets": ITEM_AMMO,
        "rounds": ITEM_AMMO,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ITEM_KINDS:
        raise ValueError(f"Unsupported item kind: {kind!r}")
    return normalized


def _load_icon(kind: str, size: int) -> pygame.Surface | None:
    key = (kind, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]

    path = ITEM_ICON_PATHS.get(kind)
    if path is None or not Path(path).exists():
        _ICON_CACHE[key] = None
        return None

    try:
        icon = pygame.image.load(str(path))
        if pygame.display.get_surface() is not None:
            icon = icon.convert_alpha()
        else:
            icon = icon.copy()
    except pygame.error:
        _ICON_CACHE[key] = None
        return None

    _ICON_CACHE[key] = pygame.transform.smoothscale(icon, (size, size))
    return _ICON_CACHE[key]


@dataclass
class Item:
    pos: tuple[int, int] | pygame.Vector2
    kind: str
    amount: int = 1
    size: int = 28
    rect: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        self.kind = normalize_item_kind(self.kind)
        self.amount = max(1, int(self.amount))
        self.rect = pygame.Rect(0, 0, self.size, self.size)
        self.rect.center = (int(self.pos[0]), int(self.pos[1]))

    def draw(self, screen: pygame.Surface, camera) -> None:
        view = camera.apply(self.rect)
        color = ITEM_COLORS[self.kind]

        shadow = pygame.Surface((view.width + 8, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 72), shadow.get_rect())
        screen.blit(shadow, shadow.get_rect(center=(view.centerx + 2, view.bottom - 1)))

        back = pygame.Surface((view.width + 8, view.height + 8), pygame.SRCALPHA)
        pygame.draw.rect(back, (26, 29, 25, 205), back.get_rect(), border_radius=6)
        pygame.draw.rect(back, (*color, 215), back.get_rect().inflate(-3, -3), 2, border_radius=5)
        screen.blit(back, back.get_rect(center=view.center))

        icon = self._asset_icon(max(18, self.size))
        if icon is not None:
            screen.blit(icon, icon.get_rect(center=view.center))
        else:
            icon = _load_icon(self.kind, max(14, self.size - 8))
            if icon is not None:
                screen.blit(icon, icon.get_rect(center=view.center))
            elif self.kind == ITEM_GRENADE:
                self._draw_grenade(screen, view, color)
            else:
                pygame.draw.circle(screen, color, view.center, max(6, view.width // 3))

        if self.amount > 1:
            self._draw_amount(screen, view)

    def _draw_grenade(self, screen: pygame.Surface, view: pygame.Rect, color: tuple[int, int, int]) -> None:
        body = pygame.Rect(0, 0, max(12, view.width - 10), max(14, view.height - 8))
        body.midbottom = (view.centerx, view.bottom - 5)
        pygame.draw.ellipse(screen, (36, 45, 34), body.inflate(3, 3))
        pygame.draw.ellipse(screen, color, body)
        pin = pygame.Rect(0, 0, max(7, view.width // 4), max(5, view.height // 6))
        pin.midbottom = (view.centerx + 3, body.top + 3)
        pygame.draw.rect(screen, (190, 186, 140), pin, border_radius=2)
        pygame.draw.line(screen, (38, 42, 35), (body.left + 4, body.centery), (body.right - 4, body.centery), 2)

    def _draw_amount(self, screen: pygame.Surface, view: pygame.Rect) -> None:
        badge = pygame.Rect(0, 0, 18, 14)
        badge.bottomright = (view.right + 6, view.bottom + 4)
        pygame.draw.rect(screen, (30, 28, 23), badge, border_radius=4)
        pygame.draw.rect(screen, (238, 232, 207), badge, 1, border_radius=4)
        font = pygame.font.Font(None, 16)
        text = font.render(str(self.amount), True, (248, 235, 194))
        screen.blit(text, text.get_rect(center=badge.center))

    def _asset_icon(self, size: int) -> pygame.Surface | None:
        frame_index = ITEM_PROP_FRAMES.get(self.kind)
        if frame_index is None:
            return None
        try:
            return get_assets().frame("prop", frame_index, size)
        except (KeyError, IndexError, pygame.error):
            return None


__all__ = [
    "ITEM_AMMO",
    "ITEM_GRENADE",
    "ITEM_KINDS",
    "ITEM_MEDKIT",
    "Item",
    "normalize_item_kind",
]
