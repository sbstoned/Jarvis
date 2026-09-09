$ErrorActionPreference = "Stop"
$jarvisDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $jarvisDir "START_COMMAND_CENTER.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "JARVIS Command Center.lnk"

$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $jarvisDir
$shortcut.Description = "Launch JARVIS voice engine and Command Center"
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Host ""
Write-Host "Created desktop shortcut:" -ForegroundColor Cyan
Write-Host $shortcutPath -ForegroundColor Green
Write-Host ""
Write-Host "You can now start JARVIS with one double-click." -ForegroundColor Cyan
