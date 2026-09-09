from pathlib import Path
a=Path("ui/airtouch/airtouch.js").read_text(encoding="utf-8")
assert "gesturePauseEnabled:false" in a
assert "gesturePauseHoldMs:1800" in a
assert "visualCursorLoop" in a
assert "inferenceIntervalMs" in a
assert "state.processingMs*0.82" in a
assert "firstInferenceLogged" in a
print("v2.36 Air Touch smoothness regression passed.")
