param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$app = Join-Path $projectRoot "pyforge\ui\app.py"
$python = if ([IO.Path]::IsPathRooted($PythonExe)) { $PythonExe } else { Join-Path $projectRoot $PythonExe }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python executable not found: $python" }
$env:PYTHONPATH = $projectRoot
$env:PYFORGE_DATA_ROOT = Join-Path $projectRoot "local_runtime\data"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
& $python -m streamlit run $app --server.address 127.0.0.1 --server.port $Port --server.headless true --server.runOnSave true --browser.gatherUsageStats false
