"""
voice.py — Fila de fala (TTS) com cooldown por tipo de alerta, pra não floodar

Mantém um processo PowerShell aberto o tempo todo (não spawna um PowerShell
novo a cada frase — isso adicionava ~1s de atraso por callout).

Usa Microsoft Antonio (Natural) via WinRT quando a voz está instalada no
Windows; cai para System.Speech (Maria Desktop) se o natural não existir.
"""

from __future__ import annotations

import itertools
import os
import queue
import re
import subprocess
import threading
import time

from config import (
    ALERT_COOLDOWN_SECONDS,
    VOICE_NAME,
    VOICE_PITCH,
    VOICE_RATE,
    VOICE_VOLUME,
)
from voice.tts_text import is_neural_voice, normalize_for_tts

_EXIT = "__EXIT__"
_CREATE_NO_WINDOW = 0x08000000
_TTS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_loop.ps1")


def _tts_parts(text: str) -> list[str]:
    """Quebra em frases — o backend natural aguenta mais, mas o corte ainda ajuda."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts or [text.strip()]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class VoiceCoach:
    def __init__(self):
        self._queue: queue.PriorityQueue[tuple[int, int, str | None]] = queue.PriorityQueue()
        self._seq = itertools.count()
        self._last_spoken: dict[str, float] = {}
        self._ready = threading.Event()
        self._backend = "unknown"
        self._voice_name: str | None = None
        self._neural = is_neural_voice(VOICE_NAME)
        self._proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()
        self._muted = False
        self._stderr_thread: threading.Thread | None = None
        self._thread = threading.Thread(target=self._worker, daemon=True, name="VoiceCoach-TTS")
        self._thread.start()
        if not self._ready.wait(timeout=25):
            print("  [voice] AVISO: TTS demorou para iniciar. Audio pode falhar.")

    @property
    def voice_name(self) -> str:
        return self._voice_name or VOICE_NAME

    @property
    def backend(self) -> str:
        return self._backend

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def _rate_and_volume(self) -> tuple[int, int]:
        rate = max(-10, min(10, (VOICE_RATE - 150) // 10))
        volume = int(VOICE_VOLUME * 100)
        return rate, volume

    def _tts_env(self) -> dict[str, str]:
        rate, volume = self._rate_and_volume()
        env = os.environ.copy()
        env["COACH_TTS_VOICE"] = VOICE_NAME
        env["COACH_TTS_RATE"] = str(rate)
        env["COACH_TTS_VOLUME"] = str(volume)
        env["COACH_TTS_SPEAKING_RATE"] = str(round(_clamp(VOICE_RATE / 150.0, 0.5, 6.0), 3))
        env["COACH_TTS_PITCH"] = str(round(_clamp(VOICE_PITCH, 0.0, 2.0), 3))
        env["COACH_TTS_AUDIO_VOLUME"] = str(round(_clamp(VOICE_VOLUME, 0.0, 1.0), 3))
        env["COACH_TTS_EXIT"] = _EXIT
        return env

    def _handle_stderr_line(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        if text.startswith("VOICE:"):
            self._voice_name = text[6:].strip() or self._voice_name
            self._neural = is_neural_voice(self._voice_name or "")
            print(f"  [voice] selecionada: {self._voice_name}")
            return
        if text.startswith("BACKEND:"):
            self._backend = text[8:].strip() or self._backend
            print(f"  [voice] backend: {self._backend}")
            return
        if text == "READY":
            return
        print(f"  [voice] {text}")

    def _drain_stderr(self) -> None:
        proc = self._proc
        if not proc or not proc.stderr:
            return
        for raw in proc.stderr:
            self._handle_stderr_line(raw)

    def _wait_until_ready(self, timeout: float = 20.0) -> bool:
        proc = self._proc
        if not proc or not proc.stderr:
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                return False
            raw = proc.stderr.readline()
            if not raw:
                return False
            line = raw.strip()
            self._handle_stderr_line(line)
            if line == "READY":
                return True
        return False

    def _start_tts_process(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        kwargs: dict = dict(
            args=["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", _TTS_SCRIPT],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=self._tts_env(),
        )
        if os.name == "nt":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        self._proc = subprocess.Popen(**kwargs)
        ready = self._wait_until_ready()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True, name="VoiceCoach-TTS-err"
        )
        self._stderr_thread.start()
        if not ready:
            print("  [voice] AVISO: loop TTS nao sinalizou READY.")

    def _stop_tts_process(self) -> None:
        proc = self._proc
        if not proc or proc.poll() is not None:
            self._proc = None
            return
        try:
            if proc.stdin:
                proc.stdin.write(f"{_EXIT}\n")
                proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        self._proc = None

    def _speak_line(self, text: str) -> None:
        line = text.replace("\r", " ").replace("\n", " ").strip()
        if not line:
            return
        with self._proc_lock:
            self._start_tts_process()
            assert self._proc and self._proc.stdin
            try:
                self._proc.stdin.write(line + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                self._stop_tts_process()
                self._start_tts_process()
                if self._proc and self._proc.stdin:
                    self._proc.stdin.write(line + "\n")
                    self._proc.stdin.flush()

    def _worker(self):
        try:
            self._start_tts_process()
            if self._backend == "unknown":
                self._backend = "powershell-persistent"
            print("  [voice] build: antonio-d239")
            shown = self._voice_name or VOICE_NAME
            print(f"  [voice] TTS ativo ({self._backend}: {shown})")
            if shown and "maria" in shown.casefold() and "antonio" in VOICE_NAME.casefold():
                print("  [voice] AVISO: Antonio Natural nao foi selecionado. Instale a voz no Windows.")
        except Exception as exc:
            self._backend = "powershell-persistent"
            print(f"  [voice] System.Speech/WinRT indisponivel ({exc}).")
        finally:
            self._ready.set()

        while True:
            _priority, _seq, text = self._queue.get()
            if text is None:
                self._queue.task_done()
                self._stop_tts_process()
                break

            try:
                self._speak_line(text)
            except Exception as exc:
                print(f"  [voice] ERRO ao falar: {exc}")

            self._queue.task_done()

    def test_speak(self) -> bool:
        """Fala uma frase curta na inicializacao para confirmar que o audio funciona."""
        self.say("Coach de voz pronto.", alert_key=None, cooldown=0)
        deadline = time.time() + 12
        while self._queue.unfinished_tasks > 0 and time.time() < deadline:
            time.sleep(0.05)
        return self._backend != "unknown"

    def say(
        self,
        text: str,
        alert_key: str | None = None,
        cooldown: int = ALERT_COOLDOWN_SECONDS,
        priority: int = 0,
    ):
        now = time.time()
        if alert_key:
            last = self._last_spoken.get(alert_key, 0)
            if now - last < cooldown:
                return
            self._last_spoken[alert_key] = now

        spoken = normalize_for_tts(text, phonetic=not self._neural)
        parts = _tts_parts(spoken)
        for part in parts:
            print(f"  [VOZ] {part}")
            if self._muted:
                continue
            self._queue.put((-priority, next(self._seq), part))
