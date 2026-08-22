"""
roles.py — Fonte única de mapeamento de posição/rota (API, LCU, fala).
"""

# Posição bruta da Live Client / LCU → papel ingame
API_POSITION_TO_INGAME: dict[str, str] = {
    "TOP": "top",
    "JUNGLE": "jungler",
    "MIDDLE": "mid",
    "MID": "mid",
    "BOTTOM": "adc",
    "BOT": "adc",
    "UTILITY": "suporte",
    "SUPPORT": "suporte",
}

# Aliases de entrada (LCU, strings variadas)
POSITION_ALIASES: dict[str, str] = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "JGL": "JUNGLE",
    "MIDDLE": "MIDDLE",
    "MID": "MIDDLE",
    "BOTTOM": "BOTTOM",
    "BOT": "BOTTOM",
    "ADC": "BOTTOM",
    "UTILITY": "UTILITY",
    "SUPPORT": "UTILITY",
    "SUP": "UTILITY",
    "SUPORTE": "UTILITY",
}

# Rótulos para TTS
POSITION_SPOKEN: dict[str, str] = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "mid",
    "MID": "mid",
    "BOTTOM": "adc",
    "BOT": "bot",
    "UTILITY": "suporte",
    "SUPPORT": "suporte",
    "top": "top",
    "mid": "mid",
    "bot": "bot",
    "adc": "adc",
    "suporte": "suporte",
    "jungler": "jungle",
}

# Papel ingame → lane (para alertas de feed)
ROLE_TO_LANE: dict[str, str] = {
    "top": "top",
    "mid": "mid",
    "adc": "bot",
    "suporte": "bot",
}

# Subconjunto falado no narrator (respawn)
ROLE_SPOKEN: dict[str, str] = {
    "adc": "adc",
    "suporte": "suporte",
    "top": "top",
    "mid": "mid",
    "jungler": "jungle",
}


def normalize_api_position(raw: str | None) -> str:
    role = (raw or "").strip().upper()
    return POSITION_ALIASES.get(role, role)


def ingame_role_from_api_position(raw: str | None) -> str | None:
    if not raw:
        return None
    return API_POSITION_TO_INGAME.get(normalize_api_position(raw))


def ingame_role_from_lcu(lcu_position: str | None) -> str | None:
    return ingame_role_from_api_position(lcu_position)


def position_label(raw: str | None) -> str:
    if not raw:
        return "?"
    normalized = normalize_api_position(raw)
    if normalized in POSITION_SPOKEN:
        return POSITION_SPOKEN[normalized]
    lower = raw.strip().lower()
    return POSITION_SPOKEN.get(lower, lower)


def role_spoken(role: str | None) -> str:
    if not role:
        return "inimigo"
    return ROLE_SPOKEN.get(role, role)
