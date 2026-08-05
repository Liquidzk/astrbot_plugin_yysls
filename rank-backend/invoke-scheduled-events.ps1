$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ToolRoot ".venv\Scripts\python.exe"
$Updater = Join-Path $ToolRoot "update_current_snapshot.py"
$Config = Join-Path $ToolRoot "ranks.json"
$UpdaterTask = "Yanyun Rank Updater"
$LogDir = Join-Path $ToolRoot "output\logs"
$LogFile = Join-Path $LogDir "scheduled-events.log"

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

$Task = Get-ScheduledTask -TaskName $UpdaterTask -ErrorAction Stop
$WasRunning = $Task.State -eq "Running"

if ($WasRunning) {
    Stop-ScheduledTask -TaskName $UpdaterTask
    Start-Sleep -Seconds 2
}

Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "python.exe" -and
        $_.CommandLine -like "*$Updater*" -and
        $_.CommandLine -like "*--interval 300*"
    } |
    ForEach-Object { Stop-ProcessTree -ProcessId $_.ProcessId }

try {
    & $Python $Updater `
        --config $Config `
        --apply-events-only *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        throw "Scheduled rank event command failed with exit code $LASTEXITCODE"
    }
}
finally {
    if ($WasRunning) {
        Start-ScheduledTask -TaskName $UpdaterTask
    }
}
