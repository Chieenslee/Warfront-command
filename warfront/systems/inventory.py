from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from warfront.entities.items import ITEM_AMMO, ITEM_GRENADE, ITEM_MEDKIT, normalize_item_kind


@dataclass
class Inventory:
    medkits: int = 0
    grenades: int = 0
    ammo: int = 0
    medkit_heal: int = 45

    def add_item(self, item: Any, amount: int | None = None) -> None:
        kind = normalize_item_kind(getattr(item, "kind", item))
        value = getattr(item, "amount", amount if amount is not None else 1)
        value = max(1, int(value))

        if kind == ITEM_MEDKIT:
            self.medkits += value
        elif kind == ITEM_GRENADE:
            self.grenades += value
        elif kind == ITEM_AMMO:
            self.ammo += value

    def use_medkit(self, player) -> bool:
        if self.medkits <= 0:
            return False

        max_hp = getattr(player, "max_hp", None)
        current_hp = getattr(player, "hp", None)
        if max_hp is None or current_hp is None or current_hp >= max_hp:
            return False

        player.hp = min(max_hp, current_hp + self.medkit_heal)
        self.medkits -= 1
        return True

    def use_grenade(self) -> bool:
        if self.grenades <= 0:
            return False

        self.grenades -= 1
        return True


__all__ = ["Inventory"]
