param(
    [string]$Destination = $env:JARVIS_QWEN_8B_MODEL_PATH
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = 'D:\Qwen3-8B-Abliterated\GGUF\Qwen3-8B-abliterated.i1-Q4_K_M.gguf'
}

$Url = 'https://huggingface.co/mradermacher/Qwen3-8B-abliterated-i1-GGUF/resolve/main/Qwen3-8B-abliterated.i1-Q4_K_M.gguf?download=true'
$Directory = Split-Path -Parent $Destination
$Partial = "$Destination.part"

New-Item -ItemType Directory -Force -Path $Directory | Out-Null

if (Test-Path -LiteralPath $Destination -PathType Leaf) {
    $sizeGB = [Math]::Round(((Get-Item -LiteralPath $Destination).Length / 1GB), 2)
    if ($sizeGB -ge 4.5) {
        Write-Host "Qwen3-8B Abliterated Q4_K_M is already installed:" -ForegroundColor Green
        Write-Host "  $Destination ($sizeGB GB)"
        exit 0
    }
    Write-Host "Existing model file looks incomplete ($sizeGB GB); downloading again." -ForegroundColor Yellow
    Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
}

$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) {
    Write-Error 'Windows curl.exe was not found. Install/update Windows curl and run this downloader again.'
    exit 1
}

Write-Host ''
Write-Host 'Downloading Qwen3-8B Abliterated Q4_K_M (~5.03 GB)...' -ForegroundColor Cyan
Write-Host 'Source: mradermacher/Qwen3-8B-abliterated-i1-GGUF (imatrix) on Hugging Face'
Write-Host "Destination: $Destination"
Write-Host 'The .part file is kept if interrupted so the next run can resume.'
Write-Host ''

& $curl.Source -L --fail --retry 5 --retry-delay 5 --connect-timeout 30 -C - --output $Partial $Url
if ($LASTEXITCODE -ne 0) {
    Write-Error "Download stopped with curl exit code $LASTEXITCODE. Run this script again to resume."
    exit $LASTEXITCODE
}

$downloadedGB = [Math]::Round(((Get-Item -LiteralPath $Partial).Length / 1GB), 2)
if ($downloadedGB -lt 4.5) {
    Write-Error "Downloaded file is unexpectedly small ($downloadedGB GB). Leaving $Partial for inspection/resume."
    exit 2
}

Move-Item -LiteralPath $Partial -Destination $Destination -Force
Write-Host ''
Write-Host "Installed Qwen3-8B Abliterated Q4_K_M: $Destination ($downloadedGB GB)" -ForegroundColor Green
Write-Host 'Restart Jarvis if it is currently open, then choose the 8B model directly under AUTO.'
