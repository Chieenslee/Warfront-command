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
    def __init__(self, pos, is_player=False, tank=False):
        self.is_player = is_player
        self.tank = tank
        self.unit_kind = "player" if is_player else ("light_tank" if tank else "rifleman")
        self.stats = UNIT_STATS[self.unit_kind]
        self.rect = pygame.Rect(pos[0], pos[1], 32 if not tank else 46, 36 if not tank else 42)
        self.hp = self.stats.hp
        self.max_hp = self.hp
        self.armor = self.stats.armor
        self.damage_amount = self.stats.damage
        self.weapon_range = self.stats.range
        self.speed = self.stats.speed
        self.reload = 0.0
        self.flash = 0.0
        self.angle = 0.0
        self.wander = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        self.think_time = random.uniform(0.5, 1.5)
        self.anim_time = random.uniform(0.0, 1.0)
        self.moving = False
        self.move_angle = 0.0
        self.shooting_flash = 0.0
        self.melee_flash = 0.0
        self.weapon_pose = "rifle"
        self.dead_time = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def damage(self, amount: int, armor_piercing: int = 0) -> int:
        mitigation = max(0, self.armor - armor_piercing)
        actual = max(1, int(amount) - mitigation)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.dead_time = 0.45 if not self.tank else 0.75
        self.flash = 0.12
        return actual

    def update_player(self, dt: float, keys, mouse_world, tilemap) -> None:
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
        if self.moving and self.shooting_flash <= 0 and self.melee_flash <= 0:
            self.angle = self.move_angle
        elif aim.length_squared():
            self.angle = math.degrees(math.atan2(aim.y, aim.x))
        self.reload = max(0.0, self.reload - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shooting_flash = max(0.0, self.shooting_flash - dt)
        self.melee_flash = max(0.0, self.melee_flash - dt)
        self.anim_time += dt

    def update_enemy(self, dt: float, player, tilemap, path: list[tuple[int, int]] | None = None) -> list[Bullet]:
        bullets: list[Bullet] = []
        self.think_time -= dt
        to_player = pygame.Vector2(player.rect.center) - pygame.Vector2(self.rect.center)
        distance = to_player.length()
        has_los = tilemap.has_line_of_sight(self.rect.center, player.rect.center)

        if distance < 520 and (not has_los or distance > self.weapon_range * 0.72) and path and len(path) > 1:
            target_index = 1
            current_tile_center = tilemap.tile_center(path[target_index])
            if pygame.Vector2(self.rect.center).distance_to(current_tile_center) < 10 and len(path) > 2:
                target_index = 2
            step = tilemap.tile_center(path[target_index]) - pygame.Vector2(self.rect.center)
            self.wander = step.normalize() if step.length_squared() else pygame.Vector2()
        elif has_los and distance < self.weapon_range * 0.85:
            self.wander = pygame.Vector2()
        elif self.think_time <= 0:
            self.think_time = random.uniform(0.4, 1.0)
            if distance < 520:
                self.wander = pygame.Vector2()
            else:
                self.wander = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))

        speed = self.speed
        self.moving = False
        if self.wander.length_squared():
            self.move_angle = math.degrees(math.atan2(self.wander.y, self.wander.x))
            before = self.rect.topleft
            self.rect = move_with_collision(self.rect, self.wander.normalize() * speed * dt, tilemap)
            self.moving = self.rect.topleft != before

        if distance and (not self.moving or self.shooting_flash > 0):
            self.angle = math.degrees(math.atan2(to_player.y, to_player.x))
        elif self.moving:
            self.angle = self.move_angle
        self.reload = max(0.0, self.reload - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shooting_flash = max(0.0, self.shooting_flash - dt)
        self.melee_flash = max(0.0, self.melee_flash - dt)
        self.anim_time += dt
        if has_los and distance < self.weapon_range and self.reload <= 0:
            self.reload = 1.2 if self.tank else 0.85
            if distance:
                self.angle = math.degrees(math.atan2(to_player.y, to_player.x))
            self.shooting_flash = 0.12
            bullets.append(Bullet(self.rect.center, to_player, friendly=False, damage=self.damage_amount))
        return bullets

    def shoot(self, target) -> Bullet | None:
        if self.reload > 0:
            return None
        direction = pygame.Vector2(target) - pygame.Vector2(self.rect.center)
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

        if self.flash > 0:
            flash = pygame.Surface(sprite_rect.size, pygame.SRCALPHA)
            flash.fill((255, 238, 190, 70))
            screen.blit(flash, sprite_rect)

        if self.shooting_flash > 0:
            barrel = pygame.Vector2(math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle)))
            muzzle = pygame.Vector2(view.center) + barrel * (34 if self.tank else 24)
            pygame.draw.circle(screen, (248, 197, 82), muzzle, 8 if self.tank else 5)
            pygame.draw.circle(screen, (255, 238, 190), muzzle, 4 if self.tank else 3)

        hp_w = max(view.width, 44)
        hp_rect = pygame.Rect(view.centerx - hp_w // 2, sprite_rect.top - 8, hp_w, 5)
        pygame.draw.rect(screen, (35, 30, 28), hp_rect)
        hp_rect.width = int(hp_w * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(screen, (77, 176, 88) if self.is_player else (204, 73, 57), hp_rect)

    def _current_sprite(self) -> pygame.Surface:
        assets = get_assets()
        if self.tank:
            indices = self._tank_indices()
            frame = indices[int(self.anim_time * 8) % len(indices)]
            sprite = assets.frame("m4_sherman", frame, 70)
            return pygame.transform.flip(sprite, True, False) if self._direction_bucket() == 3 else sprite

        group = "allied_soldier" if self.is_player else "axis_soldier"
        indices = self._soldier_indices()
        frame = indices[int(self.anim_time * (9 if self.moving else 5)) % len(indices)]
        sprite = assets.frame(group, frame, 70)
        return pygame.transform.flip(sprite, True, False) if self._direction_bucket() == 3 else sprite

    def _direction_bucket(self) -> int:
        angle = self.angle % 360
        if 45 <= angle < 135:
            return 2  # down
        if 135 <= angle < 225:
            return 3  # left
        if 225 <= angle < 315:
            return 0  # up
        return 1  # right

    def _soldier_indices(self) -> list[int]:
        bucket = self._direction_bucket()
        if not self.alive:
            return get_soldier_frames("allied" if self.is_player else "axis", "downed")
        faction = "allied" if self.is_player else "axis"
        if self.melee_flash > 0:
            return {
                0: get_soldier_frames(faction, "melee", "up"),
                1: get_soldier_frames(faction, "melee", "side"),
                2: get_soldier_frames(faction, "melee", "down"),
                3: get_soldier_frames(faction, "melee", "side"),
            }[bucket]
        if self.shooting_flash > 0:
            return {
                0: get_soldier_frames(faction, "fire", "up"),
                1: get_soldier_frames(faction, "fire", "side"),
                2: get_soldier_frames(faction, "fire", "down"),
                3: get_soldier_frames(faction, "fire", "side"),
            }[bucket]
        if self.moving:
            return {
                0: get_soldier_frames(faction, "walk", "up"),
                1: get_soldier_frames(faction, "walk", "side"),
                2: get_soldier_frames(faction, "walk", "down"),
                3: get_soldier_frames(faction, "walk", "side"),
            }[bucket]
        if self.is_player and self.weapon_pose in {"rifle", "sniper"}:
            return {
                0: get_soldier_frames(faction, "rifle", "up"),
                1: get_soldier_frames(faction, "rifle", "side"),
                2: get_soldier_frames(faction, "rifle", "down"),
                3: get_soldier_frames(faction, "rifle", "side"),
            }[bucket]
        if self.is_player and self.weapon_pose == "pistol":
            return {
                0: get_soldier_frames(faction, "utility", "up"),
                1: get_soldier_frames(faction, "utility", "side"),
                2: get_soldier_frames(faction, "utility", "down"),
                3: get_soldier_frames(faction, "utility", "side"),
            }[bucket]
        return {
            0: get_soldier_frames(faction, "idle", "up"),
            1: get_soldier_frames(faction, "idle", "side"),
            2: get_soldier_frames(faction, "idle", "down"),
            3: get_soldier_frames(faction, "idle", "side"),
        }[bucket]

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
