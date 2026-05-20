from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from warfront.assets import registry


WHITE_THRESHOLD = 242
PADDING = 6


@dataclass(frozen=True)
class SheetJob:
    source: Path
    output_dir: Path
    prefix: str
    min_area: int
    max_items: int
    min_size: tuple[int, int] = (12, 12)
    max_size: tuple[int, int] = (280, 280)


def ensure_dirs() -> None:
    for path in [
        registry.ASSET_DIR / "ui" / "icons",
        registry.ASSET_DIR / "ui" / "cursor",
        registry.ASSET_DIR / "cut_sprites" / "characters",
        registry.ASSET_DIR / "cut_sprites" / "vehicles",
        registry.ASSET_DIR / "cut_sprites" / "aircraft",
        registry.ASSET_DIR / "cut_sprites" / "props",
        registry.ASSET_DIR / "cut_sprites" / "effects",
        registry.ASSET_DIR / "tilemaps" / "tileset",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def rgba_without_white_background(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    arr = np.array(image)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    white = (rgb[:, :, 0] > WHITE_THRESHOLD) & (rgb[:, :, 1] > WHITE_THRESHOLD) & (rgb[:, :, 2] > WHITE_THRESHOLD)
    alpha[white] = 0
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def component_boxes(image: Image.Image, min_area: int, min_size: tuple[int, int], max_size: tuple[int, int]) -> list[tuple[int, int, int, int, int]]:
    arr = np.array(image)
    mask = arr[:, :, 3] > 0
    labels, count = ndimage.label(mask)
    slices = ndimage.find_objects(labels)
    boxes: list[tuple[int, int, int, int, int]] = []

    for label_id, slc in enumerate(slices, start=1):
        if slc is None:
            continue
        ys, xs = slc
        x1, x2 = xs.start, xs.stop
        y1, y2 = ys.start, ys.stop
        w, h = x2 - x1, y2 - y1
        if w < min_size[0] or h < min_size[1] or w > max_size[0] or h > max_size[1]:
            continue
        area = int((labels[slc] == label_id).sum())
        if area < min_area:
            continue
        boxes.append((x1, y1, x2, y2, area))

    boxes.sort(key=lambda box: (box[1], box[0]))
    return boxes


def crop_with_padding(image: Image.Image, box: tuple[int, int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2, _ = box
    x1 = max(0, x1 - PADDING)
    y1 = max(0, y1 - PADDING)
    x2 = min(image.width, x2 + PADDING)
    y2 = min(image.height, y2 + PADDING)
    return image.crop((x1, y1, x2, y2))


def extract_sheet(job: SheetJob) -> list[dict[str, object]]:
    image = rgba_without_white_background(job.source)
    boxes = component_boxes(image, job.min_area, job.min_size, job.max_size)[: job.max_items]
    metadata = []
    for index, box in enumerate(boxes):
        crop = crop_with_padding(image, box)
        filename = f"{job.prefix}_{index:03d}.png"
        out = job.output_dir / filename
        crop.save(out)
        metadata.append(
            {
                "name": out.stem,
                "file": str(out.relative_to(registry.ASSET_DIR)).replace("\\", "/"),
                "source": job.source.name,
                "source_box": box[:4],
                "size": crop.size,
            }
        )
    return metadata


def draw_icon(path: Path, kind: str) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    if kind == "hp":
        d.rounded_rectangle((8, 14, 56, 50), radius=8, fill=(65, 78, 55), outline=(35, 39, 32), width=3)
        d.rectangle((28, 20, 36, 44), fill=(232, 232, 210))
        d.rectangle((20, 28, 44, 36), fill=(232, 232, 210))
    elif kind == "ammo":
        for x in (18, 27, 36):
            d.rounded_rectangle((x, 14, x + 8, 50), radius=3, fill=(190, 139, 66), outline=(64, 47, 31), width=2)
            d.rectangle((x, 14, x + 8, 22), fill=(216, 185, 92))
    elif kind == "objective":
        d.ellipse((10, 10, 54, 54), outline=(226, 196, 82), width=5)
        d.ellipse((22, 22, 42, 42), outline=(226, 196, 82), width=4)
        d.line((32, 8, 32, 56), fill=(42, 39, 32), width=3)
        d.line((8, 32, 56, 32), fill=(42, 39, 32), width=3)
    elif kind == "restart":
        d.arc((13, 13, 51, 51), 35, 330, fill=(232, 232, 210), width=6)
        d.polygon([(46, 11), (55, 24), (39, 25)], fill=(232, 232, 210))
    elif kind == "warning":
        d.polygon([(32, 8), (57, 54), (7, 54)], fill=(184, 59, 47), outline=(45, 34, 30))
        d.rectangle((29, 23, 35, 40), fill=(250, 229, 170))
        d.rectangle((29, 45, 35, 50), fill=(250, 229, 170))
    image.save(path)


def draw_crosshair(path: Path) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.ellipse((18, 18, 46, 46), outline=(235, 230, 205), width=3)
    d.ellipse((27, 27, 37, 37), outline=(184, 59, 47), width=2)
    d.line((32, 2, 32, 20), fill=(235, 230, 205), width=3)
    d.line((32, 44, 32, 62), fill=(235, 230, 205), width=3)
    d.line((2, 32, 20, 32), fill=(235, 230, 205), width=3)
    d.line((44, 32, 62, 32), fill=(235, 230, 205), width=3)
    image.save(path)


def tile_base(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGBA", (48, 48), (*color, 255))


def draw_tileset() -> None:
    out_dir = registry.ASSET_DIR / "tilemaps" / "tileset"
    tiles: dict[str, Image.Image] = {}

    grass = tile_base((70, 108, 62))
    d = ImageDraw.Draw(grass)
    for i in range(14):
        x = (i * 13) % 48
        y = (i * 19) % 48
        d.line((x, y, x + 5, y - 3), fill=(96, 140, 75), width=2)
    tiles["grass.png"] = grass

    road = tile_base((96, 86, 72))
    d = ImageDraw.Draw(road)
    for y in range(8, 48, 12):
        d.line((0, y, 48, y + 4), fill=(118, 108, 90), width=2)
    tiles["road.png"] = road

    trench = tile_base((82, 61, 43))
    d = ImageDraw.Draw(trench)
    d.rounded_rectangle((7, 8, 41, 40), radius=6, fill=(48, 36, 29))
    for x in range(8, 42, 8):
        d.line((x, 8, x + 4, 40), fill=(124, 95, 62), width=3)
    tiles["trench.png"] = trench

    water = tile_base((43, 91, 117))
    d = ImageDraw.Draw(water)
    for y in (13, 28, 41):
        d.arc((4, y - 8, 28, y + 8), 15, 165, fill=(108, 160, 178), width=2)
        d.arc((24, y - 8, 48, y + 8), 15, 165, fill=(108, 160, 178), width=2)
    tiles["water.png"] = water

    wall = tile_base((78, 80, 73))
    d = ImageDraw.Draw(wall)
    for y in range(0, 48, 16):
        d.rectangle((0, y, 48, y + 15), outline=(42, 45, 42), width=2)
    for x in range(0, 48, 16):
        d.line((x, 0, x, 48), fill=(98, 101, 92), width=1)
    tiles["wall.png"] = wall

    sandbag = Image.new("RGBA", (96, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(sandbag)
    for row, y in enumerate((24, 12, 2)):
        for x in range(4 + row * 10, 84 - row * 10, 24):
            d.rounded_rectangle((x, y, x + 28, y + 15), radius=7, fill=(158, 132, 92), outline=(75, 58, 40), width=2)
    tiles["sandbag_wall.png"] = sandbag

    capture = tile_base((132, 121, 80))
    d = ImageDraw.Draw(capture)
    d.ellipse((9, 9, 39, 39), outline=(190, 67, 54), width=4)
    d.line((24, 4, 24, 44), fill=(40, 37, 32), width=3)
    tiles["capture_point.png"] = capture

    for name, tile in tiles.items():
        tile.save(out_dir / name)


def generate_ui() -> None:
    icon_dir = registry.ASSET_DIR / "ui" / "icons"
    for kind in ["hp", "ammo", "objective", "restart", "warning"]:
        draw_icon(icon_dir / f"{kind}.png", kind)
    draw_crosshair(registry.ASSET_DIR / "ui" / "cursor" / "crosshair.png")


def main() -> int:
    ensure_dirs()
    metadata: dict[str, list[dict[str, object]]] = {}

    jobs = [
        SheetJob(registry.CHARACTERS["allied_soldier"], registry.ASSET_DIR / "cut_sprites" / "characters", "allied_soldier", 280, 180, (18, 24), (130, 130)),
        SheetJob(registry.CHARACTERS["axis_soldier"], registry.ASSET_DIR / "cut_sprites" / "characters", "axis_soldier", 280, 180, (18, 24), (130, 130)),
        SheetJob(registry.VEHICLES["allied_m4_sherman"], registry.ASSET_DIR / "cut_sprites" / "vehicles", "m4_sherman", 900, 160, (35, 24), (260, 170)),
        SheetJob(registry.AIRCRAFT["axis_heavy_bomber"], registry.ASSET_DIR / "cut_sprites" / "aircraft", "axis_bomber", 900, 170, (35, 24), (260, 180)),
        SheetJob(registry.PROPS["military_support_logistics"], registry.ASSET_DIR / "cut_sprites" / "props", "prop", 260, 140, (16, 16), (190, 130)),
    ]

    for job in jobs:
        metadata[job.prefix] = extract_sheet(job)

    effect_sources = [
        (registry.VEHICLES["allied_m4_sherman"], "tank_effect"),
        (registry.AIRCRAFT["axis_heavy_bomber"], "air_effect"),
        (registry.PROPS["military_support_logistics"], "prop_effect"),
    ]
    effects = []
    for source, prefix in effect_sources:
        image = rgba_without_white_background(source)
        boxes = component_boxes(image, 450, (18, 18), (180, 180))
        orange_boxes = []
        arr = np.array(image)
        for box in boxes:
            x1, y1, x2, y2, _ = box
            crop = arr[y1:y2, x1:x2]
            alpha = crop[:, :, 3] > 0
            if not alpha.any():
                continue
            red = crop[:, :, 0] > 150
            warm = crop[:, :, 1] > 70
            blue_low = crop[:, :, 2] < 95
            smoke = (crop[:, :, 0] > 80) & (crop[:, :, 0] < 180) & (abs(crop[:, :, 0].astype(int) - crop[:, :, 1].astype(int)) < 35)
            score = int(((red & warm & blue_low) | smoke & alpha).sum())
            if score > 80:
                orange_boxes.append((score, box))
        orange_boxes.sort(key=lambda item: (-item[0], item[1][1], item[1][0]))
        for index, (_, box) in enumerate(orange_boxes[:36]):
            crop = crop_with_padding(image, box)
            out = registry.ASSET_DIR / "cut_sprites" / "effects" / f"{prefix}_{index:03d}.png"
            crop.save(out)
            effects.append({"name": out.stem, "file": str(out.relative_to(registry.ASSET_DIR)).replace("\\", "/"), "source": source.name, "source_box": box[:4], "size": crop.size})
    metadata["effects"] = effects

    generate_ui()
    draw_tileset()

    with (registry.ASSET_DIR / "generated_assets.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("Generated assets:")
    for group, items in metadata.items():
        print(f"  {group}: {len(items)} sprites")
    print("  ui/icons: 5 icons")
    print("  ui/cursor: 1 cursor")
    print("  tilemaps/tileset: 7 tiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

