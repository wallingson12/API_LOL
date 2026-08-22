from data.champion_data import (
    is_ranged_champion,
    champion_has_tag,
)
from analysis.lane_matchup import get_matchup_advice
from analysis.enemy_tips import pick_enemy_tip_for_tts
from analysis.matchup_dangers import pick_danger_tip_for_tts
from analysis.role_resolve import ingame_role_from_lcu
from voice.positions import normalize_lane_role, position_label

# Re-export para lcu_client e outros módulos
__all__ = ["normalize_lane_role", "build_pregame_lines", "build_ingame_briefing_lines"]


def _count_ranged(champ_ids: list[int]) -> int:
    return sum(1 for cid in champ_ids if is_ranged_champion(cid))


def _team_has_tag(champ_ids: list[int], tag: str) -> bool:
    return any(champion_has_tag(cid, tag) for cid in champ_ids)


def build_lane_matchup_line(
    my_role: str,
    my_champ_id: int | None = None,
    my_champ_name: str | None = None,
    opponent_id: int | None = None,
    opponent_name: str | None = None,
    my_ingame_role: str | None = None,
) -> tuple[str, str] | None:
    """Briefing da lane: classe, alcance e enemytip em uma fala."""
    role = normalize_lane_role(my_role)
    if not role or role == "JUNGLE":
        return None
    if not opponent_id and not opponent_name:
        return None

    ingame = my_ingame_role or ingame_role_from_lcu(my_role) or ingame_role_from_lcu(role)
    matchup = get_matchup_advice(
        my_champ_id=my_champ_id,
        my_champ_name=my_champ_name,
        opp_champ_id=opponent_id,
        opp_champ_name=opponent_name,
        my_ingame_role=ingame,
    )
    if not matchup:
        return None

    my_name, opp_name, advice = matchup
    key_id = opponent_id or opp_name or "?"
    text = f"{opp_name}, {advice}"

    tip = pick_danger_tip_for_tts(opponent_id, opponent_name)
    if not tip:
        tip = pick_enemy_tip_for_tts(opponent_id, opponent_name)
    if tip:
        text = f"{text} {tip}"

    return text, f"lane_briefing_{key_id}_{role}_{my_champ_id or my_name}"


def _append_extras(lines: list[tuple[str, str]], ctx: dict) -> None:
    ally_ids = ctx.get("ally_champ_ids") or []
    enemy_ids = ctx.get("enemy_champ_ids") or []

    ally_count = len(ally_ids)
    if ally_count >= 4 and not _team_has_tag(ally_ids, "Tank"):
        if ally_count >= 5:
            text = "Seu time não tem tanque."
        else:
            text = "Seu time ainda não tem tanque."
        lines.append((text, f"no_tank_{'_'.join(map(str, sorted(ally_ids)))}"))

    ally_ranged = _count_ranged(ally_ids)
    enemy_ranged = _count_ranged(enemy_ids)
    if enemy_ids and enemy_ranged > ally_ranged:
        lines.append((
            "Inimigos têm mais campeões de longo alcance. Respeite distância segura.",
            f"ranged_adv_{enemy_ranged}_vs_{ally_ranged}",
        ))
    elif ally_ids and enemy_ids and ally_ranged > enemy_ranged:
        lines.append((
            "Seu time tem mais alcance. Aproveite para punir quando eles se aproximarem.",
            f"ranged_us_{ally_ranged}_vs_{enemy_ranged}",
        ))


def build_pregame_lines(ctx: dict) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []

    my_champ_id = ctx.get("my_champ_id")
    my_position = normalize_lane_role(ctx.get("my_position") or "")

    lane_line = build_lane_matchup_line(
        my_position,
        my_champ_id=my_champ_id,
        opponent_id=ctx.get("lane_opponent_id"),
        opponent_name=ctx.get("lane_opponent_name"),
    )
    if not lane_line:
        return lines

    lines.append(lane_line)
    _append_extras(lines, ctx)
    return lines


def build_ingame_briefing_lines(
    my_role: str | None,
    my_champ_name: str | None,
    lane_opponent_name: str | None,
    my_ingame_role: str | None = None,
) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    if my_role and lane_opponent_name and my_champ_name:
        lane_line = build_lane_matchup_line(
            my_role,
            my_champ_name=my_champ_name,
            opponent_name=lane_opponent_name,
            my_ingame_role=my_ingame_role,
        )
        if lane_line:
            lines.append(lane_line)
    return lines
