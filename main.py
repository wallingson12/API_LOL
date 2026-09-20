"""Ponto de entrada — interface gráfica controla o coach."""

import sys
from pathlib import Path

_COACH_DIR = Path(__file__).resolve().parent / "coach"
if str(_COACH_DIR) not in sys.path:
    sys.path.insert(0, str(_COACH_DIR))

from engine import CoachEngine
from ui.desktop import run_ui


def main():
    print("API_LOL ANTONIO-LOCAL 2026-09-20")
    engine = CoachEngine()
    try:
        run_ui(engine)
    except KeyboardInterrupt:
        engine.stop()


if __name__ == "__main__":
    main()
