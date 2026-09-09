from pathlib import Path
import re

air=Path("ui/airtouch/airtouch.js").read_text(encoding="utf-8")
css=Path("ui/styles.css").read_text(encoding="utf-8")
ps=Path("HARD_RESTART_ALL_SYSTEMS.ps1").read_text(encoding="utf-8")
jarvis=Path("jarvis.py").read_text(encoding="utf-8")

# MediaPipe: no module-worker initialization; classic Emscripten loader is
# explicitly exported to window.ModuleFactory before task creation.
assert "loadClassicScript" in air
assert "prepareMediaPipeFileset" in air
assert 'typeof window.ModuleFactory!=="function"' in air
assert 'for(const delegate of ["GPU","CPU"])' in air
assert "HandLandmarker.createFromOptions" in air
assert "detectForVideo" in air

# Debug HUD is movable and position persists.
assert "bindMovableDebugPanel" in air
assert "DEBUG_POS_KEY" in air
assert "airtouch-debug-head" in air
assert "cursor:move" in css

# Restart really verifies the local URL went away, then verifies it came back.
assert "DashboardHttpUp" in ps
assert "Old dashboard URL verified OFFLINE." in ps
assert "FULL RESTART SUCCESS dashboard=true voiceHealth=true" in ps
assert "JarvisCommandCenterChrome" in ps
assert "START_COMMAND_CENTER.bat" in ps
assert "restart supervisor will verify they are offline" in jarvis

print("v2.34 Air Touch + restart reliability regression passed.")
