"""Bridge do coach → analyzer (histórico Riot API). Evita conflito de config.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

_ANALYZER_DIR = Path(__file__).resolve().parents[2] / "analyzer"
_PYTHON = sys.executable

FILAS_UI = {
    "1": "Ranked Solo/Duo",
    "2": "Ranked Flex",
    "3": "ARAM",
    "4": "Normal Draft",
    "5": "Normal Blind",
    "6": "Todas as filas",
}


def run_match_history(
    *,
    modo: str = "pessoal",
    fila_key: str = "1",
    qtd: int | None = None,
    riot_id: str | None = None,
    on_line: Callable[[str], None] | None = None,
) -> dict:
    """Executa analyzer/runner.py em processo separado e devolve stdout."""
    if not _ANALYZER_DIR.exists():
        return {"ok": False, "log": "", "error": f"Pasta analyzer não encontrada: {_ANALYZER_DIR}"}

    cmd = [
        _PYTHON,
        str(_ANALYZER_DIR / "runner.py"),
        "--modo", modo,
        "--fila", fila_key,
    ]
    if qtd:
        cmd.extend(["--qtd", str(qtd)])
    if riot_id:
        cmd.extend(["--riot-id", riot_id])

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_ANALYZER_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            lines.append(line)
            if on_line:
                on_line(line)
        code = proc.wait()
        log = "\n".join(lines)
        if code != 0:
            return {"ok": False, "log": log, "error": "Análise terminou com erro (veja log)."}
        return {"ok": True, "log": log, "error": None}
    except Exception as exc:
        return {"ok": False, "log": "", "error": str(exc)}
