param([int]$Port = 8501)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$app = Join-Path $projectRoot "pyforge\ui\app.py"
$logs = Join-Path $projectRoot "local_runtime\logs"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python executable not found: $python" }
if (-not (Test-Path -LiteralPath $app -PathType Leaf)) { throw "Chat app not found: $app" }
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -eq "127.0.0.1" } |
    Select-Object -First 1
if ($listener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $expectedBare = '"' + $python + '" -m streamlit run ' + $app + ' '
    $expectedQuoted = '"' + $python + '" -m streamlit run "' + $app + '" '
    $owned = $owner -and (
        $owner.CommandLine.StartsWith($expectedBare, [StringComparison]::OrdinalIgnoreCase) -or
        $owner.CommandLine.StartsWith($expectedQuoted, [StringComparison]::OrdinalIgnoreCase)
    )
    if (-not $owned -or
        -not $owner.CommandLine.Contains("--server.port $Port")) {
        throw "Port $Port belongs to a process that is not this project's Streamlit server; refusing to stop it."
    }
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($owner.ParentProcessId)"
    Stop-Process -Id $owner.ProcessId -Force
    $parentOwned = $parent -and (
        $parent.CommandLine.StartsWith($expectedBare, [StringComparison]::OrdinalIgnoreCase) -or
        $parent.CommandLine.StartsWith($expectedQuoted, [StringComparison]::OrdinalIgnoreCase)
    )
    if ($parentOwned) {
        Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
    }
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $stillListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $stillListening) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port did not close after stopping PyForge."
    }
}

$env:PYTHONPATH = $projectRoot
$env:PYFORGE_DATA_ROOT = Join-Path $projectRoot "local_runtime\data"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdout = Join-Path $logs "$stamp-chat-stdout.log"
$stderr = Join-Path $logs "$stamp-chat-stderr.log"
$arguments = @(
    "-m", "streamlit", "run", ('"' + $app + '"'),
    "--server.address", "127.0.0.1",
    "--server.port", "$Port",
    "--server.headless", "true",
    "--server.runOnSave", "true",
    "--browser.gatherUsageStats", "false"
)
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$health = "http://127.0.0.1:$Port/_stcore/health"
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    if ($process.HasExited) { throw "PyForge exited with code $($process.ExitCode); inspect $stderr" }
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $health -TimeoutSec 2
        if ($response.StatusCode -eq 200 -and $response.Content.Trim() -eq "ok") {
            Write-Output "PyForge chat ready at http://127.0.0.1:$Port (launcher PID $($process.Id)); logs: $stdout, $stderr"
            exit 0
        }
    } catch [System.Net.WebException] {
        Start-Sleep -Milliseconds 500
    }
}
throw "PyForge did not become healthy on port $Port; inspect $stderr"
