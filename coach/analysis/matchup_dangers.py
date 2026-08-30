"""
matchup_dangers.py — Dicas curtas de perigo por campeão inimigo (TTS-friendly).
Fonte: campo danger_tip em champions.json
"""

from data.champion_data import get_champion_profile, get_champion_profile_by_name
from data.notices import get_champion_note


def pick_danger_tip_for_tts(
    champion_id: int | str | None = None,
    champion_name: str | None = None,
) -> str | None:
    """Dica curta de perigo do oponente."""
    profile = None
    if champion_id:
        profile = get_champion_profile(champion_id)
    if not profile and champion_name:
        profile = get_champion_profile_by_name(champion_name)
    name = champion_name or (profile or {}).get("name") or ""
    user = get_champion_note(name)
    if user.get("danger_tip"):
        return user["danger_tip"]
    if not profile:
        return None
    tip = profile.get("danger_tip")
    return tip if tip else None
