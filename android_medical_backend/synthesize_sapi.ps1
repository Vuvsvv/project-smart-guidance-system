param(
    [Parameter(Mandatory=$true)]
    [string]$Text,

    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = -1
$synth.Volume = 100
$synth.SetOutputToWaveFile($OutputPath)
$synth.Speak($Text)
$synth.Dispose()
