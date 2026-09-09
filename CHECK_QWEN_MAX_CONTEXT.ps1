param([int]$Port = 8081)
$ErrorActionPreference = 'SilentlyContinue'

Write-Host ''
Write-Host 'Context environment diagnostics:'
Write-Host "  JARVIS_QWEN_35_CONTEXT      = $env:JARVIS_QWEN_35_CONTEXT"
Write-Host "  JARVIS_QWEN_35_9B_CONTEXT   = $env:JARVIS_QWEN_35_9B_CONTEXT"
Write-Host "  JARVIS_QWEN_CONTEXT         = $env:JARVIS_QWEN_CONTEXT (legacy; ignored by Qwen3.5 V32)"
Write-Host "  JARVIS_QWEN_CONTEXT_TOKENS  = $env:JARVIS_QWEN_CONTEXT_TOKENS (legacy fallback; not a Qwen3.5 launch target)"
$BaseUrl = "http://127.0.0.1:$Port"
$JarvisDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeProfilePath = Join-Path $JarvisDir 'qwen_runtime_profile.json'
Write-Host "Checking Jarvis Qwen runtime at $BaseUrl ..."
try {
    $health = Invoke-WebRequest -UseBasicParsing "$BaseUrl/health" -TimeoutSec 3
    if ($health.StatusCode -ne 200) { throw "health status $($health.StatusCode)" }
} catch {
    Write-Host "FAIL: Qwen is not healthy on port $Port." -ForegroundColor Red
    exit 1
}

$ctx = 0
try {
    $data = (Invoke-WebRequest -UseBasicParsing "$BaseUrl/props" -TimeoutSec 3).Content | ConvertFrom-Json
    $vals = New-Object System.Collections.Generic.List[int]
    function Scan($obj) {
        if ($null -eq $obj) { return }
        if ($obj -is [pscustomobject]) {
            foreach ($prop in $obj.PSObject.Properties) {
                if ($prop.Name -in @('n_ctx','ctx_size','context_size','context_length','n_ctx_slot')) {
                    try { $n=[int]$prop.Value; if($n -ge 4096){$vals.Add($n)} } catch {}
                }
                Scan $prop.Value
            }
        } elseif ($obj -is [System.Collections.IDictionary]) {
            foreach($key in $obj.Keys){ Scan $obj[$key] }
        } elseif ($obj -is [System.Collections.IEnumerable] -and -not ($obj -is [string])) {
            foreach($item in $obj){ Scan $item }
        }
    }
    Scan $data
    if($vals.Count -gt 0){$ctx=($vals|Measure-Object -Minimum).Minimum}
} catch {}

$proc = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | Where-Object {
    $_.CommandLine -and ($_.CommandLine -match "(--port|-p)\s+$Port(\s|$)")
} | Select-Object -First 1
$cmd = if($proc){[string]$proc.CommandLine}else{''}
$slotOk = $cmd -match '(?:-np|--parallel)\s+1(?:\s|$)'
$shiftOk = $cmd -match '--no-context-shift(?:\s|$)'
$gpuOk = $cmd -match '(?:-ngl|--gpu-layers|--n-gpu-layers)\s+all(?:\s|$)'
$splitOk = $cmd -match '(?:-sm|--split-mode)\s+none(?:\s|$)'
$yarnCmd = $cmd -match '--rope-scaling\s+yarn(?:\s|$)'
$yarnScaleCmd = 0.0
if($cmd -match '--rope-scale\s+([0-9.]+)'){try{$yarnScaleCmd=[double]$Matches[1]}catch{}}

$rp = $null
try { if(Test-Path $RuntimeProfilePath){$rp=Get-Content $RuntimeProfilePath -Raw|ConvertFrom-Json} } catch {}
$model = if($rp){[string]$rp.model}else{''}
$family = if($rp){[string]$rp.model_family}else{''}
$is35 = ($family -match 'qwen3\.5' -or $model -match '(?i)Qwen3[._-]?5.*9B')
$is8 = (-not $is35 -and $model -match '(?i)Qwen3-8B')
$yarnProfile = if($rp){[bool]$rp.yarn_enabled}else{$false}
$yarnScaleProfile = if($rp -and $null -ne $rp.yarn_scale){[double]$rp.yarn_scale}else{0.0}
$kv = if($rp){[string]$rp.kv_cache}else{''}
$kvLoc = if($rp){[string]$rp.kv_location}else{''}
$promptCache = if($rp -and $null -ne $rp.prompt_cache){[bool]$rp.prompt_cache}else{$false}

Write-Host "Model       : $model"
Write-Host "Context     : $ctx"
Write-Host "One slot    : $slotOk"
Write-Host "Ctx shift   : $(if($shiftOk){'OFF'}else{'NOT CONFIRMED'})"
Write-Host "GPU layers  : $(if($gpuOk){'ALL'}else{'NOT CONFIRMED / PARTIAL'})"
Write-Host "Split mode  : $(if($splitOk){'NONE / single GPU'}else{'NOT CONFIRMED'})"
if($is35){
    Write-Host "KV cache    : $kv"
    Write-Host "KV location : $kvLoc"
    Write-Host "Prompt cache: $promptCache"
    Write-Host "YaRN        : $(if($yarnCmd -or $yarnProfile){'ON'}else{'OFF'})"
    Write-Host "YaRN scale  : $(if($yarnScaleCmd -gt 0){$yarnScaleCmd}else{$yarnScaleProfile})"
}
if($rp -and $rp.context_fallback_used){Write-Host "Fallback    : YES (requested $($rp.requested_context), running $($rp.context))" -ForegroundColor Yellow}
if($proc){Write-Host "PID         : $($proc.ProcessId)"}

if($is35){
    if($ctx -ge 40960 -and $slotOk -and $shiftOk -and $splitOk){
        if($ctx -ge 900000 -and ($yarnCmd -or $yarnProfile)){
            Write-Host "PASS: Qwen3.5-9B is running an opt-in extended ~1M YaRN profile." -ForegroundColor Green
        } elseif($ctx -gt 262144 -and ($yarnCmd -or $yarnProfile)){
            Write-Host "PASS: Qwen3.5-9B is running an extended YaRN fallback context ($ctx)." -ForegroundColor Green
        } elseif($ctx -eq 262144){
            if($kvLoc -match '(?i)CPU|no-kv-offload' -or -not $promptCache){
                Write-Host "FAIL: Native 262K is live, but the V32 throughput profile is not active (KV must be offloaded and prompt cache enabled)." -ForegroundColor Yellow
                exit 2
            }
            Write-Host "PASS: Qwen3.5-9B is running native 262,144 with V32 GPU-KV/prompt-cache throughput policy." -ForegroundColor Green
        } elseif($ctx -ge 131072){
            Write-Host "PASS: Qwen3.5-9B is running a 128K+ memory-safe fallback context ($ctx)." -ForegroundColor Green
        } else {
            Write-Host "PASS: Qwen3.5-9B is running the final memory-safe fallback context ($ctx)." -ForegroundColor Yellow
        }
        exit 0
    }
    Write-Host "FAIL: Qwen3.5-9B is healthy but its managed V32 runtime profile is incomplete." -ForegroundColor Yellow
    exit 2
}
if($is8){
    if($ctx -eq 40960 -and $slotOk -and $shiftOk -and $gpuOk -and $splitOk){
        Write-Host "PASS: Jarvis Qwen3-8B is running the full 40,960-token profile." -ForegroundColor Green
        exit 0
    }
    Write-Host "FAIL: Qwen3-8B is healthy but does not match the full max-context profile." -ForegroundColor Yellow
    exit 2
}

Write-Host "INFO: Active Qwen is healthy. This verifier has strict profiles for the 8B and Qwen3.5-9B selections." -ForegroundColor Cyan
exit 0
