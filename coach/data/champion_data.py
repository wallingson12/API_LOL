"""
champion_data.py — Cache unificado de campeões (champions.json)
"""

import json
import os
import requests

from config import (
    DDRAGON_VERSIONS_URL,
    DDRAGON_CHAMP_URL_TMPL,
    DDRAGON_CHAMP_DETAIL_URL_TMPL,
    CHAMPIONS_FILE,
)

_champions: dict[str, dict] | None = None

RANGED_ATTACK_RANGE = 300

_TAG_PT = {
    "Mage": "mago",
    "Marksman": "atirador",
    "Fighter": "lutador",
    "Tank": "tanque",
    "Assassin": "assassino",
    "Support": "suporte",
}


def _fetch_latest_version() -> str:
    r = requests.get(DDRAGON_VERSIONS_URL, timeout=5)
    r.raise_for_status()
    return r.json()[0]


def _build_from_api(existing: dict[str, dict] | None = None) -> dict[str, dict]:
    """Busca lista de campeões; preserva danger_tip / enemy_tips já curados."""
    version = _fetch_latest_version()
    url = DDRAGON_CHAMP_URL_TMPL.format(version=version)
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    raw = r.json()["data"]
    existing = existing or {}

    champions: dict[str, dict] = {}
    for champ in raw.values():
        key = str(champ["key"])
        stats = champ.get("stats") or {}
        prev = existing.get(key) or {}
        entry = {
            "id": champ["id"],
            "key": key,
            "name": champ["name"],
            "tags": champ.get("tags") or [],
            "attackrange": int(stats.get("attackrange", 125) or 125),
        }
        if prev.get("danger_tip"):
            entry["danger_tip"] = prev["danger_tip"]
        if prev.get("enemy_tips"):
            entry["enemy_tips"] = list(prev["enemy_tips"])
        champions[key] = entry
    return champions


def _ensure_profile_keys(champions: dict[str, dict]) -> dict[str, dict]:
    for numeric_key, profile in champions.items():
        if not profile.get("key"):
            profile["key"] = numeric_key
    return champions


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_champions_file() -> dict[str, dict] | None:
    if not os.path.exists(CHAMPIONS_FILE):
        return None
    try:
        with open(CHAMPIONS_FILE, "r", encoding="utf-8") as f:
            return _ensure_profile_keys(json.load(f))
    except Exception:
        return None


def load_champions(force_refresh: bool = False) -> dict[str, str]:
    """Retorna mapa id → nome (derivado do cache unificado)."""
    global _champions
    if _champions is not None and not force_refresh:
        return {key: profile["name"] for key, profile in _champions.items()}

    if not force_refresh:
        disk = _read_champions_file()
        if disk:
            _champions = disk
            return {key: profile["name"] for key, profile in _champions.items()}

    try:
        existing = _read_champions_file() or _champions or {}
        _champions = _ensure_profile_keys(_build_from_api(existing))
        _save_json(CHAMPIONS_FILE, _champions)
    except Exception as e:
        print(f"  [champion_data] não foi possível buscar campeões: {e}")
        _champions = _champions or _read_champions_file() or {}

    return {key: profile["name"] for key, profile in (_champions or {}).items()}


def load_champion_profiles(force_refresh: bool = False) -> dict[str, dict]:
    load_champions(force_refresh=force_refresh)
    return _champions or {}


def reload_champions_from_disk() -> dict[str, dict]:
    """Relê champions.json (depois de scrape / edição)."""
    global _champions
    disk = _read_champions_file()
    if disk:
        _champions = disk
    return _champions or {}


def get_champion_name(champion_id: int | str) -> str:
    champs = load_champions()
    return champs.get(str(champion_id), f"Campeão {champion_id}")


def get_champion_profile(champion_id: int | str) -> dict | None:
    profiles = load_champion_profiles()
    return profiles.get(str(champion_id))


def get_champion_profile_by_name(champion_name: str) -> dict | None:
    if not champion_name:
        return None
    profiles = load_champion_profiles()
    target = champion_name.lower().replace(" ", "").replace("'", "")
    for profile in profiles.values():
        pname = (profile.get("name") or "").lower().replace(" ", "").replace("'", "")
        pid = (profile.get("id") or "").lower().replace(" ", "").replace("'", "")
        if target == pname or target == pid:
            return profile
    return None


def get_champion_id_by_name(champion_name: str) -> int | None:
    profile = get_champion_profile_by_name(champion_name)
    if not profile:
        return None
    try:
        return int(profile.get("key") or 0) or None
    except (TypeError, ValueError):
        return None


def is_ranged_champion(champion_id: int | str) -> bool:
    profile = get_champion_profile(champion_id)
    if not profile:
        return False
    return profile.get("attackrange", 125) >= RANGED_ATTACK_RANGE


def champion_has_tag(champion_id: int | str, tag: str) -> bool:
    profile = get_champion_profile(champion_id)
    if not profile:
        return False
    return tag in (profile.get("tags") or [])


def get_champion_class_label(
    champion_id: int | str | None = None,
    champion_name: str | None = None,
) -> str | None:
    profile = None
    if champion_id:
        profile = get_champion_profile(champion_id)
    if not profile and champion_name:
        profile = get_champion_profile_by_name(champion_name)
    if not profile:
        return None
    tags = profile.get("tags") or []
    if not tags:
        return None
    return _TAG_PT.get(tags[0], tags[0].lower())


def _fetch_enemy_tips_from_api(ddragon_id: str) -> list[str]:
    version = _fetch_latest_version()
    url = DDRAGON_CHAMP_DETAIL_URL_TMPL.format(version=version, champ_id=ddragon_id)
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    payload = r.json().get("data", {}).get(ddragon_id, {})
    return list(payload.get("enemytips") or [])


def get_enemy_tips(
    champion_id: int | str | None = None,
    champion_name: str | None = None,
) -> list[str]:
    profile = None
    if champion_id:
        profile = get_champion_profile(champion_id)
    if not profile and champion_name:
        profile = get_champion_profile_by_name(champion_name)
    if not profile:
        return []

    cached = profile.get("enemy_tips")
    if cached:
        return list(cached)

    ddragon_id = profile.get("id")
    if not ddragon_id:
        return []

    try:
        tips = _fetch_enemy_tips_from_api(ddragon_id)
    except Exception as e:
        print(f"  [champion_data] enemytips de {ddragon_id}: {e}")
        tips = []

    profile["enemy_tips"] = tips
    if _champions is not None:
        _save_json(CHAMPIONS_FILE, _champions)
    return tips
