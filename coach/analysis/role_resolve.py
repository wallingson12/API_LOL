from core.roles import ingame_role_from_lcu

from game.events import parse_role





def resolve_my_role(me: dict | None, lcu_position: str | None) -> str | None:

    from_lcu = ingame_role_from_lcu(lcu_position)

    if from_lcu:

        return from_lcu

    return parse_role(me) if me else None





def resolve_lane_opponent(

    enemies: list[dict],

    my_role: str | None,

    lcu_opponent_name: str | None = None,

) -> dict | None:

    if not my_role or my_role == "jungler":

        return None



    if lcu_opponent_name:

        target = lcu_opponent_name.lower()

        for enemy in enemies:

            if (enemy.get("championName") or "").lower() == target:

                return enemy



    for enemy in enemies:

        if parse_role(enemy) == my_role:

            return enemy

    return None

