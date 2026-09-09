from pathlib import Path
import ast
d=Path("ui/dashboard.py").read_text(encoding="utf-8")
a=Path("ui/app.js").read_text(encoding="utf-8")
j=Path("jarvis.py").read_text(encoding="utf-8")
ast.parse(d); ast.parse(j)

# POST routes must live in do_POST, not do_GET.
get_block=d[d.index("    def do_GET(self):"):d.index("    def do_POST(self):")]
post_block=d[d.index("    def do_POST(self):"):]
assert "/api/voice/settings" not in get_block
assert "/api/voice/preview" not in get_block
assert "/api/voice/settings" in post_block
assert "/api/voice/preview" in post_block

# Preview route persists chosen voice before invoking preview.
assert "settings_payload['kokoro_voice'] = voice" in post_block
assert "settings = save_voice_settings_dashboard(settings_payload)" in post_block
assert "send_command_to_jarvis(command)" in post_block

# UI must not silently swallow preview failures or reselect defaults.
assert "Selecting & generating preview" in a
assert "Preview failed — click to retry" in a
assert "data.settings" in a
assert "Selected — click to preview again" in a

# Jarvis engine itself also persists the chosen preview voice.
assert 'settings["kokoro_voice"]=voice' in j
assert "Voice preview played and selected." in j
print("v2.49 voice preview/selection regression passed.")
