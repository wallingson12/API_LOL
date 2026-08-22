import time

from config import (
    JUNGLE_LANE_LOOK_INTERVAL_SECONDS,
    JUNGLE_OBJECTIVE_REMINDER_INTERVAL_SECONDS,
)
from game.events import parse_role
from analysis.analyzer import get_my_team_and_enemies


def _primary_objective(available: list[str], game_time: float) -> str | None:
    if not available:
        return None
    avail = set(available)

    if game_time >= 1200:
        for key in ("baron", "elder", "dragon", "voidgrub", "herald"):
            if key in avail:
                return key
    if game_time >= 840:
        for key in ("herald", "elder", "dragon", "voidgrub"):
            if key in avail:
                return key
    if game_time >= 300:
        for key in ("voidgrub", "dragon"):
            if key in avail:
                return key
    return available[0]


class JungleReminderTracker:
    def __init__(self):
        self._last_lane_look = 0.0
        self._last_objective = 0.0
        self._lane_variant = 0

    def reset(self):
        self.__init__()

    def update(
        self,
        game_data: dict,
        objective_tracker,
        now_mono: float | None = None,
        game_live: bool = False,
    ) -> list[dict]:
        if not game_live:
            return []

        me, _, _ = get_my_team_and_enemies(game_data)
        if not me or parse_role(me) != "jungler":
            return []

        clock = now_mono if now_mono is not None else time.monotonic()
        if self._last_lane_look == 0.0:
            self._last_lane_look = clock
        if self._last_objective == 0.0:
            self._last_objective = clock

        alerts = []
        game_time = float(game_data.get("gameData", {}).get("gameTime", 0) or 0)

        lane_due = clock - self._last_lane_look >= JUNGLE_LANE_LOOK_INTERVAL_SECONDS
        objective_due = (
            clock - self._last_objective >= JUNGLE_OBJECTIVE_REMINDER_INTERVAL_SECONDS
        )

        objectives = (
            objective_tracker.available_objectives(game_data)
            if objective_tracker
            else []
        )
        primary = _primary_objective(objectives, game_time)

        # Alterna quando os dois vencem no mesmo tick — evita duas falas seguidas
        if lane_due and objective_due and primary:
            if self._lane_variant % 2 == 0:
                objective_due = False
            else:
                lane_due = False

        if lane_due:
            self._last_lane_look = clock
            alerts.append({
                "type": "jg_look_lanes",
                "variant": self._lane_variant,
            })
            self._lane_variant += 1

        if objective_due and primary:
            self._last_objective = clock
            alerts.append({
                "type": "jg_objective_up",
                "objective": primary,
            })

        return alerts
