from pathlib import Path
base=Path(__file__).resolve().parent
app=(base/'ui'/'app.js').read_text(encoding='utf-8')
dash=(base/'ui'/'dashboard.py').read_text(encoding='utf-8')
start=(base/'START_COMMAND_CENTER.bat').read_text(encoding='utf-8',errors='ignore')
mp=(base/'multi_provider.py').read_text(encoding='utf-8')
lqp=(base/'local_qwen_project.py').read_text(encoding='utf-8')
assert "v2.59-resilient-dashboard" in app and "v2.59-resilient-dashboard" in dash
assert "__pollLiveStateBusy" in app and "setInterval(pollLiveState,750)" in app
assert "jarvisSafeJson('/api/telemetry',6000,{})" in app
assert "jarvisClientLog('heartbeat.failure'" in app
assert "/api/client-log" in dash and "/api/diagnostics/logs" in dash
assert "dashboard_frontend.log" in dash and "dashboard_http.log" in dash
assert "Chrome_v259" in start
assert 'QWEN_STREAM_IDLE_TIMEOUT = int(os.getenv("JARVIS_QWEN_STREAM_IDLE_TIMEOUT", "600"))' in mp
assert 'QWEN_STREAM_HARD_TIMEOUT = int(os.getenv("JARVIS_QWEN_STREAM_HARD_TIMEOUT", "0"))' in mp
assert 'return ask_qwen(prompt, progress_callback=on_stream, hard_timeout=0)' in lqp
print('PASS: v2.59 resilient dashboard diagnostics + unlimited active Qwen settings verified.')
