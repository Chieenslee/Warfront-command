from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "warfront" / "assets"
DEFAULT_SOURCE = ASSET_DIR / "source_sheets" / "terrain_tilesheet.png"
TILESET_DIR = ASSET_DIR / "tilemaps" / "tileset"
PROP_DIR = ASSET_DIR / "cut_sprites" / "props" / "terrain"
BASE_SHEET_SIZE = (1024, 576)
TILE_SIZE = 64
TARGET_TILE_SIZE = 48
WHITE_ALPHA_THRESHOLD = 238


TILE_CROPS = {
    "grass.png": (0, 0, 64, 64),
    "grass_flower.png": (128, 64, 64, 64),
    "road.png": (320, 0, 64, 64),
    "trench.png": (320, 128, 64, 64),
    "water.png": (640, 0, 64, 64),
    "wall.png": (0, 384, 64, 64),
    "capture_point.png": (896, 320, 64, 64),
    "sandbag_wall.png": (704, 384, 192, 64),
}


PROP_CROPS = {
    "logs.png": (512, 352, 160, 120),
    "sandbags_large.png": (704, 352, 172, 90),
    "radio.png": (904, 342, 100, 94),
    "bush_small.png": (526, 496, 42, 42),
    "grass_tall.png": (586, 494, 52, 48),
    "stones.png": (654, 508, 60, 32),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Slice the terrain tilesheet into Warfront Command assets.")
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Path to terrain sheet. Default: {DEFAULT_SOURCE}",
    )
    args = parser.parse_args()
    source = args.source.resolve()
    if not source.exists():
        raise SystemExit(
            f"Không thấy file terrain sheet: {source}\n"
            f"Hãy lưu ảnh bạn gửi thành: {DEFAULT_SOURCE}"
        )

    pygame.init()
    try:
        sheet = pygame.image.load(str(source))
        width, height = sheet.get_size()
        if width < 800 or height < 450:
            raise SystemExit(f"Sheet quá nhỏ: {width}x{height}. Cần tối thiểu 800x450.")

        backup_dir = TILESET_DIR / "_backup_before_terrain_import"
        backup_dir.mkdir(parents=True, exist_ok=True)
        TILESET_DIR.mkdir(parents=True, exist_ok=True)
        PROP_DIR.mkdir(parents=True, exist_ok=True)

        for path in TILESET_DIR.glob("*.png"):
            backup = backup_dir / path.name
            if not backup.exists():
                shutil.copy2(path, backup)

        for filename, rect in TILE_CROPS.items():
            if filename == "capture_point.png":
                pygame.image.save(make_capture_point(), str(TILESET_DIR / filename))
                continue
            inset = 0 if filename in {"sandbag_wall.png"} else 2
            tile = crop(sheet, scaled_rect(rect, width, height, inset=inset))
            if filename not in {"sandbag_wall.png"}:
                tile = pygame.transform.scale(tile, (TARGET_TILE_SIZE, TARGET_TILE_SIZE))
            else:
                tile = make_near_white_transparent(tile)
                tile = trim_transparent(tile)
                tile = pygame.transform.scale(tile, (TARGET_TILE_SIZE, TARGET_TILE_SIZE // 2))
            pygame.image.save(tile, str(TILESET_DIR / filename))

        for filename, rect in PROP_CROPS.items():
            prop = crop(sheet, scaled_rect(rect, width, height))
            prop = make_near_white_transparent(prop)
            pygame.image.save(trim_transparent(prop), str(PROP_DIR / filename))

        print(f"Imported terrain sheet: {source}")
        print(f"Tiles written to: {TILESET_DIR}")
        print(f"Props written to: {PROP_DIR}")
    finally:
        pygame.quit()


def crop(surface: pygame.Surface, rect_tuple: tuple[int, int, int, int]) -> pygame.Surface:
    rect = pygame.Rect(rect_tuple)
    result = pygame.Surface(rect.size, pygame.SRCALPHA)
    result.blit(surface, (0, 0), rect)
    return result


def scaled_rect(rect_tuple: tuple[int, int, int, int], width: int, height: int, inset: int = 0) -> tuple[int, int, int, int]:
    scale_x = width / BASE_SHEET_SIZE[0]
    scale_y = height / BASE_SHEET_SIZE[1]
    x, y, w, h = rect_tuple
    x += inset
    y += inset
    w -= inset * 2
    h -= inset * 2
    return (
        int(round(x * scale_x)),
        int(round(y * scale_y)),
        max(1, int(round(w * scale_x))),
        max(1, int(round(h * scale_y))),
    )


def make_near_white_transparent(surface: pygame.Surface) -> pygame.Surface:
    result = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    result.blit(surface, (0, 0))
    width, height = result.get_size()
    for y in range(height):
        for x in range(width):
            r, g, b, a = result.get_at((x, y))
            if a and r >= WHITE_ALPHA_THRESHOLD and g >= WHITE_ALPHA_THRESHOLD and b >= WHITE_ALPHA_THRESHOLD:
                result.set_at((x, y), (r, g, b, 0))
    return result


def make_capture_point() -> pygame.Surface:
    surface = pygame.Surface((TARGET_TILE_SIZE, TARGET_TILE_SIZE), pygame.SRCALPHA)
    center = TARGET_TILE_SIZE // 2
    pygame.draw.circle(surface, (188, 67, 54, 175), (center, center), 18)
    pygame.draw.circle(surface, (238, 203, 116, 210), (center, center), 18, 3)
    pygame.draw.circle(surface, (38, 42, 35, 230), (center, center), 6)
    pygame.draw.line(surface, (238, 203, 116, 230), (center, 8), (center, 40), 2)
    pygame.draw.line(surface, (238, 203, 116, 230), (8, center), (40, center), 2)
    return surface


def trim_transparent(surface: pygame.Surface) -> pygame.Surface:
    mask = pygame.mask.from_surface(surface)
    rects = mask.get_bounding_rects()
    if not rects:
        return surface
    bounds = rects[0].copy()
    for rect in rects[1:]:
        bounds.union_ip(rect)
    result = pygame.Surface(bounds.size, pygame.SRCALPHA)
    result.blit(surface, (0, 0), bounds)
    return result


if __name__ == "__main__":
    main()
