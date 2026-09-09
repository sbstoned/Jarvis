import ast
import json
import os
import tempfile
import threading
from pathlib import Path


def function_source(tree, name):
    node = next(item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)
    return ast.Module(body=[node], type_ignores=[])


# Exercise the real dashboard startup reset in isolation against a temporary file.
dashboard_source = Path("ui/dashboard.py").read_text(encoding="utf-8")
dashboard_tree = ast.parse(dashboard_source)
namespace = {
    "AIRTOUCH_LOCK": threading.RLock(),
    "AIRTOUCH_DEFAULTS": {"enabled": False, "cameraEnabled": False, "smoothing": 0.32},
    "json": json,
    "os": os,
}
exec(compile(function_source(dashboard_tree, "reset_airtouch_startup_state"), "ui/dashboard.py", "exec"), namespace)

with tempfile.TemporaryDirectory() as temp_dir:
    settings_file = Path(temp_dir) / "airtouch_settings.json"
    before = {
        "enabled": True,
        "cameraEnabled": True,
        "paused": True,
        "sensitivity": 1.75,
        "smoothing": 0.71,
        "debug": True,
        "calibration": {"x": 0.2, "y": 0.8},
        "layoutPosition": {"left": 123, "top": 45},
        "futurePreference": "must survive",
    }
    settings_file.write_text(json.dumps(before), encoding="utf-8")
    namespace["AIRTOUCH_SETTINGS_FILE"] = str(settings_file)
    namespace["safe_json_file"] = lambda path, default: json.loads(Path(path).read_text(encoding="utf-8"))

    result = namespace["reset_airtouch_startup_state"]()
    after = json.loads(settings_file.read_text(encoding="utf-8"))

    assert result == after
    assert after["enabled"] is False
    assert after["cameraEnabled"] is False
    assert {k: v for k, v in after.items() if k not in ("enabled", "cameraEnabled")} == {
        k: v for k, v in before.items() if k not in ("enabled", "cameraEnabled")
    }

assert "reset_airtouch_startup_state()\n    server = ThreadingHTTPServer" in dashboard_source

# Verify a voice-engine-only restart applies the same two-field reset.
jarvis_source = Path("jarvis.py").read_text(encoding="utf-8")
jarvis_tree = ast.parse(jarvis_source)
saved = []
voice_namespace = {
    "_airtouch_settings": lambda: {
        "enabled": True,
        "cameraEnabled": True,
        "sensitivity": 1.6,
        "debug": True,
        "calibration": [1, 2, 3],
    },
    "_save_airtouch_settings": lambda value: saved.append(dict(value)) or True,
}
exec(compile(function_source(jarvis_tree, "_reset_airtouch_startup_state"), "jarvis.py", "exec"), voice_namespace)
assert voice_namespace["_reset_airtouch_startup_state"]() is True
assert saved == [{
    "enabled": False,
    "cameraEnabled": False,
    "sensitivity": 1.6,
    "debug": True,
    "calibration": [1, 2, 3],
}]
main_body = jarvis_source[jarvis_source.index("def main():"):]
assert main_body.index("_reset_airtouch_startup_state()") < main_body.index("test_hermes_api()")

# Startup JavaScript must not call startCamera/getUserMedia. Only deliberate UI
# and voice action paths may enter startCamera.
air = Path("ui/airtouch/airtouch.js").read_text(encoding="utf-8")
init_body = air[air.index("function init(){"):air.index("window.AirTouch=")]
assert "startCamera(" not in init_body
assert "getUserMedia" not in init_body
assert "state.settings.enabled=false;\n  state.settings.cameraEnabled=false;" in air
assert "...server,enabled:false,cameraEnabled:false" in air
assert air.count("getUserMedia(") == 1
assert 'if(key==="enabled"){state.settings.enabled?startCamera()' in air

# Exercise enable/disable/pause/resume through the real voice handler with
# isolated persistence/UI stubs.
voice_cases = [
    ("Hey Jarvis, enable Air Touch", {"enabled": False, "cameraEnabled": False, "paused": True}, "enable", {"enabled": True, "cameraEnabled": True, "paused": False}),
    ("disable Air Touch", {"enabled": True, "cameraEnabled": True, "paused": False, "externalControl": True}, "disable", {"enabled": False, "cameraEnabled": False, "externalControl": False}),
    ("pause Air Touch", {"enabled": True, "cameraEnabled": True, "paused": False}, "pause", {"paused": True}),
    ("resume Air Touch", {"enabled": True, "cameraEnabled": True, "paused": True}, "resume", {"paused": False}),
]
handler_code = compile(function_source(jarvis_tree, "handle_airtouch_command"), "jarvis.py", "exec")
for command, initial, expected_action, expected_values in voice_cases:
    persisted = []
    actions = []
    handler_namespace = {
        "clean_transcription": lambda text: text,
        "_airtouch_settings": lambda current=dict(initial): dict(current),
        "_save_airtouch_settings": lambda value: persisted.append(dict(value)) or True,
        "_airtouch_ui_action": lambda action, **payload: actions.append((action, payload)),
        "_airtouch_target": lambda: {},
    }
    exec(handler_code, handler_namespace)
    handled, response = handler_namespace["handle_airtouch_command"](command)
    assert handled and response
    assert persisted and actions and actions[-1][0] == expected_action
    for key, value in expected_values.items():
        assert persisted[-1][key] == value, (command, key, persisted[-1])

for action in ("enable", "disable", "pause", "resume"):
    assert f'if(name==="{action}")' in air

print("Air Touch startup-off regression passed: runtime state reset, preferences preserved, no startup webcam path, and voice/UI controls retained.")
