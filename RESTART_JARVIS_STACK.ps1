param(
    [int]$JarvisPid = 0,
    [int]$DelaySeconds = 3
)

$ErrorActionPreference = "SilentlyContinue"
$root = $PSScriptRoot
$dashboardUrl = "http://127.0.0.1:8080"
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir "restart_supervisor.log"
$profileMarker = "JarvisCommandCenterChrome"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-RestartLog([string]$Message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff')  $Message"
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Stop-ProcessTreeSafe([int]$TargetPid) {
    if ($TargetPid -le 0 -or $TargetPid -eq $PID) { return }
    try {
        & taskkill.exe /PID $TargetPid /T /F *> $null
    } catch {
        try { Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue } catch {}
    }
}

function Stop-ProcessOnlySafe([int]$TargetPid) {
    # Important: the restart supervisor may be a child of jarvis.py.
    # Killing the Jarvis process TREE could also kill this supervisor.
    if ($TargetPid -le 0 -or $TargetPid -eq $PID) { return }
    try {
        Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue
    } catch {}
}

function Close-JarvisBrowserWindow {
    Write-RestartLog "Closing Jarvis Command Center browser window."

    # First close any visible JARVIS app-mode window gracefully.
    try {
        Get-Process chrome,msedge -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -match 'JARVIS|Jarvis Command Center|J\.A\.R\.V\.I\.S' } |
            ForEach-Object {
                try { $_.CloseMainWindow() | Out-Null } catch {}
            }
    } catch {}

    Start-Sleep -Milliseconds 400

    # New v2.19.3 launches the Command Center in its own browser profile.
    # That lets us kill Jarvis's UI without closing the user's normal tabs.
    try {
        $browserProcesses = Get-CimInstance Win32_Process | Where-Object {
            ($_.Name -in @('chrome.exe','msedge.exe')) -and (
                $_.CommandLine -match $profileMarker -or
                $_.CommandLine -match '--app=http://127\.0\.0\.1:8080' -or
                $_.CommandLine -match '--kiosk.*127\.0\.0\.1:8080'
            )
        }
        foreach ($proc in $browserProcesses) {
            Stop-ProcessTreeSafe ([int]$proc.ProcessId)
        }
    } catch {}
}

function Stop-DashboardListener {
    Write-RestartLog "Stopping dashboard listener on port 8080."
    try {
        $listeners = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
        foreach ($listener in $listeners) {
            Stop-ProcessTreeSafe ([int]$listener.OwningProcess)
        }
    } catch {}
}

function Stop-JarvisPythonProcesses {
    Write-RestartLog "Stopping Jarvis Python processes."
    try {
        $escapedRoot = [regex]::Escape($root)
        $pythonProcesses = Get-CimInstance Win32_Process | Where-Object {
            ($_.Name -in @('python.exe','pythonw.exe')) -and
            ($_.CommandLine -match $escapedRoot) -and (
                $_.CommandLine -match 'jarvis\.py' -or
                $_.CommandLine -match 'ui[\\/]dashboard\.py'
            )
        }

        foreach ($proc in $pythonProcesses) {
            $pidToStop = [int]$proc.ProcessId
            if ($pidToStop -ne $PID -and $pidToStop -ne $JarvisPid) {
                Stop-ProcessTreeSafe $pidToStop
            }
        }
    } catch {}
}

function Stop-HardwareHelpers {
    Write-RestartLog "Stopping hardware sensor helper."
    try {
        Get-Process JarvisHardwareSensors -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-ProcessTreeSafe ([int]$_.Id)
        }
    } catch {}
}

function Wait-PortClosed([int]$Port, [int]$TimeoutSeconds = 12) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Wait-DashboardReady([int]$TimeoutSeconds = 35) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri "$dashboardUrl/api/health" -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 400
    }
    return $false
}

Write-RestartLog "===== RESTART REQUESTED. Supervisor PID=$PID JarvisPid=$JarvisPid ====="

# Give Jarvis time to speak its short confirmation before the audio process dies.
Start-Sleep -Seconds ([Math]::Max(1, $DelaySeconds))

Close-JarvisBrowserWindow
Stop-DashboardListener
Stop-HardwareHelpers
Stop-JarvisPythonProcesses

# Kill ONLY the original Jarvis process, not its child tree. This is the key
# fix that allows this external supervisor to survive and finish the restart.
if ($JarvisPid -gt 0) {
    Write-RestartLog "Stopping original Jarvis PID $JarvisPid without /T."
    Stop-ProcessOnlySafe $JarvisPid
}

Write-RestartLog "Stopping Hermes gateway."
try { hermes gateway stop | Out-Null } catch {}

$portClosed = Wait-PortClosed -Port 8080 -TimeoutSeconds 12
Write-RestartLog "Dashboard port closed=$portClosed"

Start-Sleep -Seconds 2

$launcher = Join-Path $root "START_COMMAND_CENTER.bat"
if (-not (Test-Path $launcher)) {
    Write-RestartLog "ERROR: START_COMMAND_CENTER.bat is missing."
    exit 20
}

Write-RestartLog "Launching fresh Jarvis stack."
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "`"$launcher`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden

if (Wait-DashboardReady -TimeoutSeconds 40) {
    Write-RestartLog "SUCCESS: Fresh dashboard responded at $dashboardUrl."
    exit 0
}

Write-RestartLog "ERROR: Fresh dashboard did not become ready within timeout."
exit 21
