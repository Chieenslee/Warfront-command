import math

import pygame

from warfront.assets.loader import get_assets


class GrenadeProjectile:
    def __init__(self, start, target, max_range: float):
        self.start = pygame.Vector2(start)
        target = pygame.Vector2(target)
        direction = target - self.start
        distance = min(max_range, direction.length())
        if direction.length_squared():
            target = self.start + direction.normalize() * distance
        self.target = target
        self.pos = pygame.Vector2(self.start)
        self.flight_time = max(0.34, min(0.95, distance / 820))
        self.timer = 0.0
        self.done = False
        self.spin = 0.0

    def update(self, dt: float) -> bool:
        self.timer += dt
        self.spin += dt * 520
        t = min(1.0, self.timer / self.flight_time)
        eased = 1 - (1 - t) * (1 - t)
        self.pos = self.start.lerp(self.target, eased)
        self.done = t >= 1.0
        return not self.done

    def draw(self, screen: pygame.Surface, camera) -> None:
        view = self.pos - camera.offset
        t = min(1.0, self.timer / self.flight_time)
        arc = math.sin(t * math.pi) * 34
        body = pygame.Vector2(view.x, view.y - arc)

        shadow_w = max(8, int(18 - arc * 0.16))
        shadow = pygame.Surface((shadow_w * 2, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
        screen.blit(shadow, shadow.get_rect(center=(view.x + 2, view.y + 8)))

        sprite = get_assets().frame("prop", 114, 28)
        sprite = pygame.transform.rotate(sprite, self.spin)
        screen.blit(sprite, sprite.get_rect(center=body))
        trail = self.start.lerp(self.target, max(0.0, t - 0.08)) - camera.offset
        pygame.draw.line(screen, (206, 190, 126), body, trail, 2)


__all__ = ["GrenadeProjectile"]
