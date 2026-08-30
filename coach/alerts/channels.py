"""Canal de alerta: voz (decisão agora) vs texto (consulta no HUD)."""

from __future__ import annotations

from data.notices import channel_override

CHANNEL_VOICE = "voice"
CHANNEL_TEXT = "text"
CHANNEL_BOTH = "both"

# Padrão de jogador: voz só quando o delay da leitura mata a jogada.
DEFAULT_CHANNELS: dict[str, str] = {
    "num_advantage": CHANNEL_VOICE,
    "enemy_jg_dead_gank": CHANNEL_VOICE,
    "objective_spawn": CHANNEL_VOICE,
    "tower_taken_recall": CHANNEL_VOICE,
    "tower_lost_first": CHANNEL_BOTH,
    "lane_level_danger": CHANNEL_VOICE,
    "my_death_streak": CHANNEL_VOICE,
    "enemy_item_effect": CHANNEL_VOICE,
    "resource_critical": CHANNEL_VOICE,
    "gold_threshold": CHANNEL_VOICE,
    "player_respawned": CHANNEL_VOICE,
    "game_start": CHANNEL_VOICE,
    "map_reminder": CHANNEL_TEXT,
    "ward_place_reminder": CHANNEL_TEXT,
    "ward_expiring": CHANNEL_TEXT,
    "trinket_full": CHANNEL_TEXT,
    "jg_look_lanes": CHANNEL_TEXT,
    "jg_objective_up": CHANNEL_TEXT,
    "objective_ward": CHANNEL_TEXT,
    "dragon_score": CHANNEL_TEXT,
    "build_suggest": CHANNEL_TEXT,
    "resource_low_mana": CHANNEL_TEXT,
    "resource_low_hp": CHANNEL_TEXT,
    "lane_briefing": CHANNEL_TEXT,
    "champion_note": CHANNEL_TEXT,
    "dragon_info": CHANNEL_TEXT,
    "wave_tip": CHANNEL_TEXT,
}

CHANNEL_LABELS: dict[str, str] = {
    CHANNEL_VOICE: "Voz",
    CHANNEL_TEXT: "Escrito",
    CHANNEL_BOTH: "Voz + escrito",
}

EDITABLE_ALERT_TYPES: tuple[tuple[str, str], ...] = (
    ("num_advantage", "Vantagem numérica"),
    ("enemy_jg_dead_gank", "Jungle inimigo morto"),
    ("objective_spawn", "Objetivo nascendo"),
    ("objective_ward", "Wardar objetivo"),
    ("tower_taken_recall", "Torre derrubada → base"),
    ("tower_lost_first", "Primeira torre caiu"),
    ("lane_level_danger", "Oponente com nível"),
    ("my_death_streak", "Duas mortes seguidas"),
    ("enemy_item_effect", "Item tático inimigo"),
    ("build_suggest", "Sugestão de item"),
    ("map_reminder", "Olhe o mapa"),
    ("ward_place_reminder", "Lembrete de ward"),
    ("ward_expiring", "Ward expirando"),
    ("trinket_full", "Pingente cheio"),
    ("jg_look_lanes", "Jungle: olhar rotas"),
    ("jg_objective_up", "Jungle: objetivo no mapa"),
    ("dragon_score", "Placar de dragões"),
    ("resource_low_mana", "Mana baixa"),
    ("resource_low_hp", "Vida baixa"),
    ("resource_critical", "Sem recurso e em perigo"),
)


def resolve_channel(alert: dict) -> str:
    if alert.get("channel") in (CHANNEL_VOICE, CHANNEL_TEXT, CHANNEL_BOTH):
        return alert["channel"]
    alert_type = alert.get("type") or ""
    override = channel_override(alert_type)
    if override:
        return override
    return DEFAULT_CHANNELS.get(alert_type, CHANNEL_VOICE)


def uses_voice(channel: str) -> bool:
    return channel in (CHANNEL_VOICE, CHANNEL_BOTH)


def uses_text(channel: str) -> bool:
    return channel in (CHANNEL_TEXT, CHANNEL_BOTH)
