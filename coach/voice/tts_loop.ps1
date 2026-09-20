# Persistent TTS loop for the LoL coach.
# Prefers Microsoft Antonio (Natural) via WinRT; falls back to System.Speech (Maria).
$ErrorActionPreference = 'Continue'
$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$VoiceName = $env:COACH_TTS_VOICE
if ([string]::IsNullOrWhiteSpace($VoiceName)) {
  $VoiceName = 'Microsoft Antonio (Natural) - Portuguese (Brazil)'
}
$SapiRate = 2
if ($env:COACH_TTS_RATE) { $SapiRate = [int]$env:COACH_TTS_RATE }
$SapiVolume = 100
if ($env:COACH_TTS_VOLUME) { $SapiVolume = [int]$env:COACH_TTS_VOLUME }
$SpeakingRate = 1.17
if ($env:COACH_TTS_SPEAKING_RATE) { $SpeakingRate = [double]$env:COACH_TTS_SPEAKING_RATE }
$AudioPitch = 1.1
if ($env:COACH_TTS_PITCH) { $AudioPitch = [double]$env:COACH_TTS_PITCH }
$AudioVolume = 1.0
if ($env:COACH_TTS_AUDIO_VOLUME) { $AudioVolume = [double]$env:COACH_TTS_AUDIO_VOLUME }
$ExitToken = '__EXIT__'
if ($env:COACH_TTS_EXIT) { $ExitToken = $env:COACH_TTS_EXIT }

function Write-VoiceLog([string]$msg) {
  [Console]::Error.WriteLine($msg)
}

function Get-SearchTokens([string]$preferred) {
  $skip = @('Microsoft', 'Online', 'Natural', 'Portuguese', 'Brazil', 'Brasil', 'Desktop')
  $tokens = @()
  foreach ($part in ($preferred -split '[^A-Za-z0-9]+')) {
    if ($part -and ($skip -notcontains $part)) { $tokens += $part }
  }
  return $tokens
}

function Select-PreferredName([object[]]$names, [string]$preferred) {
  if (-not $names) { return $null }
  $p = $preferred.ToLowerInvariant()
  foreach ($n in $names) {
    if ($n -and $n.ToLowerInvariant() -eq $p) { return $n }
  }
  foreach ($n in $names) {
    if ($n -and $n.ToLowerInvariant().Contains($p)) { return $n }
  }
  $tokens = Get-SearchTokens $preferred
  foreach ($token in $tokens) {
    $t = $token.ToLowerInvariant()
    foreach ($n in $names) {
      if ($n -and $n.ToLowerInvariant().Contains($t)) { return $n }
    }
  }
  return $null
}

function Wait-WinRtOp($op, [int]$timeoutSec = 30) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while ($op.Status.ToString() -eq 'Started') {
    if ($sw.Elapsed.TotalSeconds -gt $timeoutSec) { throw "TTS timeout ($timeoutSec s)" }
    Start-Sleep -Milliseconds 15
  }
  $status = $op.Status.ToString()
  if ($status -eq 'Error') { throw "TTS error: $($op.ErrorCode)" }
  if ($status -eq 'Canceled') { throw 'TTS canceled' }
  return $op.GetResults()
}

$useWinRT = $false
$winrtSynth = $null
$sapi = $null
$selectedName = ''
$backend = 'none'

try {
  [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
  [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
  $winrtSynth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
  $voices = @([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices)
  $ptVoices = @($voices | Where-Object { $_.Language -like 'pt*' })
  $ptNames = @($ptVoices | ForEach-Object { $_.DisplayName })
  $allNames = @($voices | ForEach-Object { $_.DisplayName })
  $pick = Select-PreferredName $ptNames $VoiceName
  if (-not $pick) { $pick = Select-PreferredName $allNames $VoiceName }
  if (-not $pick) {
    $naturalPt = @($ptVoices | Where-Object { $_.DisplayName -match 'Natural' } | Select-Object -First 1)
    if ($naturalPt) { $pick = $naturalPt.DisplayName }
  }
  if (-not $pick -and $ptNames.Count -gt 0) { $pick = $ptNames[0] }
  if ($pick) {
    $match = $voices | Where-Object { $_.DisplayName -eq $pick } | Select-Object -First 1
    if ($match) {
      $winrtSynth.Voice = $match
      $winrtSynth.Options.SpeakingRate = $SpeakingRate
      $winrtSynth.Options.AudioPitch = $AudioPitch
      $winrtSynth.Options.AudioVolume = $AudioVolume
      $useWinRT = $true
      $selectedName = $match.DisplayName
      $backend = 'winrt-natural'
    }
  }
} catch {
  $useWinRT = $false
  $winrtSynth = $null
  Write-VoiceLog ("WINRT_FAIL:" + $_.Exception.Message)
}

if (-not $useWinRT) {
  try {
    Add-Type -AssemblyName System.Speech
    $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $sapi.Rate = $SapiRate
    $sapi.Volume = $SapiVolume
    $sapiNames = @($sapi.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
    $pick = Select-PreferredName $sapiNames $VoiceName
    if ($pick) {
      $sapi.SelectVoice($pick)
    } else {
      foreach ($v in $sapi.GetInstalledVoices()) {
        if ($v.VoiceInfo.Culture.Name -like 'pt*') {
          $sapi.SelectVoice($v.VoiceInfo.Name)
          break
        }
      }
    }
    $selectedName = $sapi.Voice.Name
    $backend = 'system-speech'
  } catch {
    Write-VoiceLog ("SAPI_FAIL:" + $_.Exception.Message)
    exit 1
  }
}

function Speak-WinRT-MediaPlayer($stream) {
  [Windows.Media.Playback.MediaPlayer, Windows.Media.Playback, ContentType = WindowsRuntime] | Out-Null
  [Windows.Media.Core.MediaSource, Windows.Media.Core, ContentType = WindowsRuntime] | Out-Null
  $player = [Windows.Media.Playback.MediaPlayer]::new()
  $player.CommandManager.IsEnabled = $false
  $player.Volume = $AudioVolume
  $player.Source = [Windows.Media.Core.MediaSource]::CreateFromStream($stream, $stream.ContentType)
  $player.Play()
  $waitMs = 400
  try { $waitMs = [Math]::Max(80, [int]$stream.Duration.TotalMilliseconds + 150) } catch {}
  Start-Sleep -Milliseconds $waitMs
  $player.Pause()
  $player.Source = $null
  $player.Dispose()
}

function Speak-WinRT([string]$text) {
  $stream = Wait-WinRtOp ($script:winrtSynth.SynthesizeTextToStreamAsync($text))
  try {
    $size = [uint32]$stream.Size
    $reader = [Windows.Storage.Streams.DataReader]::new($stream.GetInputStreamAt(0))
    [void](Wait-WinRtOp ($reader.LoadAsync($size)))
    $bytes = [byte[]]::new($size)
    try { $reader.ReadBytes($bytes) } catch { $reader.ReadBytes([ref]$bytes) }
    $ms = New-Object System.IO.MemoryStream -ArgumentList @(, $bytes)
    $player = New-Object System.Media.SoundPlayer
    $player.Stream = $ms
    $player.PlaySync()
    $player.Dispose()
    $ms.Dispose()
    $reader.Dispose()
  } catch {
    Write-VoiceLog ("SOUNDPLAYER_FAIL:" + $_.Exception.Message)
    Speak-WinRT-MediaPlayer $stream
  } finally {
    try { $stream.Dispose() } catch {}
  }
}

Write-VoiceLog ("VOICE:" + $selectedName)
Write-VoiceLog ("BACKEND:" + $backend)
Write-VoiceLog 'READY'

while ($null -ne ($line = [Console]::In.ReadLine())) {
  if ($line -eq $ExitToken) { break }
  if ($line.Length -le 0) { continue }
  try {
    if ($useWinRT) { Speak-WinRT $line }
    else { $sapi.Speak($line) }
  } catch {
    Write-VoiceLog ("SPEAK_FAIL:" + $_.Exception.Message)
  }
}
