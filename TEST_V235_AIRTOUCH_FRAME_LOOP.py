from pathlib import Path
a=Path("ui/airtouch/airtouch.js").read_text(encoding="utf-8")
assert 'requestAnimationFrame(frameLoop)' in a
assert 'First animation frame callback received' in a
assert 'Inference loop produced zero camera frames after 2 seconds' in a
assert 'state.settings.cameraEnabled=true' in a
assert 'state.settings.paused=false' in a
assert 'populateCameras().catch' in a
assert 'detectForVideo(state.video,now)' in a
print("v2.35 Air Touch frame-loop regression passed.")
