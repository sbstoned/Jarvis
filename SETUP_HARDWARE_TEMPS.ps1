param(
    [string]$InstallDir = "$PSScriptRoot\tools\LibreHardwareMonitor"
)

$ErrorActionPreference = "Stop"
Write-Host "============================================================"
Write-Host "JARVIS - HARDWARE TEMPERATURE SENSOR SETUP"
Write-Host "============================================================"
Write-Host ""
Write-Host "This installs LibreHardwareMonitor from its official GitHub release."
Write-Host "Jarvis only needs it running to read CPU/RAM temperature sensors."
Write-Host ""

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$tempZip = Join-Path $env:TEMP "LibreHardwareMonitor-Jarvis.zip"

try {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest" `
        -Headers @{ "User-Agent" = "Jarvis-Temperature-Setup" }

    $asset = $release.assets |
        Where-Object { $_.name -like "*.zip" } |
        Select-Object -First 1

    if (-not $asset) {
        throw "No ZIP asset was found in the latest LibreHardwareMonitor release."
    }

    Write-Host "Downloading $($asset.name)..."
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tempZip

    Write-Host "Extracting..."
    Expand-Archive -Path $tempZip -DestinationPath $InstallDir -Force

    $exe = Get-ChildItem -Path $InstallDir -Filter "LibreHardwareMonitor.exe" -Recurse |
        Select-Object -First 1

    if (-not $exe) {
        throw "LibreHardwareMonitor.exe was not found after extraction."
    }

    Write-Host ""
    Write-Host "Starting LibreHardwareMonitor as Administrator..."
    Start-Process -FilePath $exe.FullName -Verb RunAs

    Write-Host ""
    Write-Host "Done. Leave LibreHardwareMonitor running."
    Write-Host "Jarvis should detect available hardware temperatures within about 10 seconds."
    Write-Host "RAM temperature only appears if your DIMMs/motherboard expose that sensor."
}
finally {
    Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
}

Read-Host "Press Enter to close"
