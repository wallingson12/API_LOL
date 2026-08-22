import re

from data.champion_data import get_enemy_tips

_MAX_WORDS = 22
_MAX_SENTENCES = 2


def _clean_tip(text: str) -> str:
    out = re.sub(r"<[^>]+>", "", text or "")
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part[-1] not in ".!?":
            part += "."
        out.append(part)
    return out


def _compact_tip(text: str) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return text.strip()

    selected: list[str] = []
    word_count = 0
    for sentence in sentences[:_MAX_SENTENCES]:
        words = len(sentence.split())
        if word_count + words > _MAX_WORDS and selected:
            break
        selected.append(sentence)
        word_count += words

    return " ".join(selected)


def pick_enemy_tip_for_tts(
    champion_id: int | str | None = None,
    champion_name: str | None = None,
) -> str | None:
    tips = get_enemy_tips(champion_id, champion_name)
    if not tips:
        return None

    candidates = []
    for raw in tips:
        cleaned = _clean_tip(raw)
        if not cleaned:
            continue
        candidates.append(_compact_tip(cleaned))

    if not candidates:
        return None

    return min(candidates, key=len)
