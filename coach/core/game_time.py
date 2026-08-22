"""Tempo de jogo (gameTime) a partir do snapshot da Live Client API."""


def game_time(game_data: dict) -> float:
    return float(game_data.get("gameData", {}).get("gameTime", 0) or 0)
