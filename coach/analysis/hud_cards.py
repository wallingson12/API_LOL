"""Cartões escritos do HUD (consulta, não TTS)."""

from __future__ import annotations

from data.champion_data import get_champion_profile_by_name
from data.knowledge import (
    WAVE_TIPS,
    format_dragon_body,
    rune_suggestion_for_tags,
)
from data.notices import get_champion_note


def build_hud_cards(
    *,
    my_role: str | None,
    my_champion: str | None,
    opponent_name: str | None,
    dragon_key: str | None,
    elder_phase: bool,
    ward_hud: dict | None = None,
) -> list[dict]:
    cards: list[dict] = []

    opp_card = _opponent_card(opponent_name, my_champion)
    if opp_card:
        cards.append(opp_card)

    rune_card = _rune_card(my_champion, opponent_name)
    if rune_card:
        cards.append(rune_card)

    cards.append(_dragon_card(dragon_key, elder_phase))

    ward_card = _ward_live_card(ward_hud)
    if ward_card:
        cards.append(ward_card)

    if my_role and my_role != "jungler":
        cards.append({
            "id": "wave",
            "title": "Wave",
            "body": " ".join(item["body"] for item in WAVE_TIPS[:2]),
            "kind": "info",
        })

    return [c for c in cards if (c.get("body") or "").strip()]


def _opponent_card(opponent_name: str | None, my_champion: str | None) -> dict | None:
    if not opponent_name:
        return None
    user = get_champion_note(opponent_name)
    profile = get_champion_profile_by_name(opponent_name) or {}
    official = list(profile.get("enemy_tips") or [])
    parts = []
    if user.get("danger_tip"):
        parts.append(user["danger_tip"])
    elif profile.get("danger_tip"):
        parts.append(profile["danger_tip"])
    if user.get("notes"):
        parts.append(user["notes"])
    if official:
        parts.append(" ".join(official[:2]))
    if not parts:
        return None
    vs = f"Vs {opponent_name}"
    if my_champion:
        vs = f"{my_champion} vs {opponent_name}"
    return {
        "id": "opponent",
        "title": vs,
        "body": " ".join(parts),
        "kind": "warn",
    }


def _rune_card(my_champion: str | None, opponent_name: str | None) -> dict | None:
    user = get_champion_note(my_champion or "")
    if user.get("runes"):
        return {
            "id": "runes",
            "title": f"Runas · {my_champion}",
            "body": user["runes"],
            "kind": "info",
        }
    profile = get_champion_profile_by_name(my_champion or "") if my_champion else None
    sug = rune_suggestion_for_tags((profile or {}).get("tags") or [])
    if not sug:
        return None
    body = (
        f"{sug['primary']} — {sug['keystone']}. "
        f"Secundária: {sug['secondary']}. {sug['note']}"
    )
    if opponent_name:
        opp_note = get_champion_note(opponent_name)
        if opp_note.get("runes"):
            body += f" Vs {opponent_name}: {opp_note['runes']}"
    return {
        "id": "runes",
        "title": f"Runas · {sug['tag']}",
        "body": body,
        "kind": "info",
    }


def _dragon_card(dragon_key: str | None, elder_phase: bool) -> dict:
    if elder_phase:
        key = "elder"
        title = "Ancião"
    elif dragon_key:
        from data.knowledge import DRAGONS
        title = (DRAGONS.get(dragon_key) or {}).get("name") or "Dragão"
        key = dragon_key
    else:
        title = "Dragões"
        key = None
    return {
        "id": "dragon",
        "title": title,
        "body": format_dragon_body(key),
        "kind": "info",
    }


def _ward_live_card(ward_hud: dict | None) -> dict | None:
    if not ward_hud:
        return {
            "id": "ward",
            "title": "Visão",
            "body": (
                "Amarela 90–120s. Rosa até morrer (desativa furtivas). "
                "Azul lv9, 1 HP, de longe. Oráculo ~8s de sweep."
            ),
            "kind": "info",
        }
    parts = []
    charges = ward_hud.get("trinket_charges")
    if charges is not None:
        parts.append(f"Pingente: {charges} carga(s).")
    remaining = ward_hud.get("next_expiry")
    if remaining is not None:
        parts.append(f"Sua amarela acaba em {int(remaining)}s.")
    parts.append("Rosa: pit/bush. Azul: checar objetivo sem andar.")
    return {
        "id": "ward",
        "title": "Visão",
        "body": " ".join(parts),
        "kind": "info",
    }
