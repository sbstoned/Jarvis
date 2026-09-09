param(
    [switch]$InstallCommon,
    [switch]$InstallExtended,
    [switch]$InstallCppBuildTools
)

$ErrorActionPreference = 'Continue'
Write-Host "Jarvis V42 Developer Tool Setup" -ForegroundColor Cyan
Write-Host "This script audits by default. Nothing is installed unless you pass -InstallCommon, -InstallExtended, or -InstallCppBuildTools."

$tools = @('git','python','pip','uv','poetry','node','npm','pnpm','yarn','bun','deno','cargo','rustc','cmake','ctest','ninja','dotnet','java','javac','gradle','mvn','go','flutter','dart','adb','docker','podman','wsl','pwsh','bash','kubectl','helm','sqlite3','php','ruby','composer','zig','nim','clojure','crystal','racket','gfortran','nvcc','wasm-pack','rg','fd','jq','7z')
foreach ($tool in $tools) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) { Write-Host "[OK] $tool -> $($cmd.Source)" -ForegroundColor Green }
    else { Write-Host "[--] $tool not found" -ForegroundColor DarkYellow }
}

if ($InstallCommon) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "winget is required for -InstallCommon. Install/repair App Installer first." -ForegroundColor Red
    } else {
        $packages = @(
            'Git.Git',
            'Python.Python.3.13',
            'OpenJS.NodeJS.LTS',
            'Rustlang.Rustup',
            'Kitware.CMake',
            'Ninja-build.Ninja',
            'GoLang.Go',
            'BurntSushi.ripgrep.MSVC',
            'jqlang.jq',
            '7zip.7zip'
        )
        foreach ($id in $packages) {
            Write-Host "Installing/updating $id..." -ForegroundColor Cyan
            winget install --id $id --exact --silent --accept-source-agreements --accept-package-agreements
        }
    }
}

if ($InstallExtended) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "winget is required for -InstallExtended." -ForegroundColor Red
    } else {
        # Optional developer utilities. Individual package failures are non-fatal; the
        # capability scanner will re-audit exactly what became available.
        $packages = @(
            'Microsoft.PowerShell',
            'DenoLand.Deno',
            'astral-sh.uv',
            'Kubernetes.kubectl',
            'Helm.Helm'
        )
        foreach ($id in $packages) {
            Write-Host "Installing/updating optional $id..." -ForegroundColor Cyan
            winget install --id $id --exact --silent --accept-source-agreements --accept-package-agreements
        }
    }
}

if ($InstallCppBuildTools) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "winget is required for C++ Build Tools installation." -ForegroundColor Red
    } else {
        Write-Host "Installing Visual Studio 2022 Build Tools C++ workload. This is a large install." -ForegroundColor Yellow
        winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --accept-source-agreements --accept-package-agreements --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
    }
}

Write-Host "Done. Open a new PowerShell/Jarvis process after installations so PATH changes are visible." -ForegroundColor Cyan
