"""
enemy_item_board.py — Quadro UI + voz NA HORA em que o inimigo ganha o efeito.
"""

from __future__ import annotations

from analysis.analyzer import get_my_team_and_enemies
from data.item_data import get_item, get_item_efeitos

BOARD_KEYS = (
    "cura",
    "vampirismo",
    "escudo",
    "resistencia_magica",
    "corta_cura",
)

BOARD_LABELS = {
    "cura": "Cura",
    "vampirismo": "Vampirismo",
    "escudo": "Escudo",
    "resistencia_magica": "Resistência mágica",
    "corta_cura": "Corta cura",
}

# 1x por campeão+efeito na partida
_VOICE_EFFECTS = (
    "vampirismo",
    "corta_cura",
    "cura",
    "resistencia_magica",
    "escudo",
)

_VOICE_LINES = {
    "vampirismo": "{champ} com vampirismo. Compre corta cura.",
    "corta_cura": "{champ} com corta cura. Não prolongue a troca.",
    "cura": "{champ} com cura. Compre corta cura.",
    "resistencia_magica": "{champ} com resistência mágica.",
    "escudo": "{champ} com escudo.",
}


def _empty_board() -> dict[str, list[dict]]:
    return {k: [] for k in BOARD_KEYS}


def build_enemy_item_board(game_data: dict | None) -> dict[str, list[dict]]:
    """Por efeito: [{champion, items: [nomes]}]. Só inimigos."""
    board = _empty_board()
    if not game_data:
        return board

    _, _, enemies = get_my_team_and_enemies(game_data)

    for enemy in enemies:
        champ = enemy.get("championName") or "?"
        by_effect: dict[str, list[str]] = {k: [] for k in BOARD_KEYS}
        seen_ids: set[int] = set()

        for raw in enemy.get("items") or []:
            iid = raw.get("itemID")
            if iid is None:
                continue
            try:
                iid_int = int(iid)
            except (TypeError, ValueError):
                continue
            if iid_int in seen_ids:
                continue
            seen_ids.add(iid_int)
            efeitos = get_item_efeitos(iid_int)
            if not efeitos:
                continue
            nome = (get_item(iid_int) or {}).get("name") or raw.get("displayName") or str(iid_int)
            for efeito in BOARD_KEYS:
                if efeito in efeitos and nome not in by_effect[efeito]:
                    by_effect[efeito].append(nome)

        for efeito in BOARD_KEYS:
            if by_effect[efeito]:
                board[efeito].append({
                    "champion": champ,
                    "items": by_effect[efeito],
                })

    return board


def format_board_lines(board: dict[str, list[dict]] | None) -> dict[str, str]:
    board = board or _empty_board()
    out: dict[str, str] = {}
    for key in BOARD_KEYS:
        rows = board.get(key) or []
        if not rows:
            out[key] = "—"
            continue
        lines = []
        for row in rows:
            items = ", ".join(row.get("items") or [])
            lines.append(f"{row.get('champion', '?')} — {items}")
        out[key] = "\n".join(lines)
    return out


class EnemyItemAlertTracker:
    """Primeira vez que inimigo ganha efeito tático → alerta imediato."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def reset(self) -> None:
        self._seen.clear()

    def alerts_from_board(self, board: dict[str, list[dict]] | None) -> list[dict]:
        alerts: list[dict] = []
        if not board:
            return alerts
        for efeito in _VOICE_EFFECTS:
            for row in board.get(efeito) or []:
                champ = (row.get("champion") or "?").strip()
                if not champ or champ == "?":
                    continue
                key = (champ.lower(), efeito)
                if key in self._seen:
                    continue
                self._seen.add(key)
                item = (row.get("items") or [None])[0]
                tmpl = _VOICE_LINES.get(efeito) or "{champ} com item tático."
                alerts.append({
                    "type": "enemy_item_effect",
                    "effect": efeito,
                    "champion": champ,
                    "item": item,
                    "text": tmpl.format(champ=champ),
                    "key": f"enemy_item_{efeito}_{champ}",
                })
        return alerts
