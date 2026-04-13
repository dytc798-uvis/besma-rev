<#!
운영 서버 일괄 배포 (Windows / PowerShell).

전제:
  - 로컬 SSH config에 Host 별칭 `besma-prod` 가 정의되어 있어야 한다.
  - 저장소에 비밀키·비밀번호를 넣지 않는다.

사용:
  저장소 루트 또는 아무 경로에서:
    powershell -ExecutionPolicy Bypass -File .\deploy\deploy_prod.ps1

실패 시:
  - 원격 스크립트는 단계마다 [prod-deploy ...] 로그를 남긴다.
  - 마지막에 실패한 단계가 stderr에 이어진다.
#>
param()

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RemoteBash = Join-Path $ScriptDir "remote_prod_deploy.sh"

if (-not (Test-Path -LiteralPath $RemoteBash)) {
  throw "[deploy_prod.ps1] remote_prod_deploy.sh not found: $RemoteBash"
}

$sshHost = "besma-prod"
Write-Host ""
Write-Host "[deploy_prod.ps1] $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK') 시작 — ssh ${sshHost}" -ForegroundColor Cyan
Write-Host "[deploy_prod.ps1] 원격 스크립트: $RemoteBash (stdin으로 전달)" -ForegroundColor DarkGray

$raw = Get-Content -LiteralPath $RemoteBash -Raw -Encoding UTF8
if ([string]::IsNullOrWhiteSpace($raw)) {
  throw "[deploy_prod.ps1] remote_prod_deploy.sh is empty"
}

# Unix 줄바꿈으로 통일 (로컬 CRLF만 있어도 원격 bash가 해석 가능하도록)
$unix = $raw -replace "`r`n", "`n" -replace "`r", "`n"

try {
  $unix | ssh $sshHost "bash -s"
  $exit = $LASTEXITCODE
} catch {
  Write-Host "[deploy_prod.ps1] ERROR: ssh 호출 예외 — $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

if ($exit -ne 0) {
  Write-Host "[deploy_prod.ps1] ERROR: ssh 종료 코드 $exit (원격 로그의 STEP 확인)" -ForegroundColor Red
  exit $exit
}

Write-Host ""
Write-Host "[deploy_prod.ps1] $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK') 성공적으로 완료" -ForegroundColor Green
exit 0
