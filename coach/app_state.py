"""Estado compartilhado entre o coach e a interface desktop."""

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    status: str = "stopped"  # stopped | idle | champ_select | in_game | post_game
    status_label: str = "Coach parado"
    coach_running: bool = False
    voice_enabled: bool = True  # sempre ligada — sem toggle na UI
    keep_range_enabled: bool = False
    data_loaded: bool = False
    game_time: float = 0.0
    my_champion: str = ""
    my_role: str = ""
    dragon_us: int = 0
    dragon_them: int = 0
    elder_phase: bool = False
    # Quadro: inimigos com itens táticos (só UI + voz na hora da compra)
    enemy_item_board: dict = field(default_factory=lambda: {
        "cura": [],
        "vampirismo": [],
        "escudo": [],
        "resistencia_magica": [],
        "corta_cura": [],
    })
    recent_log: list[str] = field(default_factory=list)
    analysis_text: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def log(self, message: str, max_items: int = 40) -> None:
        with self._lock:
            self.recent_log.insert(0, message)
            del self.recent_log[max_items:]

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
                "data_loaded": self.data_loaded,
                "game_time": self.game_time,
                "game_time_fmt": _fmt_time(self.game_time),
                "my_champion": self.my_champion,
                "my_role": self.my_role,
                "dragon_us": self.dragon_us,
                "dragon_them": self.dragon_them,
                "dragon_score": f"{self.dragon_us} × {self.dragon_them}",
                "elder_phase": self.elder_phase,
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
                "recent_log": list(self.recent_log),
                "analysis_text": self.analysis_text,
            }


def _fmt_time(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


STATE = AppState()
