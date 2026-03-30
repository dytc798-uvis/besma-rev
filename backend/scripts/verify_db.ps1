Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$backendDir = Resolve-Path "$PSScriptRoot\.."
Push-Location $backendDir
try {
$py = Join-Path (Resolve-Path "$PSScriptRoot\..") ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  throw "venv python not found: $py"
}

$env:PYTHONPATH = $backendDir

& $py "scripts\verify_document_instances_schema.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 의미 보존 진단(후보가 0건이어야 통과)
& $py "scripts\diagnose_document_instances_fallback_candidates.py" --limit 200 --report-dir "reports"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}

