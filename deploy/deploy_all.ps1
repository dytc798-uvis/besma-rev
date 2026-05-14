param(
  [string]$RepoRoot = "",
  [string]$Branch = "main",
  [string]$RemoteUser = "ubuntu",
  [string]$RemoteHost = "api.besma.co.kr",
  [string]$RemoteProjectRoot = "/home/ubuntu/besma-rev",
  [string]$SshKeyPath = "",
  [switch]$RunMigrations = $true,
  [switch]$SkipPush,
  [switch]$SkipFrontendBuild,
  [switch]$AllowDirtyWorkingTree,
  [switch]$AllowSkipPushUnpushed,
  [switch]$SkipGitPreflightFetch,
  [switch]$RemoteGitCleanUntracked
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $RepoRoot = Split-Path -Parent $scriptDir
}

function Get-DotEnvValue {
  param([string]$EnvPath, [string]$Key)
  if (-not (Test-Path -LiteralPath $EnvPath)) { return "" }
  foreach ($line in Get-Content -LiteralPath $EnvPath) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
    $parts = $trimmed -split "=", 2
    if ($parts.Count -ne 2) { continue }
    if ($parts[0].Trim() -eq $Key) { return $parts[1].Trim() }
  }
  return ""
}

function Resolve-BesmaSshKeyPath {
  param([string]$RepoRoot)
  $envPath = Join-Path $RepoRoot ".env"
  $fromEnv = Get-DotEnvValue -EnvPath $envPath -Key "BESMA_SSH_KEY_PATH"
  $candidates = @(
    $fromEnv,
    (Join-Path $RepoRoot ".secrets\besma-key.pem"),
    (Join-Path $RepoRoot "besma-key.pem"),
    (Join-Path $env:USERPROFILE "Downloads\besma-key.pem")
  ) | Where-Object { $_ -ne "" }
  foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
  }
  return ""
}

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

$defaultDownloads = Join-Path $env:USERPROFILE "Downloads\besma-key.pem"
if ([string]::IsNullOrWhiteSpace($SshKeyPath)) {
  $SshKeyPath = Resolve-BesmaSshKeyPath -RepoRoot $RepoRoot
  if ([string]::IsNullOrWhiteSpace($SshKeyPath)) {
    throw "SSH key not found. Set BESMA_SSH_KEY_PATH in .env (see .env.example), place besma-key.pem under .secrets\, or pass -SshKeyPath. Tried: .env BESMA_SSH_KEY_PATH, .secrets\besma-key.pem, repo root, $defaultDownloads"
  }
} elseif (-not (Test-Path -LiteralPath $SshKeyPath)) {
  throw "SSH key not found: $SshKeyPath"
}

$backendDeployCmd = if ($RunMigrations) { "RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh" } else { "./deploy/deploy_backend.sh" }
$cleanUntrackedVersions = if ($RemoteGitCleanUntracked) {
  @"
echo "[deploy] RemoteGitCleanUntracked: removing untracked files under backend/alembic/versions"
git clean -fd backend/alembic/versions/
"@
} else { "" }
$remoteCmd = @"
set -eo pipefail
cd $RemoteProjectRoot
$cleanUntrackedVersions
git pull --ff-only
echo "[deploy] Remote HEAD after pull: `$(git rev-parse HEAD)"
git log -1 --oneline
chmod +x ./deploy/deploy_backend.sh
$backendDeployCmd
curl -fsS 'http://127.0.0.1:8001/health'
"@

Exec-Step "Git preflight (branch, SHA, fetch, clean tree, push policy)" {
  $currentBranch = (git -C $RepoRoot branch --show-current).Trim()
  if ($currentBranch -ne $Branch) {
    throw "Current git branch is '$currentBranch' but -Branch is '$Branch'. Checkout $Branch or pass -Branch."
  }
  Write-Host "Branch: $currentBranch (deploy target: $Branch)" -ForegroundColor Yellow
  $localSha = (git -C $RepoRoot rev-parse HEAD).Trim()
  Write-Host "Local HEAD SHA: $localSha" -ForegroundColor Yellow
  git -C $RepoRoot log -1 --oneline
  if (-not $SkipGitPreflightFetch) {
    git -C $RepoRoot fetch origin
  }
  $porcelain = @(git -C $RepoRoot status --porcelain 2>$null)
  if ($porcelain.Count -gt 0) {
    if ($AllowDirtyWorkingTree) {
      Write-Host "WARNING: working tree is not clean ($($porcelain.Count) path(s)). EC2 only receives committed+pushed history; uncommitted edits will NOT run on the server." -ForegroundColor Yellow
    } else {
      throw "Working tree is not clean. Commit (or stash) before deploy, or pass -AllowDirtyWorkingTree to override. Uncommitted fixes do not reach EC2 via git pull."
    }
  }
  if ($SkipPush) {
    $aheadLine = git -C $RepoRoot rev-list --count "origin/$Branch..HEAD" 2>$null
    $ahead = 0
    if ($LASTEXITCODE -eq 0 -and $aheadLine -match '^\d+$') {
      $ahead = [int]$aheadLine.Trim()
    }
    if ($ahead -gt 0) {
      if ($AllowSkipPushUnpushed) {
        Write-Host "WARNING: -SkipPush but local is $ahead commit(s) ahead of origin/$Branch; server will not see them until you push." -ForegroundColor Yellow
      } else {
        throw "Local is $ahead commit(s) ahead of origin/$Branch but -SkipPush is set. Push first or pass -AllowSkipPushUnpushed to deploy old origin tip anyway."
      }
    }
  }
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
  if ($LASTEXITCODE -ne 0) {
    throw "Remote deploy failed (ssh exit $LASTEXITCODE). Check EC2 git pull / merge and deploy_backend.sh logs above."
  }
}

Exec-Step "Verify API endpoints on remote" {
  # Single-quoted here-string: PowerShell must not parse `&` or `?` inside remote URLs (curl exit 3 / malformed URL).
  $remoteVerify = @'
set -e
curl -fsS 'http://127.0.0.1:8001/health' >/dev/null
curl -fsS -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8001/notices' | head -n 1
curl -fsS -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8001/safety-policy-goals/view?scope=HQ' | head -n 1
curl -fsS -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8001/dynamic-menus/sidebar?ui_type=HQ_SAFE' | head -n 1
'@
  $unixVerify = ($remoteVerify -replace "`r`n", "`n" -replace "`r", "`n").TrimEnd()
  $unixVerify | & ssh -i $SshKeyPath "$RemoteUser@$RemoteHost" "bash -s"
  if ($LASTEXITCODE -ne 0) {
    throw "Remote verification ssh failed (exit $LASTEXITCODE)."
  }
}

Write-Host ""
Write-Host "Deploy completed." -ForegroundColor Green
