param(
    [string]$Voice = "Microsoft An",
    [int]$Rate = 1
)

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$release = Join-Path $project "Warfront_Release"
$segmentsPath = Join-Path $release "narration_segments.json"
$clipsDir = Join-Path $release "narration_clips"
$outputPath = Join-Path $release "WarfrontCommand_narration_vi.wav"

New-Item -ItemType Directory -Force -Path $clipsDir | Out-Null
Add-Type -AssemblyName System.Speech
$segments = Get-Content -Raw -Encoding UTF8 $segmentsPath | ConvertFrom-Json
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice($Voice)
$speaker.Rate = $Rate
$speaker.Volume = 100

for ($index = 0; $index -lt $segments.Count; $index++) {
    $path = Join-Path $clipsDir ("segment_{0:D3}.wav" -f $index)
    $speaker.SetOutputToWaveFile($path)
    $speaker.Speak([string]$segments[$index].text)
    $speaker.SetOutputToNull()
    Write-Host ("generated {0}" -f $path)
}

$speaker.Dispose()
python (Join-Path $PSScriptRoot "combine_narration_wav.py") $segmentsPath $clipsDir $outputPath 855
