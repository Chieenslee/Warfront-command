import math
import random

import pygame

from warfront.assets.loader import get_assets
from warfront.config import COLORS
from warfront.entities.animations import get_soldier_frames, get_tank_frames
from warfront.entities.projectile import Bullet
from warfront.systems.balance import UNIT_STATS


def move_with_collision(rect: pygame.Rect, delta: pygame.Vector2, tilemap) -> pygame.Rect:
    moved = rect.copy()
    moved.x += int(delta.x)
    if tilemap.blocked(moved):
        moved.x = rect.x
    moved.y += int(delta.y)
    if tilemap.blocked(moved):
        moved.y = rect.y
    return moved


class Soldier:
    def __init__(self, pos, is_player=False, tank=False, team=None, bot_name=None, difficulty="normal"):
        self.is_player = is_player
        self.bot_name = bot_name
        self.team = team if team else ("player" if is_player else "enemy")
        self.tank = tank
        self.unit_kind = "player" if is_player else ("light_tank" if tank else "rifleman")
        self.stats = UNIT_STATS[self.unit_kind]
        self.rect = pygame.Rect(pos[0], pos[1], 32 if not tank else 46, 36 if not tank else 42)
        
        self.difficulty = difficulty
        hp_mult = 0.6 if difficulty == "easy" else (1.5 if difficulty == "hard" else 1.0)
        dmg_mult = 0.5 if difficulty == "easy" else (1.3 if difficulty == "hard" else 1.0)
        
        self.hp = int(self.stats.hp * hp_mult)
        self.max_hp = self.hp
        self.armor = self.stats.armor
        self.damage_amount = int(self.stats.damage * dmg_mult)
        self.weapon_range = self.stats.range
        self.speed = self.stats.speed
        self.reload = 0.0
        self.flash = 0.0
        self.angle = 0.0
        self.aim_angle = 0.0
        self.wander = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        self.think_time = random.uniform(0.5, 1.5)
        self.anim_time = random.uniform(0.0, 1.0)
        self.anim_state = "idle_down"
        self.moving = False
        self.move_angle = 0.0
        self.shooting_flash = 0.0
        self.melee_flash = 0.0
        self.weapon_pose = "rifle"
        self.dead_time = 0.0
        self.player_controlled = False  # True when a network client is driving this bot

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def damage(self, amount: int, armor_piercing: int = 0) -> int:
        mitigation = max(0, self.armor - armor_piercing)
        actual = max(1, int(amount) - mitigation)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.dead_time = 0.45 if not self.tank else 0.75
            self.moving = False
            self.shooting_flash = 0.0
            self.melee_flash = 0.0
        self.flash = 0.12
        return actual

    def update_player(self, dt: float, keys, mouse_world, tilemap) -> None:
        if not self.alive:
            self._tick_timers(dt)
            return

        direction = pygame.Vector2(
            int(keys[pygame.K_d]) - int(keys[pygame.K_a]),
            int(keys[pygame.K_s]) - int(keys[pygame.K_w]),
        )
        if direction.length_squared():
            direction = direction.normalize()
        self.moving = direction.length_squared() > 0
        self.rect = move_with_collision(self.rect, direction * self.speed * dt, tilemap)
        if self.moving:
            self.move_angle = math.degrees(math.atan2(direction.y, direction.x))
        aim = pygame.Vector2(mouse_world) - pygame.Vector2(self.rect.center)
        if aim.length_squared():
            self.aim_angle = math.degrees(math.atan2(aim.y, aim.x))
        if self.shooting_flash > 0 or self.melee_flash > 0:
            self.angle = self.aim_angle
        elif self.moving:
            self.angle = self.move_angle
        elif aim.length_squared():
            self.angle = self.aim_angle
        self._tick_timers(dt)

    def get_nearest_target(self, targets: list):
        nearest = None
        min_dist = float('inf')
        for t in targets:
            if t.alive:
                dist = pygame.Vector2(self.rect.center).distance_to(t.rect.center)
                if dist < min_dist:
                    min_dist = dist
                    nearest = t
        return nearest, min_dist

    def update_bot(self, dt: float, enemies: list, follow_target, tilemap, path: list[tuple[int, int]] | None = None) -> list[Bullet]:
        bullets: list[Bullet] = []
        if not self.alive:
            self.moving = False
            self._tick_timers(dt)
            return bullets

        self.think_time -= dt

        if not getattr(self, "player_controlled", False):
            # ── Normal AI movement logic ──────────────────────────────────────
            target, distance = self.get_nearest_target(enemies)
            
            has_los = False
            to_target = pygame.Vector2()
            if target:
                to_target = pygame.Vector2(target.rect.center) - pygame.Vector2(self.rect.center)
                has_los = tilemap.has_line_of_sight(self.rect.center, target.rect.center)
                
            follow_dist = float('inf')
            if follow_target and follow_target.alive:
                follow_dist = pygame.Vector2(self.rect.center).distance_to(follow_target.rect.center)

            # Movement logic
            if getattr(self, "difficulty", "normal") == "hard" and target and has_los and distance < 450:
                if self.think_time <= 0:
                    self.think_time = random.uniform(0.3, 0.7)
                    dodge_dir = random.choice([-1, 1])
                    perp = pygame.Vector2(-to_target.y, to_target.x).normalize()
                    self.wander = (perp * dodge_dir + to_target.normalize() * random.uniform(-0.4, 0.2)).normalize()
            elif target and distance < 520 and (not has_los or distance > self.weapon_range * 0.72) and path and len(path) > 1:
                target_index = 1
                current_tile_center = tilemap.tile_center(path[target_index])
                if pygame.Vector2(self.rect.center).distance_to(current_tile_center) < 10 and len(path) > 2:
                    target_index = 2
                step = tilemap.tile_center(path[target_index]) - pygame.Vector2(self.rect.center)
                self.wander = step.normalize() if step.length_squared() else pygame.Vector2()
            elif target and has_los and distance < self.weapon_range * 0.85 and getattr(self, "difficulty", "normal") != "hard":
                self.wander = pygame.Vector2()
            elif follow_target and follow_dist > 150:
                step = pygame.Vector2(follow_target.rect.center) - pygame.Vector2(self.rect.center)
                self.wander = step.normalize() if step.length_squared() else pygame.Vector2()
            elif self.think_time <= 0:
                self.think_time = random.uniform(0.4, 1.0)
                if target and distance < 520:
                    self.wander = pygame.Vector2()
                else:
                    self.wander = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

            # Aim logic
            if target and distance < 600:
                target_angle = math.degrees(math.atan2(to_target.y, to_target.x))
                diff = (target_angle - self.aim_angle + 180) % 360 - 180
                
                diff_level = getattr(self, "difficulty", "normal")
                aim_speed = 720 * dt if diff_level == "hard" else (270 * dt if diff_level == "normal" else 120 * dt)
                
                if abs(diff) <= aim_speed:
                    self.aim_angle = target_angle
                else:
                    self.aim_angle += aim_speed if diff > 0 else -aim_speed
            elif self.moving:
                self.aim_angle = self.move_angle

            # Shoot logic (AI)
            if target and has_los and distance < self.weapon_range and self.reload <= 0:
                self.reload = 1.2 if self.tank else 0.85
                if distance:
                    self.angle = self.aim_angle
                self.shooting_flash = 0.12
                friendly = self.team == "player"
                bullets.append(Bullet(self.rect.center, to_target, friendly=friendly, damage=self.damage_amount))
        else:
            # ── Player-controlled: AI replaced by network input ───────────────
            # wander and aim_angle are already set by _sync_host from client input
            target = None
            has_los = False
            to_target = pygame.Vector2()

        # ── Shared: physics movement ──────────────────────────────────────────
        speed = self.speed
        self.moving = False
        if self.wander.length_squared():
            self.move_angle = math.degrees(math.atan2(self.wander.y, self.wander.x))
            before = self.rect.topleft
            self.rect = move_with_collision(self.rect, self.wander.normalize() * speed * dt, tilemap)
            self.moving = self.rect.topleft != before

        if self.shooting_flash > 0 or self.melee_flash > 0:
            self.angle = self.aim_angle
        elif self.moving:
            self.angle = self.move_angle
        elif getattr(self, "player_controlled", False):
            self.angle = self.aim_angle
        elif not getattr(self, "player_controlled", False) and target and has_los:
            self.angle = self.aim_angle
            
        self._tick_timers(dt)
        return bullets

    def update_enemy(self, dt: float, player, tilemap, path: list[tuple[int, int]] | None = None) -> list[Bullet]:
        """Legacy wrapper: enemies target the player directly."""
        return self.update_bot(dt, [player], follow_target=None, tilemap=tilemap, path=path)

    def shoot(self, target) -> Bullet | None:
        if self.reload > 0 or self.melee_flash > 0 or not self.alive:
            return None
        direction = pygame.Vector2(target) - pygame.Vector2(self.rect.center)
        if not direction.length_squared():
            return None
        self.aim_angle = math.degrees(math.atan2(direction.y, direction.x))
        self.angle = self.aim_angle
        self.reload = 0.18
        self.shooting_flash = 0.08
        return Bullet(self.rect.center, direction, friendly=True, damage=self.damage_amount, armor_piercing=8)

    def draw(self, screen: pygame.Surface, camera) -> None:
        view = camera.apply(self.rect)
        sprite = self._current_sprite()
        sprite_rect = sprite.get_rect(midbottom=(view.centerx, view.bottom + 10))

        shadow = pygame.Surface((sprite_rect.width, max(8, sprite_rect.height // 5)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 72), shadow.get_rect())
        screen.blit(shadow, shadow.get_rect(center=(sprite_rect.centerx + 2, sprite_rect.bottom - 8)))
        screen.blit(sprite, sprite_rect)

        if self.alive and self.flash > 0:
            flash = pygame.Surface(sprite_rect.size, pygame.SRCALPHA)
            flash.fill((255, 238, 190, 70))
            screen.blit(flash, sprite_rect)

        if self.alive and self.tank and self.shooting_flash > 0:
            barrel = pygame.Vector2(math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle)))
            muzzle = pygame.Vector2(view.center) + barrel * (34 if self.tank else 24)
            pygame.draw.circle(screen, (248, 197, 82), muzzle, 8 if self.tank else 5)
            pygame.draw.circle(screen, (255, 238, 190), muzzle, 4 if self.tank else 3)

        if not self.alive:
            return

        hp_w = max(view.width, 44)
        hp_rect = pygame.Rect(view.centerx - hp_w // 2, sprite_rect.top - 8, hp_w, 5)
        pygame.draw.rect(screen, (35, 30, 28), hp_rect)
        hp_rect.width = int(hp_w * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(screen, (77, 176, 88) if self.team == "player" else (204, 73, 57), hp_rect)
        
        if getattr(self, "bot_name", None):
            font = pygame.font.SysFont("consolas", 12)
            name_text = font.render(self.bot_name, True, (245, 232, 184))
            name_rect = name_text.get_rect(center=(view.centerx, sprite_rect.top - 16))
            
            # Simple shadow for text
            shadow_text = font.render(self.bot_name, True, (20, 20, 18))
            screen.blit(shadow_text, (name_rect.x + 1, name_rect.y + 1))
            screen.blit(name_text, name_rect)

    def _current_sprite(self) -> pygame.Surface:
        assets = get_assets()
        if self.tank:
            indices = self._tank_indices()
            frame = indices[int(self.anim_time * 8) % len(indices)]
            sprite = assets.frame("m4_sherman", frame, 70)
            return pygame.transform.flip(sprite, True, False) if self._direction_bucket() == 3 else sprite

        group = "allied_soldier" if self.team == "player" else "axis_soldier"
        state, indices = self._soldier_animation()
        if state != self.anim_state:
            self.anim_state = state
            self.anim_time = 0.0
        if state == "downed":
            frame_index = min(int(self.anim_time * 8), len(indices) - 1)
        else:
            frame_index = int(self.anim_time * self._anim_fps()) % len(indices)
        frame = indices[frame_index]
        sprite = assets.frame(group, frame, 70)
        return pygame.transform.flip(sprite, True, False) if self._direction_bucket() == 3 else sprite

    def _tick_timers(self, dt: float) -> None:
        self.reload = max(0.0, self.reload - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shooting_flash = max(0.0, self.shooting_flash - dt)
        self.melee_flash = max(0.0, self.melee_flash - dt)
        self.anim_time += dt

    def _direction_bucket(self) -> int:
        angle = self.angle % 360
        if 45 <= angle < 135:
            return 2  # down
        if 135 <= angle < 225:
            return 3  # left
        if 225 <= angle < 315:
            return 0  # up
        return 1  # right

    def _direction_name(self) -> str:
        bucket = self._direction_bucket()
        return {0: "up", 1: "side", 2: "down", 3: "side"}[bucket]

    def _anim_fps(self) -> float:
        if self.shooting_flash > 0 or self.melee_flash > 0:
            return 16.0
        return 9.0 if self.moving else 5.0

    def _soldier_animation(self) -> tuple[str, list[int]]:
        direction = self._direction_name()
        faction = "allied" if self.team == "player" else "axis"
        if not self.alive:
            return "downed", get_soldier_frames(faction, "downed")
        if self.melee_flash > 0:
            return f"melee_{direction}", get_soldier_frames(faction, "melee_bash", direction)
        if self.shooting_flash > 0:
            return f"shoot_{direction}", get_soldier_frames(faction, "shoot", direction)
        if self.moving:
            return f"run_{direction}", get_soldier_frames(faction, "run", direction)
        if self.team == "player" and self.weapon_pose in {"rifle", "sniper"}:
            return f"ready_{direction}", get_soldier_frames(faction, "rifle", direction)
        if self.team == "player" and self.weapon_pose == "pistol":
            return f"pistol_{direction}", get_soldier_frames(faction, "utility", direction)
        return f"idle_{direction}", get_soldier_frames(faction, "idle", direction)

    def _tank_indices(self) -> list[int]:
        bucket = self._direction_bucket()
        if not self.alive:
            return get_tank_frames("wreck")
        action = "fire" if self.shooting_flash > 0 else "move"
        return {
            0: get_tank_frames(action, "up"),
            1: get_tank_frames(action, "side"),
            2: get_tank_frames(action, "down"),
            3: get_tank_frames(action, "side"),
        }[bucket]
