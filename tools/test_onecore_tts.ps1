$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object { $_.Language -eq "vi-VN" } |
    Select-Object -First 1
if ($null -eq $voice) {
    throw "No vi-VN OneCore voice found"
}
$synth.Voice = $voice
Write-Host ("voice=" + $voice.DisplayName)
$operation = $synth.SynthesizeTextToStreamAsync("Xin chào. Đây là bản thử giọng tiếng Việt cho Warfront Command.")
while ($operation.Status -eq 0) {
    Start-Sleep -Milliseconds 40
}
if ($operation.Status -ne 1) {
    throw ("Synthesis failed with WinRT status " + $operation.Status)
}
$stream = $operation.GetResults()
$readStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
$outputPath = Join-Path (Split-Path -Parent $PSScriptRoot) "Warfront_Release\onecore_voice_test.wav"
$output = [IO.File]::Create($outputPath)
$readStream.CopyTo($output)
$output.Dispose()
$readStream.Dispose()
$stream.Dispose()
$synth.Dispose()
Write-Host ("wrote=" + $outputPath)
