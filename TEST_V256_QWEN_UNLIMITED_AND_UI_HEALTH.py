from pathlib import Path
import re

root = Path(__file__).resolve().parent
mp = (root / 'multi_provider.py').read_text(encoding='utf-8')
project = (root / 'local_qwen_project.py').read_text(encoding='utf-8')
dash = (root / 'ui' / 'dashboard.py').read_text(encoding='utf-8')
app = (root / 'ui' / 'app.js').read_text(encoding='utf-8')

assert 'JARVIS_QWEN_STREAM_IDLE_TIMEOUT", "600"' in mp
assert 'JARVIS_QWEN_STREAM_HARD_TIMEOUT", "0"' in mp
assert 'hard_timeout > 0 and elapsed > hard_timeout' in mp
assert 'hard_timeout=0' in project
assert "if path == '/api/health':" in dash
assert "api/health?watchdog=" in app
assert '__jarvisBackendFailures>=8' in app
assert 'showDashboardConnectionWarning' in app
assert "stage==='complete' || stage==='failure'" in app
assert 'setInterval(jarvisBackendWatchdog,3000)' in app
assert 'setInterval(jarvisRestartStatusWatchdog,2000)' in app
print('PASS: v2.56 unlimited-active-Qwen + dashboard health/restart overlay regression checks passed.')
