# BESMA 로컬 개발 환경 일괄 준비 (Windows)
# 사용: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$SecretsDir = Join-Path $RepoRoot ".secrets"
$DbPath = Join-Path $RepoRoot "database\besma.db"

function Write-Step([string]$Msg) {
  Write-Host ""
  Write-Host "==> $Msg" -ForegroundColor Cyan
}

Write-Host "BESMA local setup" -ForegroundColor Green
Write-Host "Repo: $RepoRoot"

# --- SSH key check (배포용, 로컬 MVP 실행에는 불필요) ---
Write-Step "SSH key (besma-key.pem) — 배포용"
$keyCandidates = @(
  "Z:\4. 안전보건관리실\besma-key.pem",
  (Join-Path $SecretsDir "besma-key.pem"),
  (Join-Path $RepoRoot "besma-key.pem"),
  (Join-Path $env:USERPROFILE "Downloads\besma-key.pem"),
  (Join-Path $env:USERPROFILE ".ssh\besma-key.pem")
)
$foundKey = $null
foreach ($p in $keyCandidates) {
  if (Test-Path -LiteralPath $p) {
    $foundKey = (Resolve-Path -LiteralPath $p).Path
    break
  }
}
if ($foundKey) {
  Write-Host "  FOUND: $foundKey" -ForegroundColor Green
  if (-not (Test-Path -LiteralPath (Join-Path $SecretsDir "besma-key.pem"))) {
    New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null
    Copy-Item -LiteralPath $foundKey -Destination (Join-Path $SecretsDir "besma-key.pem") -Force
    Write-Host "  Copied to .secrets\besma-key.pem" -ForegroundColor Green
  }
} else {
  Write-Host "  NOT FOUND — 로컬 백엔드+프론트 실행은 가능, 운영 서버 배포(SSH)는 불가" -ForegroundColor Yellow
  Write-Host "  키 복구 후: .secrets\besma-key.pem 에 두고 deploy\fix_ssh_key_permissions.ps1 실행" -ForegroundColor DarkGray
}

# --- Python backend ---
Write-Step "Backend venv + pip"
$py = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Push-Location $BackendDir
  try {
    py -3.11 -m venv .venv
  } finally {
    Pop-Location
  }
}
& $py -m pip install --upgrade pip | Out-Null
& (Join-Path $BackendDir ".venv\Scripts\pip.exe") install -r (Join-Path $BackendDir "requirements.txt")

# --- DB init (fresh install: seed create_all → alembic stamp) ---
Write-Step "Database init"
$env:ENV = "local"
$env:DEV_BYPASS_AUTH = "true"
$env:PYTHONPATH = $BackendDir
Push-Location $BackendDir
try {
  if (-not (Test-Path -LiteralPath $DbPath)) {
    Write-Host "  Fresh DB: seed_data + alembic stamp head"
    & $py -m app.seed.seed_data
    & $py -m alembic stamp head
  } else {
    Write-Host "  Existing DB: alembic upgrade head + seed sync"
    & $py -m alembic upgrade head
    & $py -m app.seed.seed_data
  }
} finally {
  Pop-Location
}

# --- Frontend ---
Write-Step "Frontend npm install"
Push-Location $FrontendDir
try {
  npm install
} finally {
  Pop-Location
}

# --- Env files ---
Write-Step "Env files"
if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
  Copy-Item (Join-Path $RepoRoot ".env.example") (Join-Path $RepoRoot ".env")
  Write-Host "  Created .env from .env.example — BESMA_SSH_KEY_PATH 확인" -ForegroundColor Yellow
}
if (-not (Test-Path (Join-Path $FrontendDir ".env.local"))) {
  @"
VITE_API_BASE_URL=http://127.0.0.1:8001
"@ | Set-Content -Encoding UTF8 (Join-Path $FrontendDir ".env.local")
  Write-Host "  Created frontend/.env.local"
}

Write-Step "Done"
Write-Host "  Full local:  .\run_local_mvp.bat"
Write-Host "  Frontend:    .\run_frontend.bat  → http://127.0.0.1:5174"
Write-Host "  Backend:     .\run_backend.bat   → http://127.0.0.1:8001/health"
Write-Host "  Demo login:  hq01 / 1111  (본사),  site01 / 1111  (현장)"
Write-Host "  기능인제 소장: ID=소속현장코드, PW=소장 주민번호 앞6자리 (HQ 명부 반영 후 발급)"
if (-not $foundKey) {
  Write-Host ""
  Write-Host "  besma-key.pem 없음 → 프론트만(운영 API): frontend/.env.local 에" -ForegroundColor Yellow
  Write-Host "  VITE_API_BASE_URL=https://api.besma.co.kr 로 변경" -ForegroundColor Yellow
}
