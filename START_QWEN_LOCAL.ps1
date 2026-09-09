param(
    [string]$ServerExe = "",
    [string]$ModelPath = "",
    [int]$Port = 0,
    [string]$Profile = "",
    [int]$ContextTokens = 0,
    [int]$MaxOutputTokens = 0,
    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
$jarvisDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# V42.63: one readiness controller for both one-click startup and live routing.
# The controller waits for the native llama-server PID, /health and /props.
# All original parameters remain optional. With no arguments it resolves the
# saved dropdown, model paths and environment overrides in qwen_model_manager.py.
# It exits successfully only after the model is verified; the detached native
# server then remains alive for Jarvis. The selected dropdown is never rewritten.
$controller = Join-Path $jarvisDir 'qwen_model_manager.py'
$python = Join-Path $jarvisDir '.venv\Scripts\python.exe'
$prefix = @()
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $python = $pythonCommand.Source
    } else {
        $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
        if (-not $pyCommand) { throw 'Python was not found. Run this launcher from your configured Jarvis installation.' }
        $python = $pyCommand.Source
        $prefix = @('-3')
    }
}

$controllerArgs = @($controller, '--timeout', [string]$TimeoutSeconds)
if (-not [string]::IsNullOrWhiteSpace($ServerExe)) { $controllerArgs += @('--server-exe', $ServerExe) }
if (-not [string]::IsNullOrWhiteSpace($ModelPath)) { $controllerArgs += @('--model-path', $ModelPath) }
if (-not [string]::IsNullOrWhiteSpace($Profile)) { $controllerArgs += @('--profile', $Profile) }
if ($Port -gt 0) { $controllerArgs += @('--port', [string]$Port) }
if ($ContextTokens -gt 0) { $controllerArgs += @('--context-tokens', [string]$ContextTokens) }
if ($MaxOutputTokens -gt 0) { $controllerArgs += @('--max-output-tokens', [string]$MaxOutputTokens) }

& $python @prefix @controllerArgs
exit $LASTEXITCODE
