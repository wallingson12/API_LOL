"""
narrator.py — Converte eventos/alertas em frases faladas em PT-BR
"""

import re

from core.lanes import lane_label
from core.players import find_player
from core.roles import role_spoken
from voice.spoken import count_word, seconds_word, structure_phrase

_NON_PLAYER_PREFIXES = (
    "Minion_", "OrderMinion_", "ChaosMinion_", "Turret_", "SRU_", "HA_", "TT_",
    "Inhibitor_", "Baron_", "Dragon_", "Herald_",
)


def _is_player_killer(killer: str) -> bool:
    if not killer or killer == "?":
        return False
    return not any(killer.startswith(prefix) for prefix in _NON_PLAYER_PREFIXES)


def _is_our_structure(structure_team: str | None, my_team: str | None) -> bool:
    if not structure_team or not my_team:
        return False
    return structure_team.upper() == my_team.upper()


def _structure_short(label: str) -> str:
    return label[2:] if label.startswith("a ") else label


def _narrate_structure_destroyed(
    ev: dict,
    my_name: str,
    my_team: str | None,
    all_players: list[dict] | None = None,
) -> str | None:
    killer = ev.get("killer", "?")
    lane = ev.get("lane", "?")
    lane_name = lane_label(lane)
    label = structure_phrase(ev)
    ours = _is_our_structure(ev.get("structure_team"), my_team)
    players = all_players or []

    killer_player = find_player(players, killer) if players else None
    if killer_player and my_team:
        pname = killer_player.get("riotIdGameName") or killer_player.get("summonerName")
        if pname == my_name:
            if ours:
                return f"Você perdeu {label}."
            return None
        if killer_player.get("team") == my_team:
            if ours:
                return f"Aliado perdeu {label}."
            return f"Aliado destruiu {label} inimiga."
        if ours:
            return f"Inimigo destruiu {label}."
        return f"Inimigo perdeu {label}."

    if killer == my_name:
        if ours:
            return f"Você perdeu {label}."
        return None

    if _is_player_killer(killer):
        if ours:
            return f"Inimigo destruiu {label}."
        return f"Inimigo perdeu {label}."

    if ours:
        short = _structure_short(label)
        return f"Sua {short} caiu. Defenda o {lane_name}."

    return f"Torre inimiga {label} caiu."


def narrate_event(
    ev: dict,
    my_name: str,
    my_team: str | None = None,
    all_players: list[dict] | None = None,
) -> str | None:
    t = ev["type"]

    if t == "turret":
        return _narrate_structure_destroyed(ev, my_name, my_team, all_players)

    if t == "inhibitor":
        return _narrate_structure_destroyed(ev, my_name, my_team, all_players)

    if t == "player_respawned":
        return None

    if t == "gold_threshold":
        if ev.get("gold") == 1000:
            return "Volte à base. Aperte Tab e veja os itens inimigos."
        return None

    return None


def narrate_respawn(ev: dict, my_role: str | None) -> tuple[str, str] | None:
    """Só caçador inimigo e oponente de lane."""
    if ev.get("type") != "player_respawned" or not ev.get("is_enemy"):
        return None

    role = ev.get("role")
    player = ev.get("player", "?")

    if role == "jungler":
        return ("Jungle inimigo voltou.", "respawn_jg")

    if my_role and my_role != "jungler" and role == my_role:
        label = role_spoken(role)
        return (f"O {label} inimigo voltou.", f"respawn_{role}_{player}")

    return None


def narrate_alert(alert: dict) -> tuple[str, str] | None:
    t = alert["type"]

    if t == "num_advantage":
        allies = alert.get("allies_alive", 0)
        enemies = alert.get("enemies_alive", 0)
        # Só o placar — objetivo já tem alerta próprio de spawn (evita "Larvas/Arauto" a cada luta)
        if enemies == 0:
            text = f"{count_word(allies)} a zero."
        else:
            text = f"{count_word(allies)} a {count_word(enemies)}."
        return (text, f"num_adv_{allies}_{enemies}")

    if t == "dragon_score":
        us = int(alert.get("us", 0) or 0)
        them = int(alert.get("them", 0) or 0)
        if them == 0:
            text = f"Dragões: {count_word(us)} a zero."
        else:
            text = f"Dragões: {count_word(us)} a {count_word(them)}."
        return (text, f"dragon_score_{us}_{them}")

    if t == "enemy_jg_dead_gank":
        if alert.get("is_jungler"):
            return (
                "Jungle caiu. Pegue objetivo.",
                f"jg_dead_{alert['victim']}",
            )
        return (
            "Jungle caiu. Pressione.",
            f"jg_gank_{alert['victim']}",
        )

    if t == "jg_look_lanes":
        messages = (
            "Olhe as rotas.",
            "Olhe top, mid e bot.",
        )
        variant = int(alert.get("variant", 0)) % len(messages)
        return (messages[variant], "jg_look_lanes")

    if t == "jg_objective_up":
        labels = {
            "dragon": "Dragão no mapa.",
            "elder": "Dragão ancião no mapa.",
            "herald": "Arauto no top.",
            "baron": "Barão no mapa.",
            "voidgrub": "Larvas no top.",
        }
        obj = alert.get("objective", "")
        text = labels.get(obj)
        if not text:
            return None
        return (text, f"jg_objective_{obj}")

    if t == "my_death_streak":
        return (
            "Fique calmo e foque em farmar.",
            "my_death_streak",
        )

    if t == "tower_taken_recall":
        desc = alert.get("turret_desc", "")
        match = re.match(r"(T[123]) do (\w+)", desc)
        if match:
            tier, lane_name = match.group(1), match.group(2)
            text = (
                f"Você destruiu a {tier} do {lane_name} inimiga, "
                f"volte base e ajude outra lane."
            )
        else:
            lane_name = lane_label(alert.get("lane", "?"))
            text = (
                f"Você destruiu torre inimiga no {lane_name}, "
                f"volte base e ajude outra lane."
            )
        return (text, f"tower_taken_{alert.get('lane', '?')}")

    if t == "tower_lost_first":
        lane = alert.get("lane", "?")
        lane_name = lane_label(lane)
        return (
            f"Perdemos a primeira torre no {lane_name}. Fique calmo.",
            "tower_lost_first",
        )

    if t == "ward_expiring":
        sec = alert.get("seconds", 15)
        return (
            f"Sua visão amarela acaba em {seconds_word(sec)} segundos.",
            "ward_expiring",
        )

    if t == "trinket_full":
        return (
            "Pingente cheio. Coloque visão no mapa.",
            "trinket_full",
        )

    if t == "ward_place_reminder":
        return (
            "Lembre de colocar visão.",
            "ward_place_reminder",
        )

    if t == "enemy_item_effect":
        text = (alert.get("text") or "").strip()
        if not text:
            return None
        key = alert.get("key") or f"enemy_item_{alert.get('effect')}_{alert.get('champion')}"
        return (text, key)

    if t == "lane_level_danger":
        opp_name = alert.get("opponent_name") or "Oponente"
        gap = int(alert.get("gap", 0) or 0)
        return (
            f"Cuidado: {opp_name} está {count_word(gap)} níveis acima.",
            f"lane_level_{opp_name}_{gap}",
        )

    _OBJECTIVE_LABELS = {
        "dragon": "dragão",
        "elder": "dragão ancião",
        "herald": "arauto",
        "baron": "barão",
        "voidgrub": "larvas",
    }
    _OBJECTIVE_LABELS_TITLE = {
        "dragon": "Dragão",
        "elder": "Dragão ancião",
        "herald": "Arauto",
        "baron": "Barão",
        "voidgrub": "Larvas",
    }
    _OBJECTIVE_SPAWN_VERB = {
        "voidgrub": "aparecem",
    }

    if t == "objective_ward":
        obj = alert["objective"]
        sec = alert["seconds"]
        sec_spoken = seconds_word(int(sec))
        if obj == "voidgrub":
            text = f"Visão nas larvas. Em {sec_spoken} segundos."
        else:
            name = _OBJECTIVE_LABELS.get(obj, "objetivo")
            text = f"Visão no {name}. Em {sec_spoken} segundos."
        return (text, f"ward_{obj}")

    if t == "objective_spawn":
        obj = alert["objective"]
        title = _OBJECTIVE_LABELS_TITLE.get(obj, "Objetivo")
        verb = _OBJECTIVE_SPAWN_VERB.get(obj, "aparece")
        sec_spoken = seconds_word(int(alert["seconds"]))
        return (
            f"{title} {verb} em {sec_spoken} segundos. Pingue no mapa.",
            f"spawn_{obj}",
        )

    return None
