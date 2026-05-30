import random

import pygame

from warfront.assets.loader import get_assets


MAX_PARTICLES = 650


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

    def explosion(self, pos, intensity: float = 1.0) -> None:
        center = pygame.Vector2(pos)
        intensity = max(0.2, min(1.0, float(intensity)))
        self.smoke(center, max(3, int(18 * intensity)))
        self.sparks(center, max(4, int(26 * intensity)))
        burst_count = max(6, int(24 * intensity))
        for i in range(burst_count):
            angle = i / burst_count * 6.28318
            speed = random.uniform(80, 210)
            vel = pygame.Vector2(speed, 0).rotate_rad(angle)
            color = random.choice(((255, 226, 126), (246, 143, 63), (209, 72, 45), (255, 246, 188)))
            self.particles.append(Particle(center, vel, random.randint(5, 11), color, random.uniform(0.18, 0.34)))
        rings = ((26, 0.18), (42, 0.24), (58, 0.3)) if intensity >= 0.75 else ((28, 0.2),)
        for radius, life in rings:
            self.particles.append(Particle(center, (0, 0), radius, (248, 197, 82), life))

    def sprite(self, pos, group: str, index: int, target_height: int, life: float = 0.22, vel=(0, 0)) -> None:
        frame = self.assets.frame(group, index, target_height)
        self.particles.append(Particle(pos, vel, max(1, target_height // 2), (255, 255, 255), life, frame))

    def update(self, dt: float) -> None:
        self.particles = [p for p in self.particles if p.update(dt)]
        if len(self.particles) > MAX_PARTICLES:
            self.particles = sorted(self.particles, key=lambda p: p.life / max(0.001, p.max_life))[-MAX_PARTICLES:]

    def draw(self, screen: pygame.Surface, camera) -> None:
        view = screen.get_rect().inflate(180, 180)
        for particle in self.particles:
            screen_pos = particle.pos - camera.offset
            if view.collidepoint(int(screen_pos.x), int(screen_pos.y)):
                particle.draw(screen, camera)
