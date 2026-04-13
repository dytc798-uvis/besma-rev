<#!
Windows에서 OpenSSH가 요구하는 형태로 개인키 ACL을 맞춘다.
"Permissions too open" / icacls 거절 시: 관리자 PowerShell에서 재실행하거나 -CopyToUserSsh 사용.

사용:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\fix_ssh_key_permissions.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\fix_ssh_key_permissions.ps1 -KeyPath "D:\besma-rev\besma-key.pem"
  powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\fix_ssh_key_permissions.ps1 -CopyToUserSsh
#>
param(
  [string]$KeyPath = "",
  [switch]$CopyToUserSsh
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$candidates = @(
  (Join-Path $repoRoot ".secrets\besma-key.pem"),
  (Join-Path $repoRoot "besma-key.pem")
)

if ($KeyPath -eq "") {
  foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c) {
      $KeyPath = $c
      break
    }
  }
}

if ($KeyPath -eq "" -or -not (Test-Path -LiteralPath $KeyPath)) {
  throw "키 파일을 찾을 수 없습니다. -KeyPath 로 전체 경로를 지정하세요. 후보: $($candidates -join ', ')"
}

$KeyPath = (Resolve-Path -LiteralPath $KeyPath).Path
$targetPath = $KeyPath

if ($CopyToUserSsh) {
  $sshDir = Join-Path $env:USERPROFILE ".ssh"
  if (-not (Test-Path -LiteralPath $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
  }
  $targetPath = Join-Path $sshDir "besma-key.pem"
  Copy-Item -LiteralPath $KeyPath -Destination $targetPath -Force
  Write-Host "[fix_ssh_key] copied to: $targetPath (ACL will be fixed here)" -ForegroundColor Cyan
}

$user = $env:USERNAME
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value

Write-Host "[fix_ssh_key] target: $targetPath" -ForegroundColor Cyan
Write-Host "[fix_ssh_key] user: $user (SID $sid)" -ForegroundColor DarkGray

function Invoke-IcaclsExe {
  # icacls stdout 이 반환값과 섞이지 않도록 Out-Host 로 호스트만 출력.
  param([Parameter(Mandatory)][string[]]$IcArguments)
  & icacls.exe @IcArguments | Out-Host
  $exit = $LASTEXITCODE
  if ($null -eq $exit) { $exit = 0 }
  return [int]$exit
}

# 1) 상속 끄기 + 본인에게 읽기만
$code = Invoke-IcaclsExe -IcArguments @($targetPath, "/inheritance:r")
if ($code -ne 0) {
  Write-Host "[fix_ssh_key] ERROR: icacls /inheritance:r failed (exit $code). Try:" -ForegroundColor Red
  Write-Host "  1) PowerShell을 '관리자 권한으로 실행'한 뒤 다시 이 스크립트 실행" -ForegroundColor Yellow
  Write-Host "  2) 관리자 CMD: takeown /f `"$targetPath`"" -ForegroundColor Yellow
  Write-Host "  3) 또는 -CopyToUserSsh 로 $env:USERPROFILE\.ssh\ 아래 복사본에 ACL 적용" -ForegroundColor Yellow
  exit $code
}

$code = Invoke-IcaclsExe -IcArguments @($targetPath, "/grant:r", "${user}:R")
if ($code -ne 0) {
  Write-Host "[fix_ssh_key] ERROR: icacls /grant failed (exit $code). 관리자 권한 또는 takeown 필요." -ForegroundColor Red
  exit $code
}

# 2) 흔한 '다른 사람에게 읽힘' 원인 제거 (없으면 무시)
$removes = @(
  "BUILTIN\Users",
  "Everyone",
  "NT AUTHORITY\Authenticated Users"
)
foreach ($r in $removes) {
  $null = & icacls.exe $targetPath /remove $r 2>$null
}

Write-Host "[fix_ssh_key] current ACL:" -ForegroundColor Cyan
& icacls.exe $targetPath

Write-Host ""
Write-Host "[fix_ssh_key] OK. Test with:" -ForegroundColor Green
Write-Host "  ssh -i `"$targetPath`" ubuntu@api.besma.co.kr" -ForegroundColor White
Write-Host "  deploy: -IdentityFile `"$targetPath`"" -ForegroundColor White
