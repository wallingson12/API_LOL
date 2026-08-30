"""Prioridade de alertas táticos (maior = fala primeiro)."""

PRIORITY_CRITICAL = 100
PRIORITY_HIGH = 80
PRIORITY_MEDIUM = 50
PRIORITY_LOW = 25
PRIORITY_AMBIENT = 10

ALERT_PRIORITY: dict[str, int] = {
    "num_advantage": PRIORITY_CRITICAL,
    "objective_spawn": 95,
    "enemy_jg_dead_gank": 90,
    "resource_critical": 89,
    "dragon_score": 88,
    "tower_taken_recall": 85,
    "tower_lost_first": 82,
    "lane_level_danger": 75,
    "enemy_item_effect": 70,
    "build_suggest": 72,
    "my_death_streak": 60,
    "resource_low_mana": 58,
    "resource_low_hp": 56,
    "objective_ward": 55,
    "jg_objective_up": 45,
    "jg_look_lanes": 40,
    "ward_expiring": 30,
    "trinket_full": 28,
    "ward_place_reminder": 20,
}

EVENT_SPEECH_PRIORITY: dict[str, int] = {
    "player_respawned": 72,
    "gold_threshold": 68,
    "turret": 62,
    "inhibitor": 62,
    "map_reminder": PRIORITY_AMBIENT,
    "game_start": PRIORITY_AMBIENT,
}


def alert_priority(alert: dict) -> int:
    return ALERT_PRIORITY.get(alert.get("type", ""), PRIORITY_MEDIUM)


def sort_alerts(alerts: list[dict]) -> list[dict]:
    return sorted(alerts, key=alert_priority, reverse=True)


def event_speech_priority(event_type: str) -> int:
    return EVENT_SPEECH_PRIORITY.get(event_type, PRIORITY_MEDIUM)
