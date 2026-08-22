"""
live_client.py — Leitura da Live Client Data API (local, durante a partida)
"""

import requests
import urllib3
from config import LIVE_API_URL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_session = requests.Session()


def get_game_data() -> dict | None:
    """
    Busca o snapshot completo do jogo ao vivo.
    Retorna None se não houver partida em andamento.
    """
    try:
        r = _session.get(LIVE_API_URL, verify=False, timeout=0.8)
        if r.status_code == 200:
            return r.json()
        return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        print(f"  [live_client] erro inesperado: {e}")
        return None


def is_game_active() -> bool:
    """Verifica rapidamente se há uma partida em andamento."""
    return get_game_data() is not None
