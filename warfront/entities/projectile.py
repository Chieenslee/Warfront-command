import pygame

from warfront.config import BULLET_SPEED, COLORS, ENEMY_BULLET_SPEED


class Bullet:
    def __init__(
        self,
        pos,
        direction,
        friendly=True,
        *,
        damage: int | None = None,
        speed: float | None = None,
        life: float | None = None,
        armor_piercing: int = 0,
        weapon: str = "rifle",
    ):
        self.pos = pygame.Vector2(pos)
        self.direction = pygame.Vector2(direction)
        if self.direction.length_squared() == 0:
            self.direction = pygame.Vector2(1, 0)
        self.direction = self.direction.normalize()
        self.friendly = friendly
        self.speed = speed if speed is not None else (BULLET_SPEED if friendly else ENEMY_BULLET_SPEED)
        self.damage = damage if damage is not None else (34 if friendly else 18)
        self.life = life if life is not None else (1.3 if friendly else 1.8)
        self.armor_piercing = armor_piercing
        self.weapon = weapon
        self.rect = pygame.Rect(0, 0, 10, 5)

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.pos += self.direction * self.speed * dt
        self.rect.center = self.pos
        return self.life > 0

    def draw(self, screen: pygame.Surface, camera) -> None:
        center = self.pos - camera.offset
        end = center - self.direction * 14
        color = (249, 214, 112) if self.friendly else COLORS["danger"]
        glow = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*color, 65), (14, 14), 10)
        screen.blit(glow, center - pygame.Vector2(14, 14))
        pygame.draw.line(screen, (42, 34, 28), center, end, 5)
        pygame.draw.line(screen, color, center, end, 3)
        pygame.draw.circle(screen, (255, 240, 178), center, 3)
