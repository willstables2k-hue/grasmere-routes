# Wrapper for the Windows Scheduled Task — runs scripts/fresho_pull.py with
# logging. Picks up FRESHO_EMAIL / FRESHO_PASSWORD / BRAIN_DB_URL from the
# user environment (same vars the KPI dashboard pipeline already uses).
#
# Manual run:
#   powershell -ExecutionPolicy Bypass -File C:\Users\William\grasmere-routes\scripts\fresho_pull_scheduled.ps1

$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repo 'scripts\logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$ts  = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$log = Join-Path $logDir "fresho_pull_$ts.log"

# Keep only the last 30 logs so the directory doesn't grow forever
Get-ChildItem $logDir -Filter 'fresho_pull_*.log' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 |
    Remove-Item -Force -ErrorAction SilentlyContinue

Set-Location $repo

# Sanity-check required env vars; fail fast with a useful log line
$missing = @()
foreach ($v in 'FRESHO_EMAIL','FRESHO_PASSWORD','BRAIN_DB_URL') {
    if (-not [Environment]::GetEnvironmentVariable($v, 'User') -and
        -not [Environment]::GetEnvironmentVariable($v, 'Machine') -and
        -not [Environment]::GetEnvironmentVariable($v, 'Process')) {
        $missing += $v
    }
}
if ($missing.Count -gt 0) {
    "[$(Get-Date -f s)] missing env vars: $($missing -join ', ')" | Tee-Object -FilePath $log -Append
    exit 2
}

"[$(Get-Date -f s)] starting fresho_pull (today's deliveries)" | Tee-Object -FilePath $log -Append
& python (Join-Path $repo 'scripts\fresho_pull.py') *>&1 | Tee-Object -FilePath $log -Append
$rc = $LASTEXITCODE
"[$(Get-Date -f s)] finished with exit code $rc" | Tee-Object -FilePath $log -Append
exit $rc
