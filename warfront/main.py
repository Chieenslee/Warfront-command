import math
import random
import sys
import json
from pathlib import Path

import pygame

from warfront.assets.loader import get_assets
from warfront.assets.registry import ASSET_DIR
from warfront.config import CAPTURE_SECONDS, FPS, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_SIZE
from warfront.core.camera import Camera
from warfront.entities.items import ITEM_AMMO, ITEM_GRENADE, ITEM_MEDKIT, Item
from warfront.entities.grenade import GrenadeProjectile
from warfront.entities.soldier import Soldier
from warfront.entities.support import EnemyAircraft, MortarShell
from warfront.entities.vehicles import TankVehicle
from warfront.systems.balance import UNIT_STATS
from warfront.systems.campaign import CHAPTERS_BY_MAP, SHOP_ITEMS, CampaignState
from warfront.systems.combat_effects import CombatEffects
from warfront.systems.inventory import Inventory
from warfront.systems.modes import OFFLINE_CONFIG, ModeConfig
from warfront.systems.particles import ParticleSystem
from warfront.systems.weapons import WEAPONS, weapon_name
from warfront.world import astar, bfs_nearest, dfs_reachable, grid_from_tilemap
from warfront.world.map_data import DEFAULT_MAP_ID, MAPS
from warfront.world.tilemap import TileMap

SAVE_PATH = Path.home() / ".warfront_command" / "save.json"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Warfront Command")
        self.fullscreen = True
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22)
        self.small_font = pygame.font.SysFont("consolas", 16)
        self.big_font = pygame.font.SysFont("consolas", 48, bold=True)
        self.assets = get_assets()
        pygame.mouse.set_visible(False)
        self.map_ids = list(MAPS)
        self.selected_map_index = self.map_ids.index(DEFAULT_MAP_ID)
        self.state = "title"
        self.menu_tab = "operations"
        self.shop_page = 0
        self.shop_filter = "all"
        self.title_buttons: list[tuple[pygame.Rect, str]] = []
        self.title_selection = 1
        self.title_notice = ""
        self.menu_buttons: list[tuple[pygame.Rect, str]] = []
        self.result_buttons: list[tuple[pygame.Rect, str]] = []
        self.campaign = self._load_campaign()
        self.mode_config: ModeConfig = OFFLINE_CONFIG
        self.inventory = Inventory(medkits=1, grenades=1, ammo=90)
        self.weapon_mode = "rifle"
        self.equipped_primary = "rifle"
        self.equipped_sidearm = "tokarev"
        self.sounds = self._load_sounds()
        self._start_music()
        self.reset(self.current_map_id)

    @property
    def current_map_id(self) -> str:
        return self.map_ids[self.selected_map_index]

    def reset(self, map_id: str | None = None) -> None:
        if map_id and map_id in self.map_ids:
            self.selected_map_index = self.map_ids.index(map_id)
        self.tilemap = TileMap(map_id or self.current_map_id)
        self.camera = Camera(self.tilemap.width, self.tilemap.height)
        spawns = self.tilemap.spawns
        self.player = Soldier(self.tilemap.spawn_position(spawns["player"]), is_player=True)
        self.player.weapon_pose = WEAPONS.get(self.weapon_mode, WEAPONS["rifle"]).animation_key
        self.enemies = [Soldier(self.tilemap.spawn_position(pos)) for pos in spawns["enemies"]]
        self.bullets = []
        self.grenades = []
        self.enemy_aircraft = self._spawn_enemy_aircraft(spawns)
        self.mortar_shells = []
        self.melee_swings = []
        self.floaters: list[tuple[str, pygame.Vector2, tuple[int, int, int], float]] = []
        self.mortar_cooldown = 0.0
        self.particles = ParticleSystem()
        self.effects = CombatEffects(self.particles)
        self.corpses: list[tuple[pygame.Surface, pygame.Rect, float]] = []
        armor_bonus = self.campaign.purchases.get("armor", 0) * 20
        self.player.max_hp += armor_bonus
        self.player.hp = self.player.max_hp
        self.player.armor += self.campaign.purchases.get("armor", 0) * 4
        self.player.vehicle = None
        self.enemy_vehicles = [
            TankVehicle(self.tilemap.spawn_position(pos), self._enemy_tank_kind(index), faction="enemy")
            for index, pos in enumerate(spawns["tanks"])
        ]
        self.vehicles = self._spawn_player_vehicles()
        pouch_level = self.campaign.purchases.get("field_pouches", 0)
        self.inventory.ammo = max(self.inventory.ammo, 45 + pouch_level * 20)
        self.inventory.medkits = max(self.inventory.medkits, 1 + pouch_level)
        self.inventory.grenades = max(self.inventory.grenades, 1 + pouch_level)
        self.items = self._spawn_items()
        self.passable_grid = grid_from_tilemap(self.tilemap)
        self.reachable_tiles = dfs_reachable(self.tilemap.world_to_tile(self.player.rect.center), self.passable_grid)
        self.enemy_paths: dict[int, list[tuple[int, int]]] = {}
        self.ai_timer = 0.0
        self.mission_started = self.tilemap.doors_open
        self.mission_grace = 0.0
        self.mission_elapsed = 0.0
        self.capture = 0.0
        self.result = None
        self.result_awarded = False
        self.result_reward = 0
        self.stats = {"inf": 0, "armor": 0, "air": 0, "supplies": 0}
        self.radio_log: list[tuple[str, tuple[int, int, int], float]] = []
        self.add_radio(f"DEPLOY: {self.tilemap.data['title']}", (238, 203, 116), 5.0)
        self._start_music()

    def _spawn_enemy_aircraft(self, spawns: dict) -> list[EnemyAircraft]:
        aircraft = []
        for run in [*spawns.get("aircraft_enemies", []), *spawns.get("air_support", [])]:
            aircraft.append(
                EnemyAircraft(
                    self.tilemap.tile_center(tuple(run["entry"])),
                    self.tilemap.tile_center(tuple(run["exit"])),
                    self.tilemap.tile_center(tuple(run.get("target", run["exit"]))),
                    str(run.get("unit", "bomber")),
                )
            )
        return aircraft

    def _load_sounds(self) -> dict[str, pygame.mixer.Sound]:
        sounds = {}
        try:
            pygame.mixer.init()
        except pygame.error:
            return sounds
        for name in ["rifle", "explosion", "pickup", "heal", "grenade", "menu_select", "tank_fire", "hit", "capture"]:
            path = ASSET_DIR / "audio" / "sfx" / f"{name}.wav"
            if path.exists():
                sounds[name] = pygame.mixer.Sound(str(path))
        return sounds

    def _load_campaign(self) -> CampaignState:
        if not SAVE_PATH.exists():
            return CampaignState(credits=99999)
        try:
            state = CampaignState.from_dict(json.loads(SAVE_PATH.read_text(encoding="utf-8")))
            state.credits = max(state.credits, 99999)
            return state
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return CampaignState(credits=99999)

    def save_campaign(self) -> None:
        try:
            SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            SAVE_PATH.write_text(json.dumps(self.campaign.to_dict(), indent=2), encoding="utf-8")
        except OSError:
            self.add_radio("SAVE FAILED", (255, 118, 100), 4.0)

    def _play_sound(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound:
            sound.play()

    def _start_music(self) -> None:
        map_id = self.current_map_id
        music_files = {
            "jungle_outpost": "jungle_outpost.wav",
            "trench_line": "trench_line.wav",
            "river_bridge": "river_bridge.wav",
            "armored_front": "armored_front.wav",
        }
        filename = music_files.get(map_id, "battlefield_loop.wav")
        music_path = ASSET_DIR / "audio" / "music" / filename
        if not music_path.exists():
            music_path = ASSET_DIR / "audio" / "music" / "battlefield_loop.wav"

        if not pygame.mixer.get_init() or not music_path.exists():
            return

        # Check if the requested music is already loaded
        current_music = getattr(self, "_current_music_path", None)
        if current_music == music_path:
            return

        try:
            pygame.mixer.music.load(str(music_path))
            pygame.mixer.music.set_volume(0.28)
            pygame.mixer.music.play(-1)
            self._current_music_path = music_path
        except pygame.error:
            pass

    def _spawn_items(self) -> list[Item]:
        items = []
        for kind, points in self.tilemap.item_spawns.items():
            for point in points:
                if self.tilemap.passable_tile(point):
                    items.append(Item(self.tilemap.tile_center(point), kind, amount=1))
        return items

    def _spawn_player_vehicles(self) -> list[TankVehicle]:
        if self.campaign.purchases.get("tank", 0) <= 0:
            return []
        depot_tiles = [
            (x, y)
            for y, row in enumerate(self.tilemap.rows)
            for x, tile in enumerate(row)
            if tile == "D"
        ]
        spawn_tile = depot_tiles[0] if depot_tiles else self.tilemap.spawns["player"]
        vehicle = TankVehicle(self.tilemap.spawn_position(spawn_tile), "sherman", faction="ally")
        vehicle.rect.center = self.tilemap.tile_center(spawn_tile)
        return [vehicle]

    @staticmethod
    def _enemy_tank_kind(index: int) -> str:
        return ("light_tank", "sherman", "heavy_tank")[index % 3]

    @property
    def active_actor(self):
        return self.player.vehicle if getattr(self.player, "vehicle", None) else self.player

    def _move_rect(self, rect: pygame.Rect, delta: pygame.Vector2) -> pygame.Rect:
        moved = rect.copy()
        moved.x += int(delta.x)
        if self.tilemap.blocked(moved):
            moved.x = rect.x
        moved.y += int(delta.y)
        if self.tilemap.blocked(moved):
            moved.y = rect.y
        return moved

    def _move_vehicle(self, vehicle: TankVehicle, delta: pygame.Vector2) -> None:
        total = pygame.Vector2(delta) + vehicle.move_remainder
        step = pygame.Vector2(int(total.x), int(total.y))
        vehicle.move_remainder = total - step
        if not step.length_squared():
            return
        before = vehicle.rect.topleft
        vehicle.rect = self._move_rect(vehicle.rect, step)
        vehicle.moving = vehicle.rect.topleft != before
        if vehicle.rect.topleft == before:
            vehicle.move_remainder.update(0, 0)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN | pygame.SCALED if self.fullscreen else pygame.SCALED
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            if self.state == "play" and not self.result:
                self.update(dt)
            self.draw()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                if self.state == "title" and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if self.state == "menu" and event.key == pygame.K_ESCAPE:
                    self.state = "title"
                    self._play_sound("menu_select")
                if self.state == "title" and event.key in (pygame.K_DOWN, pygame.K_s):
                    self.title_selection = (self.title_selection + 1) % len(self._title_actions())
                    self._play_sound("menu_select")
                elif self.state == "title" and event.key in (pygame.K_UP, pygame.K_w):
                    self.title_selection = (self.title_selection - 1) % len(self._title_actions())
                    self._play_sound("menu_select")
                elif self.state == "title" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.run_title_action(self._title_actions()[self.title_selection][0])
                elif self.state == "play" and event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif self.state == "menu" and event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_map_index = (self.selected_map_index + 1) % len(self.map_ids)
                    self._play_sound("menu_select")
                elif self.state == "menu" and event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_map_index = (self.selected_map_index - 1) % len(self.map_ids)
                    self._play_sound("menu_select")
                elif self.state == "menu" and event.key == pygame.K_TAB:
                    self.menu_tab = {"operations": "story", "story": "shop", "shop": "operations"}[self.menu_tab]
                    self._play_sound("menu_select")
                elif self.state == "menu" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_selected_map()
                elif self.state == "play" and event.key == pygame.K_r and self.result:
                    self.reset()
                elif self.state == "play" and self.result and event.key == pygame.K_RETURN:
                    self.state = "menu"
                    self.menu_tab = "operations"
                elif self.state == "play" and self.result and event.key == pygame.K_ESCAPE:
                    self.state = "title"
                elif self.state == "play" and event.key == pygame.K_h:
                    if self.inventory.use_medkit(self.player):
                        self._play_sound("heal")
                elif self.state == "play" and event.key == pygame.K_g:
                    self.throw_grenade(self.camera.world_mouse(pygame.mouse.get_pos()))
                elif self.state == "play" and event.key == pygame.K_e:
                    self.interact()
                elif self.state == "play" and event.key == pygame.K_q:
                    self.swing_gun_bash(self.camera.world_mouse(pygame.mouse.get_pos()))
                elif self.state == "play" and event.key == pygame.K_1:
                    self.weapon_mode = self.equipped_primary
                elif self.state == "play" and event.key == pygame.K_2:
                    self.weapon_mode = self.equipped_sidearm
                elif self.state == "play" and event.key == pygame.K_3:
                    self.swing_gun_bash(self.camera.world_mouse(pygame.mouse.get_pos()))
                elif self.state == "play" and event.key == pygame.K_m:
                    self.call_mortar(self.camera.world_mouse(pygame.mouse.get_pos()))
            if self.state == "title" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_title_click(event.pos)
            if self.state == "menu" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_menu_click(event.pos)
            if self.state == "play" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.result:
                actor = self.active_actor
                if actor is self.player and self.inventory.ammo <= 0:
                    continue
                bullet = actor.shoot(self.camera.world_mouse(event.pos))
                if bullet:
                    if actor is self.player:
                        definition = self.active_weapon()
                        spread = random.uniform(-definition.spread_degrees, definition.spread_degrees)
                        bullet.direction = bullet.direction.rotate(spread)
                        bullet.damage = definition.damage + self.weapon_damage_bonus()
                        bullet.speed = definition.bullet_speed
                        bullet.armor_piercing = definition.armor_piercing
                        bullet.life = max(0.35, definition.range_px / max(1, definition.bullet_speed))
                        bullet.weapon = "rifle"
                        actor.reload = definition.cooldown * self.weapon_cooldown_scale()
                        if definition.recoil_shake:
                            self.camera.shake(definition.recoil_shake, 0.045)
                    self.bullets.append(bullet)
                    if actor is self.player:
                        self.inventory.ammo = max(0, self.inventory.ammo - 1)
                    weapon = getattr(bullet, "weapon", "rifle")
                    self.effects.muzzle_flash(actor.rect.center, bullet.direction, "tank" if weapon == "tank" else "rifle")
                    self._play_sound("tank_fire" if weapon == "tank" else "rifle")
            if self.state == "play" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and not self.result:
                self.throw_grenade(self.camera.world_mouse(event.pos))
            if self.state == "play" and self.result and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_result_click(event.pos)

    def interact(self) -> None:
        if self.try_open_safe_door():
            return
        self.toggle_vehicle()

    def try_open_safe_door(self) -> bool:
        if self.tilemap.doors_open:
            return False
        actor = self.active_actor
        for rect in self.tilemap.door_rects:
            if pygame.Vector2(rect.center).distance_to(actor.rect.center) <= 120:
                self.tilemap.open_doors()
                self.mission_started = True
                self.mission_grace = 2.25
                self.passable_grid = grid_from_tilemap(self.tilemap)
                self.reachable_tiles = dfs_reachable(self.tilemap.world_to_tile(actor.rect.center), self.passable_grid)
                self.ai_timer = 0.0
                self._play_sound("menu_select")
                self.add_radio("SAFE GATE OPEN - CONTACT STARTED", (238, 203, 116), 4.5)
                return True
        return False

    def toggle_vehicle(self) -> None:
        if getattr(self.player, "vehicle", None):
            vehicle = self.player.vehicle
            exit_rect = self.player.rect.copy()
            for pos in vehicle.exit_candidates():
                exit_rect.center = pos
                if not self.tilemap.blocked(exit_rect):
                    vehicle.exit(override_pos=pos)
                    return
            # Fallback to default if everything is blocked
            vehicle.exit()
            return

        for vehicle in self.vehicles:
            if not vehicle.alive:
                continue
            if pygame.Vector2(vehicle.rect.center).distance_to(self.player.rect.center) <= 78:
                if vehicle.enter(self.player):
                    self.player.rect.center = vehicle.rect.center
                    self._play_sound("menu_select")
                return

    def throw_grenade(self, target) -> None:
        if not self.inventory.use_grenade():
            return
        start = pygame.Vector2(self.active_actor.rect.center)
        max_range = max(560, min(980, min(self.tilemap.width, self.tilemap.height) * 0.52))
        self.grenades.append(GrenadeProjectile(start, target, max_range))
        self._play_sound("grenade")

    def swing_gun_bash(self, target) -> None:
        if self.player.reload > 0.12:
            return
        direction = pygame.Vector2(target) - pygame.Vector2(self.player.rect.center)
        if direction.length_squared():
            self.player.angle = math.degrees(math.atan2(direction.y, direction.x))
            swing_pos = pygame.Vector2(self.player.rect.center) + direction.normalize() * 34
        else:
            swing_pos = pygame.Vector2(self.player.rect.center)
        definition = WEAPONS["gun_bash"]
        self.player.reload = definition.cooldown
        self.player.melee_flash = 0.18
        self.melee_swings.append((swing_pos, self.player.angle, 0.18))
        origin = pygame.Vector2(self.player.rect.center)
        hit_any = False
        for enemy in list(self.enemies):
            if pygame.Vector2(enemy.rect.center).distance_to(origin) <= definition.range_px:
                was_alive = enemy.alive
                actual = enemy.damage(definition.damage, 8)
                self.add_floater(f"-{actual}", enemy.rect.center, (255, 214, 118))
                self.effects.bullet_hit(enemy.rect.center, "rifle")
                hit_any = True
                if was_alive and not enemy.alive:
                    self.register_kill("inf")
                    self.corpses.append((enemy._current_sprite(), enemy.rect.copy(), 3.0))
        for vehicle in self.enemy_vehicles:
            if pygame.Vector2(vehicle.rect.center).distance_to(origin) <= definition.range_px + 8:
                actual = vehicle.damage(12, 2)
                self.add_floater(f"-{actual}", vehicle.rect.center, (255, 166, 104))
                self.effects.bullet_hit(vehicle.rect.center, "rifle")
                hit_any = True
        if hit_any:
            self.camera.shake(0.35, 0.07)

    def add_floater(self, text: str, pos, color: tuple[int, int, int] = (248, 232, 177), life: float = 0.85) -> None:
        self.floaters.append((text, pygame.Vector2(pos), color, life))

    def add_radio(self, text: str, color: tuple[int, int, int] = (238, 232, 207), life: float = 4.0) -> None:
        self.radio_log.insert(0, (text, color, life))
        self.radio_log = self.radio_log[:5]

    def register_kill(self, kind: str) -> None:
        if kind in self.stats:
            self.stats[kind] += 1

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, int(seconds))
        return f"{total // 60:02d}:{total % 60:02d}"

    def detonate_explosion(
        self,
        target,
        *,
        damage: int,
        radius: int,
        armor_piercing: int,
        friendly_scale: float,
        damage_enemies: bool = True,
        damage_allies: bool = True,
    ) -> None:
        target = pygame.Vector2(target)
        self.effects.bullet_hit(target, "grenade")
        self.camera.shake(1.6, 0.2)
        if damage_allies:
            self.apply_blast_to_player(target, radius, damage, armor_piercing, friendly_scale)
            for vehicle in self.vehicles:
                if pygame.Vector2(vehicle.rect.center).distance_to(target) <= radius + 20:
                    vehicle.damage(damage, armor_piercing)
                    if not vehicle.alive:
                        self.effects.tank_explosion(vehicle.rect.center)
                        self._play_sound("explosion")
        if damage_enemies:
            for enemy in list(self.enemies):
                distance = pygame.Vector2(enemy.rect.center).distance_to(target)
                if distance <= radius:
                    was_alive = enemy.alive
                    actual = enemy.damage(damage, armor_piercing)
                    self.add_floater(f"-{actual}", enemy.rect.center, (255, 214, 118))
                    if was_alive and not enemy.alive:
                        self.register_kill("inf")
                        self.corpses.append((enemy._current_sprite(), enemy.rect.copy(), 3.0))
                        self.add_radio("INFANTRY DOWN", (255, 214, 118))
            for vehicle in self.enemy_vehicles:
                if pygame.Vector2(vehicle.rect.center).distance_to(target) <= radius + 20:
                    was_alive = vehicle.alive
                    actual = vehicle.damage(damage, armor_piercing)
                    self.add_floater(f"-{actual}", vehicle.rect.center, (255, 166, 104))
                    if was_alive and not vehicle.alive:
                        self.register_kill("armor")
                        self.effects.tank_explosion(vehicle.rect.center)
                        self._play_sound("explosion")
                        self.add_radio("ENEMY ARMOR DESTROYED", (255, 166, 104), 4.5)
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]

    def apply_blast_to_player(self, target: pygame.Vector2, radius: int, damage: int, armor_piercing: int, friendly_scale: float = 0.45) -> None:
        actor = self.active_actor
        distance = pygame.Vector2(actor.rect.center).distance_to(target)
        if distance > radius:
            return
        falloff = max(0.25, 1.0 - distance / max(1, radius))
        actor.damage(int(damage * friendly_scale * falloff), armor_piercing)
        self.add_floater("HIT", actor.rect.center, (255, 118, 100))
        self.camera.shake(0.9, 0.12)

    def call_mortar(self, target) -> None:
        mortar = WEAPONS["mortar"]
        if self.campaign.purchases.get("mortar", 0) <= 0:
            return
        if self.mortar_cooldown > 0 or self.inventory.grenades <= 0:
            return
        if pygame.Vector2(target).distance_to(self.active_actor.rect.center) > mortar.range_px:
            return
        self.inventory.grenades -= 1
        self.mortar_cooldown = mortar.cooldown
        self.mortar_shells.append(MortarShell(target, weapon_id="mortar"))
        self._play_sound("grenade")

    def detonate_grenade(self, target) -> None:
        grenade = WEAPONS["grenade"]
        self.detonate_explosion(target, damage=grenade.damage, radius=92, armor_piercing=grenade.armor_piercing, friendly_scale=0.45)

    def _title_actions(self) -> list[tuple[str, str, str]]:
        return [
            ("online", "BẮT ĐẦU ONLINE", "Để sẵn khung cho co-op vượt ải sau này"),
            ("offline", "BẮT ĐẦU OFFLINE", "Vào phòng tác chiến và chọn map"),
            ("pvp", "CHẾ ĐỘ PVP", "Để sẵn khung đấu người chơi sau này"),
            ("maps", "DANH SÁCH MÀN CHƠI", "Xem toàn bộ nhiệm vụ hiện có"),
            ("shop", "SHOP VŨ KHÍ", "Mua súng, vật phẩm, pháo cối và xe tăng"),
            ("quit", "THOÁT", "Rời game"),
        ]

    def run_title_action(self, action: str) -> None:
        self.title_notice = ""
        if action in {"offline", "maps"}:
            self.menu_tab = "operations"
            self.state = "menu"
        elif action == "shop":
            self.menu_tab = "shop"
            self.state = "menu"
        elif action in {"online", "pvp"}:
            self.title_notice = "Chế độ online đã được giữ chỗ trong kiến trúc, sẽ nối mạng ở giai đoạn sau."
            self._play_sound("menu_select")
        elif action == "quit":
            pygame.quit()
            sys.exit()

    def handle_title_click(self, pos: tuple[int, int]) -> None:
        for index, (rect, action) in enumerate(self.title_buttons):
            if rect.collidepoint(pos):
                self.title_selection = index
                self.run_title_action(action)
                return

    def start_selected_map(self) -> None:
        self.weapon_mode = self.equipped_primary
        self.reset(self.current_map_id)
        self.state = "play"

    def active_weapon(self):
        return WEAPONS.get(self.weapon_mode, WEAPONS["rifle"])

    def weapon_damage_bonus(self) -> int:
        return self.campaign.purchases.get("weapon_training", 0) * 4

    def weapon_cooldown_scale(self) -> float:
        return max(0.62, 1.0 - self.campaign.purchases.get("reload_drill", 0) * 0.07)

    def handle_menu_click(self, pos: tuple[int, int]) -> None:
        for rect, action in self.menu_buttons:
            if rect.collidepoint(pos):
                if action == "play":
                    self.start_selected_map()
                elif action.startswith("map:"):
                    self.selected_map_index = self.map_ids.index(action.split(":", 1)[1])
                    self._play_sound("menu_select")
                elif action.startswith("tab:"):
                    self.menu_tab = action.split(":", 1)[1]
                    self._play_sound("menu_select")
                elif action.startswith("buy:"):
                    self.buy_shop_item(action.split(":", 1)[1])
                elif action.startswith("equip:"):
                    self.equip_weapon(action.split(":", 1)[1])
                elif action.startswith("shop_page:"):
                    self.shop_page = max(0, int(action.split(":", 1)[1]))
                    self._play_sound("menu_select")
                elif action.startswith("shop_filter:"):
                    self.shop_filter = action.split(":", 1)[1]
                    self.shop_page = 0
                    self._play_sound("menu_select")
                elif action == "title":
                    self.state = "title"

    def handle_result_click(self, pos: tuple[int, int]) -> None:
        for rect, action in self.result_buttons:
            if not rect.collidepoint(pos):
                continue
            self._play_sound("menu_select")
            if action == "retry":
                self.reset()
            elif action == "next_map":
                current_idx = self.map_ids.index(self.current_map_id)
                next_idx = current_idx + 1
                if next_idx < len(self.map_ids):
                    self.reset(self.map_ids[next_idx])
            elif action == "maps":
                self.state = "menu"
                self.menu_tab = "operations"
            elif action == "title":
                self.state = "title"
            elif action == "quit":
                pygame.quit()
                sys.exit()
            return

    def buy_shop_item(self, item_id: str) -> None:
        if not self.campaign.buy(item_id):
            return
        item = SHOP_ITEMS[item_id]
        if item.kind == "weapon":
            self.equip_weapon(item_id)
        if item_id == "medkit":
            self.inventory.medkits += 1
        elif item_id == "grenade":
            self.inventory.grenades += 1
        elif item_id == "ammo":
            self.inventory.ammo += 45
        elif item_id == "armor":
            self.player.max_hp += 20
            self.player.hp = self.player.max_hp
            self.player.armor += 4
        elif item_id == "tank" and self.state == "play":
            self.vehicles = self._spawn_player_vehicles()
        self.save_campaign()
        self._play_sound("pickup")

    def equip_weapon(self, item_id: str) -> None:
        weapon = WEAPONS.get(item_id)
        if weapon is None:
            return
        if item_id != "rifle" and self.campaign.purchases.get(item_id, 0) <= 0:
            return
        if weapon.slot == "primary":
            self.equipped_primary = item_id
            self.weapon_mode = item_id
        elif weapon.slot in {"secondary", "sidearm"}:
            self.equipped_sidearm = item_id
            self.weapon_mode = item_id
        elif weapon.slot == "melee":
            self.weapon_mode = item_id
        if hasattr(self, "player"):
            self.player.weapon_pose = weapon.animation_key
        self._play_sound("menu_select")

    def update(self, dt: float) -> None:
        self.mission_elapsed += dt
        keys = pygame.key.get_pressed()
        mouse_world = self.camera.world_mouse(pygame.mouse.get_pos())
        self.player.weapon_pose = self.active_weapon().animation_key
        if getattr(self.player, "vehicle", None):
            self.update_player_vehicle(dt, keys, mouse_world)
            self.player.rect.center = self.player.vehicle.rect.center
        else:
            self.player.update_player(dt, keys, mouse_world, self.tilemap)
        self.camera.follow(self.active_actor.rect, self.screen.get_size(), dt)
        self.mission_grace = max(0.0, self.mission_grace - dt)
        self.mortar_cooldown = max(0.0, self.mortar_cooldown - dt)
        self.melee_swings = [(pos, angle, life - dt) for pos, angle, life in self.melee_swings if life > dt]
        self.radio_log = [(text, color, life - dt) for text, color, life in self.radio_log if life > dt]

        if self.mission_started:
            self.ai_timer -= dt
            if self.ai_timer <= 0:
                self.ai_timer = 0.25
                target_tile = self.tilemap.world_to_tile(self.active_actor.rect.center)
                self.enemy_paths = {}
                for enemy in [*self.enemies, *self.enemy_vehicles]:
                    enemy_tile = self.tilemap.world_to_tile(enemy.rect.center)
                    path = astar(enemy_tile, target_tile, self.passable_grid)
                    if not path:
                        nearby_goal = bfs_nearest(enemy_tile, [target_tile], self.passable_grid)
                        path = astar(enemy_tile, nearby_goal, self.passable_grid) if nearby_goal else []
                    self.enemy_paths[id(enemy)] = path

            for enemy in self.enemies:
                if self.mission_grace > 0:
                    enemy.reload = max(enemy.reload, self.mission_grace)
                self.bullets.extend(enemy.update_enemy(dt, self.active_actor, self.tilemap, self.enemy_paths.get(id(enemy))))
            self.update_enemy_vehicles(dt)
            self.update_enemy_aircraft(dt)
        for vehicle in [*self.vehicles, *self.enemy_vehicles]:
            vehicle.update(dt)
            if vehicle.moving and random.random() < 12 * dt:
                back_angle = (vehicle.angle + 180) % 360
                back_dir = pygame.Vector2(math.cos(math.radians(back_angle)), math.sin(math.radians(back_angle)))
                smoke_pos = pygame.Vector2(vehicle.rect.center) + back_dir * (vehicle.stats.size[0] * 0.4)
                self.particles.smoke(smoke_pos, 1)

        self.pickup_items()
        self.update_grenades(dt)
        self.update_support_visuals(dt)

        alive_bullets = []
        for bullet in self.bullets:
            if not bullet.update(dt):
                continue
            if bullet.friendly:
                aircraft_hit = next((plane for plane in self.enemy_aircraft if plane.alive and plane.rect.colliderect(bullet.rect)), None)
                if aircraft_hit:
                    was_alive = aircraft_hit.alive
                    actual = aircraft_hit.damage(bullet.damage, bullet.armor_piercing)
                    self.add_floater(f"-{actual}", aircraft_hit.rect.center, (255, 226, 92))
                    self.effects.bullet_hit(bullet.pos, "rifle")
                    self._play_sound("hit")
                    self.camera.shake(0.3, 0.06)
                    if was_alive and not aircraft_hit.alive:
                        self.register_kill("air")
                        self.effects.bomber_strike_effect(aircraft_hit.rect.center, (0, 1), 0.85)
                        self._play_sound("explosion")
                        self.add_radio("ENEMY AIRCRAFT SHOT DOWN", (160, 190, 222), 4.5)
                    continue
            if self.tilemap.bullet_blocked(bullet.rect):
                self.particles.sparks(bullet.pos, 6)
                continue
            if bullet.friendly:
                hit = next((enemy for enemy in self.enemies if enemy.alive and enemy.rect.colliderect(bullet.rect)), None)
                if hit:
                    was_alive = hit.alive
                    actual = hit.damage(bullet.damage, bullet.armor_piercing)
                    self.add_floater(f"-{actual}", hit.rect.center, (255, 214, 118))
                    self.effects.bullet_hit(bullet.pos, bullet.weapon)
                    self._play_sound("hit")
                    if was_alive and not hit.alive:
                        self.register_kill("inf")
                        self.corpses.append((hit._current_sprite(), hit.rect.copy(), 3.0))
                        self.effects.soldier_death_smoke(hit.rect.center, bullet.weapon)
                        self.camera.shake(0.45, 0.08)
                        self.add_radio("INFANTRY DOWN", (255, 214, 118))
                    continue
                vehicle_hit = next((vehicle for vehicle in self.enemy_vehicles if vehicle.alive and vehicle.rect.colliderect(bullet.rect)), None)
                if vehicle_hit:
                    was_alive = vehicle_hit.alive
                    actual = vehicle_hit.damage(bullet.damage, bullet.armor_piercing)
                    self.add_floater(f"-{actual}", vehicle_hit.rect.center, (255, 166, 104))
                    self.effects.bullet_hit(bullet.pos, bullet.weapon)
                    self._play_sound("hit")
                    if was_alive and not vehicle_hit.alive:
                        self.register_kill("armor")
                        self.effects.tank_explosion(vehicle_hit.rect.center)
                        self.camera.shake(1.4, 0.22)
                        self._play_sound("explosion")
                        self.add_radio("ENEMY ARMOR DESTROYED", (255, 166, 104), 4.5)
                    continue
            else:
                active = self.active_actor
                friendly_targets = [active]
                friendly_targets.extend(vehicle for vehicle in self.vehicles if vehicle is not active)
                if active is not self.player:
                    friendly_targets.append(self.player)
                hit_target = next((target for target in friendly_targets if target.alive and target.rect.colliderect(bullet.rect)), None)
                if hit_target:
                    actual = hit_target.damage(bullet.damage, bullet.armor_piercing)
                    self.add_floater(f"-{actual}", hit_target.rect.center, (255, 118, 100))
                    self.effects.bullet_hit(bullet.pos, bullet.weapon)
                    self._play_sound("hit")
                    self.camera.shake(0.8, 0.12)
                    continue
            alive_bullets.append(bullet)
        self.bullets = alive_bullets
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]
        self.enemy_vehicles = [vehicle for vehicle in self.enemy_vehicles if vehicle.alive]
        self.enemy_aircraft = [plane for plane in self.enemy_aircraft if plane.alive]
        self.vehicles = [vehicle for vehicle in self.vehicles if vehicle.alive]
        self.corpses = [(sprite, rect, life - dt) for sprite, rect, life in self.corpses if life > dt]
        self.floaters = [(text, pos + pygame.Vector2(0, -28 * dt), color, life - dt) for text, pos, color, life in self.floaters if life > dt]
        self.particles.update(dt)

        if (
            self.mission_started
            and self.tilemap.capture_rect.colliderect(self.active_actor.rect)
            and not self.enemies
            and not self.enemy_vehicles
            and not self.enemy_aircraft
        ):
            self.capture += dt
        else:
            self.capture = max(0.0, self.capture - dt * 0.6)

        if self.player.hp <= 0 and self.result is None:
            self.result = "MISSION FAILED"
            self.add_radio("MISSION FAILED", (255, 118, 100), 8.0)
        elif self.capture >= CAPTURE_SECONDS and self.result is None:
            self.result = "VICTORY"
            self.add_radio("SECTOR SECURED", (101, 174, 109), 8.0)
            chapter = CHAPTERS_BY_MAP.get(self.tilemap.map_id)
            if chapter and not self.result_awarded:
                self.campaign.credits += chapter.reward
                unlocked = self.campaign.unlock_next_after(self.tilemap.map_id)
                if unlocked:
                    self.add_radio(f"UNLOCKED: {MAPS[unlocked]['title']}", (238, 203, 116), 6.0)
                self.result_reward = chapter.reward
                self.result_awarded = True
                self.save_campaign()
                self._play_sound("capture")

    def update_grenades(self, dt: float) -> None:
        live_grenades = []
        for grenade in self.grenades:
            if grenade.update(dt):
                live_grenades.append(grenade)
            else:
                self.detonate_grenade(grenade.target)
        self.grenades = live_grenades

    def update_support_visuals(self, dt: float) -> None:
        live_shells = []
        for shell in self.mortar_shells:
            if shell.update(dt):
                live_shells.append(shell)
            else:
                if shell.hostile:
                    self.enemy_air_bomb_detonate(shell.target)
                elif shell.weapon_id == "mortar":
                    mortar = WEAPONS["mortar"]
                    self.detonate_explosion(
                        shell.target,
                        damage=mortar.damage,
                        radius=118,
                        armor_piercing=mortar.armor_piercing,
                        friendly_scale=0.35,
                    )
                else:
                    self.detonate_grenade(shell.target)
        self.mortar_shells = live_shells

    def update_player_vehicle(self, dt: float, keys, mouse_world) -> None:
        vehicle = self.player.vehicle
        vehicle.moving = False
        turn = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
        throttle = int(keys[pygame.K_w]) - int(keys[pygame.K_s])
        aim = pygame.Vector2(mouse_world) - pygame.Vector2(vehicle.rect.center)
        if aim.length_squared():
            vehicle.rotate_turret_toward(math.degrees(math.atan2(aim.y, aim.x)), 145 * dt)
        if turn:
            vehicle.angle = (vehicle.angle + turn * 95 * dt) % 360
        if throttle:
            facing = pygame.Vector2(math.cos(math.radians(vehicle.angle)), math.sin(math.radians(vehicle.angle)))
            self._move_vehicle(vehicle, facing * vehicle.speed * throttle * dt)

    def update_enemy_vehicles(self, dt: float) -> None:
        target = self.active_actor
        for vehicle in self.enemy_vehicles:
            vehicle.moving = False
            to_target = pygame.Vector2(target.rect.center) - pygame.Vector2(vehicle.rect.center)
            distance = to_target.length()
            path = self.enemy_paths.get(id(vehicle))
            step = pygame.Vector2()
            has_los = self.tilemap.has_line_of_sight(vehicle.rect.center, target.rect.center)
            preferred_range = UNIT_STATS[vehicle.kind].range * 0.68
            if path and len(path) > 1 and (not has_los or distance > preferred_range):
                lookahead = 2 if len(path) > 2 else 1
                next_tile = self.tilemap.tile_center(path[lookahead])
                step = next_tile - pygame.Vector2(vehicle.rect.center)
            elif distance < 230 and distance:
                step = -to_target
            elif distance > 0:
                side = pygame.Vector2(-to_target.y, to_target.x)
                step = side if (pygame.time.get_ticks() // 900 + id(vehicle)) % 2 else -side
            if step.length_squared():
                vehicle.rotate_toward(math.degrees(math.atan2(step.y, step.x)), 95 * dt)
                facing = pygame.Vector2(math.cos(math.radians(vehicle.angle)), math.sin(math.radians(vehicle.angle)))
                before = vehicle.rect.topleft
                self._move_vehicle(vehicle, facing * vehicle.speed * 0.5 * dt)
                if vehicle.rect.topleft == before:
                    sidestep = pygame.Vector2(-facing.y, facing.x)
                    if (pygame.time.get_ticks() // 700 + id(vehicle)) % 2:
                        sidestep *= -1
                    self._move_vehicle(vehicle, sidestep * vehicle.speed * 0.34 * dt)
                    vehicle.rotate_toward(vehicle.angle + 85, 140 * dt)
            if distance:
                vehicle.rotate_turret_toward(math.degrees(math.atan2(to_target.y, to_target.x)), 75 * dt)
            if (
                distance < UNIT_STATS[vehicle.kind].range
                and vehicle.reload <= 0
                and has_los
            ):
                if self.mission_grace > 0:
                    vehicle.reload = self.mission_grace
                    continue
                bullet = vehicle.shoot(target.rect.center)
                if bullet:
                    self.bullets.append(bullet)
                    self.effects.muzzle_flash(vehicle.rect.center, bullet.direction, "tank")
                    self._play_sound("tank_fire")

    def update_enemy_aircraft(self, dt: float) -> None:
        for aircraft in self.enemy_aircraft:
            target = aircraft.update(dt, self.active_actor.rect.center)
            if target is None or self.mission_grace > 0:
                continue
            self.enemy_airstrike(target, aircraft)

    def enemy_airstrike(self, target, aircraft: EnemyAircraft) -> None:
        target = pygame.Vector2(target)
        self.mortar_shells.append(MortarShell(target, delay=0.95, weapon_id="air_bomb", hostile=True))
        self._play_sound("explosion")

    def enemy_air_bomb_detonate(self, target) -> None:
        target = pygame.Vector2(target)
        direction = pygame.Vector2(self.active_actor.rect.center) - target
        self.effects.bomber_strike_effect(target, direction, 1.05)
        self.camera.shake(1.7, 0.24)
        if pygame.Vector2(self.active_actor.rect.center).distance_to(target) <= 125:
            self.active_actor.damage(UNIT_STATS["bomber"].damage, 28)
        for vehicle in self.vehicles:
            if pygame.Vector2(vehicle.rect.center).distance_to(target) <= 125:
                vehicle.damage(UNIT_STATS["bomber"].damage, 34)

    def pickup_items(self) -> None:
        remaining = []
        for item in self.items:
            if self.player.rect.colliderect(item.rect):
                self.inventory.add_item(item)
                self.stats["supplies"] += 1
                self._play_sound("pickup")
                self.particles.sparks(item.rect.center, 5)
                self.add_floater(f"+{item.kind.upper()}", item.rect.center, (132, 232, 138), 0.9)
                self.add_radio(f"SUPPLY PICKUP: {item.kind.upper()}", (132, 232, 138), 3.2)
            else:
                remaining.append(item)
        self.items = remaining

    def draw(self) -> None:
        if self.state == "title":
            self.draw_title()
            self._draw_cursor()
            pygame.display.flip()
            return

        if self.state == "menu":
            self.draw_menu()
            self._draw_cursor()
            pygame.display.flip()
            return

        self.screen.fill((24, 35, 29))
        self.tilemap.draw(self.screen, self.camera)
        self._draw_capture_zone()
        for item in self.items:
            item.draw(self.screen, self.camera)
        self._draw_nearest_item_hint()
        for bullet in self.bullets:
            bullet.draw(self.screen, self.camera)
        for grenade in self.grenades:
            grenade.draw(self.screen, self.camera)
        for shell in self.mortar_shells:
            shell.draw(self.screen, self.camera)
        self._draw_melee_swings()
        self._draw_corpses()
        actors = [*self.enemies, *self.enemy_vehicles, *self.vehicles, *self.enemy_aircraft]
        if not getattr(self.player, "vehicle", None):
            actors.append(self.player)
        for entity in sorted(actors, key=lambda item: item.rect.centery):
            entity.draw(self.screen, self.camera)
        self.particles.draw(self.screen, self.camera)
        self._draw_floaters()
        self._draw_objective_pointer()
        self._draw_ui()
        self._draw_cursor()
        pygame.display.flip()

    def _current_objective_target(self) -> tuple[str, pygame.Vector2, tuple[int, int, int]] | None:
        actor_pos = pygame.Vector2(self.active_actor.rect.center)
        if not self.mission_started and self.tilemap.door_rects:
            nearest_door = min(self.tilemap.door_rects, key=lambda rect: actor_pos.distance_to(rect.center))
            return "GATE", pygame.Vector2(nearest_door.center), (238, 203, 116)

        hostiles = [*self.enemies, *self.enemy_vehicles, *self.enemy_aircraft]
        if hostiles:
            nearest_hostile = min(hostiles, key=lambda enemy: actor_pos.distance_to(enemy.rect.center))
            label = "AIR" if nearest_hostile in self.enemy_aircraft else "TARGET"
            color = (160, 190, 222) if label == "AIR" else (222, 83, 64)
            return label, pygame.Vector2(nearest_hostile.rect.center), color

        return "CAPTURE", pygame.Vector2(self.tilemap.capture_rect.center), (238, 203, 116)

    def _draw_objective_pointer(self) -> None:
        target = self._current_objective_target()
        if target is None:
            return
        label, world_pos, color = target
        screen_pos = world_pos - self.camera.offset
        margin = 72
        visible_rect = pygame.Rect(margin, margin, SCREEN_WIDTH - margin * 2, SCREEN_HEIGHT - margin * 2)
        pulse = 4 + int(2 * math.sin(pygame.time.get_ticks() / 180))
        if visible_rect.collidepoint(screen_pos):
            pygame.draw.circle(self.screen, (12, 16, 14), screen_pos, 18 + pulse, 3)
            pygame.draw.circle(self.screen, color, screen_pos, 14 + pulse, 2)
            text = self.small_font.render(label, True, (245, 232, 184))
            self.screen.blit(text, text.get_rect(center=(int(screen_pos.x), int(screen_pos.y) - 28)))
            return

        player_screen = pygame.Vector2(self.camera.apply(self.active_actor.rect).center)
        direction = screen_pos - player_screen
        if not direction.length_squared():
            return
        direction = direction.normalize()
        edge = player_screen + direction * 1000
        edge.x = max(margin, min(SCREEN_WIDTH - margin, edge.x))
        edge.y = max(margin, min(SCREEN_HEIGHT - margin, edge.y))
        if abs(direction.x) > abs(direction.y):
            edge.y = player_screen.y + direction.y * abs((edge.x - player_screen.x) / max(0.001, direction.x))
        else:
            edge.x = player_screen.x + direction.x * abs((edge.y - player_screen.y) / max(0.001, direction.y))
        edge.x = max(margin, min(SCREEN_WIDTH - margin, edge.x))
        edge.y = max(margin, min(SCREEN_HEIGHT - margin, edge.y))

        normal = pygame.Vector2(-direction.y, direction.x)
        tip = edge
        tail = edge - direction * 22
        points = [tip, tail + normal * 9, tail - normal * 9]
        pygame.draw.polygon(self.screen, (12, 16, 14), [(int(p.x), int(p.y)) for p in points])
        inner = [tip - direction * 2, tail + normal * 6, tail - normal * 6]
        pygame.draw.polygon(self.screen, color, [(int(p.x), int(p.y)) for p in inner])
        distance = int(world_pos.distance_to(self.active_actor.rect.center) / TILE_SIZE)
        text = self.small_font.render(f"{label} {distance}m", True, (245, 232, 184))
        label_pos = tail - direction * 28
        self.screen.blit(text, text.get_rect(center=(int(label_pos.x), int(label_pos.y))))

    def _draw_nearest_item_hint(self) -> None:
        if not self.items:
            return
        player_tile = self.tilemap.world_to_tile(self.player.rect.center)
        goals = [self.tilemap.world_to_tile(item.rect.center) for item in self.items]
        nearest = bfs_nearest(player_tile, goals, self.passable_grid)
        if nearest is None:
            return
        target = self.tilemap.tile_center(nearest) - self.camera.offset
        player = pygame.Vector2(self.camera.apply(self.player.rect).center)
        if player.distance_to(target) < 60:
            return
        direction = target - player
        if direction.length_squared():
            direction = direction.normalize()
        point = player + direction * 44
        pygame.draw.circle(self.screen, (238, 203, 116), point, 6)
        pygame.draw.line(self.screen, (238, 203, 116), point, point + direction * 18, 3)

    def _draw_corpses(self) -> None:
        for sprite, world_rect, life in self.corpses:
            view = self.camera.apply(world_rect)
            image = sprite.copy()
            image.set_alpha(max(40, min(255, int(255 * life / 3.0))))
            rect = image.get_rect(midbottom=(view.centerx, view.bottom + 10))
            self.screen.blit(image, rect)

    def _draw_floaters(self) -> None:
        for text, pos, color, life in self.floaters:
            alpha = max(0, min(255, int(255 * life / 0.85)))
            label = self.small_font.render(text, True, color)
            label.set_alpha(alpha)
            shadow = self.small_font.render(text, True, (20, 18, 14))
            shadow.set_alpha(alpha)
            center = pos - self.camera.offset
            rect = label.get_rect(center=(int(center.x), int(center.y)))
            self.screen.blit(shadow, rect.move(1, 1))
            self.screen.blit(label, rect)

    def _draw_melee_swings(self) -> None:
        for pos, angle, life in self.melee_swings:
            sprite = self.assets.frame("prop", 90, 44)
            sprite = pygame.transform.rotate(sprite, -angle - 35)
            sprite.set_alpha(max(0, min(255, int(255 * life / 0.18))))
            self.screen.blit(sprite, sprite.get_rect(center=pos - self.camera.offset))

    def draw_title(self) -> None:
        self.screen.fill((14, 18, 16))
        concept = self.assets.screens.get("shop_weapons_concept") or self.assets.screens.get("menu_operations_concept")
        if concept is not None:
            background = pygame.transform.smoothscale(concept, self.screen.get_size())
            background.set_alpha(108)
            self.screen.blit(background, (0, 0))
        else:
            self._draw_map_preview(self.screen.get_rect().inflate(90, 90), MAPS[self.current_map_id], muted=True)

        veil = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        veil.fill((7, 9, 8, 168))
        self.screen.blit(veil, (0, 0))

        scan = pygame.Surface((SCREEN_WIDTH, 2), pygame.SRCALPHA)
        scan.fill((238, 203, 116, 92))
        self.screen.blit(scan, (0, 92 + int(math.sin(pygame.time.get_ticks() / 360) * 18)))

        self.title_buttons = []
        title = self.big_font.render("WARFRONT COMMAND", True, (248, 232, 177))
        subtitle = self.font.render("BỘ CHỈ HUY TIỀN TUYẾN", True, (189, 204, 168))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 92)))
        self.screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 135)))

        left_panel = pygame.Rect(86, 178, 410, 386)
        right_panel = pygame.Rect(546, 178, 468, 386)
        self._draw_3d_panel(left_panel, fill=(15, 21, 18), alpha=218, border=(91, 108, 83), depth=8, radius=7)
        self._draw_3d_panel(right_panel, fill=(15, 21, 18), alpha=212, border=(91, 108, 83), depth=8, radius=7)

        for index, (action, label, desc) in enumerate(self._title_actions()):
            rect = pygame.Rect(left_panel.left + 28, left_panel.top + 28 + index * 56, left_panel.width - 56, 44)
            selected = index == self.title_selection
            hot = rect.collidepoint(pygame.mouse.get_pos())
            fill = (129, 70, 48) if selected else (35, 48, 40)
            edge = (238, 203, 116) if selected else (87, 103, 78)
            self._draw_3d_button(rect, fill, edge, active=selected, hot=hot, depth=5)
            if selected or hot:
                marker = pygame.Rect(rect.left + 8, rect.top + 8, 4, rect.height - 16)
                pygame.draw.rect(self.screen, (255, 223, 128), marker, border_radius=2)
            text = self.font.render(label, True, (255, 241, 196) if selected else (223, 224, 198))
            self.screen.blit(text, (rect.left + 22, rect.top + 9))
            self.title_buttons.append((rect, action))

            if selected:
                desc_text = self.small_font.render(desc, True, (207, 217, 184))
                self.screen.blit(desc_text, (right_panel.left + 28, right_panel.top + 40))

        self._draw_title_loadout(right_panel)
        if self.title_notice:
            notice = self.small_font.render(self.title_notice, True, (238, 203, 116))
            self.screen.blit(notice, notice.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 36)))
        else:
            hint = self.small_font.render("W/S chọn, Enter xác nhận, Esc thoát, F11 đổi toàn màn hình", True, (189, 204, 168))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 36)))

    def _draw_title_loadout(self, panel: pygame.Rect) -> None:
        header = self.font.render("KHO VŨ KHÍ HIỆN TẠI", True, (245, 232, 184))
        self.screen.blit(header, (panel.left + 28, panel.top + 88))
        lines = [
            f"Súng chính: {weapon_name(self.equipped_primary)}",
            f"Súng phụ: {weapon_name(self.equipped_sidearm)}",
            "Cận chiến: đánh bằng báng súng",
            f"Vật phẩm: {self.inventory.medkits} medkit / {self.inventory.grenades} lựu / {self.inventory.ammo} đạn",
            f"Ngân sách: {self.campaign.credits} credits",
        ]
        y = panel.top + 126
        for line in lines:
            text = self.small_font.render(self._fit_text(line, self.small_font, panel.width - 56), True, (212, 219, 190))
            self.screen.blit(text, (panel.left + 28, y))
            y += 24

        map_header = self.font.render("MAP SẴN SÀNG", True, (245, 232, 184))
        self.screen.blit(map_header, (panel.left + 28, panel.top + 262))
        preview_rect = pygame.Rect(panel.left + 210, panel.top + 246, panel.width - 238, 112)
        pygame.draw.rect(self.screen, (20, 25, 22), preview_rect, border_radius=6)
        self._draw_map_preview(preview_rect.inflate(-10, -10), MAPS[self.current_map_id])
        map_name = self.small_font.render(self._fit_text(MAPS[self.current_map_id]["title"], self.small_font, 162), True, (238, 203, 116))
        self.screen.blit(map_name, (panel.left + 28, panel.top + 300))

    def draw_menu(self) -> None:
        self._draw_menu_background()
        self.menu_buttons = []
        title = self.big_font.render("WARFRONT COMMAND", True, (245, 232, 184))
        subtitle = self.font.render("Tactical operations board", True, (189, 204, 168))
        shadow = self.big_font.render("WARFRONT COMMAND", True, (48, 38, 28))
        self.screen.blit(shadow, shadow.get_rect(center=(SCREEN_WIDTH // 2 + 3, 69)))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 66)))
        self.screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 106)))

        panel = pygame.Rect(80, 166, 470, 364)
        preview = pygame.Rect(590, 166, 450, 364)
        self._draw_3d_panel(panel, fill=(14, 20, 17), alpha=218, border=(91, 108, 83), depth=8, radius=7)
        self._draw_3d_panel(preview, fill=(14, 20, 17), alpha=212, border=(91, 108, 83), depth=8, radius=7)
        self._draw_menu_tabs(panel.top - 48)

        if self.menu_tab == "story":
            self._draw_story_panel(panel)
        elif self.menu_tab == "shop":
            self._draw_shop_panel(panel)
        else:
            self._draw_operations_panel(panel)

        if self.menu_tab == "shop":
            self._draw_loadout_preview(preview)
        else:
            current_data = MAPS[self.current_map_id]
            preview_title = self.font.render(current_data["title"], True, (245, 232, 184))
            self.screen.blit(preview_title, (preview.left + 24, preview.top + 18))
            difficulty, diff_color = self._mission_difficulty(current_data)
            chapter = CHAPTERS_BY_MAP.get(self.current_map_id)
            summary = f"{difficulty}  |  {self._mission_stats(current_data)}"
            if chapter:
                summary += f"  |  +{chapter.reward}c"
            summary_text = self.small_font.render(self._fit_text(summary, self.small_font, preview.width - 48), True, diff_color)
            self.screen.blit(summary_text, (preview.left + 24, preview.top + 45))
            self._draw_map_preview(preview.inflate(-32, -92).move(0, 54), current_data)
        help_panel = pygame.Rect(SCREEN_WIDTH // 2 - 355, SCREEN_HEIGHT - 54, 710, 32)
        self._draw_3d_panel(help_panel, fill=(16, 20, 18), alpha=176, border=(78, 92, 73), depth=3, radius=5)
        help_text = self.small_font.render("Tab đổi bảng   W/S chọn map   Enter bắt đầu   Chuột để mua/trang bị", True, (189, 204, 168))
        self.screen.blit(help_text, help_text.get_rect(center=help_panel.center))

    def _draw_menu_tabs(self, y: int) -> None:
        labels = [("operations", "Operations"), ("story", "Story"), ("shop", "Shop")]
        start_x = 80
        for index, (tab, label_text) in enumerate(labels):
            rect = pygame.Rect(start_x + index * 156, y, 142, 34)
            active = self.menu_tab == tab
            self._draw_3d_button(
                rect,
                (91, 108, 83) if active else (33, 44, 37),
                (226, 196, 82) if active else (78, 92, 73),
                active=active,
                hot=rect.collidepoint(pygame.mouse.get_pos()),
                depth=4,
            )
            label = self.small_font.render(label_text, True, (245, 232, 184))
            self.screen.blit(label, label.get_rect(center=rect.center))
            self.menu_buttons.append((rect, f"tab:{tab}"))

    def _draw_operations_panel(self, panel: pygame.Rect) -> None:
        for index, map_id in enumerate(self.map_ids):
            data = MAPS[map_id]
            rect = pygame.Rect(panel.left + 24, panel.top + 16 + index * 61, panel.width - 48, 54)
            selected = index == self.selected_map_index
            color = (84, 102, 71) if selected else (35, 47, 40)
            self._draw_3d_button(
                rect,
                color,
                (226, 196, 82) if selected else (78, 92, 73),
                active=selected,
                hot=rect.collidepoint(pygame.mouse.get_pos()),
                depth=5,
            )
            if selected:
                pygame.draw.rect(self.screen, (238, 203, 116), pygame.Rect(rect.left + 7, rect.top + 7, 5, rect.height - 14), border_radius=2)
            elif rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(self.screen, (189, 204, 168), pygame.Rect(rect.left + 7, rect.top + 9, 3, rect.height - 18), border_radius=2)
            difficulty, diff_color = self._mission_difficulty(data)
            chapter = CHAPTERS_BY_MAP.get(map_id)
            status = self._map_access_label(map_id)
            badge_left = rect.right - 112
            name = self.font.render(self._fit_text(data["title"], self.font, badge_left - rect.left - 62), True, (245, 232, 184))
            stats = self.small_font.render(self._fit_text(self._mission_stats(data), self.small_font, 176), True, (228, 205, 126))
            brief_text = self._fit_text(data["briefing"], self.small_font, rect.width - 66 - stats.get_width() - 18)
            brief = self.small_font.render(brief_text, True, (200, 207, 180))
            icon = pygame.transform.smoothscale(self.assets.icons["objective"], (26, 26))
            self.screen.blit(icon, (rect.left + 16, rect.top + 12))
            self.screen.blit(name, (rect.left + 52, rect.top + 5))
            self.screen.blit(brief, (rect.left + 52, rect.top + 29))
            self.screen.blit(stats, (rect.right - stats.get_width() - 12, rect.top + 29))
            self._draw_badge(pygame.Rect(badge_left, rect.top + 7, 52, 18), status, (69, 117, 86))
            self._draw_badge(pygame.Rect(badge_left + 58, rect.top + 7, 46, 18), difficulty, diff_color)
            self.menu_buttons.append((rect, f"map:{map_id}"))

        play_rect = pygame.Rect(panel.left + 24, panel.bottom - 70, panel.width - 48, 46)
        self._draw_3d_button(
            play_rect,
            (153, 61, 48),
            (238, 203, 116),
            active=True,
            hot=play_rect.collidepoint(pygame.mouse.get_pos()),
            depth=6,
        )
        play = self.font.render("START MISSION", True, (255, 240, 190))
        self.screen.blit(play, play.get_rect(center=play_rect.center))
        self.menu_buttons.append((play_rect, "play"))

    def _draw_loadout_preview(self, panel: pygame.Rect) -> None:
        title = self.font.render("LOADOUT BOARD", True, (245, 232, 184))
        self.screen.blit(title, (panel.left + 24, panel.top + 18))
        budget = self.small_font.render(f"Credits {self.campaign.credits}  |  Ammo {self.inventory.ammo}", True, (238, 203, 116))
        self.screen.blit(budget, (panel.left + 24, panel.top + 47))
        hint = self.small_font.render(
            self._fit_text("Click item to buy/equip. Use filters.", self.small_font, panel.width - 48),
            True,
            (189, 204, 168),
        )
        self.screen.blit(hint, (panel.left + 24, panel.top + 66))

        cards = [
            ("PRIMARY", self.equipped_primary, pygame.Rect(panel.left + 24, panel.top + 96, panel.width - 48, 100)),
            ("SIDEARM", self.equipped_sidearm, pygame.Rect(panel.left + 24, panel.top + 210, panel.width - 48, 100)),
        ]
        for label, weapon_id, rect in cards:
            weapon = WEAPONS.get(weapon_id, WEAPONS["rifle"])
            active = self.weapon_mode == weapon_id
            self._draw_3d_button(rect, (42, 58, 45) if active else (35, 48, 40), (238, 203, 116) if active else (78, 92, 73), active=active, depth=5)
            if active:
                pygame.draw.rect(self.screen, (238, 203, 116), pygame.Rect(rect.left + 8, rect.top + 9, 5, rect.height - 18), border_radius=2)
            icon = self._shop_icon(weapon_id)
            if icon is not None:
                icon = pygame.transform.smoothscale(icon, (50, 36))
                self.screen.blit(icon, icon.get_rect(center=(rect.left + 42, rect.top + 35)))
            self._draw_badge(pygame.Rect(rect.left + 12, rect.bottom - 28, 68, 18), label, (91, 108, 83))
            name = self.font.render(self._fit_text(weapon.name, self.font, rect.width - 112), True, (245, 232, 184))
            self.screen.blit(name, (rect.left + 92, rect.top + 10))
            meta = self.small_font.render(
                f"DMG {weapon.damage}  RNG {weapon.range_px}  AP {weapon.armor_piercing}",
                True,
                (200, 207, 180),
            )
            self.screen.blit(meta, (rect.left + 92, rect.top + 35))
            self._draw_weapon_stat_bars(weapon, pygame.Rect(rect.left + 92, rect.top + 58, rect.width - 110, 38))

        supply_rect = pygame.Rect(panel.left + 24, panel.bottom - 42, panel.width - 48, 26)
        pygame.draw.rect(self.screen, (31, 43, 36), supply_rect, border_radius=5)
        pygame.draw.rect(self.screen, (78, 92, 73), supply_rect, 1, border_radius=5)
        supply = self.small_font.render(
            f"Supplies: Medkit x{self.inventory.medkits}   Grenade x{self.inventory.grenades}   Mortar {'ON' if self.campaign.purchases.get('mortar', 0) else 'OFF'}",
            True,
            (238, 232, 207),
        )
        self.screen.blit(supply, supply.get_rect(center=supply_rect.center))

    def _draw_weapon_stat_bars(self, weapon, rect: pygame.Rect) -> None:
        stats = [
            ("DMG", weapon.damage / 140),
            ("ROF", min(1.0, weapon.shots_per_second / 8)),
            ("RNG", weapon.range_px / 980),
            ("STB", 1.0 - min(1.0, weapon.spread_degrees / 14)),
        ]
        col_w = rect.width // 2
        for index, (label, value) in enumerate(stats):
            col = index % 2
            row = index // 2
            bar = pygame.Rect(rect.left + col * col_w + 36, rect.top + row * 18 + 5, col_w - 44, 7)
            text = self.small_font.render(label, True, (189, 204, 168))
            self.screen.blit(text, (bar.left - 34, bar.top - 5))
            pygame.draw.rect(self.screen, (24, 30, 26), bar, border_radius=3)
            fill = bar.copy()
            fill.width = max(2, int(bar.width * max(0.0, min(1.0, value))))
            pygame.draw.rect(self.screen, (226, 196, 82), fill, border_radius=3)
            pygame.draw.rect(self.screen, (78, 92, 73), bar, 1, border_radius=3)

    def _draw_story_panel(self, panel: pygame.Rect) -> None:
        inner = panel.inflate(-36, -28)
        inner.height -= 62
        shade = pygame.Surface(inner.size, pygame.SRCALPHA)
        shade.fill((8, 12, 10, 94))
        self.screen.blit(shade, inner)
        pygame.draw.rect(self.screen, (35, 48, 40), inner, 1, border_radius=6)
        chapter = CHAPTERS_BY_MAP[self.current_map_id]
        lines = [
            chapter.title.upper(),
            chapter.briefing,
            f"Objective: {chapter.objective}",
            f"Reward: {chapter.reward} credits",
            "",
            "Command says this sector decides the next supply route.",
            "Secure it cleanly, conserve supplies, and return alive.",
        ]
        y = panel.top + 30
        for i, line in enumerate(lines):
            font = self.font if i == 0 else self.small_font
            color = (245, 232, 184) if i == 0 else (200, 207, 180)
            for wrapped in self._wrap_text(line, font, panel.width - 54):
                text = font.render(wrapped, True, color)
                self.screen.blit(text, (panel.left + 28, y))
                y += 30 if font == self.font else 22

    def _draw_shop_panel(self, panel: pygame.Rect) -> None:
        credits = self.font.render(f"Credits: {self.campaign.credits}", True, (238, 203, 116))
        self.screen.blit(credits, (panel.left + 28, panel.top + 24))
        equipped = self.small_font.render(f"Eq: {weapon_name(self.equipped_primary)} / {weapon_name(self.equipped_sidearm)}", True, (189, 204, 168))
        self.screen.blit(equipped, (panel.left + 28, panel.top + 50))
        self._draw_shop_filters(panel)

        items = [(item_id, item) for item_id, item in SHOP_ITEMS.items() if self._shop_filter_match(item_id, item)]
        page_size = 6
        pages = max(1, math.ceil(len(items) / page_size))
        self.shop_page = min(self.shop_page, pages - 1)
        start = self.shop_page * page_size
        visible = items[start : start + page_size]

        for index, (item_id, item) in enumerate(visible):
            col = index % 2
            row = index // 2
            col_w = (panel.width - 58) // 2
            rect = pygame.Rect(panel.left + 22 + col * (col_w + 14), panel.top + 118 + row * 62, col_w, 54)
            can_buy = self.campaign.can_buy(item_id)
            bought_count = self.campaign.purchases.get(item_id, 0)
            owned = bought_count > 0
            maxed = item.max_purchases is not None and bought_count >= item.max_purchases
            equipped_item = item_id in {self.equipped_primary, self.equipped_sidearm, self.weapon_mode}
            border = (238, 203, 116) if equipped_item else ((226, 196, 82) if can_buy else (84, 84, 76))
            self._draw_3d_button(
                rect,
                (54, 74, 54) if equipped_item else ((42, 58, 45) if can_buy or owned else (42, 42, 39)),
                border,
                active=equipped_item,
                hot=rect.collidepoint(pygame.mouse.get_pos()),
                depth=4,
            )
            if equipped_item:
                pygame.draw.rect(self.screen, (238, 203, 116), pygame.Rect(rect.left + 6, rect.top + 8, 4, rect.height - 16), border_radius=2)
            elif rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(self.screen, (189, 204, 168), pygame.Rect(rect.left + 6, rect.top + 10, 3, rect.height - 20), border_radius=2)
            price = "OWNED" if owned and item.max_purchases == 1 else ("MAX" if maxed else f"{item.cost}c")
            icon = self._shop_icon(item_id)
            if icon is not None:
                self.screen.blit(icon, icon.get_rect(center=(rect.left + 27, rect.centery)))
                text_x = rect.left + 50
            else:
                text_x = rect.left + 16
            level = f" Lv {bought_count}/{item.max_purchases}" if item.max_purchases and item.max_purchases > 1 else ""
            name = self.small_font.render(self._fit_text(f"{item.name}{level} - {price}", self.small_font, rect.right - text_x - 8), True, (245, 232, 184))
            desc = self.small_font.render(self._fit_text(self._shop_description(item_id, item.description), self.small_font, rect.right - text_x - 8), True, (200, 207, 180))
            self.screen.blit(name, (text_x, rect.top + 4))
            self.screen.blit(desc, (text_x, rect.top + 28))
            self.menu_buttons.append((rect, f"equip:{item_id}" if owned and item.kind == "weapon" else f"buy:{item_id}"))

        nav_y = panel.bottom - 44
        page_label = self.small_font.render(f"Page {self.shop_page + 1}/{pages}", True, (238, 203, 116))
        self.screen.blit(page_label, page_label.get_rect(center=(panel.centerx, nav_y + 16)))
        if self.shop_page > 0:
            prev_rect = pygame.Rect(panel.left + 24, nav_y, 86, 32)
            self._draw_3d_button(prev_rect, (35, 48, 40), (226, 196, 82), hot=prev_rect.collidepoint(pygame.mouse.get_pos()), depth=4)
            self.screen.blit(self.small_font.render("< Prev", True, (245, 232, 184)), (prev_rect.left + 15, prev_rect.top + 7))
            self.menu_buttons.append((prev_rect, f"shop_page:{self.shop_page - 1}"))
        if self.shop_page < pages - 1:
            next_rect = pygame.Rect(panel.right - 110, nav_y, 86, 32)
            self._draw_3d_button(next_rect, (35, 48, 40), (226, 196, 82), hot=next_rect.collidepoint(pygame.mouse.get_pos()), depth=4)
            self.screen.blit(self.small_font.render("Next >", True, (245, 232, 184)), (next_rect.left + 14, next_rect.top + 7))
            self.menu_buttons.append((next_rect, f"shop_page:{self.shop_page + 1}"))

    def _draw_shop_filters(self, panel: pygame.Rect) -> None:
        filters = [
            ("all", "ALL"),
            ("weapons", "GUNS"),
            ("supplies", "SUPPLY"),
            ("vehicles", "ARMOR"),
        ]
        y = panel.top + 78
        gap = 8
        width = (panel.width - 48 - gap * (len(filters) - 1)) // len(filters)
        for index, (filter_id, label_text) in enumerate(filters):
            rect = pygame.Rect(panel.left + 24 + index * (width + gap), y, width, 28)
            active = self.shop_filter == filter_id
            self._draw_3d_button(
                rect,
                (91, 108, 83) if active else (31, 43, 36),
                (238, 203, 116) if active else (78, 92, 73),
                active=active,
                hot=rect.collidepoint(pygame.mouse.get_pos()),
                depth=3,
            )
            label = self.small_font.render(label_text, True, (245, 232, 184))
            self.screen.blit(label, label.get_rect(center=rect.center))
            self.menu_buttons.append((rect, f"shop_filter:{filter_id}"))

    def _shop_filter_match(self, item_id: str, item) -> bool:
        if self.shop_filter == "all":
            return True
        weapon = WEAPONS.get(item_id)
        if self.shop_filter == "weapons":
            return item.kind == "weapon" or (weapon is not None and weapon.slot in {"primary", "secondary", "sidearm"})
        if self.shop_filter == "supplies":
            return item.kind in {"consumable", "support", "upgrade"} and item_id != "armor"
        if self.shop_filter == "vehicles":
            return item.kind == "vehicle" or item_id == "armor"
        return True

    def _shop_description(self, item_id: str, fallback: str) -> str:
        weapon = WEAPONS.get(item_id)
        if weapon is None or weapon.slot not in {"primary", "secondary", "sidearm", "melee", "support"}:
            return fallback
        if weapon.slot == "support":
            return f"DMG {weapon.damage} / RNG {weapon.range_px} / CD {weapon.cooldown:.1f}s"
        if weapon.slot == "melee":
            return f"DMG {weapon.damage} / RNG {weapon.range_px} / CD {weapon.cooldown:.2f}s"
        return (
            f"DMG {weapon.damage} / RNG {weapon.range_px} / "
            f"ROF {weapon.shots_per_second}/s / SPR {weapon.spread_degrees:g}"
        )

    def _draw_menu_background(self) -> None:
        self.screen.fill((18, 26, 22))
        concept = self.assets.screens.get("menu_operations_concept")
        if concept is not None:
            self.screen.blit(concept, (0, 0))
        else:
            self._draw_map_preview(self.screen.get_rect().inflate(90, 90), MAPS[self.current_map_id], muted=True)
        veil = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        veil.fill((8, 12, 10, 218 if concept is not None else 185))
        self.screen.blit(veil, (0, 0))
        scan_x = int((pygame.time.get_ticks() / 18) % (SCREEN_WIDTH + 220)) - 220
        beam = pygame.Surface((220, SCREEN_HEIGHT), pygame.SRCALPHA)
        for x in range(220):
            alpha = max(0, 42 - abs(x - 110) // 3)
            pygame.draw.line(beam, (118, 148, 98, alpha), (x, 0), (x, SCREEN_HEIGHT))
        self.screen.blit(beam, (scan_x, 0))
        for i in range(18):
            x = (i * 97 + pygame.time.get_ticks() // 65) % SCREEN_WIDTH
            y = (i * 53) % SCREEN_HEIGHT
            pygame.draw.circle(self.screen, (116, 136, 98), (x, y), 1)

    def _map_access_label(self, map_id: str) -> str:
        if map_id in self.campaign.unlocked_maps:
            return "READY"
        if self.campaign.credits >= 99999:
            return "TEST"
        return "LOCK"

    def _mission_difficulty(self, data: dict) -> tuple[str, tuple[int, int, int]]:
        spawns = data["spawns"]
        air = len(spawns.get("aircraft_enemies", [])) + len(spawns.get("air_support", []))
        score = len(spawns["enemies"]) + len(spawns["tanks"]) * 2 + air * 3
        if score <= 5:
            return "EASY", (101, 174, 109)
        if score <= 9:
            return "MID", (226, 196, 82)
        if score <= 13:
            return "HARD", (216, 126, 72)
        return "HELL", (204, 73, 57)

    def _draw_badge(
        self,
        rect: pygame.Rect,
        text: str,
        color: tuple[int, int, int],
        text_color: tuple[int, int, int] = (245, 232, 184),
    ) -> None:
        fill = tuple(max(0, channel - 45) for channel in color)
        shadow = pygame.Surface((rect.width, rect.height + 3), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 72), pygame.Rect(0, 3, rect.width, rect.height), border_radius=4)
        self.screen.blit(shadow, rect)
        pygame.draw.rect(self.screen, fill, rect.move(0, 2), border_radius=4)
        pygame.draw.rect(self.screen, fill, rect, border_radius=4)
        pygame.draw.rect(self.screen, tuple(min(255, channel + 22) for channel in fill), rect.inflate(-4, -rect.height // 2).move(0, 2), border_radius=3)
        pygame.draw.line(self.screen, tuple(min(255, channel + 45) for channel in color), (rect.left + 4, rect.top + 1), (rect.right - 4, rect.top + 1), 1)
        pygame.draw.line(self.screen, tuple(max(0, channel - 50) for channel in fill), (rect.left + 4, rect.bottom - 1), (rect.right - 4, rect.bottom - 1), 1)
        pygame.draw.rect(self.screen, color, rect, 1, border_radius=4)
        label = self.small_font.render(self._fit_text(text, self.small_font, rect.width - 6), True, text_color)
        self.screen.blit(label, label.get_rect(center=rect.center))

    def _mission_stats(self, data: dict) -> str:
        spawns = data["spawns"]
        air = len(spawns.get("aircraft_enemies", [])) + len(spawns.get("air_support", []))
        return f"{len(spawns['enemies'])} INF / {len(spawns['tanks'])} ARM" + (f" / {air} AIR" if air else "")

    @staticmethod
    def _fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
        if font.size(text)[0] <= max_width:
            return text
        ellipsis = "..."
        while text and font.size(text + ellipsis)[0] > max_width:
            text = text[:-1]
        return text.rstrip() + ellipsis

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        if not text:
            return [""]
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _draw_3d_button(
        self,
        rect: pygame.Rect,
        fill: tuple[int, int, int],
        border: tuple[int, int, int],
        *,
        active: bool = False,
        hot: bool = False,
        depth: int = 4,
        radius: int = 6,
    ) -> None:
        lift = 1 if hot else 0
        body = rect.move(0, -lift)
        shadow = pygame.Surface((body.width, body.height + depth), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 92), pygame.Rect(0, depth, body.width, body.height), border_radius=radius)
        self.screen.blit(shadow, body)

        if active or hot:
            pulse = 28 + int(18 * math.sin(pygame.time.get_ticks() / 180))
            glow = pygame.Surface(body.inflate(12, 12).size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*border, pulse if active else 24), glow.get_rect(), border_radius=radius + 4)
            self.screen.blit(glow, body.inflate(12, 12))

        top = tuple(min(255, c + (28 if active or hot else 16)) for c in fill)
        bottom = tuple(max(0, c - 28) for c in fill)
        pygame.draw.rect(self.screen, bottom, body.move(0, depth), border_radius=radius)
        pygame.draw.rect(self.screen, fill, body, border_radius=radius)
        pygame.draw.rect(self.screen, top, body.inflate(-8, -body.height // 2).move(0, 4), border_radius=max(2, radius - 2))
        pygame.draw.line(self.screen, tuple(min(255, c + 55) for c in fill), (body.left + 8, body.top + 3), (body.right - 8, body.top + 3), 1)
        pygame.draw.line(self.screen, tuple(max(0, c - 46) for c in fill), (body.left + 8, body.bottom - 2), (body.right - 8, body.bottom - 2), 2)
        pygame.draw.rect(self.screen, border, body, 2 if active else 1, border_radius=radius)

    def _draw_3d_panel(
        self,
        rect: pygame.Rect,
        *,
        fill: tuple[int, int, int] = (16, 21, 18),
        alpha: int = 178,
        border: tuple[int, int, int] = (78, 92, 73),
        depth: int = 5,
        radius: int = 6,
    ) -> None:
        shadow = pygame.Surface((rect.width + 10, rect.height + depth + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 92), pygame.Rect(5, depth + 5, rect.width, rect.height), border_radius=radius)
        self.screen.blit(shadow, (rect.left - 5, rect.top - 5))
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (*fill, alpha), bg.get_rect(), border_radius=radius)
        self.screen.blit(bg, rect)
        highlight = pygame.Rect(rect.left + 4, rect.top + 3, rect.width - 8, max(5, rect.height // 4))
        hi = pygame.Surface(highlight.size, pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 220, 22), hi.get_rect(), border_radius=max(2, radius - 2))
        self.screen.blit(hi, highlight)
        pygame.draw.line(self.screen, tuple(min(255, c + 35) for c in border), (rect.left + 8, rect.top + 2), (rect.right - 8, rect.top + 2), 1)
        pygame.draw.line(self.screen, tuple(max(0, c - 42) for c in border), (rect.left + 8, rect.bottom - 2), (rect.right - 8, rect.bottom - 2), 2)
        pygame.draw.rect(self.screen, border, rect, 1, border_radius=radius)

    def _panel(self, rect: pygame.Rect) -> None:
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((12, 16, 14, 214))
        self.screen.blit(bg, rect)
        pygame.draw.rect(self.screen, (42, 52, 42), rect.inflate(8, 8), 1, border_radius=10)
        pygame.draw.rect(self.screen, (91, 108, 83), rect, 2, border_radius=8)

    def _draw_map_preview(self, rect: pygame.Rect, data: dict, muted: bool = False) -> None:
        rows = data["rows"]
        cols = len(rows[0])
        tile_w = rect.width / cols
        tile_h = rect.height / len(rows)
        colors = {
            "#": (76, 78, 72),
            "w": (45, 91, 115),
            "r": (96, 86, 72),
            "t": (83, 62, 43),
            "g": (49, 91, 48),
            "C": (188, 67, 54),
            "S": (50, 57, 48),
            "M": (78, 112, 77),
            "A": (128, 104, 58),
            "D": (94, 91, 80),
            ".": (70, 108, 62),
        }
        for y, row in enumerate(rows):
            for x, tile in enumerate(row):
                cell = pygame.Rect(
                    int(rect.left + x * tile_w),
                    int(rect.top + y * tile_h),
                    math.ceil(tile_w),
                    math.ceil(tile_h),
                )
                color = colors.get(tile, colors["."])
                if muted:
                    color = tuple(max(0, c - 20) for c in color)
                pygame.draw.rect(self.screen, color, cell)
                if not muted and tile == "w":
                    pygame.draw.line(self.screen, (113, 163, 178), cell.midleft, cell.midright, 1)
                elif not muted and tile == "C":
                    pygame.draw.rect(self.screen, (238, 203, 116), cell, 1)
        if muted:
            return

        def to_screen(tile: tuple[int, int], clamp: bool = False) -> tuple[int, int]:
            tx, ty = tile
            cx = int(rect.left + (tx + 0.5) * tile_w)
            cy = int(rect.top + (ty + 0.5) * tile_h)
            if clamp:
                cx = max(rect.left + 4, min(rect.right - 4, cx))
                cy = max(rect.top + 4, min(rect.bottom - 4, cy))
            return cx, cy

        for zone in data.get("safe_zones", []):
            zx, zy, zw, zh = zone["rect"]
            zone_rect = pygame.Rect(
                int(rect.left + zx * tile_w),
                int(rect.top + zy * tile_h),
                int(zw * tile_w),
                int(zh * tile_h),
            )
            safe_overlay = pygame.Surface(zone_rect.size, pygame.SRCALPHA)
            safe_overlay.fill((82, 176, 91, 38))
            self.screen.blit(safe_overlay, zone_rect)
            pygame.draw.rect(self.screen, (101, 174, 109), zone_rect, 2)

        for door in data.get("doors", []):
            cx, cy = to_screen(door)
            door_rect = pygame.Rect(0, 0, max(8, int(tile_w * 0.8)), max(8, int(tile_h * 0.8)))
            door_rect.center = (cx, cy)
            pygame.draw.rect(self.screen, (238, 203, 116), door_rect, border_radius=2)
            pygame.draw.rect(self.screen, (33, 25, 18), door_rect, 1, border_radius=2)

        for point in data.get("capture_points", []):
            cx, cy = to_screen(tuple(point["tile"]))
            radius = max(8, int(point.get("radius", 2) * min(tile_w, tile_h)))
            pygame.draw.circle(self.screen, (238, 203, 116), (cx, cy), radius, 2)
            pygame.draw.line(self.screen, (238, 203, 116), (cx - 7, cy), (cx + 7, cy), 2)
            pygame.draw.line(self.screen, (238, 203, 116), (cx, cy - 7), (cx, cy + 7), 2)

        item_colors = {
            "medkit": (102, 190, 117),
            "grenade": (177, 149, 72),
            "ammo": (226, 196, 82),
        }
        for kind, points in data.get("items", {}).items():
            for point in points:
                cx, cy = to_screen(point)
                pygame.draw.circle(self.screen, (12, 16, 14), (cx, cy), 4)
                pygame.draw.circle(self.screen, item_colors.get(kind, (189, 204, 168)), (cx, cy), 3)

        spawns = data["spawns"]
        markers = [(spawns["player"], (83, 176, 91), "P")]
        markers += [(pos, (204, 73, 57), "E") for pos in spawns["enemies"]]
        markers += [(pos, (196, 160, 83), "T") for pos in spawns["tanks"]]
        for (tx, ty), color, label in markers:
            cx, cy = to_screen((tx, ty))
            pygame.draw.circle(self.screen, (12, 16, 14), (cx, cy), 7)
            pygame.draw.circle(self.screen, color, (cx, cy), 5)
            text = self.small_font.render(label, True, (245, 232, 184))
            self.screen.blit(text, text.get_rect(center=(cx, cy - 13)))

        for aircraft in [*spawns.get("aircraft_enemies", []), *spawns.get("air_support", [])]:
            start = to_screen(tuple(aircraft["entry"]), clamp=True)
            end = to_screen(tuple(aircraft["exit"]), clamp=True)
            target = to_screen(tuple(aircraft.get("target", aircraft["exit"])), clamp=True)
            pygame.draw.line(self.screen, (160, 190, 222), start, end, 2)
            pygame.draw.circle(self.screen, (15, 22, 28), target, 7)
            pygame.draw.circle(self.screen, (160, 190, 222), target, 5)
            pygame.draw.polygon(
                self.screen,
                (160, 190, 222),
                [(start[0], start[1] - 6), (start[0] - 5, start[1] + 5), (start[0] + 5, start[1] + 5)],
            )
            air_text = self.small_font.render("AIR", True, (225, 236, 245))
            self.screen.blit(air_text, air_text.get_rect(center=(target[0], target[1] - 15)))

        legend = [("P", (83, 176, 91)), ("E", (204, 73, 57)), ("T", (196, 160, 83)), ("AIR", (160, 190, 222)), ("SUP", (226, 196, 82))]
        legend_rect = pygame.Rect(rect.left + 8, rect.bottom - 28, min(rect.width - 16, 292), 22)
        legend_bg = pygame.Surface(legend_rect.size, pygame.SRCALPHA)
        legend_bg.fill((12, 16, 14, 155))
        self.screen.blit(legend_bg, legend_rect)
        x = legend_rect.left + 8
        for label, color in legend:
            pygame.draw.circle(self.screen, color, (x + 5, legend_rect.centery), 4)
            text = self.small_font.render(label, True, (232, 226, 200))
            self.screen.blit(text, (x + 14, legend_rect.top + 3))
            x += text.get_width() + 32

    def _draw_capture_zone(self) -> None:
        rect = self.camera.apply(self.tilemap.capture_rect)
        pygame.draw.rect(self.screen, (232, 205, 89), rect, 3, border_radius=6)
        fill = rect.copy()
        fill.width = int(rect.width * min(1.0, self.capture / CAPTURE_SECONDS))
        pygame.draw.rect(self.screen, (232, 205, 89), fill.inflate(-8, -8), border_radius=4)

    def _draw_ui(self) -> None:
        if self.result:
            self._draw_result_overlay()
            return

        actor = self.active_actor
        hp_label = "Tank" if actor is not self.player else "HP"
        ammo_label = f"Ammo: {self.inventory.ammo}" if actor is self.player else "Tank cannon"
        mortar = "ready" if self.mortar_cooldown <= 0 else f"{self.mortar_cooldown:.0f}s"
        weapon = self.active_weapon()
        self._draw_compact_hud(
            [
                ("warning", f"{len(self.enemies)} INF / {len(self.enemy_vehicles)} ARM / {len(self.enemy_aircraft)} AIR"),
                ("hp", f"{hp_label} {max(0, actor.hp)}"),
                ("ammo", ammo_label),
                ("objective", f"{weapon.name}  D{weapon.damage}  R{weapon.shots_per_second}/s"),
            ]
        )
        self._draw_mission_tracker()
        self._draw_minimap()
        self._draw_radio_log()
        self._draw_action_bar(mortar)
        vehicle_hint = "E: enter/exit tank   " if self.vehicles else ""
        door_hint = "E: open safe-room gate   " if not self.tilemap.doors_open else ""
        objective = "Open the gate to begin" if not self.mission_started else "Clear hostiles, then hold command"
        hint = f"{door_hint}{vehicle_hint}{objective}".strip()
        if hint:
            self._draw_bottom_hint(hint)

    def _draw_hud_icon(self, icon_name: str, pos: tuple[int, int], text: str) -> None:
        icon = pygame.transform.smoothscale(self.assets.icons[icon_name], (30, 30))
        label = self.font.render(text, True, (238, 232, 207))
        panel = pygame.Rect(pos[0] - 5, pos[1] - 4, label.get_width() + 48, 38)
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        bg.fill((20, 24, 21, 145))
        self.screen.blit(bg, panel)
        self.screen.blit(icon, pos)
        self.screen.blit(label, (pos[0] + 38, pos[1] + 4))

    def _draw_compact_hud(self, rows: list[tuple[str, str]]) -> None:
        panel = pygame.Rect(14, 12, 548, 78)
        self._draw_3d_panel(panel, fill=(15, 20, 17), alpha=188, border=(78, 92, 73), depth=6, radius=6)
        cell_w = (panel.width - 28) // 2
        cell_h = 28
        for index, (icon_name, text) in enumerate(rows):
            col = index % 2
            row = index // 2
            cell = pygame.Rect(panel.left + 10 + col * (cell_w + 8), panel.top + 9 + row * 32, cell_w, cell_h)
            accent = (238, 203, 116) if icon_name in {"warning", "objective"} else (101, 174, 109)
            self._draw_3d_panel(cell, fill=(25, 34, 29), alpha=214, border=(62, 76, 65), depth=2, radius=4)
            pygame.draw.rect(self.screen, accent, pygame.Rect(cell.left + 4, cell.top + 5, 3, cell.height - 10), border_radius=2)
            icon = pygame.transform.smoothscale(self.assets.icons[icon_name], (18, 18))
            label = self.small_font.render(self._fit_text(text, self.small_font, cell.width - 46), True, (238, 232, 207))
            self.screen.blit(icon, (cell.left + 8, cell.top + 5))
            self.screen.blit(label, (cell.left + 34, cell.top + 6))

    def _draw_mission_tracker(self) -> None:
        panel = pygame.Rect(14, 102, 318, 150)
        self._draw_3d_panel(panel, fill=(15, 20, 17), alpha=184, border=(78, 92, 73), depth=6, radius=6)

        title = self.small_font.render("MISSION TRACKER", True, (238, 203, 116))
        self.screen.blit(title, (panel.left + 10, panel.top + 8))
        status = "GATE CLOSED" if not self.mission_started else "ACTIVE"
        status_color = (226, 196, 82) if not self.mission_started else (101, 174, 109)
        self._draw_badge(pygame.Rect(panel.right - 104, panel.top + 7, 90, 18), status, status_color)

        hostiles = len(self.enemies) + len(self.enemy_vehicles) + len(self.enemy_aircraft)
        capture_ready = self.mission_started and hostiles == 0
        rows = [
            ("1", "Open safe-room gate", self.mission_started),
            ("2", f"Eliminate hostiles: {hostiles}", hostiles == 0),
            ("3", "Hold command point", self.capture >= CAPTURE_SECONDS),
        ]
        y = panel.top + 34
        for number, text, done in rows:
            dot = pygame.Rect(panel.left + 10, y + 2, 18, 18)
            fill = (75, 129, 83) if done else ((95, 80, 47) if number == "3" and capture_ready else (37, 48, 41))
            pygame.draw.rect(self.screen, fill, dot, border_radius=4)
            pygame.draw.rect(self.screen, (101, 174, 109) if done else (78, 92, 73), dot, 1, border_radius=4)
            step = self.small_font.render(number, True, (245, 232, 184))
            self.screen.blit(step, step.get_rect(center=dot.center))
            label_color = (226, 235, 205) if done or capture_ready else (185, 194, 171)
            label = self.small_font.render(self._fit_text(text, self.small_font, panel.width - 56), True, label_color)
            self.screen.blit(label, (panel.left + 36, y + 2))
            y += 25

        pct = self.small_font.render(f"CAPTURE {int(min(1.0, self.capture / CAPTURE_SECONDS) * 100)}%", True, (238, 232, 207))
        self.screen.blit(pct, (panel.left + 10, panel.bottom - 36))
        bar = pygame.Rect(panel.left + 10, panel.bottom - 17, panel.width - 20, 10)
        pygame.draw.rect(self.screen, (29, 36, 31), bar, border_radius=4)
        progress = min(1.0, self.capture / CAPTURE_SECONDS)
        fill = bar.copy()
        fill.width = int(bar.width * progress)
        if fill.width > 0:
            pygame.draw.rect(self.screen, (238, 203, 116), fill, border_radius=4)
        pygame.draw.rect(self.screen, (78, 92, 73), bar, 1, border_radius=4)

    def _draw_bottom_hint(self, text: str) -> None:
        label = self.small_font.render(self._fit_text(text, self.small_font, SCREEN_WIDTH - 540), True, (238, 232, 207))
        panel = pygame.Rect(14, SCREEN_HEIGHT - 34, label.get_width() + 24, 26)
        self._draw_3d_panel(panel, fill=(20, 24, 21), alpha=176, border=(78, 92, 73), depth=3, radius=4)
        self.screen.blit(label, (panel.left + 12, panel.top + 5))

    def _draw_radio_log(self) -> None:
        if not self.radio_log:
            return
        panel = pygame.Rect(SCREEN_WIDTH - 298, 148, 282, 28 + 20 * min(5, len(self.radio_log)))
        self._draw_3d_panel(panel, fill=(15, 20, 17), alpha=170, border=(78, 92, 73), depth=5, radius=5)
        title = self.small_font.render("RADIO", True, (238, 203, 116))
        self.screen.blit(title, (panel.left + 10, panel.top + 6))
        y = panel.top + 26
        for text, color, life in self.radio_log[:5]:
            alpha = max(65, min(255, int(255 * min(1.0, life / 1.8))))
            label = self.small_font.render(self._fit_text(text, self.small_font, panel.width - 22), True, color)
            label.set_alpha(alpha)
            self.screen.blit(label, (panel.left + 10, y))
            y += 20

    def _draw_action_bar(self, mortar_status: str) -> None:
        slots = [
            ("1", weapon_name(self.equipped_primary), self._shop_icon(self.equipped_primary), self.weapon_mode == self.equipped_primary, None),
            ("2", weapon_name(self.equipped_sidearm), self._shop_icon(self.equipped_sidearm), self.weapon_mode == self.equipped_sidearm, None),
            ("Q", "Bash", self.assets.frame("prop", 90, 32), False, None),
            ("G", f"Gren x{self.inventory.grenades}", self._shop_icon("grenade"), False, self.inventory.grenades > 0),
            ("H", f"Med x{self.inventory.medkits}", self._shop_icon("medkit"), False, self.inventory.medkits > 0),
            ("M", f"Mortar {mortar_status}", self._shop_icon("mortar"), False, self.campaign.purchases.get("mortar", 0) > 0 and self.inventory.grenades > 0 and self.mortar_cooldown <= 0),
        ]
        slot_w = 148
        panel = pygame.Rect(SCREEN_WIDTH // 2 - (slot_w * len(slots)) // 2, SCREEN_HEIGHT - 88, slot_w * len(slots), 58)
        self._draw_3d_panel(panel, fill=(15, 20, 17), alpha=196, border=(78, 92, 73), depth=6, radius=6)

        for index, (key, label_text, icon, active, ready) in enumerate(slots):
            rect = pygame.Rect(panel.left + index * slot_w + 6, panel.top + 7, slot_w - 12, 44)
            disabled = ready is False
            fill = (82, 102, 76) if active else ((36, 49, 41) if not disabled else (35, 35, 32))
            border = (238, 203, 116) if active or ready is True else ((78, 92, 73) if ready is None else (87, 74, 68))
            self._draw_3d_button(rect, fill, border, active=active, depth=3, radius=5)
            if active:
                pygame.draw.rect(self.screen, (238, 203, 116), pygame.Rect(rect.left + 4, rect.top + 7, 3, rect.height - 14), border_radius=2)

            key_rect = pygame.Rect(rect.left + 9, rect.top + 6, 24, 20)
            pygame.draw.rect(self.screen, (18, 22, 19), key_rect, border_radius=4)
            pygame.draw.rect(self.screen, border, key_rect, 1, border_radius=4)
            key_label = self.small_font.render(key, True, (245, 232, 184))
            self.screen.blit(key_label, key_label.get_rect(center=key_rect.center))

            if icon is not None:
                icon = pygame.transform.smoothscale(icon, (28, 28))
                if disabled:
                    icon.set_alpha(120)
                self.screen.blit(icon, icon.get_rect(center=(rect.left + 48, rect.centery)))
                text_x = rect.left + 64
            else:
                text_x = rect.left + 40
            label = self.small_font.render(self._fit_text(label_text, self.small_font, rect.right - text_x - 18), True, (238, 232, 207) if not disabled else (145, 143, 130))
            self.screen.blit(label, (text_x, rect.top + 14))

            if ready is True:
                pygame.draw.circle(self.screen, (92, 212, 105), (rect.right - 10, rect.top + 10), 4)
            elif ready is False:
                pygame.draw.line(self.screen, (180, 78, 62), (rect.right - 17, rect.top + 9), (rect.right - 8, rect.top + 18), 2)
                pygame.draw.line(self.screen, (180, 78, 62), (rect.right - 8, rect.top + 9), (rect.right - 17, rect.top + 18), 2)

    def _draw_minimap(self) -> None:
        rows = self.tilemap.rows
        cols = len(rows[0])
        panel = pygame.Rect(SCREEN_WIDTH - 190, 14, 174, 126)
        map_rect = panel.inflate(-14, -22).move(0, 6)
        self._draw_3d_panel(panel, fill=(18, 22, 19), alpha=190, border=(78, 92, 73), depth=5, radius=6)
        label = self.small_font.render("TAC MAP", True, (238, 203, 116))
        self.screen.blit(label, (panel.left + 8, panel.top + 5))

        tile_w = map_rect.width / cols
        tile_h = map_rect.height / len(rows)
        colors = {
            "#": (68, 72, 66),
            "S": (52, 58, 52),
            "w": (42, 80, 102),
            "r": (94, 82, 65),
            "t": (80, 58, 42),
            "g": (44, 82, 46),
            "C": (181, 67, 54),
            ".": (55, 96, 56),
        }
        for y, row in enumerate(rows):
            for x, tile in enumerate(row):
                rect = pygame.Rect(
                    int(map_rect.left + x * tile_w),
                    int(map_rect.top + y * tile_h),
                    max(1, math.ceil(tile_w)),
                    max(1, math.ceil(tile_h)),
                )
                pygame.draw.rect(self.screen, colors.get(tile, colors["."]), rect)

        def map_point(world_pos) -> tuple[int, int]:
            px = map_rect.left + (world_pos[0] / max(1, self.tilemap.width)) * map_rect.width
            py = map_rect.top + (world_pos[1] / max(1, self.tilemap.height)) * map_rect.height
            return int(px), int(py)

        def point(world_pos, color, radius=3):
            px, py = map_point(world_pos)
            pygame.draw.circle(self.screen, (12, 14, 12), (int(px), int(py)), radius + 1)
            pygame.draw.circle(self.screen, color, (int(px), int(py)), radius)

        view = pygame.Rect(
            int(map_rect.left + (self.camera.offset.x / max(1, self.tilemap.width)) * map_rect.width),
            int(map_rect.top + (self.camera.offset.y / max(1, self.tilemap.height)) * map_rect.height),
            max(8, int((SCREEN_WIDTH / max(1, self.tilemap.width)) * map_rect.width)),
            max(8, int((SCREEN_HEIGHT / max(1, self.tilemap.height)) * map_rect.height)),
        )
        pygame.draw.rect(self.screen, (238, 232, 207), view.clip(map_rect), 1)

        capture_marker = map_point(self.tilemap.capture_rect.center)
        pulse = 4 + int(2 * math.sin(pygame.time.get_ticks() / 180))
        pygame.draw.circle(self.screen, (12, 14, 12), capture_marker, 6)
        pygame.draw.circle(self.screen, (238, 203, 116), capture_marker, 4)
        if not self.tilemap.doors_open:
            for door in self.tilemap.door_rects:
                door_pos = map_point(door.center)
                pygame.draw.rect(self.screen, (238, 203, 116), pygame.Rect(0, 0, 6, 6).move(door_pos[0] - 3, door_pos[1] - 3))

        point(self.active_actor.rect.center, (93, 214, 111), 4)
        for enemy in self.enemies:
            point(enemy.rect.center, (210, 76, 61), 3)
        for vehicle in self.enemy_vehicles:
            point(vehicle.rect.center, (220, 143, 72), 4)
        for aircraft in self.enemy_aircraft:
            point(aircraft.rect.center, (236, 214, 87), 3)
        for vehicle in self.vehicles:
            point(vehicle.rect.center, (86, 151, 224), 3)

        objective = self._current_objective_target()
        if objective is not None:
            label, world_pos, color = objective
            target_pos = map_point(world_pos)
            player_pos = map_point(self.active_actor.rect.center)
            pygame.draw.line(self.screen, color, player_pos, target_pos, 1)
            pygame.draw.circle(self.screen, (12, 14, 12), target_pos, 7 + pulse)
            pygame.draw.circle(self.screen, color, target_pos, 4 + pulse)
            tag = self.small_font.render(label[:3], True, (245, 232, 184))
            self.screen.blit(tag, tag.get_rect(center=(target_pos[0], target_pos[1] - 12)))

    def _draw_result_overlay(self) -> None:
        self.result_buttons = []
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))
        
        # Increase height of panel slightly to fit 5 buttons elegantly if next_map is available
        panel_h = 360
        panel = pygame.Rect(SCREEN_WIDTH // 2 - 270, SCREEN_HEIGHT // 2 - panel_h // 2, 540, panel_h)
        border = (238, 203, 116) if self.result == "VICTORY" else (204, 73, 57)
        self._draw_3d_panel(panel, fill=(14, 20, 17), alpha=232, border=border, depth=10, radius=8)
        title_color = (255, 236, 166) if self.result == "VICTORY" else (255, 184, 150)
        title_shadow = self.big_font.render(self.result, True, (42, 34, 24))
        title = self.big_font.render(self.result, True, title_color)
        self.screen.blit(title_shadow, title_shadow.get_rect(center=(panel.centerx + 3, panel.top + 53)))
        self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 50)))
        subtitle_text = "Sector secured. Choose the next operation." if self.result == "VICTORY" else "Regroup and choose your next move."
        subtitle = self.small_font.render(subtitle_text, True, (200, 207, 180))
        self.screen.blit(subtitle, subtitle.get_rect(center=(panel.centerx, panel.top + 91)))
        result_stats = (
            f"Time {self._format_time(self.mission_elapsed)}   "
            f"Kills {self.stats['inf']}/{self.stats['armor']}/{self.stats['air']}   "
            f"Sup {self.stats['supplies']}   +{self.result_reward}c"
        )
        stats_label = self.small_font.render(self._fit_text(result_stats, self.small_font, panel.width - 72), True, (238, 203, 116))
        stats_rect = pygame.Rect(panel.left + 46, panel.top + 112, panel.width - 92, 28)
        pygame.draw.rect(self.screen, (28, 39, 32), stats_rect, border_radius=5)
        pygame.draw.rect(self.screen, (78, 92, 73), stats_rect, 1, border_radius=5)
        self.screen.blit(stats_label, stats_label.get_rect(center=stats_rect.center))

        # Build actions list dynamically
        actions = []
        if self.result == "VICTORY":
            current_idx = self.map_ids.index(self.current_map_id)
            next_idx = current_idx + 1
            if next_idx < len(self.map_ids):
                actions.append(("next_map", "SANG MÀN TIẾP"))
        
        actions.extend([
            ("retry", "RETRY"),
            ("maps", "CHỌN MAP"),
            ("title", "MENU"),
            ("quit", "THOÁT"),
        ])

        # Slightly adjust button height and spacing to perfectly fit 4 or 5 buttons
        btn_h = 28
        btn_spacing = 34
        for index, (action, label_text) in enumerate(actions):
            rect = pygame.Rect(panel.left + 66, panel.top + 145 + index * btn_spacing, panel.width - 132, btn_h)
            
            # Custom primary flag: true for next_map, or maps (if next_map not available on victory)
            primary = (action == "next_map") or (action == "maps" and self.result == "VICTORY" and not any(a[0] == "next_map" for a in actions))
            hot = rect.collidepoint(pygame.mouse.get_pos())
            
            # Premium green fill (45, 110, 54) for primary button, and classic (35, 48, 40) for others
            fill = (45, 110, 54) if primary else (35, 48, 40)
            self._draw_3d_button(
                rect,
                fill,
                (238, 203, 116) if primary or hot else (91, 108, 83),
                active=primary,
                hot=hot,
                depth=4,
                radius=5,
            )
            if primary or hot:
                pygame.draw.rect(self.screen, (255, 223, 128), pygame.Rect(rect.left + 9, rect.top + 6, 4, rect.height - 12), border_radius=2)
            label = self.font.render(label_text, True, (255, 240, 190) if primary else (245, 232, 184))
            self.screen.blit(label, label.get_rect(center=rect.center))
            self.result_buttons.append((rect, action))

        hint = self.small_font.render("R retry   Enter chọn map   Esc menu", True, (189, 204, 168))
        self.screen.blit(hint, hint.get_rect(center=(panel.centerx, panel.bottom - 20)))

    def _shop_icon(self, item_id: str) -> pygame.Surface | None:
        weapon = WEAPONS.get(item_id)
        if weapon is not None:
            if weapon.slot == "melee" and "pickaxe" in self.assets.icons:
                return pygame.transform.smoothscale(self.assets.icons["pickaxe"], (32, 32))
            if weapon.slot in {"secondary", "sidearm"}:
                return pygame.transform.smoothscale(self.assets.frame("prop", 86, 34), (32, 28))
            if weapon.slot == "primary":
                return pygame.transform.smoothscale(self.assets.frame("prop", 90, 34), (36, 24))
        if item_id == "medkit":
            return pygame.transform.smoothscale(self.assets.frame("prop", 65, 34), (34, 34))
        if item_id == "grenade":
            return pygame.transform.smoothscale(self.assets.frame("prop", 114, 34), (34, 34))
        if item_id == "ammo":
            return pygame.transform.smoothscale(self.assets.frame("prop", 88, 34), (34, 34))
        if item_id == "mortar":
            return pygame.transform.smoothscale(self.assets.frame("prop", 98, 34), (34, 34))
        if item_id == "armor":
            return pygame.transform.smoothscale(self.assets.icons["hp"], (30, 30))
        if item_id == "tank":
            return self.assets.frame("m4_sherman", 75, 34)
        return None

    def _draw_cursor(self) -> None:
        cursor = pygame.transform.smoothscale(self.assets.cursor, (42, 42))
        rect = cursor.get_rect(center=pygame.mouse.get_pos())
        self.screen.blit(cursor, rect)


def main() -> None:
    Game().run()
