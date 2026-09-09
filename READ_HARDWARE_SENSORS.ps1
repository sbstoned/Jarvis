param([string]$BaseDir="$PSScriptRoot\tools\LibreHardwareMonitor")
$ErrorActionPreference="Stop"
try{
  $BaseDir=[IO.Path]::GetFullPath($BaseDir)
  $dll=Join-Path $BaseDir "LibreHardwareMonitorLib.dll"
  if(-not(Test-Path $dll)){throw "LibreHardwareMonitorLib.dll not found at $dll"}
  Push-Location $BaseDir
  try{
    Add-Type -Path $dll
    $computer=[LibreHardwareMonitor.Hardware.Computer]::new()
    $computer.IsCpuEnabled=$true
    $computer.IsMemoryEnabled=$true
    $computer.IsMotherboardEnabled=$true
    $computer.IsControllerEnabled=$true
    $computer.IsGpuEnabled=$true
    $computer.IsStorageEnabled=$true
    $computer.Open()
    function Read-Node($h){
      try{$h.Update()}catch{}
      $items=@()
      foreach($s in $h.Sensors){
        if($s.SensorType.ToString() -eq "Temperature" -and $null -ne $s.Value){
          $items += [pscustomobject]@{
            HardwareName=[string]$h.Name
            HardwareType=[string]$h.HardwareType
            HardwareId=[string]$h.Identifier
            SensorName=[string]$s.Name
            SensorId=[string]$s.Identifier
            Value=[double]$s.Value
          }
        }
      }
      foreach($sub in $h.SubHardware){$items += Read-Node $sub}
      return $items
    }
    $all=@()
    foreach($h in $computer.Hardware){$all += Read-Node $h}
    $computer.Close()
    [pscustomobject]@{ok=$true;source="LibreHardwareMonitor direct DLL";sensors=@($all)}|ConvertTo-Json -Depth 6 -Compress
  }finally{Pop-Location}
}catch{
  [pscustomobject]@{ok=$false;source="LibreHardwareMonitor direct DLL";error=$_.Exception.Message;sensors=@()}|ConvertTo-Json -Depth 6 -Compress
  exit 0
}
