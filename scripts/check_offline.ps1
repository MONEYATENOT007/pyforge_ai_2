param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
Write-Host "Read-only PyForge preflight; no model or package download."
& $PythonExe -m pyforge doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
