param(
  [string]$Root
)

$ErrorActionPreference = "SilentlyContinue"
if(-not $Root){ $Root = $PSScriptRoot }

function VoiceProcs {
  @(
    Get-CimInstance Win32_Process | Where-Object {
      ($_.Name -in @('python.exe','pythonw.exe')) -and
      ($_.CommandLine -match [regex]::Escape($Root)) -and
      ($_.CommandLine -match 'jarvis\.py')
    }
  )
}
function DashProcs {
  @(
    Get-CimInstance Win32_Process | Where-Object {
      ($_.Name -in @('python.exe','pythonw.exe')) -and
      ($_.CommandLine -match [regex]::Escape($Root)) -and
      ($_.CommandLine -match 'ui[\\/]dashboard\.py')
    }
  )
}
function DashboardHealthy {
  try {
    $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8080/api/health" -TimeoutSec 5
    if($r.StatusCode -ne 200){ return $false }
    $d = $r.Content | ConvertFrom-Json
    return ($d.ok -eq $true -and [string]$d.build_id -eq "v2.60-project-attachments")
  } catch {
    return $false
  }
}

$voice = @(VoiceProcs)
$dash  = @(DashProcs)
$healthy = DashboardHealthy

# Fully healthy existing Jarvis: don't create duplicate processes.
if($voice.Count -eq 1 -and $dash.Count -ge 1 -and $healthy){
  Write-Output "HEALTHY"
  exit 0
}

# Partial/stale startup: clean only Jarvis processes from this exact project.
foreach($p in $voice){ try { & taskkill.exe /PID ([int]$p.ProcessId) /T /F *> $null } catch {} }
foreach($p in $dash){ try { & taskkill.exe /PID ([int]$p.ProcessId) /T /F *> $null } catch {} }

# Also free 8080 only if the listener belongs to a Python process whose
# command line points at this Jarvis root.
try {
  Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $pid = [int]$_.OwningProcess
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid"
    if($proc -and $proc.Name -in @('python.exe','pythonw.exe') -and
       $proc.CommandLine -match [regex]::Escape($Root)){
      & taskkill.exe /PID $pid /T /F *> $null
    }
  }
} catch {}

Write-Output "CLEAN"
exit 10
