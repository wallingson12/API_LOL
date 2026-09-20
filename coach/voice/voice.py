"""
voice.py — Fila de fala (TTS) com cooldown por tipo de alerta, pra não floodar

Mesmo System.Speech local de sempre. Escolhe Microsoft Antonio (Natural)
em vez da primeira voz pt-BR (Maria Desktop).
"""

import itertools
import os
import queue
import re
import subprocess
import tempfile
import threading
import time

from config import VOICE_RATE, VOICE_VOLUME, ALERT_COOLDOWN_SECONDS
from voice.tts_text import normalize_for_tts

_EXIT = "__EXIT__"
_CREATE_NO_WINDOW = 0x08000000
_PREFERRED_VOICE = "Antonio"

_PS1 = r"""
$ErrorActionPreference = 'Continue'
$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$Rate = 2
if ($env:COACH_TTS_RATE) { $Rate = [int]$env:COACH_TTS_RATE }
$Volume = 100
if ($env:COACH_TTS_VOLUME) { $Volume = [int]$env:COACH_TTS_VOLUME }
$ExitToken = '__EXIT__'
function Log([string]$m) { [Console]::Error.WriteLine($m) }

$speaker = $null
$picked = $null

try {
  $speaker = New-Object -ComObject SAPI.SpVoice
  $speaker.Rate = $Rate
  $speaker.Volume = $Volume
  $cat = New-Object -ComObject SAPI.SpObjectTokenCategory
  $cat.SetId('HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices', $false)
  $tokens = $cat.EnumerateTokens('', '')
  foreach ($t in $tokens) {
    $d = $t.GetDescription()
    Log ("TOKEN:" + $d)
    if (-not $picked -and $d -match 'Antonio') {
      $speaker.Voice = $t
      $picked = $d
    }
  }
} catch {
  Log ("ONECORE_COM_FAIL:" + $_.Exception.Message)
}

if (-not $picked) {
  Add-Type -AssemblyName System.Speech
  $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $speaker.Rate = $Rate
  $speaker.Volume = $Volume
  foreach ($v in $speaker.GetInstalledVoices()) {
    $n = $v.VoiceInfo.Name
    Log ("SAPI:" + $n)
    if (-not $picked -and $n -match 'Antonio') {
      $speaker.SelectVoice($n)
      $picked = $n
    }
  }
  if (-not $picked) {
    foreach ($v in $speaker.GetInstalledVoices()) {
      if ($v.VoiceInfo.Culture.Name -like 'pt*') {
        $speaker.SelectVoice($v.VoiceInfo.Name)
        $picked = $v.VoiceInfo.Name
        break
      }
    }
  }
  $useDotNet = $true
} else {
  $useDotNet = $false
}

Log ("VOICE:" + $picked)
Log 'READY'

while ($null -ne ($line = [Console]::In.ReadLine())) {
  if ($line -eq $ExitToken) { break }
  if ($line.Length -le 0) { continue }
  try {
    if ($useDotNet) { $speaker.Speak($line) }
    else { [void]$speaker.Speak($line, 0) }
  } catch {
    Log ("SPEAK_FAIL:" + $_.Exception.Message)
  }
}
""".strip()


def _tts_parts(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts or [text.strip()]


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
        self._ps1_path = self._write_ps1()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="VoiceCoach-TTS")
        self._thread.start()
        if not self._ready.wait(timeout=20):
            print("  [voice] AVISO: TTS demorou para iniciar. Audio pode falhar.")

    @property
    def voice_name(self) -> str:
        return self._voice_name or _PREFERRED_VOICE

    @property
    def backend(self) -> str:
        return self._backend

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def _write_ps1(self) -> str:
        path = os.path.join(tempfile.gettempdir(), "coach_antonio_tts.ps1")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_PS1)
        return path

    def _rate_and_volume(self) -> tuple[int, int]:
        rate = max(-10, min(10, (VOICE_RATE - 150) // 10))
        volume = int(VOICE_VOLUME * 100)
        return rate, volume

    def _tts_env(self) -> dict[str, str]:
        rate, volume = self._rate_and_volume()
        env = os.environ.copy()
        env["COACH_TTS_RATE"] = str(rate)
        env["COACH_TTS_VOLUME"] = str(volume)
        env["COACH_TTS_VOICE"] = _PREFERRED_VOICE
        return env

    def _handle_stderr_line(self, line: str) -> None:
        text = line.strip()
        if not text or text == "READY":
            return
        if text.startswith("VOICE:"):
            self._voice_name = text[6:].strip() or self._voice_name
            return
        print(f"  [voice] {text}")

    def _wait_until_ready(self, timeout: float = 15.0) -> bool:
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

    def _drain_stderr(self) -> None:
        proc = self._proc
        if not proc or not proc.stderr:
            return
        for raw in proc.stderr:
            self._handle_stderr_line(raw)

    def _start_tts_process(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        kwargs: dict = dict(
            args=["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", self._ps1_path],
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
        self._wait_until_ready()
        threading.Thread(target=self._drain_stderr, daemon=True, name="VoiceCoach-TTS-err").start()

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
            shown = self._voice_name or "(detectando voz)"
            print("  [voice] ANTONIO-LOCAL 2026-09-20")
            print(f"  [voice] TTS local ({shown})")
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
