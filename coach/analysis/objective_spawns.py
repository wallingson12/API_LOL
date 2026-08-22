from config import (
    DRAGON_FIRST_SPAWN,
    DRAGON_RESPAWN,
    ELDER_DRAGON_RESPAWN,
    DRAGON_SOUL_COUNT,
    BARON_FIRST_SPAWN,
    BARON_RESPAWN,
    HERALD_FIRST_SPAWN,
    BARON_SPAWN_ENDS_HERALD,
    OBJECTIVE_SPAWN_ALERT_SECONDS,
    OBJECTIVE_WARD_SECONDS,
    VOIDGRUB_FIRST_SPAWN,
    VOIDGRUB_RESPAWN,
    VOIDGRUB_SECOND_WAVE_DEADLINE,
    VOIDGRUB_DESPAWN,
    VOIDGRUB_WARD_SECONDS,
)

_VOIDGRUB_EVENT_NAMES = frozenset({
    "VoidGrubKill",
    "VoidgrubKill",
    "VoidGrubKilled",
})


from core.game_time import game_time


def _is_voidgrub_event(name: str) -> bool:
    if not name:
        return False
    if name in _VOIDGRUB_EVENT_NAMES:
        return True
    lower = name.lower()
    return "voidgrub" in lower and "kill" in lower


def _is_elder_dragon(dragon_type: str) -> bool:
    if not dragon_type:
        return False
    return "elder" in dragon_type.lower()


def _killer_team(game_data: dict, killer_name: str) -> str | None:
    if not killer_name or killer_name == "?":
        return None
    killer_lower = killer_name.lower()
    for player in game_data.get("allPlayers", []):
        name = player.get("riotIdGameName") or player.get("summonerName", "")
        if name and (killer_name == name or killer_lower == name.lower()):
            return player.get("team")
        champ = player.get("championName", "")
        if champ and killer_lower.startswith(champ.lower()):
            return player.get("team")
    return None


class ObjectiveSpawnTracker:
    def __init__(self):
        self._bootstrapped = False
        self._next_dragon = DRAGON_FIRST_SPAWN
        self._next_baron = BARON_FIRST_SPAWN
        self._next_herald = HERALD_FIRST_SPAWN
        self._dragon_in_pit = False
        self._elder_phase = False
        self._dragon_counts: dict[str, int] = {}
        self._herald_done = False
        self._alerted: set[str] = set()
        self._ward_alerted: set[str] = set()
        self._voidgrub_kill_times: list[float] = []
        self._voidgrub_done = False
        self._voidgrub_in_pit = False
        self._next_voidgrub_spawn = VOIDGRUB_FIRST_SPAWN

    def reset(self):
        self.__init__()

    def _load_voidgrub_kills(self, game_data: dict) -> None:
        kills = []
        for ev in game_data.get("events", {}).get("Events", []):
            if _is_voidgrub_event(ev.get("EventName", "")):
                kills.append(float(ev.get("EventTime", 0) or 0))
        self._voidgrub_kill_times = sorted(kills)

    def _recompute_voidgrubs(self, now: float) -> None:
        if now >= VOIDGRUB_DESPAWN:
            self._voidgrub_done = True
            self._voidgrub_in_pit = False
            return

        kills = self._voidgrub_kill_times

        if now < VOIDGRUB_FIRST_SPAWN:
            self._voidgrub_done = False
            self._voidgrub_in_pit = False
            self._next_voidgrub_spawn = VOIDGRUB_FIRST_SPAWN
            return

        w1 = kills[:3]
        if len(w1) < 3:
            self._voidgrub_done = False
            self._voidgrub_in_pit = True
            self._next_voidgrub_spawn = VOIDGRUB_FIRST_SPAWN
            return

        w1_end = w1[2]
        w2 = kills[3:6]
        can_have_wave2 = w1_end < VOIDGRUB_SECOND_WAVE_DEADLINE

        if can_have_wave2 and len(w2) < 3:
            w2_spawn = w1_end + VOIDGRUB_RESPAWN
            if now < w2_spawn:
                self._voidgrub_done = False
                self._voidgrub_in_pit = False
                self._next_voidgrub_spawn = w2_spawn
            else:
                self._voidgrub_done = False
                self._voidgrub_in_pit = True
                self._next_voidgrub_spawn = w2_spawn
            return

        self._voidgrub_done = True
        self._voidgrub_in_pit = False

    def _dragon_objective_key(self) -> str:
        return "elder" if self._elder_phase else "dragon"

    def _clear_dragon_alerts(self) -> None:
        self._alerted.discard("dragon")
        self._alerted.discard("elder")
        self._ward_alerted.discard("ward_dragon")
        self._ward_alerted.discard("ward_elder")

    def _register_dragon_kill(
        self,
        kill_time: float,
        dragon_type: str,
        killer: str,
        game_data: dict,
    ) -> None:
        if _is_elder_dragon(dragon_type):
            self._elder_phase = True
            self._next_dragon = kill_time + ELDER_DRAGON_RESPAWN
        else:
            team = _killer_team(game_data, killer)
            if team:
                self._dragon_counts[team] = self._dragon_counts.get(team, 0) + 1
                if self._dragon_counts[team] >= DRAGON_SOUL_COUNT:
                    self._elder_phase = True
                    self._next_dragon = kill_time + ELDER_DRAGON_RESPAWN
                else:
                    self._next_dragon = kill_time + DRAGON_RESPAWN
            else:
                self._next_dragon = kill_time + DRAGON_RESPAWN

        self._dragon_in_pit = False
        self._clear_dragon_alerts()

    def _replay_dragon_history(self, game_data: dict) -> None:
        self._dragon_counts = {}
        self._elder_phase = False
        self._next_dragon = DRAGON_FIRST_SPAWN
        self._dragon_in_pit = False

        dragon_events = sorted(
            (
                ev
                for ev in game_data.get("events", {}).get("Events", [])
                if ev.get("EventName") == "DragonKill"
            ),
            key=lambda ev: float(ev.get("EventTime", 0) or 0),
        )
        for ev in dragon_events:
            self._register_dragon_kill(
                float(ev.get("EventTime", 0) or 0),
                ev.get("DragonType", ""),
                ev.get("KillerName", "?"),
                game_data,
            )

    def _bootstrap(self, game_data: dict) -> None:
        if self._bootstrapped:
            return
        self._bootstrapped = True

        for ev in game_data.get("events", {}).get("Events", []):
            name = ev.get("EventName")
            t = float(ev.get("EventTime", 0) or 0)
            if name == "BaronKill":
                self._next_baron = t + BARON_RESPAWN
            elif name == "HeraldKill":
                self._herald_done = True
            elif _is_voidgrub_event(name or ""):
                if t not in self._voidgrub_kill_times:
                    self._voidgrub_kill_times.append(t)

        self._voidgrub_kill_times.sort()
        self._replay_dragon_history(game_data)

        now = game_time(game_data)
        if now >= BARON_SPAWN_ENDS_HERALD:
            self._herald_done = True

        self._recompute_voidgrubs(now)

    def dragon_score(self, my_team: str | None) -> tuple[int, int]:
        """(dragões do seu time, dragões inimigos) — elementais apenas."""
        if not my_team:
            return 0, 0
        us = self._dragon_counts.get(my_team, 0)
        them = sum(
            count for team, count in self._dragon_counts.items()
            if team != my_team
        )
        return us, them

    @property
    def elder_phase(self) -> bool:
        return self._elder_phase

    def alerts_from_dragon_events(
        self,
        events: list[dict],
        my_team: str | None,
    ) -> list[dict]:
        """Fala o placar quando um dragão elemental cai."""
        alerts = []
        for ev in events:
            if ev.get("type") != "dragon":
                continue
            if _is_elder_dragon(ev.get("dragon_type", "")):
                continue
            us, them = self.dragon_score(my_team)
            alerts.append({
                "type": "dragon_score",
                "us": us,
                "them": them,
            })
        return alerts

    def observe_events(self, events: list[dict], game_data: dict) -> None:
        self._bootstrap(game_data)
        now = game_time(game_data)

        for ev in events:
            t = ev.get("type")
            if t == "dragon":
                kill_time = float(ev.get("event_time", now) or now)
                self._register_dragon_kill(
                    kill_time,
                    ev.get("dragon_type", ""),
                    ev.get("killer", "?"),
                    game_data,
                )
            elif t == "baron":
                kill_time = float(ev.get("event_time", now) or now)
                self._next_baron = kill_time + BARON_RESPAWN
                self._alerted.discard("baron")
                self._ward_alerted.discard("ward_baron")
            elif t == "herald":
                self._herald_done = True
                self._alerted.discard("herald")
                self._ward_alerted.discard("ward_herald")
            elif t == "voidgrub":
                kill_time = float(ev.get("event_time", now) or now)
                if kill_time not in self._voidgrub_kill_times:
                    self._voidgrub_kill_times.append(kill_time)
                    self._voidgrub_kill_times.sort()
                self._alerted.discard("voidgrub")
                self._ward_alerted.discard("ward_voidgrub")

        self._recompute_voidgrubs(now)

    def _sync_state(self, game_data: dict) -> float:
        self._bootstrap(game_data)
        now = game_time(game_data)

        if now >= BARON_SPAWN_ENDS_HERALD:
            self._herald_done = True

        if not self._dragon_in_pit and now >= self._next_dragon:
            self._dragon_in_pit = True

        self._recompute_voidgrubs(now)

        return now

    def available_objectives(self, game_data: dict) -> list[str]:
        """Objetivos neutros que estão no mapa agora (não só prestes a nascer)."""
        now = self._sync_state(game_data)
        available = []

        if self._dragon_in_pit:
            available.append(self._dragon_objective_key())

        if self._voidgrub_in_pit and not self._voidgrub_done:
            available.append("voidgrub")

        if (
            not self._herald_done
            and now < BARON_SPAWN_ENDS_HERALD
            and now >= self._next_herald
        ):
            available.append("herald")

        if now >= self._next_baron:
            available.append("baron")

        return available

    def update(self, game_data: dict) -> list[dict]:
        now = self._sync_state(game_data)
        alerts = []

        if not self._dragon_in_pit:
            dragon_key = self._dragon_objective_key()
            alerts.extend(
                self._pre_spawn_alerts(dragon_key, self._next_dragon, now, OBJECTIVE_WARD_SECONDS)
            )

        if not self._voidgrub_done and not self._voidgrub_in_pit:
            alerts.extend(
                self._pre_spawn_alerts("voidgrub", self._next_voidgrub_spawn, now, VOIDGRUB_WARD_SECONDS)
            )

        if not self._herald_done and now < BARON_SPAWN_ENDS_HERALD:
            alerts.extend(
                self._pre_spawn_alerts("herald", self._next_herald, now, OBJECTIVE_WARD_SECONDS)
            )

        alerts.extend(
            self._pre_spawn_alerts("baron", self._next_baron, now, OBJECTIVE_WARD_SECONDS)
        )

        return alerts

    def _pre_spawn_alerts(
        self,
        objective: str,
        spawn_at: float,
        now: float,
        ward_seconds: int,
    ) -> list[dict]:
        out = []
        remaining = int(spawn_at - now)
        if remaining <= 0:
            return out

        ward_key = f"ward_{objective}"
        if (
            ward_seconds
            and remaining <= ward_seconds
            and ward_key not in self._ward_alerted
        ):
            self._ward_alerted.add(ward_key)
            out.append({
                "type": "objective_ward",
                "objective": objective,
                "seconds": remaining,
            })

        spawn = self._spawn_alert(objective, spawn_at, now)
        if spawn:
            out.append(spawn)

        return out

    def _spawn_alert(self, objective: str, spawn_at: float, now: float) -> dict | None:
        remaining = int(spawn_at - now)
        if remaining <= 0 or remaining > OBJECTIVE_SPAWN_ALERT_SECONDS:
            return None
        if objective in self._alerted:
            return None
        self._alerted.add(objective)
        return {"type": "objective_spawn", "objective": objective, "seconds": remaining}
