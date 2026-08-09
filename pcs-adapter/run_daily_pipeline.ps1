[CmdletBinding()]
param(
    [string]$DevPaceRoot = "C:\Users\jingh\TLA\dev-pace",
    [string]$Timezone = "Asia/Tokyo",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$adapterRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$aggregateScript = Join-Path $DevPaceRoot "tools\aggregate_activity.py"
$dailyOutput = Join-Path $DevPaceRoot "outputs\activity_daily.jsonl"
$importOutput = Join-Path $adapterRoot "outputs\pcs_imports.jsonl"

if (-not (Test-Path -LiteralPath $aggregateScript)) { throw "aggregate script not found: $aggregateScript" }
if (-not $env:PCS_API_URL -or -not $env:PCS_CLIENT_ID -or -not $env:PCS_CLIENT_TOKEN) {
    throw "PCS_API_URL, PCS_CLIENT_ID, and PCS_CLIENT_TOKEN must be set for the scheduled task user"
}

& $Python $aggregateScript --input (Join-Path $DevPaceRoot "logs") --output $dailyOutput --timezone $Timezone
if ($LASTEXITCODE -ne 0) { throw "daily aggregation failed with exit code $LASTEXITCODE" }
& $Python (Join-Path $adapterRoot "adapter.py") --input $dailyOutput --output $importOutput --url $env:PCS_API_URL
if ($LASTEXITCODE -ne 0) { throw "PCS submission failed with exit code $LASTEXITCODE" }

Write-Output (ConvertTo-Json @{ status = "submitted"; dailyOutput = $dailyOutput; importOutput = $importOutput })
