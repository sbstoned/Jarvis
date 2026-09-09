param([switch]$NoPrompt)
$root=$PSScriptRoot
$exe=Join-Path $root 'tools\JarvisHardwareSensors\JarvisHardwareSensors.exe'
$cache=Join-Path $root 'hardware_sensor_snapshot.json'
if(-not(Test-Path $exe)){
  & (Join-Path $root 'BUILD_HARDWARE_HELPER.bat')
}
if(-not(Test-Path $exe)){Write-Host 'Hardware helper is unavailable.'; exit 1}
$args='--watch `"'+$cache+'`"'
Start-Process -FilePath $exe -ArgumentList $args -Verb RunAs -WindowStyle Hidden
Write-Host 'Elevated Jarvis hardware sensor bridge started.'
