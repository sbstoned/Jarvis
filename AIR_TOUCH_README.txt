JARVIS v2.30 — AIR TOUCH

ARCHITECTURE
Webcam -> browser getUserMedia -> MediaPipe Hand Landmarker initialized and run on the
main browser thread -> local gesture state machine -> direct DOM / existing panel layout manager.

MediaPipe Tasks Vision 0.10.35 uses its official browser initialization pattern. Its generated
classic WASM loader publishes ModuleFactory globally, so it must not be dynamically imported
as an ES module inside a module Web Worker. GPU is preferred with an automatic CPU fallback.
No webcam frames are sent to Hermes, Gemini, ElevenLabs, or the Jarvis Python backend.

LOCAL DEPENDENCIES
MediaPipe Tasks Vision 0.10.35 — Apache-2.0
MediaPipe Hand Landmarker model — Google MediaPipe model asset
Browser APIs: getUserMedia, WebAssembly, requestAnimationFrame, WebGL (GPU delegate).

FIRST RUN
START_COMMAND_CENTER.bat automatically tries SETUP_AIR_TOUCH.ps1 if local MediaPipe
assets are missing. Jarvis still starts if download is unavailable.
SETUP_AIR_TOUCH.bat can also be run manually once.

GESTURES
Index finger: air cursor
Thumb/index pinch: click
Pinch hold on panel header: drag
Pinch hold at right/bottom panel edge: resize
Two fingers vertical: scroll target panel/page
Double pinch: double click
Fast horizontal swipe: switch dashboard
Open palm held: pause
Closed fist: cancel/release

AIR TOUCH VOICE COMMANDS
enable/disable/pause/resume/calibrate Air Touch
open/close Air Touch keyboard
enable/disable desktop control
increase/decrease cursor sensitivity
what am I pointing at
click/open/expand/minimize/move/scroll/type this

SAFETY
External Windows control is OFF by default.
Global Windows emergency hotkey: CTRL+ALT+SHIFT+X
HUD emergency-stop button.
Password fields blocked.
No automatic submit/purchase/delete/send behavior.
Tracking loss releases active drag/click.
Camera footage is not recorded or saved.

SETTINGS
Stored in airtouch_settings.json and browser localStorage.
Camera preview and debug mode default OFF.
Existing dashboard panel layout persists through dashboard_layout.json + localStorage.

IMPORTANT TEST LIMITATION
Automated structural/syntax tests can run here. Actual camera FPS, camera permission,
gesture accuracy and visible latency require the physical Windows webcam and browser,
so those values are intentionally not claimed until tested on the PC.
