from data.champion_data import (
    get_champion_name,
    get_champion_profile,
    get_champion_profile_by_name,
    get_champion_class_label,
    is_ranged_champion,
    get_champion_id_by_name,
    RANGED_ATTACK_RANGE,
)


def _resolve_profile(champ_id: int | None, champ_name: str | None) -> tuple[str, dict | None]:
    if champ_id:
        profile = get_champion_profile(champ_id)
        name = get_champion_name(champ_id)
        if profile:
            return name, profile
    if champ_name:
        profile = get_champion_profile_by_name(champ_name)
        if profile:
            return profile.get("name") or champ_name, profile
        return champ_name, None
    return "?", None


def _opponent_fight_style(champ_id: int | None, champ_name: str | None) -> str | None:
    cid = champ_id
    if not cid and champ_name:
        cid = get_champion_id_by_name(champ_name)
    if cid and is_ranged_champion(cid):
        return "ataca de longe."
    profile = get_champion_profile(cid) if cid else get_champion_profile_by_name(champ_name or "")
    if profile:
        if profile.get("attackrange", 125) >= RANGED_ATTACK_RANGE:
            return "ataca de longe."
        return "joga corpo a corpo."
    return None


def _build_lane_advice(champ_id: int | None, champ_name: str | None) -> str:
    classe = get_champion_class_label(champ_id, champ_name)
    style = _opponent_fight_style(champ_id, champ_name)
    if classe and style:
        return f"{classe}. {style[0].upper()}{style[1:]}"
    if classe:
        return f"{classe}."
    if style:
        return style
    return "Respeita o early."


def get_matchup_advice(
    my_champ_id: int | None = None,
    my_champ_name: str | None = None,
    opp_champ_id: int | None = None,
    opp_champ_name: str | None = None,
    my_ingame_role: str | None = None,
) -> tuple[str, str, str] | None:
    """Retorna (meu_nome, oponente_nome, frase curta sobre alcance do oponente)."""
    my_name, _ = _resolve_profile(my_champ_id, my_champ_name)
    opp_name, _ = _resolve_profile(opp_champ_id, opp_champ_name)

    if not opp_name or opp_name == "?":
        return None

    advice = _build_lane_advice(opp_champ_id, opp_champ_name)
    return my_name, opp_name, advice
