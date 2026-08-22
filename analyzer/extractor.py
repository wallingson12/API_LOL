from datetime import datetime, timezone

from item_names import item_name


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def _fase(minuto: int) -> str:
    if minuto < 15:   return "Early"
    elif minuto < 25: return "Mid"
    return "Late"


def _nome_jogador(p: dict) -> str:
    return p.get("riotIdGameName") or p.get("summonerName") or "?"


# ─────────────────────────────────────────
# TIMELINE — snapshots + eventos
# ─────────────────────────────────────────
def extrair_timeline(timeline: dict, participant_id: int) -> dict:
    """Snapshots de gold/CS/XP aos 10/15/20min + kills/mortes por fase."""
    if not timeline:
        return {}

    frames     = timeline.get("info", {}).get("frames", [])
    gold_snap  = {}
    cs_snap    = {}
    xp_snap    = {}
    kills_fase = {"Early": 0, "Mid": 0, "Late": 0}
    mortes_fase = {"Early": 0, "Mid": 0, "Late": 0}

    for frame in frames:
        minuto = frame["timestamp"] // 60000
        pf     = frame.get("participantFrames", {}).get(str(participant_id), {})
        if pf:
            for snap in [10, 15, 20]:
                if minuto == snap:
                    gold_snap[snap] = pf.get("totalGold", 0)
                    cs_snap[snap]   = pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0)
                    xp_snap[snap]   = pf.get("xp", 0)

        for evento in frame.get("events", []):
            if evento.get("type") == "CHAMPION_KILL":
                fase = _fase(minuto)
                if evento.get("killerId") == participant_id:
                    kills_fase[fase] += 1
                if evento.get("victimId") == participant_id:
                    mortes_fase[fase] += 1

    return {
        "Gold@10":      gold_snap.get(10, "-"),
        "Gold@15":      gold_snap.get(15, "-"),
        "Gold@20":      gold_snap.get(20, "-"),
        "CS@10":        cs_snap.get(10, "-"),
        "CS@15":        cs_snap.get(15, "-"),
        "XP@10":        xp_snap.get(10, "-"),
        "XP@15":        xp_snap.get(15, "-"),
        "Kills Early":  kills_fase["Early"],
        "Kills Mid":    kills_fase["Mid"],
        "Kills Late":   kills_fase["Late"],
        "Mortes Early": mortes_fase["Early"],
        "Mortes Mid":   mortes_fase["Mid"],
        "Mortes Late":  mortes_fase["Late"],
    }


def extrair_eventos_mortes(match: dict, timeline: dict) -> list[dict]:
    """Todos os eventos CHAMPION_KILL com posição X/Y e contexto completo."""
    if not timeline or not match:
        return []

    info         = match["info"]
    match_id     = match["metadata"]["matchId"]
    participants = {p["participantId"]: p for p in info["participants"]}
    frames       = timeline.get("info", {}).get("frames", [])
    ts           = info.get("gameStartTimestamp", 0)
    data_partida = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%d/%m/%Y %H:%M") if ts else "-"
    eventos      = []

    for frame in frames:
        minuto = frame["timestamp"] // 60000
        for evento in frame.get("events", []):
            if evento.get("type") != "CHAMPION_KILL":
                continue

            killer_id = evento.get("killerId", 0)
            victim_id = evento.get("victimId", 0)
            pos       = evento.get("position", {})
            killer_p  = participants.get(killer_id, {})
            victim_p  = participants.get(victim_id, {})

            assistentes = [
                participants.get(a, {}).get("championName", "?")
                for a in evento.get("assistingParticipantIds", [])
            ]

            eventos.append({
                "Partida":         match_id,
                "Data":            data_partida,
                "Minuto":          minuto,
                "Fase":            _fase(minuto),
                "X":               pos.get("x", 0),
                "Y":               pos.get("y", 0),
                "Killer":          _nome_jogador(killer_p),
                "Killer_Campeão":  killer_p.get("championName", "?"),
                "Killer_Time":     "Azul" if killer_p.get("teamId") == 100 else "Vermelho",
                "Killer_Vitória":  "✅" if killer_p.get("win") else "❌",
                "Victim":          _nome_jogador(victim_p),
                "Victim_Campeão":  victim_p.get("championName", "?"),
                "Victim_Time":     "Azul" if victim_p.get("teamId") == 100 else "Vermelho",
                "Assistentes":     ", ".join(assistentes),
                "Duração_Partida": round(info["gameDuration"] / 60, 1),
            })

    return eventos


# ─────────────────────────────────────────
# STATS COMPLETOS POR PARTICIPANTE
# ─────────────────────────────────────────
def extrair_stats_participante(match: dict, timeline: dict, jogador: dict) -> dict:
    """Extrai TODOS os campos disponíveis da API para um participante."""
    info         = match["info"]
    participants = info["participants"]
    duracao_min  = info["gameDuration"] / 60

    ts           = info.get("gameStartTimestamp", 0)
    data_partida = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%d/%m/%Y %H:%M") if ts else "-"
    dia_semana   = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%A") if ts else "-"

    # KDA e KP
    kills   = jogador["kills"]
    deaths  = jogador["deaths"]
    assists = jogador["assists"]
    kda     = (kills + assists) / max(deaths, 1)
    kills_time = sum(p["kills"] for p in participants if p["teamId"] == jogador["teamId"])
    kp      = round((kills + assists) / max(kills_time, 1) * 100, 1)

    # CS
    cs_total = jogador["totalMinionsKilled"] + jogador["neutralMinionsKilled"]

    # Runas
    perks    = jogador.get("perks", {})
    styles   = perks.get("styles", [])
    keystone      = "-"
    runa_primaria = "-"
    runa_secundaria = "-"
    if len(styles) >= 1:
        runa_primaria = styles[0].get("description", "-")
        sels = styles[0].get("selections", [])
        if sels:
            keystone = sels[0].get("perk", "-")
    if len(styles) >= 2:
        runa_secundaria = styles[1].get("description", "-")

    stats = {
        # ── Identificação ──
        "Partida":              match["metadata"]["matchId"],
        "Data":                 data_partida,
        "Dia":                  dia_semana,
        "Jogador":              _nome_jogador(jogador),
        "Campeão":              jogador["championName"],
        "Nível Final":          jogador.get("champLevel", 0),
        "Time":                 "Azul" if jogador["teamId"] == 100 else "Vermelho",
        "Lane":                 jogador.get("teamPosition", "?"),
        "Lane Individual":      jogador.get("individualPosition", "?"),
        "Vitória":              "✅" if jogador["win"] else "❌",
        "Rendeu":               "✅" if jogador.get("gameEndedInSurrender") else "❌",
        "Rendeu Cedo":          "✅" if jogador.get("gameEndedInEarlySurrender") else "❌",
        "Duração (min)":        round(duracao_min, 1),

        # ── KDA ──
        "K":                    kills,
        "D":                    deaths,
        "A":                    assists,
        "KDA":                  round(kda, 2),
        "KP%":                  kp,
        "1º Sangue":            "✅" if jogador.get("firstBloodKill") else "",
        "Assistiu 1º Sangue":   "✅" if jogador.get("firstBloodAssist") else "",
        "Maior Spree":          jogador.get("largestKillingSpree", 0),
        "Maior Multi-kill":     jogador.get("largestMultiKill", 0),
        "Triple Kills":         jogador.get("tripleKills", 0),
        "Quadra Kills":         jogador.get("quadraKills", 0),
        "Penta Kills":          jogador.get("pentaKills", 0),
        "Bounty Level":         jogador.get("bountyLevel", 0),
        "Maior Sequência Vivo (s)": jogador.get("longestTimeSpentLiving", 0),

        # ── Farm ──
        "CS":                   cs_total,
        "CS/min":               round(cs_total / duracao_min, 1),
        "Minions":              jogador.get("totalMinionsKilled", 0),
        "Jungle CS":            jogador.get("neutralMinionsKilled", 0),

        # ── Dano causado ──
        "Dano":                 jogador.get("totalDamageDealtToChampions", 0),
        "Dano/min":             round(jogador.get("totalDamageDealtToChampions", 0) / duracao_min),
        "Dano Físico":          jogador.get("physicalDamageDealtToChampions", 0),
        "Dano Mágico":          jogador.get("magicDamageDealtToChampions", 0),
        "Dano Verdadeiro":      jogador.get("trueDamageDealtToChampions", 0),
        "Dano Total (all)":     jogador.get("totalDamageDealt", 0),
        "Maior Crítico":        jogador.get("largestCriticalStrike", 0),

        # ── Dano tomado e sustain ──
        "Dano Tomado":          jogador.get("totalDamageTaken", 0),
        "Dano Físico Tomado":   jogador.get("physicalDamageTaken", 0),
        "Dano Mágico Tomado":   jogador.get("magicDamageTaken", 0),
        "Dano Verdadeiro Tomado": jogador.get("trueDamageTaken", 0),
        "Cura Total":           jogador.get("totalHeal", 0),
        "Cura em Aliados":      jogador.get("totalHealsOnTeammates", 0),
        "Shield em Aliados":    jogador.get("totalDamageShieldedOnTeammates", 0),
        "Unidades Curadas":     jogador.get("totalUnitsHealed", 0),
        "Tempo Morto (s)":      jogador.get("totalTimeSpentDead", 0),

        # ── Objetivos ──
        "Dano Torres":          jogador.get("damageDealtToTurrets", 0),
        "Dano Objetivos":       jogador.get("damageDealtToObjectives", 0),
        "Torres Destruídas":    jogador.get("turretKills", 0),
        "Torres Participação":  jogador.get("turretTakedowns", 0),
        "Torres Perdidas":      jogador.get("turretsLost", 0),
        "Inibidores":           jogador.get("inhibitorKills", 0),
        "Inibidores Perdidos":  jogador.get("inhibitorsLost", 0),
        "Dragões":              jogador.get("dragonKills", 0),
        "Barões":               jogador.get("baronKills", 0),
        "Objetivos Roubados":   jogador.get("objectivesStolen", 0),
        "Nexus Kills":          jogador.get("nexusKills", 0),

        # ── CC ──
        "Tempo CC em Inimigos (s)": jogador.get("timeCCingOthers", 0),
        "Duração CC Total (s)":     jogador.get("totalTimeCCDealt", 0),

        # ── Gold ──
        "Gold":                 jogador.get("goldEarned", 0),
        "Gold/min":             round(jogador.get("goldEarned", 0) / duracao_min),
        "Gold Gasto":           jogador.get("goldSpent", 0),
        "Itens Comprados":      jogador.get("itemsPurchased", 0),
        "Consumíveis":          jogador.get("consumablesPurchased", 0),

        # ── Itens (nomes legíveis) ──
        "Item0":                item_name(jogador.get("item0", 0)),
        "Item1":                item_name(jogador.get("item1", 0)),
        "Item2":                item_name(jogador.get("item2", 0)),
        "Item3":                item_name(jogador.get("item3", 0)),
        "Item4":                item_name(jogador.get("item4", 0)),
        "Item5":                item_name(jogador.get("item5", 0)),
        "Trinket":              item_name(jogador.get("item6", 0)),

        # ── Feitiços ──
        "Feitiço1 ID":          jogador.get("summoner1Id", 0),
        "Feitiço2 ID":          jogador.get("summoner2Id", 0),
        "Feitiço1 Usos":        jogador.get("summoner1Casts", 0),
        "Feitiço2 Usos":        jogador.get("summoner2Casts", 0),

        # ── Habilidades ──
        "Q Usos":               jogador.get("spell1Casts", 0),
        "W Usos":               jogador.get("spell2Casts", 0),
        "E Usos":               jogador.get("spell3Casts", 0),
        "R Usos":               jogador.get("spell4Casts", 0),

        # ── Visão ──
        "Visão":                jogador.get("visionScore", 0),
        "Wards Colocados":      jogador.get("wardsPlaced", 0),
        "Wards Destruídos":     jogador.get("wardsKilled", 0),
        "Control Wards Comprados": jogador.get("visionWardsBoughtInGame", 0),
        "Control Wards Colocados": jogador.get("detectorWardsPlaced", 0),
        "Wards Comprados":      jogador.get("sightWardsBoughtInGame", 0),

        # ── Pings ──
        "Ping All-In":          jogador.get("allInPings", 0),
        "Ping Ajuda":           jogador.get("assistMePings", 0),
        "Ping Perigo":          jogador.get("dangerPings", 0),
        "Ping SS":              jogador.get("enemyMissingPings", 0),
        "Ping A Caminho":       jogador.get("onMyWayPings", 0),
        "Ping Push":            jogador.get("pushPings", 0),
        "Ping Voltar":          jogador.get("getBackPings", 0),
        "Ping Visão Inimiga":   jogador.get("enemyVisionPings", 0),
        "Ping Precisa Visão":   jogador.get("needVisionPings", 0),
        "Ping Segurar":         jogador.get("holdPings", 0),
        "Ping Visão Limpa":     jogador.get("visionClearedPings", 0),
        "Ping Comando":         jogador.get("commandPings", 0),

        # ── Runas ──
        "Runa Primária":        runa_primaria,
        "Runa Secundária":      runa_secundaria,
        "Keystone ID":          keystone,
    }

    # Timeline
    if timeline:
        tl = extrair_timeline(timeline, jogador["participantId"])
        stats.update(tl)

    return stats


def extrair_stats_jogador(match: dict, timeline: dict, puuid: str) -> dict | None:
    """Modo pessoal — só o jogador com o PUUID informado."""
    jogador = next((p for p in match["info"]["participants"] if p["puuid"] == puuid), None)
    if not jogador:
        return None
    return extrair_stats_participante(match, timeline, jogador)


def extrair_stats_completo(match: dict, timeline: dict) -> list[dict]:
    """Modo completo — todos os 10 jogadores."""
    return [extrair_stats_participante(match, timeline, p) for p in match["info"]["participants"]]
