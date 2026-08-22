"""
lcu_client.py — Leitura da LCU API (cliente do LoL, antes/depois da partida)

Usa o lockfile gerado automaticamente pelo cliente do LoL para autenticação.
Útil para pegar composição de champ select, runas e feitiços antes da
Live Client Data API ficar disponível (que só funciona já dentro da partida).
"""

import base64
import requests
import urllib3
from config import LOCKFILE_PATH

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def read_lockfile() -> dict | None:
    """
    Lê o lockfile do cliente do LoL para extrair porta e token de auth.
    Formato do lockfile: name:pid:port:password:protocol
    """
    try:
        with open(LOCKFILE_PATH, "r") as f:
            content = f.read().strip()
        parts = content.split(":")
        if len(parts) != 5:
            return None
        return {
            "name": parts[0],
            "pid": parts[1],
            "port": parts[2],
            "password": parts[3],
            "protocol": parts[4],
        }
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  [lcu_client] erro ao ler lockfile: {e}")
        return None


def _auth_header(lock: dict) -> dict:
    token = base64.b64encode(f"riot:{lock['password']}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def lcu_get(endpoint: str) -> dict | list | None:
    """Faz GET em um endpoint da LCU API. Ex: '/lol-gameflow/v1/session'"""
    lock = read_lockfile()
    if not lock:
        return None
    url = f"{lock['protocol']}://127.0.0.1:{lock['port']}{endpoint}"
    try:
        r = requests.get(url, headers=_auth_header(lock), verify=False, timeout=2)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def get_gameflow_phase() -> str | None:
    """Retorna a fase atual: None, Lobby, ChampSelect, InProgress, WaitingForStats, etc."""
    data = lcu_get("/lol-gameflow/v1/gameflow-phase")
    return data if isinstance(data, str) else None


def get_champ_select_session() -> dict | None:
    """Retorna a sessão de champ select ativa (picks, bans, feitiços)."""
    return lcu_get("/lol-champ-select/v1/session")


def get_current_summoner() -> dict | None:
    """Retorna dados do invocador logado no cliente."""
    return lcu_get("/lol-summoner/v1/current-summoner")


def parse_champ_select_teams(session: dict) -> tuple[list[str], list[str]]:
    """
    Extrai nomes dos campeões já selecionados (aliados e inimigos) a partir
    da sessão de champ select da LCU API.
    """
    from data.champion_data import get_champion_name

    ctx = parse_champ_select_context(session)
    ally_names = [get_champion_name(cid) for cid in ctx.get("ally_champ_ids", [])]
    enemy_names = [get_champion_name(cid) for cid in ctx.get("enemy_champ_ids", [])]
    return ally_names, enemy_names


def _pick_champion_id(member: dict) -> int | None:
    champ_id = member.get("championId") or member.get("championPickIntent") or 0
    return champ_id if champ_id > 0 else None


def _member_lane_role(member: dict) -> str:
    """Rota atribuída no champ select (LCU). Campos variam por patch/fila."""
    from analysis.pregame_briefing import normalize_lane_role

    for field in ("assignedPosition", "position", "teamPosition", "preferredRole"):
        role = normalize_lane_role(member.get(field) or "")
        if role in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"):
            return role
    return ""


def parse_champ_select_context(session: dict) -> dict:
    """
    Contexto do champ select: seu campeão, lane, oponente de lane e composições.

    Fontes:
    - LCU /lol-champ-select/v1/session (picks + assignedPosition)
    - Data Dragon via champion_data (tipo/tags do campeão)
    """
    local_cell = session.get("localPlayerCellId")
    my_member = None
    for member in session.get("myTeam", []):
        if member.get("cellId") == local_cell:
            my_member = member
            break

    my_champ_id = _pick_champion_id(my_member) if my_member else None
    my_position = _member_lane_role(my_member or {})

    ally_champ_ids: list[int] = []
    enemy_champ_ids: list[int] = []
    lane_opponent_id = None
    lane_opponent_name = None

    for member in session.get("myTeam", []):
        champ_id = _pick_champion_id(member)
        if champ_id:
            ally_champ_ids.append(champ_id)

    for member in session.get("theirTeam", []):
        champ_id = _pick_champion_id(member)
        if champ_id:
            enemy_champ_ids.append(champ_id)
        enemy_role = _member_lane_role(member)
        if my_position and champ_id and enemy_role == my_position:
            lane_opponent_id = champ_id

    if lane_opponent_id:
        from data.champion_data import get_champion_name
        lane_opponent_name = get_champion_name(lane_opponent_id)

    return {
        "my_champ_id": my_champ_id,
        "my_position": my_position,
        "ally_champ_ids": ally_champ_ids,
        "enemy_champ_ids": enemy_champ_ids,
        "lane_opponent_id": lane_opponent_id,
        "lane_opponent_name": lane_opponent_name,
    }

