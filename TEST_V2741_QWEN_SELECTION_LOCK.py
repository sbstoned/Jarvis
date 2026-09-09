from pathlib import Path
import tempfile
import importlib.util

root=Path(__file__).resolve().parent
manager=(root/'qwen_model_manager.py').read_text(encoding='utf-8')
jarvis=(root/'jarvis.py').read_text(encoding='utf-8')
app=(root/'ui'/'app.js').read_text(encoding='utf-8')
bat=(root/'START_QWEN_LOCAL.bat').read_text(encoding='utf-8')
ps1=(root/'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')

assert 'SELECTION_FILE = JARVIS_DIR / "qwen_selected_profile.json"' in manager
assert 'def save_selected_profile' in manager
assert 'def selected_profile' in manager
assert 'def resolve_profile' in manager
assert 'Explicit 8B selection NEVER falls back' in manager
assert '__jarvis_switch_qwen_only__' in jarvis.lower()
assert 'save_selected_profile(requested_qwen_profile)' in jarvis
assert 'QWEN_PROVIDER_SELECTION_KEY' in app
assert "switchLocalQwenFromDropdown" in app
assert "qwen_profile:profile" in app
assert 'set "JARVIS_QWEN_MODEL_PATH=D:' not in bat
assert 'qwen_selected_profile.json' in ps1
assert "if ($SelectedProfile -eq '8b')" in ps1
assert "version = 'v2.74.1'" in ps1
print('PASS: v2.74.1 persistent Qwen selector lock is present and startup no longer forces 27B.')
