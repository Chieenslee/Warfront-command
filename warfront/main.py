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
from warfront.network import NetworkServer, NetworkClient

SAVE_PATH = Path.home() / ".warfront_command" / "save.json"


class _DummyBullet:
    """Lightweight bullet used by Client to render server-authoritative bullet positions."""
    def __init__(self, x: float, y: float, rot: float):
        self.pos = pygame.Vector2(x, y)
        self.rot = rot

    def draw(self, surface: pygame.Surface, camera) -> None:
        end = self.pos + pygame.Vector2(math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))) * 12
        pygame.draw.line(surface, (255, 230, 150), camera.apply_pos(self.pos), camera.apply_pos(end), 2)

    def update(self, dt: float) -> bool:
        return True


class _NetworkKeyState:
    def __init__(self, keys: dict):
        self.keys = keys

    def __getitem__(self, key: int) -> bool:
        return {
            pygame.K_w: self.keys.get("w", False),
            pygame.K_a: self.keys.get("a", False),
            pygame.K_s: self.keys.get("s", False),
            pygame.K_d: self.keys.get("d", False),
        }.get(key, False)


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
        self.state = "name_input"
        self.previous_state = "title"
        self.player_name = ""
        self.host_ip = "127.0.0.1"
        self.network_mode = "offline"
        self.menu_tab = "operations"
        self.shop_page = 0
        self.shop_filter = "all"
        self.title_buttons: list[tuple[pygame.Rect, str]] = []
        self.title_selection = 0
        self.title_notice = ""
        self.menu_buttons: list[tuple[pygame.Rect, str]] = []
        self.result_buttons: list[tuple[pygame.Rect, str]] = []
        self.lobby_buttons: list[tuple[pygame.Rect, str]] = []
        self.campaign = self._load_campaign()
        self.mode_config: ModeConfig = OFFLINE_CONFIG
        self.inventory = Inventory(medkits=1, grenades=1, ammo=90)
        self.weapon_mode = "rifle"
        self.equipped_primary = "rifle"
        self.equipped_sidearm = "tokarev"
        self.cutscene_index = 0
        self.cutscene_timer = 0.0
        self.sounds = self._load_sounds()
        self.network_server = None
        self.network_client = None
        self.lobby_players = []
        self.online_sessions: dict[str, dict] = {}
        self._start_music()
        self.reset(self.current_map_id)

    @property
    def current_map_id(self) -> str:
        return self.map_ids[self.selected_map_index]

    def is_online(self) -> bool:
        return getattr(self, "network_mode", "offline") in {"host", "client"}

    def is_online_pvp(self) -> bool:
        return self.is_online() and getattr(self, "game_mode", "campaign") == "pvp"

    @staticmethod
    def _inventory_to_dict(inventory: Inventory) -> dict:
        return {
            "medkits": inventory.medkits,
            "grenades": inventory.grenades,
            "ammo": inventory.ammo,
            "medkit_heal": inventory.medkit_heal,
        }

    @staticmethod
    def _inventory_from_dict(data: dict | None) -> Inventory:
        data = data or {}
        return Inventory(
            medkits=int(data.get("medkits", 1)),
            grenades=int(data.get("grenades", 1)),
            ammo=int(data.get("ammo", 90)),
            medkit_heal=int(data.get("medkit_heal", 45)),
        )

    def _remote_team_for_slot(self, slot: int) -> str:
        if not self.is_online_pvp():
            return "blue"
        # Host is blue. Clients alternate red/blue so Online 2v2 works with
        # 1-3 joined players while the first joiner is immediately an opponent.
        return "red" if slot % 2 == 0 else "blue"

    def _display_team(self, team: str) -> str:
        return "BLUE" if team == "blue" else "RED"

    def _soldier_team_for_online(self, pvp_team: str) -> str:
        return "enemy" if pvp_team == "red" else "player"

    def _session_for_client(self, client_id: str, name: str, slot: int) -> dict:
        session = self.online_sessions.get(client_id)
        if session is None:
            pouch_level = self.campaign.purchases.get("field_pouches", 0)
            session = {
                "id": client_id,
                "name": name,
                "team": self._remote_team_for_slot(slot),
                "inventory": Inventory(medkits=1 + pouch_level, grenades=1 + pouch_level, ammo=90 + pouch_level * 20),
                "primary": self.equipped_primary,
                "sidearm": self.equipped_sidearm,
                "weapon_mode": self.equipped_primary,
                "vehicle": None,
                "connected": True,
                "last_slot": slot,
            }
            self.online_sessions[client_id] = session
        session["name"] = name
        session["connected"] = True
        session["last_slot"] = slot
        return session

    def _host_player_team(self) -> str:
        return "blue"

    def _actor_team(self, actor) -> str:
        if actor is self.player or actor is getattr(self.player, "vehicle", None):
            return self._host_player_team()
        return getattr(actor, "pvp_team", "blue" if getattr(actor, "team", "player") == "player" else "red")

    def _player_spawn_tile(self, index: int, team: str = "blue") -> tuple[int, int]:
        base = self.tilemap.spawns["player"]
        if self.is_online_pvp() and team == "red" and self.tilemap.spawns.get("enemies"):
            base = self.tilemap.spawns["enemies"][index % len(self.tilemap.spawns["enemies"])]
        offsets = [(0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, 1), (1, -1)]
        for offset in offsets[index:] + offsets[:index]:
            tile = (base[0] + offset[0], base[1] + offset[1])
            if self.tilemap.passable_tile(tile):
                return tile
        return base

    def _spawn_remote_player(self, index: int, name: str, pvp_team: str = "blue") -> Soldier:
        spawn_tile = self._player_spawn_tile(index + 1, pvp_team)
        remote = Soldier(
            self.tilemap.spawn_position(spawn_tile),
            is_player=False,
            team=self._soldier_team_for_online(pvp_team),
            bot_name=name,
        )
        remote.player_controlled = True
        remote.pvp_team = pvp_team
        remote.speed = self.player.speed
        remote.vehicle = None
        return remote

    def reset(self, map_id: str | None = None) -> None:
        if map_id and map_id in self.map_ids:
            self.selected_map_index = self.map_ids.index(map_id)
        self.tilemap = TileMap(map_id or self.current_map_id)
        self.camera = Camera(self.tilemap.width, self.tilemap.height)
        spawns = self.tilemap.spawns
        self.player = Soldier(self.tilemap.spawn_position(spawns["player"]), is_player=True, bot_name=getattr(self, "player_name", "Player"))
        self.player.weapon_pose = WEAPONS.get(self.weapon_mode, WEAPONS["rifle"]).animation_key

        self.ally_bots = []
        if getattr(self, "game_mode", "campaign") == "pvp":
            if getattr(self, "network_mode", "offline") == "offline":
                # Spawn a single enemy PVP bot far from player
                enemy_pos = self.tilemap.spawn_position(spawns["enemies"][0] if spawns["enemies"] else (self.player.rect.x + 400, self.player.rect.y + 400))
                bot = Soldier(enemy_pos, is_player=False, team="enemy", bot_name=f"Bot ({getattr(self, 'bot_difficulty', 'normal')})", difficulty=getattr(self, "bot_difficulty", "normal"))
                self.enemies = [bot]
            else:
                self.enemies = []
        else:
            if getattr(self, "network_mode", "offline") == "offline":
                # Offline: spawn 3 AI ally bots
                for i in range(1, 4):
                    bot_pos = (self.player.rect.x + random.randint(-40, 40), self.player.rect.y + random.randint(-40, 40))
                    bot = Soldier(bot_pos, is_player=False, team="player", bot_name=f"Bot {i}")
                    bot.speed = self.player.speed * 0.95
                    self.ally_bots.append(bot)
            # Online: do not spawn ally bots. Remote human players are created
            # only after real clients send input, so empty slots never overlap
            # with real accounts.

            if getattr(self, "network_mode", "offline") == "client":
                self.enemies = []
            else:
                self.enemies = [Soldier(self.tilemap.spawn_position(pos)) for pos in spawns["enemies"]]

        self.bullets = []
        self.grenades = []
        self.enemy_aircraft = [] if self.is_online_pvp() or getattr(self, "network_mode", "offline") == "client" else self._spawn_enemy_aircraft(spawns)
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
        self.enemy_vehicles = [] if self.is_online_pvp() or getattr(self, "network_mode", "offline") == "client" else [
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
        self.winning_team = None
        self.result_awarded = False
        self.result_reward = 0
        self.boss_triggered = False
        self.boss_vehicle = None
        self.stats = {"inf": 0, "armor": 0, "air": 0, "supplies": 0}
        self.radio_log: list[tuple[str, tuple[int, int, int], float]] = []
        self.add_radio(f"TRIỂN KHAI: {self.tilemap.data['title']}", (238, 203, 116), 5.0)
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
        music_dir = ASSET_DIR / "audio" / "music"
        candidates = []
        if map_id in music_files:
            candidates.append(music_dir / music_files[map_id])
        candidates.extend(music_dir / filename for filename in music_files.values())
        music_path = next((path for path in candidates if path.exists()), None)

        if not pygame.mixer.get_init() or music_path is None:
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
        except pygame.error as exc:
            print(f"[AUDIO] Music load failed: {exc}")

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

    def _actor_alive_for_team(self, actor) -> bool:
        vehicle = getattr(actor, "vehicle", None)
        return bool(getattr(actor, "alive", False) or (vehicle is not None and getattr(vehicle, "alive", False)))

    def _controlled_actor_for(self, soldier):
        vehicle = getattr(soldier, "vehicle", None)
        return vehicle if vehicle is not None and vehicle.alive else soldier

    def _pvp_team_alive(self, team: str) -> bool:
        if team == self._host_player_team() and self._actor_alive_for_team(self.player):
            return True
        return any(
            session.get("connected", False)
            and getattr(session.get("actor"), "pvp_team", "blue") == team
            and self._actor_alive_for_team(session.get("actor"))
            for session in self.online_sessions.values()
        ) or any(
            self._remote_session_for_bot(bot) is None
            and getattr(bot, "pvp_team", "blue") == team
            and self._actor_alive_for_team(bot)
            for bot in getattr(self, "ally_bots", [])
        )

    def _remote_session_for_bot(self, bot):
        for session in self.online_sessions.values():
            if session.get("actor") is bot:
                return session
        return None

    def _weapon_for_session(self, session: dict):
        weapon_id = session.get("weapon_mode") or session.get("primary") or "rifle"
        return WEAPONS.get(weapon_id, WEAPONS["rifle"])

    def _apply_weapon_to_bullet(self, bullet, definition, owner_team: str) -> None:
        bullet.damage = definition.damage + self.weapon_damage_bonus()
        bullet.speed = definition.bullet_speed
        bullet.armor_piercing = definition.armor_piercing
        bullet.life = max(0.35, definition.range_px / max(1, definition.bullet_speed))
        bullet.weapon = definition.id
        bullet.owner_team = owner_team
        bullet.friendly = owner_team == "blue"

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

    def _poll_lobby_network(self) -> None:
        """Called every frame while in lobby state. Syncs player list and handles game start from host."""
        if not self.network_client:
            return
        if self.network_client.connected:
            state = self.network_client.server_state
            self.lobby_players = state.get("lobby_players", [])
            if state.get("status") == "playing":
                # Host has started the game - client follows
                if self.network_mode == "client":
                    self.game_mode = state.get("game_mode", "campaign")
                    map_id = state.get("map_id", self.current_map_id)
                    if map_id in self.map_ids:
                        self.selected_map_index = self.map_ids.index(map_id)
                    self.previous_state = "title"
                    self.start_selected_map()
        if self.network_mode == "host" and self.network_server:
            # Host: keep broadcasting lobby status so clients can see player list
            host_id = self.network_client.client_id if self.network_client else "host"
            client_records = []
            remote_slot = 0
            for client in self.network_server.get_clients().values():
                if client.get("id") == host_id:
                    continue
                session = self._session_for_client(client["id"], client.get("name", "Player"), remote_slot)
                client_records.append(
                    {
                        "id": client["id"],
                        "name": session["name"],
                        "team": session["team"],
                        "ready": client.get("ready", True),
                        "connected": True,
                    }
                )
                remote_slot += 1
            players = [{"id": host_id, "name": self.player_name or "Host", "team": self._host_player_team(), "ready": True, "connected": True}]
            players.extend(client_records)
            self.lobby_players = players
            self.network_server.broadcast_state(
                {
                    "status": "lobby",
                    "map_id": self.current_map_id,
                    "game_mode": getattr(self, "game_mode", "campaign"),
                    "players": [p["name"] for p in players],
                    "lobby_players": players,
                }
            )

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            if self.state == "play" and not self.result:
                self.update(dt)
            elif self.state == "cutscene":
                self.cutscene_timer += dt
            elif self.state == "lobby":
                # Poll network for lobby sync even when not in play state
                self._poll_lobby_network()
            self.draw()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                if self.state in ("title", "name_input", "ip_input", "pvp_menu", "lobby") and event.key == pygame.K_ESCAPE:
                    if self.state in ("pvp_menu", "lobby"):
                        self.state = "title"
                        if self.network_server:
                            self.network_server.stop()
                            self.network_server = None
                        if self.network_client:
                            self.network_client.stop()
                            self.network_client = None
                    else:
                        pygame.quit()
                        sys.exit()

                # Handle text input for name/IP
                if self.state == "lobby":
                    if event.key == pygame.K_RETURN and getattr(self, "network_mode", "offline") == "host":
                        self.start_selected_map()
                    continue
                if self.state == "name_input":
                    if event.key == pygame.K_RETURN and self.player_name.strip():
                        self.state = "title"
                    elif event.key == pygame.K_BACKSPACE:
                        self.player_name = self.player_name[:-1]
                    else:
                        if len(self.player_name) < 12 and event.unicode.isprintable():
                            self.player_name += event.unicode
                    continue

                if self.state == "ip_input":
                    if event.key == pygame.K_RETURN and self.host_ip.strip():
                        self.network_mode = "client"
                        self.state = "lobby"
                        if self.network_client:
                            self.network_client.stop()
                        self.network_client = NetworkClient(self.host_ip, self.player_name)
                    elif event.key == pygame.K_BACKSPACE:
                        self.host_ip = self.host_ip[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "title"
                    else:
                        if len(self.host_ip) < 16 and (event.unicode.isdigit() or event.unicode == "."):
                            self.host_ip += event.unicode
                    continue

                if self.state == "pvp_menu":
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        self.pvp_selection = (getattr(self, "pvp_selection", 0) + 1) % 4
                        self._play_sound("menu_select")
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.pvp_selection = (getattr(self, "pvp_selection", 0) - 1) % 4
                        self._play_sound("menu_select")
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.run_pvp_action()
                    continue

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
                elif self.state == "cutscene" and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                    chapter = CHAPTERS_BY_MAP.get(self.current_map_id)
                    if chapter and getattr(chapter, "dialogues", ()):
                        # If typing is still happening, we can skip to end of typing (which we can't easily track without complex state, so we just advance to next line)
                        self.cutscene_index += 1
                        self.cutscene_timer = 0.0
                        if self.cutscene_index >= len(chapter.dialogues):
                            self.state = "play"
                    else:
                        self.state = "play"
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
                elif self.state == "play" and event.key == pygame.K_h and getattr(self, "network_mode", "offline") != "client":
                    if self.inventory.use_medkit(self.player):
                        self._play_sound("heal")
                elif self.state == "play" and getattr(self, "network_mode", "offline") != "client":
                    if event.key == pygame.K_g:
                        self.throw_grenade(self.camera.world_mouse(pygame.mouse.get_pos()))
                    elif event.key == pygame.K_e:
                        self.interact()
                    elif event.key == pygame.K_q:
                        self.swing_gun_bash(self.camera.world_mouse(pygame.mouse.get_pos()))
                    elif event.key == pygame.K_1:
                        self.weapon_mode = self.equipped_primary
                    elif event.key == pygame.K_2:
                        self.weapon_mode = self.equipped_sidearm
                    elif event.key == pygame.K_3:
                        self.swing_gun_bash(self.camera.world_mouse(pygame.mouse.get_pos()))
                    elif event.key == pygame.K_m:
                        self.call_mortar(self.camera.world_mouse(pygame.mouse.get_pos()))
            if self.state == "title" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_title_click(event.pos)
            if self.state == "lobby" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_lobby_click(event.pos)
            if self.state == "menu" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_menu_click(event.pos)
            if self.state == "play" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.result:
                if getattr(self, "network_mode", "offline") == "client":
                    continue
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
                        bullet.owner_team = self._actor_team(actor)
                        actor.reload = definition.cooldown * self.weapon_cooldown_scale()
                        if definition.recoil_shake:
                            self.camera.shake(definition.recoil_shake, 0.045)
                    else:
                        bullet.owner_team = self._actor_team(actor)
                    self.bullets.append(bullet)
                    if actor is self.player:
                        self.inventory.ammo = max(0, self.inventory.ammo - 1)
                    weapon = getattr(bullet, "weapon", "rifle")
                    self.effects.muzzle_flash(actor.rect.center, bullet.direction, "tank" if weapon == "tank" else "rifle")
                    self._play_sound("tank_fire" if weapon == "tank" else "rifle")
            if self.state == "play" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and not self.result:
                if getattr(self, "network_mode", "offline") != "client":
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
                    vehicle.pvp_team = self._host_player_team()
                    self.player.rect.center = vehicle.rect.center
                    self._play_sound("menu_select")
                return

    def throw_grenade(self, target) -> None:
        if not self.inventory.use_grenade():
            return
        start = pygame.Vector2(self.active_actor.rect.center)
        max_range = max(560, min(980, min(self.tilemap.width, self.tilemap.height) * 0.52))
        grenade = GrenadeProjectile(start, target, max_range)
        grenade.owner_team = self._actor_team(self.active_actor)
        self.grenades.append(grenade)
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
        owner_team: str | None = None,
    ) -> None:
        target = pygame.Vector2(target)
        self.effects.bullet_hit(target, "grenade")
        self.camera.shake(1.6, 0.2)
        if self.is_online_pvp() and owner_team in {"blue", "red"}:
            for actor in [self.player, *getattr(self, "ally_bots", []), *self.vehicles]:
                if not getattr(actor, "alive", False) or self._actor_team(actor) == owner_team:
                    continue
                distance = pygame.Vector2(actor.rect.center).distance_to(target)
                if distance <= radius + (20 if isinstance(actor, TankVehicle) else 0):
                    falloff = max(0.25, 1.0 - distance / max(1, radius))
                    actual = actor.damage(int(damage * falloff), armor_piercing)
                    self.add_floater(f"-{actual}", actor.rect.center, (255, 118, 100))
                    if isinstance(actor, TankVehicle) and not actor.alive:
                        self.effects.tank_explosion(actor.rect.center)
            return
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

    def detonate_grenade(self, target, owner_team: str | None = None) -> None:
        grenade = WEAPONS["grenade"]
        self.detonate_explosion(
            target,
            damage=grenade.damage,
            radius=92,
            armor_piercing=grenade.armor_piercing,
            friendly_scale=0.45,
            owner_team=owner_team,
        )

    def _title_actions(self) -> list[tuple[str, str, str]]:
        return [
            ("offline", "BẮT ĐẦU OFFLINE", "Chơi chiến dịch một mình cùng 3 Bot AI hỗ trợ."),
            ("online", "TẠO PHÒNG (HOST)", "Làm máy chủ để mời bạn bè qua mạng LAN/IP."),
            ("join", "VÀO PHÒNG (JOIN)", "Nhập IP để tham gia vào phòng của người khác."),
            ("pvp", "CHẾ ĐỘ PVP", "Đấu trường sinh tử: Solo vs Bot hoặc Online 2v2."),
            ("shop", "KHO VŨ KHÍ & NÂNG CẤP", "Mua súng, giáp, vật phẩm và xe tăng."),
            ("quit", "THOÁT GAME", "Rời khỏi hệ thống chỉ huy."),
        ]

    def run_title_action(self, action: str) -> None:
        self.title_notice = ""
        if action == "offline":
            self.network_mode = "offline"
            self.menu_tab = "operations"
            self.state = "menu"
        elif action == "maps":
            self.menu_tab = "operations"
            self.state = "menu"
        elif action == "shop":
            self.menu_tab = "shop"
            self.state = "menu"
        elif action == "online":
            self.network_mode = "host"
            self.state = "lobby"
            try:
                import socket
                self.local_ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                self.local_ip = "127.0.0.1"
            if self.network_server:
                self.network_server.stop()
            if self.network_client:
                self.network_client.stop()
            self.network_server = NetworkServer()
            self.network_client = NetworkClient("127.0.0.1", self.player_name)
            self._play_sound("menu_select")
        elif action == "join":
            self.state = "ip_input"
            self._play_sound("menu_select")
        elif action == "pvp":
            self.state = "pvp_menu"
            self.pvp_selection = 0
            self._play_sound("menu_select")
        elif action == "quit":
            pygame.quit()
            sys.exit()

    def run_pvp_action(self) -> None:
        actions = ["bot_easy", "bot_normal", "bot_hard", "online_2v2"]
        action = actions[getattr(self, "pvp_selection", 0)]
        self.game_mode = "pvp"
        if action.startswith("bot_"):
            self.bot_difficulty = action.split("_")[1]
            self.network_mode = "offline"
            self.menu_tab = "operations"
            self.state = "menu"
            self._play_sound("menu_select")
        elif action == "online_2v2":
            self.network_mode = "host"
            self.state = "lobby"
            try:
                import socket
                self.local_ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                self.local_ip = "127.0.0.1"
            if self.network_server:
                self.network_server.stop()
            if self.network_client:
                self.network_client.stop()
            self.network_server = NetworkServer()
            self.network_client = NetworkClient("127.0.0.1", self.player_name)
            self._play_sound("menu_select")

    def handle_title_click(self, pos: tuple[int, int]) -> None:
        for index, (rect, action) in enumerate(self.title_buttons):
            if rect.collidepoint(pos):
                self.title_selection = index
                self.run_title_action(action)
                return

    def start_selected_map(self) -> None:
        self.weapon_mode = self.equipped_primary
        self.reset(self.current_map_id)
        chapter = CHAPTERS_BY_MAP.get(self.current_map_id)
        if chapter and getattr(chapter, "dialogues", ()) and getattr(self, "network_mode", "offline") == "offline":
            self.state = "cutscene"
            self.cutscene_index = 0
            self.cutscene_timer = 0.0
        else:
            self.state = "play"

        if getattr(self, "network_mode", "offline") == "host" and self.network_server:
            self.network_server.broadcast_state({"status": "playing", "map_id": self.current_map_id, "game_mode": getattr(self, "game_mode", "campaign")})

    def active_weapon(self):
        return WEAPONS.get(self.weapon_mode, WEAPONS["rifle"])

    def weapon_damage_bonus(self) -> int:
        return self.campaign.purchases.get("weapon_training", 0) * 4

    def weapon_cooldown_scale(self) -> float:
        return max(0.62, 1.0 - self.campaign.purchases.get("reload_drill", 0) * 0.07)

    def handle_title_click(self, pos: tuple[int, int]) -> None:
        for rect, action in self.title_buttons:
            if rect.collidepoint(pos):
                self.run_title_action(action)
                return

    def handle_lobby_click(self, pos: tuple[int, int]) -> None:
        for rect, action in self.lobby_buttons:
            if rect.collidepoint(pos):
                if action == "shop":
                    self.menu_tab = "shop"
                    self.previous_state = "lobby"
                    self.state = "menu"
                    self._play_sound("menu_select")
                elif action == "maps":
                    self.menu_tab = "operations"
                    self.previous_state = "lobby"
                    self.state = "menu"
                    self._play_sound("menu_select")
                elif action == "start":
                    self.start_selected_map()
                return

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
                elif action == "back_lobby":
                    self.previous_state = "title"
                    self.state = "lobby"
                    self._play_sound("menu_select")
                elif action == "play" and getattr(self, "previous_state", "title") == "lobby":
                    # coming from lobby, start game
                    self.previous_state = "title"
                    self.start_selected_map()

    def handle_result_click(self, pos: tuple[int, int]) -> None:
        for rect, action in self.result_buttons:
            if not rect.collidepoint(pos):
                continue
            self._play_sound("menu_select")
            if action == "retry":
                self.reset()
                self.state = "play"
            elif action == "next_map":
                current_idx = self.map_ids.index(self.current_map_id)
                next_idx = current_idx + 1
                if next_idx < len(self.map_ids):
                    self.reset(self.map_ids[next_idx])
                    chapter = CHAPTERS_BY_MAP.get(self.current_map_id)
                    if chapter and getattr(chapter, "dialogues", ()):
                        self.state = "cutscene"
                        self.cutscene_index = 0
                        self.cutscene_timer = 0.0
                    else:
                        self.state = "play"
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
        # Network lobby sync (fallback check inside update in case run() missed a frame)
        if self.state == "lobby" and getattr(self, "network_client", None) and self.network_client.connected:
            state = self.network_client.server_state
            if state.get("status") == "playing":
                if self.network_mode == "client":
                    self.game_mode = state.get("game_mode", "campaign")
                    map_id = state.get("map_id", self.current_map_id)
                    if map_id in self.map_ids:
                        self.selected_map_index = self.map_ids.index(map_id)
                    self.start_selected_map()

        # Send inputs and receive state for Client
        is_client = False
        if self.state == "play" and getattr(self, "network_mode", "offline") == "client":
            is_client = self._sync_client(dt)

        if not is_client:
            self.mission_elapsed += dt

        if not is_client:
            keys = pygame.key.get_pressed()
            mouse_world = self.camera.world_mouse(pygame.mouse.get_pos())
            self.player.weapon_pose = self.active_weapon().animation_key
            if getattr(self.player, "vehicle", None):
                self.update_player_vehicle(dt, keys, mouse_world)
                self.player.rect.center = self.player.vehicle.rect.center
            else:
                self.player.update_player(dt, keys, mouse_world, self.tilemap)
        if not is_client:
            self.camera.follow(self.active_actor.rect, self.screen.get_size(), dt)
        self.mission_grace = max(0.0, self.mission_grace - dt)
        self.mortar_cooldown = max(0.0, self.mortar_cooldown - dt)
        self.melee_swings = [(pos, angle, life - dt) for pos, angle, life in self.melee_swings if life > dt]
        self.radio_log = [(text, color, life - dt) for text, color, life in self.radio_log if life > dt]

        if not is_client and not self.mission_started:
            for bot in getattr(self, "ally_bots", []):
                if getattr(bot, "player_controlled", False):
                    continue

        if self.mission_started and not is_client:
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
                # Enemies target the nearest human player (host or any client bot)
                all_human_targets = [self.active_actor] + [b for b in getattr(self, "ally_bots", []) if b.alive and b.player_controlled]
                nearest_target = min(all_human_targets, key=lambda t: pygame.Vector2(enemy.rect.center).distance_to(t.rect.center))
                self.bullets.extend(enemy.update_bot(dt, [nearest_target], follow_target=nearest_target, tilemap=self.tilemap, path=self.enemy_paths.get(id(enemy))))

            for bot in getattr(self, "ally_bots", []):
                if not getattr(bot, "player_controlled", False):
                    self.bullets.extend(bot.update_bot(dt, self.enemies + self.enemy_vehicles, self.active_actor, self.tilemap))

            self.update_enemy_vehicles(dt)
            self.update_enemy_aircraft(dt)
        if not is_client:
            for vehicle in [*self.vehicles, *self.enemy_vehicles]:
                vehicle.update(dt)
                if vehicle.moving and random.random() < 12 * dt:
                    back_angle = (vehicle.angle + 180) % 360
                    back_dir = pygame.Vector2(math.cos(math.radians(back_angle)), math.sin(math.radians(back_angle)))
                    smoke_pos = pygame.Vector2(vehicle.rect.center) + back_dir * (vehicle.stats.size[0] * 0.4)
                    self.particles.smoke(smoke_pos, 1)

        if not is_client:
            self.pickup_items()
            self.update_grenades(dt)
            self.update_support_visuals(dt)

        if not is_client:
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
                if self.is_online_pvp() and hasattr(bullet, "owner_team"):
                    owner_team = getattr(bullet, "owner_team", "blue")
                    targets = [self.player, *getattr(self, "ally_bots", []), *self.vehicles]
                    hit_target = next(
                        (
                            target
                            for target in targets
                            if getattr(target, "alive", False)
                            and self._actor_team(target) != owner_team
                            and target.rect.colliderect(bullet.rect)
                        ),
                        None,
                    )
                    if hit_target:
                        was_alive = hit_target.alive
                        actual = hit_target.damage(bullet.damage, bullet.armor_piercing)
                        self.add_floater(f"-{actual}", hit_target.rect.center, (255, 118, 100))
                        self.effects.bullet_hit(bullet.pos, bullet.weapon)
                        self._play_sound("hit")
                        self.camera.shake(0.8, 0.12)
                        if was_alive and not hit_target.alive and isinstance(hit_target, TankVehicle):
                            self.effects.tank_explosion(hit_target.rect.center)
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
                            self.add_radio("ĐÃ TIÊU DIỆT XE TĂNG ĐỊCH", (255, 166, 104), 4.5)
                        continue
                else:
                    active = self.active_actor
                    friendly_targets = [active]
                    friendly_targets.extend(vehicle for vehicle in self.vehicles if vehicle is not active)
                    if active is not self.player:
                        friendly_targets.append(self.player)
                    friendly_targets.extend(getattr(self, "ally_bots", []))
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

        # Add dead bots to corpses (host/offline only - client tracks bots via server state)
        if not is_client:
            if not self.is_online():
                for bot in getattr(self, "ally_bots", []):
                    if not bot.alive:
                        self.corpses.append((bot._current_sprite(), bot.rect.copy(), 3.0))
                self.ally_bots = [bot for bot in getattr(self, "ally_bots", []) if bot.alive]

        self.corpses = [(sprite, rect, life - dt) for sprite, rect, life in self.corpses if life > dt]
        self.floaters = [(text, pos + pygame.Vector2(0, -28 * dt), color, life - dt) for text, pos, color, life in self.floaters if life > dt]
        self.particles.update(dt)

        if not is_client:
            if self.mission_started and self.tilemap.capture_rect.colliderect(self.active_actor.rect):
                map_config = MAPS.get(self.current_map_id)
                if map_config and "boss_wave" in map_config and not getattr(self, "boss_triggered", False):
                    self.boss_triggered = True
                    boss_data = map_config["boss_wave"]
                    boss_pos = self.tilemap.spawn_position(boss_data["boss_spawn"])
                    boss = TankVehicle(boss_pos, boss_data["boss_kind"], faction="enemy")
                    self.enemy_vehicles.append(boss)
                    self.boss_vehicle = boss
                    for add_pos in boss_data.get("adds_spawns", []):
                        pos = self.tilemap.spawn_position(add_pos)
                        self.enemies.append(Soldier(pos, is_player=False))
                    self.add_radio("CẢNH BÁO: SIÊU TĂNG HẠNG NẶNG ĐANG TIẾN LÊN!", (255, 60, 60), 8.0)
                    self._play_sound("explosion")
                    self.camera.shake(2.0, 0.5)

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

            if getattr(self, "game_mode", "campaign") == "pvp":
                if self.is_online_pvp():
                    red_has_joined = any(session.get("team") == "red" for session in self.online_sessions.values())
                    blue_alive = self._pvp_team_alive("blue")
                    red_alive = self._pvp_team_alive("red")
                    if red_has_joined and self.result is None:
                        if blue_alive and not red_alive:
                            self.result = "VICTORY"
                            self.winning_team = "blue"
                            self.add_radio("BLUE TEAM WINS", (101, 174, 109), 8.0)
                            self.result_reward = 150
                            self.result_awarded = True
                            self.campaign.credits += self.result_reward
                            self.save_campaign()
                            self._play_sound("capture")
                        elif red_alive and not blue_alive:
                            self.result = "DEFEAT"
                            self.winning_team = "red"
                            self.add_radio("RED TEAM WINS", (255, 118, 100), 8.0)
                else:
                    if self.player.hp <= 0 and self.result is None:
                        self.result = "DEFEAT"
                        self.winning_team = "enemy"
                        self.add_radio("BẠN ĐÃ BỊ HẠ GỤC", (255, 118, 100), 8.0)
                    elif not self.enemies and self.result is None:
                        self.result = "VICTORY"
                        self.winning_team = "blue"
                        self.add_radio("ĐÃ TIÊU DIỆT MỤC TIÊU", (101, 174, 109), 8.0)
                        self.result_reward = 150 # PVP reward
                        self.result_awarded = True
                        self.campaign.credits += self.result_reward
                        self.save_campaign()
                        self._play_sound("capture")
            else:
                if self.player.hp <= 0 and self.result is None:
                    self.result = "MISSION FAILED"
                    self.winning_team = "enemy"
                    self.add_radio("NHIỆM VỤ THẤT BẠI", (255, 118, 100), 8.0)
                elif self.capture >= CAPTURE_SECONDS and self.result is None:
                    if getattr(self, "boss_triggered", False) and getattr(self, "boss_vehicle", None) and self.boss_vehicle.alive:
                        pass # Wait for boss to die
                    else:
                        self.result = "VICTORY"
                        self.winning_team = "blue"
                        self.add_radio("ĐÃ KIỂM SOÁT KHU VỰC", (101, 174, 109), 8.0)
                        chapter = CHAPTERS_BY_MAP.get(self.tilemap.map_id)
                        if chapter and not self.result_awarded:
                            self.campaign.credits += chapter.reward
                            unlocked = self.campaign.unlock_next_after(self.tilemap.map_id)
                            if unlocked:
                                self.add_radio(f"ĐÃ MỞ KHÓA: {MAPS[unlocked]['title']}", (238, 203, 116), 6.0)
                            self.result_reward = chapter.reward
                            self.result_awarded = True
                            self.save_campaign()
                            self._play_sound("capture")

        # Network Host state serialization
        if getattr(self, "network_mode", "offline") == "host":
            self._sync_host(dt)

    def _sync_host(self, dt: float) -> None:
        if not self.network_server:
            return

        host_client_id = self.network_client.client_id if getattr(self, "network_client", None) else None

        # Process real remote clients only. The host also owns a local loopback
        # client for lobby sync; skip it so it never creates a fake P2.
        client_inputs = [
            (addr, data)
            for addr, data in self.network_server.get_clients().items()
            if data["id"] != host_client_id
        ]
        client_mapping = {}
        vehicle_mapping = {}
        connected_ids = {data["id"] for _addr, data in client_inputs}
        for session in self.online_sessions.values():
            session["connected"] = session["id"] in connected_ids
        while len(self.ally_bots) < len(client_inputs):
            self.ally_bots.append(self._spawn_remote_player(len(self.ally_bots), f"P{len(self.ally_bots) + 2}"))

        for bot_idx, (_addr, data) in enumerate(client_inputs):
            session = self._session_for_client(data["id"], data.get("name", f"P{bot_idx + 2}"), bot_idx)
            bot = session.get("actor")
            if bot is None or bot not in self.ally_bots:
                if bot_idx < len(self.ally_bots) and self._remote_session_for_bot(self.ally_bots[bot_idx]) is None:
                    bot = self.ally_bots[bot_idx]
                else:
                    bot = self._spawn_remote_player(bot_idx, session["name"], session["team"])
                    self.ally_bots.append(bot)
                session["actor"] = bot
            bot.bot_name = session["name"]
            bot.player_controlled = True
            bot.pvp_team = session["team"]
            bot.team = self._soldier_team_for_online(session["team"])
            actor = self._controlled_actor_for(bot)
            inputs = data["inputs"]
            if inputs:
                keys = inputs.get("keys", {})
                actor = self._controlled_actor_for(bot)
                mx, my = inputs.get("mouse_world", [actor.rect.centerx, actor.rect.centery])
                now_ms = pygame.time.get_ticks()

                weapon_id = inputs.get("weapon_mode", session.get("weapon_mode", session.get("primary", "rifle")))
                if inputs.get("weapon1"):
                    weapon_id = session.get("primary", self.equipped_primary)
                elif inputs.get("weapon2"):
                    weapon_id = session.get("sidearm", self.equipped_sidearm)
                if weapon_id in WEAPONS:
                    session["weapon_mode"] = weapon_id
                definition = self._weapon_for_session(session)
                bot.weapon_pose = definition.animation_key

                inventory = session["inventory"]
                if inputs.get("shoot") and actor.reload <= 0:
                    if actor is bot and inventory.ammo <= 0:
                        bullet = None
                    else:
                        bullet = actor.shoot(pygame.Vector2(mx, my))
                    if bullet:
                        if actor is bot:
                            spread = random.uniform(-definition.spread_degrees, definition.spread_degrees)
                            bullet.direction = bullet.direction.rotate(spread)
                            self._apply_weapon_to_bullet(bullet, definition, session["team"])
                            actor.reload = definition.cooldown * self.weapon_cooldown_scale()
                            inventory.ammo = max(0, inventory.ammo - 1)
                        else:
                            bullet.owner_team = session["team"]
                            bullet.friendly = session["team"] == "blue"
                        self.bullets.append(bullet)
                        self.effects.muzzle_flash(actor.rect.center, bullet.direction, "tank" if getattr(bullet, "weapon", "") == "tank" else "rifle")
                        self._play_sound("tank_fire" if getattr(bullet, "weapon", "") == "tank" else "rifle")

                if actor is bot:
                    bot.update_player(dt, _NetworkKeyState(keys), pygame.Vector2(mx, my), self.tilemap)
                    bot.weapon_pose = definition.animation_key
                else:
                    actor.moving = False
                    turn = int(keys.get("d", False)) - int(keys.get("a", False))
                    throttle = int(keys.get("w", False)) - int(keys.get("s", False))
                    aim = pygame.Vector2(mx, my) - pygame.Vector2(actor.rect.center)
                    if aim.length_squared():
                        actor.rotate_turret_toward(math.degrees(math.atan2(aim.y, aim.x)), 145 * dt)
                    if turn:
                        actor.angle = (actor.angle + turn * 95 * dt) % 360
                    if throttle:
                        facing = pygame.Vector2(math.cos(math.radians(actor.angle)), math.sin(math.radians(actor.angle)))
                        self._move_vehicle(actor, facing * actor.speed * throttle * dt)
                    bot.rect.center = actor.rect.center

                if inputs.get("interact") and now_ms - getattr(bot, "_net_interact_ms", -99999) >= 450:
                    bot._net_interact_ms = now_ms
                    near_door = any(
                        pygame.Vector2(actor.rect.center).distance_to(door.center) <= 140
                        for door in self.tilemap.door_rects
                    ) if not self.tilemap.doors_open else False
                    if near_door:
                        self.tilemap.open_doors()
                        self.mission_started = True
                        self.mission_grace = 1.5
                        self.add_radio(f"{bot.bot_name} OPENED SAFE-ROOM GATE", (238, 203, 116), 4.0)
                        self._play_sound("capture")
                    elif getattr(bot, "vehicle", None):
                        vehicle = bot.vehicle
                        for pos in vehicle.exit_candidates():
                            exit_rect = bot.rect.copy()
                            exit_rect.center = pos
                            if not self.tilemap.blocked(exit_rect):
                                vehicle.exit(override_pos=pos)
                                session["vehicle"] = None
                                break
                    else:
                        for vehicle in self.vehicles:
                            if vehicle.alive and not vehicle.occupied and pygame.Vector2(vehicle.rect.center).distance_to(bot.rect.center) <= 78:
                                if vehicle.enter(bot):
                                    vehicle.pvp_team = session["team"]
                                    bot.rect.center = vehicle.rect.center
                                    session["vehicle"] = self.vehicles.index(vehicle)
                                    self._play_sound("menu_select")
                                break

                if inputs.get("medkit") and now_ms - getattr(bot, "_net_medkit_ms", -99999) >= 8000:
                    if inventory.use_medkit(bot):
                        bot._net_medkit_ms = now_ms
                        self.add_floater("+55", bot.rect.center, (108, 224, 116))
                        self._play_sound("heal")

                if inputs.get("melee") and now_ms - getattr(bot, "_net_melee_ms", -99999) >= 420:
                    bot._net_melee_ms = now_ms
                    bash = WEAPONS["gun_bash"]
                    bot.melee_flash = 0.16
                    self.melee_swings.append((pygame.Vector2(bot.rect.center), bot.aim_angle, 0.16))
                    origin = pygame.Vector2(bot.rect.center)
                    facing = pygame.Vector2(math.cos(math.radians(bot.aim_angle)), math.sin(math.radians(bot.aim_angle)))
                    targets = [*self.enemies, *self.enemy_vehicles]
                    if self.is_online_pvp():
                        targets.extend(
                            other for other in [self.player, *self.ally_bots] if other is not bot and self._actor_team(other) != session["team"]
                        )
                    for target in targets:
                        to_target = pygame.Vector2(target.rect.center) - origin
                        if to_target.length() <= bash.range_px and (
                            not to_target.length_squared() or facing.dot(to_target.normalize()) > 0.18
                        ):
                            actual = target.damage(bash.damage, bash.armor_piercing)
                            self.add_floater(f"-{actual}", target.rect.center, (255, 226, 128))
                            self.effects.bullet_hit(target.rect.center, "gun_bash")

                if inputs.get("grenade") and now_ms - getattr(bot, "_net_grenade_ms", -99999) >= 1300 and inventory.use_grenade():
                    bot._net_grenade_ms = now_ms
                    grenade = WEAPONS["grenade"]
                    projectile = GrenadeProjectile(actor.rect.center, pygame.Vector2(mx, my), grenade.range_px)
                    projectile.owner_team = session["team"]
                    self.grenades.append(projectile)
                    self._play_sound("grenade")

                if inputs.get("mortar") and now_ms - getattr(bot, "_net_mortar_ms", -99999) >= 7500 and inventory.grenades > 0:
                    target = pygame.Vector2(mx, my)
                    if pygame.Vector2(actor.rect.center).distance_to(target) <= WEAPONS["mortar"].range_px:
                        bot._net_mortar_ms = now_ms
                        inventory.grenades -= 1
                        self.mortar_shells.append(MortarShell(target, weapon_id="mortar", hostile=False))
                        self.add_radio(f"{bot.bot_name} MORTAR SUPPORT", (238, 203, 116), 3.0)

        for client_id, session in self.online_sessions.items():
            bot = session.get("actor")
            if bot in self.ally_bots:
                client_mapping[client_id] = self.ally_bots.index(bot)
                actor = self._controlled_actor_for(bot)
                if actor is not bot and actor in self.vehicles:
                    vehicle_mapping[client_id] = self.vehicles.index(actor)

        # Serialize state
        def serialize_soldier(s):
            session = self._remote_session_for_bot(s)
            vehicle = getattr(s, "vehicle", None)
            return {
                "x": s.rect.centerx,
                "y": s.rect.centery,
                "hp": s.hp,
                "max_hp": s.max_hp,
                "aim": s.aim_angle,
                "alive": s.alive,
                "name": s.bot_name,
                "team": getattr(s, "team", "player"),
                "pvp_team": getattr(s, "pvp_team", self._host_player_team() if s is self.player else "blue"),
                "pose": getattr(s, "weapon_pose", "rifle"),
                "weapon_mode": session.get("weapon_mode", "rifle") if session else self.weapon_mode,
                "inventory": self._inventory_to_dict(session["inventory"]) if session else self._inventory_to_dict(self.inventory),
                "vehicle_index": self.vehicles.index(vehicle) if vehicle in self.vehicles else -1,
                "moving": getattr(s, "moving", False),
                "angle": getattr(s, "angle", 0.0),
                "move_angle": getattr(s, "move_angle", 0.0),
                "shooting_flash": getattr(s, "shooting_flash", 0.0),
                "melee_flash": getattr(s, "melee_flash", 0.0),
                "anim_time": getattr(s, "anim_time", 0.0),
                "anim_state": getattr(s, "anim_state", "idle_down"),
            }

        def serialize_vehicle(v):
            return {
                "x": v.rect.centerx,
                "y": v.rect.centery,
                "hp": v.hp,
                "max_hp": v.max_hp,
                "kind": getattr(v, "kind", "sherman"),
                "faction": getattr(v, "faction", "enemy"),
                "angle": getattr(v, "angle", 0.0),
                "turret": getattr(v, "turret_angle", getattr(v, "angle", 0.0)),
                "moving": getattr(v, "moving", False),
                "shooting_flash": getattr(v, "shooting_flash", 0.0),
                "anim_time": getattr(v, "anim_time", 0.0),
                "owner_id": next((sid for sid, session in self.online_sessions.items() if getattr(session.get("actor"), "vehicle", None) is v), ""),
                "owner_team": next((session["team"] for session in self.online_sessions.values() if getattr(session.get("actor"), "vehicle", None) is v), self._host_player_team() if v is getattr(self.player, "vehicle", None) else ""),
                "alive": v.alive,
            }

        def serialize_aircraft(a):
            return {
                "x": a.rect.centerx,
                "y": a.rect.centery,
                "hp": a.hp,
                "max_hp": a.max_hp,
                "unit": getattr(a, "unit", "bomber"),
                "angle": getattr(a, "angle", 0.0),
                "alive": a.alive,
            }

        def serialize_item(item):
            return {
                "x": item.rect.centerx,
                "y": item.rect.centery,
                "kind": item.kind,
                "amount": item.amount,
            }

        boss_index = -1
        if getattr(self, "boss_vehicle", None) in self.enemy_vehicles:
            boss_index = self.enemy_vehicles.index(self.boss_vehicle)

        state = {
            "status": "playing",
            "map_id": self.current_map_id,
            "player": serialize_soldier(self.player),
            "ally_bots": [serialize_soldier(b) for b in self.ally_bots],
            "enemies": [serialize_soldier(e) for e in self.enemies],
            "enemy_vehicles": [serialize_vehicle(v) for v in self.enemy_vehicles],
            "vehicles": [serialize_vehicle(v) for v in self.vehicles],
            "enemy_aircraft": [serialize_aircraft(a) for a in self.enemy_aircraft],
            "items": [serialize_item(item) for item in self.items],
            "bullets": [
                {"x": b.pos.x, "y": b.pos.y, "rot": math.degrees(math.atan2(b.direction.y, b.direction.x))}
                for b in self.bullets
                if hasattr(b, "direction")
            ],
            "client_mapping": client_mapping,
            "vehicle_mapping": vehicle_mapping,
            "host_inventory": self._inventory_to_dict(self.inventory),
            "mission_started": self.mission_started,
            "doors_open": self.tilemap.doors_open,
            "capture": self.capture,
            "result": self.result,
            "winning_team": getattr(self, "winning_team", None),
            "result_reward": self.result_reward,
            "stats": self.stats,
            "boss_index": boss_index,
        }
        self.network_server.broadcast_state(state)

    def _sync_client(self, dt: float) -> bool:
        if not getattr(self, "network_client", None) or not self.network_client.connected:
            return False

        # Gather local inputs
        keys = pygame.key.get_pressed()
        mouse_world = self.camera.world_mouse(pygame.mouse.get_pos())
        mouse_buttons = pygame.mouse.get_pressed()
        if keys[pygame.K_1]:
            self.weapon_mode = self.equipped_primary
        elif keys[pygame.K_2]:
            self.weapon_mode = self.equipped_sidearm

        inputs = {
            "keys": {"w": keys[pygame.K_w], "a": keys[pygame.K_a], "s": keys[pygame.K_s], "d": keys[pygame.K_d]},
            "mouse_world": [mouse_world.x, mouse_world.y],
            "shoot": mouse_buttons[0],
            "grenade": keys[pygame.K_g] or mouse_buttons[2],
            "medkit": keys[pygame.K_h],
            "melee": keys[pygame.K_q],
            "mortar": keys[pygame.K_m],
            "interact": keys[pygame.K_e],
            "weapon1": keys[pygame.K_1],
            "weapon2": keys[pygame.K_2],
            "pose": self.active_weapon().animation_key,
            "weapon_mode": self.weapon_mode,
        }
        self.network_client.update_inputs(inputs)

        # Override local state with server state
        state = self.network_client.server_state
        if state.get("status") == "playing":
            def apply_soldier_anim(soldier: Soldier, payload: dict, previous_center=None) -> None:
                soldier.max_hp = payload.get("max_hp", soldier.max_hp)
                soldier.aim_angle = payload.get("aim", soldier.aim_angle)
                soldier.angle = payload.get("angle", soldier.aim_angle)
                soldier.move_angle = payload.get("move_angle", soldier.move_angle)
                soldier.team = payload.get("team", soldier.team)
                soldier.pvp_team = payload.get("pvp_team", getattr(soldier, "pvp_team", "blue"))
                soldier.weapon_pose = payload.get("pose", soldier.weapon_pose)
                soldier.shooting_flash = payload.get("shooting_flash", 0.0)
                soldier.melee_flash = payload.get("melee_flash", 0.0)
                if "anim_state" in payload and payload["anim_state"] != soldier.anim_state:
                    soldier.anim_state = payload["anim_state"]
                    soldier.anim_time = payload.get("anim_time", 0.0)
                else:
                    soldier.anim_time = payload.get("anim_time", soldier.anim_time)
                if "moving" in payload:
                    soldier.moving = payload["moving"]
                elif previous_center is not None:
                    soldier.moving = pygame.Vector2(soldier.rect.center).distance_to(previous_center) > 1
                if not payload.get("alive", True):
                    soldier.hp = 0

            if "player" in state:
                p = state["player"]
                previous_center = pygame.Vector2(self.player.rect.center)
                self.player.rect.center = (p["x"], p["y"])
                self.player.hp = p["hp"]
                apply_soldier_anim(self.player, p, previous_center)

            srv_bots = state.get("ally_bots", [])
            # Dynamically resize ally_bots list to match server
            while len(self.ally_bots) < len(srv_bots):
                bot_pos = self.player.rect.center
                new_bot = Soldier(bot_pos, is_player=False, team="player", bot_name=f"P{len(self.ally_bots)+2}")
                new_bot.player_controlled = True
                self.ally_bots.append(new_bot)
            while len(self.ally_bots) > len(srv_bots):
                self.ally_bots.pop()

            for i, b_state in enumerate(srv_bots):
                previous_center = pygame.Vector2(self.ally_bots[i].rect.center)
                self.ally_bots[i].rect.center = (b_state["x"], b_state["y"])
                self.ally_bots[i].hp = b_state["hp"]
                self.ally_bots[i].bot_name = b_state.get("name", f"P{i+2}")
                self.ally_bots[i].player_controlled = True
                apply_soldier_anim(self.ally_bots[i], b_state, previous_center)

            if "enemies" in state:
                srv_enemies = state["enemies"]
                while len(self.enemies) < len(srv_enemies):
                    new_enemy = Soldier(self.player.rect.center, is_player=False, team="enemy", bot_name="Enemy")
                    self.enemies.append(new_enemy)
                while len(self.enemies) > len(srv_enemies):
                    self.enemies.pop()
                for i, e_state in enumerate(srv_enemies):
                    previous_center = pygame.Vector2(self.enemies[i].rect.center)
                    self.enemies[i].rect.center = (e_state["x"], e_state["y"])
                    self.enemies[i].hp = e_state["hp"]
                    apply_soldier_anim(self.enemies[i], e_state, previous_center)

            def sync_tanks(target_list: list[TankVehicle], records: list[dict], faction: str) -> None:
                while len(target_list) < len(records):
                    record = records[len(target_list)]
                    target_list.append(TankVehicle((record.get("x", 0), record.get("y", 0)), record.get("kind", "sherman"), faction=faction))
                while len(target_list) > len(records):
                    target_list.pop()
                for tank, record in zip(target_list, records):
                    if getattr(tank, "kind", None) != record.get("kind", tank.kind):
                        tank.__init__((record.get("x", tank.rect.centerx), record.get("y", tank.rect.centery)), record.get("kind", "sherman"), faction=record.get("faction", faction))
                    tank.rect.center = (record["x"], record["y"])
                    tank.hp = record["hp"]
                    tank.max_hp = record.get("max_hp", tank.max_hp)
                    tank.angle = record.get("angle", tank.angle)
                    tank.turret_angle = record.get("turret", tank.turret_angle)
                    tank.faction = record.get("faction", faction)
                    tank.pvp_team = record.get("owner_team", getattr(tank, "pvp_team", "blue"))
                    tank.moving = record.get("moving", tank.moving)
                    tank.shooting_flash = record.get("shooting_flash", 0.0)
                    tank.anim_time = record.get("anim_time", tank.anim_time)
                    tank.occupied = bool(record.get("owner_id"))

            if "enemy_vehicles" in state:
                sync_tanks(self.enemy_vehicles, state["enemy_vehicles"], "enemy")
                boss_index = state.get("boss_index", -1)
                self.boss_vehicle = self.enemy_vehicles[boss_index] if 0 <= boss_index < len(self.enemy_vehicles) else None

            if "vehicles" in state:
                sync_tanks(self.vehicles, state["vehicles"], "ally")

            if "enemy_aircraft" in state:
                srv_planes = state["enemy_aircraft"]
                while len(self.enemy_aircraft) < len(srv_planes):
                    record = srv_planes[len(self.enemy_aircraft)]
                    self.enemy_aircraft.append(EnemyAircraft((record.get("x", 0), record.get("y", 0)), (record.get("x", 0), record.get("y", 0)), (record.get("x", 0), record.get("y", 0)), record.get("unit", "bomber")))
                while len(self.enemy_aircraft) > len(srv_planes):
                    self.enemy_aircraft.pop()
                for plane, record in zip(self.enemy_aircraft, srv_planes):
                    plane.unit = record.get("unit", plane.unit)
                    plane.pos.update(record["x"], record["y"])
                    plane.rect.center = plane.pos
                    plane.hp = record["hp"]
                    plane.max_hp = record.get("max_hp", plane.max_hp)
                    plane.angle = record.get("angle", plane.angle)

            if "items" in state:
                srv_items = state["items"]
                while len(self.items) < len(srv_items):
                    record = srv_items[len(self.items)]
                    self.items.append(Item((record.get("x", 0), record.get("y", 0)), record.get("kind", ITEM_AMMO), record.get("amount", 1)))
                while len(self.items) > len(srv_items):
                    self.items.pop()
                for index, record in enumerate(srv_items):
                    if self.items[index].kind != record.get("kind", self.items[index].kind):
                        self.items[index] = Item((record["x"], record["y"]), record.get("kind", ITEM_AMMO), record.get("amount", 1))
                    self.items[index].rect.center = (record["x"], record["y"])
                    self.items[index].amount = record.get("amount", self.items[index].amount)

            self.mission_started = state.get("mission_started", self.mission_started)
            if state.get("doors_open"):
                self.tilemap.open_doors()
            self.capture = state.get("capture", self.capture)
            self.result = state.get("result", self.result)
            self.winning_team = state.get("winning_team", getattr(self, "winning_team", None))
            self.result_reward = state.get("result_reward", self.result_reward)
            self.stats.update(state.get("stats", {}))

            # Use server bullets directly for rendering (DummyBullet)
            if "bullets" in state:
                self.bullets.clear()
                for b_state in state["bullets"]:
                    self.bullets.append(_DummyBullet(b_state["x"], b_state["y"], b_state["rot"]))

            # Move camera to the bot we are controlling
            client_mapping = state.get("client_mapping", {})
            my_bot_idx = client_mapping.get(self.network_client.client_id, -1)
            vehicle_mapping = state.get("vehicle_mapping", {})
            my_vehicle_idx = vehicle_mapping.get(self.network_client.client_id, -1)
            if my_bot_idx >= 0 and my_bot_idx < len(self.ally_bots):
                bot_state = srv_bots[my_bot_idx] if my_bot_idx < len(srv_bots) else {}
                if self.winning_team in {"blue", "red"} and self.result:
                    self.result = "VICTORY" if bot_state.get("pvp_team") == self.winning_team else "DEFEAT"
                self.inventory = self._inventory_from_dict(bot_state.get("inventory"))
                if 0 <= my_vehicle_idx < len(self.vehicles):
                    self.ally_bots[my_bot_idx].vehicle = self.vehicles[my_vehicle_idx]
                    self.ally_bots[my_bot_idx].rect.center = self.vehicles[my_vehicle_idx].rect.center
                    self.camera.follow(self.vehicles[my_vehicle_idx].rect, self.screen.get_size(), dt)
                else:
                    self.ally_bots[my_bot_idx].vehicle = None
                    self.camera.follow(self.ally_bots[my_bot_idx].rect, self.screen.get_size(), dt)
            else:
                # Fallback: camera follows server player position
                self.inventory = self._inventory_from_dict(state.get("host_inventory"))
                self.camera.follow(self.player.rect, self.screen.get_size(), dt)
        return True

    def update_grenades(self, dt: float) -> None:
        live_grenades = []
        for grenade in self.grenades:
            if grenade.update(dt):
                live_grenades.append(grenade)
            else:
                self.detonate_grenade(grenade.target, getattr(grenade, "owner_team", None))
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
            picked_up = False
            targets = [(self.player, self.inventory)]
            for bot in getattr(self, "ally_bots", []):
                if bot.alive and getattr(bot, "player_controlled", False):
                    session = self._remote_session_for_bot(bot)
                    targets.append((bot, session["inventory"] if session else self.inventory))
            for target, inventory in targets:
                if target.rect.colliderect(item.rect):
                    inventory.add_item(item)
                    self.stats["supplies"] += 1
                    self._play_sound("pickup")
                    self.particles.sparks(item.rect.center, 5)
                    self.add_floater(f"+{item.kind.upper()}", item.rect.center, (132, 232, 138), 0.9)
                    self.add_radio(f"SUPPLY PICKUP: {item.kind.upper()}", (132, 232, 138), 3.2)
                    picked_up = True
                    break
            if not picked_up:
                remaining.append(item)
        self.items = remaining

    def draw(self) -> None:
        if self.state == "name_input":
            self._draw_menu_background()
            title = self.big_font.render("WARFRONT COMMAND", True, (245, 232, 184))
            self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 150)))
            prompt = self.font.render("Nhập Tên Chỉ Huy Của Bạn:", True, (189, 204, 168))
            self.screen.blit(prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 250)))

            box = pygame.Rect(SCREEN_WIDTH // 2 - 150, 300, 300, 50)
            pygame.draw.rect(self.screen, (24, 30, 26), box)
            pygame.draw.rect(self.screen, (238, 203, 116), box, width=2)

            name_surf = self.font.render(self.player_name + "_", True, (255, 255, 255))
            self.screen.blit(name_surf, name_surf.get_rect(center=box.center))

            hint = self.small_font.render("Nhấn ENTER để xác nhận", True, (140, 150, 130))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 380)))

            self._draw_cursor()
            pygame.display.flip()
            return

        if self.state == "ip_input":
            self._draw_menu_background()
            title = self.font.render("VÀO PHÒNG (JOIN LOBBY)", True, (245, 232, 184))
            self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 200)))
            prompt = self.small_font.render("Nhập IP của máy chủ (Host):", True, (189, 204, 168))
            self.screen.blit(prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 250)))

            box = pygame.Rect(SCREEN_WIDTH // 2 - 150, 300, 300, 50)
            pygame.draw.rect(self.screen, (24, 30, 26), box)
            pygame.draw.rect(self.screen, (238, 203, 116), box, width=2)

            ip_surf = self.font.render(self.host_ip + "_", True, (255, 255, 255))
            self.screen.blit(ip_surf, ip_surf.get_rect(center=box.center))

            hint = self.small_font.render("Nhấn ENTER để kết nối | ESC để quay lại", True, (140, 150, 130))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 380)))

            self._draw_cursor()
            pygame.display.flip()
            return

        if self.state == "lobby":
            self._draw_menu_background()
            if getattr(self, "network_mode", "offline") == "host":
                ip_text = self.big_font.render(f"IP PHÒNG CỦA BẠN: {getattr(self, 'local_ip', '127.0.0.1')}", True, (255, 223, 128))
                self.screen.blit(ip_text, ip_text.get_rect(center=(SCREEN_WIDTH // 2, 80)))
                subtitle = self.font.render("Hãy gửi IP này cho bạn bè để họ nhập vào!", True, (189, 204, 168))
                self.screen.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 130)))
            else:
                ip_text = self.big_font.render(f"ĐANG TRONG PHÒNG: {self.host_ip}", True, (245, 232, 184))
                self.screen.blit(ip_text, ip_text.get_rect(center=(SCREEN_WIDTH // 2, 80)))

            # Draw player slots
            connected_players = []
            if self.network_client and self.network_client.connected:
                connected_players = self.network_client.server_state.get("players", [self.player_name])
            elif self.player_name:
                connected_players = [self.player_name]

            slot_start_y = 200
            for i in range(4):
                rect = pygame.Rect(SCREEN_WIDTH // 2 - 250, slot_start_y + i * 80, 500, 60)
                self._draw_3d_panel(rect, fill=(15, 21, 18), alpha=200, border=(91, 108, 83), depth=4, radius=4)

                if i < len(connected_players):
                    name = connected_players[i]
                    color = (255, 223, 128) if i == 0 else (207, 217, 184)
                else:
                    name = "Chỗ trống - chờ người chơi thật" if getattr(self, "network_mode", "offline") == "host" else "Đang chờ..."
                    color = (140, 150, 130)

                text = self.font.render(name, True, color)
                self.screen.blit(text, (rect.left + 20, rect.centery - text.get_height() // 2))

            # Draw Controls
            self.lobby_buttons.clear()
            mouse_pos = pygame.mouse.get_pos()

            if getattr(self, "network_mode", "offline") == "host":
                # Host Controls
                map_rect = pygame.Rect(SCREEN_WIDTH // 2 - 320, 560, 200, 50)
                shop_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 560, 200, 50)
                start_rect = pygame.Rect(SCREEN_WIDTH // 2 + 120, 560, 200, 50)

                # Choose map
                hover_map = map_rect.collidepoint(mouse_pos)
                self._draw_3d_button(map_rect, (45, 58, 50) if hover_map else (35, 48, 40), (87, 103, 78), active=False, depth=4)
                text = self.font.render("CHỌN MAP", True, (255, 241, 196) if hover_map else (207, 217, 184))
                self.screen.blit(text, text.get_rect(center=map_rect.center))
                self.lobby_buttons.append((map_rect, "maps"))

                # Shop
                hover_shop = shop_rect.collidepoint(mouse_pos)
                self._draw_3d_button(shop_rect, (45, 58, 50) if hover_shop else (35, 48, 40), (87, 103, 78), active=False, depth=4)
                text = self.font.render("SHOP", True, (255, 241, 196) if hover_shop else (207, 217, 184))
                self.screen.blit(text, text.get_rect(center=shop_rect.center))
                self.lobby_buttons.append((shop_rect, "shop"))

                # Start
                hover_start = start_rect.collidepoint(mouse_pos)
                self._draw_3d_button(start_rect, (65, 88, 70) if hover_start else (55, 78, 60), (107, 123, 98), active=False, depth=4)
                text = self.font.render("BẮT ĐẦU", True, (255, 255, 255) if hover_start else (223, 224, 198))
                self.screen.blit(text, text.get_rect(center=start_rect.center))
                self.lobby_buttons.append((start_rect, "start"))

                # Show currently selected map
                map_title = MAPS.get(self.current_map_id, {}).get("title", "Unknown Map")
                map_info = self.small_font.render(f"Map hiện tại: {map_title}", True, (189, 204, 168))
                self.screen.blit(map_info, map_info.get_rect(center=(SCREEN_WIDTH // 2, 530)))
            else:
                # Client Controls
                shop_rect = pygame.Rect(SCREEN_WIDTH // 2 - 220, 560, 200, 50)
                start_rect = pygame.Rect(SCREEN_WIDTH // 2 + 20, 560, 200, 50)

                # Shop
                hover_shop = shop_rect.collidepoint(mouse_pos)
                self._draw_3d_button(shop_rect, (45, 58, 50) if hover_shop else (35, 48, 40), (87, 103, 78), active=False, depth=4)
                text = self.font.render("SHOP", True, (255, 241, 196) if hover_shop else (207, 217, 184))
                self.screen.blit(text, text.get_rect(center=shop_rect.center))
                self.lobby_buttons.append((shop_rect, "shop"))

                # Waiting
                self._draw_3d_button(start_rect, (35, 48, 40), (87, 103, 78), active=False, depth=4)
                text = self.font.render("ĐANG CHỜ CHỦ PHÒNG...", True, (140, 150, 130))
                self.screen.blit(text, text.get_rect(center=start_rect.center))

            hint = self.small_font.render("ESC để rời phòng", True, (140, 150, 130))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 640)))

            self._draw_cursor()
            pygame.display.flip()
            return

        if self.state == "pvp_menu":
            self._draw_menu_background()
            title = self.big_font.render("CHỌN CHẾ ĐỘ PVP", True, (245, 232, 184))
            self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 150)))

            options = [
                ("SOLO VS BOT (DỄ)", "Phù hợp để làm quen. Bot phản xạ chậm và máu giấy."),
                ("SOLO VS BOT (THƯỜNG)", "Đấu tay đôi công bằng. Chỉ số ngang bằng với bạn."),
                ("SOLO VS BOT (KHÓ)", "Siêu Bot có khả năng né đạn và ngắm bắn cực chuẩn."),
                ("ONLINE (2v2)", "Tạo phòng và mời bạn bè tham gia đấu trường 2v2.")
            ]

            for idx, (label, desc) in enumerate(options):
                rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, 240 + idx * 70, 400, 50)
                selected = getattr(self, "pvp_selection", 0) == idx
                self._draw_3d_button(rect, (129, 70, 48) if selected else (35, 48, 40), (238, 203, 116) if selected else (87, 103, 78), active=selected, depth=4)
                if selected:
                    marker = pygame.Rect(rect.left + 8, rect.top + 8, 4, rect.height - 16)
                    pygame.draw.rect(self.screen, (255, 223, 128), marker, border_radius=2)
                text = self.font.render(label, True, (255, 241, 196) if selected else (223, 224, 198))
                self.screen.blit(text, text.get_rect(center=rect.center))

                if selected:
                    desc_text = self.small_font.render(desc, True, (207, 217, 184))
                    self.screen.blit(desc_text, desc_text.get_rect(center=(SCREEN_WIDTH // 2, 540)))

            hint = self.small_font.render("Nhấn ENTER để chọn | ESC để quay lại", True, (140, 150, 130))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 600)))

            self._draw_cursor()
            pygame.display.flip()
            return

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
        actors = [*self.enemies, *self.enemy_vehicles, *self.vehicles, *self.enemy_aircraft, *getattr(self, "ally_bots", [])]
        if not getattr(self.player, "vehicle", None):
            actors.append(self.player)
        for entity in sorted(actors, key=lambda item: item.rect.centery):
            entity.draw(self.screen, self.camera)
        self.particles.draw(self.screen, self.camera)
        self._draw_floaters()
        self._draw_objective_pointer()

        if self.state == "cutscene":
            self._draw_cutscene()
        else:
            self._draw_ui()

        self._draw_cursor()
        pygame.display.flip()

    def _draw_cutscene(self) -> None:
        chapter = CHAPTERS_BY_MAP.get(self.current_map_id)
        if not chapter or not getattr(chapter, "dialogues", ()):
            self.state = "play"
            return

        # Draw cinematic letterbox
        bar_height = 80
        pygame.draw.rect(self.screen, (10, 14, 12), (0, 0, SCREEN_WIDTH, bar_height))
        pygame.draw.rect(self.screen, (10, 14, 12), (0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height))

        if self.cutscene_index < len(chapter.dialogues):
            speaker, text = chapter.dialogues[self.cutscene_index]

            # Typewriter effect (reveal ~20 characters per second)
            reveal_count = int(self.cutscene_timer * 20)
            displayed_text = text[:reveal_count]

            speaker_color = (238, 203, 116) if speaker != "HQ COMMAND" else (189, 204, 168)
            speaker_surf = self.font.render(speaker + ":", True, speaker_color)
            self.screen.blit(speaker_surf, (40, SCREEN_HEIGHT - bar_height + 15))

            text_surf = self.small_font.render(displayed_text, True, (245, 232, 184))
            self.screen.blit(text_surf, (40 + speaker_surf.get_width() + 10, SCREEN_HEIGHT - bar_height + 18))

            hint_surf = self.font.render("Nhấn SPACE để tiếp tục", True, (80, 100, 80))
            self.screen.blit(hint_surf, hint_surf.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 10)))

            # Auto-advance if fully typed and waited a bit
            if reveal_count > len(text) + 60: # about 3 seconds after typing finishes
                self.cutscene_index += 1
                self.cutscene_timer = 0.0
                if self.cutscene_index >= len(chapter.dialogues):
                    self.state = "play"
        else:
            self.state = "play"

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

        if getattr(self, "previous_state", "title") == "lobby":
            # Shrink play button and add back-to-lobby button
            play_rect = pygame.Rect(panel.left + 24, panel.bottom - 70, (panel.width - 56) // 2, 46)
            lobby_rect = pygame.Rect(play_rect.right + 8, panel.bottom - 70, (panel.width - 56) // 2, 46)
            hot_lobby = lobby_rect.collidepoint(pygame.mouse.get_pos())
            self._draw_3d_button(lobby_rect, (35, 48, 40) if not hot_lobby else (55, 70, 60), (87, 103, 78), active=True, hot=hot_lobby, depth=6)
            back_lbl = self.font.render("◀ VỀ PHÒNG CHỜ", True, (255, 240, 190))
            self.screen.blit(back_lbl, back_lbl.get_rect(center=lobby_rect.center))
            self.menu_buttons.append((lobby_rect, "back_lobby"))

        self._draw_3d_button(
            play_rect,
            (153, 61, 48),
            (238, 203, 116),
            active=True,
            hot=play_rect.collidepoint(pygame.mouse.get_pos()),
            depth=6,
        )
        play_label = "BẮT ĐẦU" if getattr(self, "previous_state", "title") == "lobby" else "START MISSION"
        play = self.font.render(play_label, True, (255, 240, 190))
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
        equipped = self.small_font.render(f"Đang dùng: {weapon_name(self.equipped_primary)} / {weapon_name(self.equipped_sidearm)}", True, (189, 204, 168))
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

            price = "SỞ HỮU" if owned and item.max_purchases == 1 else ("TỐI ĐA" if maxed else f"{item.cost}c")
            icon = self._shop_icon(item_id)
            if icon is not None:
                self.screen.blit(icon, icon.get_rect(center=(rect.left + 27, rect.centery)))
                text_x = rect.left + 50
            else:
                text_x = rect.left + 16

            level = f" Lv {bought_count}/{item.max_purchases}" if item.max_purchases and item.max_purchases > 1 else ""
            name_text = f"{item.name}{level} - {price}"
            if not can_buy and not owned:
                name_text = f"[KHOÁ] {name_text}"

            name = self.small_font.render(self._fit_text(name_text, self.small_font, rect.right - text_x - 8), True, (245, 232, 184) if can_buy or owned else (140, 140, 130))
            desc = self.small_font.render(self._fit_text(self._shop_description(item_id, item.description), self.small_font, rect.right - text_x - 8), True, (200, 207, 180))
            self.screen.blit(name, (text_x, rect.top + 4))
            self.screen.blit(desc, (text_x, rect.top + 28))
            self.menu_buttons.append((rect, f"equip:{item_id}" if owned and item.kind == "weapon" else f"buy:{item_id}"))

        nav_y = panel.bottom - 44
        page_label = self.small_font.render(f"Trang {self.shop_page + 1}/{pages}", True, (238, 203, 116))
        self.screen.blit(page_label, page_label.get_rect(center=(panel.centerx, nav_y + 16)))
        if self.shop_page > 0:
            prev_rect = pygame.Rect(panel.left + 24, nav_y, 86, 32)
            self._draw_3d_button(prev_rect, (35, 48, 40), (226, 196, 82), hot=prev_rect.collidepoint(pygame.mouse.get_pos()), depth=4)
            self.screen.blit(self.small_font.render("< Trước", True, (245, 232, 184)), (prev_rect.left + 15, prev_rect.top + 7))
            self.menu_buttons.append((prev_rect, f"shop_page:{self.shop_page - 1}"))
        if self.shop_page < pages - 1:
            next_rect = pygame.Rect(panel.right - 110, nav_y, 86, 32)
            self._draw_3d_button(next_rect, (35, 48, 40), (226, 196, 82), hot=next_rect.collidepoint(pygame.mouse.get_pos()), depth=4)
            self.screen.blit(self.small_font.render("Tiếp >", True, (245, 232, 184)), (next_rect.left + 14, next_rect.top + 7))
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
        pressed = hot and pygame.mouse.get_pressed()[0]
        actual_depth = 1 if pressed else depth
        lift = -(depth - 1) if pressed else (2 if hot else 0)
        body = rect.move(0, -lift)

        shadow = pygame.Surface((body.width, body.height + actual_depth), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), pygame.Rect(0, actual_depth, body.width, body.height), border_radius=radius)
        self.screen.blit(shadow, body)

        if active or hot:
            pulse = 35 + int(20 * math.sin(pygame.time.get_ticks() / 150))
            glow = pygame.Surface(body.inflate(16, 16).size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*border, pulse if active else 30), glow.get_rect(), border_radius=radius + 4)
            self.screen.blit(glow, body.inflate(16, 16))

        top = tuple(min(255, c + (35 if active or hot else 20)) for c in fill)
        bottom = tuple(max(0, c - 35) for c in fill)
        pygame.draw.rect(self.screen, bottom, body.move(0, actual_depth), border_radius=radius)
        pygame.draw.rect(self.screen, fill, body, border_radius=radius)

        # Glassy highlight
        highlight_rect = body.inflate(-8, -body.height // 2).move(0, 4)
        highlight = pygame.Surface(highlight_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(highlight, (*top, 140), highlight.get_rect(), border_radius=max(2, radius - 2))
        self.screen.blit(highlight, highlight_rect)

        pygame.draw.line(self.screen, tuple(min(255, c + 65) for c in fill), (body.left + 8, body.top + 2), (body.right - 8, body.top + 2), 1)
        pygame.draw.line(self.screen, tuple(max(0, c - 55) for c in fill), (body.left + 8, body.bottom - 2), (body.right - 8, body.bottom - 2), 2)
        pygame.draw.rect(self.screen, border, body, 2 if active else 1, border_radius=radius)

    def _draw_3d_panel(
        self,
        rect: pygame.Rect,
        *,
        fill: tuple[int, int, int] = (16, 21, 18),
        alpha: int = 190,
        border: tuple[int, int, int] = (78, 92, 73),
        depth: int = 6,
        radius: int = 8,
    ) -> None:
        shadow = pygame.Surface((rect.width + 12, rect.height + depth + 12), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 120), pygame.Rect(6, depth + 6, rect.width, rect.height), border_radius=radius)
        self.screen.blit(shadow, (rect.left - 6, rect.top - 6))

        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (*fill, alpha), bg.get_rect(), border_radius=radius)
        # Inner glow / Glass effect
        pygame.draw.rect(bg, (*tuple(min(255, c + 40) for c in fill), 30), bg.get_rect(), border_radius=radius)
        self.screen.blit(bg, rect)

        highlight = pygame.Rect(rect.left + 4, rect.top + 3, rect.width - 8, max(5, rect.height // 3))
        hi = pygame.Surface(highlight.size, pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 230, 25), hi.get_rect(), border_radius=max(2, radius - 2))
        self.screen.blit(hi, highlight)

        pygame.draw.line(self.screen, tuple(min(255, c + 45) for c in border), (rect.left + 8, rect.top + 2), (rect.right - 8, rect.top + 2), 1)
        pygame.draw.line(self.screen, tuple(max(0, c - 50) for c in border), (rect.left + 8, rect.bottom - 2), (rect.right - 8, rect.bottom - 2), 2)
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

        if getattr(self, "boss_vehicle", None) and self.boss_vehicle.alive:
            bar_w = 400
            bar_h = 24
            bar_rect = pygame.Rect((SCREEN_WIDTH - bar_w) // 2, 40, bar_w, bar_h)
            pygame.draw.rect(self.screen, (35, 30, 28), bar_rect, border_radius=4)
            pygame.draw.rect(self.screen, (78, 92, 73), bar_rect, 2, border_radius=4)
            fill_w = int(bar_w * max(0, self.boss_vehicle.hp) / self.boss_vehicle.max_hp)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (220, 70, 54), pygame.Rect(bar_rect.left, bar_rect.top, fill_w, bar_h), border_radius=4)
            title = self.font.render("SIÊU TĂNG HẠNG NẶNG (BOSS)", True, (255, 184, 150))
            self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 25)))
        vehicle_hint = "E: lên/xuống xe   " if self.vehicles else ""
        door_hint = "E: mở cổng an toàn   " if not self.tilemap.doors_open else ""
        objective = "Mở cổng để bắt đầu" if not self.mission_started else "Tiêu diệt địch và chiếm cứ điểm"
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
