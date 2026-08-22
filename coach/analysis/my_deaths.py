from config import MY_DEATH_STREAK_COUNT, MY_DEATH_STREAK_WINDOW_SECONDS
from core.game_time import game_time

class MyDeathTracker:
    def __init__(self):
        self._death_times: list[float] = []

    def reset(self):
        self._death_times.clear()

    def alerts_from_events(self, events: list[dict], game_data: dict, my_name: str) -> list[dict]:
        now = game_time(game_data)
        out = []

        for ev in events:
            if ev.get("type") != "kill" or ev.get("victim") != my_name:
                continue

            self._death_times.append(now)
            self._death_times = [
                t for t in self._death_times
                if now - t <= MY_DEATH_STREAK_WINDOW_SECONDS
            ]

            if len(self._death_times) >= MY_DEATH_STREAK_COUNT:
                out.append({
                    "type": "my_death_streak",
                    "count": len(self._death_times),
                    "window_seconds": MY_DEATH_STREAK_WINDOW_SECONDS,
                })
                self._death_times.clear()

        return out
