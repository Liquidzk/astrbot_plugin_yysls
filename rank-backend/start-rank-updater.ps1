$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ToolRoot ".venv\Scripts\python.exe"
$Updater = Join-Path $ToolRoot "update_current_snapshot.py"
$Config = Join-Path $ToolRoot "ranks.json"
$Output = Join-Path (Split-Path -Parent $ToolRoot) "data\current-ranks.json"
$LogDir = Join-Path $ToolRoot "output\logs"
$LogFile = Join-Path $LogDir "rank-updater.log"
$ErrorLogFile = Join-Path $LogDir "rank-updater.err.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Rank updater virtual environment not found: $Python"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ToolRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

function Stop-ProcessTree {
    param([int]$ProcessId)

    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" |
        ForEach-Object { Stop-ProcessTree -ProcessId $_.ProcessId }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

# Scheduled Task stop can leave the Python child behind. Keep one updater only.
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.CommandLine -like "*$Updater*" -and
        $_.CommandLine -like "*--interval 300*"
    } |
    ForEach-Object { Stop-ProcessTree -ProcessId $_.ProcessId }

$Process = Start-Process -FilePath $Python `
    -ArgumentList @(
        $Updater,
        "--config",
        $Config,
        "--output",
        $Output,
        "--interval",
        "300"
    ) `
    -WorkingDirectory $ToolRoot `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError $ErrorLogFile

$Process.WaitForExit()
exit $Process.ExitCode
