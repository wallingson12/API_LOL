"""Estado compartilhado entre o coach e a interface desktop."""

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    status: str = "stopped"  # stopped | idle | champ_select | in_game | post_game
    status_label: str = "Coach parado"
    coach_running: bool = False
    voice_enabled: bool = True  # sempre ligada — sem toggle na UI
    keep_range_enabled: bool = False
    vision_enabled: bool = False
    vision_champion: str = ""
    vision_confidence: float = 0.0
    data_loaded: bool = False
    game_time: float = 0.0
    my_champion: str = ""
    my_role: str = ""
    opponent_champion: str = ""
    dragon_us: int = 0
    dragon_them: int = 0
    elder_phase: bool = False
    last_dragon_key: str = ""
    # Quadro: inimigos com itens táticos (só UI + voz na hora da compra)
    enemy_item_board: dict = field(default_factory=lambda: {
        "cura": [],
        "vampirismo": [],
        "escudo": [],
        "resistencia_magica": [],
        "corta_cura": [],
    })
    build_suggestion: str = ""
    hud_alerts: list[dict] = field(default_factory=list)
    hud_cards: list[dict] = field(default_factory=list)
    recent_log: list[str] = field(default_factory=list)
    analysis_text: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _hud_keys: dict[str, float] = field(default_factory=dict, repr=False)

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def log(self, message: str, max_items: int = 40) -> None:
        with self._lock:
            self.recent_log.insert(0, message)
            del self.recent_log[max_items:]

    def push_hud(
        self,
        text: str,
        kind: str = "info",
        key: str | None = None,
        cooldown: float = 20.0,
        max_items: int = 12,
    ) -> None:
        text = (text or "").strip()
        if not text:
            return
        now = time.monotonic()
        with self._lock:
            if key:
                last = self._hud_keys.get(key, 0.0)
                if now - last < cooldown:
                    return
                self._hud_keys[key] = now
            self.hud_alerts.insert(0, {"text": text, "kind": kind, "ts": now})
            del self.hud_alerts[max_items:]

    def clear_hud(self) -> None:
        with self._lock:
            self.hud_alerts.clear()
            self.hud_cards = []
            self._hud_keys.clear()
            self.opponent_champion = ""
            self.last_dragon_key = ""

    def set_analysis(self, text: str) -> None:
        with self._lock:
            self.analysis_text = text

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "status_label": self.status_label,
                "coach_running": self.coach_running,
                "voice_enabled": self.voice_enabled,
                "keep_range_enabled": self.keep_range_enabled,
                "vision_enabled": self.vision_enabled,
                "vision_champion": self.vision_champion,
                "vision_confidence": self.vision_confidence,
                "data_loaded": self.data_loaded,
                "game_time": self.game_time,
                "game_time_fmt": _fmt_time(self.game_time),
                "my_champion": self.my_champion,
                "my_role": self.my_role,
                "opponent_champion": self.opponent_champion,
                "dragon_us": self.dragon_us,
                "dragon_them": self.dragon_them,
                "dragon_score": f"{self.dragon_us} × {self.dragon_them}",
                "elder_phase": self.elder_phase,
                "last_dragon_key": self.last_dragon_key,
                "enemy_item_board": {
                    k: [dict(row) for row in (self.enemy_item_board.get(k) or [])]
                    for k in (
                        "cura",
                        "vampirismo",
                        "escudo",
                        "resistencia_magica",
                        "corta_cura",
                    )
                },
                "build_suggestion": self.build_suggestion,
                "hud_alerts": [dict(row) for row in self.hud_alerts],
                "hud_cards": [dict(row) for row in self.hud_cards],
                "recent_log": list(self.recent_log),
                "analysis_text": self.analysis_text,
            }


def _fmt_time(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


STATE = AppState()
