$ErrorActionPreference='Stop'
$taskRoot='D:\JSI\workfiles\besma-renewal-20261026'
$python=Join-Path $taskRoot '.venv-daily\Scripts\python.exe'
$day=Get-Date -Format 'yyyy-MM-dd'
$receipt="D:\JSI\safety-workbench\work\attendance-daily\$day\latest.json"
if(-not(Test-Path -LiteralPath $receipt)){exit 0}
$options=@('-i','E:\SecureKeys\ssh\besma-ncp-ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519')
$fingerprint=(& ssh-keygen -y -f 'E:\SecureKeys\ssh\besma-ncp-ed25519' | & ssh-keygen -lf -) -join ''
$hostFingerprint=(& ssh-keygen -F '101.79.24.88' -l) -join ''
if($fingerprint -notmatch [regex]::Escape('SHA256:Iihen1N6ttLDlzN96IzsaOYGf2tAl8l7kvAc7C8S/2Y') -or $hostFingerprint -notmatch [regex]::Escape('SHA256:UdTiy0n77FCIzWM3HESLqY7plu8UATBBpzjWe+UK09g')){throw 'SSH fingerprint verification failed'}
$catalog=Join-Path $taskRoot 'private\daily-publish-catalog.json'
$catalogJson=& ssh @options 'besma-admin@101.79.24.88' 'sudo /srv/besma/backend/.venv/bin/python -B /srv/besma/tools/receive_workspace_attendance.py --catalog'
if($LASTEXITCODE -ne 0){throw 'Catalog read failed'}
$catalogJson | Set-Content -LiteralPath $catalog -Encoding utf8
$out=Join-Path $taskRoot ('private\daily-attendance-'+$day.Replace('-','')+'.json')
& $python -X utf8 (Join-Path $taskRoot 'release\tools\build-daily-attendance.py') --receipt $receipt --catalog $catalog --out $out
if($LASTEXITCODE -ne 0){throw 'Daily attendance validation failed'}
$hash=(Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLowerInvariant()
$remote='/home/besma-admin/.besma-workspace-attendance-inbox/besma-daily-attendance-'+$day.Replace('-','')+'-'+$hash.Substring(0,12)+'.json'
& scp @options $out ('besma-admin@101.79.24.88:'+$remote)
if($LASTEXITCODE -ne 0){throw 'Daily upload failed'}
$result=& ssh @options 'besma-admin@101.79.24.88' ('sudo /srv/besma/backend/.venv/bin/python -B /srv/besma/tools/receive_workspace_attendance.py '+$remote)
if($LASTEXITCODE -ne 0){throw 'Daily apply failed'}
$result | Set-Content -LiteralPath (Join-Path $taskRoot 'qa\daily-publish-last.json') -Encoding utf8
$result
