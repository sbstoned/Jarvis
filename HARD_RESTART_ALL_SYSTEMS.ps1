param([int]$OldJarvisPid=0,[string]$RequestId="")
$ErrorActionPreference="SilentlyContinue"
$root=$PSScriptRoot
$dashboardUrl="http://127.0.0.1:8080"
$hermesUrl="http://127.0.0.1:8642/v1/models"
$logDir=Join-Path $root "logs"
$logFile=Join-Path $logDir "hard_restart.log"
$statusFile=Join-Path $root "restart_status.json"
$flag=Join-Path $root "restart_in_progress.flag"
$profilePath=Join-Path $env:TEMP "JarvisCommandCenterChrome"
New-Item -ItemType Directory -Force -Path $logDir|Out-Null

function Log([string]$m){Add-Content $logFile "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss.fff') [$RequestId] $m" -Encoding UTF8}
function WriteStatus([string]$stage,[string]$message,[bool]$success=$false){
  $o=[ordered]@{request_id=$RequestId;stage=$stage;message=$message;success=$success;supervisor_pid=$PID;old_jarvis_pid=$OldJarvisPid;updated_at=(Get-Date -Format o)}
  try{$tmp="$statusFile.$PID.tmp";$o|ConvertTo-Json|Set-Content $tmp -Encoding UTF8;Move-Item $tmp $statusFile -Force}catch{}
  Log "$stage - $message"
}
function StopOnly([int]$id){if($id -gt 0 -and $id -ne $PID){try{Stop-Process -Id $id -Force}catch{}}}
function KillTree([int]$id){if($id -gt 0 -and $id -ne $PID){try{& taskkill.exe /PID $id /T /F *> $null}catch{}}}
function VoiceProcs{@(Get-CimInstance Win32_Process|Where-Object{($_.Name -in @('python.exe','pythonw.exe')) -and $_.CommandLine -and $_.CommandLine -match [regex]::Escape($root) -and $_.CommandLine -match 'jarvis\.py'})}
function DashProcs{@(Get-CimInstance Win32_Process|Where-Object{($_.Name -in @('python.exe','pythonw.exe')) -and $_.CommandLine -and $_.CommandLine -match [regex]::Escape($root) -and $_.CommandLine -match 'ui[\\/]dashboard\.py'})}
function WrapperProcs{@(Get-CimInstance Win32_Process|Where-Object{$_.Name -eq 'cmd.exe' -and $_.CommandLine -and $_.CommandLine -match [regex]::Escape($root) -and $_.CommandLine -match 'START_VOICE_ENGINE|START_COMMAND_CENTER|dashboard\.py|JARVIS Command Center Launcher'})}
function HardwareProcs{@(Get-Process JarvisHardwareSensors -ErrorAction SilentlyContinue)}
function DashListeners{@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)}
function HermesListeners{@(Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue)}
function HermesProcs{$owners=@(HermesListeners|ForEach-Object{[int]$_.OwningProcess});@(Get-CimInstance Win32_Process|Where-Object{([int]$_.ProcessId -in $owners) -or ($_.CommandLine -and $_.CommandLine -match 'hermes' -and $_.CommandLine -match 'gateway')})}
function HttpUp([string]$u){try{$r=Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 1;return($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)}catch{return $false}}
function DashboardHttpUp{
  try{
    $r=Invoke-WebRequest -UseBasicParsing "$dashboardUrl/api/health" -TimeoutSec 5
    if($r.StatusCode -ne 200){return $false}
    $d=$r.Content|ConvertFrom-Json
    return($d.ok -eq $true -and [string]$d.build_id -eq "v2.60-project-attachments")
  }catch{return $false}
}
function HermesHttpUp{return(HttpUp $hermesUrl)}
function VoiceHealthy([datetime]$notBefore){
  $f=Join-Path $root "voice_health.json"
  try{if(-not(Test-Path $f)){return $false};$d=Get-Content $f -Raw|ConvertFrom-Json;$updated=[datetime]$d.updated_at;$p=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$d.pid)";return($p -and $p.CommandLine -match [regex]::Escape($root) -and $updated -ge $notBefore -and ((Get-Date)-$updated).TotalSeconds -lt 30)}catch{return $false}
}
function CloseJarvisUi{
  WriteStatus "shutdown-ui" "Closing Jarvis Command Center UI."
  Get-CimInstance Win32_Process|Where-Object{($_.Name -in @('chrome.exe','msedge.exe')) -and $_.CommandLine -and ($_.CommandLine -match 'JarvisCommandCenterChrome' -or $_.CommandLine -match '--app=http://127\.0\.0\.1:8080')}|ForEach-Object{KillTree([int]$_.ProcessId)}
  Get-Process chrome,msedge -ErrorAction SilentlyContinue|Where-Object{$_.MainWindowTitle -match 'JARVIS Command Center|Jarvis Command Center|J\.A\.R\.V\.I\.S'}|ForEach-Object{try{$_.CloseMainWindow()|Out-Null}catch{}}
}
function StopOldStack{
  DashListeners|ForEach-Object{KillTree([int]$_.OwningProcess)}
  DashProcs|ForEach-Object{KillTree([int]$_.ProcessId)}
  HardwareProcs|ForEach-Object{KillTree([int]$_.Id)}
  VoiceProcs|ForEach-Object{StopOnly([int]$_.ProcessId)}
  WrapperProcs|ForEach-Object{StopOnly([int]$_.ProcessId)}
  if($OldJarvisPid -gt 0){StopOnly $OldJarvisPid}
}
function Snapshot{[ordered]@{dashListeners=@(DashListeners).Count;dashProcesses=@(DashProcs).Count;voice=@(VoiceProcs).Count;hardware=@(HardwareProcs).Count;wrappers=@(WrapperProcs).Count;dashHttp=[bool](DashboardHttpUp);hermesListeners=@(HermesListeners).Count;hermesProcesses=@(HermesProcs).Count;hermesHttp=[bool](HermesHttpUp)}}
function FullyDown($s){return($s.dashListeners -eq 0 -and $s.dashProcesses -eq 0 -and $s.voice -eq 0 -and $s.hardware -eq 0 -and $s.wrappers -eq 0 -and -not $s.dashHttp -and $s.hermesListeners -eq 0 -and $s.hermesProcesses -eq 0 -and -not $s.hermesHttp)}
function OpenCommandCenter{
  $c=@((Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),(Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),(Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),(Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"))
  $b=$c|Where-Object{$_ -and(Test-Path $_)}|Select-Object -First 1
  if($b){Start-Process -FilePath $b -ArgumentList @("--user-data-dir=$profilePath","--app=$dashboardUrl","--start-maximized")}else{Start-Process $dashboardUrl}
}

$mutex=New-Object System.Threading.Mutex($false,"Local\JarvisFullRestart_v245")
$have=$false
try{$have=$mutex.WaitOne(0,$false)}catch{}
if(-not $have){WriteStatus "failure" "Another restart supervisor is already running.";exit 10}
Set-Content $flag "$(Get-Date -Format o) request=$RequestId supervisor=$PID" -Encoding ASCII

try{
  WriteStatus "supervisor-ready" "External supervisor is alive."
  Start-Sleep -Seconds 3
  CloseJarvisUi
  WriteStatus "shutdown-services" "Stopping dashboard, voice, hardware and wrappers."
  StopOldStack
  WriteStatus "shutdown-hermes" "Stopping Hermes gateway."
  try{hermes gateway stop|Out-Null}catch{}
  HermesProcs|ForEach-Object{KillTree([int]$_.ProcessId)}

  WriteStatus "verify-down" "Waiting for old URL and services to go offline."
  $deadline=(Get-Date).AddSeconds(35)
  do{$down=Snapshot;Log("down="+($down|ConvertTo-Json -Compress));if(FullyDown $down){break};Start-Sleep -Milliseconds 500}while((Get-Date)-lt $deadline)
  $down=Snapshot
  if(-not(FullyDown $down)){WriteStatus "force-clean" "Retrying cleanup.";StopOldStack;HermesProcs|ForEach-Object{KillTree([int]$_.ProcessId)};Start-Sleep -Seconds 2;$down=Snapshot}
  if(-not(FullyDown $down)){WriteStatus "failure" ("Old stack still alive: "+($down|ConvertTo-Json -Compress));exit 30}

  WriteStatus "offline-confirmed" "Old Jarvis URL and stack are fully OFFLINE."
  Start-Sleep -Seconds 1
  $launcher=Join-Path $root "START_COMMAND_CENTER.bat"
  if(-not(Test-Path $launcher)){WriteStatus "failure" "START_COMMAND_CENTER.bat is missing.";exit 31}

  $started=Get-Date
  WriteStatus "launching" "Launching fresh Jarvis stack."
  try{$fresh=Start-Process -FilePath "cmd.exe" -ArgumentList @("/d","/s","/c","`"$launcher`" --supervised-restart") -WorkingDirectory $root -PassThru;Log "fresh launcher pid=$($fresh.Id)"}catch{WriteStatus "failure" ("Fresh launcher failed: "+$_.Exception.Message);exit 32}

  WriteStatus "verify-up" "Waiting for fresh dashboard and voice."
  $deadline=(Get-Date).AddSeconds(120);$ready=$false
  do{$d=[bool](DashboardHttpUp);$v=[bool](VoiceHealthy $started);Log "up dashboard=$d voice=$v";if($d -and $v){$ready=$true;break};Start-Sleep -Milliseconds 600}while((Get-Date)-lt $deadline)
  if(-not $ready){WriteStatus "failure" "Fresh stack did not become healthy before timeout.";exit 33}

  WriteStatus "reopening-ui" "Fresh stack healthy; reopening Command Center."
  OpenCommandCenter
  Start-Sleep -Seconds 2
  WriteStatus "complete" "FULL RESTART SUCCESS: dashboard, voice and UI are back." $true
  exit 0
}finally{
  Remove-Item $flag -Force -ErrorAction SilentlyContinue
  if($have){try{$mutex.ReleaseMutex()|Out-Null}catch{}}
  try{$mutex.Dispose()}catch{}
  Log "supervisor exit"
}
