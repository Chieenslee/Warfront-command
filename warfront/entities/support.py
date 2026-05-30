import random

import pygame

from warfront.assets.loader import get_assets
from warfront.config import COLORS
from warfront.systems.balance import UNIT_STATS


import math

class EnemyAircraft:
    def __init__(self, entry, exit, target=None, unit: str = "bomber"):
        self.unit = unit
        self.stats = UNIT_STATS["bomber"]
        self.center = pygame.Vector2(target) if target is not None else (pygame.Vector2(entry) + pygame.Vector2(exit)) * 0.5
        self.radius = 280.0
        self.angle = 0.0
        self.pos = self.center + pygame.Vector2(self.radius, 0)
        self.rect = pygame.Rect(0, 0, 74, 46)
        self.rect.center = self.pos
        self.hp = self.stats.hp
        self.max_hp = self.stats.hp
        self.armor = self.stats.armor
        self.speed = self.stats.speed
        self.angular_speed = self.speed / self.radius
        self.reload = 2.0
        self.bomb_cooldown = random.uniform(2.6, 7.4)
        self.flash = 0.0
        self.anim_time = 0.0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def damage(self, amount: int, armor_piercing: int = 0) -> int:
        mitigation = max(0, self.armor - armor_piercing)
        actual = max(1, int(amount) - mitigation)
        self.hp = max(0, self.hp - actual)
        self.flash = 0.14
        return actual

    def update(self, dt: float, target_pos) -> pygame.Vector2 | None:
        self.reload = max(0.0, self.reload - dt)
        self.bomb_cooldown = max(0.0, self.bomb_cooldown - dt)
        self.flash = max(0.0, self.flash - dt)
        self.anim_time += dt

        # Orbit around center
        self.angle += self.angular_speed * dt
        self.pos.x = self.center.x + math.cos(self.angle) * self.radius
        # Use an elliptical orbit for isometric perspective
        self.pos.y = self.center.y + math.sin(self.angle) * self.radius * 0.6
        self.rect.center = self.pos

        player = pygame.Vector2(target_pos)
        # Drop bomb if player is within range
        if self.bomb_cooldown <= 0 and player.distance_to(self.pos) <= 400:
            self.bomb_cooldown = random.uniform(6.0, 9.2)
            return player
        return None

    def draw(self, screen: pygame.Surface, camera) -> None:
        dx = -math.sin(self.angle)
        
        frame = 43 + int(self.anim_time * 10) % 8
        sprite = get_assets().frame("axis_bomber", frame, 86)
        
        # Flip sprite if flying left to avoid it being upside down
        if dx < 0:
            sprite = pygame.transform.flip(sprite, True, False)
            
        rect = sprite.get_rect(center=self.pos - camera.offset)

        shadow = pygame.Surface((rect.width, max(10, rect.height // 4)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 56), shadow.get_rect())
        screen.blit(shadow, shadow.get_rect(center=(rect.centerx + 14, rect.centery + 42)))
        screen.blit(sprite, rect)
        
        if self.flash > 0:
            flash = pygame.Surface(rect.size, pygame.SRCALPHA)
            flash.fill((255, 238, 190, 74))
            screen.blit(flash, rect)

        hp = pygame.Rect(rect.centerx - 34, rect.top - 10, 68, 5)
        pygame.draw.rect(screen, (35, 30, 28), hp)
        hp.width = int(68 * max(0, self.hp) / self.max_hp)
        pygame.draw.rect(screen, COLORS["danger"], hp)


class MortarShell:
    def __init__(self, target, delay: float = 0.75, weapon_id: str = "mortar", hostile: bool = False):
        self.target = pygame.Vector2(target)
        self.delay = delay
        self.weapon_id = weapon_id
        self.hostile = hostile
        self.timer = 0.0
        self.done = False

    def update(self, dt: float) -> bool:
        self.timer += dt
        self.done = self.timer >= self.delay
        return not self.done

    @property
    def pos(self) -> pygame.Vector2:
        t = min(1.0, self.timer / self.delay)
        return self.target + pygame.Vector2(0, -260 * (1 - t))

    def draw(self, screen: pygame.Surface, camera) -> None:
        pos = self.pos - camera.offset
        sprite_index = 101 if self.hostile else 98
        sprite = get_assets().frame("prop", sprite_index, 34)
        sprite = pygame.transform.rotate(sprite, -65 if not self.hostile else -110)
        screen.blit(sprite, sprite.get_rect(center=pos))
        color = (220, 70, 54) if self.hostile else (238, 203, 116)
        pygame.draw.circle(screen, color, self.target - camera.offset, 18, 2)


__all__ = ["EnemyAircraft", "MortarShell"]
