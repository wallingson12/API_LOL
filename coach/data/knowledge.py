"""
Conhecimento tático de referência (dragões, wards, runas, MID, wave).

Texto para HUD — não para TTS. Editável pela aba Avisos (overrides em user_notices).
"""

from __future__ import annotations

DRAGON_TYPE_MAP: dict[str, str] = {
    "fire": "infernal",
    "infernal": "infernal",
    "water": "ocean",
    "ocean": "ocean",
    "earth": "mountain",
    "mountain": "mountain",
    "air": "cloud",
    "cloud": "cloud",
    "hextech": "hextech",
    "chemtech": "chemtech",
    "elder": "elder",
}

DRAGONS: dict[str, dict] = {
    "infernal": {
        "name": "Infernal",
        "stack": "+3% AD e AP por stack (até 12%).",
        "soul": "Alma: ataques e habilidades explodem em área (dano adaptativo).",
        "rift": "Rift: paredes abrem rotas de flank; cinzas infernais no mapa.",
        "play": "Priorize se o time escala dano. Alma decide teamfight.",
    },
    "mountain": {
        "name": "Montanha",
        "stack": "+6% armadura e RM por stack (até 24%).",
        "soul": "Alma: escudo após ~5s sem tomar dano.",
        "rift": "Rift: novas paredes e gargalos no jungle/pit.",
        "play": "Bom vs burst. Escudo vale se vocês resetam luta, não em all-in contínuo.",
    },
    "ocean": {
        "name": "Oceano",
        "stack": "Regen de vida fora de combate (~2% da vida faltante / 5s).",
        "soul": "Alma: dano em inimigos cura e devolve mana.",
        "rift": "Rift: mais mato e frutos de vida.",
        "play": "Ganha lane longa e siege. Alma favorece luta estendida.",
    },
    "cloud": {
        "name": "Nuvem",
        "stack": "+5% tenacidade a slow e MS fora de combate por stack.",
        "soul": "Alma: MS alto; dispara ainda mais depois da ultimate.",
        "rift": "Rift: zonas de velocidade em buffs/pit; mais flores de visão.",
        "play": "Rotações e engage. Quem tem alma chega primeiro no lado.",
    },
    "hextech": {
        "name": "Hextec",
        "stack": "+5% aceleração de habilidade e velocidade de ataque por stack.",
        "soul": "Alma: raio em cadeia (dano verdadeiro + slow).",
        "rift": "Rift: portais hextec para rotacionar.",
        "play": "Universal. Alma trava posicionamento em 5v5.",
    },
    "chemtech": {
        "name": "Quimiotec",
        "stack": "+6% tenacidade e poder de cura/escudo por stack.",
        "soul": "Alma: abaixo de 50% HP, +13% dano e mitigação.",
        "rift": "Rift: plantas mutadas (visão, dash, fruto).",
        "play": "Anti-CC e comps que lutam feridas. Alma é nula se você já morreu no burst.",
    },
    "elder": {
        "name": "Ancião",
        "stack": "Não empilha. Substitui dragões elementais após a alma.",
        "soul": "Buff: queima e executa abaixo de ~20% HP (duração limitada).",
        "rift": "Nasce ~6 min após a alma / último ancião.",
        "play": "Não lute 50/50 cego. Visão no pit, wave empurrada, numeração.",
    },
}

WARDS: list[dict] = [
    {
        "id": "stealth",
        "name": "Sentinela Furtiva (amarela)",
        "duration": "90–120s (sobe com o nível médio da partida)",
        "use": "Visão invisível, 900 de alcance. Some 2s depois de colocar. Limite 3 no mapa.",
        "when": "River, pixel brush, caminho do jungle. Recoloque antes de expirar.",
    },
    {
        "id": "control",
        "name": "Sentinela de Controle (rosa)",
        "duration": "Até ser destruída (visível)",
        "use": "Revela e desativa wards furtivas e armadilhas. Revela camuflagem. 75 ouro (mais barata no suporte). 1 no mapa por jogador.",
        "when": "Pit de dragão/barão, bush que o inimigo warda, invade.",
    },
    {
        "id": "farsight",
        "name": "Alteração da Visão Distante (azul)",
        "duration": "Até morrer (1 HP, visível). Sem limite de quantidade.",
        "use": "Warda de longe (~4000). Visão menor (500). Não conta no limite de furtivas.",
        "when": "Lv 9+. Checar pit sem andar, cobrir side enquanto você mid/farm.",
    },
    {
        "id": "oracle",
        "name": "Lente do Oráculo (vermelha)",
        "duration": "Varredura ativa ~8s (não é ward)",
        "use": "Revela e desativa visão/armadilhas no cone. Não dá Vision Score sozinha — o abate da ward sim.",
        "when": "Setup de objetivo, invade, entrar em bush contestado. Jungle e suporte priorizam.",
    },
    {
        "id": "faelight",
        "name": "Faelight (superward)",
        "duration": "Herdada da ward + zona extra ~45s no ponto",
        "use": "Pontos no mapa: wardar ali vira visão ampliada (jungle/rotações).",
        "when": "Se o ponto estiver livre, vale mais que um pixel comum.",
    },
]

RUNE_BY_TAG: dict[str, dict] = {
    "Mage": {
        "primary": "Feitiçaria",
        "keystone": "Cometa Arcano · Ágape · Fase",
        "secondary": "Inspiração ou Dominação",
        "note": "Cometa = poke. Ágape = all-in. Fase = kitar / sobreviver gank.",
    },
    "Assassin": {
        "primary": "Dominação",
        "keystone": "Eletrocutar · Predador",
        "secondary": "Precisão ou Feitiçaria",
        "note": "Eletrocutar ganha troca curta. Predador se o plano é rotear, não 1v1 eterno.",
    },
    "Fighter": {
        "primary": "Precisão",
        "keystone": "Conquistador · Ritmo Fatal",
        "secondary": "Determinação ou Dominação",
        "note": "Conquistador em luta longa. Ritmo se você ganha o primeiro auto.",
    },
    "Tank": {
        "primary": "Determinação",
        "keystone": "Aperto dos Mortos-Vivos · Pós-choque",
        "secondary": "Inspiração ou Precisão",
        "note": "Aperto escala. Pós-choque se você prende e explode.",
    },
    "Marksman": {
        "primary": "Precisão",
        "keystone": "Ritmo Fatal · Agilidade · Cometa (raro)",
        "secondary": "Dominação ou Inspiração",
        "note": "Ritmo vs melee. Agilidade se o matchup é farm e scale.",
    },
    "Support": {
        "primary": "Inspiração / Determinação / Feitiçaria",
        "keystone": "Depende do kit (poke, engage, enchanter)",
        "secondary": "A que completa visão, roam ou cura",
        "note": "Engage: Determinação. Poke: Feitiçaria. Enchanter: Inspiração/Feitiçaria.",
    },
}

LANE_MACRO: list[dict] = [
    {
        "id": "side_tower_lost",
        "title": "Primeira torre caiu",
        "body": "Cuidado com rotação. Ward rio e laterais. Não doe a próxima torre de graça.",
    },
    {
        "id": "enemies_collapse",
        "title": "Inimigos vindo na lane",
        "body": "Sem numeração, recua. Limpa debaixo da torre e pede ajuda.",
    },
    {
        "id": "team_hunting",
        "title": "Time só procura luta",
        "body": "Wave, torre, objetivo. Kill sem wave empurrada perde o mapa.",
    },
    {
        "id": "low_mana",
        "title": "Mana baixa",
        "body": "Planeje o recall antes de zerar.",
    },
    {
        "id": "wave_mid",
        "title": "Wave no meio",
        "body": "Não baseie se o inimigo consegue empurrar e bater torre.",
    },
    {
        "id": "wave_your_tower",
        "title": "Wave na sua torre",
        "body": "Fique e farme.",
    },
    {
        "id": "wave_their_tower",
        "title": "Wave na torre inimiga",
        "body": "Janela de recall. Crashou, some.",
    },
    {
        "id": "push_before_base",
        "title": "Antes do recall",
        "body": "Se for seguro, empurra até a torre inimiga.",
    },
    {
        "id": "survive",
        "title": "Sem mana/vida e em perigo",
        "body": "Sobrevive. Baseia.",
    },
]

WAVE_TIPS: list[dict] = [
    {
        "id": "freeze",
        "title": "Freeze perto da torre",
        "body": "Mate os magos/casters aos poucos e deixe melee inimigos vivos. A wave trava no seu lado: você farma seguro e o inimigo anda no range de gank.",
    },
    {
        "id": "last_hit_read",
        "title": "Leia o last-hit inimigo",
        "body": "Olhe o minion aliado prestes a morrer. O oponente vai dar um passo para farmar. Esse é o momento de trade, poke ou recuar — você já sabe onde ele vai estar.",
    },
    {
        "id": "crash",
        "title": "Crash",
        "body": "Empurra até a torre, some (base, ward, roam, jungle). Não fique parado no meio depois de crashar.",
    },
    {
        "id": "slow_push",
        "title": "Slow push",
        "body": "Mate só casters, empilhe 2–3 waves. Crash pesado abre roam ou placa a torre. Não faça isso se o jungle inimigo está sumido do seu lado.",
    },
]


def normalize_dragon_key(raw: str | None) -> str | None:
    if not raw:
        return None
    token = raw.strip().lower()
    if token in DRAGON_TYPE_MAP:
        return DRAGON_TYPE_MAP[token]
    for key, mapped in DRAGON_TYPE_MAP.items():
        if key in token:
            return mapped
    return None


def dragon_card(key: str | None) -> dict | None:
    if not key:
        return None
    data = DRAGONS.get(key)
    if not data:
        return None
    return {"id": key, **data}


def format_dragon_body(key: str | None) -> str:
    data = dragon_card(key)
    if not data:
        return "Dois elementos no começo; o 3º vira o rift. Alma no 4º dragão do mesmo time."
    return " ".join(
        part for part in (data["stack"], data["soul"], data["play"]) if part
    )


def format_ward_reference() -> str:
    lines = []
    for ward in WARDS:
        lines.append(f"{ward['name']} — {ward['duration']}. {ward['use']}")
    return "\n".join(lines)


def rune_suggestion_for_tags(tags: list[str] | None) -> dict | None:
    if not tags:
        return None
    for tag in tags:
        if tag in RUNE_BY_TAG:
            return {"tag": tag, **RUNE_BY_TAG[tag]}
    return None
