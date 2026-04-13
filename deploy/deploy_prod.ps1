<#!
Production deploy (Windows PowerShell).

Prereqs:
  - SSH: define Host alias in %USERPROFILE%\.ssh\config (default name: besma-prod),
    OR pass -SshHost "user@hostname".
  - No keys/passwords in this repo.

Usage (avoid broken profile that runs Set-Location at startup):
  powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy_prod.ps1

Optional:
  -SshHost "ubuntu@api.example.com"
  -SshConfig "C:\Users\you\.ssh\config"
  -IdentityFile "D:\besma-rev\.secrets\besma-key.pem"   # if ssh-agent has no key (use .secrets/; gitignored)

Remote steps are in remote_prod_deploy.sh (piped to ssh ... "bash -s").
#>
param(
  [string]$SshHost = "besma-prod",
  [string]$SshConfig = "",
  [string]$IdentityFile = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RemoteBash = Join-Path $ScriptDir "remote_prod_deploy.sh"

if (-not (Test-Path -LiteralPath $RemoteBash)) {
  throw "remote_prod_deploy.sh not found: $RemoteBash"
}

function Test-SshConfigDefinesHost {
  param(
    [string]$ConfigPath,
    [string]$HostName
  )
  if (-not (Test-Path -LiteralPath $ConfigPath)) {
    return $false
  }
  foreach ($line in Get-Content -LiteralPath $ConfigPath) {
    if ($line -match '^\s*Host\s+(.+)$') {
      $names = ($matches[1] -split '\s+') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
      if ($names -contains $HostName) {
        return $true
      }
    }
  }
  return $false
}

$defaultConfig = Join-Path $env:USERPROFILE ".ssh\config"
$configPath = if ($SshConfig -ne "") { $SshConfig } else { $defaultConfig }

# Build ssh argument list (OpenSSH on Windows)
$sshArgs = @()
if ($IdentityFile -ne "") {
  if (-not (Test-Path -LiteralPath $IdentityFile)) {
    throw "IdentityFile not found: $IdentityFile"
  }
  $resolvedId = (Resolve-Path -LiteralPath $IdentityFile).Path
  $sshArgs += "-i", $resolvedId
}
if ($SshConfig -ne "" -and (Test-Path -LiteralPath $SshConfig)) {
  $sshArgs += "-F", $SshConfig
} elseif (Test-Path -LiteralPath $defaultConfig) {
  $sshArgs += "-F", $defaultConfig
}

# If using a bare Host alias (no @), warn when config does not list it
if ($SshHost -notmatch '@' -and (Test-Path -LiteralPath $configPath)) {
  if (-not (Test-SshConfigDefinesHost -ConfigPath $configPath -HostName $SshHost)) {
    Write-Host ""
    Write-Host "WARNING: Host '$SshHost' not found under 'Host' lines in: $configPath" -ForegroundColor Yellow
    Write-Host "Add something like:" -ForegroundColor Yellow
    Write-Host @"

Host besma-prod
  HostName your.server.example
  User ubuntu
  IdentityFile ~/.ssh/your_key

"@ -ForegroundColor DarkYellow
    Write-Host "Or run with: -SshHost `"user@hostname`"" -ForegroundColor Yellow
    Write-Host ""
  }
}

Write-Host ""
Write-Host "[deploy_prod] $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK') start -> ssh $SshHost" -ForegroundColor Cyan
Write-Host "[deploy_prod] script: $RemoteBash (stdin)" -ForegroundColor DarkGray
if ($sshArgs.Count -gt 0) {
  $redacted = $sshArgs -join ' '
  if ($IdentityFile -ne "") {
    $redacted = $redacted -replace [regex]::Escape((Resolve-Path -LiteralPath $IdentityFile).Path), '[identity]'
  }
  Write-Host "[deploy_prod] ssh args: $redacted" -ForegroundColor DarkGray
}

$raw = Get-Content -LiteralPath $RemoteBash -Raw -Encoding UTF8
if ([string]::IsNullOrWhiteSpace($raw)) {
  throw "remote_prod_deploy.sh is empty"
}

$unix = $raw -replace "`r`n", "`n" -replace "`r", "`n"

$sshCmd = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $sshCmd) {
  throw "ssh not found in PATH. Install OpenSSH Client (Windows Optional Feature)."
}

try {
  if ($sshArgs.Count -gt 0) {
    $unix | & ssh @sshArgs $SshHost "bash -s"
  } else {
    $unix | & ssh $SshHost "bash -s"
  }
  $exit = $LASTEXITCODE
} catch {
  Write-Host "[deploy_prod] ERROR: ssh threw: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

if ($exit -ne 0) {
  Write-Host "[deploy_prod] ERROR: ssh exit code $exit" -ForegroundColor Red
  Write-Host "  If you see 'Could not resolve hostname', fix ~/.ssh/config Host alias or use -SshHost." -ForegroundColor Red
  Write-Host "  If you see 'Permission denied (publickey)', pass -IdentityFile path\to\besma-key.pem (or use ssh-agent / ~/.ssh/config)." -ForegroundColor Red
  Write-Host "  If PowerShell profile errors appear first, use: powershell -NoProfile -File ..." -ForegroundColor Red
  Write-Host "  Check remote [prod-deploy ...] STEP lines above for the failing step." -ForegroundColor Red
  exit $exit
}

Write-Host ""
Write-Host "[deploy_prod] $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK') OK" -ForegroundColor Green
exit 0
