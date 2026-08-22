
def advantage_action(
    game_time: float,
    available: list[str],
    enemy_inhib_destroyed: bool = False,
) -> str:
    """Uma palavra ou frase curta. Falada separado do placar."""
    avail = set(available)

    if game_time >= 1200:
        if "baron" in avail:
            return "Barão."
        if "elder" in avail:
            return "Dragão ancião."
        if "dragon" in avail:
            return "Dragão."
        if enemy_inhib_destroyed:
            return "Feche o jogo."

    if game_time >= 840:
        if "herald" in avail:
            return "Arauto."
        if "elder" in avail:
            return "Dragão ancião."
        if "dragon" in avail:
            return "Dragão."
        return "Ataque torre."

    if game_time >= 300:
        if "voidgrub" in avail:
            return "Larvas."
        if "dragon" in avail:
            return "Dragão."
        return "Ataque torre."

    return "Fique na rota."
