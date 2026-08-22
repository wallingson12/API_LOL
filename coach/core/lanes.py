"""
lanes.py — Mapeamento de estruturas Riot (L0/L1/L2) e rótulos falados.
"""

import re

# Riot: L0=bot, L1=mid, L2=top (lol-livegame-client Constants)
STRUCTURE_LANE_MAP: dict[str, str] = {
    "L0": "bot",
    "L1": "mid",
    "L2": "top",
    "R": "top",
    "C": "mid",
    "L": "bot",
}

LANES: tuple[str, ...] = ("top", "mid", "bot")

LANE_SPOKEN: dict[str, str] = {
    "top": "top",
    "mid": "mid",
    "bot": "bot",
}


def parse_lane_from_structure_id(structure_id: str) -> str:
    lane_match = re.search(r"_(L[0-2])_", structure_id)
    if lane_match:
        return STRUCTURE_LANE_MAP.get(lane_match.group(1), "?")
    short_lane_match = re.search(r"_([RCL])_", structure_id)
    if short_lane_match:
        return STRUCTURE_LANE_MAP.get(short_lane_match.group(1), "?")
    return "?"


def lane_label(lane: str | None) -> str:
    if not lane:
        return "?"
    return LANE_SPOKEN.get(lane.lower(), lane.lower())
