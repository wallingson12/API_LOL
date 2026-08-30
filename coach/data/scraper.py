"""
Coleta permitida: só Data Dragon oficial da Riot (CDN público).

Não raspa u.gg / op.gg / sites de terceiro — ToS deles e da Riot não cobrem isso.
"""

from __future__ import annotations

import json
import os
import time

import requests

from config import (
    CHAMPIONS_FILE,
    DDRAGON_CHAMP_DETAIL_URL_TMPL,
    DDRAGON_RUNES_URL_TMPL,
    DDRAGON_VERSIONS_URL,
    RUNES_FILE,
)
from data.champion_data import load_champion_profiles, load_champions

_session = requests.Session()


def latest_version() -> str:
    r = _session.get(DDRAGON_VERSIONS_URL, timeout=8)
    r.raise_for_status()
    return r.json()[0]


def fetch_runes(force: bool = False) -> list[dict]:
    if not force and os.path.exists(RUNES_FILE):
        try:
            with open(RUNES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data:
                return data
        except Exception:
            pass

    version = latest_version()
    url = DDRAGON_RUNES_URL_TMPL.format(version=version)
    r = _session.get(url, timeout=12)
    r.raise_for_status()
    raw = r.json()
    slim = []
    for tree in raw:
        slots = []
        for slot in tree.get("slots") or []:
            slots.append([
                {
                    "id": rune.get("id"),
                    "key": rune.get("key"),
                    "name": rune.get("name"),
                }
                for rune in (slot.get("runes") or [])
            ])
        slim.append({
            "id": tree.get("id"),
            "key": tree.get("key"),
            "name": tree.get("name"),
            "slots": slots,
        })
    os.makedirs(os.path.dirname(RUNES_FILE), exist_ok=True)
    with open(RUNES_FILE, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    return slim


def fetch_champion_tips(ddragon_id: str, version: str | None = None) -> dict:
    version = version or latest_version()
    url = DDRAGON_CHAMP_DETAIL_URL_TMPL.format(version=version, champ_id=ddragon_id)
    r = _session.get(url, timeout=10)
    r.raise_for_status()
    payload = r.json().get("data", {}).get(ddragon_id, {})
    return {
        "enemy_tips": list(payload.get("enemytips") or []),
        "ally_tips": list(payload.get("allytips") or []),
        "title": payload.get("title") or "",
        "partype": payload.get("partype") or "",
    }


def refresh_champion_tips(
    *,
    only_missing: bool = True,
    ddragon_id: str | None = None,
    on_progress=None,
) -> dict:
    """Atualiza enemytips/allytips no champions.json via Data Dragon."""
    profiles = load_champion_profiles()
    version = latest_version()
    updated = 0
    skipped = 0
    errors: list[str] = []

    targets = []
    for key, profile in profiles.items():
        cid = profile.get("id")
        if not cid:
            continue
        if ddragon_id and cid != ddragon_id:
            continue
        if only_missing and profile.get("enemy_tips"):
            skipped += 1
            continue
        targets.append((key, profile, cid))

    total = len(targets)
    for i, (key, profile, cid) in enumerate(targets, 1):
        if on_progress:
            on_progress(i, total, profile.get("name") or cid)
        try:
            tips = fetch_champion_tips(cid, version=version)
        except Exception as exc:
            errors.append(f"{cid}: {exc}")
            continue
        if tips.get("enemy_tips"):
            profile["enemy_tips"] = tips["enemy_tips"]
        if tips.get("ally_tips"):
            profile["ally_tips"] = tips["ally_tips"]
        updated += 1
        time.sleep(0.05)

    if updated:
        os.makedirs(os.path.dirname(CHAMPIONS_FILE), exist_ok=True)
        with open(CHAMPIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        load_champions(force_refresh=False)
        from data.champion_data import reload_champions_from_disk
        reload_champions_from_disk()

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "version": version,
    }


def format_rune_trees(trees: list[dict] | None = None) -> str:
    if trees is None:
        if not os.path.exists(RUNES_FILE):
            return ""
        try:
            with open(RUNES_FILE, "r", encoding="utf-8") as f:
                trees = json.load(f)
        except Exception:
            return ""
    lines = []
    for tree in trees:
        name = tree.get("name") or tree.get("key")
        slots = tree.get("slots") or []
        if not slots:
            continue
        keys = ", ".join(r.get("name") or "?" for r in (slots[0] or []))
        lines.append(f"{name}: {keys}")
    return "\n".join(lines)
