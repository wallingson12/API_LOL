"""Avisos editáveis pelo usuário (overrides + notas por campeão)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy

from config import USER_NOTICES_FILE
from data.knowledge import LANE_MACRO, WARDS, WAVE_TIPS

_lock = threading.Lock()
_cache: dict | None = None

DEFAULT_CHANNEL_OVERRIDES: dict[str, str] = {
    "map_reminder": "text",
    "ward_place_reminder": "text",
    "ward_expiring": "text",
    "trinket_full": "text",
    "jg_look_lanes": "text",
    "jg_objective_up": "text",
    "objective_ward": "text",
    "dragon_score": "text",
    "build_suggest": "text",
    "lane_briefing": "text",
}

_BUILTIN_NOTICES: list[dict] = []


def _seed_builtin() -> list[dict]:
    out = []
    for item in LANE_MACRO:
        out.append({
            "id": f"lane_{item['id']}",
            "title": item["title"],
            "body": item["body"],
            "category": "lane",
            "channel": "text",
            "champion": "",
            "role": "",
            "enabled": True,
            "builtin": True,
        })
    for item in WAVE_TIPS:
        out.append({
            "id": f"wave_{item['id']}",
            "title": item["title"],
            "body": item["body"],
            "category": "wave",
            "channel": "text",
            "champion": "",
            "role": "",
            "enabled": True,
            "builtin": True,
        })
    for item in WARDS:
        out.append({
            "id": f"ward_{item['id']}",
            "title": item["name"],
            "body": f"{item['duration']}. {item['use']} {item['when']}",
            "category": "wards",
            "channel": "text",
            "champion": "",
            "role": "",
            "enabled": True,
            "builtin": True,
        })
    return out


def _empty_store() -> dict:
    return {
        "channel_overrides": dict(DEFAULT_CHANNEL_OVERRIDES),
        "champion_notes": {},
        "notices": [],
        "hidden_builtin": [],
    }


def _read_disk() -> dict:
    if not os.path.exists(USER_NOTICES_FILE):
        return _empty_store()
    try:
        with open(USER_NOTICES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    store = _empty_store()
    store["channel_overrides"].update(data.get("channel_overrides") or {})
    store["champion_notes"] = data.get("champion_notes") or {}
    store["notices"] = list(data.get("notices") or [])
    store["hidden_builtin"] = list(data.get("hidden_builtin") or [])
    return store


def _write_disk(store: dict) -> None:
    os.makedirs(os.path.dirname(USER_NOTICES_FILE), exist_ok=True)
    payload = {
        "channel_overrides": store.get("channel_overrides") or {},
        "champion_notes": store.get("champion_notes") or {},
        "notices": store.get("notices") or [],
        "hidden_builtin": store.get("hidden_builtin") or [],
    }
    with open(USER_NOTICES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_store(force: bool = False) -> dict:
    global _cache, _BUILTIN_NOTICES
    with _lock:
        if _cache is None or force:
            _cache = _read_disk()
            _BUILTIN_NOTICES = _seed_builtin()
        return _cache


def save_store() -> None:
    store = load_store()
    with _lock:
        _write_disk(store)


def channel_override(alert_type: str) -> str | None:
    store = load_store()
    value = (store.get("channel_overrides") or {}).get(alert_type)
    if value in ("voice", "text", "both"):
        return value
    return None


def set_channel_override(alert_type: str, channel: str) -> None:
    if channel not in ("voice", "text", "both"):
        return
    store = load_store()
    store.setdefault("channel_overrides", {})[alert_type] = channel
    save_store()


def get_champion_note(champion_name: str) -> dict:
    if not champion_name:
        return {}
    store = load_store()
    notes = store.get("champion_notes") or {}
    key = _champ_key(champion_name)
    for name, payload in notes.items():
        if _champ_key(name) == key:
            return dict(payload or {})
    return {}


def set_champion_note(champion_name: str, payload: dict) -> None:
    if not champion_name:
        return
    store = load_store()
    notes = store.setdefault("champion_notes", {})
    key = champion_name
    for name in list(notes):
        if _champ_key(name) == _champ_key(champion_name):
            key = name
            break
    merged = dict(notes.get(key) or {})
    merged.update({k: v for k, v in payload.items() if v is not None})
    notes[key] = merged
    save_store()


def list_notices() -> list[dict]:
    store = load_store()
    user = list(store.get("notices") or [])
    user_ids = {n.get("id") for n in user}
    builtin = []
    for item in _seed_builtin():
        if item["id"] in user_ids:
            continue
        hidden = store.get("hidden_builtin") or []
        if item["id"] in hidden:
            continue
        builtin.append(item)
    # user copies of builtin ids replace the seed
    merged = {n["id"]: n for n in builtin}
    for item in user:
        nid = item.get("id")
        if not nid:
            continue
        merged[nid] = item
    return sorted(merged.values(), key=lambda n: (n.get("category") or "", n.get("title") or ""))


def upsert_notice(notice: dict) -> dict:
    store = load_store()
    item = deepcopy(notice)
    if not item.get("id"):
        item["id"] = f"custom_{uuid.uuid4().hex[:8]}"
    item.setdefault("title", "")
    item.setdefault("body", "")
    item.setdefault("category", "custom")
    item.setdefault("channel", "text")
    item.setdefault("champion", "")
    item.setdefault("role", "")
    item.setdefault("enabled", True)
    item["builtin"] = bool(item.get("builtin"))
    notices = store.setdefault("notices", [])
    for i, existing in enumerate(notices):
        if existing.get("id") == item["id"]:
            notices[i] = item
            save_store()
            return item
    notices.append(item)
    save_store()
    return item


def delete_notice(notice_id: str) -> None:
    store = load_store()
    store["notices"] = [n for n in (store.get("notices") or []) if n.get("id") != notice_id]
    if notice_id.startswith(("lane_", "mid_", "wave_", "ward_")):
        hidden = store.setdefault("hidden_builtin", [])
        if notice_id not in hidden:
            hidden.append(notice_id)
    save_store()


def enabled_notices(
    *,
    category: str | None = None,
    champion: str | None = None,
    role: str | None = None,
) -> list[dict]:
    out = []
    champ_key = _champ_key(champion or "")
    role_key = (role or "").lower()
    for notice in list_notices():
        if not notice.get("enabled", True):
            continue
        if category and notice.get("category") != category:
            continue
        n_champ = _champ_key(notice.get("champion") or "")
        if n_champ and champ_key and n_champ != champ_key:
            continue
        n_role = (notice.get("role") or "").lower()
        if n_role and role_key and n_role != role_key:
            continue
        out.append(notice)
    return out


def _champ_key(name: str) -> str:
    return (name or "").lower().replace(" ", "").replace("'", "")
