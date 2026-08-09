[CmdletBinding()]
param(
    [string]$TaskName = "dev-pace-daily-pcs-submit",
    [datetime]$At = (Get-Date -Hour 0 -Minute 5 -Second 0),
    [string]$PowerShell = (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe")
)

$ErrorActionPreference = "Stop"
$pipeline = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "run_daily_pipeline.ps1"
$action = New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$pipeline`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Aggregate dev-pace logs and submit privacy-reduced daily measurements to PCS." -Force | Out-Null
Write-Output "Registered $TaskName at $($At.ToString('HH:mm'))."
