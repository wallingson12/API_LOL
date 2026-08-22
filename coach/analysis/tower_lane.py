from core.lanes import LANES
from core.players import find_player, kill_name_matches, player_name
from game.player_match import names_match

def _empty_lane_stats() -> dict[str, int]:
    return {"our_towers": 0, "their_towers": 0, "our_inhibs": 0, "their_inhibs": 0}


def _is_me_killer(killer: str, my_name: str, players: list[dict]) -> bool:
    if not killer or killer == "?" or not my_name:
        return False
    if names_match(killer, my_name):
        return True
    for player in players:
        if not kill_name_matches(killer, player):
            continue
        pname = player_name(player)
        if names_match(pname, my_name) or pname == my_name:
            return True
    return False

class TowerLaneTracker:
    """Rastreia torres/inibidores por rota e gera alertas táticos."""

    def __init__(self):
        self._we_lost_on_lane: set[str] = set()
        self._they_lost_on_lane: set[str] = set()
        self._sides_alerted: set[str] = set()
        self._first_tower_lost_alerted = False
        self._lane_stats: dict[str, dict[str, int]] = {
            lane: _empty_lane_stats() for lane in LANES
        }
        self._first_structure_fallen = False

    def reset(self):
        self._we_lost_on_lane.clear()
        self._they_lost_on_lane.clear()
        self._sides_alerted.clear()
        self._first_tower_lost_alerted = False
        self._lane_stats = {lane: _empty_lane_stats() for lane in LANES}
        self._first_structure_fallen = False

    def enemy_inhib_destroyed(self) -> bool:
        return any(stats["their_inhibs"] > 0 for stats in self._lane_stats.values())

    def _is_our_structure(self, structure_team: str | None, my_team: str | None) -> bool:
        if not structure_team or not my_team:
            return False
        return structure_team.upper() == my_team.upper()

    def observe_events(self, events: list[dict], my_team: str | None) -> None:
        for ev in events:
            if ev.get("type") not in ("turret", "inhibitor"):
                continue
            self._record_structure(ev, my_team)

    def _record_structure(self, ev: dict, my_team: str | None) -> None:
        lane = ev.get("lane")
        if lane not in LANES:
            return

        ours = self._is_our_structure(ev.get("structure_team"), my_team)
        stats = self._lane_stats[lane]
        if ev.get("type") == "turret":
            if ours:
                stats["our_towers"] += 1
            else:
                stats["their_towers"] += 1
            self._first_structure_fallen = True
        elif ev.get("type") == "inhibitor":
            if ours:
                stats["our_inhibs"] += 1
            else:
                stats["their_inhibs"] += 1
            self._first_structure_fallen = True

    def alerts_from_events(
        self,
        events: list[dict],
        my_team: str | None,
        my_name: str,
        my_role: str | None = None,
        game_data: dict | None = None,
    ) -> list[dict]:
        if not my_team:
            return []

        players = (game_data or {}).get("allPlayers") or []
        out = []

        for ev in events:
            if ev.get("type") not in ("turret", "inhibitor"):
                continue

            lane = ev.get("lane")
            if not lane or lane == "?":
                continue

            ours = self._is_our_structure(ev.get("structure_team"), my_team)

            if ev.get("type") != "turret":
                continue

            killer = ev.get("killer", "?")
            i_destroyed_enemy = not ours and _is_me_killer(killer, my_name, players)
            if i_destroyed_enemy:
                out.append({
                    "type": "tower_taken_recall",
                    "lane": lane,
                    "turret_desc": ev.get("turret_desc", ""),
                })

            if ours:
                self._we_lost_on_lane.add(lane)
                if (
                    not self._first_tower_lost_alerted
                    and lane not in self._they_lost_on_lane
                ):
                    self._first_tower_lost_alerted = True
                    out.append({
                        "type": "tower_lost_first",
                        "lane": lane,
                    })
                continue

            self._they_lost_on_lane.add(lane)
            if lane not in self._we_lost_on_lane:
                self._sides_alerted.add(lane)
        return out
