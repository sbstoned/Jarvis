from pathlib import Path
import re
import subprocess
import threading
import urllib.request
from http.server import ThreadingHTTPServer

j = Path("jarvis.py").read_text(encoding="utf-8")
d = Path("ui/dashboard.py").read_text(encoding="utf-8")
a = Path("ui/airtouch/airtouch.js").read_text(encoding="utf-8")
setup = Path("SETUP_AIR_TOUCH.ps1").read_text(encoding="utf-8")

assert "handle_airtouch_command" in j
assert "/api/airtouch/settings" in d
assert "/api/airtouch/external" in d
assert "RegisterHotKey" in d
assert "restart_after_success" in j
assert "initializeAdjustablePanels" in Path("ui/app.js").read_text(encoding="utf-8")
assert "localStorage" in a
assert "FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_ROOT)" in a
assert "HandLandmarker.createFromOptions(fileset,options)" in a
assert "detectForVideo(state.video" in a
assert 'executionMode:"main thread"' in a
assert "new Worker" not in a
assert "createImageBitmap" not in a
assert "def do_HEAD(self):" in d
assert "'.mjs': 'application/javascript; charset=utf-8'" in d
assert "'.wasm': 'application/wasm'" in d
assert "'.task': 'application/octet-stream'" in d

version = re.search(r'MEDIAPIPE_VERSION="([^"]+)"', a).group(1)
setup_versions = re.findall(r"tasks-vision@([^/]+)/", setup)
assert setup_versions and all(item == version for item in setup_versions)

assets = {
    "/airtouch/vendor/vision_bundle.mjs": ("application/javascript", 100_000),
    "/airtouch/vendor/wasm/vision_wasm_internal.js": ("application/javascript", 100_000),
    "/airtouch/vendor/wasm/vision_wasm_internal.wasm": ("application/wasm", 1_000_000),
    "/airtouch/vendor/wasm/vision_wasm_nosimd_internal.js": ("application/javascript", 100_000),
    "/airtouch/vendor/wasm/vision_wasm_nosimd_internal.wasm": ("application/wasm", 1_000_000),
    "/airtouch/model/hand_landmarker.task": ("application/octet-stream", 1_000_000),
}
for endpoint, (_, minimum) in assets.items():
    file_path = Path("ui/airtouch") / endpoint.removeprefix("/airtouch/")
    assert file_path.stat().st_size >= minimum, (file_path, file_path.stat().st_size)
    if file_path.suffix == ".wasm":
        assert file_path.read_bytes()[:4] == b"\0asm"
    if file_path.name.endswith("_internal.js"):
        assert "var ModuleFactory" in file_path.read_text(encoding="utf-8", errors="ignore")
bundle = Path("ui/airtouch/vendor/vision_bundle.mjs").read_text(encoding="utf-8")
assert 'ModuleFactory not set.' in bundle and 'self.ModuleFactory' in bundle
assert 'wasmLoaderPath' in bundle and 'wasmBinaryPath' in bundle

# Exercise the real handler on an ephemeral test port; this does not restart Jarvis.
from ui.dashboard import DashboardHandler
server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    base = f"http://127.0.0.1:{server.server_address[1]}"
    for endpoint, (expected_mime, minimum) in assets.items():
        request = urllib.request.Request(base + endpoint, method="HEAD")
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert expected_mime in response.headers.get_content_type()
            assert int(response.headers["Content-Length"]) >= minimum
            assert response.read() == b""
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)

for script in ("ui/airtouch/airtouch.js", "ui/airtouch/airtouch-worker.js", "TEST_AIR_TOUCH.js"):
    checked = subprocess.run(["node", "--check", script], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
structural = subprocess.run(["node", "TEST_AIR_TOUCH.js"], capture_output=True, text=True)
assert structural.returncode == 0, structural.stderr

print(
    f"Air Touch integration regression passed (MediaPipe {version}; main-thread runtime; "
    "local bundle/WASM/model sizes and magic; HEAD MIME endpoints; JavaScript syntax)."
)
