from pathlib import Path
import ast

root = Path(__file__).resolve().parent
jarvis = (root / 'jarvis.py').read_text(encoding='utf-8')
manager = (root / 'qwen_model_manager.py').read_text(encoding='utf-8')
dashboard = (root / 'ui' / 'dashboard.py').read_text(encoding='utf-8')
app = (root / 'ui' / 'app.js').read_text(encoding='utf-8')
html = (root / 'ui' / 'index.html').read_text(encoding='utf-8')
ps = (root / 'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')
bench = (root / 'CHECK_QWEN_PERFORMANCE.py').read_text(encoding='utf-8')
downloader = (root / 'DOWNLOAD_QWEN3_8B_ABLITERATED_Q4_K_M.ps1').read_text(encoding='utf-8')

for source in (jarvis, manager, dashboard, bench):
    ast.parse(source)

assert html.index('value="auto"') < html.index('value="qwen8b"') < html.index('value="qwen"')
assert 'QWEN3 8B — ABLITERATED Q4_K_M (8GB FAST)' in html
assert "qwenProfile=providerChoiceNow==='qwen8b'?'8b'" in app
assert 'qwen_profile:qwenProfile' in app
assert '[JARVIS_QWEN_PROFILE]' in dashboard
assert "qwen_profile in {'auto','8b','27b'}" in dashboard
assert 'extract_profile_marker' in jarvis
assert 'ensure_qwen_profile' in jarvis
assert 'qwen_profile=requested_qwen_profile or "auto"' in jarvis
assert 'D:\\Qwen3-8B-Abliterated\\GGUF\\Qwen3-8B-abliterated.i1-Q4_K_M.gguf' in manager
assert 'DOWNLOAD_QWEN3_8B_ABLITERATED_Q4_K_M.bat' in manager
assert '$Target8GBSmallModel' in ps
assert "$ProfileName = 'full-gpu-8b-q4'" in ps
assert '$DefaultContext = 8192' in ps
assert '$AutoManualNgl = 99' in ps
assert "version = 'v2.74.1'" in ps
assert 'mradermacher/Qwen3-8B-abliterated-i1-GGUF' in downloader
assert 'Qwen3-8B-abliterated.i1-Q4_K_M.gguf' in downloader
assert '"stream": True' in bench
assert 'JARVIS_QWEN_BENCHMARK_TOKENS", "64"' in bench
assert 'Time to first token' in bench

from qwen_model_manager import extract_profile_marker, normalize_profile
clean, profile = extract_profile_marker('[JARVIS_QWEN_PROFILE] 8b\nmake a project\n[JARVIS_ATTACHED_FILE] C:\\tmp\\x.zip')
assert profile == '8b'
assert clean.startswith('make a project')
assert normalize_profile('qwen38b') == '8b'
assert normalize_profile('auto') == 'auto'

print('PASS: v2.74/v2.74.1 Qwen 8B/27B dropdown, persistent switching, RTX 4070 profile, downloader, and live benchmark are present.')
