from pathlib import Path
import ast

j=Path("jarvis.py").read_text(encoding="utf-8")
air=Path("ui/airtouch/airtouch.js").read_text(encoding="utf-8")

handlers=j[j.index("handlers = ["):j.index("]",j.index("handlers = ["))]
assert handlers.index("handle_direct_coding_request") < handlers.index("handle_airtouch_command")

# Development requests mentioning Air Touch must not be swallowed by operational handler.
assert "development_words" in j
assert '"fix"' in j and '"not working"' in j
assert "_looks_like_coding_followup" in j
assert "LAST_CODING_CONTEXT" in j

# Air Touch must expose diagnostics and use the supported main-thread Tasks runtime.
for term in [
    "airLog(", "PIPELINE LOG", "MEDIAPIPE_VERSION", 'executionMode:"main thread"',
    "FilesetResolver.forVisionTasks", 'delegate:"GPU"', 'delegate="CPU"',
    "wasmLoaderUrl", "wasmBinaryUrl", "MEDIAPIPE_MODEL_URL",
]:
    assert term in air, term
assert "new Worker" not in air

ast.parse(j)
print("v2.33 routing/Air Touch regression passed.")
