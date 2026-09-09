$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $root "ai_providers.env"

Write-Host ""
Write-Host "JARVIS AI Provider Setup" -ForegroundColor Cyan
Write-Host "OpenAI can reuse OPENAI_API_KEY from your Hermes .env." -ForegroundColor DarkGray
Write-Host "Leave any field blank to keep it unset here." -ForegroundColor DarkGray
Write-Host ""

function Read-Secret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    if ($secure.Length -eq 0) { return "" }
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

$openai = Read-Secret "OpenAI API key (optional)"
$claude = Read-Secret "Anthropic API key for Claude"
$openaiModel = Read-Host "OpenAI model [gpt-5.6-sol]"
$claudeModel = Read-Host "Claude model [claude-sonnet-4-20250514]"
if ([string]::IsNullOrWhiteSpace($openaiModel)) { $openaiModel = "gpt-5.6-sol" }
if ([string]::IsNullOrWhiteSpace($claudeModel)) { $claudeModel = "claude-sonnet-4-20250514" }

$lines = @(
    "# Local Jarvis provider credentials. Do not share this file.",
    "JARVIS_OPENAI_MODEL=$openaiModel",
    "JARVIS_ANTHROPIC_MODEL=$claudeModel"
)
if (-not [string]::IsNullOrWhiteSpace($openai)) { $lines += "OPENAI_API_KEY=$openai" }
if (-not [string]::IsNullOrWhiteSpace($claude)) { $lines += "ANTHROPIC_API_KEY=$claude" }
Set-Content -Path $envPath -Value $lines -Encoding UTF8

Write-Host ""
Write-Host "Saved provider configuration to:" -ForegroundColor Green
Write-Host $envPath
Write-Host "Restart Jarvis after changing provider keys." -ForegroundColor Cyan
Write-Host ""
Pause
