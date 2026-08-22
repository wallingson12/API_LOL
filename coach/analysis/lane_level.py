from config import LANE_LEVEL_DANGER_GAP

from analysis.role_resolve import resolve_my_role, resolve_lane_opponent

from game.events import parse_role





def _find_lane_opponent(

    me: dict,

    enemies: list[dict],

    lcu_position: str | None,

    lcu_opponent_name: str | None,

) -> dict | None:

    my_role = resolve_my_role(me, lcu_position)

    if not my_role or my_role == "jungler":

        return None



    if lcu_opponent_name:

        opponent = resolve_lane_opponent(enemies, my_role, lcu_opponent_name)

        if opponent:

            return opponent



    # Sem rota da LCU não chuta — a Live Client erra rota (ex.: support como mid).

    if not lcu_position:

        return None



    matches = [enemy for enemy in enemies if parse_role(enemy) == my_role]

    if len(matches) == 1:

        return matches[0]

    return None





class LaneLevelTracker:

    def __init__(self):

        self._alerted = False

        self._alerted_opponent: str | None = None



    def reset(self):

        self._alerted = False

        self._alerted_opponent = None



    def analyze(

        self,

        me: dict,

        enemies: list[dict],

        lcu_position: str | None = None,

        lcu_opponent_name: str | None = None,

    ) -> dict | None:

        opponent = _find_lane_opponent(me, enemies, lcu_position, lcu_opponent_name)

        if not opponent:

            return None



        opp_name = opponent.get("championName") or "?"

        gap = int(opponent.get("level", 1) or 1) - int(me.get("level", 1) or 1)

        if gap < LANE_LEVEL_DANGER_GAP:

            self._alerted = False

            self._alerted_opponent = None

            return None



        if self._alerted and self._alerted_opponent == opp_name:

            return None



        self._alerted = True

        self._alerted_opponent = opp_name

        my_role = resolve_my_role(me, lcu_position) or parse_role(me) or "lane"

        return {

            "type": "lane_level_danger",

            "position": my_role,

            "opponent_name": opp_name,

            "gap": gap,

        }


