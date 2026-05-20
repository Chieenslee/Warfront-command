from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnitStats:
    hp: int
    damage: int
    range: int
    speed: int
    armor: int


UNIT_STATS: dict[str, UnitStats] = {
    "player": UnitStats(hp=120, damage=32, range=430, speed=230, armor=6),
    "rifleman": UnitStats(hp=70, damage=18, range=360, speed=105, armor=2),
    "elite": UnitStats(hp=105, damage=26, range=410, speed=118, armor=5),
    "light_tank": UnitStats(hp=260, damage=45, range=500, speed=78, armor=24),
    "sherman": UnitStats(hp=420, damage=58, range=560, speed=65, armor=36),
    "heavy_tank": UnitStats(hp=620, damage=76, range=610, speed=48, armor=52),
    "super_heavy": UnitStats(hp=1800, damage=110, range=700, speed=35, armor=85),
    "bomber": UnitStats(hp=300, damage=135, range=720, speed=310, armor=18),
}


__all__ = ["UNIT_STATS", "UnitStats"]
