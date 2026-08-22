"""Resolve IDs de item → nome legível (usa coach/data/items.json)."""

from __future__ import annotations

import json
from pathlib import Path

_ITEMS_FILE = Path(__file__).resolve().parent.parent / "coach" / "data" / "items.json"
_cache: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    names: dict[str, str] = {}
    if _ITEMS_FILE.exists():
        try:
            with open(_ITEMS_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            for iid, meta in (raw or {}).items():
                nome = (meta or {}).get("name")
                if nome:
                    names[str(iid)] = str(nome)
        except Exception:
            pass
    _cache = names
    return _cache


def item_name(item_id: int | str | None) -> str:
    """Nome do item; slot vazio → '' ; ID desconhecido → 'Item {id}'."""
    try:
        iid = int(item_id or 0)
    except (TypeError, ValueError):
        return ""
    if iid <= 0:
        return ""
    names = _load()
    return names.get(str(iid)) or f"Item {iid}"
