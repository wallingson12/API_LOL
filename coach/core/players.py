"""
players.py — Identificação de jogadores (nome, kill feed, active player).
"""

from game.player_match import (
    active_player_name,
    find_active_player,
    names_match,
    normalize_player_name,
    player_display_name,
)


def player_name(player: dict) -> str:
    return player_display_name(player)


def cache_keys(player: dict) -> list[str]:
    keys: list[str] = []
    pname = player_name(player)
    keys.append(pname)
    keys.append(normalize_player_name(pname))
    champ = (player.get("championName") or "").lower()
    if champ:
        keys.append(champ)
    return keys


def kill_name_matches(kill_name: str, player: dict) -> bool:
    if not kill_name:
        return False

    pname = player_name(player)
    if kill_name == pname:
        return True

    kill_norm = normalize_player_name(kill_name)
    if kill_norm == normalize_player_name(pname):
        return True

    champ = player.get("championName", "")
    if champ and kill_norm == champ.lower():
        return True

    if champ and kill_name.lower().startswith(champ.lower()):
        return True

    if pname and kill_name.lower().startswith(pname.lower()):
        return True

    return False


def find_player(all_players: list[dict], kill_name: str) -> dict | None:
    for player in all_players:
        if kill_name_matches(kill_name, player):
            return player
    return None
