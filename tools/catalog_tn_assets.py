from __future__ import annotations

import json
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
TN_DIR = Path("D:/My/Games/TN")
ASSET_DIR = ROOT / "warfront" / "assets"
MANIFEST_PATH = ASSET_DIR / "tn_manifest.json"
OVERVIEW_PATH = ROOT / "tn_asset_catalog.png"


SHEET_ROLES = {
    0: ("operations_menu", "Operations/map selection menu concept"),
    1: ("main_menu_shop_weapons", "Main menu, shop UI, weapon cards, item/action fragments"),
    2: ("shop_weapons", "Weapon shop UI and weapon/item fragments"),
    3: ("shop_weapons_compact", "Compact/cropped weapon shop and item fragments"),
    4: ("character_tools", "Character actions with tools and melee weapons"),
    5: ("character_weapons_a", "Character actions with firearms set A"),
    6: ("character_weapons_b", "Character actions with firearms set B"),
    7: ("weapon_catalog_actions", "Weapon names, long guns, and action examples"),
    8: ("character_weapons_c", "Additional character weapon/action rows"),
}


WEAPON_CANDIDATES = [
    "ak47",
    "ak74",
    "stv_380",
    "svd",
    "mosin",
    "vss",
    "tokarev",
    "makarov",
    "pickaxe",
    "grenade",
    "mortar",
    "tank_cannon",
]


def main() -> None:
    files = sorted(TN_DIR.glob("*.png"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"No PNG files found in {TN_DIR}")

    pygame.init()
    try:
        entries = []
        thumbs = []
        for index, path in enumerate(files):
            image = pygame.image.load(str(path))
            role, description = SHEET_ROLES.get(index, (f"tn_sheet_{index:02d}", "Unclassified TN sheet"))
            entries.append(
                {
                    "index": index,
                    "role": role,
                    "description": description,
                    "source": str(path),
                    "width": image.get_width(),
                    "height": image.get_height(),
                    "copy": f"source_sheets/tn_imported/tn_sheet_{index:02d}_{path.name}",
                    "status": "cataloged_needs_precise_cropping",
                }
            )
            thumb = pygame.transform.smoothscale(image, _fit_size(image.get_size(), (260, 210)))
            thumbs.append((thumb, f"{index}: {role}"))

        manifest = {
            "source_dir": str(TN_DIR),
            "generated_by": "tools/catalog_tn_assets.py",
            "sheets": entries,
            "ui_targets": {
                "title": "main_menu_shop_weapons",
                "operations": "operations_menu",
                "shop": "shop_weapons",
            },
            "weapon_candidates": WEAPON_CANDIDATES,
            "animation_groups_needed": [
                "rifle_idle",
                "rifle_walk",
                "rifle_fire",
                "pistol_idle",
                "pistol_walk",
                "pistol_fire",
                "sniper_idle",
                "sniper_walk",
                "sniper_fire",
                "pickaxe_idle",
                "pickaxe_walk",
                "pickaxe_attack",
                "grenade_throw",
                "death",
            ],
            "next_step": "Open tn_asset_catalog.png, record exact crop rectangles, then promote entries from candidates to cut sprites.",
        }

        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _save_overview(thumbs)
        print(f"Wrote {MANIFEST_PATH}")
        print(f"Wrote {OVERVIEW_PATH}")
    finally:
        pygame.quit()


def _fit_size(size: tuple[int, int], bounds: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    bound_w, bound_h = bounds
    scale = min(bound_w / width, bound_h / height)
    return max(1, int(width * scale)), max(1, int(height * scale))


def _save_overview(thumbs: list[tuple[pygame.Surface, str]]) -> None:
    font = pygame.font.SysFont("consolas", 15)
    cols = 3
    cell_w, cell_h = 300, 250
    rows = (len(thumbs) + cols - 1) // cols
    sheet = pygame.Surface((cols * cell_w, rows * cell_h), pygame.SRCALPHA)
    sheet.fill((24, 30, 26))
    for index, (thumb, label) in enumerate(thumbs):
        x = (index % cols) * cell_w
        y = (index // cols) * cell_h
        pygame.draw.rect(sheet, (52, 65, 55), pygame.Rect(x + 10, y + 10, cell_w - 20, cell_h - 20), 1)
        sheet.blit(thumb, thumb.get_rect(center=(x + cell_w // 2, y + 112)))
        text = font.render(label, True, (238, 232, 207))
        sheet.blit(text, (x + 18, y + 218))
    pygame.image.save(sheet, str(OVERVIEW_PATH))


if __name__ == "__main__":
    main()
