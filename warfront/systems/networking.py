from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NetworkPlayer:
    player_id: str
    callsign: str
    team: str
    ready: bool = False


@dataclass(frozen=True, slots=True)
class CombatSyncEvent:
    tick: int
    event_type: str
    payload: dict


@dataclass(slots=True)
class LobbyState:
    mode: str
    max_players: int
    players: list[NetworkPlayer] = field(default_factory=list)

    @property
    def full(self) -> bool:
        return len(self.players) >= self.max_players

    def add_local_placeholder(self, callsign: str = "Player") -> None:
        if self.full:
            return
        self.players.append(NetworkPlayer("local", callsign, "allied", ready=True))


__all__ = ["CombatSyncEvent", "LobbyState", "NetworkPlayer"]
