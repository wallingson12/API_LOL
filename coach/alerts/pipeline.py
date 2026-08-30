"""Coleta, canal (voz/texto) e ordenação de alertas táticos."""

from alerts.channels import resolve_channel, uses_text, uses_voice
from alerts.priority import alert_priority, sort_alerts
from analysis.analyzer import analyze_snapshot
from analysis.coaching_alerts import coaching_alerts_from_events
from analysis.jungle_reminders import JungleReminderTracker
from analysis.my_deaths import MyDeathTracker
from analysis.objective_spawns import ObjectiveSpawnTracker
from analysis.tower_lane import TowerLaneTracker
from analysis.ward_tracker import WardTracker
from app_state import STATE
from core.game_time import game_time as snapshot_game_time
from voice.narrator import narrate_alert
from voice.voice import VoiceCoach


def _filter_noisy_alerts(alerts: list[dict], game_data: dict) -> list[dict]:
    """Corta lembretes fracos no early game."""
    gt = snapshot_game_time(game_data)
    out = []
    for alert in alerts:
        t = alert.get("type")
        if t == "ward_place_reminder" and gt < 180:
            continue
        if t == "trinket_full" and gt < 90:
            continue
        out.append(alert)
    return out


def collect_ingame_alerts(
    *,
    game_data: dict,
    new_events: list[dict],
    my_name: str,
    my_team: str | None,
    my_role: str | None,
    lcu_lane_ctx: dict,
    jungle_reminders: JungleReminderTracker,
    objective_spawns: ObjectiveSpawnTracker,
    my_deaths: MyDeathTracker,
    tower_lane: TowerLaneTracker,
    ward_tracker: WardTracker,
    tracker_is_live: bool,
    monotonic_now: float,
    extra_alerts: list[dict] | None = None,
) -> list[dict]:
    """Agrega alertas de todos os trackers; tower_lane observa estruturas primeiro."""
    tower_lane.observe_events(new_events, my_team)

    alerts: list[dict] = []
    alerts.extend(objective_spawns.alerts_from_dragon_events(new_events, my_team))
    alerts.extend(jungle_reminders.update(
        game_data, objective_spawns, monotonic_now, tracker_is_live,
    ))
    alerts.extend(coaching_alerts_from_events(
        game_data, new_events, objective_spawns,
        enemy_inhib_destroyed=tower_lane.enemy_inhib_destroyed(),
    ))
    alerts.extend(objective_spawns.update(game_data))
    alerts.extend(analyze_snapshot(game_data, lcu_lane_ctx))
    alerts.extend(my_deaths.alerts_from_events(new_events, game_data, my_name))
    alerts.extend(tower_lane.alerts_from_events(
        new_events, my_team, my_name, my_role, game_data,
    ))
    alerts.extend(ward_tracker.update(game_data, my_name))
    if extra_alerts:
        alerts.extend(extra_alerts)
    alerts = _filter_noisy_alerts(alerts, game_data)
    return sort_alerts(alerts)


def _hud_kind(alert_type: str) -> str:
    if alert_type in (
        "lane_level_danger",
        "resource_critical",
        "resource_low_hp",
        "tower_lost_first",
    ):
        return "warn"
    if alert_type in ("num_advantage", "enemy_jg_dead_gank", "objective_spawn"):
        return "live"
    return "info"


def dispatch_alerts(voice: VoiceCoach | None, alerts: list[dict]) -> None:
    for alert in alerts:
        result = narrate_alert(alert)
        voice_text = None
        key = alert.get("key")
        if result:
            voice_text, key = result
        hud_text = (alert.get("hud") or alert.get("text") or voice_text or "").strip()
        channel = resolve_channel(alert)
        if uses_voice(channel) and voice_text and voice:
            voice.say(voice_text, alert_key=key, priority=alert_priority(alert))
        if uses_text(channel) and hud_text:
            STATE.push_hud(hud_text, kind=_hud_kind(alert.get("type") or ""), key=key)


def speak_alerts(voice: VoiceCoach, alerts: list[dict]) -> None:
    dispatch_alerts(voice, alerts)
