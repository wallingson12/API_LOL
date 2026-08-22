"""
tts_text.py — Ajustes antes do TTS (Maria / System.Speech PT-BR)

Maria soletra se o acento se perde (dragão→dragao) ou se não conhece o léxico.
Usamos fonética estável (dragaum, dragoens) para ela falar a palavra inteira.
"""

import re

from voice.spoken import count_word, seconds_word

# Fonética que a Maria fala como palavra (não soletra letra a letra)
_PHONETIC = (
    (r"\b[Dd]ragões\b", "dragoens"),
    (r"\b[Dd]ragão\b", "dragaum"),
    (r"\b[Dd]ragao\b", "dragaum"),
    (r"\b[Dd]ragoes\b", "dragoens"),
    (r"\b[Bb]arões\b", "baroens"),
    (r"\b[Bb]arão\b", "baraum"),
    (r"\b[Bb]arao\b", "baraum"),
    (r"\b[Aa]ncião\b", "anciaum"),
    (r"\b[Aa]nciao\b", "anciaum"),
    (r"\b[Vv]isões\b", "visoens"),
    (r"\b[Vv]isão\b", "visaum"),
    (r"\b[Vv]isao\b", "visaum"),
)


def normalize_for_tts(text: str) -> str:
    if not text:
        return text

    out = text.strip()

    out = re.sub(r"\s*\((nossa|inimiga|azul|vermelho)\)\.?", "", out, flags=re.IGNORECASE)
    out = re.sub(r"^Há\b", "Faz", out)
    out = re.sub(r"\bHá tempo\b", "Faz tempo", out, flags=re.IGNORECASE)

    replacements = (
        (r"\bward\b", "visão", re.IGNORECASE),
        (r"\bWard\b", "Visão"),
        (r"\btrinket\b", "pingente", re.IGNORECASE),
        (r"\bVolte para a base\b", "Volte à base"),
        (r"\bDragão Ancião\b", "dragão ancião"),
        (r"\bCaçador\b", "jungle"),
        (r"\bcontra\b", "a", re.IGNORECASE),
    )

    for item in replacements:
        if len(item) == 2:
            pattern, repl = item
            flags = 0
        else:
            pattern, repl, flags = item
        out = re.sub(pattern, repl, out, flags=flags)

    out = re.sub(
        r"\b(\d+) a (\d+)\b",
        lambda m: f"{count_word(int(m.group(1)))} a {count_word(int(m.group(2)))}",
        out,
    )
    out = re.sub(
        r"\b(\d+) contra (\d+)\b",
        lambda m: f"{count_word(int(m.group(1)))} a {count_word(int(m.group(2)))}",
        out,
    )
    out = re.sub(
        r"\b(\d+) níveis\b",
        lambda m: f"{count_word(int(m.group(1)))} níveis",
        out,
    )
    out = re.sub(
        r"\bem (\d+) segundos\b",
        lambda m: f"em {seconds_word(int(m.group(1)))} segundos",
        out,
    )

    for pattern, repl in _PHONETIC:
        out = re.sub(pattern, repl, out)

    out = re.sub(r"\s+", " ", out).strip()
    if out and out[-1] not in ".!?":
        out += "."
    return out
