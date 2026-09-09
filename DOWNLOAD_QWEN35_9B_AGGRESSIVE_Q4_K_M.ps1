param(
    [string]$Destination = $env:JARVIS_QWEN_35_9B_MODEL_PATH
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = 'D:\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive\GGUF\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf'
}

$Url = 'https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive/resolve/main/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf?download=true'
$Directory = Split-Path -Parent $Destination
$Partial = "$Destination.part"

New-Item -ItemType Directory -Force -Path $Directory | Out-Null

if (Test-Path -LiteralPath $Destination -PathType Leaf) {
    $sizeGB = [Math]::Round(((Get-Item -LiteralPath $Destination).Length / 1GB), 2)
    if ($sizeGB -ge 5.0) {
        Write-Host 'Qwen3.5-9B HauhauCS Aggressive Q4_K_M is already installed:' -ForegroundColor Green
        Write-Host "  $Destination ($sizeGB GB)"
        exit 0
    }
    Write-Host "Existing model file looks incomplete ($sizeGB GB); downloading again." -ForegroundColor Yellow
    Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
}

$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) {
    Write-Error 'Windows curl.exe was not found.'
    exit 1
}

Write-Host ''
Write-Host 'Downloading Qwen3.5-9B Uncensored HauhauCS Aggressive Q4_K_M (~5.3 GB)...' -ForegroundColor Cyan
Write-Host 'Source: HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive on Hugging Face'
Write-Host "Destination: $Destination"
Write-Host 'Interrupted downloads are kept as .part and resumed on the next run.'
Write-Host ''

& $curl.Source -L --fail --retry 5 --retry-delay 5 --connect-timeout 30 -C - --output $Partial $Url
if ($LASTEXITCODE -ne 0) {
    Write-Error "Download stopped with curl exit code $LASTEXITCODE. Run this script again to resume."
    exit $LASTEXITCODE
}

$downloadedGB = [Math]::Round(((Get-Item -LiteralPath $Partial).Length / 1GB), 2)
if ($downloadedGB -lt 5.0) {
    Write-Error "Downloaded file is unexpectedly small ($downloadedGB GB). Leaving $Partial for inspection/resume."
    exit 2
}

Move-Item -LiteralPath $Partial -Destination $Destination -Force
Write-Host ''
Write-Host "Installed Qwen3.5-9B HauhauCS Aggressive Q4_K_M: $Destination ($downloadedGB GB)" -ForegroundColor Green
Write-Host ''
Write-Host 'Next: restart Jarvis and choose QWEN3.5 9B from the model dropdown.'
Write-Host 'Jarvis V31 will try ~1,010,000 YaRN context first and automatically fall back through 524K/262K/131K/65K/40K as needed.'
