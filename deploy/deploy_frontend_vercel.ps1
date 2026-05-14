param(
  [string]$RepoRoot = "",
  [string]$Scope = "",
  [string]$Project = "",
  [string]$RootDirectory = "",
  [switch]$SkipBuild,
  [switch]$RunLogin,
  [switch]$AllowDirtyWorkingTree,
  [switch]$SkipGitPreflightFetch
)

$ErrorActionPreference = "Stop"

function Get-EnvMap {
  param([string]$EnvPath)
  $map = @{}
  if (-not (Test-Path -LiteralPath $EnvPath)) {
    return $map
  }
  foreach ($line in Get-Content -LiteralPath $EnvPath) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) {
      continue
    }
    $parts = $trimmed -split "=", 2
    if ($parts.Count -ne 2) {
      continue
    }
    $key = $parts[0].Trim()
    $value = $parts[1].Trim()
    if ($key -ne "") {
      $map[$key] = $value
    }
  }
  return $map
}

function Resolve-Setting {
  param(
    [string]$Explicit,
    [hashtable]$EnvMap,
    [string]$Key,
    [string]$Fallback
  )
  if ($Explicit -ne "") { return $Explicit }
  if ($EnvMap.ContainsKey($Key) -and $EnvMap[$Key] -ne "") { return $EnvMap[$Key] }
  return $Fallback
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoFallback = Split-Path -Parent $scriptDir
$envPath = Join-Path $repoFallback ".env"
$envMap = Get-EnvMap -EnvPath $envPath

$RepoRoot = Resolve-Setting -Explicit $RepoRoot -EnvMap $envMap -Key "VERCEL_DEPLOY_REPO_ROOT" -Fallback $repoFallback
$Scope = Resolve-Setting -Explicit $Scope -EnvMap $envMap -Key "VERCEL_DEPLOY_SCOPE" -Fallback ""
$Project = Resolve-Setting -Explicit $Project -EnvMap $envMap -Key "VERCEL_DEPLOY_PROJECT" -Fallback ""
$RootDirectory = Resolve-Setting -Explicit $RootDirectory -EnvMap $envMap -Key "VERCEL_DEPLOY_ROOT" -Fallback "frontend"

if (-not (Test-Path -LiteralPath $RepoRoot)) {
  throw "RepoRoot not found: $RepoRoot"
}

$localSha = (git -C $RepoRoot rev-parse HEAD).Trim()
Write-Host "[vercel-deploy] Local HEAD SHA: $localSha" -ForegroundColor Yellow
git -C $RepoRoot log -1 --oneline
if (-not $SkipGitPreflightFetch) {
  git -C $RepoRoot fetch origin
}
$porcelain = @(git -C $RepoRoot status --porcelain 2>$null)
if ($porcelain.Count -gt 0) {
  if ($AllowDirtyWorkingTree) {
    Write-Host "[vercel-deploy] WARNING: working tree is not clean ($($porcelain.Count) path(s)). Vercel uploads from disk — you may ship uncommitted files. For predictable prod, commit and use a clean tree." -ForegroundColor Yellow
  } else {
    throw "[vercel-deploy] Working tree is not clean. Commit (or stash), or pass -AllowDirtyWorkingTree to deploy anyway."
  }
}

if ($Scope -eq "") {
  throw "VERCEL_DEPLOY_SCOPE is required (.env or -Scope)."
}
if ($Project -eq "") {
  throw "VERCEL_DEPLOY_PROJECT is required (.env or -Project)."
}

$frontendDir = Join-Path $RepoRoot $RootDirectory
if (-not (Test-Path -LiteralPath $frontendDir)) {
  throw "Frontend root not found: $frontendDir"
}

$voltaVercel = (volta which vercel).Trim()
if (-not $voltaVercel) {
  throw "volta which vercel failed. Install or expose Vercel CLI first."
}
$vercelJs = Join-Path (Split-Path -Parent $voltaVercel) "node_modules\vercel\dist\vc.js"
if (-not (Test-Path -LiteralPath $vercelJs)) {
  throw "Vercel CLI entry not found: $vercelJs"
}

$patchFile = Join-Path $env:TEMP "vercel-hostname-patch.js"
@"
const os = require('os');
os.hostname = () => 'win10-pc';
"@ | Set-Content -LiteralPath $patchFile -Encoding ASCII

function Invoke-PatchedVercel {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
  )
  & node -r $patchFile $vercelJs @Args
  if ($LASTEXITCODE -ne 0) {
    throw "Vercel command failed: $($Args -join ' ')"
  }
}

Write-Host ""
Write-Host "[vercel-deploy] RepoRoot: $RepoRoot" -ForegroundColor Cyan
Write-Host "[vercel-deploy] Scope: $Scope / Project: $Project / RootDirectory: $RootDirectory" -ForegroundColor DarkGray

if ($RunLogin) {
  Write-Host "[vercel-deploy] login" -ForegroundColor Cyan
  Invoke-PatchedVercel login
}

Write-Host "[vercel-deploy] verify login" -ForegroundColor Cyan
Invoke-PatchedVercel whoami

if (-not $SkipBuild) {
  Write-Host "[vercel-deploy] npm run build ($frontendDir)" -ForegroundColor Cyan
  npm --prefix $frontendDir run build
  if ($LASTEXITCODE -ne 0) {
    throw "Frontend build failed."
  }
}

Write-Host "[vercel-deploy] link project" -ForegroundColor Cyan
Push-Location $frontendDir
try {
  Invoke-PatchedVercel link --yes --project $Project --scope $Scope
  Invoke-PatchedVercel pull --yes --environment=production --scope $Scope
} finally {
  Pop-Location
}

Write-Host "[vercel-deploy] deploy production" -ForegroundColor Cyan
Push-Location $RepoRoot
try {
  Invoke-PatchedVercel deploy --prod --yes --scope $Scope --cwd $RepoRoot
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "[vercel-deploy] DONE" -ForegroundColor Green
