"""Rótulos de posição e lane para TTS — delega para core/."""

from core.lanes import lane_label
from core.roles import (
    POSITION_SPOKEN,
    normalize_api_position,
    position_label,
)

__all__ = [
    "lane_label",
    "normalize_lane_role",
    "position_label",
    "POSITION_SPOKEN",
    "LANE_SPOKEN",
]


def normalize_lane_role(raw: str) -> str:
    return normalize_api_position(raw)


LANE_SPOKEN = {
    "top": "top",
    "mid": "mid",
    "bot": "bot",
}
