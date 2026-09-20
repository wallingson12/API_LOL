# Persistent TTS loop. Forces Microsoft Antonio (Natural) from Speech_OneCore.
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

function Pick-VoiceName([object[]]$names, [string]$preferred) {
  $list = @()
  foreach ($n in @($names)) {
    if ($n -and "$n".Trim().Length -gt 0) { $list += "$n" }
  }
  if ($list.Count -eq 0) { return $null }
  $pref = $preferred.ToLowerInvariant()
  foreach ($n in $list) {
    if ($n.ToLowerInvariant() -eq $pref) { return $n }
  }
  foreach ($n in $list) {
    $l = $n.ToLowerInvariant()
    if ($l.Contains('antonio') -and $l.Contains('natural')) { return $n }
  }
  foreach ($n in $list) {
    if ($n.ToLowerInvariant().Contains('antonio')) { return $n }
  }
  foreach ($n in $list) {
    if ($n.ToLowerInvariant().Contains($pref)) { return $n }
  }
  return $null
}

function Wait-WinRtOp($op, [int]$timeoutSec = 30) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while ($true) {
    $st = $op.Status.ToString()
    if ($st -ne 'Started' -and $st -ne '0') { break }
    if ($sw.Elapsed.TotalSeconds -gt $timeoutSec) { throw "TTS timeout ($timeoutSec s)" }
    Start-Sleep -Milliseconds 15
  }
  $status = $op.Status.ToString()
  if ($status -eq 'Error' -or $status -eq '3') { throw "TTS error: $($op.ErrorCode)" }
  if ($status -eq 'Canceled' -or $status -eq '2') { throw 'TTS canceled' }
  return $op.GetResults()
}

function Get-WinRtVoiceList {
  $all = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
  $list = @()
  $count = 0
  try { $count = [int]$all.Count } catch { try { $count = [int]$all.Size } catch { $count = 0 } }
  if ($count -gt 0) {
    for ($i = 0; $i -lt $count; $i++) {
      $v = $null
      try { $v = $all.Item($i) } catch { try { $v = $all[$i] } catch {} }
      if ($v) { $list += $v }
    }
  }
  if ($list.Count -eq 0) {
    foreach ($v in $all) { if ($v) { $list += $v } }
  }
  return @($list)
}

$cs = @'
using System;
using System.Collections;
using System.Reflection;
using System.Speech.Synthesis;

public static class SpeechApiOneCore
{
    public static int InjectOneCoreVoices(SpeechSynthesizer synthesizer)
    {
        Type synthType = typeof(SpeechSynthesizer);
        Type objectTokenCategoryType = synthType.Assembly.GetType("System.Speech.Internal.ObjectTokens.ObjectTokenCategory");
        Type voiceInfoType = synthType.Assembly.GetType("System.Speech.Synthesis.VoiceInfo");
        Type installedVoiceType = synthType.Assembly.GetType("System.Speech.Synthesis.InstalledVoice");
        if (objectTokenCategoryType == null || voiceInfoType == null || installedVoiceType == null)
            throw new NotSupportedException("System.Speech internal types not found");

        object voiceSynthesizer = GetMember(synthesizer, "VoiceSynthesizer", true);
        if (voiceSynthesizer == null)
            throw new NotSupportedException("Property not found: VoiceSynthesizer");

        IList installedVoices = GetMember(voiceSynthesizer, "_installedVoices", false) as IList;
        if (installedVoices == null)
            throw new NotSupportedException("Field not found: _installedVoices");

        MethodInfo create = objectTokenCategoryType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic);
        if (create == null)
            throw new NotSupportedException("ObjectTokenCategory.Create not found");
        object otc = create.Invoke(null, new object[] { @"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices" });
        if (otc == null)
            throw new NotSupportedException("ObjectTokenCategory.Create failed");

        int added = 0;
        try
        {
            MethodInfo find = objectTokenCategoryType.GetMethod("FindMatchingTokens", BindingFlags.Instance | BindingFlags.NonPublic);
            IList tokens = find.Invoke(otc, new object[] { null, null }) as IList;
            if (tokens == null)
                throw new NotSupportedException("FindMatchingTokens failed");

            foreach (object token in tokens)
            {
                if (token == null || GetMember(token, "Attributes", true) == null)
                    continue;

                object voiceInfo = synthType.Assembly.CreateInstance(
                    voiceInfoType.FullName, true,
                    BindingFlags.Instance | BindingFlags.NonPublic, null,
                    new object[] { token }, null, null);
                if (voiceInfo == null)
                    continue;

                object installedVoice = synthType.Assembly.CreateInstance(
                    installedVoiceType.FullName, true,
                    BindingFlags.Instance | BindingFlags.NonPublic, null,
                    new object[] { voiceSynthesizer, voiceInfo }, null, null);
                if (installedVoice == null)
                    continue;

                InstalledVoice ivNew = (InstalledVoice)installedVoice;
                if (ivNew.VoiceInfo == null)
                    continue;
                string newName = ivNew.VoiceInfo.Name;
                bool exists = false;
                foreach (InstalledVoice iv in installedVoices)
                {
                    if (iv != null && iv.VoiceInfo != null && iv.VoiceInfo.Name == newName)
                    {
                        exists = true;
                        break;
                    }
                }
                if (exists)
                    continue;
                installedVoices.Add(installedVoice);
                added++;
            }
        }
        finally
        {
            IDisposable d = otc as IDisposable;
            if (d != null) d.Dispose();
        }
        return added;
    }

    private static object GetMember(object target, string name, bool property)
    {
        BindingFlags flags = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        if (property)
        {
            PropertyInfo p = target.GetType().GetProperty(name, flags);
            return p == null ? null : p.GetValue(target, null);
        }
        FieldInfo f = target.GetType().GetField(name, flags);
        return f == null ? null : f.GetValue(target);
    }
}
'@

Add-Type -AssemblyName System.Speech
try {
  if (-not ([System.Management.Automation.PSTypeName]'SpeechApiOneCore').Type) {
    $speechRef = [System.Speech.Synthesis.SpeechSynthesizer].Assembly.Location
    Add-Type -ReferencedAssemblies $speechRef -TypeDefinition $cs
  }
} catch {
  Write-VoiceLog ("ONECORE_COMPILE_FAIL:" + $_.Exception.Message)
}

function Copy-OneCoreToUserSapi {
  $src = 'HKLM:\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens'
  if (-not (Test-Path $src)) {
    Write-VoiceLog 'ONECORE_REG_MISSING'
    return
  }
  $dests = @(
    'HKCU:\SOFTWARE\Microsoft\Speech\Voices\Tokens',
    'HKCU:\SOFTWARE\WOW6432Node\Microsoft\Speech\Voices\Tokens'
  )
  $n = 0
  foreach ($dest in $dests) {
    if (-not (Test-Path $dest)) {
      New-Item -Path $dest -Force | Out-Null
    }
    Get-ChildItem $src -ErrorAction SilentlyContinue | ForEach-Object {
      Copy-Item -Path $_.PSPath -Destination (Join-Path $dest $_.PSChildName) -Recurse -Force -ErrorAction SilentlyContinue
      $n++
    }
  }
  Write-VoiceLog ("ONECORE_REG_COPIED:" + $n)
}

$useWinRT = $false
$winrtSynth = $null
$sapi = $null
$sapiPick = $null
$winrtPick = $null
$selectedName = ''
$backend = 'none'

# --- SAPI + OneCore primeiro: e o mesmo Speak() que ja funciona neste PC ---
try {
  Copy-OneCoreToUserSapi
  $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $sapi.Rate = $SapiRate
  $sapi.Volume = $SapiVolume
  try {
    $added = [SpeechApiOneCore]::InjectOneCoreVoices($sapi)
    Write-VoiceLog ("ONECORE_INJECTED:" + $added)
  } catch {
    Write-VoiceLog ("ONECORE_INJECT_FAIL:" + $_.Exception.Message)
  }
  $sapiNames = @($sapi.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
  Write-VoiceLog ("SAPI_VOICES:" + ($sapiNames -join ' | '))
  $sapiPick = Pick-VoiceName $sapiNames $VoiceName
  if ($sapiPick) {
    $sapi.SelectVoice($sapiPick)
    $selectedName = $sapi.Voice.Name
    $backend = 'sapi-onecore'
    Write-VoiceLog ("SAPI_SELECTED:" + $selectedName)
  } else {
    Write-VoiceLog 'SAPI_NO_ANTONIO'
  }
} catch {
  Write-VoiceLog ("SAPI_FAIL:" + $_.Exception.Message)
}

# --- WinRT so se o SAPI nao achou o Antonio ---
if (-not $sapiPick) {
  try {
    [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
    [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
    $winrtSynth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
    $winrtVoices = @(Get-WinRtVoiceList)
    $winrtNames = @($winrtVoices | ForEach-Object { $_.DisplayName })
    Write-VoiceLog ("WINRT_VOICES:" + ($winrtNames -join ' | '))
    $winrtPick = Pick-VoiceName $winrtNames $VoiceName
    if ($winrtPick) {
      $match = $winrtVoices | Where-Object { $_.DisplayName -eq $winrtPick } | Select-Object -First 1
      if ($match) {
        $winrtSynth.Voice = $match
        try {
          $winrtSynth.Options.SpeakingRate = $SpeakingRate
          $winrtSynth.Options.AudioPitch = $AudioPitch
          $winrtSynth.Options.AudioVolume = $AudioVolume
        } catch {
          Write-VoiceLog ("WINRT_OPTIONS:" + $_.Exception.Message)
        }
        $useWinRT = $true
        $selectedName = $match.DisplayName
        $backend = 'winrt-natural'
      }
    } else {
      Write-VoiceLog 'WINRT_NO_ANTONIO'
    }
  } catch {
    $useWinRT = $false
    $winrtSynth = $null
    Write-VoiceLog ("WINRT_FAIL:" + $_.Exception.Message)
  }
}

if (-not $useWinRT -and $sapi -and -not $sapiPick) {
  foreach ($v in $sapi.GetInstalledVoices()) {
    if ($v.VoiceInfo.Culture.Name -like 'pt*') {
      $sapi.SelectVoice($v.VoiceInfo.Name)
      $selectedName = $sapi.Voice.Name
      $backend = 'system-speech'
      Write-VoiceLog ("FALLBACK_VOICE:" + $selectedName)
      break
    }
  }
}

if ([string]::IsNullOrWhiteSpace($selectedName) -and $sapi) {
  $selectedName = $sapi.Voice.Name
  $backend = 'system-speech'
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
    if ($useWinRT) {
      try { Speak-WinRT $line }
      catch {
        Write-VoiceLog ("WINRT_SPEAK_FAIL:" + $_.Exception.Message)
        if ($sapi) { $sapi.Speak($line) }
        else { throw }
      }
    } else {
      $sapi.Speak($line)
    }
  } catch {
    Write-VoiceLog ("SPEAK_FAIL:" + $_.Exception.Message)
  }
}
