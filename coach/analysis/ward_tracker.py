import time

from config import (
    TRINKET_ITEM_IDS,
    WARD_EXPIRY_WARNING_SECONDS,
    WARD_PLACE_REMINDER_SECONDS,
    TRINKET_FULL_REMINDER_SECONDS,
    YELLOW_WARD_DURATION_MIN,
    YELLOW_WARD_DURATION_MAX,
)
from core.players import find_player, kill_name_matches
from core.game_time import game_time as snapshot_game_time

_YELLOW_WARD_TYPES = frozenset({
    "YELLOW_TRINKET",
    "STEALTH_WARD",
    "StealthWard",
    "TOTEM",
    "Totem",
    "UNDEFINED",  # API às vezes manda UNDEFINED no ward amarelo
})

_SKIP_WARD_TYPES = frozenset({
    "CONTROL_WARD",
    "VISION_WARD",
    "BLUE_TRINKET",
    "FARSIGHT",
    "Farsight",
})



def _yellow_ward_duration(game_data: dict) -> float:
    """90s no início, até 120s conforme level médio do jogo (Data Dragon / wiki)."""
    players = game_data.get("allPlayers") or []
    if not players:
        return float(YELLOW_WARD_DURATION_MIN)
    avg_level = sum(int(p.get("level", 1) or 1) for p in players) / len(players)
    span = YELLOW_WARD_DURATION_MAX - YELLOW_WARD_DURATION_MIN
    return min(
        float(YELLOW_WARD_DURATION_MAX),
        max(float(YELLOW_WARD_DURATION_MIN), YELLOW_WARD_DURATION_MIN + (avg_level - 1) * (span / 17)),
    )


def _my_trinket_charges(game_data: dict, my_name: str) -> int | None:
    for player in game_data.get("allPlayers") or []:
        pname = player.get("riotIdGameName") or player.get("summonerName")
        if pname != my_name:
            continue
        for item in player.get("items") or []:
            if item.get("itemID") in TRINKET_ITEM_IDS:
                return int(item.get("count", 0) or 0)
    return None


def _is_my_ward_event(creator: str, my_name: str, players: list[dict]) -> bool:
    if not creator or creator == "?" or not my_name:
        return False
    player = find_player(players, creator)
    if player:
        pname = player.get("riotIdGameName") or player.get("summonerName")
        return pname == my_name
    return creator == my_name or kill_name_matches(creator, {"summonerName": my_name, "riotIdGameName": my_name})


def _is_yellow_ward(ward_type: str) -> bool:
    if not ward_type:
        return True
    upper = ward_type.upper()
    if any(skip in upper for skip in ("CONTROL", "VISION", "FARSIGHT", "BLUE")):
        return False
    if ward_type in _SKIP_WARD_TYPES:
        return False
    return ward_type in _YELLOW_WARD_TYPES or "STEALTH" in upper or "YELLOW" in upper or "TOTEM" in upper


class WardTracker:
    def __init__(self):
        self._active_wards: list[dict] = []
        self._last_ward_game_time: float | None = None
        self._last_trinket_charges: int | None = None
        self._trinket_full_since: float | None = None
        self._last_no_ward_reminder_at: float = 0.0
        self._last_trinket_full_alert: float = 0.0

    def reset(self):
        self._active_wards.clear()
        self._last_ward_game_time = None
        self._last_trinket_charges = None
        self._trinket_full_since = None
        self._last_no_ward_reminder_at = 0.0
        self._last_trinket_full_alert = 0.0

    def _register_yellow_ward(self, game_data: dict, event_time: float | None = None) -> None:
        game_time = event_time if event_time is not None else snapshot_game_time(game_data)
        duration = _yellow_ward_duration(game_data)
        self._active_wards.append({
            "expires_at": game_time + duration,
            "warned": False,
            "duration": duration,
        })
        self._last_ward_game_time = game_time
        if len(self._active_wards) > 2:
            self._active_wards = sorted(self._active_wards, key=lambda w: w["expires_at"])[-2:]

    def observe_events(
        self,
        events: list[dict],
        game_data: dict,
        my_name: str,
    ) -> None:
        players = game_data.get("allPlayers") or []

        for ev in events:
            if ev.get("type") == "ward_placed":
                creator = ev.get("creator", "?")
                if not _is_my_ward_event(creator, my_name, players):
                    continue
                if not _is_yellow_ward(ev.get("ward_type", "")):
                    continue
                self._register_yellow_ward(game_data, ev.get("event_time"))

            elif ev.get("type") == "ward_killed":
                if self._active_wards:
                    self._active_wards.pop(0)

    def _detect_trinket_charge_drop(self, game_data: dict, my_name: str) -> None:
        charges = _my_trinket_charges(game_data, my_name)
        if charges is None:
            return
        if self._last_trinket_charges is not None and charges < self._last_trinket_charges:
            self._register_yellow_ward(game_data)
        self._last_trinket_charges = charges

    def update(self, game_data: dict, my_name: str) -> list[dict]:
        alerts: list[dict] = []
        game_time = snapshot_game_time(game_data)
        now = time.monotonic()

        self._detect_trinket_charge_drop(game_data, my_name)
        charges = _my_trinket_charges(game_data, my_name)

        if charges is not None and charges >= 2:
            if self._trinket_full_since is None:
                self._trinket_full_since = now
            elif (
                now - self._trinket_full_since >= TRINKET_FULL_REMINDER_SECONDS
                and now - self._last_trinket_full_alert >= TRINKET_FULL_REMINDER_SECONDS
            ):
                self._last_trinket_full_alert = now
                alerts.append({"type": "trinket_full"})
        else:
            self._trinket_full_since = None

        for ward in self._active_wards:
            remaining = ward["expires_at"] - game_time
            if 0 < remaining <= WARD_EXPIRY_WARNING_SECONDS and not ward["warned"]:
                ward["warned"] = True
                alerts.append({
                    "type": "ward_expiring",
                    "seconds": max(1, int(remaining)),
                })

        self._active_wards = [w for w in self._active_wards if w["expires_at"] > game_time]

        if game_time >= 120:
            since_last = (
                game_time - self._last_ward_game_time
                if self._last_ward_game_time is not None
                else game_time
            )
            if (
                since_last >= WARD_PLACE_REMINDER_SECONDS
                and now - self._last_no_ward_reminder_at >= WARD_PLACE_REMINDER_SECONDS
            ):
                self._last_no_ward_reminder_at = now
                alerts.append({"type": "ward_place_reminder", "seconds": int(since_last)})

        return alerts

    def hud_snapshot(self, game_data: dict, my_name: str) -> dict:
        game_t = snapshot_game_time(game_data)
        remaining = None
        if self._active_wards:
            remaining = max(0.0, min(w["expires_at"] - game_t for w in self._active_wards))
        return {
            "trinket_charges": _my_trinket_charges(game_data, my_name),
            "next_expiry": remaining,
            "active_yellow": len(self._active_wards),
        }
