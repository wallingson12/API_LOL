from game.player_match import find_active_player
from analysis.lane_level import LaneLevelTracker

_lane_level = LaneLevelTracker()


def get_my_team_and_enemies(game_data: dict) -> tuple[dict, list[dict], list[dict]]:
    """Retorna (eu, meu_time_sem_mim, inimigos)."""
    me = find_active_player(game_data)
    if not me:
        return {}, [], []

    all_players = game_data.get("allPlayers", [])
    my_team_id = me.get("team")
    allies = [p for p in all_players if p.get("team") == my_team_id and p is not me]
    enemies = [p for p in all_players if p.get("team") != my_team_id]
    return me, allies, enemies


def analyze_snapshot(game_data: dict, lcu_lane_ctx: dict | None = None) -> list[dict]:
    alerts = []
    me, _, enemies = get_my_team_and_enemies(game_data)
    if not me:
        return alerts

    ctx = lcu_lane_ctx or {}
    lane_alert = _lane_level.analyze(
        me,
        enemies,
        lcu_position=ctx.get("my_position"),
        lcu_opponent_name=ctx.get("lane_opponent_name"),
    )
    if lane_alert:
        alerts.append(lane_alert)

    return alerts


def reset_analyzer_state():
    global _lane_level
    _lane_level = LaneLevelTracker()
