# backend venv에서 app.main import 검증 (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Error "venv python 없음: $Py"
}
$env:ENV = if ($env:ENV) { $env:ENV } else { "prod" }
Push-Location $Backend
try {
    & $Py -c "from app.main import app; print('verify_backend_import: OK')"
} finally {
    Pop-Location
}
