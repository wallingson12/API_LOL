"""
events.py — Decodifica eventos brutos da Live Client Data API em formato legível

Foco: tudo que vem de dados reais da API (kills, mortes, torres, gold, itens),
nada de posição ou visão inferida — ver README para o porquê dessa limitação.
"""

import re

from config import GOLD_ALERT_THRESHOLDS, GOLD_RESET_MARGIN, LEVEL_ALERTS
from game.player_match import active_player_name, find_active_player, names_match, player_display_name
from voice.spoken import structure_phrase

from core.lanes import STRUCTURE_LANE_MAP, parse_lane_from_structure_id
from core.roles import API_POSITION_TO_INGAME as _ROLE_MAP

_TEAM_MAP = {"TOrder": "azul", "TChaos": "vermelho"}


# Na API da Riot, P3 = torre externa (1ª a cair), P2 = intermediária, P1 = antes do inibidor.
_RIOT_P_TO_TIER = {3: "T1", 2: "T2", 1: "T3"}


def _infer_turret_tier(turret_id: str, lane_str: str) -> str:
    """
    Infere T1/T2/T3 no sentido do jogo (ordem em que as torres caem na lane).

    Formato real da Live Client API:
    - Turret_TChaos_L0_P3_... -> T1 do bot
    - Turret_TChaos_L1_P3_... -> T1 do mid
    - Turret_TChaos_L2_P3_... -> T1 do top
    """
    point_match = re.search(r"_P([1-3])(?:_|$)", turret_id)
    if point_match:
        return _RIOT_P_TO_TIER[int(point_match.group(1))]

    numeric_parts = [int(part) for part in re.findall(r"_(\d{1,2})(?:_|$)", turret_id)]
    if numeric_parts:
        last_num = numeric_parts[-1]
        if lane_str == "mid":
            mapped = {5: "T1", 4: "T2", 3: "T3"}.get(last_num)
            if mapped:
                return mapped
        mapped = {3: "T1", 2: "T2", 1: "T3"}.get(last_num)
        if mapped:
            return mapped

    return "T1"


def parse_lane_from_id(structure_id: str) -> str:
    return parse_lane_from_structure_id(structure_id)


def parse_structure_team(structure_id: str) -> str | None:
    if "Chaos" in structure_id:
        return "CHAOS"
    if "Order" in structure_id:
        return "ORDER"
    return None


def parse_inhibitor_name(inhib_id: str) -> str:
    lane_str = parse_lane_from_id(inhib_id)
    team = parse_structure_team(inhib_id)
    team_key = "TOrder" if team == "ORDER" else ("TChaos" if team == "CHAOS" else None)
    team_str = _TEAM_MAP.get(team_key, "desconhecido")
    return f"inibidor do {lane_str} ({team_str})"


def parse_turret_name(turret_id: str) -> str:
    """
    Decodifica algo como 'Turret_T2_L_03_A' ou o formato usado no evento
    'TurretKilled' (campo TurretKilled, ex: 'Turret_OrderT2_L_03_A').
    Retorna string legível: "T2 do mid (vermelho)".
    """
    team = parse_structure_team(turret_id)
    team_key = "TOrder" if team == "ORDER" else ("TChaos" if team == "CHAOS" else None)
    team_str = _TEAM_MAP.get(team_key, "desconhecido")

    lane_match = re.search(r"_(L[0-2])_", turret_id)
    if lane_match:
        lane_str = STRUCTURE_LANE_MAP.get(lane_match.group(1), "?")
    else:
        lane_str = parse_lane_from_id(turret_id)

    pos_str = _infer_turret_tier(turret_id, lane_str)

    return f"{pos_str} do {lane_str} ({team_str})"


def structure_side_label(structure_team: str | None, my_team: str | None) -> str | None:
    """Retorna 'nossa' ou 'inimiga' relativo ao seu time."""
    if not structure_team or not my_team:
        return None
    return "nossa" if structure_team.upper() == my_team.upper() else "inimiga"


def format_structure_label(ev: dict, my_team: str | None) -> str:
    """Rótulo falado da estrutura (sem 'nossa/inimiga' entre parênteses)."""
    return structure_phrase(ev)


def _has_smite(player: dict) -> bool:
    spells = player.get("summonerSpells") or {}
    for key in ("summonerSpellOne", "summonerSpellTwo"):
        spell = spells.get(key) or {}
        text = " ".join(
            str(spell.get(field, ""))
            for field in ("displayName", "rawDisplayName", "rawDescription")
        ).lower()
        compact = text.replace("_", "").replace(" ", "")
        if any(token in text or token in compact for token in (
            "smite", "flagelo", "summonersmite", "challengesmite", "punish",
        )):
            return True
    return False


def parse_role(player: dict) -> str | None:
    raw = (player.get("position") or player.get("teamPosition") or "").upper()
    role = _ROLE_MAP.get(raw)
    if role:
        return role
    if _has_smite(player):
        return "jungler"
    return None


def filter_events(events: list[dict]) -> list[dict]:
    """
    Remove redundância: não repete morte se já teve kill no feed,
    não repete primeiro sangue se já teve abate, ignora compras e levels irrelevantes.
    """
    kill_victims = {ev["victim"] for ev in events if ev["type"] == "kill"}

    filtered = []
    for ev in events:
        t = ev["type"]

        if t in ("item_bought", "first_blood", "minions_spawn"):
            continue
        if t == "player_died" and ev["player"] in kill_victims:
            continue
        if t == "level_up" and ev.get("level") not in LEVEL_ALERTS:
            continue

        filtered.append(ev)

    return filtered


_LIVE_GAME_EVENT_TYPES = frozenset({
    "kill", "turret", "inhibitor", "dragon", "baron", "herald", "voidgrub",
    "minions_spawn",
})
_FEED_LIVE_EVENT_NAMES = frozenset({
    "MinionsSpawning", "ChampionKill", "TurretKilled", "InhibKilled",
    "DragonKill", "BaronKill", "HeraldKill", "VoidGrubKill", "VoidgrubKill",
    "VoidGrubKilled", "FirstBlood",
})


def _feed_event_marks_live(event_name: str | None) -> bool:
    if not event_name:
        return False
    if event_name in _FEED_LIVE_EVENT_NAMES:
        return True
    lower = event_name.lower()
    return "voidgrub" in lower and "kill" in lower


class GameEventTracker:
    """
    Mantém estado entre polls sucessivos da Live Client Data API para detectar
    o que MUDOU (eventos novos, mortes, itens comprados) em vez de reportar
    o estado bruto a cada chamada.
    """

    def __init__(self):
        self.seen_event_ids: set[int] = set()
        self.last_player_state: dict[str, dict] = {}  # nome -> snapshot anterior
        self.last_active_gold: int | None = None
        self._gold_announced: set[int] = set()
        self._feed_bootstrapped = False
        self._announced_structures: set[str] = set()
        self._game_live = False
        self._map_reminder_armed_at_game_time: float | None = None

    def is_game_live(self) -> bool:
        return self._game_live

    def map_reminder_armed_at(self) -> float | None:
        return self._map_reminder_armed_at_game_time

    def _arm_map_reminder(self, game_data: dict, *, from_bootstrap: bool) -> None:
        if self._map_reminder_armed_at_game_time is not None:
            return
        game_time = float(game_data.get("gameData", {}).get("gameTime", 0) or 0)
        if from_bootstrap:
            if self._game_live and game_time >= 90:
                self._map_reminder_armed_at_game_time = game_time
            return
        self._map_reminder_armed_at_game_time = game_time

    def _mark_game_live(self, game_data: dict, new_events: list[dict]) -> None:
        for ev in new_events:
            if ev.get("type") not in _LIVE_GAME_EVENT_TYPES:
                continue
            if not self._game_live:
                self._game_live = True
            self._note_live_feed_event(game_data, from_bootstrap=False)
            return

    def _note_live_feed_event(self, game_data: dict, *, from_bootstrap: bool) -> None:
        self._arm_map_reminder(game_data, from_bootstrap=from_bootstrap)

    def diff(self, game_data: dict) -> list[dict]:
        """
        Recebe o snapshot atual completo e retorna uma lista de eventos novos
        detectados desde o último diff. Cada evento é um dict com 'type' e dados.
        """
        novos = []
        novos += self._diff_feed_events(game_data)
        novos += self._diff_player_states(game_data)
        novos += self._diff_gold(game_data)
        novos = filter_events(novos)
        self._mark_game_live(game_data, novos)
        return novos

    # ── eventos do feed oficial (events[]) ──
    def _diff_feed_events(self, game_data: dict) -> list[dict]:
        out = []
        events = game_data.get("events", {}).get("Events", [])

        if not self._feed_bootstrapped:
            for ev in events:
                eid = ev.get("EventID")
                if eid is not None:
                    self.seen_event_ids.add(eid)
                if _feed_event_marks_live(ev.get("EventName")):
                    self._game_live = True
            if self._game_live:
                self._note_live_feed_event(game_data, from_bootstrap=True)
            self._feed_bootstrapped = True
            return out

        for ev in events:
            eid = ev.get("EventID")
            if eid is None or eid in self.seen_event_ids:
                continue
            self.seen_event_ids.add(eid)

            etype = ev.get("EventName")
            if etype == "MinionsSpawning":
                self._game_live = True
                self._note_live_feed_event(game_data, from_bootstrap=False)
                out.append({"type": "minions_spawn"})
                continue
            if etype == "ChampionKill":
                out.append({
                    "type": "kill",
                    "killer": ev.get("KillerName", "?"),
                    "victim": ev.get("VictimName", "?"),
                    "assisters": ev.get("Assisters", []),
                })
            elif etype == "TurretKilled":
                turret_raw = ev.get("TurretKilled", "")
                if turret_raw and turret_raw in self._announced_structures:
                    continue
                if turret_raw:
                    self._announced_structures.add(turret_raw)
                turret_desc = parse_turret_name(turret_raw) if turret_raw else "T1 do ? (desconhecido)"
                out.append({
                    "type": "turret",
                    "killer": ev.get("KillerName", "?"),
                    "turret_desc": turret_desc,
                    "lane": parse_lane_from_id(turret_raw),
                    "structure_team": parse_structure_team(turret_raw),
                })
            elif etype == "InhibKilled":
                inhib_raw = ev.get("InhibKilled", "")
                if inhib_raw and inhib_raw in self._announced_structures:
                    continue
                if inhib_raw:
                    self._announced_structures.add(inhib_raw)
                inhib_desc = parse_inhibitor_name(inhib_raw) if inhib_raw else "inibidor"
                out.append({
                    "type": "inhibitor",
                    "killer": ev.get("KillerName", "?"),
                    "inhib_desc": inhib_desc,
                    "lane": parse_lane_from_id(inhib_raw),
                    "structure_team": parse_structure_team(inhib_raw),
                })
            elif etype == "DragonKill":
                out.append({
                    "type": "dragon",
                    "killer": ev.get("KillerName", "?"),
                    "dragon_type": ev.get("DragonType", "Dragão"),
                    "event_time": ev.get("EventTime"),
                })
            elif etype == "BaronKill":
                out.append({
                    "type": "baron",
                    "killer": ev.get("KillerName", "?"),
                    "event_time": ev.get("EventTime"),
                })
            elif etype == "HeraldKill":
                out.append({
                    "type": "herald",
                    "killer": ev.get("KillerName", "?"),
                    "event_time": ev.get("EventTime"),
                })
            elif etype in ("VoidGrubKill", "VoidgrubKill", "VoidGrubKilled") or (
                etype and "voidgrub" in etype.lower() and "kill" in etype.lower()
            ):
                out.append({
                    "type": "voidgrub",
                    "killer": ev.get("KillerName", "?"),
                    "event_time": ev.get("EventTime"),
                })
            elif etype == "FirstBlood":
                out.append({"type": "first_blood", "killer": ev.get("Recipient", "?")})
            elif etype == "GameEnd":
                out.append({"type": "game_end", "result": ev.get("Result", "?")})
            elif etype == "WardPlaced":
                out.append({
                    "type": "ward_placed",
                    "creator": (
                        ev.get("CreatorName")
                        or ev.get("PlacerName")
                        or ev.get("creatorName")
                        or "?"
                    ),
                    "ward_type": ev.get("WardType") or ev.get("wardType") or "",
                    "event_time": ev.get("EventTime"),
                    "event_id": eid,
                })
            elif etype == "WardKilled":
                out.append({
                    "type": "ward_killed",
                    "event_time": ev.get("EventTime"),
                    "event_id": eid,
                })
        return out

    # ── mudanças de estado por jogador (morte, respawn, itens) ──
    def _diff_player_states(self, game_data: dict) -> list[dict]:
        out = []
        my_name = active_player_name(game_data)
        me = find_active_player(game_data)
        my_team = me.get("team") if me else None

        for p in game_data.get("allPlayers", []):
            name = player_display_name(p)
            prev = self.last_player_state.get(name)
            cur = {
                "isDead": p.get("isDead", False),
                "respawnTimer": p.get("respawnTimer", 0),
                "items": [it.get("itemID") for it in p.get("items", [])],
                "level": p.get("level", 0),
                "team": p.get("team"),
                "role": parse_role(p),
            }

            if prev:
                # Acabou de morrer agora
                if cur["isDead"] and not prev["isDead"]:
                    out.append({
                        "type": "player_died",
                        "player": name,
                        "role": cur["role"],
                        "is_enemy": my_team is not None and cur["team"] != my_team,
                    })
                # Acabou de reviver
                if not cur["isDead"] and prev["isDead"]:
                    out.append({
                        "type": "player_respawned",
                        "player": name,
                        "role": cur["role"] or prev.get("role"),
                        "is_enemy": my_team is not None and cur["team"] != my_team,
                    })
                if cur["level"] > prev["level"]:
                    out.append({"type": "level_up", "player": name, "level": cur["level"]})

            self.last_player_state[name] = cur

        return out

    def _diff_gold(self, game_data: dict) -> list[dict]:
        out = []
        current_gold = int(game_data.get("activePlayer", {}).get("currentGold", 0) or 0)

        if self.last_active_gold is None:
            self.last_active_gold = current_gold
            for threshold in GOLD_ALERT_THRESHOLDS:
                if current_gold >= threshold:
                    self._gold_announced.add(threshold)
            return out

        for threshold in GOLD_ALERT_THRESHOLDS:
            if current_gold < threshold - GOLD_RESET_MARGIN:
                self._gold_announced.discard(threshold)

        for threshold in GOLD_ALERT_THRESHOLDS:
            if (
                threshold not in self._gold_announced
                and self.last_active_gold < threshold <= current_gold
            ):
                out.append({"type": "gold_threshold", "gold": threshold})
                self._gold_announced.add(threshold)

        self.last_active_gold = current_gold
        return out
