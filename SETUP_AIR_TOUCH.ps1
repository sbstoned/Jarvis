$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$air = Join-Path $root "ui\airtouch"
$vendor = Join-Path $air "vendor"
$wasm = Join-Path $vendor "wasm"
$model = Join-Path $air "model"
New-Item -ItemType Directory -Force -Path $wasm,$model | Out-Null

function Get-AirTouchAsset {
    param(
        [string]$Destination,
        [string[]]$Urls,
        [long]$MinimumBytes = 100
    )

    if(Test-Path $Destination){
        try {
            if((Get-Item $Destination).Length -ge $MinimumBytes){
                Write-Host "Already installed: $([IO.Path]::GetFileName($Destination))" -ForegroundColor DarkGray
                return
            }
        } catch {}
        Remove-Item $Destination -Force -ErrorAction SilentlyContinue
    }

    $last = $null
    foreach($url in $Urls){
        try{
            Write-Host "Downloading $([IO.Path]::GetFileName($Destination)) from $url"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $Destination -TimeoutSec 90
            if((Get-Item $Destination).Length -lt $MinimumBytes){
                throw "Downloaded file is unexpectedly small."
            }
            return
        }catch{
            $last = $_
            Remove-Item $Destination -Force -ErrorAction SilentlyContinue
            Write-Host "  Source failed, trying fallback..." -ForegroundColor Yellow
        }
    }
    throw "Failed to download $Destination. Last error: $last"
}

Write-Host "Installing local MediaPipe Air Touch assets..." -ForegroundColor Cyan

Get-AirTouchAsset (Join-Path $vendor "vision_bundle.mjs") @(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs",
    "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs"
) 100000

Get-AirTouchAsset (Join-Path $wasm "vision_wasm_internal.js") @(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_internal.js",
    "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_internal.js"
) 100000

Get-AirTouchAsset (Join-Path $wasm "vision_wasm_internal.wasm") @(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_internal.wasm",
    "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_internal.wasm"
) 1000000

Get-AirTouchAsset (Join-Path $wasm "vision_wasm_nosimd_internal.js") @(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_nosimd_internal.js",
    "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_nosimd_internal.js"
) 100000

Get-AirTouchAsset (Join-Path $wasm "vision_wasm_nosimd_internal.wasm") @(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_nosimd_internal.wasm",
    "https://unpkg.com/@mediapipe/tasks-vision@0.10.35/wasm/vision_wasm_nosimd_internal.wasm"
) 1000000

Get-AirTouchAsset (Join-Path $model "hand_landmarker.task") @(
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
) 1000000

Write-Host ""
Write-Host "Air Touch assets installed and verified." -ForegroundColor Green
Write-Host "Webcam frames are processed locally by MediaPipe." -ForegroundColor Green
