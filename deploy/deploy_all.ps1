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

# deploy_backend.sh already loops on HEALTH_URL; avoid a duplicate trailing curl in the remote script
# (PowerShell/SSH edge cases caused libcurl exit 3 "Malformed URL" on some runs).
$backendDeployCmd = if ($RunMigrations) { "RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh" } else { "./deploy/deploy_backend.sh" }
$backendDeployCmd = $backendDeployCmd.Trim()

$cleanUntrackedVersions = if ($RemoteGitCleanUntracked) {
  @(
    'echo "[deploy] RemoteGitCleanUntracked: removing untracked files under backend/alembic/versions"'
    "git clean -fd backend/alembic/versions/"
  ) -join "`n"
} else { "" }

# Build remote bash with explicit LF joins so CRLF from the .ps1 file cannot produce `script.sh\r` on the server.
$remoteParts = [System.Collections.Generic.List[string]]::new()
$remoteParts.Add("set -eo pipefail")
$remoteParts.Add("cd $RemoteProjectRoot")
if (-not [string]::IsNullOrWhiteSpace($cleanUntrackedVersions)) {
  foreach ($ln in ($cleanUntrackedVersions -split "`n")) {
    $t = $ln.Trim().Trim([char]13)
    if ($t.Length -gt 0) { $remoteParts.Add($t) }
  }
}
$remoteParts.Add("git pull --ff-only")
$remoteParts.Add('echo "[deploy] Remote HEAD after pull: $(git rev-parse HEAD)"')
$remoteParts.Add("git log -1 --oneline")
$remoteParts.Add("chmod +x ./deploy/deploy_backend.sh")
$remoteParts.Add($backendDeployCmd)
$deployScriptBody = (($remoteParts | ForEach-Object { ($_ + "").Replace("`r", "").TrimEnd() }) -join "`n").TrimEnd() + "`n"

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
  # Avoid piping a string into ssh stdin from Windows PowerShell (can inject stray CR / phantom lines after deploy_backend).
  $tmpLocal = Join-Path ([System.IO.Path]::GetTempPath()) ("besma-remote-deploy-" + [Guid]::NewGuid().ToString() + ".sh")
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  try {
    [System.IO.File]::WriteAllText($tmpLocal, $deployScriptBody, $utf8NoBom)
    $tmpRemote = "/tmp/besma-remote-deploy-$([Guid]::NewGuid().ToString('N')).sh"
    & scp -i $SshKeyPath -q $tmpLocal "${RemoteUser}@${RemoteHost}:$tmpRemote"
    if ($LASTEXITCODE -ne 0) {
      throw "scp deploy script to remote failed (exit $LASTEXITCODE)."
    }
    & ssh -i $SshKeyPath "${RemoteUser}@${RemoteHost}" $('chmod +x {0} && bash {0}; ec=$?; rm -f {0}; exit $ec' -f $tmpRemote)
    if ($LASTEXITCODE -ne 0) {
      throw "Remote deploy failed (ssh exit $LASTEXITCODE). Check EC2 git pull / merge and deploy_backend.sh logs above."
    }
  }
  finally {
    if (Test-Path -LiteralPath $tmpLocal) {
      Remove-Item -LiteralPath $tmpLocal -Force -ErrorAction SilentlyContinue
    }
  }
}

Exec-Step "Verify API endpoints on remote" {
  $remoteVerify = @'
set -e
curl -fsS http://127.0.0.1:8001/health >/dev/null
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/notices | head -n 1
curl -sS -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8001/safety-policy-goals/view?scope=HQ" | head -n 1
curl -sS -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8001/dynamic-menus/sidebar?ui_type=HQ_SAFE" | head -n 1
'@
  $verifyBody = ([regex]::Replace(($remoteVerify -replace "`r`n", "`n" -replace "`r", "").TrimEnd(), "`r+", "")).TrimEnd() + "`n"
  $tmpLocalV = Join-Path ([System.IO.Path]::GetTempPath()) ("besma-remote-verify-" + [Guid]::NewGuid().ToString() + ".sh")
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  try {
    [System.IO.File]::WriteAllText($tmpLocalV, $verifyBody, $utf8NoBom)
    $tmpRemoteV = "/tmp/besma-remote-verify-$([Guid]::NewGuid().ToString('N')).sh"
    & scp -i $SshKeyPath -q $tmpLocalV "${RemoteUser}@${RemoteHost}:$tmpRemoteV"
    if ($LASTEXITCODE -ne 0) {
      throw "scp verify script to remote failed (exit $LASTEXITCODE)."
    }
    & ssh -i $SshKeyPath "${RemoteUser}@${RemoteHost}" $('chmod +x {0} && bash {0}; ec=$?; rm -f {0}; exit $ec' -f $tmpRemoteV)
    if ($LASTEXITCODE -ne 0) {
      throw "Remote verification ssh failed (exit $LASTEXITCODE)."
    }
  }
  finally {
    if (Test-Path -LiteralPath $tmpLocalV) {
      Remove-Item -LiteralPath $tmpLocalV -Force -ErrorAction SilentlyContinue
    }
  }
}

Write-Host ""
Write-Host "Deploy completed." -ForegroundColor Green
