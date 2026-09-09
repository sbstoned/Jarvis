"""Local Qwen model selection/switching for Jarvis v2.74.1+.

Jarvis owns one llama.cpp server on port 8081.  The dashboard can select among:
  * Qwen3-8B Abliterated Q4_K_M (fast / proven 40,960-token profile)
  * Qwen3.5-9B Uncensored HauhauCS Aggressive Q4_K_M (fast worker)
  * Qwen3.8-27B Uncensored HauhauCS Aggressive Q2_K_P (optional 10.68 GB quality profile)
  * Qwen3.8-27B OBLITERATED Q4_K_M (legacy large quality profile)

Only one model is resident at a time. This module owns the native server process,
readiness checks and bounded memory recovery for both Jarvis and the PS launcher.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional, Tuple
from urllib.parse import urlsplit

import requests

JARVIS_DIR = Path(__file__).resolve().parent
QWEN_PORT = int(os.getenv("JARVIS_QWEN_PORT", "8081") or "8081")
QWEN_BASE_URL = os.getenv("JARVIS_QWEN_BASE_URL", f"http://127.0.0.1:{QWEN_PORT}").rstrip("/")
QWEN_SERVER_EXE = os.path.expandvars(os.getenv("JARVIS_QWEN_SERVER_EXE", r"C:\llama.cpp\llama-server.exe"))
QWEN_27B_MODEL_PATH = os.path.expandvars(os.getenv(
    "JARVIS_QWEN_27B_MODEL_PATH",
    os.getenv("JARVIS_QWEN_MODEL_PATH", r"D:\Qwen3.8-27B-OBLITERATED\GGUF\Qwen3.8-27B-OBLITERATED-Q4_K_M.gguf"),
))
QWEN_8B_MODEL_PATH = os.path.expandvars(os.getenv(
    "JARVIS_QWEN_8B_MODEL_PATH",
    r"D:\Qwen3-8B-Abliterated\GGUF\Qwen3-8B-abliterated.i1-Q4_K_M.gguf",
))
QWEN_35_9B_MODEL_PATH = os.path.expandvars(os.getenv(
    "JARVIS_QWEN_35_9B_MODEL_PATH",
    r"D:\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive\GGUF\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
))

QWEN_38_27B_AGGRESSIVE_Q2_FILENAME = "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf"

def _first_existing_model_path(env_name: str, *candidates: str) -> str:
    """Use an explicit override first, then common Jarvis D:-drive layouts."""
    override = os.path.expandvars(os.getenv(env_name, "")).strip()
    if override:
        return override
    expanded = [os.path.expandvars(str(x)) for x in candidates if str(x).strip()]
    for candidate in expanded:
        try:
            if Path(candidate).is_file():
                return candidate
        except Exception:
            pass
    return expanded[0] if expanded else ""

QWEN_38_27B_AGGRESSIVE_Q2_MODEL_PATH = _first_existing_model_path(
    "JARVIS_QWEN_38_27B_AGGRESSIVE_Q2_MODEL_PATH",
    rf"D:\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF\{QWEN_38_27B_AGGRESSIVE_Q2_FILENAME}",
    rf"D:\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF\GGUF\{QWEN_38_27B_AGGRESSIVE_Q2_FILENAME}",
    rf"D:\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive\GGUF\{QWEN_38_27B_AGGRESSIVE_Q2_FILENAME}",
    rf"D:\{QWEN_38_27B_AGGRESSIVE_Q2_FILENAME}",
)
RUNTIME_PROFILE = JARVIS_DIR / "qwen_runtime_profile.json"
SELECTION_FILE = JARVIS_DIR / "qwen_selected_profile.json"
START_SCRIPT = JARVIS_DIR / "START_QWEN_LOCAL.ps1"
SWITCH_LOCK = threading.RLock()
STARTUP_REPORT = JARVIS_DIR / "qwen_startup_report.json"
_OWNED_SERVER = None

MODEL_PROFILES = {
    "8b": {
        "label": "Qwen3-8B Abliterated Q4_K_M (8 GB fast)",
        "path": QWEN_8B_MODEL_PATH,
    },
    "9b35": {
        "label": "Qwen3.5-9B HauhauCS Aggressive Q4_K_M (fast worker)",
        "path": QWEN_35_9B_MODEL_PATH,
        "native_context": 262144,
        "runtime_context_default": 40960,
        "runtime_context_min": 16384,
    },
    "27b38q2": {
        "label": "Qwen3.8-27B HauhauCS Aggressive Q2_K_P (10.68 GB optional quality)",
        "path": QWEN_38_27B_AGGRESSIVE_Q2_MODEL_PATH,
        "hf_repo": "HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF",
        "hf_file": QWEN_38_27B_AGGRESSIVE_Q2_FILENAME,
        # HauhauCS/Qwen model card: 262,144 is the native context maximum.
        # Framework-specific extension beyond native context is deliberately opt-in.
        "native_context": 262144,
        "runtime_context_default": 40960,
        "runtime_context_min": 16384,
    },
    "27b": {
        "label": "Qwen3.8-27B OBLITERATED Q4_K_M (large quality)",
        "path": QWEN_27B_MODEL_PATH,
    },
}


def normalize_profile(profile: str | None) -> str:
    """Normalize UI/voice aliases while preserving AUTO."""
    raw = str(profile or "auto").strip().lower()
    compact = re.sub(r"[\s_.-]+", "", raw)
    if compact in {"8", "8b", "qwen8b", "qwen38b", "qwen38"}:
        return "8b"
    if compact in {
        "9", "9b", "9b35", "35", "qwen9b", "qwen35", "qwen359b",
        "qwen359baggressive", "hauhau", "aggressive",
    }:
        return "9b35"
    if compact in {
        "27b38q2", "27q2", "qwen38q2", "qwen3827bq2", "qwen3827baggressive",
        "aggressive27", "hauhau27", "hauhau27q2", "q2kp27", "q2kp",
    }:
        return "27b38q2"
    if compact in {"27", "27b", "qwen27b", "qwen3827b", "quality", "large"}:
        return "27b"
    return "auto"


def _auto_profile() -> str:
    """Return the lightweight standby model used when AUTO is not in a project stage.

    V42.6 project AUTO mode is hybrid and may temporarily promote hard stages to
    ``27b38q2``. This resolver intentionally keeps 9B as the fast standby/routine
    worker. The legacy OBLITERATED 27B is never an AUTO specialist.
    """
    override = normalize_profile(os.getenv("JARVIS_QWEN_AUTO_PROFILE", "auto"))
    # V42.6 AUTO is intentionally a two-model pool only. Never silently route
    # AUTO into the legacy OBLITERATED 27B or the 8B profile.
    if override in {"9b35", "27b38q2"}:
        return override
    if Path(QWEN_35_9B_MODEL_PATH).is_file():
        return "9b35"
    if Path(QWEN_38_27B_AGGRESSIVE_Q2_MODEL_PATH).is_file():
        return "27b38q2"
    # Return the expected worker so the caller reports the actionable missing path.
    return "9b35"


def resolve_profile(profile: str | None) -> str:
    selection = normalize_profile(profile)
    return _auto_profile() if selection == "auto" else selection


def selected_profile() -> str:
    try:
        data = json.loads(SELECTION_FILE.read_text(encoding="utf-8-sig"))
        return normalize_profile(data.get("profile"))
    except Exception:
        # V42.6: AUTO is the default selector. Project AUTO mode is hybrid and
        # routes difficult work between the 9B worker and the new 27B specialist.
        return "auto"


def save_selected_profile(profile: str | None) -> str:
    selection = normalize_profile(profile)
    try:
        tmp = SELECTION_FILE.with_suffix(SELECTION_FILE.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"profile": selection, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, SELECTION_FILE)
    except Exception:
        pass
    return selection


def profile_info(profile: str | None) -> dict:
    return dict(MODEL_PROFILES[resolve_profile(profile)])


def extract_profile_marker(command: str) -> Tuple[str, str]:
    """Strip dashboard-only profile metadata and return (clean_command, profile)."""
    requested = ""
    kept = []
    for line in str(command or "").splitlines():
        m = re.match(r"^\[JARVIS_QWEN_PROFILE\]\s+([A-Za-z0-9_.-]+)\s*$", line.strip(), re.I)
        if m:
            requested = normalize_profile(m.group(1))
        else:
            kept.append(line)
    return "\n".join(kept).strip(), requested


def _health(timeout: float = 1.5) -> bool:
    try:
        return requests.get(f"{QWEN_BASE_URL}/health", timeout=timeout).status_code == 200
    except Exception:
        return False


def _read_runtime_profile() -> dict:
    try:
        data = json.loads(RUNTIME_PROFILE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _runtime_context_tokens(timeout: float = 1.5, *, allow_record: bool = True) -> int:
    """Read the *target server slot* context from llama.cpp /props.

    Modern llama.cpp /props payloads may contain more than one context-looking
    number (for example target/default generation context plus speculative/MTP
    draft metadata).  The old recursive-min parser could therefore report a
    small draft/output window such as 6,144 even while the actual one-slot target
    server was running at 262,144.  The documented runtime value
    default_generation_settings.n_ctx is authoritative when present.
    """
    def valid(value):
        try:
            iv = int(value)
        except Exception:
            return 0
        return iv if 4096 <= iv <= 2_000_000 else 0

    def from_props(payload):
        if not isinstance(payload, dict):
            return 0

        # Official llama.cpp /props runtime slot field.  Prefer this before any
        # recursive scan so speculative/draft/MTP metadata cannot shrink the
        # reported target context.
        default = payload.get("default_generation_settings")
        if isinstance(default, dict):
            ctx = valid(default.get("n_ctx"))
            if ctx:
                return ctx

        # Compatibility with server builds that expose the slot directly.
        for key in ("n_ctx_slot", "n_ctx", "ctx_size", "context_size"):
            ctx = valid(payload.get(key))
            if ctx:
                return ctx

        # Last-resort compatibility scan. Runtime-looking n_ctx fields outrank
        # generic/model metadata and speculative/draft branches are deliberately
        # lowest priority.
        candidates = []
        def walk(value, path=()):
            if isinstance(value, dict):
                for key, item in value.items():
                    low = str(key).lower()
                    next_path = path + (low,)
                    if isinstance(item, (int, float)) and not isinstance(item, bool):
                        ctx = valid(item)
                        if ctx:
                            draft = any(any(tag in part for tag in ("draft", "spec", "mtp")) for part in next_path)
                            if low in {"n_ctx", "n_ctx_slot", "ctx_size", "context_size"}:
                                candidates.append((3 if draft else 0, ctx))
                            elif low in {"context_length", "n_ctx_train", "max_position_embeddings", "max_context_length"}:
                                candidates.append((4 if draft else 2, ctx))
                    walk(item, next_path)
            elif isinstance(value, list):
                for item in value:
                    walk(item, path)
        walk(payload)
        if not candidates:
            return 0
        best = min(priority for priority, _ in candidates)
        # At equal priority prefer the larger target-capacity value; using min
        # was the source of the misleading 6,144-token status with MTP payloads.
        return max(ctx for priority, ctx in candidates if priority == best)

    try:
        r = requests.get(f"{QWEN_BASE_URL}/props", timeout=timeout)
        if r.status_code == 200:
            ctx = from_props(r.json())
            if ctx:
                return ctx
    except Exception:
        pass
    if not allow_record:
        return 0
    try:
        return int(_read_runtime_profile().get("context") or 0)
    except Exception:
        return 0


def _env_int(names, default: int, low: int, high: int) -> int:
    for name in names:
        try:
            raw = os.getenv(name, "")
            if raw and re.fullmatch(r"-?\d+", raw.strip()):
                return max(low, min(high, int(raw)))
        except Exception:
            pass
    return default


def _desired_context(profile: str) -> int:
    if profile == "8b":
        return _env_int(
            ("JARVIS_QWEN_8B_CONTEXT", "JARVIS_QWEN_CONTEXT", "JARVIS_QWEN_CONTEXT_TOKENS"),
            40960, 4096, 40960,
        )
    if profile == "9b35":
        # Native capability is not a safe default allocation. Use the same 40K
        # starting slot as the specialist; larger native/YaRN windows stay opt-in.
        default_ctx = 1010000 if os.getenv("JARVIS_QWEN35_TRY_YARN", "").strip().lower() in {"1","true","yes","on"} else 40960
        return _env_int(
            ("JARVIS_QWEN_35_CONTEXT", "JARVIS_QWEN_35_9B_CONTEXT"),
            default_ctx, 16384, 1010000,
        )
    if profile == "27b38q2":
        # Native capability and runtime allocation are deliberately separate.
        # The HauhauCS 27B can address 262,144 tokens, but allocating the full KV
        # cache can prevent llama.cpp from becoming healthy on typical Jarvis
        # hardware. Use the previously proven 40,960-token runtime by default and
        # permit explicit opt-in increases up to the native maximum.
        return _env_int(
            ("JARVIS_QWEN_38_RUNTIME_CONTEXT", "JARVIS_QWEN_38_CONTEXT", "JARVIS_QWEN_38_27B_CONTEXT"),
            40960, 16384, 262144,
        )
    return _env_int(("JARVIS_QWEN_27B_CONTEXT", "JARVIS_QWEN_CONTEXT_TOKENS"), 40960, 4096, 262144)


def _runtime_matches(profile: str, desired_context: int | None = None) -> bool:
    """Require the selected model and its expected one-slot runtime."""
    if not _health():
        return False
    if active_profile() != profile:
        return False
    if profile == "27b":
        # Preserve the legacy OBLITERATED 27B behavior; its context remains
        # hardware-fit/manual and is not part of the V42.59 HauhauCS change.
        return True

    actual = _runtime_context_tokens()
    desired = desired_context or _desired_context(profile)
    data = _read_runtime_profile()
    if actual != desired:
        # Accept a verified same-model fallback without continually restarting it.
        fallback_ok = (
            profile in {"8b", "9b35"}
            and bool(data.get("context_fallback_used"))
            and int(data.get("requested_context") or 0) == desired
            and int(data.get("context") or 0) == actual
            and actual >= int(MODEL_PROFILES[profile].get("runtime_context_min", 4096))
        )
        # For the 27B specialist, any verified one-slot runtime from 16K through
        # the native maximum is valid. This permits an explicit hardware-fit
        # override/fallback without a restart loop, while still rejecting the old
        # genuinely tiny 6,144 target slot.
        fallback_ok = fallback_ok or (
            profile == "27b38q2" and 16384 <= int(actual or 0) <= int(MODEL_PROFILES["27b38q2"]["native_context"])
        )
        if not fallback_ok:
            return False

    # Our still-live native handle already proves the one-slot launch flags.
    # Avoid spawning PowerShell for every generation call in this common case.
    if (_OWNED_SERVER is not None and _OWNED_SERVER.poll() is None
            and data.get("pid") == _OWNED_SERVER.pid and data.get("status") == "ready"):
        return int(data.get("parallel_slots") or 0) == 1 and data.get("context_shift") == "off"
    cmd = _windows_server_commandline()
    if cmd:
        if not re.search(r"(?:-np|--parallel)\s+1(?:\s|$)", cmd, re.I):
            return False
        if "--no-context-shift" not in cmd.lower():
            return False
    else:
        if int(data.get("parallel_slots") or 0) != 1:
            return False
        if str(data.get("context_shift") or "").lower() != "off":
            return False
    return True


def _same_path(a: str, b: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))
    except Exception:
        return str(a).strip().lower() == str(b).strip().lower()


def _windows_server_commandline() -> str:
    if os.name != "nt":
        return ""
    script = (
        f"$p={QWEN_PORT}; "
        "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" -ErrorAction SilentlyContinue | "
        "Where-Object { $_.CommandLine -and ($_.CommandLine -match ('(--port|-p)\\s+'+$p+'(\\s|$)')) } | "
        "Select-Object -First 1 -ExpandProperty CommandLine"
    )
    try:
        cp = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=15,
        )
        return (cp.stdout or "").strip()
    except Exception:
        return ""


def active_profile() -> str:
    # The live server is authoritative. A previous launch receipt must never
    # relabel a different model as the user's strictly selected model.
    try:
        response = requests.get(f"{QWEN_BASE_URL}/props", timeout=1.0)
        props = response.json() if response.status_code == 200 else {}
        model = props.get("model_path") if isinstance(props, dict) else None
        if model:
            return next((key for key, info in MODEL_PROFILES.items()
                         if _same_path(model, info["path"])), "")
    except Exception:
        pass
    cmd = _windows_server_commandline()
    if cmd:
        match = re.search(r'(?:^|\s)(?:-m|--model)\s+(?:"([^"]+)"|(\S+))', cmd, re.I)
        if match:
            model = match.group(1) or match.group(2)
            return next((key for key, info in MODEL_PROFILES.items()
                         if _same_path(model, info["path"])), "")
    data = _read_runtime_profile()
    if data.get("status") in {"failed", "cancelled", "timeout"}:
        return ""
    model = str(data.get("model") or "")
    if model:
        return next((key for key, info in MODEL_PROFILES.items()
                     if _same_path(model, info["path"])), "")
    return ""


def _port_open() -> bool:
    # A loading server returns HTTP 503. Testing only /health == 200 here used
    # to mistake that still-running server for a stopped process.
    try:
        with socket.create_connection(("127.0.0.1", QWEN_PORT), timeout=0.3):
            return True
    except OSError:
        return False


def _terminate_server(proc) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    proc.wait(timeout=8)


def _stop_local_qwen() -> None:
    global _OWNED_SERVER
    _terminate_server(_OWNED_SERVER)
    _OWNED_SERVER = None
    if os.name != "nt":
        return
    script = (
        f"$p={QWEN_PORT}; "
        "$targets=Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" -ErrorAction SilentlyContinue | "
        "Where-Object { $_.CommandLine -and ($_.CommandLine -match ('(--port|-p)\\s+'+$p+'(\\s|$)')) }; "
        "$targets | ForEach-Object { "
        "if (Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue) { "
        "Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; "
        "Wait-Process -Id $_.ProcessId -Timeout 15 -ErrorAction SilentlyContinue } }"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Stop-Process failed")[-1800:])
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and _port_open():
        time.sleep(0.4)


def _write_json(path: Path, data: dict) -> None:
    # Only one controller owns a port at a time, including external PS launchers.
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _log_tail(path: Path, limit: int = 6000) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - limit))
            return handle.read(limit).decode("utf-8", errors="replace").strip()
    except OSError:
        return ""


def _profile_report_path(profile: str) -> Path:
    return STARTUP_REPORT.with_name(STARTUP_REPORT.stem + "_" + profile + STARTUP_REPORT.suffix)


def _save_startup_report(receipt: dict) -> None:
    # Keep each AUTO member's last attempt after switching to its peer.
    _write_json(_profile_report_path(receipt["profile"]), receipt)
    _write_json(STARTUP_REPORT, receipt)


def _memory_failure(detail: str) -> bool:
    return bool(re.search(
        r'out of memory|cudaErrorMemoryAllocation|cudaMalloc.*fail|'
        r'(?:failed|unable) to (?:allocate|alloc)|cannot allocate memory|'
        r'not enough (?:memory|space)|paging file is too small|bad_alloc|'
        r'(?:cuda|ggml).*alloc.*fail', detail, re.I))


def _startup_attempts(profile: str, context: int) -> list[dict]:
    """At most three launches, always the same GGUF. Retry only proven OOMs."""
    layers = os.getenv("JARVIS_QWEN_GPU_LAYERS", "all").strip().lower()
    if layers not in {"all", "auto"} and not re.fullmatch(r"\d+", layers):
        raise ValueError("JARVIS_QWEN_GPU_LAYERS must be all, auto or a nonnegative integer.")
    floor = int(MODEL_PROFILES[profile].get("runtime_context_min", 4096))
    attempts = [{"context": context, "gpu_layers": layers}]
    if os.getenv("JARVIS_QWEN_STARTUP_FALLBACK", "1").lower() in {"0", "false", "no", "off"}:
        return attempts
    # The first retry keeps GPU throughput, shrinking only the KV allocation.
    # The last retry also offloads fewer layers; it may trade speed for fit.
    reduced_layers = str(min(int(layers), 16)) if layers.isdigit() else "16"
    for ctx, ngl in ((max(floor, min(context, 16384)), layers),
                     (max(floor, min(context, 16384)), reduced_layers)):
        item = {"context": ctx, "gpu_layers": ngl}
        if item not in attempts:
            attempts.append(item)
    return attempts


def _server_command(profile: str, attempt: dict, max_output: int = 0) -> list[str]:
    context = int(attempt["context"])
    output = max_output or _env_int(
        ("JARVIS_QWEN_38_SERVER_MAX_OUTPUT_TOKENS",) if profile == "27b38q2" else
        ("JARVIS_QWEN_SERVER_MAX_OUTPUT_TOKENS",), 20480, 256, 65536)
    # Leave room for evidence in both models, especially after a memory fallback.
    output = min(output, max(256, context // 2))
    args = [str(QWEN_SERVER_EXE), "-m", str(MODEL_PROFILES[profile]["path"]),
            "-c", str(context), "-n", str(output), "--jinja",
            "--reasoning-format", "deepseek", "-np", "1", "--no-context-shift",
            "-ngl", str(attempt["gpu_layers"]), "-sm", "none", "-mg", "0",
            "--host", "127.0.0.1", "--port", str(QWEN_PORT)]
    for env, flag in (("JARVIS_QWEN_CACHE_TYPE_K", "--cache-type-k"),
                      ("JARVIS_QWEN_CACHE_TYPE_V", "--cache-type-v")):
        value = os.getenv(env, "").strip()
        if value:
            args.extend([flag, value])
    if profile == "9b35" and context > 262144:
        args.extend(["--rope-scaling", "yarn", "--rope-scale", "4",
                     "--yarn-orig-ctx", "262144"])
    return args


def _launch_server(command: list[str], stdout, stderr):
    kwargs = dict(cwd=str(Path(QWEN_SERVER_EXE).resolve().parent),
                  stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                  close_fds=True)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    # Keep this native handle: a shell wrapper exiting is never a health signal.
    return subprocess.Popen(command, **kwargs)


@contextmanager
def _thread_switch_lock(cancelled, deadline):
    while time.monotonic() < deadline:
        if cancelled():
            raise InterruptedError("Model startup cancelled by Stop.")
        if SWITCH_LOCK.acquire(timeout=0.25):
            try:
                yield
            finally:
                SWITCH_LOCK.release()
            return
    raise TimeoutError("Timed out waiting for the active model switch.")


@contextmanager
def _host_switch_lock(cancelled, deadline):
    """Serialize app and one-click launches across Windows processes."""
    if os.name != "nt":
        yield
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateMutexW(None, False, f"Local\\JarvisQwenStartup_{QWEN_PORT}")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        while time.monotonic() < deadline:
            if cancelled():
                raise InterruptedError("Model startup cancelled by Stop.")
            status = kernel.WaitForSingleObject(handle, 250)
            if status in (0, 0x80):  # acquired, or recovered from an exited owner
                acquired = True
                break
            if status != 0x102:
                raise ctypes.WinError(ctypes.get_last_error())
        if not acquired:
            raise TimeoutError("Timed out waiting for another Qwen launcher to finish.")
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def ensure_qwen_profile(
    profile: str | None,
    progress: Optional[Callable[[str], None]] = None,
    timeout: int = 600,
    persist_selection: bool = True,
    *,
    cancelled: Optional[Callable[[], bool]] = None,
    context_tokens: int = 0,
    max_output_tokens: int = 0,
) -> Tuple[bool, str]:
    """Ensure the requested Qwen GGUF owns port 8081.

    ``persist_selection=False`` is used by V42.6 AUTO project routing so temporary
    9B/27B stage switches never overwrite the user's dropdown selection.
    """
    global _OWNED_SERVER
    selection = normalize_profile(profile)
    if persist_selection:
        save_selected_profile(selection)
    requested = resolve_profile(selection)
    if selection == "auto":
        peer = "27b38q2" if requested == "9b35" else "9b35"
        first = ensure_qwen_profile(requested, progress, timeout, False,
                                    cancelled=cancelled, context_tokens=context_tokens,
                                    max_output_tokens=max_output_tokens)
        if first[0] or (cancelled and cancelled()):
            return first
        if progress:
            progress(f"AUTO could not start {requested}; trying {peer}. {first[1]}")
        second = ensure_qwen_profile(peer, progress, timeout, False, cancelled=cancelled,
                                     context_tokens=context_tokens, max_output_tokens=max_output_tokens)
        return second if second[0] else (False, f"AUTO could not activate either model: {first[1]}; {second[1]}")
    info = MODEL_PROFILES[requested]
    model_path = str(info["path"])
    is_cancelled = cancelled or (lambda: False)

    def report(message: str) -> None:
        if progress:
            try:
                progress(message)
            except Exception:
                pass

    if not Path(model_path).is_file():
        if requested == "8b":
            return False, (
                f"The Qwen3-8B Abliterated Q4_K_M model is not installed at {model_path}. "
                "Run DOWNLOAD_QWEN3_8B_ABLITERATED_Q4_K_M.bat once, then select it again."
            )
        if requested == "9b35":
            return False, (
                f"The Qwen3.5-9B HauhauCS Aggressive Q4_K_M model is not installed at {model_path}. "
                "Run DOWNLOAD_QWEN35_9B_AGGRESSIVE_Q4_K_M.bat once, then select Qwen3.5 9B again."
            )
        if requested == "27b38q2":
            return False, (
                f"The Qwen3.8-27B HauhauCS Aggressive Q2_K_P model is not installed at {model_path}. "
                "Place the GGUF in the default D:-drive repo folder, set "
                "JARVIS_QWEN_38_27B_AGGRESSIVE_Q2_MODEL_PATH, or run "
                "DOWNLOAD_QWEN38_27B_AGGRESSIVE_Q2_K_P.bat."
            )
        return False, f"The requested local Qwen model was not found: {model_path}"

    if not Path(QWEN_SERVER_EXE).is_file():
        return False, f"llama-server.exe was not found at {QWEN_SERVER_EXE}. Set JARVIS_QWEN_SERVER_EXE to its installed path."

    endpoint = urlsplit(QWEN_BASE_URL)
    if (endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost"}
            or (endpoint.port or 80) != QWEN_PORT or endpoint.path not in {"", "/"}):
        return False, (f"Local model switching requires JARVIS_QWEN_BASE_URL=http://127.0.0.1:{QWEN_PORT}. "
                       "Set JARVIS_QWEN_PORT and the base URL to the same local server port.")

    desired_context = int(context_tokens or _desired_context(requested))
    floor = int(info.get("runtime_context_min", 4096))
    ceiling = 1010000 if requested == "9b35" else int(info.get("native_context", 262144))
    if not floor <= desired_context <= ceiling:
        return False, f"{requested} context must be between {floor:,} and {ceiling:,} tokens."
    deadline = time.monotonic() + max(1, float(timeout))

    try:
        with _thread_switch_lock(is_cancelled, deadline), _host_switch_lock(is_cancelled, deadline):
            if is_cancelled():
                return False, "Model startup cancelled by Stop."
            if _runtime_matches(requested, desired_context):
                ctx = _runtime_context_tokens()
                return True, f"{info['label']} is already active at {ctx:,}-token context."

            attempts = _startup_attempts(requested, desired_context)
            report(f"Loading {info['label']}; waiting for the native server to finish initializing…")
            _stop_local_qwen()
            if _port_open():
                return False, f"Port {QWEN_PORT} is still occupied. Close the process using it or choose another JARVIS_QWEN_PORT."
            receipt = {"version": "42.63.0", "profile": requested, "model": model_path,
                       "requested_context": desired_context, "port": QWEN_PORT,
                       "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "attempts": []}
            stdout_path = JARVIS_DIR / "qwen_server_stdout.log"
            stderr_path = JARVIS_DIR / "qwen_server_stderr.log"
            for number, attempt in enumerate(attempts, 1):
                if is_cancelled():
                    return False, "Model startup cancelled by Stop."
                if time.monotonic() >= deadline:
                    break
                command = _server_command(requested, attempt, max_output_tokens)
                record = dict(attempt, number=number, command=command, status="loading")
                receipt["attempts"].append(record)
                _save_startup_report(receipt)
                proc = None
                ready = False
                failure = ""
                try:
                    # Direct file handles cannot fill a PIPE and stall the loader.
                    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                        proc = _launch_server(command, out, err)
                    _OWNED_SERVER = proc
                    runtime = dict(profile=requested, model=model_path, pid=proc.pid,
                                   generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                                   model_family={"9b35": "qwen35", "27b38q2": "qwen38"}.get(requested, "qwen3"),
                                   context=attempt["context"], runtime_context=attempt["context"],
                                   requested_context=desired_context, native_context=info.get("native_context", desired_context),
                                   context_fallback_used=attempt["context"] != desired_context,
                                   gpu_layers=attempt["gpu_layers"], startup_fallback_used=number > 1,
                                   max_output_tokens=int(command[command.index("-n") + 1]),
                                   parallel_slots=1, context_shift="off", port=QWEN_PORT,
                                   status="loading")
                    _write_json(RUNTIME_PROFILE, runtime)
                    last_report = 0.0
                    while time.monotonic() < deadline:
                        if is_cancelled():
                            failure = "Model startup cancelled by Stop."
                            record["status"] = "cancelled"
                            break
                        rc = proc.poll()
                        if rc is not None:
                            failure = f"llama-server exited with code {rc} before becoming ready."
                            break
                        if _health(timeout=0.6):
                            if active_profile() != requested:
                                failure = "The server on the Qwen port reports a different model than the selected GGUF."
                                break
                            actual = _runtime_context_tokens(timeout=0.6, allow_record=False)
                            if actual == attempt["context"]:
                                runtime.update(context=actual, runtime_context=actual, status="ready")
                                _write_json(RUNTIME_PROFILE, runtime)
                                record.update(status="ready", pid=proc.pid, actual_context=actual)
                                receipt["status"] = "ready"
                                _save_startup_report(receipt)
                                ready = True
                                message = f"{info['label']} is verified online at {actual:,}-token context"
                                if number > 1:
                                    message += f" (memory fallback, GPU layers={attempt['gpu_layers']})"
                                report(message + ".")
                                return True, message + "."
                            if actual:
                                failure = f"Server slot is {actual:,} tokens; requested {attempt['context']:,}. Check llama.cpp runtime flags."
                                break
                        now = time.monotonic()
                        if now - last_report >= 5:
                            last_report = now
                            report(f"Loading {requested}: attempt {number}/{len(attempts)}, context={attempt['context']:,}, GPU layers={attempt['gpu_layers']}; waiting for /health and live context…")
                        time.sleep(0.25)
                    else:
                        failure = f"Timed out after {timeout}s waiting for llama-server readiness."
                        record["status"] = "timeout"
                except Exception as exc:
                    failure = f"Could not start {requested}: {exc}"
                finally:
                    if not ready:
                        _terminate_server(proc)
                        if _OWNED_SERVER is proc:
                            _OWNED_SERVER = None
                        data = _read_runtime_profile()
                        if proc is not None and data.get("pid") == proc.pid:
                            data["status"] = record["status"] if record["status"] != "loading" else "failed"
                            _write_json(RUNTIME_PROFILE, data)
                tail = (_log_tail(stderr_path) + "\n" + _log_tail(stdout_path)).strip()
                record.update(error=failure, log_tail=tail, exit_code=proc.returncode if proc else None)
                if record["status"] == "loading":
                    record["status"] = "failed"
                receipt["status"] = record["status"]
                _save_startup_report(receipt)
                if (record["status"] != "failed" or not _memory_failure(tail)
                        or number == len(attempts) or time.monotonic() >= deadline):
                    return False, (f"{info['label']}: {failure} {tail[-2200:]} "
                                   f"Startup details: {_profile_report_path(requested)}")
                report(f"{requested} hit a memory allocation error. Retrying the SAME model with a smaller allocation…")
            return False, f"Timed out loading {info['label']}. Startup details: {STARTUP_REPORT}"
    except Exception as exc:
        return False, f"Could not activate {info['label']}: {exc}. Check {STARTUP_REPORT}."


def describe_profiles() -> dict:
    return {
        "selection": selected_profile(),
        "resolved": resolve_profile(selected_profile()),
        "active": active_profile(),
        "active_context": _runtime_context_tokens() if _health() else 0,
        "models": {
            key: {
                "label": value["label"],
                "path": value["path"],
                "installed": Path(value["path"]).is_file(),
                "desired_context": _desired_context(key),
            }
            for key, value in MODEL_PROFILES.items()
        },
    }


def _main(argv=None) -> int:
    """START_QWEN_LOCAL.ps1 uses the same controller as the dashboard."""
    import argparse
    global QWEN_SERVER_EXE, QWEN_PORT, QWEN_BASE_URL
    parser = argparse.ArgumentParser(description="Start and verify the selected local Qwen model.")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--model-path", default="")
    parser.add_argument("--server-exe", default="")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--context-tokens", type=int, default=0)
    parser.add_argument("--max-output-tokens", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    if args.server_exe:
        QWEN_SERVER_EXE = os.path.expandvars(args.server_exe)
    if args.port is not None:
        QWEN_PORT = args.port
        QWEN_BASE_URL = f"http://127.0.0.1:{QWEN_PORT}"
    selection = normalize_profile(args.profile) if args.profile else selected_profile()
    if args.model_path:
        # Older wrappers may supply only -ModelPath. Infer that model family
        # before applying its context limits, without changing the saved choice.
        if not args.profile or selection == "auto":
            leaf = re.split(r"[\\/]", args.model_path)[-1].lower()
            if "27b" in leaf and "aggressive" in leaf and "q2_k_p" in leaf:
                selection = "27b38q2"
            elif "qwen3.5-9b" in leaf:
                selection = "9b35"
            elif "qwen3-8b" in leaf:
                selection = "8b"
            elif "27b" in leaf:
                selection = "27b"
        selection = resolve_profile(selection)
        MODEL_PROFILES[selection]["path"] = os.path.expandvars(args.model_path)
    ok, detail = ensure_qwen_profile(
        selection, progress=lambda message: print(message, flush=True),
        timeout=args.timeout, persist_selection=False,
        context_tokens=args.context_tokens, max_output_tokens=args.max_output_tokens)
    print(detail, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_main())
