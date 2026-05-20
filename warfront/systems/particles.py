import random

import pygame

from warfront.assets.loader import get_assets


class Particle:
    def __init__(self, pos, vel, radius, color, life, sprite: pygame.Surface | None = None):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.radius = radius
        self.color = color
        self.life = life
        self.max_life = life
        self.sprite = sprite

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.pos += self.vel * dt
        self.vel *= 0.92
        return self.life > 0

    def draw(self, screen: pygame.Surface, camera) -> None:
        alpha = max(0, min(255, int(255 * self.life / self.max_life)))
        if self.sprite is not None:
            sprite = self.sprite.copy()
            sprite.set_alpha(alpha)
            screen.blit(sprite, sprite.get_rect(center=self.pos - camera.offset))
            return

        radius = max(1, int(self.radius * self.life / self.max_life))
        surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.color, alpha), (radius + 1, radius + 1), radius)
        screen.blit(surf, self.pos - camera.offset - pygame.Vector2(radius, radius))


class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []
        self.assets = get_assets()

    def smoke(self, pos, amount=8) -> None:
        for _ in range(amount):
            vel = pygame.Vector2(random.uniform(-35, 35), random.uniform(-45, 15))
            self.particles.append(Particle(pos, vel, random.randint(5, 11), (82, 82, 76), random.uniform(0.35, 0.75)))

    def sparks(self, pos, amount=10) -> None:
        for _ in range(amount):
            vel = pygame.Vector2(random.uniform(-170, 170), random.uniform(-170, 170))
            self.particles.append(Particle(pos, vel, random.randint(2, 4), (244, 181, 72), random.uniform(0.18, 0.38)))

    def explosion(self, pos) -> None:
        center = pygame.Vector2(pos)
        self.smoke(center, 18)
        self.sparks(center, 26)
        for i in range(24):
            angle = i / 24 * 6.28318
            speed = random.uniform(80, 210)
            vel = pygame.Vector2(speed, 0).rotate_rad(angle)
            color = random.choice(((255, 226, 126), (246, 143, 63), (209, 72, 45), (255, 246, 188)))
            self.particles.append(Particle(center, vel, random.randint(5, 11), color, random.uniform(0.18, 0.34)))
        for radius, life in ((26, 0.18), (42, 0.24), (58, 0.3)):
            self.particles.append(Particle(center, (0, 0), radius, (248, 197, 82), life))

    def update(self, dt: float) -> None:
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, screen: pygame.Surface, camera) -> None:
        for particle in self.particles:
            particle.draw(screen, camera)
