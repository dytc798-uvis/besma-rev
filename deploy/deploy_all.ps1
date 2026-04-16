param(
  [string]$RepoRoot = "D:\besma-rev",
  [string]$Branch = "main",
  [string]$RemoteUser = "ubuntu",
  [string]$RemoteHost = "api.besma.co.kr",
  [string]$RemoteProjectRoot = "/home/ubuntu/besma-rev",
  [string]$SshKeyPath = "$env:USERPROFILE\Downloads\besma-key.pem",
  [switch]$RunMigrations = $true,
  [switch]$SkipPush,
  [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"

function Exec-Step {
  param(
    [string]$Title,
    [scriptblock]$Action
  )
  Write-Host ""
  Write-Host "==> $Title" -ForegroundColor Cyan
  & $Action
}

if (!(Test-Path -LiteralPath $RepoRoot)) {
  throw "RepoRoot not found: $RepoRoot"
}

if (!(Test-Path -LiteralPath $SshKeyPath)) {
  throw "SSH key not found: $SshKeyPath"
}

$backendDeployCmd = if ($RunMigrations) { "RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh" } else { "./deploy/deploy_backend.sh" }
$remoteCmd = @"
set -e
cd $RemoteProjectRoot
git pull --ff-only
chmod +x ./deploy/deploy_backend.sh
$backendDeployCmd
curl -fsS http://127.0.0.1:8001/health
"@

Exec-Step "Show local git branch and latest commit" {
  git -C $RepoRoot branch --show-current
  git -C $RepoRoot log -1 --oneline
}

if (-not $SkipFrontendBuild) {
  Exec-Step "Build frontend (local check only)" {
    npm --prefix "$RepoRoot/frontend" run build
  }
}

if (-not $SkipPush) {
  Exec-Step "Push code to origin/$Branch" {
    git -C $RepoRoot push origin $Branch
  }
}

Exec-Step "Deploy backend on remote server" {
  # Windows CRLF in here-string breaks remote bash (`set: invalid option`, `cd: ...\r`).
  $unix = ($remoteCmd -replace "`r`n", "`n" -replace "`r", "`n").TrimEnd()
  $unix | & ssh -i $SshKeyPath "$RemoteUser@$RemoteHost" "bash -s"
}

Exec-Step "Verify API endpoints on remote" {
  ssh -i $SshKeyPath "$RemoteUser@$RemoteHost" "curl -i http://127.0.0.1:8001/notices | head -n 1; curl -i 'http://127.0.0.1:8001/safety-policy-goals/view?scope=HQ' | head -n 1; curl -i 'http://127.0.0.1:8001/dynamic-menus/sidebar?ui_type=HQ_SAFE' | head -n 1"
}

Write-Host ""
Write-Host "Deploy completed." -ForegroundColor Green
