from pathlib import Path
root=Path(__file__).resolve().parent
dash=(root/'ui/dashboard.py').read_text(encoding='utf-8')
app=(root/'ui/app.js').read_text(encoding='utf-8')
pre=(root/'JARVIS_START_PREFLIGHT.ps1').read_text(encoding='utf-8-sig')
start=(root/'START_COMMAND_CENTER.bat').read_text(encoding='utf-8')
mp=(root/'multi_provider.py').read_text(encoding='utf-8')
lqp=(root/'local_qwen_project.py').read_text(encoding='utf-8')
assert "DASHBOARD_BUILD_ID = 'v2.57-ui-health'" in dash
assert "'build_id': DASHBOARD_BUILD_ID" in dash
assert "status['active'] = bool(os.path.exists" in dash
assert "const JARVIS_DASHBOARD_BUILD_ID='v2.57-ui-health';" in app
assert "showDashboardConnectionWarning" in app
assert "__jarvisBackendFailures>=8" in app
assert "showJarvisRestartOverlay('JARVIS DASHBOARD CONNECTION LOST" not in app
assert "data.active===true" in app
assert "v2.57-ui-health" in pre and "/api/health" in pre
assert "v2.57-ui-health" in start and "/api/health" in start
assert 'QWEN_STREAM_IDLE_TIMEOUT = int(os.getenv("JARVIS_QWEN_STREAM_IDLE_TIMEOUT", "600"))' in mp
assert 'return ask_qwen(prompt, progress_callback=on_stream, hard_timeout=0)' in lqp
print('PASS: v2.57 dashboard health handshake + non-blocking watchdog + unlimited active Qwen checks passed.')
