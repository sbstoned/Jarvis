from pathlib import Path
root=Path(__file__).resolve().parent
app=(root/'ui/app.js').read_text(encoding='utf-8')
html=(root/'ui/index.html').read_text(encoding='utf-8')
dash=(root/'ui/dashboard.py').read_text(encoding='utf-8')
start=(root/'START_COMMAND_CENTER.bat').read_text(encoding='utf-8')
mp=(root/'multi_provider.py').read_text(encoding='utf-8')
lqp=(root/'local_qwen_project.py').read_text(encoding='utf-8')
assert "JARVIS_UI_BUILD_ID = 'v2.58-frontend-transport'" in app
assert "const JARVIS_DASHBOARD_BUILD_ID='v2.58-ui-health';" in app
assert 'function jarvisResolveUrl' in app
assert 'function jarvisFetch' in app
assert 'window.fetch=async function' not in app
assert 'let __jarvisRestartOverlay = null;' in app
assert '__jarvisBackendFailures>=20' in app
assert 'app.js?v=2.58-frontend-transport' in html
assert 'styles.css?v=2.58' in html
assert "DASHBOARD_BUILD_ID = 'v2.58-ui-health'" in dash
assert "no-store, no-cache, must-revalidate" in dash
assert 'JarvisCommandCenterChrome_v258' in start
assert 'v2.58-ui-health' in start
assert 'QWEN_STREAM_IDLE_TIMEOUT = int(os.getenv("JARVIS_QWEN_STREAM_IDLE_TIMEOUT", "600"))' in mp
assert 'QWEN_STREAM_HARD_TIMEOUT = int(os.getenv("JARVIS_QWEN_STREAM_HARD_TIMEOUT", "0"))' in mp
assert 'return ask_qwen(prompt, progress_callback=on_stream, hard_timeout=0)' in lqp
print('PASS: v2.58 frontend transport, cache isolation, dashboard health, and unlimited Qwen checks passed.')
