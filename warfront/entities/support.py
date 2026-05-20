import pygame

from warfront.assets.loader import get_assets
from warfront.config import COLORS
from warfront.systems.balance import UNIT_STATS


class EnemyAircraft:
    def __init__(self, entry, exit, target=None, unit: str = "bomber"):
        self.unit = unit
        self.stats = UNIT_STATS["bomber"]
        self.entry = pygame.Vector2(entry)
        self.exit = pygame.Vector2(exit)
        self.target_hint = pygame.Vector2(target) if target is not None else (self.entry + self.exit) * 0.5
        self.pos = pygame.Vector2(self.entry)
        self.rect = pygame.Rect(0, 0, 74, 46)
        self.rect.center = self.pos
        self.hp = self.stats.hp
        self.max_hp = self.stats.hp
        self.armor = self.stats.armor
        self.speed = self.stats.speed
        self.reload = 2.0
        self.bomb_cooldown = 3.0
        self.flash = 0.0
        self.anim_time = 0.0
        self.patrol_forward = True

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

        target_node = self.exit if self.patrol_forward else self.entry
        to_node = target_node - self.pos
        if to_node.length() < 28:
            self.patrol_forward = not self.patrol_forward
            target_node = self.exit if self.patrol_forward else self.entry
            to_node = target_node - self.pos
        if to_node.length_squared():
            self.pos += to_node.normalize() * self.speed * dt
        self.rect.center = self.pos

        player = pygame.Vector2(target_pos)
        if self.bomb_cooldown <= 0 and player.distance_to(self.pos) <= self.stats.range:
            self.bomb_cooldown = 4.8
            return player
        return None

    def draw(self, screen: pygame.Surface, camera) -> None:
        direction = (self.exit - self.entry) if self.patrol_forward else (self.entry - self.exit)
        angle = -direction.angle_to(pygame.Vector2(1, 0)) if direction.length_squared() else 0
        frame = 43 + int(self.anim_time * 10) % 8
        sprite = get_assets().frame("axis_bomber", frame, 86)
        sprite = pygame.transform.rotate(sprite, angle)
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

    def draw(self, screen: pygame.Surface, camera) -> None:
        t = min(1.0, self.timer / self.delay)
        pos = self.target - camera.offset + pygame.Vector2(0, -260 * (1 - t))
        sprite_index = 101 if self.hostile else 98
        sprite = get_assets().frame("prop", sprite_index, 34)
        sprite = pygame.transform.rotate(sprite, -65 if not self.hostile else -110)
        screen.blit(sprite, sprite.get_rect(center=pos))
        color = (220, 70, 54) if self.hostile else (238, 203, 116)
        pygame.draw.circle(screen, color, self.target - camera.offset, 18, 2)


__all__ = ["EnemyAircraft", "MortarShell"]
