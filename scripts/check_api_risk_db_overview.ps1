# openapi.json에 GET /dashboard/risk-db-overview 경로가 있는지 확인 (배포 검증용)
param(
    [string]$BaseUrl = "https://api.besma.co.kr"
)
$ErrorActionPreference = "Stop"
$u = $BaseUrl.TrimEnd("/") + "/openapi.json"
Write-Host "GET $u"
$raw = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 25
if ($raw.Content -notmatch '"/dashboard/risk-db-overview"') {
    Write-Error "openapi.json missing path /dashboard/risk-db-overview (backend may be older than frontend)."
}
Write-Host "OK: /dashboard/risk-db-overview is listed in openapi.json"
