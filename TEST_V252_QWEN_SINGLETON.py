from pathlib import Path

ROOT = Path(__file__).resolve().parent
ps1 = (ROOT / 'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')
bat = (ROOT / 'START_QWEN_LOCAL.bat').read_text(encoding='utf-8')

checks = {
    'named mutex': "Local\\JarvisQwenLocalStartup" in ps1,
    'health recheck': ps1.count('Test-QwenHealth') >= 3,
    'one slot': "'-np', '1'" in ps1,
    'loopback host': "'--host', '127.0.0.1'" in ps1,
    'hardware-aware context': "$DefaultContext = 4096" in ps1 and "'-c', " + '"$ContextSize"' + "" in ps1,
    'existing process detection': "Win32_Process" in ps1 and "llama-server.exe" in ps1,
    'bat delegates to ps1': 'START_QWEN_LOCAL.ps1' in bat,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
print('PASS: Qwen singleton/startup regression checks passed.')
