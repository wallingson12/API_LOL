"""
spoken.py — Rótulos e números para fala em português natural
"""

import re

from voice.positions import lane_label

TIER_SPOKEN = {
    "T1": "T1",
    "T2": "T2",
    "T3": "T3",
}

_COUNT_WORDS = {
    0: "zero", 1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco",
    6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez",
}

_SECONDS_WORDS = {
    15: "quinze", 30: "trinta", 45: "quarenta e cinco",
    60: "sessenta", 90: "noventa", 120: "cento e vinte",
}


def count_word(value: int) -> str:
    return _COUNT_WORDS.get(value, str(value))


def seconds_word(value: int) -> str:
    return _SECONDS_WORDS.get(value, str(value))


def structure_phrase(ev: dict) -> str:
    lane = lane_label(ev.get("lane", "?"))

    if ev.get("type") == "inhibitor":
        return f"o inibidor do {lane}"

    desc = ev.get("turret_desc", "")
    tier_match = re.match(r"(T[123])", desc)
    tier = tier_match.group(1) if tier_match else None
    tier_word = TIER_SPOKEN.get(tier or "")
    if tier_word:
        return f"a {tier_word} do {lane}"
    return f"a torre do {lane}"
