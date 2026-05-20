import pygame

from warfront.assets.loader import get_assets
from warfront.assets.registry import ASSET_DIR
from warfront.config import TILE_SIZE
from warfront.world.map_data import DEFAULT_MAP_ID, MAPS


SOLID_TILES = {"#", "w", "S", "t"}
BULLET_BLOCK_TILES = {"#", "w", "S"}
COVER_TILES = {"t", "#"}


class TileMap:
    def __init__(self, map_id: str = DEFAULT_MAP_ID):
        self.map_id = map_id
        self.data = MAPS[map_id]
        self.title = self.data["title"]
        self.briefing = self.data["briefing"]
        self.rows = self.data["rows"]
        self.spawns = self.data["spawns"]
        self.item_spawns = self.data.get("items", {})
        self.door_tiles = list(self.data.get("doors", []))
        self.doors_open = not self.door_tiles
        self.width = len(self.rows[0]) * TILE_SIZE
        self.height = len(self.rows) * TILE_SIZE
        self.capture_rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        assets = get_assets()
        tile_dir = ASSET_DIR / "tilemaps" / "tileset"
        self.tiles = {
            "grass": assets.image(tile_dir / "grass.png"),
            "road": assets.image(tile_dir / "road.png"),
            "trench": assets.image(tile_dir / "trench.png"),
            "water": assets.image(tile_dir / "water.png"),
            "wall": assets.image(tile_dir / "wall.png"),
            "capture": assets.image(tile_dir / "capture_point.png"),
            "sandbag": assets.image(tile_dir / "sandbag_wall.png"),
        }
        self.prop_frames = assets.frames("prop", 42)
        terrain_prop_dir = ASSET_DIR / "cut_sprites" / "props" / "terrain"
        self.terrain_props = {
            name: assets.image(terrain_prop_dir / filename)
            for name, filename in {
                "logs": "logs.png",
                "sandbags": "sandbags_large.png",
                "radio": "radio.png",
                "bush": "bush_small.png",
                "grass": "grass_tall.png",
                "stones": "stones.png",
            }.items()
            if (terrain_prop_dir / filename).exists()
        }
        self._build_collision()
        self._validate_spawns()
        self.props = self._build_props()

    def _build_collision(self) -> None:
        self.solid_rects: list[pygame.Rect] = []
        self.cover_rects: list[pygame.Rect] = []
        self.bullet_solid_rects: list[pygame.Rect] = []
        for y, row in enumerate(self.rows):
            for x, tile in enumerate(row):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                if tile in SOLID_TILES:
                    self.solid_rects.append(rect)
                if tile in BULLET_BLOCK_TILES:
                    self.bullet_solid_rects.append(rect)
                if tile in COVER_TILES:
                    self.cover_rects.append(rect)
                if tile == "C":
                    self.capture_rect = rect.inflate(-8, -8)

    def blocked(self, rect: pygame.Rect) -> bool:
        blockers = self.solid_rects if self.doors_open else [*self.solid_rects, *self.door_rects]
        return any(rect.colliderect(tile) for tile in blockers)

    def bullet_blocked(self, rect: pygame.Rect) -> bool:
        blockers = list(self.bullet_solid_rects)
        if not self.doors_open:
            blockers.extend(self.door_rects)
        return any(rect.colliderect(tile) for tile in blockers)

    def tile_at(self, tile_xy: tuple[int, int]) -> str:
        x, y = tile_xy
        if y < 0 or y >= len(self.rows) or x < 0 or x >= len(self.rows[y]):
            return "#"
        return self.rows[y][x]

    def passable_tile(self, tile_xy: tuple[int, int]) -> bool:
        if not self.doors_open and tile_xy in self.door_tiles:
            return False
        return self.tile_at(tile_xy) not in SOLID_TILES

    def has_line_of_sight(self, start, end, step: int = 12) -> bool:
        start = pygame.Vector2(start)
        end = pygame.Vector2(end)
        delta = end - start
        distance = delta.length()
        if distance <= 1:
            return True
        direction = delta.normalize()
        samples = max(1, int(distance // max(1, step)))
        for index in range(1, samples + 1):
            point = start + direction * min(distance, index * step)
            tile = self.world_to_tile(point)
            if tile == self.world_to_tile(start) or tile == self.world_to_tile(end):
                continue
            if self.tile_at(tile) in BULLET_BLOCK_TILES or (not self.doors_open and tile in self.door_tiles):
                return False
        return True

    def world_to_tile(self, pos: tuple[int, int] | pygame.Vector2) -> tuple[int, int]:
        return int(pos[0] // TILE_SIZE), int(pos[1] // TILE_SIZE)

    def spawn_position(self, tile_xy: tuple[int, int]) -> tuple[int, int]:
        return tile_xy[0] * TILE_SIZE + 8, tile_xy[1] * TILE_SIZE + 8

    def tile_center(self, tile_xy: tuple[int, int]) -> pygame.Vector2:
        return pygame.Vector2(tile_xy[0] * TILE_SIZE + TILE_SIZE // 2, tile_xy[1] * TILE_SIZE + TILE_SIZE // 2)

    def _validate_spawns(self) -> None:
        points = [self.spawns["player"], *self.spawns["enemies"], *self.spawns["tanks"]]
        bad = [point for point in points if self.tile_at(point) in SOLID_TILES]
        if bad:
            raise ValueError(f"Map '{self.map_id}' has blocked spawn tiles: {bad}")
        if len(points) != len(set(points)):
            raise ValueError(f"Map '{self.map_id}' has overlapping spawn tiles")

    def _build_props(self) -> list[tuple[int, int, pygame.Surface]]:
        blocked_points = {self.spawns["player"], *self.spawns["enemies"], *self.spawns["tanks"], *self.door_tiles}
        prop_indices = [3, 4, 5, 9, 12, 13, 17, 18, 27, 28, 29, 41, 43, 47, 48, 57, 63, 65, 70, 71, 73]
        props = []
        terrain_enabled = bool(self.terrain_props)
        fixed_props = {
            "D": "radio",
            "t": "sandbags",
            "g": "bush",
        }
        for y, row in enumerate(self.rows):
            for x, tile in enumerate(row):
                if tile in SOLID_TILES or tile in {"C", "M", "A", "D"} or (x, y) in blocked_points:
                    if tile == "D" and "radio" in self.terrain_props:
                        props.append(self._terrain_prop(x, y, "radio", 0.55, 34))
                    continue
                if tile in fixed_props and fixed_props[tile] in self.terrain_props:
                    seed = self._seed(x, y)
                    if seed % (5 if tile == "t" else 4) == 0:
                        scale = 0.34 if tile == "t" else 0.45
                        props.append(self._terrain_prop(x, y, fixed_props[tile], scale, 36))
                        continue
                seed = self._seed(x, y)
                near_cover = any(self.tile_at((x + dx, y + dy)) in {"#", "t"} for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                place = seed % (6 if near_cover else 19) == 0 and tile in ".rg"
                if not place:
                    continue
                if terrain_enabled:
                    terrain_name = "grass" if tile in ".r" and seed % 3 else "stones"
                    if terrain_name in self.terrain_props:
                        props.append(self._terrain_prop(x, y, terrain_name, 0.36 if terrain_name == "grass" else 0.44, 38))
                        continue
                frame = self.prop_frames[prop_indices[seed % len(prop_indices)]]
                scale = 0.68 if tile == "r" else 0.78
                frame = pygame.transform.smoothscale(frame, (max(12, int(frame.get_width() * scale)), max(12, int(frame.get_height() * scale))))
                px = x * TILE_SIZE + 8 + seed % 18
                py = y * TILE_SIZE + 22 + (seed // 7) % 12
                props.append((px, py, frame))
        return props

    def _terrain_prop(self, x: int, y: int, name: str, scale: float, base_y: int) -> tuple[int, int, pygame.Surface]:
        frame = self.terrain_props[name]
        frame = pygame.transform.smoothscale(
            frame,
            (
                max(10, int(frame.get_width() * scale)),
                max(10, int(frame.get_height() * scale)),
            ),
        )
        px = x * TILE_SIZE + TILE_SIZE // 2
        py = y * TILE_SIZE + base_y
        return px, py, frame

    @staticmethod
    def _seed(x: int, y: int) -> int:
        return (x * 928371 + y * 689287 + 137) & 0xFFFF

    def draw(self, screen: pygame.Surface, camera) -> None:
        start_x = max(0, int(camera.offset.x // TILE_SIZE) - 1)
        start_y = max(0, int(camera.offset.y // TILE_SIZE) - 1)
        end_x = min(len(self.rows[0]), start_x + screen.get_width() // TILE_SIZE + 3)
        end_y = min(len(self.rows), start_y + screen.get_height() // TILE_SIZE + 3)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = self.rows[y][x]
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                view = camera.apply(rect)
                self._draw_tile(screen, tile, view, x, y)

        for x, y, image in self.props:
            rect = image.get_rect(midbottom=(x - int(camera.offset.x), y - int(camera.offset.y)))
            if rect.colliderect(screen.get_rect()):
                shadow = pygame.Surface((rect.width, max(6, rect.height // 5)), pygame.SRCALPHA)
                pygame.draw.ellipse(shadow, (0, 0, 0, 55), shadow.get_rect())
                screen.blit(shadow, shadow.get_rect(center=(rect.centerx + 2, rect.bottom - 4)))
                screen.blit(image, rect)

        self._draw_doors(screen, camera)

    def _draw_doors(self, screen: pygame.Surface, camera) -> None:
        for x, y in self.door_tiles:
            rect = camera.apply(pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
            if self.doors_open:
                pygame.draw.rect(screen, (72, 82, 68), rect.inflate(-10, -16), border_radius=4)
                pygame.draw.line(screen, (210, 188, 111), (rect.left + 10, rect.centery), (rect.right - 10, rect.centery), 2)
                continue
            pygame.draw.rect(screen, (45, 48, 43), rect.inflate(-7, -10), border_radius=5)
            pygame.draw.rect(screen, (191, 163, 82), rect.inflate(-7, -10), 2, border_radius=5)
            for offset in (-10, 0, 10):
                pygame.draw.line(screen, (96, 102, 91), (rect.left + 11, rect.centery + offset), (rect.right - 11, rect.centery + offset), 3)
            pygame.draw.circle(screen, (228, 205, 126), (rect.centerx + 13, rect.centery), 4)

    def _draw_tile(self, screen: pygame.Surface, tile: str, rect: pygame.Rect, x: int, y: int) -> None:
        base = self.tiles["grass"].copy()
        tint = pygame.Surface(base.get_size(), pygame.SRCALPHA)
        shade = 8 + self._seed(x, y) % 16
        tint.fill((shade, shade + 2, shade // 2, 16))
        base.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        screen.blit(base, rect)

        if tile == "r":
            screen.blit(self.tiles["road"], rect)
            self._draw_soft_edges(screen, rect, x, y, "r", (47, 80, 45, 120))
        elif tile == "t":
            self._draw_sandbag_tile(screen, rect, x, y)
        elif tile == "#":
            screen.blit(self.tiles["wall"], rect)
            pygame.draw.rect(screen, (31, 35, 31), rect, 2)
            pygame.draw.line(screen, (118, 124, 108), rect.topleft, rect.topright, 2)
        elif tile == "S":
            pygame.draw.rect(screen, (50, 57, 48), rect)
            pygame.draw.rect(screen, (31, 35, 31), rect, 2)
            pygame.draw.line(screen, (132, 142, 120), rect.topleft, rect.topright, 2)
        elif tile == "w":
            screen.blit(self.tiles["water"], rect)
            self._draw_soft_edges(screen, rect, x, y, "w", (63, 103, 75, 135))
            wave = (pygame.time.get_ticks() // 240 + x * 5 + y * 3) % 12
            pygame.draw.arc(screen, (124, 181, 196), (rect.left + 8, rect.top + 10 + wave, 30, 14), 0, 3.14, 2)
        elif tile == "g":
            pygame.draw.circle(screen, (45, 83, 48), rect.center, 12)
            pygame.draw.circle(screen, (88, 136, 73), (rect.centerx - 5, rect.centery - 4), 7)
        elif tile == "C":
            screen.blit(self.tiles["capture"], rect)
        elif tile in {"M", "A", "D"}:
            screen.blit(self.tiles["road"], rect)
            labels = {"M": "MED", "A": "AMMO", "D": "DEPOT"}
            pygame.draw.rect(screen, (34, 43, 35), rect.inflate(-8, -12), border_radius=4)
            pygame.draw.rect(screen, (210, 188, 111), rect.inflate(-8, -12), 1, border_radius=4)
            label = pygame.font.Font(None, 16).render(labels[tile], True, (238, 232, 207))
            screen.blit(label, label.get_rect(center=rect.center))

        if self._seed(x, y) % 9 == 0 and tile in ".r":
            pygame.draw.circle(screen, (42, 62, 40), (rect.left + 12 + self._seed(x, y) % 22, rect.top + 18), 3)
        if tile == ".":
            self._draw_grass_blades(screen, rect, x, y)

    def _draw_sandbag_tile(self, screen: pygame.Surface, rect: pygame.Rect, x: int, y: int) -> None:
        dust = pygame.Surface(rect.size, pygame.SRCALPHA)
        dust.fill((96, 76, 50, 58))
        screen.blit(dust, rect)
        pygame.draw.ellipse(screen, (20, 18, 13, 70), rect.inflate(-8, -22).move(0, 12))
        sandbag = pygame.transform.smoothscale(self.tiles["sandbag"], (TILE_SIZE + 4, TILE_SIZE // 2 + 10))
        bag_rect = sandbag.get_rect(midbottom=(rect.centerx, rect.bottom - 4))
        screen.blit(sandbag, bag_rect)
        if self.tile_at((x - 1, y)) != "t":
            pygame.draw.line(screen, (88, 69, 47), (rect.left + 5, rect.top + 14), (rect.left + 5, rect.bottom - 8), 2)
        if self.tile_at((x + 1, y)) != "t":
            pygame.draw.line(screen, (88, 69, 47), (rect.right - 5, rect.top + 14), (rect.right - 5, rect.bottom - 8), 2)

    def _draw_soft_edges(self, screen: pygame.Surface, rect: pygame.Rect, x: int, y: int, tile: str, color: tuple[int, int, int, int]) -> None:
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        if self.tile_at((x, y - 1)) != tile:
            pygame.draw.rect(overlay, color, (0, 0, rect.width, 5))
        if self.tile_at((x, y + 1)) != tile:
            pygame.draw.rect(overlay, color, (0, rect.height - 5, rect.width, 5))
        if self.tile_at((x - 1, y)) != tile:
            pygame.draw.rect(overlay, color, (0, 0, 5, rect.height))
        if self.tile_at((x + 1, y)) != tile:
            pygame.draw.rect(overlay, color, (rect.width - 5, 0, 5, rect.height))
        screen.blit(overlay, rect)

    def _draw_grass_blades(self, screen: pygame.Surface, rect: pygame.Rect, x: int, y: int) -> None:
        seed = self._seed(x, y)
        for i in range(3):
            bx = rect.left + 8 + (seed >> (i * 3)) % 34
            by = rect.top + 10 + (seed >> (i * 5)) % 30
            color = (95, 139, 76) if i % 2 else (52, 83, 49)
            pygame.draw.line(screen, color, (bx, by), (bx + 5, by - 3), 2)
    @property
    def door_rects(self) -> list[pygame.Rect]:
        return [
            pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            for x, y in self.door_tiles
        ]

    def open_doors(self) -> None:
        self.doors_open = True
