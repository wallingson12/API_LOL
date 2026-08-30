"""Mana/vida baixas — recall e sobrevivência (quase sempre HUD)."""

from __future__ import annotations

import time

from config import (
    HP_CRITICAL_RATIO,
    HP_LOW_RATIO,
    MANA_LOW_RATIO,
    RESOURCE_ALERT_COOLDOWN_SECONDS,
)


def _active_stats(game_data: dict) -> dict:
    ap = game_data.get("activePlayer") or {}
    stats = ap.get("championStats") or {}
    return {
        "hp": float(stats.get("currentHealth") or ap.get("currentHealth") or 0),
        "max_hp": float(stats.get("maxHealth") or ap.get("maxHealth") or 0),
        "resource": float(stats.get("resourceValue") or ap.get("resourceValue") or 0),
        "max_resource": float(stats.get("resourceMax") or ap.get("resourceMax") or 0),
        "resource_type": str(
            stats.get("resourceType") or ap.get("resourceType") or ""
        ).upper(),
    }


class ResourceAlertTracker:
    def __init__(self):
        self._last: dict[str, float] = {}

    def reset(self):
        self._last.clear()

    def update(self, game_data: dict) -> list[dict]:
        stats = _active_stats(game_data)
        now = time.monotonic()
        out = []

        hp_ratio = stats["hp"] / stats["max_hp"] if stats["max_hp"] > 0 else 1.0
        mana_ratio = (
            stats["resource"] / stats["max_resource"]
            if stats["max_resource"] > 0
            else 1.0
        )
        is_mana = stats["resource_type"] in ("MANA", "")

        if hp_ratio <= HP_CRITICAL_RATIO and (not is_mana or mana_ratio <= MANA_LOW_RATIO):
            if self._due("critical", now):
                out.append({
                    "type": "resource_critical",
                    "text": "Sem recurso. Sobreviva e baseie.",
                    "hud": (
                        "Vida/mana no osso. Priorize sobreviver. "
                        "Não hold wave no meio. Baseie."
                    ),
                })
            return out

        if is_mana and mana_ratio <= MANA_LOW_RATIO and stats["max_resource"] > 0:
            if self._due("mana", now):
                out.append({
                    "type": "resource_low_mana",
                    "text": "Mana baixa. Planeje o recall antes de zerar.",
                    "hud": (
                        "Mana baixa. Planeje o recall. "
                        "Se a wave estiver na torre inimiga, crash e some. "
                        "Wave no meio: não baseie cego — eles empurram a torre."
                    ),
                })

        if hp_ratio <= HP_LOW_RATIO and stats["max_hp"] > 0:
            if self._due("hp", now):
                out.append({
                    "type": "resource_low_hp",
                    "text": "Vida baixa. Não force trade.",
                    "hud": (
                        "Vida baixa. Jogue atrás da wave/torre. "
                        "Sem mana/vida e em perigo: sobreviver > farm."
                    ),
                })

        return out

    def _due(self, key: str, now: float) -> bool:
        last = self._last.get(key, 0.0)
        if now - last < RESOURCE_ALERT_COOLDOWN_SECONDS:
            return False
        self._last[key] = now
        return True
