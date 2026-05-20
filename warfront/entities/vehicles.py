from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from warfront.assets.loader import get_assets
from warfront.config import COLORS
from warfront.entities.animations import get_tank_frames
from warfront.entities.projectile import Bullet
from warfront.systems.balance import UNIT_STATS


TANK_ANIMS = {
    "side": [26, 27, 28, 29, 30, 31, 32, 33],
    "front": [75, 76, 77, 78, 79, 80, 81, 82],
    "back": [88, 89, 90, 91, 92, 93, 94, 95],
    "wreck": [155, 156, 157, 158, 159],
}


@dataclass(frozen=True)
class VehicleStats:
    size: tuple[int, int]
    max_hp: int
    armor: int
    speed: float
    damage: int
    bullet_speed: float
    reload_time: float
    projectile_life: float
    sprite_height: int


TANK_STATS: dict[str, VehicleStats] = {
    "light_tank": VehicleStats(
        size=(38, 34),
        max_hp=UNIT_STATS["light_tank"].hp,
        armor=UNIT_STATS["light_tank"].armor,
        speed=UNIT_STATS["light_tank"].speed,
        damage=UNIT_STATS["light_tank"].damage,
        bullet_speed=650,
        reload_time=0.85,
        projectile_life=1.25,
        sprite_height=60,
    ),
    "sherman": VehicleStats(
        size=(40, 36),
        max_hp=UNIT_STATS["sherman"].hp,
        armor=UNIT_STATS["sherman"].armor,
        speed=UNIT_STATS["sherman"].speed,
        damage=UNIT_STATS["sherman"].damage,
        bullet_speed=610,
        reload_time=1.1,
        projectile_life=1.45,
        sprite_height=70,
    ),
    "heavy_tank": VehicleStats(
        size=(44, 40),
        max_hp=UNIT_STATS["heavy_tank"].hp,
        armor=UNIT_STATS["heavy_tank"].armor,
        speed=UNIT_STATS["heavy_tank"].speed,
        damage=UNIT_STATS["heavy_tank"].damage,
        bullet_speed=560,
        reload_time=1.55,
        projectile_life=1.75,
        sprite_height=82,
    ),
}


class Vehicle:
    def __init__(
        self,
        pos,
        *,
        size: tuple[int, int] = (46, 42),
        hp: int = 180,
        armor: int = 16,
        speed: float = 60,
        faction: str = "ally",
    ):
        self.rect = pygame.Rect(int(pos[0]), int(pos[1]), size[0], size[1])
        self.hp = hp
        self.max_hp = hp
        self.armor = armor
        self.speed = speed
        self.faction = faction
        self.occupied = False
        self.occupant = None
        self.angle = 0.0
        self.turret_angle = 0.0
        self.desired_angle = 0.0
        self.move_remainder = pygame.Vector2()
        self.reload = 0.0
        self.flash = 0.0
        self.shooting_flash = 0.0
        self.anim_time = 0.0
        self.moving = False

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def enter(self, player) -> bool:
        if self.occupied or not self.alive:
            return False
        self.occupied = True
        self.occupant = player
        if hasattr(player, "vehicle"):
            player.vehicle = self
        return True

    def exit_position(self) -> pygame.Vector2:
        angle = math.radians(self.angle)
        side = pygame.Vector2(-math.sin(angle), math.cos(angle))
        if side.length_squared() == 0:
            side = pygame.Vector2(0, 1)
        distance = max(self.rect.width, self.rect.height) * 0.75 + 18
        return pygame.Vector2(self.rect.center) + side.normalize() * distance

    def exit_candidates(self) -> list[pygame.Vector2]:
        preferred = self.exit_position()
        angle = math.radians(self.angle)
        side = pygame.Vector2(-math.sin(angle), math.cos(angle))
        if side.length_squared() == 0:
            side = pygame.Vector2(0, 1)
        side = side.normalize()
        distance = max(self.rect.width, self.rect.height) * 0.75 + 18
        opposite = pygame.Vector2(self.rect.center) - side * distance
        heading = pygame.Vector2(math.cos(angle), math.sin(angle)).normalize()
        behind = pygame.Vector2(self.rect.center) - heading * distance
        front = pygame.Vector2(self.rect.center) + heading * distance
        
        candidates = [preferred, opposite, behind, front]
        for deg in [45, 135, 225, 315]:
            rad = math.radians(self.angle + deg)
            diag = pygame.Vector2(math.cos(rad), math.sin(rad)) * distance
            candidates.append(pygame.Vector2(self.rect.center) + diag)
        return candidates

    def exit(self, override_pos: pygame.Vector2 | None = None):
        player = self.occupant
        if player is not None:
            if hasattr(player, "rect"):
                player.rect.center = override_pos if override_pos is not None else self.exit_position()
            if hasattr(player, "vehicle"):
                player.vehicle = None
        self.occupied = False
        self.occupant = None
        return player

    def damage(self, amount: int, armor_piercing: int = 0) -> int:
        if not self.alive:
            return 0
        mitigation = max(0, self.armor - armor_piercing)
        actual = max(1, int(amount) - mitigation)
        self.hp = max(0, self.hp - actual)
        self.flash = 0.14
        if self.hp == 0 and self.occupied:
            self.exit()
        return actual

    def shoot(self, target):
        return None

    def update(self, dt: float) -> None:
        self.reload = max(0.0, self.reload - dt)
        self.flash = max(0.0, self.flash - dt)
        self.shooting_flash = max(0.0, self.shooting_flash - dt)
        self.anim_time += dt

    def rotate_toward(self, target_angle: float, max_degrees: float) -> None:
        delta = ((target_angle - self.angle + 180) % 360) - 180
        delta = max(-max_degrees, min(max_degrees, delta))
        self.angle = (self.angle + delta) % 360

    def rotate_turret_toward(self, target_angle: float, max_degrees: float) -> None:
        delta = ((target_angle - self.turret_angle + 180) % 360) - 180
        delta = max(-max_degrees, min(max_degrees, delta))
        self.turret_angle = (self.turret_angle + delta) % 360

    def draw(self, screen: pygame.Surface, camera) -> None:
        view = camera.apply(self.rect)
        color = COLORS["ally"] if self.faction == "ally" else COLORS["enemy"]
        pygame.draw.ellipse(screen, (0, 0, 0, 76), view.inflate(8, 4).move(3, 6))
        pygame.draw.rect(screen, (42, 48, 42), view, border_radius=5)
        pygame.draw.rect(screen, color, view.inflate(-8, -8), border_radius=4)
        if self.flash > 0:
            pygame.draw.rect(screen, (255, 238, 190), view, 2, border_radius=5)
        self._draw_hp(screen, view)

    def _draw_hp(self, screen: pygame.Surface, view: pygame.Rect) -> None:
        hp_w = max(view.width, 44)
        bar = pygame.Rect(view.centerx - hp_w // 2, view.top - 8, hp_w, 5)
        pygame.draw.rect(screen, (35, 30, 28), bar)
        bar.width = int(hp_w * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(screen, (77, 176, 88) if self.faction == "ally" else COLORS["danger"], bar)


class TankVehicle(Vehicle):
    def __init__(self, pos, kind: str = "sherman", faction: str = "ally"):
        if kind not in TANK_STATS:
            raise ValueError(f"Unsupported tank kind: {kind!r}")
        self.kind = kind
        self.stats = TANK_STATS[kind]
        super().__init__(
            pos,
            size=self.stats.size,
            hp=self.stats.max_hp,
            armor=self.stats.armor,
            speed=self.stats.speed,
            faction=faction,
        )

    def shoot(self, target) -> Bullet | None:
        if not self.alive or self.reload > 0:
            return None
        aim = pygame.Vector2(target) - pygame.Vector2(self.rect.center)
        if aim.length_squared():
            target_angle = math.degrees(math.atan2(aim.y, aim.x))
            delta = abs(((target_angle - self.turret_angle + 180) % 360) - 180)
            if delta > 22:
                return None
        direction = pygame.Vector2(math.cos(math.radians(self.turret_angle)), math.sin(math.radians(self.turret_angle)))
        self.reload = self.stats.reload_time
        self.shooting_flash = 0.14

        bullet = Bullet(self.rect.center, direction, friendly=self.faction == "ally")
        bullet.damage = self.stats.damage
        bullet.speed = self.stats.bullet_speed
        bullet.life = self.stats.projectile_life
        bullet.armor_piercing = self.stats.armor // 2 + 14
        bullet.weapon = "tank"
        bullet.rect = pygame.Rect(0, 0, 16, 8)
        return bullet

    def draw(self, screen: pygame.Surface, camera) -> None:
        view = camera.apply(self.rect)
        sprite = self._current_sprite()
        sprite_rect = sprite.get_rect(midbottom=(view.centerx, view.bottom + 10))

        shadow = pygame.Surface((sprite_rect.width, max(8, sprite_rect.height // 5)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 72), shadow.get_rect())
        screen.blit(shadow, shadow.get_rect(center=(sprite_rect.centerx + 2, sprite_rect.bottom - 8)))
        screen.blit(sprite, sprite_rect)

        if self.faction != "ally":
            tint = pygame.Surface(sprite_rect.size, pygame.SRCALPHA)
            tint.fill((130, 48, 42, 50))
            screen.blit(tint, sprite_rect)

        if self.flash > 0:
            flash = pygame.Surface(sprite_rect.size, pygame.SRCALPHA)
            flash.fill((255, 238, 190, 70))
            screen.blit(flash, sprite_rect)

        base = pygame.Vector2(sprite_rect.centerx, sprite_rect.centery - 4)

        if self.shooting_flash > 0:
            barrel = pygame.Vector2(math.cos(math.radians(self.turret_angle)), math.sin(math.radians(self.turret_angle)))
            muzzle = base + barrel * (self.stats.sprite_height * 0.5)
            pygame.draw.circle(screen, (248, 197, 82), muzzle, 8)
            pygame.draw.circle(screen, (255, 238, 190), muzzle, 4)

        turret = pygame.Vector2(math.cos(math.radians(self.turret_angle)), math.sin(math.radians(self.turret_angle)))
        end = base + turret * (self.stats.sprite_height * 0.34)
        pygame.draw.line(screen, (40, 44, 38), base, end, 6)
        pygame.draw.line(screen, (95, 101, 82), base, end, 3)

        self._draw_hp(screen, pygame.Rect(sprite_rect.left, sprite_rect.top, sprite_rect.width, sprite_rect.height))

    def _current_sprite(self) -> pygame.Surface:
        indices = self._tank_indices()
        frame = indices[int(self.anim_time * 8) % len(indices)]
        sprite = get_assets().frame("m4_sherman", frame, self.stats.sprite_height)
        return pygame.transform.flip(sprite, True, False) if self._direction_bucket() == 3 else sprite

    def _direction_bucket(self) -> int:
        angle = self.angle % 360
        if 45 <= angle < 135:
            return 2
        if 135 <= angle < 225:
            return 3
        if 225 <= angle < 315:
            return 0
        return 1

    def _tank_indices(self) -> list[int]:
        if not self.alive:
            return get_tank_frames("wreck")
        action = "fire" if self.shooting_flash > 0 else ("move" if self.moving else "idle")
        return {
            0: get_tank_frames(action, "up"),
            1: get_tank_frames(action, "side"),
            2: get_tank_frames(action, "down"),
            3: get_tank_frames(action, "side"),
        }[self._direction_bucket()]


__all__ = ["TANK_STATS", "TankVehicle", "Vehicle", "VehicleStats"]
