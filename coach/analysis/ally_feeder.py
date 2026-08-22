from config import (
    FEEDER_ALERT_COOLDOWN_SECONDS,
    FEEDER_DEATH_COUNT,
    FEEDER_WINDOW_SECONDS,
)
from game.events import parse_role
from analysis.analyzer import get_my_team_and_enemies
from core.players import find_player
from core.roles import ROLE_TO_LANE
from core.game_time import game_time


class AllyFeederTracker:
    def __init__(self):
        self._lane_death_times: dict[str, list[float]] = {}
        self._last_alert_at: dict[str, float] = {}

    def reset(self):
        self._lane_death_times.clear()
        self._last_alert_at.clear()

    def _lane_for_player(self, player: dict) -> str | None:
        return ROLE_TO_LANE.get(parse_role(player) or "")

    def _recent_deaths(self, lane: str, now: float) -> int:
        times = self._lane_death_times.get(lane, [])
        recent = [t for t in times if now - t <= FEEDER_WINDOW_SECONDS]
        self._lane_death_times[lane] = recent
        return len(recent)

    def alerts_from_events(
        self,
        events: list[dict],
        game_data: dict,
        my_name: str,
    ) -> list[dict]:
        me, _, _ = get_my_team_and_enemies(game_data)
        if not me:
            return []

        my_team = me.get("team")
        my_role = parse_role(me)
        my_lane = self._lane_for_player(me)
        all_players = game_data.get("allPlayers", [])
        now = game_time(game_data)
        alerts = []

        for ev in events:
            if ev.get("type") != "kill":
                continue

            kill_name = ev.get("victim", "")
            if not kill_name or kill_name == my_name:
                continue

            victim = find_player(all_players, kill_name)
            if not victim or victim.get("team") != my_team:
                continue

            lane = self._lane_for_player(victim)
            if not lane:
                continue

            times = self._lane_death_times.setdefault(lane, [])
            times.append(now)
            self._lane_death_times[lane] = times

            if self._recent_deaths(lane, now) < FEEDER_DEATH_COUNT:
                continue

            last_alert = self._last_alert_at.get(lane, -9999.0)
            if now - last_alert < FEEDER_ALERT_COOLDOWN_SECONDS:
                continue

            self._last_alert_at[lane] = now
            alerts.append({
                "type": "lane_feeding",
                "lane": lane,
                "my_role": my_role,
                "my_lane": my_lane,
            })

        return alerts
