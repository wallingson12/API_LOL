import time
import requests
from collections import deque
from urllib.parse import quote
from config import HEADERS, REGION, PLATFORM

# ─────────────────────────────────────────
# RATE LIMIT
# ─────────────────────────────────────────
_chamadas = deque()

def get(url: str, params: dict = None) -> dict | None:
    """Faz GET respeitando os limites: 20/s e 100/2min.

    Em falha, anexa `_last_http_status` no retorno None via atributo do módulo.
    """
    global _last_http_status
    _last_http_status = None
    agora = time.time()
    while _chamadas and agora - _chamadas[0] > 120:
        _chamadas.popleft()
    if len(_chamadas) >= 95:
        espera = 120 - (agora - _chamadas[0]) + 1
        print(f"  ⏳ Rate limit preventivo, aguardando {espera:.0f}s...")
        time.sleep(espera)
        _chamadas.clear()
    if len(_chamadas) >= 1:
        time.sleep(0.06)
    _chamadas.append(time.time())

    for _ in range(3):
        r = requests.get(url, headers=HEADERS, params=params)
        _last_http_status = r.status_code
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            retry = int(r.headers.get("Retry-After", 10))
            print(f"  ⚠️  Rate limit atingido, aguardando {retry}s...")
            time.sleep(retry)
        else:
            print(f"  Erro {r.status_code}: {url}")
            return None
    return None


_last_http_status: int | None = None


# ─────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────
def get_puuid(game_name: str, tag_line: str) -> str | None:
    encoded_name = quote(game_name, safe='')
    encoded_tag  = quote(tag_line, safe='')
    url  = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}"
    data = get(url)
    return data["puuid"] if data else None


def get_match_ids(puuid: str, count: int = 20, queue: int | None = 420) -> list:
    url    = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"count": count}
    if queue is not None:
        params["queue"] = queue
    return get(url, params=params) or []


def get_match(match_id: str) -> dict | None:
    return get(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}")


def get_timeline(match_id: str) -> dict | None:
    return get(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")


def get_rank(puuid: str) -> str:
    url      = f"https://{PLATFORM}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    summoner = get(url)
    if not summoner:
        return "N/A"
    summoner_id = summoner.get("id") or summoner.get("summonerId")
    if not summoner_id:
        return "N/A"
    entries = get(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}") or []
    for e in entries:
        if e["queueType"] == "RANKED_SOLO_5x5":
            return f"{e['tier']} {e['rank']} — {e['leaguePoints']} LP ({e['wins']}W/{e['losses']}L)"
    return "Unranked"
