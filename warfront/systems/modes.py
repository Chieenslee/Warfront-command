from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GameMode(str, Enum):
    OFFLINE_CAMPAIGN = "offline_campaign"
    ONLINE_COOP = "online_coop"
    ONLINE_PVP = "online_pvp"


@dataclass
class ModeConfig:
    mode: GameMode = GameMode.OFFLINE_CAMPAIGN
    max_players: int = 1
    friendly_fire: bool = False
    sync_combat_events: bool = False

    @property
    def online(self) -> bool:
        return self.mode in {GameMode.ONLINE_COOP, GameMode.ONLINE_PVP}


OFFLINE_CONFIG = ModeConfig()
COOP_PLACEHOLDER = ModeConfig(
    mode=GameMode.ONLINE_COOP,
    max_players=4,
    friendly_fire=False,
    sync_combat_events=True,
)
PVP_PLACEHOLDER = ModeConfig(
    mode=GameMode.ONLINE_PVP,
    max_players=8,
    friendly_fire=True,
    sync_combat_events=True,
)


__all__ = ["COOP_PLACEHOLDER", "GameMode", "ModeConfig", "OFFLINE_CONFIG", "PVP_PLACEHOLDER"]
