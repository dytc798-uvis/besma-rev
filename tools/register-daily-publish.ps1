$ErrorActionPreference='Stop'
$taskRoot='D:\JSI\workfiles\besma-renewal-20261026'
$name='JSI BESMA Attendance Publish - 30min'
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'Existing task requires review before replacement'}
$powershell=(Get-Command pwsh.exe).Source
$script=Join-Path $taskRoot 'release\tools\publish-daily-attendance.ps1'
$action=New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -File "'+$script+'"') -WorkingDirectory $taskRoot
$trigger=New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddHours(8).AddMinutes(15)) -RepetitionInterval (New-TimeSpan -Minutes 30)
$evening=New-ScheduledTaskTrigger -Daily -At '18:45'
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName $name -Action $action -Trigger @($trigger,$evening) -Principal $principal -Settings $settings | Out-Null
$task=Get-ScheduledTask -TaskName $name
if($task.Principal.RunLevel -ne 'Limited' -or $task.Principal.LogonType -ne 'Interactive'){throw 'Task context mismatch'}
$task | Select-Object TaskName,State,@{N='RunLevel';E={$_.Principal.RunLevel}},@{N='LogonType';E={$_.Principal.LogonType}},@{N='Execution';E={$_.Actions.Execute}},@{N='Arguments';E={$_.Actions.Arguments}} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'qa\daily-publish-task.json') -Encoding utf8
