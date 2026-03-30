Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Run Alembic migrations for local SQLite DB (with backup)

$backendDir = Resolve-Path "$PSScriptRoot\.."
Push-Location $backendDir
try {
$py = Join-Path (Resolve-Path "$PSScriptRoot\..") ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  throw "venv python not found: $py"
}

$env:PYTHONPATH = $backendDir

$dbPath = (& $py -c "from app.config.settings import settings; from pathlib import Path; print(Path(settings.sqlite_path).resolve())")
if (-not (Test-Path $dbPath)) {
  throw "DB not found: $dbPath"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "$dbPath.$timestamp.bak"
Copy-Item -Path $dbPath -Destination $backupPath -Force
Write-Host "Backup created: $backupPath"

& $py -m alembic -c "alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}

