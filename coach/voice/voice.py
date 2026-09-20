"""
voice.py — Fila de fala (TTS) com cooldown por tipo de alerta, pra não floodar

Mantém um processo PowerShell + SAPI aberto o tempo todo (não spawna
um PowerShell novo a cada frase — isso adicionava ~1s de atraso por callout).

Usa a voz local do Narrador: Microsoft Antonio (Natural) - Portuguese (Brazil).
"""

import itertools
import os
import queue
import re
import subprocess
import threading
import time

from config import VOICE_RATE, VOICE_VOLUME, ALERT_COOLDOWN_SECONDS
from voice.tts_text import normalize_for_tts

_EXIT = "__EXIT__"
_CREATE_NO_WINDOW = 0x08000000


def _tts_parts(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts or [text.strip()]


def _powershell_tts_script(rate: int, volume: int) -> str:
    # OneCore = mesmas vozes do Narrador (Antonio Natural).
    # System.Speech sozinho só vê a Maria Desktop.
    return f"""
$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ExitToken = '{_EXIT}'
$Rate = {rate}
$Volume = {volume}
$speaker = $null
$picked = $false
$useDotNet = $false
try {{
  $speaker = New-Object -ComObject SAPI.SpVoice
  $speaker.Rate = $Rate
  $speaker.Volume = $Volume
  $cat = New-Object -ComObject SAPI.SpObjectTokenCategory
  $cat.SetId('HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech_OneCore\\Voices', $false)
  foreach ($t in $cat.EnumerateTokens('', '')) {{
    $d = $t.GetDescription()
    if ($d -match 'Antonio') {{ $speaker.Voice = $t; $picked = $true; break }}
  }}
}} catch {{
  $speaker = $null
}}
if (-not $picked) {{
  Add-Type -AssemblyName System.Speech
  $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $speaker.Rate = $Rate
  $speaker.Volume = $Volume
  $useDotNet = $true
  foreach ($v in $speaker.GetInstalledVoices()) {{
    if ($v.VoiceInfo.Name -match 'Antonio') {{ $speaker.SelectVoice($v.VoiceInfo.Name); break }}
  }}
}}
while ($null -ne ($line = [Console]::In.ReadLine())) {{
  if ($line -eq $ExitToken) {{ break }}
  if ($line.Length -gt 0) {{
    if ($useDotNet) {{ $speaker.Speak($line) }}
    else {{ [void]$speaker.Speak($line, 0) }}
  }}
}}
""".strip()


class VoiceCoach:
    def __init__(self):
        self._queue: queue.PriorityQueue[tuple[int, int, str | None]] = queue.PriorityQueue()
        self._seq = itertools.count()
        self._last_spoken: dict[str, float] = {}
        self._ready = threading.Event()
        self._backend = "unknown"
        self._voice_name: str | None = None
        self._proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()
        self._muted = False
        self._thread = threading.Thread(target=self._worker, daemon=True, name="VoiceCoach-TTS")
        self._thread.start()
        if not self._ready.wait(timeout=8):
            print("  [voice] AVISO: TTS demorou para iniciar. Audio pode falhar.")

    @property
    def voice_name(self) -> str:
        return self._voice_name or "Microsoft Antonio (Natural) - Portuguese (Brazil)"

    @property
    def backend(self) -> str:
        return self._backend

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def _rate_and_volume(self) -> tuple[int, int]:
        rate = max(-10, min(10, (VOICE_RATE - 150) // 10))
        volume = int(VOICE_VOLUME * 100)
        return rate, volume

    def _start_tts_process(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        rate, volume = self._rate_and_volume()
        kwargs: dict = dict(
            args=["powershell", "-NoProfile", "-Command", _powershell_tts_script(rate, volume)],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if os.name == "nt":
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        self._proc = subprocess.Popen(**kwargs)

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
            self._backend = "powershell-persistent"
            self._voice_name = "Microsoft Antonio (Natural) - Portuguese (Brazil)"
            print(f"  [voice] TTS ativo via System.Speech ({self._voice_name})")
        except Exception as exc:
            self._backend = "powershell-persistent"
            print(f"  [voice] System.Speech indisponivel ({exc}).")
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

        spoken = normalize_for_tts(text)
        parts = _tts_parts(spoken)
        for part in parts:
            print(f"  [VOZ] {part}")
            if self._muted:
                continue
            self._queue.put((-priority, next(self._seq), part))
