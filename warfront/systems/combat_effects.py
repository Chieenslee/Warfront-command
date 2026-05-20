from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Literal

import pygame

from warfront.systems.particles import Particle, ParticleSystem


WeaponKind = Literal["rifle", "tank", "grenade", "bomber"]
EffectKind = Literal[
    "muzzle_flash",
    "bullet_hit",
    "soldier_death_smoke",
    "tank_explosion",
    "bomber_strike",
]


@dataclass(frozen=True)
class CombatEffectEvent:
    kind: EffectKind
    pos: tuple[float, float]
    weapon: WeaponKind = "rifle"
    direction: tuple[float, float] | None = None
    scale: float = 1.0

    def spawn(self, particles: ParticleSystem) -> None:
        CombatEffects(particles).spawn(self)

    def as_callable(self) -> Callable[[ParticleSystem], None]:
        return lambda particles: self.spawn(particles)


class CombatEffects:
    def __init__(self, particles: ParticleSystem | None = None, event_log: list | None = None):
        self.particles = particles
        self.event_log = event_log

    def spawn(self, event: CombatEffectEvent) -> CombatEffectEvent:
        if self.event_log is not None:
            self.event_log.append(event)
            
        if self.particles is None:
            return event

        handlers: dict[EffectKind, Callable[[CombatEffectEvent], None]] = {
            "muzzle_flash": self._spawn_muzzle_flash,
            "bullet_hit": self._spawn_bullet_hit,
            "soldier_death_smoke": self._spawn_soldier_death_smoke,
            "tank_explosion": self._spawn_tank_explosion,
            "bomber_strike": self._spawn_bomber_strike,
        }
        handlers[event.kind](event)
        return event

    def muzzle_flash(
        self,
        pos,
        direction=(1, 0),
        weapon: WeaponKind = "rifle",
        scale: float = 1.0,
    ) -> CombatEffectEvent:
        return self.spawn(_event("muzzle_flash", pos, weapon, direction, scale))

    def bullet_hit(self, pos, weapon: WeaponKind = "rifle", scale: float = 1.0) -> CombatEffectEvent:
        return self.spawn(_event("bullet_hit", pos, weapon, None, scale))

    def soldier_death_smoke(self, pos, weapon: WeaponKind = "rifle", scale: float = 1.0) -> CombatEffectEvent:
        return self.spawn(_event("soldier_death_smoke", pos, weapon, None, scale))

    def tank_explosion(self, pos, weapon: WeaponKind = "tank", scale: float = 1.0) -> CombatEffectEvent:
        return self.spawn(_event("tank_explosion", pos, weapon, None, scale))

    def bomber_strike_effect(self, pos, direction=(0, 1), scale: float = 1.0) -> CombatEffectEvent:
        return self.spawn(_event("bomber_strike", pos, "bomber", direction, scale))

    def _spawn_muzzle_flash(self, event: CombatEffectEvent) -> None:
        pos = pygame.Vector2(event.pos)
        direction = _direction(event.direction)
        amount = _scaled({"rifle": 5, "tank": 12, "grenade": 7, "bomber": 16}[event.weapon], event.scale)
        radius = {"rifle": 3, "tank": 5, "grenade": 4, "bomber": 6}[event.weapon]

        for _ in range(amount):
            spread = pygame.Vector2(random.uniform(-0.35, 0.35), random.uniform(-0.35, 0.35))
            vel = (direction + spread).normalize() * random.uniform(90, 230)
            color = random.choice(((255, 238, 190), (248, 197, 82), (244, 181, 72)))
            self._add(pos + direction * random.uniform(4, 12), vel, radius, color, random.uniform(0.08, 0.18))

        if event.weapon in ("tank", "bomber"):
            self.particles.smoke(pos - direction * 4, _scaled(3, event.scale))

    def _spawn_bullet_hit(self, event: CombatEffectEvent) -> None:
        if event.weapon == "tank":
            self.particles.sparks(event.pos, _scaled(14, event.scale))
            self.particles.smoke(event.pos, _scaled(8, event.scale))
            return

        if event.weapon == "grenade":
            self.particles.explosion(event.pos)
            self.particles.smoke(event.pos, _scaled(8, event.scale))
            return

        if event.weapon == "bomber":
            self._spawn_bomber_strike(event)
            return

        self.particles.sparks(event.pos, _scaled(7, event.scale))

    def _spawn_soldier_death_smoke(self, event: CombatEffectEvent) -> None:
        self.particles.smoke(event.pos, _scaled(10 if event.weapon == "grenade" else 6, event.scale))
        if event.weapon in ("grenade", "tank", "bomber"):
            self.particles.sparks(event.pos, _scaled(6, event.scale))

    def _spawn_tank_explosion(self, event: CombatEffectEvent) -> None:
        self.particles.explosion(event.pos)
        self.particles.smoke(event.pos, _scaled(18, event.scale))
        self.particles.sparks(event.pos, _scaled(18, event.scale))

    def _spawn_bomber_strike(self, event: CombatEffectEvent) -> None:
        center = pygame.Vector2(event.pos)
        direction = _direction(event.direction)
        side = pygame.Vector2(-direction.y, direction.x)

        for offset in (-30, 0, 30):
            impact = center + side * offset * event.scale
            self.particles.explosion(impact)
            self.particles.smoke(impact - direction * 20, _scaled(10, event.scale))

        for _ in range(_scaled(20, event.scale)):
            vel = -direction * random.uniform(80, 160) + side * random.uniform(-90, 90)
            self._add(center, vel, random.randint(4, 8), (99, 95, 84), random.uniform(0.35, 0.7))

    def _add(self, pos, vel, radius: int, color: tuple[int, int, int], life: float) -> None:
        self.particles.particles.append(Particle(pos, vel, radius, color, life))


def make_combat_effect(
    kind: EffectKind,
    pos,
    weapon: WeaponKind = "rifle",
    direction=None,
    scale: float = 1.0,
) -> CombatEffectEvent:
    return _event(kind, pos, weapon, direction, scale)


def spawn_combat_effect(
    particles: ParticleSystem | None,
    kind: EffectKind,
    pos,
    weapon: WeaponKind = "rifle",
    direction=None,
    scale: float = 1.0,
) -> CombatEffectEvent:
    return CombatEffects(particles).spawn(_event(kind, pos, weapon, direction, scale))


def _event(kind: EffectKind, pos, weapon: WeaponKind, direction, scale: float) -> CombatEffectEvent:
    point = pygame.Vector2(pos)
    aim = None if direction is None else tuple(pygame.Vector2(direction))
    return CombatEffectEvent(kind, tuple(point), weapon, aim, max(0.1, float(scale)))


def _direction(direction: tuple[float, float] | None) -> pygame.Vector2:
    vector = pygame.Vector2(direction or (1, 0))
    if vector.length_squared() == 0:
        angle = random.uniform(0, math.tau)
        return pygame.Vector2(math.cos(angle), math.sin(angle))
    return vector.normalize()


def _scaled(amount: int, scale: float) -> int:
    return max(1, int(round(amount * max(0.1, scale))))


__all__ = [
    "CombatEffectEvent",
    "CombatEffects",
    "EffectKind",
    "WeaponKind",
    "make_combat_effect",
    "spawn_combat_effect",
]
