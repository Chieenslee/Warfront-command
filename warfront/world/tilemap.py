import pygame
from collections import defaultdict, deque
from heapq import heappop, heappush

from warfront.assets.loader import get_assets
from warfront.assets.registry import ASSET_DIR
from warfront.config import TILE_SIZE
from warfront.entities.animations import get_soldier_frames, get_tank_frames
from warfront.world.map_data import DEFAULT_MAP_ID, MAPS


SOLID_TILES = {"#", "w", "S", "t"}
BULLET_BLOCK_TILES = {"#", "S"}
COVER_TILES = {"t", "#"}


class TileMap:
    def __init__(self, map_id: str = DEFAULT_MAP_ID):
        self.map_id = map_id
        self.data = MAPS[map_id]
        self.title = self.data["title"]
        self.briefing = self.data["briefing"]
        self.spawns = self.data["spawns"]
        self.item_spawns = self.data.get("items", {})
        self.door_tiles = list(self.data.get("doors", []))
        self.rows = self._repair_supply_access(self.data["rows"])
        self.doors_open = not self.door_tiles
        self.width = len(self.rows[0]) * TILE_SIZE
        self.height = len(self.rows) * TILE_SIZE
        self.capture_rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        self._tile_cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._shadow_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._prop_bucket_size = 512
        self._marker_font = pygame.font.Font(None, 16)
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
        self._prop_buckets = self._build_prop_buckets()

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
        if rect.left < 0 or rect.top < 0 or rect.right > self.width or rect.bottom > self.height:
            return True
        blockers = self.solid_rects if self.doors_open else [*self.solid_rects, *self.door_rects]
        return any(rect.colliderect(tile) for tile in blockers)

    def bullet_blocked(self, rect: pygame.Rect) -> bool:
        if rect.right < 0 or rect.bottom < 0 or rect.left > self.width or rect.top > self.height:
            return True
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

    def _repair_supply_access(self, source_rows: tuple[str, ...]) -> tuple[str, ...]:
        if not self.item_spawns:
            return source_rows

        rows = [list(row) for row in source_rows]
        door_tiles = set(self.door_tiles)
        item_points = [
            point
            for points in self.item_spawns.values()
            for point in points
        ]

        def reachable_tiles() -> set[tuple[int, int]]:
            start = self.spawns["player"]
            queue = deque([start])
            seen = {start}
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if not (0 <= ny < len(rows) and 0 <= nx < len(rows[ny])) or (nx, ny) in seen:
                        continue
                    tile = rows[ny][nx]
                    if tile in SOLID_TILES and (nx, ny) not in door_tiles:
                        continue
                    seen.add((nx, ny))
                    queue.append((nx, ny))
            return seen

        reachable = reachable_tiles()
        for item in item_points:
            if item in reachable:
                continue
            path = self._supply_access_path(rows, item, reachable, door_tiles)
            if not path:
                continue
            for x, y in path:
                if rows[y][x] in {"#", "t"}:
                    rows[y][x] = "."
            reachable = reachable_tiles()

        return tuple("".join(row) for row in rows)

    def _supply_access_path(
        self,
        rows: list[list[str]],
        start: tuple[int, int],
        reachable: set[tuple[int, int]],
        door_tiles: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        frontier: list[tuple[int, int, int, int]] = []
        heappush(frontier, (0, 0, start[0], start[1]))
        best = {start: (0, 0)}
        previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        target: tuple[int, int] | None = None

        while frontier:
            breaks, distance, x, y = heappop(frontier)
            point = (x, y)
            if best.get(point) != (breaks, distance):
                continue
            if point in reachable:
                target = point
                break
            if breaks > 4:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= ny < len(rows) and 0 <= nx < len(rows[ny])):
                    continue
                tile = rows[ny][nx]
                if tile == "w":
                    continue
                breakable = tile in {"#", "t"} and (nx, ny) not in door_tiles
                if breakable and (nx == 0 or ny == 0 or nx == len(rows[ny]) - 1 or ny == len(rows) - 1):
                    continue
                next_breaks = breaks + (1 if breakable else 0)
                if next_breaks > 4 or (tile == "S" and (nx, ny) not in door_tiles):
                    continue
                next_distance = distance + 1
                next_point = (nx, ny)
                if (next_breaks, next_distance) >= best.get(next_point, (999, 99999)):
                    continue
                best[next_point] = (next_breaks, next_distance)
                previous[next_point] = point
                heappush(frontier, (next_breaks, next_distance, nx, ny))

        if target is None:
            return []
        path = []
        point: tuple[int, int] | None = target
        while point is not None:
            path.append(point)
            point = previous[point]
        path.reverse()
        return path

    def _build_props(self) -> list[tuple[int, int, pygame.Surface]]:
        blocked_points = {self.spawns["player"], *self.spawns["enemies"], *self.spawns["tanks"], *self.door_tiles}
        prop_count = len(self.prop_frames)
        props = []
        terrain_enabled = bool(self.terrain_props)
        fixed_props = {
            "t": "sandbags",
            "g": "bush",
        }
        for y, row in enumerate(self.rows):
            for x, tile in enumerate(row):
                if tile in SOLID_TILES or tile in {"C", "M", "A", "D"} or (x, y) in blocked_points:
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
                frame = self.prop_frames[seed % prop_count]
                scale = 0.68 if tile == "r" else 0.78
                frame = pygame.transform.smoothscale(frame, (max(12, int(frame.get_width() * scale)), max(12, int(frame.get_height() * scale))))
                px = x * TILE_SIZE + 8 + seed % 18
                py = y * TILE_SIZE + 22 + (seed // 7) % 12
                props.append((px, py, frame))
        props.extend(self._build_spawn_decorations(blocked_points))
        props.extend(self._build_decorations(blocked_points))
        return props

    def _build_spawn_decorations(self, blocked_points: set[tuple[int, int]]) -> list[tuple[int, int, pygame.Surface]]:
        assets = get_assets()
        spawn = self.spawns["player"]
        protected = self._protected_decoration_tiles(blocked_points)
        protected.update((spawn[0] + dx, spawn[1] + dy) for dx in range(-2, 3) for dy in range(-2, 3))
        protected.update(
            (x + dx, y + dy)
            for x, y in self.door_tiles
            for dx in range(-1, 2)
            for dy in range(-1, 2)
        )

        candidates: list[tuple[int, int, int]] = []
        safe_zones = self.data.get("safe_zones", [])
        if safe_zones:
            for zone in safe_zones:
                x0, y0, width, height = zone["rect"]
                for y in range(max(1, y0 - 3), min(len(self.rows) - 1, y0 + height + 4)):
                    for x in range(max(1, x0 - 3), min(len(self.rows[0]) - 1, x0 + width + 4)):
                        edge_distance = min(abs(x - x0), abs(x - (x0 + width - 1)), abs(y - y0), abs(y - (y0 + height - 1)))
                        if edge_distance <= 4:
                            candidates.append((self._seed(x, y), x, y))
        else:
            for y in range(max(1, spawn[1] - 7), min(len(self.rows) - 1, spawn[1] + 8)):
                for x in range(max(1, spawn[0] - 7), min(len(self.rows[0]) - 1, spawn[0] + 8)):
                    candidates.append((self._seed(x, y), x, y))

        decorations: list[tuple[int, int, pygame.Surface]] = []
        reserved = set(protected)
        is_mega = len(self.rows[0]) >= 100 or len(self.rows) >= 70
        target_count = 12 if is_mega else 8
        radio_used = False
        barrel_prop_indices = [100, 101, 102, 103, 104, 105, 106, 108, 109, 110, 121, 122, 124, 125]
        debris_prop_indices = [3, 4, 5, 9, 12, 13, 17, 18, 27, 28, 29, 63, 65, 70, 71, 73, 118, 119, 123, 130, 131, 132]
        soldier_frames = (
            ("allied_soldier", get_soldier_frames("allied", "downed")),
            ("axis_soldier", get_soldier_frames("axis", "downed")),
        )

        for seed, x, y in sorted(candidates):
            if len(decorations) >= target_count:
                break
            if not self._can_place_decoration(x, y, reserved):
                continue
            if any((x + dx, y + dy) in reserved for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue

            reserved.add((x, y))
            px = x * TILE_SIZE + TILE_SIZE // 2 + (seed % 13) - 6
            py = y * TILE_SIZE + 39 + ((seed >> 4) % 8)
            kind = len(decorations) % 6
            if not radio_used and "radio" in self.terrain_props:
                decorations.append(self._terrain_prop(x, y, "radio", 0.5, 34))
                radio_used = True
            elif kind in (0, 1):
                frame = assets.frame("prop", barrel_prop_indices[(seed >> 5) % len(barrel_prop_indices)], 34)
                decorations.append((px, py, frame))
            elif kind == 2:
                group, frames = soldier_frames[(seed >> 3) % len(soldier_frames)]
                frame = assets.frame(group, frames[(seed >> 5) % len(frames)], 42)
                if seed & 1:
                    frame = pygame.transform.flip(frame, True, False)
                decorations.append((px, py + 1, frame))
            else:
                frame = assets.frame("prop", debris_prop_indices[(seed >> 6) % len(debris_prop_indices)], 28)
                decorations.append((px, py, frame))
        return decorations

    def _build_decorations(self, blocked_points: set[tuple[int, int]]) -> list[tuple[int, int, pygame.Surface]]:
        assets = get_assets()
        width = len(self.rows[0])
        height = len(self.rows)
        total_tiles = width * height
        target_count = max(7, min(120, total_tiles // 170))
        if width >= 100 or height >= 70:
            target_count = max(42, min(150, total_tiles // 135))

        protected = self._protected_decoration_tiles(blocked_points)

        soldier_frames = (
            ("allied_soldier", get_soldier_frames("allied", "downed")),
            ("axis_soldier", get_soldier_frames("axis", "downed")),
        )
        tank_wreck_frames = get_tank_frames("wreck")
        barrel_prop_indices = [100, 101, 102, 103, 104, 105, 106, 108, 109, 110, 121, 122, 124, 125]
        debris_prop_indices = [3, 4, 5, 9, 12, 13, 17, 18, 27, 28, 29, 63, 65, 70, 71, 73, 118, 119, 123, 130, 131, 132]

        decorations: list[tuple[int, int, pygame.Surface]] = []
        step = 5 if target_count < 35 else 4
        for y in range(1, height - 1, step):
            for x in range(1, width - 1, step):
                if len(decorations) >= target_count:
                    return decorations
                if (x, y) in protected or self.rows[y][x] not in ".rg":
                    continue
                if any((x + dx, y + dy) in protected for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    continue
                seed = self._seed(x, y)
                if seed % 11 > 2:
                    continue

                px = x * TILE_SIZE + TILE_SIZE // 2 + (seed % 9) - 4
                py = y * TILE_SIZE + 38 + ((seed >> 4) % 7)
                kind = seed % 10
                if kind in (0, 1):
                    group, frames = soldier_frames[(seed >> 3) % len(soldier_frames)]
                    frame = assets.frame(group, frames[(seed >> 5) % len(frames)], 42)
                    if seed & 1:
                        frame = pygame.transform.flip(frame, True, False)
                    decorations.append((px, py, frame))
                elif kind in (2, 3):
                    frame = assets.frame("m4_sherman", tank_wreck_frames[(seed >> 5) % len(tank_wreck_frames)], 58)
                    if seed & 2:
                        frame = pygame.transform.flip(frame, True, False)
                    decorations.append((px, py + 8, frame))
                elif kind in (4, 5, 6):
                    frame = assets.frame("prop", barrel_prop_indices[(seed >> 6) % len(barrel_prop_indices)], 34)
                    decorations.append((px, py, frame))
                else:
                    frame = assets.frame("prop", debris_prop_indices[(seed >> 6) % len(debris_prop_indices)], 28)
                    decorations.append((px, py, frame))
        return decorations

    def _protected_decoration_tiles(self, blocked_points: set[tuple[int, int]]) -> set[tuple[int, int]]:
        item_points = {
            point
            for points in self.item_spawns.values()
            for point in points
        }
        protected = {
            *blocked_points,
            *item_points,
            *self.door_tiles,
        }
        protected.update(
            (x, y)
            for y, row in enumerate(self.rows)
            for x, tile in enumerate(row)
            if tile in {"C", "M", "A", "D"}
        )
        return protected

    def _can_place_decoration(self, x: int, y: int, protected: set[tuple[int, int]]) -> bool:
        if (x, y) in protected:
            return False
        if y <= 0 or y >= len(self.rows) - 1 or x <= 0 or x >= len(self.rows[y]) - 1:
            return False
        return self.rows[y][x] in ".rg"

    def _build_prop_buckets(self) -> dict[tuple[int, int], list[tuple[int, int, pygame.Surface]]]:
        buckets: dict[tuple[int, int], list[tuple[int, int, pygame.Surface]]] = defaultdict(list)
        for prop in self.props:
            x, y, _image = prop
            buckets[(x // self._prop_bucket_size, y // self._prop_bucket_size)].append(prop)
        return dict(buckets)

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
                screen.blit(self._tile_surface(tile, x, y), camera.apply(rect))

        for x, y, image in self._visible_props(camera):
            rect = image.get_rect(midbottom=(x - int(camera.offset.x), y - int(camera.offset.y)))
            shadow = self._prop_shadow(rect.width, max(6, rect.height // 5))
            screen.blit(shadow, shadow.get_rect(center=(rect.centerx + 2, rect.bottom - 4)))
            screen.blit(image, rect)

        self._draw_doors(screen, camera)

    def _visible_props(self, camera) -> list[tuple[int, int, pygame.Surface]]:
        view = pygame.Rect(
            int(camera.offset.x) - 128,
            int(camera.offset.y) - 128,
            pygame.display.get_surface().get_width() + 256,
            pygame.display.get_surface().get_height() + 256,
        )
        min_bx = view.left // self._prop_bucket_size
        max_bx = view.right // self._prop_bucket_size
        min_by = view.top // self._prop_bucket_size
        max_by = view.bottom // self._prop_bucket_size
        visible = []
        for by in range(min_by, max_by + 1):
            for bx in range(min_bx, max_bx + 1):
                for prop in self._prop_buckets.get((bx, by), []):
                    x, y, image = prop
                    if view.colliderect(image.get_rect(midbottom=(x, y))):
                        visible.append(prop)
        return visible

    def _prop_shadow(self, width: int, height: int) -> pygame.Surface:
        key = (width, height)
        cached = self._shadow_cache.get(key)
        if cached is not None:
            return cached
        shadow = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 55), shadow.get_rect())
        self._shadow_cache[key] = shadow
        return shadow

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
            label = self._marker_font.render(labels[tile], True, (238, 232, 207))
            screen.blit(label, label.get_rect(center=rect.center))

        if self._seed(x, y) % 9 == 0 and tile in ".r":
            pygame.draw.circle(screen, (42, 62, 40), (rect.left + 12 + self._seed(x, y) % 22, rect.top + 18), 3)
        if tile == ".":
            self._draw_grass_blades(screen, rect, x, y)

    def _tile_surface(self, tile: str, x: int, y: int) -> pygame.Surface:
        key = (tile, self._seed(x, y) % 16, self._neighbor_mask(tile, x, y))
        cached = self._tile_cache.get(key)
        if cached is not None:
            return cached
        surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self._draw_tile(surface, tile, surface.get_rect(), x, y)
        self._tile_cache[key] = surface
        return surface

    def _neighbor_mask(self, tile: str, x: int, y: int) -> int:
        if tile not in {"r", "w", "t"}:
            return 0
        mask = 0
        for bit, (dx, dy) in enumerate(((0, -1), (0, 1), (-1, 0), (1, 0))):
            if self.tile_at((x + dx, y + dy)) == tile:
                mask |= 1 << bit
        return mask

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
