param([int]$Port = 11434)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot "local_runtime"
$ollamaExe = Join-Path $runtimeRoot "ollama\ollama.exe"
if (-not (Test-Path -LiteralPath $ollamaExe -PathType Leaf)) {
    throw "Portable Ollama is missing: $ollamaExe"
}

$models = Join-Path $runtimeRoot "models"
$tempDir = Join-Path $runtimeRoot "tmp"
$logs = Join-Path $runtimeRoot "logs"
New-Item -ItemType Directory -Force -Path $models, $tempDir, $logs | Out-Null

$endpoint = "http://127.0.0.1:$Port/api/version"
try {
    $existing = Invoke-RestMethod -Uri $endpoint -TimeoutSec 2
    throw "Port $Port already has an Ollama server (version $($existing.version)); refusing to use it without verifying its model location."
} catch [System.Net.WebException] {
    # No server on this loopback port.
}

# These settings are inherited by the child process only; no global environment is changed.
$env:OLLAMA_HOST = "127.0.0.1:$Port"
$env:OLLAMA_MODELS = $models
$env:OLLAMA_NO_CLOUD = "1"
$env:OLLAMA_MAX_LOADED_MODELS = "1"
$env:TEMP = $tempDir
$env:TMP = $tempDir

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$process = Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WorkingDirectory (Split-Path -Parent $ollamaExe) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "$stamp-stdout.log") -RedirectStandardError (Join-Path $logs "$stamp-stderr.log")
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($process.HasExited) { throw "Ollama exited with code $($process.ExitCode). Inspect $logs." }
    try {
        $version = Invoke-RestMethod -Uri $endpoint -TimeoutSec 2
        Write-Output "Ollama $($version.version) started: PID $($process.Id); models=$models; cloud disabled; loopback port=$Port"
        exit 0
    } catch [System.Net.WebException] {
        Start-Sleep -Seconds 1
    }
}
throw "Ollama did not become ready within 30 seconds. Inspect $logs."
