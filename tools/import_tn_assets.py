from __future__ import annotations

import shutil
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
TN_DIR = Path("D:/My/Games/TN")
SOURCE_DIR = ROOT / "warfront" / "assets" / "source_sheets" / "tn_imported"
UI_SCREEN_DIR = ROOT / "warfront" / "assets" / "ui" / "screens"
UI_ICON_DIR = ROOT / "warfront" / "assets" / "ui" / "icons"


def main() -> None:
    files = sorted(TN_DIR.glob("*.png"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"Không thấy PNG trong {TN_DIR}")

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    UI_SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    UI_ICON_DIR.mkdir(parents=True, exist_ok=True)

    pygame.init()
    try:
        for index, path in enumerate(files):
            shutil.copy2(path, SOURCE_DIR / f"tn_sheet_{index:02d}_{path.name}")

        # New TN sheets are ordered by most recently modified:
        # 0: operations menu, 1-3: shop/weapon menu, 4-8: character weapon/action sheets.
        copy_scaled(files[0], UI_SCREEN_DIR / "menu_operations_concept.png", (1100, 650))
        if len(files) > 1:
            copy_scaled(files[1], UI_SCREEN_DIR / "shop_weapons_concept.png", (420, 650))

        # A clean pickaxe icon from the existing prop sheet; the newly imported sheets are kept
        # in source_sheets for later animation mapping.
        prop_pickaxe = ROOT / "warfront" / "assets" / "cut_sprites" / "props" / "prop_030.png"
        if prop_pickaxe.exists():
            copy_scaled(prop_pickaxe, UI_ICON_DIR / "pickaxe.png", (42, 42))

        print(f"Imported {len(files)} TN sheets into {SOURCE_DIR}")
        print(f"UI screens written to {UI_SCREEN_DIR}")
    finally:
        pygame.quit()


def copy_scaled(source: Path, target: Path, size: tuple[int, int]) -> None:
    image = pygame.image.load(str(source))
    scaled = pygame.transform.smoothscale(image, size)
    pygame.image.save(scaled, str(target))


if __name__ == "__main__":
    main()
