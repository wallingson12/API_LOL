"""
player_match.py — Identifica o jogador ativo na Live Client (Riot ID com/sem tag)
"""


def normalize_player_name(name: str | None) -> str:
    if not name:
        return ""
    return name.split("#", 1)[0].removesuffix(" Bot").strip().lower()


def names_match(name_a: str | None, name_b: str | None) -> bool:
    if not name_a or not name_b:
        return False
    if name_a == name_b:
        return True
    a = normalize_player_name(name_a)
    b = normalize_player_name(name_b)
    if a and b and a == b:
        return True
    return name_a.lower() == name_b.lower()


def active_player_name(game_data: dict) -> str | None:
    ap = game_data.get("activePlayer") or {}
    return ap.get("riotIdGameName") or ap.get("summonerName") or None


def player_display_name(player: dict) -> str:
    return player.get("riotIdGameName") or player.get("summonerName") or "?"


def find_active_player(game_data: dict) -> dict | None:
    active = active_player_name(game_data)
    if not active:
        return None
    for player in game_data.get("allPlayers") or []:
        pname = player_display_name(player)
        if names_match(active, pname):
            return player
    return None


def is_ingame_snapshot(game_data: dict) -> bool:
    """Evita entrar no loop no loading com API instável."""
    players = game_data.get("allPlayers") or []
    if len(players) >= 10:
        return True
    game_time = float(game_data.get("gameData", {}).get("gameTime", 0) or 0)
    return game_time > 5
