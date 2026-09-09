import os
import sys
import re
import time
import wave
import tempfile
import subprocess
import json
import threading
import uuid
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import requests
import desktop_automation
import web_research

# ---------------------------------------------------------------------
# Single-instance guard
# ---------------------------------------------------------------------
_JARVIS_INSTANCE_MUTEX = None
_HARD_RESTART_REQUESTED = False
_HARD_RESTART_REQUEST_LOCK = threading.Lock()

def _acquire_jarvis_single_instance():
    """Allow exactly one Jarvis voice-engine process per Windows session."""
    global _JARVIS_INSTANCE_MUTEX

    if os.name != "nt":
        return True

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(
            None,
            False,
            "Local\\JarvisVoiceEngineSingleton_v2197",
        )
        if not handle:
            return True

        _JARVIS_INSTANCE_MUTEX = handle
        ERROR_ALREADY_EXISTS = 183

        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            _JARVIS_INSTANCE_MUTEX = None
            print("Another Jarvis voice engine is already running. This duplicate instance will exit.")
            return False

        return True
    except Exception as exc:
        print(f"Single-instance check warning: {exc}")
        return True


if not _acquire_jarvis_single_instance():
    raise SystemExit(23)

from multi_provider import (
    extract_provider_request,
    ask_provider,
    provider_status,
    run_provider_coding_agent,
)
from local_qwen_project import (
    wants_project_zip, generate_project_zip, analyze_and_edit_project_zip, DEFAULT_MAX_FILES,
    prepare_project_qwen_routing, clear_project_qwen_routing,
    begin_project_run, finish_project_run, request_project_stop,
    checkpoint_stopped_project, ProjectStopRequested,
    AutomaticRepairExhausted, record_project_heartbeat,
)
from jarvis_v4242_memory import default_store as shared_memory_store, worker_context_contract
from qwen_model_manager import extract_profile_marker, ensure_qwen_profile, normalize_profile, resolve_profile, save_selected_profile, active_profile
import sounddevice as sd
import numpy as np

from faster_whisper import WhisperModel
from dotenv import load_dotenv
from openwakeword.model import Model as WakeWordModel

try:
    import win32com.client
except ImportError:
    win32com = None


# ============================================================
# JARVIS v2.9
# ============================================================
#
# Architecture:
#
#   "Hey Jarvis"
#        ↓
#   openWakeWord
#        ↓
#   Faster-Whisper
#        ↓
#   Fast local command?
#        │
#        ├── YES → answer locally
#        │
#        └── NO
#             ↓
#   PERMANENT HERMES SESSION
#             ↓
#   Gemini + Memory + Tools + Skills
#             ↓
#   ElevenLabs streaming TTS
#             ↓
#   Speakers
#
# Hermes, not this Python process, owns the persistent
# conversational history.
# ============================================================


# ============================================================
# PATHS
# ============================================================

JARVIS_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


def _shared_memory_event(kind, payload, **fields):
    """Record coordination evidence without making memory a runtime dependency."""
    try:
        return shared_memory_store(JARVIS_DIR).append_event(kind, payload, **fields)
    except Exception as exc:
        try:
            log(f"Shared memory event warning: {exc}")
        except Exception:
            pass
        return None


def _shared_memory_context(project_path="", limit=10, max_chars=4200):
    try:
        return shared_memory_store(JARVIS_DIR).context_packet(
            project=project_path, limit=limit, max_chars=max_chars,
        )
    except Exception:
        return "[]"

LOG_DIR = os.path.join(
    JARVIS_DIR,
    "logs"
)

os.makedirs(
    LOG_DIR,
    exist_ok=True,
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "jarvis.log",
)


# ============================================================
# LIVE DASHBOARD STATE
# ============================================================

LIVE_STATE_FILE = os.path.join(
    JARVIS_DIR,
    "live_state.json",
)

live_state_lock = threading.RLock()


def update_live_state(state=None, **extra):
    """Publish lightweight runtime state for the dashboard.

    Uses an atomic replace so the UI never reads a half-written JSON file.
    """
    try:
        with live_state_lock:
            current = {}
            if os.path.exists(LIVE_STATE_FILE):
                try:
                    with open(LIVE_STATE_FILE, "r", encoding="utf-8") as handle:
                        current = json.load(handle)
                except Exception:
                    current = {}

            if state is not None:
                current["state"] = str(state).upper()

            current.update(extra)
            current["updated_at"] = datetime.now().isoformat(timespec="milliseconds")
            current["pid"] = os.getpid()

            temp_path = LIVE_STATE_FILE + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(current, handle, indent=2, default=str)
            os.replace(temp_path, LIVE_STATE_FILE)
            return True
    except Exception as exc:
        try:
            log(f"Live state update error: {exc}")
        except Exception:
            pass
        return False


def request_dashboard_widget(widget, payload=None):
    update_live_state(
        ui_action={
            "id": uuid.uuid4().hex,
            "widget": str(widget).lower(),
            "payload": payload or {},
            "created_at": datetime.now().isoformat(timespec="milliseconds"),
        }
    )


JARVIS_IPC_PORT = 8765
_ipc_server = None


class AttachmentCommandResult(str):
    """Keep ordinary text replies while exposing whether the ZIP job was accepted."""
    def __new__(cls, message, accepted):
        value = super().__new__(cls, message)
        value.attachment_accepted = bool(accepted)
        return value


class JarvisIPCHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _json(self, payload, status=200):
        raw = json.dumps(payload, default=str).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            # The dashboard may intentionally disconnect when a command is
            # interrupted, the page reloads, or Jarvis is restarting. That is
            # not a Jarvis failure and should not produce a traceback storm.
            return False
        return True

    def do_GET(self):
        if self.path == "/agents":
            self._json({"service": "jarvis-core", "agents": _agent_jobs_snapshot()})
            return
        if self.path == "/state":
            try:
                with open(LIVE_STATE_FILE, "r", encoding="utf-8") as handle:
                    state = json.load(handle)
            except Exception:
                state = {"state": "UNKNOWN"}
            self._json(state)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/command":
            self._json({"error": "not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            command = clean_transcription(str(data.get("command", "")))
            if not command:
                self._json({"error": "empty command"}, 400)
                return
            answer = process_command(command)
            payload = {"status": "ok", "command": command, "response": answer or ""}
            if isinstance(answer, AttachmentCommandResult):
                payload['attachment_accepted'] = answer.attachment_accepted
            self._json(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browser/dashboard went away while the command was still running.
            return
        except Exception as exc:
            log(f"IPC command error: {exc}")
            try:
                self._json({"status": "error", "error": str(exc)}, 500)
            except Exception:
                pass


def start_jarvis_ipc_server():
    global _ipc_server
    if _ipc_server is not None:
        return
    try:
        _ipc_server = ThreadingHTTPServer(("127.0.0.1", JARVIS_IPC_PORT), JarvisIPCHandler)
        thread = threading.Thread(
            target=_ipc_server.serve_forever,
            daemon=True,
            name="JarvisIPC",
        )
        thread.start()
        log(f"Jarvis IPC listening on 127.0.0.1:{JARVIS_IPC_PORT}")
    except OSError as exc:
        log(f"Jarvis IPC unavailable: {exc}")


# ============================================================
# AUDIO
# ============================================================

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

WAKE_BLOCK_SIZE = 1280

COMMAND_BLOCK_DURATION = 0.10

COMMAND_BLOCK_SIZE = int(
    SAMPLE_RATE * COMMAND_BLOCK_DURATION
)


# ============================================================
# WAKE WORD
# ============================================================

WAKE_MODEL_NAME = "hey_jarvis"

WAKE_THRESHOLD = 0.45

WAKE_PREROLL_SECONDS = 1.2

WAKE_PREROLL_BLOCKS = max(
    1,
    int(
        WAKE_PREROLL_SECONDS
        * SAMPLE_RATE
        / WAKE_BLOCK_SIZE
    ),
)

WAKE_COOLDOWN_SECONDS = 0.35


# ============================================================
# SPEECH DETECTION
# ============================================================

SPEECH_THRESHOLD = 300
SILENCE_THRESHOLD = 180

AUTO_CALIBRATE_MIC = True
CALIBRATION_SECONDS = 1.5

END_SILENCE_SECONDS = 0.9

MAX_COMMAND_SECONDS = 45

COMMAND_START_TIMEOUT = 5.0

PRE_ROLL_SECONDS = 0.65

BARGE_IN_RMS_THRESHOLD = 900
BARGE_IN_CONSECUTIVE_BLOCKS = 8
BARGE_IN_GRACE_SECONDS = 1.25


# ============================================================
# FOLLOW-UP CONVERSATION
# ============================================================

FOLLOW_UP_MODE = True

FOLLOW_UP_SECONDS = 5.0

# Number of natural follow-ups allowed before Jarvis returns
# to wake-word standby.
MAX_FOLLOW_UPS = 3

FOLLOW_UP_PREFIXES = (
    "and ", "also ", "what ", "what about ", "how ", "how about ",
    "can ", "can you ", "could ", "could you ", "would you ",
    "tell me ", "read ", "open ", "search ", "find ", "check ",
    "show ", "do ", "is ", "are ", "when ", "where ", "why ",
    "who ", "which ", "yes", "no", "thanks", "thank you",
)

FOLLOW_UP_CANCEL_PHRASES = (
    "never mind", "nevermind", "cancel", "that's all", "that is all",
    "stop listening", "no thanks", "no thank you",
)


# ============================================================
# FAST EMAIL
# ============================================================

WORK_EMAIL_ACCOUNT = "work"
HIMALAYA_TIMEOUT = 20


# ============================================================
# FAST OUTLOOK CALENDAR / DIRECTORY
# ============================================================

OUTLOOK_CALENDAR_FOLDER = 9
OUTLOOK_CONTACTS_FOLDER = 10
CALENDAR_LOOKAHEAD_DAYS = 14


# ============================================================
# CONFIRMED ACTIONS
# ============================================================

WORK_EMAIL_ADDRESS = os.getenv("JARVIS_WORK_EMAIL_ADDRESS", "").strip()
CONFIRMATION_TIMEOUT = 12.0

# Any send / calendar write lives here only until the user confirms.
pending_action = None

# Context for natural follow-ups like "reply and tell them..."
last_email_context = None

# Wake-word barge-in state.
speech_was_interrupted = False

# ============================================================
# SPEECH / COMMAND COORDINATION
# ============================================================
# Only one command may own the foreground conversation at a time.
# A new dashboard/IPC command first interrupts current speech, then waits
# for the previous foreground command to release the lock.
foreground_command_lock = threading.RLock()

# One shared cancel signal for the currently-playing ElevenLabs stream.
speech_cancel_lock = threading.RLock()
active_speech_cancel_event = None

# Prevent two TTS streams from ever opening the output device together.
tts_playback_lock = threading.RLock()

# Full responses remain visible in the dashboard, but very long diagnostic /
# coding reports are shortened for voice playback so Jarvis does not talk for
# several minutes.
MAX_SPOKEN_RESPONSE_CHARS = 950


def interrupt_current_speech():
    global active_speech_cancel_event

    interrupted = False
    with speech_cancel_lock:
        event = active_speech_cancel_event
        if event is not None:
            event.set()
            interrupted = True

    # Kokoro/Piper playback uses sounddevice directly rather than the
    # ElevenLabs cancellation event, so stop that audio path as well.
    try:
        sd.stop()
        interrupted = True
    except Exception:
        pass

    return interrupted


def _is_stop_speech_command(text):
    normalized = re.sub(
        r"[^a-z0-9' ]+",
        " ",
        clean_transcription(text).lower(),
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized in {
        "stop",
        "stop talking",
        "stop speaking",
        "quiet",
        "be quiet",
        "shut up",
        "cancel speech",
        "stop reading",
    }


def _spoken_version(answer):
    text = str(answer or "").strip()

    if len(text) <= MAX_SPOKEN_RESPONSE_CHARS:
        return text

    # Keep the UI/chat result complete; only shorten what ElevenLabs reads.
    cut = text[:MAX_SPOKEN_RESPONSE_CHARS]
    sentence_end = max(
        cut.rfind(". "),
        cut.rfind("? "),
        cut.rfind("! "),
        cut.rfind("\n"),
    )

    if sentence_end >= 350:
        cut = cut[: sentence_end + 1]

    return (
        cut.rstrip()
        + " I've put the rest of the response in the dashboard."
    )

# ============================================================
# CODING / PROJECT AUTOMATION
# ============================================================

# Jarvis live local workspace. This folder is the source of truth when
# Jarvis inspects or improves itself. GitHub may be older.
JARVIS_HOME = os.path.abspath(JARVIS_DIR)
SELF_WORKSPACE = JARVIS_HOME
MANAGED_PROJECTS_ROOT = os.path.join(str(Path.home()), "Documents", "JarvisProjects")

PROJECT_ALIASES = {
    "jarvis": JARVIS_DIR,
    "jarvis project": JARVIS_DIR,
    "dailybread": os.path.join(os.path.expanduser("~"), "Documents", "DailyBreadpluzx"),
    "daily bread": os.path.join(os.path.expanduser("~"), "Documents", "DailyBreadpluzx"),
    "dailybreadplus": os.path.join(os.path.expanduser("~"), "Documents", "DailyBreadpluzx"),
    "scan2cookz": os.path.join(os.path.expanduser("~"), "Documents", "Scan2Cookz"),
    "scan 2 cookz": os.path.join(os.path.expanduser("~"), "Documents", "Scan2Cookz"),
}

_USER_HOME = str(Path.home())
PROJECT_DISCOVERY_ROOTS = [
    JARVIS_DIR,
    os.path.join(_USER_HOME, "Documents"),
    os.path.join(_USER_HOME, "Desktop"),
    os.path.join(_USER_HOME, "source", "repos"),
    os.path.join(_USER_HOME, "repos"),
    os.path.join(_USER_HOME, "GitHub"),
    MANAGED_PROJECTS_ROOT,
    r"C:\Projects",
    r"C:\src",
]

PROJECT_DISCOVERY_IGNORES = {
    ".git", ".venv", "venv", "node_modules", "build", ".dart_tool",
    "__pycache__", "AppData", "$Recycle.Bin",
}

def _normalized_project_name(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

def _discover_project_by_name(name):
    wanted = _normalized_project_name(name)
    if len(wanted) < 2:
        return None
    fuzzy = []
    for root_text in PROJECT_DISCOVERY_ROOTS:
        root = Path(root_text)
        if not root.exists() or not root.is_dir():
            continue
        try:
            root_depth = len(root.parts)
            for current, dirs, files in os.walk(root):
                current_path = Path(current)
                depth = len(current_path.parts) - root_depth
                dirs[:] = [d for d in dirs if d not in PROJECT_DISCOVERY_IGNORES]
                if depth >= 4:
                    dirs[:] = []
                normalized = _normalized_project_name(current_path.name)
                if normalized == wanted:
                    return str(current_path)
                if wanted in normalized or normalized in wanted:
                    markers = {"pubspec.yaml","package.json","pyproject.toml","requirements.txt","Cargo.toml","CMakeLists.txt","jarvis.py"}
                    if ".git" in dirs or markers.intersection(files):
                        fuzzy.append(str(current_path))
        except Exception as exc:
            log(f"Project discovery skipped {root}: {exc}")
    return fuzzy[0] if fuzzy else None

def _extract_named_project(command):
    for pattern in (
        r"(?:project|repo|repository|codebase)\s+(?:called|named)\s+[\"']([^\"']+)[\"']",
        r"(?:project|repo|repository|codebase)\s+[\"']([^\"']+)[\"']",
    ):
        match = re.search(pattern, command, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    match = re.search(
        r"\b(?:project|repo|repository|codebase)\s+(?:called|named\s+)?([A-Za-z0-9_.-]{2,80})\b",
        command,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


# Coding actions that are allowed without a second confirmation.
# These are local source edits/tests only.
CODING_AUTO_ALLOWED = {
    "inspect",
    "read",
    "search",
    "edit",
    "create_file",
    "patch",
    "format",
    "lint",
    "analyze",
    "test",
    "build_debug",
}

# These remain confirmation-gated because they are external,
# destructive, or hard to reverse.
CODING_CONFIRM_REQUIRED = {
    "git_push",
    "force_push",
    "publish",
    "deploy",
    "production_release",
    "delete_repo",
    "delete_project",
    "rotate_credentials",
    "change_secrets",
    "store_credentials",
}


# ============================================================
# BACKGROUND MULTI-AGENT RUNTIME
# ============================================================

AGENT_MAX_CONCURRENT = 4
AGENT_RESULT_SPOKEN_LIMIT = 650

agent_jobs = {}
agent_jobs_lock = threading.RLock()
agent_slots = threading.Semaphore(AGENT_MAX_CONCURRENT)

# Prevent two background coding agents from editing the same project
# at the same time. Read-only inspections may still run concurrently.
agent_project_claims = {}
agent_next_number = 1

# Completed job IDs waiting to be surfaced by the future UI/dashboard.
agent_completion_queue = deque()

# Local Qwen has one llama-server slot. Project generation uses that slot in
# the background while Jarvis remains responsive through local commands and
# Hermes/other providers.
qwen_project_busy = threading.Event()

AGENT_JOB_FILE = os.path.join(
    JARVIS_DIR,
    "agent_jobs.json",
)


# ============================================================
# WHISPER
# ============================================================

WHISPER_MODEL = "small.en"

WHISPER_DEVICE = "cpu"

WHISPER_COMPUTE = "int8"


# ============================================================
# HERMES
# ============================================================

HERMES_BASE_URL = (
    "http://127.0.0.1:8642"
)

HERMES_MODELS_URL = (
    f"{HERMES_BASE_URL}/v1/models"
)

# Permanent Jarvis Hermes session.
HERMES_SESSION_ID = (
    "20260821_152105_39febf"
)

HERMES_SESSION_KEY = (
    "jarvis-primary"
)

HERMES_SESSION_URL = (
    f"{HERMES_BASE_URL}/api/sessions/"
    f"{HERMES_SESSION_ID}/chat"
)

HERMES_SESSION_INFO_URL = (
    f"{HERMES_BASE_URL}/api/sessions/"
    f"{HERMES_SESSION_ID}"
)

HERMES_TIMEOUT = 180


# ============================================================
# ELEVENLABS
# ============================================================

# Charlie
ELEVENLABS_VOICE_ID = (
    "IKne3meq5aSn9XLyUdCD"
)

ELEVENLABS_MODEL = (
    "eleven_flash_v2_5"
)

ELEVENLABS_OUTPUT_FORMAT = (
    "pcm_16000"
)

ELEVENLABS_SAMPLE_RATE = 16000

TTS_ENABLED = True

VOICE_SETTINGS_FILE = os.path.join(JARVIS_DIR, "voice_settings.json")
DEFAULT_VOICE_SETTINGS = {
    "provider": "kokoro",
    "kokoro_voice": "af_heart",
    "piper_voice": "en_US-lessac-medium",
    "elevenlabs_voice_id": ELEVENLABS_VOICE_ID,
    "fallback_order": ["kokoro", "piper", "elevenlabs"],
}

def _load_voice_settings():
    data = dict(DEFAULT_VOICE_SETTINGS)
    try:
        if os.path.exists(VOICE_SETTINGS_FILE):
            with open(VOICE_SETTINGS_FILE, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            if isinstance(saved, dict):
                data.update(saved)
    except Exception as exc:
        log(f"Voice settings load error: {exc}")
    return data

def _save_voice_settings(data):
    merged = dict(DEFAULT_VOICE_SETTINGS)
    if isinstance(data, dict):
        merged.update(data)
    try:
        tmp = VOICE_SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=2)
        os.replace(tmp, VOICE_SETTINGS_FILE)
    except Exception as exc:
        log(f"Voice settings save error: {exc}")
    return merged



# ============================================================
# ENVIRONMENT
# ============================================================

HERMES_ENV = os.path.expandvars(
    r"%LOCALAPPDATA%\hermes\.env"
)

load_dotenv(
    HERMES_ENV
)

ELEVENLABS_API_KEY = os.getenv(
    "ELEVENLABS_API_KEY"
)

HERMES_API_KEY = os.getenv(
    "API_SERVER_KEY"
)


if not HERMES_API_KEY:

    raise RuntimeError(
        "API_SERVER_KEY was not found "
        "in the Hermes .env file."
    )


if not ELEVENLABS_API_KEY:

    raise RuntimeError(
        "ELEVENLABS_API_KEY was not found "
        "in the Hermes .env file."
    )


# ============================================================
# JARVIS PERSONALITY
# ============================================================

# This is layered on top of Hermes's own system prompt.
# Hermes still keeps all of its normal tools, skills,
# memory and safety behavior.

JARVIS_INSTRUCTIONS = """
Your name is Jarvis.

You are the user's persistent personal AI assistant
running on their Windows computer.

This is a continuing relationship. Use your existing
Hermes session history and persistent memory when useful.

The user communicates with you primarily through voice.

Personality:
- intelligent
- calm
- composed
- confident
- concise
- capable
- professional
- natural

Behave like a capable computer assistant, not merely
a chatbot.

When the user asks you to perform an action and an
appropriate Hermes tool exists, use the tool rather
than simply telling the user how to do it.

C:\\Users\\gunsh\\Jarvis is your live local source of truth when working
on yourself. Never assume GitHub is newer than that folder unless the user
explicitly says so.

For software-development requests, you are allowed to directly inspect,
edit, create, patch, refactor, format, and test files in the user's local
projects using Hermes terminal, file, code-execution, and software-
development skills.

When the user asks you to "find bugs", "fix bugs", "debug this project",
"work on this project", "fix yourself", "repair Jarvis", or equivalent:

1. Resolve the intended project folder first.
2. Inspect the real files before proposing a root cause.
3. Reproduce or identify the failure when practical.
4. Make the smallest reasonable code changes that fix the issue.
5. Run appropriate validation afterward, such as py_compile, pytest,
   flutter analyze, dart test, npm test, build/lint commands, or other
   project-appropriate checks that are already available locally.
6. If a validation step fails, keep debugging rather than claiming success.
7. Report the files changed, what was fixed, tests run, and anything still
   unresolved.
8. Never claim a file was changed unless a tool actually changed it.
9. Never claim a test/build passed unless that command actually completed
   successfully.

You may make ordinary local source-code edits automatically when the user
asks you to fix code. This includes editing Jarvis itself. If you edit the
currently running Jarvis program, explain that the change takes effect on
the next restart and do not attempt to replace the running process unless
the user explicitly asks.

Do not deploy to production, publish releases, push or force-push commits,
delete repositories/projects, rotate credentials, modify secrets, make
purchases, or perform other irreversible or externally consequential
development actions without explicit confirmation.

Never claim that you created, changed, scheduled, sent, deleted, moved,
or otherwise modified something unless a tool actually performed that
action successfully in the current turn. If no write tool ran, say that
nothing was changed.

The Jarvis project is located at C:\\Users\\gunsh\\Jarvis. If the user says
"check Jarvis for bugs", "check this project for bugs", or similar while
talking through Jarvis, inspect that folder specifically instead of
searching the whole computer.

You may use your configured capabilities including:
- Windows computer control
- terminal commands
- file operations
- web search
- browser automation
- coding and code execution
- memory
- skills
- task planning
- project tools
- other enabled Hermes tools

Use persistent memory for stable facts, preferences,
workflows, recurring requirements, and details that
will be useful in future conversations.

Do not unnecessarily memorize temporary information.

Jarvis V42.46 also maintains a structured shared evidence store across the
primary assistant, project runs, and background workers. Treat its records as
supporting context with provenance, scope, revision, and validation status.
Current user instructions, current project files, Git state, and freshly run
validators always outrank remembered summaries.

When delegating work, give each worker a bounded goal, project path, file or
component scope, starting repository revision, allowed tools, acceptance
command, and required structured handoff. Do not let two editing workers own
the same project simultaneously. Integrate worker results only after checking
their recorded files, commands, and validation evidence.

Use configured MCP capabilities only after their availability is confirmed.
Grant workers the smallest capability set needed for their task. Never put
credentials into prompts, memory, logs, or generated projects, and obtain
confirmation before consequential external writes.

Self-improvement is a controlled software change: form a testable hypothesis,
create a reversible checkpoint, add regression evidence, edit a disposable or
recoverable candidate, run the complete current-release validation suite, and
promote only a passing result. Never treat a model's confidence as proof.

Keep ordinary spoken responses reasonably short.
Give more detail when the task requires it or when
the user asks for it.

When you complete an action, briefly report the result.

Do not read raw technical failures aloud. Never speak:
- API keys
- passwords
- access tokens
- raw HTTP errors
- stack traces
- JSON blobs
- internal diagnostic dumps

Summarize service failures naturally instead.

For destructive, irreversible, financial, credential,
security-sensitive, or externally consequential actions,
ask for confirmation when appropriate.
""".strip()


# ============================================================
# LOGGING
# ============================================================

def log(message):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    line = (
        f"[{timestamp}] {message}"
    )

    try:

        with open(
            LOG_FILE,
            "a",
            encoding="utf-8",
        ) as file:

            file.write(
                line + "\n"
            )

    except Exception as exc:
        print(f"Logging error: {exc}", file=sys.stderr)


# ============================================================
# STARTUP
# ============================================================

print()
print("=" * 68)
print("JARVIS INITIALIZING")
print("=" * 68)
print()

# V42 capability-first startup: scan developer tools in parallel with the
# voice stack so project generation begins with a warm host capability map.
_v42_runtime = None
try:
    import jarvis_v42_runtime as _v42_runtime
    _v42_runtime.start_background_startup_scan(Path(JARVIS_DIR))
    print("Developer capability scan: running in background.")
except Exception as _v42_startup_exc:
    print(f"Developer capability scan: deferred ({_v42_startup_exc}).")

print("Loading Whisper...")

whisper = WhisperModel(
    WHISPER_MODEL,
    device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE,
)

print("Whisper ready.")

print(
    "Loading wake-word engine..."
)

wake_model = WakeWordModel(
    wakeword_models=[
        WAKE_MODEL_NAME
    ],
    inference_framework="onnx",
)

print(
    "Wake-word engine ready."
)


# ============================================================
# AUDIO UTILITIES
# ============================================================

def rms(audio):

    if (
        audio is None
        or len(audio) == 0
    ):
        return 0.0

    audio_float = audio.astype(
        np.float32
    )

    return float(
        np.sqrt(
            np.mean(
                np.square(
                    audio_float
                )
            )
        )
    )


def write_temp_wav(audio):

    temp = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    )

    temp.close()

    try:
        with wave.open(
            temp.name,
            "wb",
        ) as wf:

            wf.setnchannels(
                CHANNELS
            )

            wf.setsampwidth(
                2
            )

            wf.setframerate(
                SAMPLE_RATE
            )

            wf.writeframes(
                audio.tobytes()
            )

        return temp.name

    except Exception as exc:
        log(f"write_temp_wav error: {exc}")
        if os.path.exists(temp.name):
            try:
                os.remove(temp.name)
            except Exception:
                pass
        return ""


# ============================================================
# MICROPHONE CALIBRATION
# ============================================================

def calibrate_microphone():

    global SPEECH_THRESHOLD
    global SILENCE_THRESHOLD

    if not AUTO_CALIBRATE_MIC:
        return

    print()
    print(
        "Calibrating microphone..."
    )

    print(
        "Please remain quiet for "
        f"{CALIBRATION_SECONDS:.1f} seconds."
    )

    samples = sd.rec(
        int(
            CALIBRATION_SECONDS
            * SAMPLE_RATE
        ),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
    )

    sd.wait()

    audio = (
        samples[:, 0]
        .astype(np.int16)
    )

    ambient = rms(
        audio
    )

    SILENCE_THRESHOLD = max(
        120,
        int(
            ambient * 1.8
        ),
    )

    SPEECH_THRESHOLD = max(
        250,
        int(
            ambient * 3.2
        ),
    )

    if (
        SPEECH_THRESHOLD
        <= SILENCE_THRESHOLD
    ):

        SPEECH_THRESHOLD = (
            SILENCE_THRESHOLD
            + 100
        )

    print(
        f"Ambient level: {ambient:.0f}"
    )

    print(
        "Speech threshold: "
        f"{SPEECH_THRESHOLD}"
    )

    print(
        "Silence threshold: "
        f"{SILENCE_THRESHOLD}"
    )


# ============================================================
# WHISPER
# ============================================================

def transcribe_audio(audio):

    if (
        audio is None
        or len(audio) == 0
    ):
        return ""

    path = write_temp_wav(
        audio
    )

    try:

        segments, info = (
            whisper.transcribe(
                path,
                language="en",
                vad_filter=True,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
                temperature=0.0,
            )
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

        return text

    finally:

        try:

            os.remove(
                path
            )

        except OSError:
            pass


# ============================================================
# TEXT CLEANUP
# ============================================================

def clean_transcription(text):

    if not text:
        return ""

    text = text.strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def remove_wake_phrase(text):

    if not text:
        return ""

    pattern = re.compile(
        r"^\s*"
        r"(?:hey[\s,]+)?"
        r"jarvis"
        r"[\s,.:;!?-]*",
        re.IGNORECASE,
    )

    cleaned = pattern.sub(
        "",
        text.strip(),
        count=1,
    )

    return cleaned.strip()


# ============================================================
# LOCAL FAST COMMANDS
# ============================================================



def handle_browser_command(text):
    command=clean_transcription(text).strip()
    lower=command.lower()

    m=re.match(r"^(?:research|research the web for|research the internet for|do research on|look up and research)\s+(.+)$",command,re.I)
    if m:
        query=m.group(1).strip()
        started, message = _start_research_agent(query)
        return True, message

    m=re.match(r"^(?:search (?:google|the web|the internet) for|google|look up)\s+(.+)$",command,re.I)
    if m:return True,desktop_automation.open_web(m.group(1).strip())[1]
    m=re.match(r"^(?:go to|navigate to|open website|open page)\s+(.+)$",command,re.I)
    if m:return True,desktop_automation.open_web(m.group(1).strip())[1]

    if lower in {"read this page","read the page","what does this page say","summarize this page","summarize the page"}:
        ok,page=desktop_automation.browser_read_page()
        if not ok:return True,page
        ok_url,url=desktop_automation.browser_current_url()
        return True,ask_hermes(
            "Summarize only the copied browser-page text below. "
            f"URL: {url if ok_url else 'unknown'}\n\nPAGE TEXT:\n{page}"
        )

    m=re.match(r"^(?:find|search for)\s+(.+?)\s+(?:on|in)\s+(?:this|the)\s+page$",command,re.I)
    if m:return True,desktop_automation.browser_find(m.group(1).strip())[1]
    m=re.match(r"^(?:scroll|page)\s+(down|up)(?:\s+(\d+))?$",lower,re.I)
    if m:return True,desktop_automation.browser_scroll(m.group(1),int(m.group(2) or 6))[1]
    m=re.match(r"^(?:click|click at)\s+(\d+)\s*[, ]\s*(\d+)$",lower,re.I)
    if m:return True,desktop_automation.mouse_click(int(m.group(1)),int(m.group(2)))[1]
    m=re.match(r"^(?:move mouse|move pointer|move cursor)\s+(?:to\s+)?(\d+)\s*[, ]\s*(\d+)$",lower,re.I)
    if m:return True,desktop_automation.mouse_move(int(m.group(1)),int(m.group(2)))[1]

    if lower in {"what page am i on","what is this url","current url","browser url"}:
        ok,v=desktop_automation.browser_current_url()
        return True,(f"The current page is {v}." if ok else v)
    if lower in {"new tab","open new tab","browser new tab"}:return True,desktop_automation.browser_new_tab()[1]
    if lower in {"close tab","close this tab","browser close tab"}:return True,desktop_automation.browser_close_tab()[1]
    if lower in {"next tab","switch tab","browser next tab"}:return True,desktop_automation.browser_next_tab()[1]
    if lower in {"previous tab","last tab","browser previous tab"}:return True,desktop_automation.browser_previous_tab()[1]
    if lower in {"go back","browser back","back page"}:return True,desktop_automation.browser_back()[1]
    if lower in {"go forward","browser forward","forward page"}:return True,desktop_automation.browser_forward()[1]
    if lower in {"zoom in","browser zoom in"}:return True,desktop_automation.browser_zoom("in")[1]
    if lower in {"zoom out","browser zoom out"}:return True,desktop_automation.browser_zoom("out")[1]
    if lower in {"reset zoom","normal zoom"}:return True,desktop_automation.browser_zoom("reset")[1]
    return False,None

def handle_pc_automation_command(text):
    command=clean_transcription(text).strip()
    lower=command.lower()
    m=re.match(r"^(?:open|launch|start|run)\s+(.+?)(?:\s+(?:for me|please))?$",command,re.I)
    if m:
        target=m.group(1).strip(" .")
        if target.lower() not in {"calendar","schedule","email","mail","inbox","agents","projects","controls","applications","apps","app launcher"}:
            ok,msg=desktop_automation.open_application(target)
            if ok:return True,msg
    m=re.match(r"^(?:switch to|focus|bring forward|activate)\s+(.+)$",command,re.I)
    if m:return True,desktop_automation.focus_window(m.group(1).strip())[1]
    m=re.match(r"^(?:type|enter|write)\s+[\"']?(.*?)[\"']?$",command,re.I|re.S)
    if m and m.group(1).strip():return True,desktop_automation.type_text(m.group(1).strip())[1]
    if lower in {"what windows are open","list open windows","show open windows"}:
        ok,v=desktop_automation.window_list()
        return True,("Open windows include: "+", ".join(v[:20]) if ok else v)
    shortcuts={"save":["ctrl","s"],"copy":["ctrl","c"],"paste":["ctrl","v"],"undo":["ctrl","z"],"redo":["ctrl","y"],
               "select all":["ctrl","a"],"new tab":["ctrl","t"],"close tab":["ctrl","w"],"refresh":["ctrl","r"],
               "task manager":["ctrl","shift","esc"]}
    for phrase,keys in shortcuts.items():
        if lower in {phrase,f"press {phrase}",f"do {phrase}"}:return True,desktop_automation.hotkey(keys)[1]
    if lower.startswith("press "):
        raw=lower[6:].replace("control","ctrl").strip()
        keys=[p for p in re.split(r"\s*\+\s*|\s+",raw) if p]
        return True,(desktop_automation.hotkey(keys)[1] if len(keys)>1 else desktop_automation.press_key(keys[0])[1])
    if lower in {"click","click here"}:return True,desktop_automation.mouse_click()[1]
    if lower in {"double click","double-click"}:return True,desktop_automation.mouse_click(clicks=2)[1]
    if lower in {"close this window","close active window","close the window"}:return True,desktop_automation.close_active_window()[1]
    return False,None

def handle_local_command(text):

    global TTS_ENABLED

    command = text.lower().strip()


    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if any(
        phrase in command
        for phrase in [
            "what time is it",
            "tell me the time",
            "current time",
        ]
    ):

        now = datetime.now().strftime(
            "%I:%M %p"
        )

        now = now.lstrip(
            "0"
        )

        return (
            True,
            f"It is {now}.",
        )


    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if any(
        phrase in command
        for phrase in [
            "what date is it",
            "what's the date",
            "what day is it",
            "today's date",
        ]
    ):

        today = datetime.now().strftime(
            "%A, %B %d, %Y"
        )

        today = today.replace(
            " 0",
            " ",
        )

        return (
            True,
            f"Today is {today}.",
        )


    # --------------------------------------------------------
    # MUTE
    # --------------------------------------------------------

    if command in [
        "mute",
        "mute yourself",
        "stop talking",
    ]:

        TTS_ENABLED = False

        return (
            True,
            "Voice output muted.",
        )


    # --------------------------------------------------------
    # UNMUTE
    # --------------------------------------------------------

    if command in [
        "unmute",
        "unmute yourself",
        "turn your voice back on",
    ]:

        TTS_ENABLED = True

        return (
            True,
            "Voice output restored.",
        )


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if command in [
        "jarvis status",
        "system status",
        "what is your status",
        "what's your status",
    ]:

        return (
            True,
            (
                "Primary systems are online. "
                "Wake word, speech recognition, "
                "persistent Hermes session, Gemini "
                "and voice output are available."
            ),
        )


    return (
        False,
        None,
    )


# ============================================================
# HERMES RESPONSE EXTRACTION
# ============================================================

def find_answer_in_json(data):
    """
    Hermes versions have changed response envelopes over time.
    This handles the common session-chat response formats.
    """

    if data is None:
        return ""


    if isinstance(
        data,
        str,
    ):

        return data.strip()


    if isinstance(
        data,
        list,
    ):

        candidates = []

        for item in data:

            text = find_answer_in_json(
                item
            )

            if text:
                candidates.append(
                    text
                )

        if candidates:
            return candidates[-1]

        return ""


    if not isinstance(
        data,
        dict,
    ):

        return ""


    # Most useful / likely Hermes fields first.
    preferred_keys = [
        "final_response",
        "response",
        "output_text",
        "answer",
        "text",
        "content",
    ]

    for key in preferred_keys:

        value = data.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value.strip():

            return value.strip()


    # OpenAI-like message wrapper.
    message = data.get(
        "message"
    )

    if isinstance(
        message,
        dict,
    ):

        content = message.get(
            "content"
        )

        if isinstance(
            content,
            str,
        ) and content.strip():

            return content.strip()


    # Search nested known structures.
    nested_keys = [
        "result",
        "data",
        "assistant",
        "output",
        "messages",
        "choices",
    ]

    for key in nested_keys:

        if key not in data:
            continue

        text = find_answer_in_json(
            data[key]
        )

        if text:
            return text


    return ""


# ============================================================
# HERMES ERROR FILTER
# ============================================================

def clean_hermes_answer(answer):

    if not answer:

        return (
            "I wasn't able to generate "
            "a response."
        )

    lower = answer.lower()

    error_markers = [
        "http 429",
        "resource_exhausted",
        "quota exceeded",
        "api call failed",
        "internal server error",
        "http 500",
        "http 502",
        "http 503",
        "traceback",
        "connection refused",
        "unauthorized",
    ]

    if any(
        marker in lower
        for marker in error_markers
    ):

        return (
            "I'm having trouble reaching "
            "one of my services right now. "
            "Please try again shortly."
        )

    return answer.strip()


# ============================================================
# PERSISTENT HERMES SESSION
# ============================================================

def ask_hermes(user_text):

    print()
    print(
        "Jarvis is thinking..."
    )

    started = time.perf_counter()

    _shared_memory_event(
        "conversation_user", {"text": str(user_text or "")},
        scope="personal", status="received", confidence=1.0,
    )
    recent_shared_context = _shared_memory_context(limit=8, max_chars=3200)

    headers = {
        "Authorization":
            f"Bearer {HERMES_API_KEY}",

        "Content-Type":
            "application/json",

        # Stable memory scope.
        "X-Hermes-Session-Key":
            HERMES_SESSION_KEY,
    }

    payload = {
        "input":
            user_text,

        "instructions":
            JARVIS_INSTRUCTIONS
            + "\n\nJARVIS V42.46 SHARED MEMORY CONTEXT:\n"
            + recent_shared_context
            + "\nTreat this as potentially stale supporting context. Current user instructions, files, and tool evidence remain authoritative.",
    }

    try:

        response = requests.post(
            HERMES_SESSION_URL,
            headers=headers,
            json=payload,
            timeout=HERMES_TIMEOUT,
        )

    except requests.Timeout:

        return (
            "The AI service is taking "
            "too long to respond."
        )

    except requests.RequestException as exc:

        log(
            f"Hermes connection error: {exc}"
        )

        return (
            "I'm having trouble connecting "
            "to the AI service."
        )


    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        "Hermes response: "
        f"{elapsed:.1f}s"
    )


    if response.status_code != 200:

        log(
            "Hermes HTTP error: "
            f"{response.status_code} "
            f"{response.text[:500]}"
        )

        return (
            "I encountered a service problem "
            "while processing that request."
        )


    try:

        data = response.json()

    except Exception:

        log(
            "Hermes returned non-JSON: "
            + response.text[:500]
        )

        return (
            "I received an invalid response "
            "from the AI service."
        )


    answer = find_answer_in_json(
        data
    )


    if not answer:

        log(
            "Could not extract Hermes answer: "
            + str(data)[:1000]
        )

        return (
            "I completed the request, but "
            "couldn't read the final response."
        )


    cleaned = clean_hermes_answer(answer)
    _shared_memory_event(
        "conversation_assistant", {"text": cleaned},
        scope="personal", status="completed", confidence=1.0,
    )
    return cleaned


# ============================================================
# BACKGROUND HERMES AGENTS
# ============================================================

def _save_agent_jobs():

    try:
        with agent_jobs_lock:
            serializable = {}

            for job_id, job in agent_jobs.items():
                serializable[str(job_id)] = {
                    key: value
                    for key, value in job.items()
                    if key not in {"thread"}
                }

            # Keep snapshot, write and replacement under the same lock. Worker
            # progress and HTTP commands can save concurrently; an older
            # snapshot must not overwrite a newer state or steal its temp file.
            temp_path = AGENT_JOB_FILE + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(serializable, file, indent=2, default=str)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, AGENT_JOB_FILE)
        return True

    except Exception as exc:
        log(
            f"Agent job persistence error: {exc}"
        )
        return False


def _mark_interrupted_agent(job, reason):
    """Retain results and workspace/ZIP paths while retiring a dead worker."""
    job['previous_status'] = job.get('status')
    job['status'] = 'interrupted'
    job['stage'] = 'interrupted'
    job['activity'] = reason
    job['interruption_reason'] = reason
    job['finished_at'] = datetime.now().isoformat(timespec='seconds')
    if not job.get('result'):
        job['result'] = reason


def _reconcile_project_jobs():
    """Only actual Python worker threads can own this process's project slot."""
    changed = False
    with agent_jobs_lock:
        for job in agent_jobs.values():
            if job.get('job_type') != 'qwen_project':
                continue
            worker = job.get('thread')
            if worker is not None and worker.is_alive():
                continue
            if job.get('status') in {'queued', 'running', 'stopping'}:
                _mark_interrupted_agent(job, 'The previous project worker is no longer running. Saved project files and ZIPs are retained; a new repair can start.')
                changed = True
        if changed:
            _save_agent_jobs()


def _agent_jobs_snapshot():
    _reconcile_project_jobs()
    with agent_jobs_lock:
        return [{key: value for key, value in job.items() if key != 'thread'}
                for _, job in sorted(agent_jobs.items())]


def _load_agent_jobs():

    global agent_next_number

    if not os.path.exists(AGENT_JOB_FILE):
        return

    try:
        with open(
            AGENT_JOB_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            saved = json.load(file)

        with agent_jobs_lock:
            for key, job in saved.items():
                if not isinstance(job, dict):
                    continue
                try:
                    job_id = int(key)
                except Exception:
                    continue

                # A Python worker cannot survive a Jarvis restart.
                if job.get("status") in {
                    "queued",
                    "running",
                    "stopping",
                }:
                    _mark_interrupted_agent(job, 'This background task was interrupted when Jarvis restarted. Saved project files and ZIPs are retained.')

                job.pop('thread', None)
                job.setdefault('id', job_id)
                agent_jobs[job_id] = job

            if agent_jobs:
                agent_next_number = (
                    max(agent_jobs.keys()) + 1
                )
            # Publish the repaired startup state before the dashboard can read
            # an obsolete "running" or "saving checkpoint" record from disk.
            _save_agent_jobs()

    except Exception as exc:
        log(
            f"Agent job load error: {exc}"
        )


def _ask_hermes_background(
    user_text,
    session_key,
):

    headers = {
        "Authorization":
            f"Bearer {HERMES_API_KEY}",
        "Content-Type":
            "application/json",
        "X-Hermes-Session-Key":
            session_key,
    }

    background_instructions = (
        JARVIS_INSTRUCTIONS
        + "\n\n"
        + """
You are operating as one background Jarvis worker.

Focus exclusively on the assigned job. Do not ask the user conversational
follow-up questions unless the task truly cannot proceed without missing
information. Use real tools and files when the task requires them.

For coding work:
- inspect the real project before editing;
- make targeted local edits only when authorized;
- run appropriate validation after edits;
- never deploy, publish, push, delete a repository/project, or change
  credentials/secrets;
- clearly report files changed and validation results.

Your result will be stored for the primary Jarvis assistant to report later.
Do not attempt to speak through the microphone or control the main Jarvis
conversation loop.
""".strip()
    )

    payload = {
        "input": user_text,
        "instructions": background_instructions,
    }

    try:
        response = requests.post(
            HERMES_SESSION_URL,
            headers=headers,
            json=payload,
            timeout=HERMES_TIMEOUT,
        )

    except requests.Timeout:
        return (
            False,
            "The background AI task timed out."
        )

    except requests.RequestException as exc:
        log(
            f"Background Hermes connection error: {exc}"
        )
        return (
            False,
            "The background agent could not reach the AI service."
        )

    if response.status_code != 200:
        log(
            "Background Hermes HTTP error: "
            f"{response.status_code} "
            f"{response.text[:500]}"
        )
        return (
            False,
            "The background agent encountered an AI service error."
        )

    try:
        data = response.json()
    except Exception:
        log(
            "Background Hermes returned non-JSON: "
            + response.text[:500]
        )
        return (
            False,
            "The background agent returned an invalid response."
        )

    answer = find_answer_in_json(
        data
    )

    if not answer:
        return (
            False,
            "The background agent finished, but no result could be read."
        )

    return (
        True,
        clean_hermes_answer(answer),
    )


def _extract_agent_test_report(result):
    """Keep a durable test/validation digest beside the unabridged agent result."""
    text = str(result or "").strip()
    report_lines = []
    keywords = (
        "test", "validation", "validated", "pytest", "py_compile",
        "compile", "lint", "returncode", "passed", "failed",
    )
    for line in text.splitlines():
        clean = line.strip()
        if clean and any(keyword in clean.lower() for keyword in keywords):
            report_lines.append(clean)
    if report_lines:
        return "\n".join(report_lines)
    return "The agent reported success but did not provide a separate test-report section. See full_result."


def _short_agent_change_confirmation(result):
    """Create a short, speakable description without discarding the full report."""
    text = re.sub(r"[`#*_]+", " ", str(result or ""))
    candidates = [re.sub(r"\s+", " ", line).strip(" -:\t") for line in text.splitlines()]
    candidates = [line for line in candidates if len(line) >= 12]
    preferred = next(
        (
            line for line in candidates
            if any(term in line.lower() for term in ("changed", "fixed", "implemented", "updated", "added"))
            and not any(term in line.lower() for term in ("test", "validation", "workspace"))
        ),
        "",
    )
    summary = preferred or (candidates[0] if candidates else "The requested coding change is complete")
    return summary[:280].rstrip(" .,;")


def _background_project_scope(task):

    if not _looks_like_coding_request(task):
        return (
            task,
            None,
            True,
        )

    project_path, project_name = (
        _resolve_project_from_command(
            task
        )
    )

    if project_path is None:
        lower = task.lower()

        if any(
            phrase in lower
            for phrase in (
                "jarvis",
                "yourself",
                "your code",
                "your project",
                "this project",
                "the ui",
                " ui ",
                "dashboard",
                "command center",
                "panel",
                "panels",
                "widget",
                "widgets",
                "sidebar",
                "hud",
            )
        ):
            project_path = (
                PROJECT_ALIASES["jarvis"]
            )
            project_name = "Jarvis"
        else:
            return (
                None,
                None,
                None,
            )

    read_only = _coding_request_is_read_only(
        task
    )

    if read_only:
        mode = (
            "READ-ONLY MODE. Inspect and validate only. "
            "Do not edit, create, overwrite, rename, move, "
            "or delete project files."
        )
    else:
        mode = (
            "EDIT MODE. Local source-code edits are authorized for "
            "this task. Inspect first, make the smallest reasonable "
            "fix, and run appropriate validation afterward."
        )

    scoped = (
        f"Work on this project: {project_path}. "
        f"{mode} "
        f"User task: {task}. "
        "Do not deploy, publish, push commits, delete the project, "
        "or modify credentials/secrets. "
        "Report root cause, files changed, validation commands and "
        "results, and anything unresolved."
    )

    return (
        scoped,
        project_path,
        read_only,
    )


def _agent_worker(job_id):

    with agent_slots:

        with agent_jobs_lock:
            job = agent_jobs.get(job_id)

            if not job:
                return

            if job.get("status") == "cancelled":
                return

            job["status"] = "running"
            job["activity"] = "Agent started."
            job["started_at"] = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )

            task = job["task"]
            user_task = job.get("user_task") or task
            session_key = job["session_key"]
            project_path = job.get("project_path") or ""

        _save_agent_jobs()

        requested_provider, provider_task = extract_provider_request(user_task)
        provider_coding_request = _looks_like_coding_request(provider_task)
        shared_contract = worker_context_contract(user_task, project_path, job_id)
        provider_task = str(provider_task or "") + shared_contract
        hermes_task = str(task or "") + shared_contract
        _shared_memory_event(
            "worker_started",
            {"task": user_task, "provider": requested_provider or "gemini", "read_only": bool(job.get("read_only", False))},
            scope="worker", project=project_path, worker_id=job_id,
            run_id=session_key, status="running", confidence=1.0,
        )

        if requested_provider in {"openai", "claude", "nvidia", "qwen"}:
            if project_path and provider_coding_request:
                def _agent_progress(update):
                    with agent_jobs_lock:
                        current=agent_jobs.get(job_id)
                        if current:
                            current["activity"]=update.get("message","")
                            current["tool"]=update.get("tool","")
                            current["turn"]=update.get("turn",0)
                            current["max_turns"]=update.get("max_turns",0)
                            current["workspace"]=update.get("workspace",project_path)
                    _save_agent_jobs()

                success, result = run_provider_coding_agent(
                    requested_provider, provider_task, project_path,
                    read_only=bool(job.get("read_only",False)),
                    progress_callback=_agent_progress,
                )
                # If a paid provider is unavailable/quota exhausted, automatically
                # fall back to NVIDIA's free NIM endpoint when configured. Never
                # discard the original failure; record the fallback in activity.
                quota_markers=("insufficient_quota","credit_balance_exhausted","no credits","429")
                if (not success and requested_provider in {"openai","claude"}
                        and any(m in str(result).lower() for m in quota_markers)
                        and provider_status().get("nvidia")):
                    _agent_progress({"message":f"{requested_provider} quota unavailable; falling back to NVIDIA NIM.","tool":"provider_fallback","turn":0,"max_turns":0,"workspace":project_path})
                    success, fallback_result = run_provider_coding_agent(
                        "nvidia", provider_task, project_path,
                        read_only=bool(job.get("read_only",False)),
                        progress_callback=_agent_progress,
                    )
                    result=("Paid-provider fallback activated. "+str(fallback_result)) if success else (str(result)+"\nNVIDIA fallback also failed: "+str(fallback_result))
            else:
                success, result = ask_provider(
                    requested_provider,
                    provider_task,
                    JARVIS_INSTRUCTIONS,
                )
        else:
            success, result = _ask_hermes_background(
                provider_task if requested_provider == "gemini" else hermes_task,
                session_key,
            )

        with agent_jobs_lock:
            job = agent_jobs.get(job_id)

            if not job:
                return

            if job.get("status") == "cancelled":
                return

            job["status"] = (
                "completed"
                if success
                else "failed"
            )
            # Keep the complete provider response and a separate validation digest.
            # Both fields are persisted before any restart handoff can begin.
            job["result"] = result
            job["full_result"] = str(result or "")
            job["test_report"] = _extract_agent_test_report(result)
            job["activity"] = "Completed successfully." if success else "Failed — review agent result."
            job["finished_at"] = (
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )
            job["completion_saved_at"] = datetime.now().isoformat(timespec="milliseconds")

            if not (success and job.get("restart_after_success")):
                agent_completion_queue.append(
                    job_id
                )

            project_path = job.get(
                "project_path"
            )

            if (
                project_path
                and not job.get("read_only", True)
                and agent_project_claims.get(project_path) == job_id
            ):
                agent_project_claims.pop(
                    project_path,
                    None,
                )

        completion_persisted = _save_agent_jobs()

        _shared_memory_event(
            "worker_completed" if success else "worker_failed",
            {
                "task": user_task,
                "result": str(result or ""),
                "test_report": _extract_agent_test_report(result),
                "completion_persisted": bool(completion_persisted),
            },
            scope="worker", project=project_path, worker_id=job_id,
            run_id=session_key, status="completed" if success else "failed",
            confidence=1.0 if success else 0.8,
        )

        print()
        print(
            f"[Background Agent {job_id} "
            f"{'completed' if success else 'failed'}]"
        )
        print()


        # Composite edit+restart jobs must complete even while audio capture is blocked.
        # Never begin the shutdown path until the complete report is safely on disk.
        with agent_jobs_lock:
            finished_job = dict(agent_jobs.get(job_id) or {})
        if success and finished_job.get("restart_after_success") and completion_persisted:
            restart_thread = threading.Thread(
                target=_complete_authorized_edit_restart,
                args=(job_id,),
                daemon=False,
                name=f"JarvisPostEditRestart-{job_id}",
            )
            restart_thread.start()


def _complete_authorized_edit_restart(job_id):
    """Persist, report, speak, then hand restart control to an external process."""
    with agent_jobs_lock:
        job = dict(agent_jobs.get(job_id) or {})

    if job.get("status") != "completed":
        log(f"Agent {job_id}: auto-restart skipped because status={job.get('status')}")
        return
    if not job.get("restart_after_success"):
        log(f"Agent {job_id}: auto-restart skipped because authorization is missing.")
        return

    full_result = str(job.get("full_result") or job.get("result") or "").strip()
    test_report = str(job.get("test_report") or _extract_agent_test_report(full_result)).strip()
    changed = _short_agent_change_confirmation(full_result)
    completed_message = (
        f"Agent {job_id} completed the requested edit successfully. "
        f"What changed: {changed}. Validation passed. "
        "The full result and test report are saved in Agent Activity."
    )

    # Stage 1: durably store every report field and the handoff audit trail.
    with agent_jobs_lock:
        live = agent_jobs.get(job_id)
        if not live:
            return
        live["result"] = full_result
        live["full_result"] = full_result
        live["test_report"] = test_report
        live["restart_handoff_started"] = True
        live["restart_handoff_stage"] = "completion_saved"
        live["restart_handoff_at"] = datetime.now().isoformat(timespec="milliseconds")
    if not _save_agent_jobs():
        failure = f"Agent {job_id} completed, but its full report could not be saved. Restart cancelled."
        log(failure)
        update_live_state("STANDBY", last_answer=failure, active_command="")
        return

    # Stage 2: publish the completed result while the old dashboard is still alive.
    dashboard_saved = update_live_state(
        "COMPLETED",
        last_answer=completed_message,
        active_command="",
        agent_completion={
            "id": job_id,
            "status": "completed",
            "full_result": full_result,
            "test_report": test_report,
            "reported_at": datetime.now().isoformat(timespec="milliseconds"),
        },
    )
    if not dashboard_saved:
        failure = f"Agent {job_id} completed, but the dashboard result could not be updated. Restart cancelled."
        log(failure)
        return

    print(f"\nJarvis: {completed_message}\n")
    log(f"JARVIS: {completed_message}")

    # Stage 3: finish the short spoken confirmation before shutdown begins.
    spoken = f"Agent {job_id} finished. Here is what changed: {changed}. Tests passed. Restarting all systems now."
    try:
        speak_text(_spoken_version(spoken))
    except Exception as exc:
        # Speech is best effort, but it is deliberately attempted before launch.
        log(f"Restart acknowledgement speech failed: {exc}")

    with agent_jobs_lock:
        live = agent_jobs.get(job_id)
        if live:
            live["restart_handoff_stage"] = "supervisor_launching"
    if not _save_agent_jobs():
        failure = f"Agent {job_id} report metadata could not be finalized. Restart cancelled."
        log(failure)
        update_live_state("STANDBY", last_answer=failure, active_command="")
        return

    update_live_state("RESTARTING", last_answer=completed_message, active_command="")

    # Stage 4: only now launch the detached supervisor. It owns teardown/relaunch.
    ok, restart_message = _schedule_jarvis_stack_restart()
    if not ok:
        log(f"Authorized post-edit restart failed to launch: {restart_message}")
        update_live_state("STANDBY", last_answer=restart_message, active_command="")




def _research_worker(job_id):
    with agent_slots:
        with agent_jobs_lock:
            job = agent_jobs.get(job_id)
            if not job:
                return
            job["status"] = "running"
            job["activity"] = "Searching the web."
            job["started_at"] = datetime.now().isoformat(timespec="seconds")
            query = job.get("research_query") or job.get("user_task") or ""
            session_key = job.get("session_key")
            job["error"] = ""
        _save_agent_jobs()

        success = False
        result = ""
        failure_detail = ""
        usable_sources = []

        try:
            data = web_research.research(query, max_sources=5)
            for source in data.get("sources") or []:
                source_text = str(source.get("text") or "").strip()
                if source_text and not source_text.startswith("[Could not read page:"):
                    usable_sources.append(source)
        except Exception as exc:
            failure_detail = f"Local web retrieval error: {exc}"
            log(f"Research Agent {job_id}: {failure_detail}")

        if usable_sources:
            with agent_jobs_lock:
                current = agent_jobs.get(job_id)
                if current:
                    current["activity"] = f"Reading {len(usable_sources)} web sources."
                    current["tool"] = "web_research"
            _save_agent_jobs()

            blocks = []
            for i, source in enumerate(usable_sources, 1):
                blocks.append(
                    f"SOURCE {i}\nTitle: {source.get('title','')}\n"
                    f"URL: {source.get('url','')}\nTEXT:\n"
                    f"{str(source.get('text') or '')[:9000]}"
                )
            prompt = (
                "Complete this CURRENT web research request using only the supplied "
                "retrieved source text. Give a concise useful synthesis, distinguish "
                "facts from uncertainty, and include source URLs.\n"
                f"QUESTION: {query}\n\n" + "\n\n".join(blocks)
            )
            success, result = _ask_hermes_background(prompt, session_key)
            if not success:
                failure_detail = result

        if not success:
            with agent_jobs_lock:
                current = agent_jobs.get(job_id)
                if current:
                    current["activity"] = "Using Hermes web search tools."
                    current["tool"] = "hermes_web_search"
            _save_agent_jobs()

            native_prompt = (
                "Research the following request using your Web Search & Scraping tools. "
                "You MUST actually search current public web sources; do not answer only "
                "from memory. Return a short synthesis with the most important current "
                "developments and source names/URLs. If a web tool fails, explain the "
                "specific failure rather than inventing results.\n\n"
                f"RESEARCH REQUEST: {query}"
            )
            success, native_result = _ask_hermes_background(native_prompt, session_key)
            if success:
                result = native_result
            else:
                failure_detail = native_result or failure_detail or "No usable web sources were returned."
                result = f"Research failed: {failure_detail}"

        with agent_jobs_lock:
            job = agent_jobs.get(job_id)
            if not job:
                return
            job["status"] = "completed" if success else "failed"
            job["result"] = result
            job["error"] = "" if success else failure_detail
            job["activity"] = "Research completed." if success else "Research failed."
            job["finished_at"] = datetime.now().isoformat(timespec="seconds")
            agent_completion_queue.append(job_id)
        _save_agent_jobs()
        print(f"\n[Background Research Agent {job_id} {'completed' if success else 'failed'}]\n")


def _start_research_agent(query):
    global agent_next_number
    query=clean_transcription(query).strip()
    if not query:return False,"Tell me what you want researched."
    with agent_jobs_lock:
        job_id=agent_next_number; agent_next_number+=1
        session_key=f"{HERMES_SESSION_KEY}-research-{job_id}-{uuid.uuid4().hex[:8]}"
        job={
            "id":job_id,"task":f"Research the web: {query}","user_task":query,
            "provider":"gemini","job_type":"research","research_query":query,
            "status":"queued","activity":"Waiting for a research slot.","tool":"",
            "turn":0,"max_turns":0,"result":"",
            "created_at":datetime.now().isoformat(timespec="seconds"),
            "started_at":"","finished_at":"","session_key":session_key,
            "project_path":"","read_only":True,
        }
        agent_jobs[job_id]=job
        thread=threading.Thread(target=_research_worker,args=(job_id,),daemon=True,name=f"JarvisResearch-{job_id}")
        job["thread"]=thread; thread.start()
    _save_agent_jobs()
    return True,f"Research Agent {job_id} is working on that in the background. You can keep talking to me."



_JARVIS_ATTACHMENT_RE = re.compile(
    r'\[JARVIS_ATTACHED_FILE\]\s+(?P<path>"[^"]+"|.*?)(?=\s+\[JARVIS_[A-Z0-9_]+\]|$)',
    flags=re.IGNORECASE | re.DOTALL,
)
_JARVIS_PROFILE_RE = re.compile(
    r'\[JARVIS_QWEN_PROFILE\]\s+(?P<profile>[A-Za-z0-9_.-]+)',
    flags=re.IGNORECASE,
)


def _inline_qwen_profile_marker(command):
    """Extract dashboard Qwen profile metadata even when it shares a line with user text."""
    text = str(command or '')
    matches = list(_JARVIS_PROFILE_RE.finditer(text))
    profile = matches[-1].group('profile').strip() if matches else ''
    clean = _JARVIS_PROFILE_RE.sub(' ', text)
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r' *\n *', '\n', clean).strip()
    return clean, profile


def _attached_file_markers(command):
    """Return (clean_command, attached_paths) from dashboard metadata anywhere in the command.

    Older dashboard code emitted markers on their own line. Newer UI paths can append the marker
    to the user's sentence, e.g. ``finish this project [JARVIS_ATTACHED_FILE] C:\\x.zip``.
    Treat the marker as transport metadata, never as project requirements.
    """
    text = str(command or '')
    paths = []
    for match in _JARVIS_ATTACHMENT_RE.finditer(text):
        raw = str(match.group('path') or '').strip().strip('"').strip()
        if raw:
            paths.append(raw)
    clean = _JARVIS_ATTACHMENT_RE.sub(' ', text)
    clean = re.sub(r'[ \t]+', ' ', clean)
    clean = re.sub(r' *\n *', '\n', clean).strip()
    return clean, paths


def _normalize_attached_project_instruction(command):
    """Remove UI/provider routing prose while keeping the actual project edit instruction."""
    text = str(command or '').strip()
    # Dashboard/provider phrasing such as "use qwen to finish this project" is routing metadata,
    # not a requirement that the generated application itself use Qwen.
    text = re.sub(
        r'^\s*(?:please\s+)?(?:use|ask)\s+(?:local\s+)?qwen(?:\s*(?:3(?:\.5|\.8)?|8b|9b|9b35|27b|27b38q2|38q2|q2_k_p))?\s+to\s+',
        '', text, count=1, flags=re.IGNORECASE,
    )
    text = re.sub(r'\s+', ' ', text).strip()
    return text or 'finish this project'


def _first_attached_zip(command):
    """Return (clean_command, existing_zip, zip_marker_seen).

    zip_marker_seen lets routing fail closed: if the dashboard supplied a ZIP marker but the file
    cannot be resolved, Jarvis must NOT reinterpret the same sentence as a brand-new project.
    """
    clean, paths = _attached_file_markers(command)
    zip_paths = [raw for raw in paths if str(raw).strip().strip('"').lower().endswith('.zip')]
    for raw in zip_paths:
        try:
            p = Path(str(raw).strip().strip('"')).expanduser().resolve()
            if p.exists() and p.is_file() and p.suffix.lower() == '.zip':
                return _normalize_attached_project_instruction(clean), p, True
        except Exception:
            continue
    return _normalize_attached_project_instruction(clean), None, bool(zip_paths)


def _qwen_project_worker(job_id):
    """Generate a downloadable Qwen project without blocking Jarvis conversation."""
    ok = False
    detail = "Project worker exited before producing a result."
    zip_path = None
    result = ""
    stopped_by_user = False
    automatic_exhausted = False
    try:
        with agent_jobs_lock:
            job = agent_jobs.get(job_id)
            if not job:
                return
            job["status"] = "running"
            job["started_at"] = datetime.now().isoformat(timespec="seconds")
            job["activity"] = "Qwen is planning the project."
        _save_agent_jobs()
        qwen_project_busy.set()

        def _progress(message):
            info = message if isinstance(message, dict) else {"message": str(message)}
            with agent_jobs_lock:
                live = agent_jobs.get(job_id)
                if live:
                    live["activity"] = str(info.get("message") or "Qwen is working…")
                    live["tool"] = "local_qwen_project"
                    for key in ("stage", "percent", "current", "total", "generated_tokens_estimate", "elapsed_seconds", "streaming", "model_profile", "model_role"):
                        if key in info:
                            live[key] = info[key]
                    if info.get("model_profile"):
                        mode = normalize_profile(live.get("qwen_profile") or "auto")
                        if mode == "auto":
                            live["provider"] = f"qwen-auto:{info.get('model_profile')}"
                        else:
                            live["provider"] = f"qwen-{mode}"
            _save_agent_jobs()
            try:
                record_project_heartbeat(info)
            except Exception:
                pass

        with agent_jobs_lock:
            live_job = agent_jobs.get(job_id) or {}
            request = str(live_job.get("user_task") or "")
            source_zip = str(live_job.get("source_zip") or "").strip()
            qwen_profile = str(live_job.get("qwen_profile") or "auto")

        begin_project_run(job_id, request, source_zip)

        try:
            switch_ok, switch_detail = prepare_project_qwen_routing(
                qwen_profile,
                progress_callback=lambda message: _progress(message if isinstance(message, dict) else {"message": str(message), "stage": "model_switch", "percent": 1}),
            )
            if not switch_ok:
                raise RuntimeError(switch_detail)
            ready_model = active_profile()
            _progress({"message": switch_detail, "stage": "model_ready", "percent": 2,
                       "model_profile": ready_model,
                       "model_role": ("locked" if normalize_profile(qwen_profile) != "auto" else
                                      "specialist" if ready_model == "27b38q2" else "worker")})

            if source_zip:
                ok, detail, zip_path = analyze_and_edit_project_zip(
                    request,
                    source_zip,
                    max_audit_passes=0,
                    progress_callback=_progress,
                )
            else:
                ok, detail, zip_path = generate_project_zip(
                    request,
                    max_files=DEFAULT_MAX_FILES,
                    max_audit_passes=0,
                    progress_callback=_progress,
                )
        except AutomaticRepairExhausted as exc:
            automatic_exhausted = True
            ok, detail, zip_path = checkpoint_stopped_project(job_id, str(exc))
        except ProjectStopRequested as exc:
            stopped_by_user = True
            ok, detail, zip_path = checkpoint_stopped_project(job_id, str(exc))

        checkpoint_ready = bool(zip_path and not ok and "CHECKPOINT" in str(detail or "").upper())
        if zip_path:
            if ok:
                result = (
                    f"Your Qwen project is ready. {detail} "
                    f"ZIP_FILE: {zip_path}\n"
                    f"DOWNLOAD_URL: /downloads/{zip_path.name}"
                )
            elif checkpoint_ready:
                result = (
                    f"Qwen saved a resumable project checkpoint. {detail} "
                    f"ZIP_FILE: {zip_path}\n"
                    f"DOWNLOAD_URL: /downloads/{zip_path.name}"
                )
            else:
                result = (
                    f"Qwen returned a project ZIP with verification warnings. {detail} "
                    f"ZIP_FILE: {zip_path}\n"
                    f"DOWNLOAD_URL: /downloads/{zip_path.name}"
                )
        else:
            result = f"Qwen could not produce a project ZIP. {detail}"

        with agent_jobs_lock:
            live = agent_jobs.get(job_id)
            if not live:
                return
            live["status"] = "completed" if ok else ("stopped" if (stopped_by_user or automatic_exhausted) else "failed")
            live["automatic_checkpoint"] = bool(automatic_exhausted)
            live["result"] = result
            live["error"] = "" if ok else str(detail)
            if ok:
                live["activity"] = "Project ZIP ready."
            elif automatic_exhausted and checkpoint_ready:
                live["activity"] = "Repair budget exhausted; resumable checkpoint ZIP saved automatically."
            elif automatic_exhausted:
                live["activity"] = "Repair budget exhausted before a checkpointable workspace existed."
            elif stopped_by_user and checkpoint_ready:
                live["activity"] = "Stopped safely; resumable checkpoint ZIP ready."
            elif stopped_by_user:
                live["activity"] = "Stopped safely before a checkpointable workspace existed."
            elif checkpoint_ready:
                live["activity"] = "Resumable checkpoint ZIP ready."
            elif zip_path:
                live["activity"] = "Project ZIP ready with verification warnings."
            else:
                live["activity"] = "Project build did not produce a ZIP."
            if zip_path:
                live["stage"] = "complete" if ok else ("checkpoint" if checkpoint_ready else "complete_with_warnings")
                live["percent"] = 100
            live["finished_at"] = datetime.now().isoformat(timespec="seconds")
            if zip_path:
                live["zip_path"] = str(zip_path)
                live["download_url"] = f"/downloads/{zip_path.name}"
            agent_completion_queue.append(job_id)
        _save_agent_jobs()
        _shared_memory_event(
            "project_completed" if ok else ("project_automatic_checkpoint" if automatic_exhausted else "project_stopped" if stopped_by_user else "project_failed"),
            {"detail": str(detail or ""), "zip_path": str(zip_path or ""), "checkpoint_ready": checkpoint_ready},
            scope="run", run_id=job_id,
            status="completed" if ok else "checkpoint" if checkpoint_ready else "failed",
            confidence=1.0,
        )
        print(f"\n[Qwen Project Agent {job_id} {'completed' if ok else 'failed'}]\n")
    except Exception as exc:
        with agent_jobs_lock:
            live = agent_jobs.get(job_id)
            if live:
                live["status"] = "failed"
                live["result"] = f"Qwen project generation failed: {exc}"
                live["error"] = str(exc)
                live["activity"] = "Project generation failed."
                live["finished_at"] = datetime.now().isoformat(timespec="seconds")
                agent_completion_queue.append(job_id)
        _save_agent_jobs()
        log(f"Qwen project worker error: {exc}")
    finally:
        try:
            finish_project_run(job_id, {
                "ok": bool(ok),
                "detail": str(detail or "")[-12000:],
                "zip_path": str(zip_path or ""),
                "stopped_by_user": bool(stopped_by_user),
                "automatic_exhausted": bool(automatic_exhausted),
            })
        except Exception:
            pass
        try:
            clear_project_qwen_routing()
        except Exception:
            pass
        qwen_project_busy.clear()


def _start_qwen_project_job(command, source_zip=None, qwen_profile="auto"):
    global agent_next_number

    with agent_jobs_lock:
        _reconcile_project_jobs()
        for job in agent_jobs.values():
            worker = job.get('thread')
            # Even after a result is published the worker may still be closing
            # its run/model. Keep the slot until that thread actually exits.
            if job.get("job_type") == "qwen_project" and worker is not None and worker.is_alive():
                phase = ('saving its checkpoint' if job.get('status') == 'stopping' else
                         'running' if job.get('status') in {'queued', 'running'} else 'finishing cleanup')
                return False, (
                    f"Qwen Project Agent {job.get('id')} is still {phase}. "
                    + ("Your attached ZIP is retained. Send it again when that job finishes."
                       if source_zip else "Send the next project request when that job finishes.")
                )

        job_id = agent_next_number
        agent_next_number += 1
        job = {
            "id": job_id,
            "task": command,
            "user_task": command,
            "provider": ("qwen-auto-hybrid" if normalize_profile(qwen_profile) == "auto" else f"qwen-{normalize_profile(qwen_profile)}"),
            "qwen_profile": str(qwen_profile or "auto"),
            "job_type": "qwen_project",
            "status": "queued",
            "activity": "Waiting to start local Qwen project generation.",
            "tool": "local_qwen_project",
            "turn": 0,
            "max_turns": 0,
            "result": "",
            "error": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "started_at": "",
            "finished_at": "",
            "session_key": "",
            "project_path": "",
            "read_only": False,
            "stage": "queued",
            "percent": 0,
            "current": 0,
            "total": 0,
            "generated_tokens_estimate": 0,
            "source_zip": str(source_zip or ""),
        }
        agent_jobs[job_id] = job
        thread = threading.Thread(
            target=_qwen_project_worker,
            args=(job_id,),
            daemon=True,
            name=f"JarvisQwenProject-{job_id}",
        )
        job["thread"] = thread
        try:
            thread.start()
        except Exception as exc:
            job.update(status='failed', stage='failed', error=str(exc),
                       activity='The project worker could not start.',
                       finished_at=datetime.now().isoformat(timespec='seconds'))
            _save_agent_jobs()
            return False, f'The project worker could not start: {exc}. Your request and attached ZIP can be retried.'

    _save_agent_jobs()
    return True, (
        f"Qwen Project Agent {job_id} is building that in the background. "
        "You can keep talking to me or start another agent."
    )


def _start_background_agent(task, safety_text=None, restart_after_success=False):

    global agent_next_number

    scoped_task, project_path, read_only = (
        _background_project_scope(
            task
        )
    )

    if scoped_task is None:
        return (
            False,
            (
                "Tell me which project that agent should work on. "
                "You can say Jarvis, DailyBread, Scan2Cookz, "
                "or give me the project folder path."
            ),
        )

    # IMPORTANT: safety classification must inspect the user's original
    # request, not Jarvis-generated guardrail text appended to the agent prompt.
    # Otherwise phrases such as "Never force-push" inside our own instructions
    # falsely look like a request to force-push and block ordinary UI edits.
    safety_subject = task if safety_text is None else safety_text
    if _coding_request_needs_confirmation(safety_subject):
        return (
            False,
            (
                "That background task includes a destructive or sensitive "
                "action such as a force-push, project deletion, or credential "
                "change. I won't run those actions unattended."
            ),
        )

    with agent_jobs_lock:

        if (
            project_path
            and not read_only
            and project_path in agent_project_claims
        ):
            other_id = agent_project_claims[
                project_path
            ]

            return (
                False,
                (
                    f"Agent {other_id} is already editing that project. "
                    "I won't let two agents modify the same project at once."
                ),
            )

        job_id = agent_next_number
        agent_next_number += 1

        session_key = (
            f"{HERMES_SESSION_KEY}-agent-"
            f"{job_id}-{uuid.uuid4().hex[:8]}"
        )

        requested_provider, _provider_task = extract_provider_request(task)

        job = {
            "id": job_id,
            "task": scoped_task,
            "user_task": task,
            "provider": requested_provider or "gemini",
             "status": "queued",
            "activity": "Waiting for an agent slot.",
            "tool": "",
            "turn": 0,
            "max_turns": 0,
            "result": "",
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "started_at": "",
            "finished_at": "",
            "session_key": session_key,
            "project_path": project_path or "",
            "read_only": bool(read_only),
            # Set before the worker thread starts. This avoids a race where a fast
            # coding agent can finish before the caller marks the job for restart.
            "restart_after_success": bool(restart_after_success),
            "restart_authorized_at": (
                datetime.now().isoformat(timespec="seconds")
                if restart_after_success else ""
            ),
        }

        agent_jobs[job_id] = job

        if (
            project_path
            and not read_only
        ):
            agent_project_claims[
                project_path
            ] = job_id

        thread = threading.Thread(
            target=_agent_worker,
            args=(job_id,),
            daemon=True,
            name=f"JarvisAgent-{job_id}",
        )

        job["thread"] = thread

        thread.start()

    _save_agent_jobs()
    _shared_memory_event(
        "worker_queued",
        {"task": task, "provider": requested_provider or "gemini", "read_only": bool(read_only)},
        scope="worker", project=project_path, worker_id=job_id,
        run_id=session_key, status="queued", confidence=1.0,
    )

    return (
        True,
        (
            f"Agent {job_id} is working on that in the background. "
            "You can keep talking to me or start another agent."
        ),
    )


def _agent_status_text():

    with agent_jobs_lock:
        jobs = [
            dict(job)
            for _, job in sorted(
                agent_jobs.items()
            )
        ]

    if not jobs:
        return (
            "You don't have any background agents yet."
        )

    active = [
        job
        for job in jobs
        if job.get("status") in {
            "queued",
            "running",
        }
    ]

    recent = jobs[-5:]

    pieces = []

    for job in recent:
        user_task = (
            job.get("user_task")
            or job.get("task", "")
        )

        if len(user_task) > 90:
            user_task = (
                user_task[:87] + "..."
            )

        status=job.get("status","unknown")
        if status in {"queued","running"}:
            activity=job.get("activity") or ("Waiting for an agent slot." if status=="queued" else "Working.")
            turn=job.get("turn") or 0
            max_turns=job.get("max_turns") or 0
            tool=job.get("tool") or ""
            detail=f"Agent {job['id']} is {status}. {activity}"
            if tool:
                detail+=f" Current tool: {tool}."
            if turn:
                detail+=f" Turn {turn} of {max_turns or '?'}."
            pieces.append(detail)
        else:
            pieces.append(
                f"Agent {job['id']} is {status}: {user_task}"
            )

    prefix = (
        f"{len(active)} background agent"
        f"{'s are' if len(active) != 1 else ' is'} active. "
    )

    return (
        prefix
        + " ".join(pieces)
    )


def _all_agent_results_text():

    with agent_jobs_lock:
        jobs = [
            dict(job)
            for _, job in sorted(
                agent_jobs.items()
            )
        ]

    if not jobs:
        return (
            "You don't have any background agent results yet."
        )

    completed = [
        job
        for job in jobs
        if job.get("status") in {
            "completed",
            "failed",
            "interrupted",
        }
    ]

    if not completed:
        return (
            "Your background agents are still working. "
            "Ask me for agent status to see their progress."
        )

    # Prefer the most recent five finished agents so spoken output
    # stays useful instead of becoming a huge historical dump.
    completed = completed[-5:]

    pieces = []

    for job in completed:

        job_id = job.get(
            "id",
            "?"
        )

        status = job.get(
            "status",
            "unknown",
        )

        result = (
            job.get("result")
            or "No result was returned."
        )

        # Keep each spoken result concise. Full output remains persisted
        # in agent_jobs.json for the future dashboard.
        if len(result) > 900:
            result = (
                result[:900].rstrip()
                + " ..."
            )

        pieces.append(
            f"Agent {job_id} is {status}. {result}"
        )

    return (
        "Here are the stored results from your recent background agents. "
        + " ".join(pieces)
    )


def _agent_result_text(job_id):

    with agent_jobs_lock:
        job = agent_jobs.get(job_id)

        if not job:
            return (
                f"I don't have an agent {job_id}."
            )

        status = job.get(
            "status",
            "unknown",
        )

        result = job.get(
            "result",
            "",
        )

    if status in {"queued", "running"}:
        activity = job.get("activity") or ("Waiting for an agent slot." if status == "queued" else "Working.")
        tool = job.get("tool") or ""
        turn = job.get("turn") or 0
        max_turns = job.get("max_turns") or 0
        detail = f" Current activity: {activity}"
        if tool:
            detail += f" Tool: {tool}."
        if turn:
            detail += f" Tool turn {turn} of {max_turns or '?'}."
        return f"Agent {job_id} is {status}.{detail}"

    if status == "failed":
        error = str(job.get("error") or "").strip()
        detail = error or result or "The agent did not record a specific failure reason."
        if len(detail) > AGENT_RESULT_SPOKEN_LIMIT:
            detail = detail[:AGENT_RESULT_SPOKEN_LIMIT].rstrip() + " ..."
        return f"Agent {job_id} failed. The recorded reason is: {detail}"

    if not result:
        return (
            f"Agent {job_id} is {status}, but it did not return a result."
        )

    if len(result) > AGENT_RESULT_SPOKEN_LIMIT:
        short = result[:AGENT_RESULT_SPOKEN_LIMIT].rstrip()
        return (
            f"Agent {job_id} is {status}. "
            f"Here is the short summary: {short} ... "
            "The full report is available in the Agent Activity panel."
        )

    return (
        f"Agent {job_id} is {status}. "
        f"Here is the result from that background job: {result}"
    )


def _spoken_agent_id(text):

    lower = clean_transcription(
        text
    ).lower()

    digit_match = re.search(
        r"\b(?:agent|task)\s*(\d+)\b",
        lower,
    )

    if digit_match:
        return int(
            digit_match.group(1)
        )

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    word_match = re.search(
        r"\b(?:agent|task)\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten)\b",
        lower,
    )

    if word_match:
        return number_words[
            word_match.group(1)
        ]

    return None


def _latest_self_improvement_job():
    with agent_jobs_lock:
        matches = [dict(job) for job in agent_jobs.values() if job.get("self_improvement")]
    return matches[-1] if matches else None


def handle_self_improvement_command(text):
    command = clean_transcription(text).strip()
    lower = command.lower()

    status_question = (
        ("improv" in lower or "self" in lower)
        and any(q in lower for q in ("did you finish", "are you finished", "have you finished", "what are you doing", "how is it going", "status"))
    )
    if status_question:
        job = _latest_self_improvement_job()
        if not job:
            return True, "I haven't started a self-improvement job yet."
        return True, _agent_result_text(job.get("id"))

    phrases = ("improve yourself", "make yourself better", "upgrade yourself", "work on yourself",
               "improve jarvis", "optimize yourself", "self improve", "self-improve")
    if not any(p in lower for p in phrases):
        return False, None

    task = (
        f"using OpenAI work on project {SELF_WORKSPACE}. This exact local folder is Jarvis's live source of truth. "
        "Do not pull/reset from GitHub to replace it. Treat current files and current Git state as authoritative, not old conversation history. "
        "First call workspace_info, inspect Git status, then inspect the current implementation relevant to the improvement. "
        "Choose ONE high-confidence improvement that materially improves reliability, responsiveness, understanding, tooling, self-maintenance, or UX. "
        "Before editing, record a falsifiable failure or improvement hypothesis and create a reversible checkpoint. Add or update a regression test that proves the intended behavior. "
        "Make the smallest safe local change. Preserve unrelated working-tree changes and existing behavior. Use file backups before edits. "
        "Run targeted validation plus the complete current-release validation suite. Promote the change only when those validators pass; otherwise restore the checkpoint. "
        "Inspect the final Git diff and clearly report exact files changed, tests, evidence, rollback point, and remaining risk. "
        "Do not modify secrets, provider keys, credentials, ai_providers.env, or .git internals. Do not deploy, publish, commit, push, force-reset, or delete user work. "
        "If a safe improvement cannot be proven, make no change and explain why. User request: " + command
    )
    started, message = _start_background_agent(task)
    if started:
        with agent_jobs_lock:
            newest = max(agent_jobs) if agent_jobs else None
            if newest and newest in agent_jobs:
                agent_jobs[newest]["self_improvement"] = True
        _save_agent_jobs()
    return True, message


def _latest_failed_agent():
    with agent_jobs_lock:
        failed = [
            dict(job) for _, job in sorted(agent_jobs.items())
            if job.get("status") == "failed"
        ]
    return failed[-1] if failed else None


def handle_background_agent_command(text):

    command = clean_transcription(
        text
    ).strip()

    lower = command.lower()

    generic_failure_followup = any(phrase in lower for phrase in (
        "why did it fail", "why it fail", "why did that fail",
        "why did the agent fail", "why did my agent fail",
        "what failed", "what went wrong with the agent",
    ))
    if generic_failure_followup:
        failed = _latest_failed_agent()
        if not failed:
            return True, "I don't have a failed background agent to explain."
        return True, _agent_result_text(int(failed.get("id")))

    requested_failure_agent = _spoken_agent_id(command)
    if requested_failure_agent is not None and "fail" in lower:
        return True, _agent_result_text(requested_failure_agent)

    status_phrases = (
        "agent status",
        "agents status",
        "background task status",
        "background tasks",
        "what are my agents doing",
        "what are the agents doing",
        "how are my agents doing",
        "what is my agent doing",
        "what's my agent doing",
        "what are agents doing right now",
        "what is agent doing right now",
        "what are agents working on",
        "what are my agents working on",
    )

    if any(
        phrase in lower
        for phrase in status_phrases
    ):
        return (
            True,
            _agent_status_text(),
        )


    plural_result_phrases = (
        "what did my agents find",
        "what did the agents find",
        "what have my agents found",
        "what have the agents found",
        "what did my agents do",
        "what did the agents do",
        "agent results",
        "agents results",
        "results from my agents",
        "results from the agents",
        "tell me what my agents found",
        "tell me what the agents found",
    )

    if any(
        phrase in lower
        for phrase in plural_result_phrases
    ):
        return (
            True,
            _all_agent_results_text(),
        )

    agent_result_query = bool(re.search(
        r"\b(?:what|show|tell|give|read|report|summarize|summarise)\b"
        r".{0,80}\b(?:agents?|background agents?)\b"
        r".{0,80}\b(?:results?|found|find|did|done|report|reported)\b"
        r"|\b(?:agents?|background agents?)\b.{0,40}\b(?:results?|status)\b",
        lower, flags=re.IGNORECASE,
    ))
    if agent_result_query:
        return True, _all_agent_results_text()

    requested_agent_id = (
        _spoken_agent_id(
            command
        )
    )

    if (
        requested_agent_id is not None
        and any(
            phrase in lower
            for phrase in (
                "result",
                "results",
                "what did",
                "what found",
                "what happened",
                "finished",
                "done",
                "status",
                "tell me about",
                "find",
                "found",
            )
        )
    ):
        return (
            True,
            _agent_result_text(
                requested_agent_id
            ),
        )

    if (
        requested_agent_id is not None
        and (
            "agent" in lower
            or "task" in lower
        )
    ):
        return (
            True,
            _agent_result_text(
                requested_agent_id
            ),
        )

    start_patterns = (
        r"^(?:deploy|deploying|start|starting|launch|launching|send|sending)\s+(?:(?:an|a|another)\s+)?agent\s+(?:to\s+)?(.+)$",
        r"^(?:have|having|tell|telling)\s+(?:(?:an|a|another)\s+)?agent\s+(?:to\s+)?(.+)$",
        r"^(?:put|putting|run|running)\s+(.+?)\s+in\s+the\s+background$",
    )

    for pattern in start_patterns:

        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        task = match.group(1).strip(
            " ,."
        )

        if not task:
            return (
                True,
                "Tell me what you want the background agent to do.",
            )

        started, message = (
            _start_background_agent(
                task
            )
        )

        return (
            True,
            message,
        )

    return False, None


_load_agent_jobs()


def _schedule_jarvis_stack_restart():
    """Launch a tiny detached Python bootstrapper and require its handshake."""
    global _HARD_RESTART_REQUESTED

    with _HARD_RESTART_REQUEST_LOCK:
        if _HARD_RESTART_REQUESTED:
            return True, "A full Jarvis restart is already in progress."
        _HARD_RESTART_REQUESTED=True

    bootstrap=os.path.join(JARVIS_DIR,"restart_supervisor.py")
    status_file=os.path.join(JARVIS_DIR,"restart_status.json")
    request_id=uuid.uuid4().hex

    if not os.path.exists(bootstrap):
        with _HARD_RESTART_REQUEST_LOCK:
            _HARD_RESTART_REQUESTED=False
        return False,f"The restart bootstrap is missing: {bootstrap}"

    try:
        flags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"DETACHED_PROCESS",0)
        proc=subprocess.Popen(
            [sys.executable,bootstrap,"--old-pid",str(os.getpid()),"--request-id",request_id],
            cwd=JARVIS_DIR,creationflags=flags,close_fds=True,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        log(f"Restart bootstrap launched pid={proc.pid} request={request_id}")

        deadline=time.time()+8.0; ready=False; last_stage=""
        while time.time()<deadline:
            if proc.poll() is not None:
                break
            try:
                with open(status_file,"r",encoding="utf-8-sig") as f:
                    st=json.load(f)
                if str(st.get("request_id") or "")==request_id:
                    last_stage=str(st.get("stage") or "")
                    if last_stage=="supervisor-ready":
                        ready=True; break
                    if last_stage=="failure": break
            except Exception: pass
            time.sleep(.10)

        if not ready:
            try:
                if proc.poll() is None: proc.terminate()
            except Exception: pass
            with _HARD_RESTART_REQUEST_LOCK:
                _HARD_RESTART_REQUESTED=False
            msg=("The restart bootstrap did not confirm it was alive, so shutdown was cancelled. "
                 f"Last stage: {last_stage or 'no handshake'}.")
            log(msg); return False,msg

        return True,("The external restart supervisor is confirmed online. It will close the Jarvis UI, "
                     "stop the dashboard, voice engine, Hermes and related services, verify the old URL "
                     "is offline, then launch and verify a fresh stack and reopen the Command Center.")
    except Exception as exc:
        with _HARD_RESTART_REQUEST_LOCK:
            _HARD_RESTART_REQUESTED=False
        log(f"Restart bootstrap error: {exc}")
        return False,f"I couldn't start the restart supervisor: {exc}"



def _announce_agent_completion_if_needed():
    global pending_action

    if not agent_completion_queue:
        return False

    try:
        job_id = agent_completion_queue.popleft()
    except IndexError:
        return False

    with agent_jobs_lock:
        job = dict(agent_jobs.get(job_id) or {})

    if not job:
        return False

    status = job.get("status", "unknown")
    auto_restart = bool(job.get("restart_after_success"))

    if job.get("job_type") == "research":
        if status == "completed":
            result = str(job.get("result") or "").strip()
            summary = result[:900].rstrip() + (" ..." if len(result) > 900 else "")
            message = f"Research Agent {job_id} finished. {summary}"
        else:
            reason = str(job.get("error") or job.get("result") or "No specific error was recorded.").strip()
            if len(reason) > 700:
                reason = reason[:700].rstrip() + " ..."
            message = f"Research Agent {job_id} failed. Reason: {reason}"
    elif job.get("self_improvement"):
        if status == "completed":
            result = str(job.get("result") or "").strip()
            summary = result[:700].rstrip() + (" ..." if len(result) > 700 else "")

            if auto_restart:
                message = (
                    f"Agent {job_id} finished the self-improvement successfully. "
                    + (f"Here is what it changed: {summary} " if summary else "")
                    + "Validation passed. You already authorized the restart, "
                      "so I am shutting down and restarting all systems now."
                )
            else:
                message = (
                    f"Agent {job_id} finished improving me successfully. "
                    + (f"Here is what it did: {summary} " if summary else "")
                    + "The changes are ready in my live local Jarvis folder. "
                      "Would you like me to restart my voice engine, dashboard "
                      "services, and Hermes now so we can test them?"
                )
                pending_action = {"type": "restart_jarvis_stack", "agent_id": job_id}
        else:
            message = (
                f"Agent {job_id} finished the self-improvement job with status "
                f"{status}. I will not restart because the job did not complete "
                "successfully. Check Agent Activity for the details."
            )
    elif auto_restart:
        if status == "completed":
            result = str(job.get("result") or "").strip()
            summary = result[:700].rstrip() + (" ..." if len(result) > 700 else "")
            message = (
                f"Agent {job_id} completed the requested edit successfully. "
                + (f"Here is what it changed: {summary} " if summary else "")
                + "Validation passed. You already authorized a full restart, "
                  "so I am restarting all systems now."
            )
        else:
            message = (
                f"Agent {job_id} finished with status {status}. "
                "I am not restarting because the edit did not validate successfully."
            )
    elif job.get("job_type") == "qwen_project":
        result = str(job.get("result") or "").strip()
        if status == "completed":
            message = result or f"Qwen Project Agent {job_id} finished and the ZIP is ready."
            spoken_message = f"Qwen Project Agent {job_id} finished. Your verified project ZIP is ready in chat."
        else:
            message = result or f"Qwen Project Agent {job_id} did not finish a verified ZIP."
            spoken_message = f"Qwen Project Agent {job_id} finished, but the project did not pass verification. Check chat for details."
    else:
        message = (
            f"Agent {job_id} is {status}. "
            f"You can ask me what Agent {job_id} did for the full result."
        )

    print(f"\nJarvis: {message}\n")
    log(f"JARVIS: {message}")
    update_live_state("SPEAKING", last_answer=message, active_command="")

    if job.get("job_type") == "qwen_project":
        def _speak_qwen_project_done():
            try:
                speak_text(_spoken_version(spoken_message))
            except Exception as exc:
                log(f"Qwen project completion speech error: {exc}")
            finally:
                update_live_state("LISTENING" if FOLLOW_UP_MODE else "STANDBY", active_command="")
        threading.Thread(
            target=_speak_qwen_project_done,
            daemon=True,
            name=f"JarvisQwenProjectDone-{job_id}",
        ).start()
    else:
        speak_elevenlabs(_spoken_version(message))

    # Only restart after the completion message has actually been delivered.
    if auto_restart and status == "completed":
        success, restart_message = _schedule_jarvis_stack_restart()
        if not success:
            log(f"Authorized post-edit restart failed to launch: {restart_message}")

    return True


# ============================================================
# ELEVENLABS STREAMING TTS
# ============================================================

def _resolve_tts_output_device():
    """Return a usable sounddevice output device and log what Jarvis selected."""
    try:
        devices=sd.query_devices()
        default_out=None
        try:
            default_pair=sd.default.device
            if isinstance(default_pair,(list,tuple)) and len(default_pair)>1:
                default_out=int(default_pair[1])
        except Exception:
            default_out=None

        if default_out is not None and default_out>=0:
            info=devices[default_out]
            if int(info.get("max_output_channels",0))>0:
                log(f"TTS output device: {default_out} {info.get('name','unknown')}")
                return default_out

        for idx,info in enumerate(devices):
            if int(info.get("max_output_channels",0))>0:
                log(f"TTS fallback output device: {idx} {info.get('name','unknown')}")
                return idx
    except Exception as exc:
        log(f"TTS output-device discovery failed: {exc}")
    return None



def _play_wav_file(path):
    try:
        import wave
        with wave.open(path, "rb") as wf:
            channels = wf.getnchannels()
            samplerate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
        if sampwidth != 2:
            raise RuntimeError(f"Unsupported WAV sample width: {sampwidth}")
        data = np.frombuffer(frames, dtype=np.int16)
        if channels > 1:
            data = data.reshape(-1, channels)
        device = _resolve_tts_output_device()
        sd.play(data, samplerate=samplerate, device=device, blocking=True)
        return True
    except Exception as exc:
        log(f"WAV playback error: {exc}")
        return False


def _kokoro_available():
    try:
        import kokoro_onnx
        return True
    except Exception:
        return False


def _piper_available():
    return shutil.which("piper") is not None


def _kokoro_voice_candidates():
    return [
        "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica",
        "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah",
        "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir",
        "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
        "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
        "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    ]


def _piper_voice_candidates():
    return [
        "en_US-lessac-medium",
        "en_US-amy-medium",
        "en_US-ryan-high",
        "en_US-hfc_female-medium",
        "en_US-hfc_male-medium",
        "en_GB-alba-medium",
        "en_GB-jenny_dioco-medium",
    ]


def _kokoro_model_paths():
    base=os.path.join(JARVIS_DIR,"tools","kokoro")
    return os.path.join(base,"kokoro-v1.0.onnx"),os.path.join(base,"voices-v1.0.bin")

def _run_kokoro_tts(text, voice=None):
    voice=voice or str(_load_voice_settings().get("kokoro_voice") or "af_heart")
    try:
        from kokoro_onnx import Kokoro
    except Exception as exc:
        return False,f"Kokoro ONNX runtime unavailable: {exc}"
    model_path,voices_path=_kokoro_model_paths()
    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        return False,"Kokoro model files are missing. Run SETUP_LOCAL_TTS.bat."
    try:
        engine=Kokoro(model_path,voices_path)
        samples,sample_rate=engine.create(text,voice=voice,speed=1.0,lang="en-us")
        device=_resolve_tts_output_device()
        sd.play(np.asarray(samples,dtype=np.float32),samplerate=int(sample_rate),device=device,blocking=True)
        return True,f"Kokoro ONNX playback completed with {voice}."
    except Exception as exc:
        return False,f"Kokoro ONNX failed: {exc}"


def _run_piper_tts(text, voice=None):
    voice = voice or str(_load_voice_settings().get("piper_voice") or "en_US-lessac-medium")
    exe = shutil.which("piper")
    if not exe:
        return False, "Piper CLI not installed."
    voices_dir = os.path.join(JARVIS_DIR, "tools", "piper_voices")
    model = os.path.join(voices_dir, voice + ".onnx")
    config = model + ".json"
    if not os.path.exists(model):
        return False, f"Piper voice model not installed: {voice}"
    temp = os.path.join(tempfile.gettempdir(), f"jarvis_piper_{uuid.uuid4().hex}.wav")
    cmd = [exe, "--model", model, "--output_file", temp]
    if os.path.exists(config):
        cmd += ["--config", config]
    try:
        result = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=120)
        if result.returncode != 0:
            return False, f"Piper failed: {(result.stderr or result.stdout or '')[:300]}"
        if not os.path.exists(temp):
            return False, "Piper did not create audio."
        ok = _play_wav_file(temp)
        try:
            os.remove(temp)
        except Exception:
            pass
        return ok, "Piper playback completed." if ok else "Piper generated audio but playback failed."
    except Exception as exc:
        return False, f"Piper error: {exc}"


def get_voice_provider_status():
    settings = _load_voice_settings()
    return {
        "settings": settings,
        "providers": {
            "kokoro": {"configured": _kokoro_available(), "voices": _kokoro_voice_candidates()},
            "piper": {"configured": _piper_available(), "voices": _piper_voice_candidates()},
            "elevenlabs": {
                "configured": bool(ELEVENLABS_API_KEY),
                "voices": [{"id": settings.get("elevenlabs_voice_id", ELEVENLABS_VOICE_ID), "name": "Current ElevenLabs voice"}],
            },
        },
    }


def speak_text(text, provider=None):
    """Speak text and always return the dashboard to a non-speaking state.

    ElevenLabs already performs its own state cleanup, while local Kokoro/Piper
    playback previously did not.  Keeping the cleanup here prevents the HUD
    from remaining stuck on SPEAKING after local/project completion messages.
    """
    if not text or not TTS_ENABLED:
        update_live_state("LISTENING" if FOLLOW_UP_MODE else "STANDBY")
        return False

    settings = _load_voice_settings()
    requested = str(provider or settings.get("provider") or "kokoro").lower()
    order = [requested]
    for candidate in settings.get("fallback_order", ["kokoro", "piper", "elevenlabs"]):
        candidate = str(candidate).lower()
        if candidate not in order:
            order.append(candidate)

    succeeded = False
    used_provider = None
    try:
        for candidate in order:
            used_provider = candidate
            if candidate == "kokoro":
                ok, detail = _run_kokoro_tts(text, settings.get("kokoro_voice"))
            elif candidate == "piper":
                ok, detail = _run_piper_tts(text, settings.get("piper_voice"))
            elif candidate == "elevenlabs":
                try:
                    speak_elevenlabs(text)
                    ok, detail = True, "ElevenLabs request completed."
                except Exception as exc:
                    ok, detail = False, f"ElevenLabs error: {exc}"
            else:
                continue
            log(f"TTS provider {candidate}: {detail}")
            if ok:
                succeeded = True
                break
        return succeeded
    finally:
        # Harmless if ElevenLabs already reset the state; essential for local TTS.
        update_live_state("LISTENING" if FOLLOW_UP_MODE else "STANDBY")


def preview_voice(provider, voice, phrase="Hello, sir. Jarvis voice preview online."):
    provider = str(provider or "").lower()
    if provider == "kokoro":
        return _run_kokoro_tts(phrase, voice)
    if provider == "piper":
        return _run_piper_tts(phrase, voice)
    if provider == "elevenlabs":
        try:
            speak_elevenlabs(phrase)
            return True, "ElevenLabs preview completed."
        except Exception as exc:
            return False, f"ElevenLabs preview failed: {exc}"
    return False, "Unknown voice provider."


def speak_elevenlabs(text):
    global speech_was_interrupted
    global active_speech_cancel_event

    speech_was_interrupted = False

    if not TTS_ENABLED or not text:
        return

    # The process-command lock should already serialize foreground speech,
    # but this second lock guarantees that no direct caller can create a
    # second ElevenLabs stream on top of the first.
    with tts_playback_lock:
        cancel_event = threading.Event()

        with speech_cancel_lock:
            # Cancel anything older before registering this stream.
            previous = active_speech_cancel_event
            if previous is not None and previous is not cancel_event:
                previous.set()
            active_speech_cancel_event = cancel_event

        print("Jarvis is speaking...")
        update_live_state("SPEAKING", last_answer=text)

        started = time.perf_counter()

        url = (
            "https://api.elevenlabs.io/v1/"
            f"text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
        )

        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        }

        params = {"output_format": ELEVENLABS_OUTPUT_FORMAT}

        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": 1.0,
            },
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=120,
                stream=True,
            )
        except requests.RequestException as exc:
            log(f"TTS connection error: {exc}")
            with speech_cancel_lock:
                if active_speech_cancel_event is cancel_event:
                    active_speech_cancel_event = None
            return

        if response.status_code != 200:
            log(f"ElevenLabs HTTP error: {response.status_code} {response.text[:300] if hasattr(response, 'text') else ''}")
            with speech_cancel_lock:
                if active_speech_cancel_event is cancel_event:
                    active_speech_cancel_event = None
            return

        first_audio = True
        leftover = b""
        monitor_stop = threading.Event()

        def monitor_for_barge_in():
            try:
                loud_blocks = 0
                monitor_started = time.time()

                with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    blocksize=WAKE_BLOCK_SIZE,
                ) as interrupt_stream:

                    while not monitor_stop.is_set() and not cancel_event.is_set():
                        data, overflowed = interrupt_stream.read(WAKE_BLOCK_SIZE)
                        audio = data[:, 0].copy().astype(np.int16)

                        prediction = wake_model.predict(audio)
                        score = float(prediction.get(WAKE_MODEL_NAME, 0.0))

                        if score >= WAKE_THRESHOLD:
                            cancel_event.set()
                            wake_model.reset()
                            return

                        if time.time() - monitor_started >= BARGE_IN_GRACE_SECONDS:
                            level = rms(audio)

                            if level >= BARGE_IN_RMS_THRESHOLD:
                                loud_blocks += 1
                            else:
                                loud_blocks = max(0, loud_blocks - 1)

                            if loud_blocks >= BARGE_IN_CONSECUTIVE_BLOCKS:
                                cancel_event.set()
                                return

            except Exception as exc:
                log(f"Barge-in monitor unavailable: {exc}")

        monitor_thread = threading.Thread(
            target=monitor_for_barge_in,
            daemon=True,
            name="JarvisBargeIn",
        )
        monitor_started=False

        tts_device=_resolve_tts_output_device()
        try:
            with sd.RawOutputStream(
                samplerate=ELEVENLABS_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=0,
                device=tts_device,
            ) as output:

                for chunk in response.iter_content(chunk_size=4096):
                    if cancel_event.is_set():
                        speech_was_interrupted = True
                        print("Speech interrupted.")
                        break

                    if not chunk:
                        continue

                    if first_audio:
                        latency = time.perf_counter() - started
                        print(f"Voice latency: {latency:.2f}s")
                        log(f"TTS first PCM audio received; latency={latency:.2f}s bytes={len(chunk)} device={tts_device}")
                        first_audio = False

                    chunk = leftover + chunk

                    if len(chunk) % 2 != 0:
                        leftover = chunk[-1:]
                        chunk = chunk[:-1]
                    else:
                        leftover = b""

                    if chunk and not cancel_event.is_set():
                        output.write(chunk)
                        if not monitor_started:
                            monitor_thread.start()
                            monitor_started=True

        except Exception as exc:
            log(f"TTS playback error: {exc}")

        finally:
            if first_audio:
                log("TTS ended without receiving any playable PCM audio.")
            cancel_event.set()
            monitor_stop.set()

            try:
                response.close()
            except Exception:
                pass

            if monitor_started:
                try:
                    monitor_thread.join(timeout=0.5)
                except Exception:
                    pass

            with speech_cancel_lock:
                if active_speech_cancel_event is cancel_event:
                    active_speech_cancel_event = None

            wake_model.reset()
            update_live_state("LISTENING" if FOLLOW_UP_MODE else "STANDBY")




# ============================================================
# WAKE WORD
# ============================================================

def wait_for_wake_word(
    stream,
):

    pre_roll = deque(
        maxlen=
            WAKE_PREROLL_BLOCKS
    )


    while True:

        if _announce_agent_completion_if_needed():
            wake_model.reset()

        data, overflowed = stream.read(
            WAKE_BLOCK_SIZE
        )

        audio = (
            data[:, 0]
            .copy()
            .astype(np.int16)
        )

        pre_roll.append(
            audio
        )


        prediction = (
            wake_model.predict(
                audio
            )
        )


        score = float(
            prediction.get(
                WAKE_MODEL_NAME,
                0.0,
            )
        )


        if score >= WAKE_THRESHOLD:

            print()
            print(
                "Wake word detected "
                f"({score:.2f})"
            )
            _write_voice_health("wake_detected", f"score={score:.2f}")

            wake_model.reset()


            return np.concatenate(
                list(
                    pre_roll
                )
            )


# ============================================================
# CAPTURE AFTER WAKE
# ============================================================

def capture_after_wake(
    stream,
    initial_audio,
):

    chunks = [
        initial_audio
    ]

    silence_started = None

    capture_started = time.time()


    while True:

        data, overflowed = stream.read(
            COMMAND_BLOCK_SIZE
        )

        audio = (
            data[:, 0]
            .copy()
            .astype(np.int16)
        )

        chunks.append(
            audio
        )


        level = rms(
            audio
        )


        if (
            level
            <= SILENCE_THRESHOLD
        ):

            if silence_started is None:

                silence_started = (
                    time.time()
                )

            elif (
                time.time()
                - silence_started
                >= END_SILENCE_SECONDS
            ):

                break

        else:

            silence_started = None


        if (
            time.time()
            - capture_started
            >= MAX_COMMAND_SECONDS
        ):

            break


    combined = np.concatenate(
        chunks
    )


    print(
        "Transcribing..."
    )
    update_live_state("TRANSCRIBING")


    text = clean_transcription(
        transcribe_audio(
            combined
        )
    )


    return remove_wake_phrase(
        text
    )


# ============================================================
# FOLLOW-UP CAPTURE
# ============================================================

def capture_followup(
    stream,
    timeout,
):

    started = time.time()
    update_live_state("LISTENING")


    pre_roll = deque(
        maxlen=max(
            1,
            int(
                PRE_ROLL_SECONDS
                / COMMAND_BLOCK_DURATION
            ),
        )
    )


    while (
        time.time()
        - started
        < timeout
    ):

        data, overflowed = stream.read(
            COMMAND_BLOCK_SIZE
        )

        audio = (
            data[:, 0]
            .copy()
            .astype(np.int16)
        )

        pre_roll.append(
            audio
        )


        level = rms(
            audio
        )


        if (
            level
            < SPEECH_THRESHOLD
        ):

            continue


        print(
            "Follow-up detected."
        )


        chunks = list(
            pre_roll
        )

        silence_started = None

        speech_started_at = (
            time.time()
        )


        while True:

            data, overflowed = stream.read(
                COMMAND_BLOCK_SIZE
            )

            audio = (
                data[:, 0]
                .copy()
                .astype(np.int16)
            )

            chunks.append(
                audio
            )


            level = rms(
                audio
            )


            if (
                level
                <= SILENCE_THRESHOLD
            ):

                if silence_started is None:

                    silence_started = (
                        time.time()
                    )

                elif (
                    time.time()
                    - silence_started
                    >= END_SILENCE_SECONDS
                ):

                    break

            else:

                silence_started = None


            if (
                time.time()
                - speech_started_at
                >= MAX_COMMAND_SECONDS
            ):

                break


        combined = np.concatenate(
            chunks
        )


        print(
            "Transcribing follow-up..."
        )
        update_live_state("TRANSCRIBING")


        return clean_transcription(
            transcribe_audio(
                combined
            )
        )


    return ""



# ============================================================
# FOLLOW-UP FILTER
# ============================================================

def is_likely_followup(text):

    if not text:
        return False

    normalized = clean_transcription(text).lower().strip()

    if not normalized:
        return False

    if normalized.startswith(("hey jarvis", "jarvis")):
        return True

    if any(
        phrase in normalized
        for phrase in FOLLOW_UP_CANCEL_PHRASES
    ):
        return True

    # Confirmation answers are valid short follow-ups.
    if normalized.strip(" .?!,") in {
        "yes", "yeah", "yep", "no", "nope",
        "confirm", "do it", "go ahead",
    }:
        return True

    # Ignore random one-word captures like "recent" or "risk".
    words = re.findall(r"[a-z0-9']+", normalized)

    if len(words) == 1:
        return False

    # We are already inside a short follow-up window directly after Jarvis spoke.
    # Treat any meaningful multi-word utterance as conversational continuation;
    # this is more natural and avoids dropping requests that do not begin with a
    # hard-coded prefix.
    return True


def is_followup_cancel(text):

    normalized = clean_transcription(text).lower().strip()

    return any(
        phrase in normalized
        for phrase in FOLLOW_UP_CANCEL_PHRASES
    )


# ============================================================
# HIMALAYA FAST EMAIL PATH
# ============================================================

def run_himalaya(args, timeout=HIMALAYA_TIMEOUT):

    args = list(args)

    if args and args[0] == "--json":
        command = [
            "himalaya",
            "--account",
            WORK_EMAIL_ACCOUNT,
            "--json",
            *args[1:],
        ]
    else:
        command = [
            "himalaya",
            "--account",
            WORK_EMAIL_ACCOUNT,
            *args,
        ]

    kwargs = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            command,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Himalaya timed out."
    except Exception as exc:
        return False, "", str(exc)

    if result.returncode != 0:
        return (
            False,
            result.stdout.strip(),
            result.stderr.strip(),
        )

    return (
        True,
        result.stdout.strip(),
        result.stderr.strip(),
    )


def _find_envelope_dicts(value):

    found = []

    if isinstance(value, dict):

        lower_keys = {
            str(key).lower()
            for key in value.keys()
        }

        if (
            "id" in lower_keys
            and "subject" in lower_keys
        ):
            found.append(value)

        for child in value.values():
            found.extend(
                _find_envelope_dicts(child)
            )

    elif isinstance(value, list):

        for child in value:
            found.extend(
                _find_envelope_dicts(child)
            )

    return found


def _dict_value_case_insensitive(data, *names):

    wanted = {
        name.lower()
        for name in names
    }

    for key, value in data.items():

        if str(key).lower() in wanted:
            return value

    return None


def _format_sender(value):

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):

        name = _dict_value_case_insensitive(
            value,
            "name",
            "display_name",
            "display-name",
        )

        address = _dict_value_case_insensitive(
            value,
            "address",
            "email",
            "addr",
        )

        if name and address:
            return f"{name} <{address}>"

        return str(
            name or address or "Unknown sender"
        )

    if isinstance(value, list) and value:
        return _format_sender(
            value[0]
        )

    return "Unknown sender"


def get_latest_work_email():

    ok, output, error = run_himalaya(
        [
            "--json",
            "envelope",
            "list",
        ]
    )

    if ok and output:

        try:
            data = json.loads(
                output
            )

            envelopes = _find_envelope_dicts(
                data
            )

            if envelopes:

                item = envelopes[0]

                return {
                    "id": str(
                        _dict_value_case_insensitive(
                            item,
                            "id",
                        )
                    ),
                    "subject": str(
                        _dict_value_case_insensitive(
                            item,
                            "subject",
                        )
                        or "(no subject)"
                    ),
                    "from": _format_sender(
                        _dict_value_case_insensitive(
                            item,
                            "from",
                            "sender",
                        )
                    ),
                    "date": str(
                        _dict_value_case_insensitive(
                            item,
                            "date",
                            "received",
                            "received_at",
                        )
                        or ""
                    ),
                }

        except Exception:
            pass

    ok, output, error = run_himalaya(
        [
            "envelope",
            "list",
        ]
    )

    if not ok:
        log(
            f"Himalaya list error: {error}"
        )
        return None

    for line in output.splitlines():

        if "│" not in line:
            continue

        cells = [
            cell.strip()
            for cell in line.strip("│").split("│")
        ]

        if (
            len(cells) >= 5
            and cells[0].isdigit()
        ):

            return {
                "id": cells[0],
                "subject": cells[2] or "(no subject)",
                "from": cells[3] or "Unknown sender",
                "date": cells[4],
            }

    return None


def read_work_email(message_id):

    ok, output, error = run_himalaya(
        [
            "message",
            "read",
            str(message_id),
        ]
    )

    if not ok:
        log(
            f"Himalaya read error: {error}"
        )
        return None

    return output


def extract_readable_email_body(raw_message):

    if not raw_message:
        return ""

    lines = raw_message.splitlines()

    body_lines = []
    in_body = False

    for line in lines:

        stripped = line.strip()

        if not in_body:

            if stripped == "":
                in_body = True

            continue

        if re.match(r"^\[\d+\]\s+", stripped):
            continue

        if stripped.lower().startswith(
            (
                "content-type:",
                "content-transfer-encoding:",
                "content-disposition:",
            )
        ):
            continue

        body_lines.append(
            line
        )

    body = "\n".join(
        body_lines
    ).strip()

    if len(body) > 1200:
        body = body[:1200].rstrip() + "..."

    return body


def extract_email_address(value):

    if not value:
        return ""

    match = re.search(
        r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}",
        str(value),
        flags=re.IGNORECASE,
    )

    return match.group(0) if match else ""


def remember_email_context(message):

    global last_email_context

    if not message:
        return

    last_email_context = dict(message)
    last_email_context["sender_email"] = extract_email_address(
        last_email_context.get("from", "")
    )


def handle_fast_email_command(text):

    command = clean_transcription(
        text
    ).lower().strip()

    other_account_words = (
        "personal email",
        "gmail",
        "dailybread email",
        "daily bread email",
        "icloud",
    )

    if any(
        phrase in command
        for phrase in other_account_words
    ):
        return False, None

    email_words = (
        "email" in command
        or "e-mail" in command
        or "mailbox" in command
        or "inbox" in command
        or "work mail" in command
        or "workmail" in command
        or (
            any(
                typo in command
                for typo in (
                    "emo",
                    "e mail",
                    "emale",
                    "emial",
                )
            )
            and (
                "work" in command
                or "newest" in command
                or "latest" in command
                or "recent" in command
            )
        )
    )

    if not email_words:
        return False, None

    latest_words = (
        "latest" in command
        or "newest" in command
        or "most recent" in command
        or "check my work email" in command
        or "check work email" in command
        or "check my email" in command
        or "check my inbox" in command
    )

    read_words = (
        "read" in command
        and (
            "latest" in command
            or "newest" in command
            or "most recent" in command
            or "last email" in command
        )
    )

    if not latest_words and not read_words:
        return False, None

    started = time.perf_counter()

    latest = get_latest_work_email()

    if not latest:
        return (
            True,
            "I couldn't retrieve the work inbox right now.",
        )

    elapsed = time.perf_counter() - started

    print(
        f"Fast email lookup: {elapsed:.1f}s"
    )

    remember_email_context(
        latest
    )

    subject = latest["subject"]
    sender = latest["from"]
    date = latest["date"]

    if read_words:

        raw = read_work_email(
            latest["id"]
        )

        body = extract_readable_email_body(
            raw
        )

        if body:
            return (
                True,
                (
                    f"The newest work email is from {sender}. "
                    f"The subject is {subject}. "
                    f"It says: {body}"
                ),
            )

        return (
            True,
            (
                f"The newest work email is from {sender}. "
                f"The subject is {subject}. "
                "It does not have a readable text body, "
                "so it may mainly contain an attachment."
            ),
        )

    date_text = (
        f", received {date}"
        if date
        else ""
    )

    return (
        True,
        (
            f"Your newest work email is from {sender}"
            f"{date_text}. The subject is {subject}."
        ),
    )



# ============================================================
# OUTLOOK FAST CALENDAR / DIRECTORY
# ============================================================

OUTLOOK_WORKER_TIMEOUT = 15

OUTLOOK_WORKER_CODE = r"""
import sys
import json
import gc
from datetime import datetime

import pythoncom
import win32com.client


def dt_obj(value):
    return {
        "year": value.year,
        "month": value.month,
        "day": value.day,
        "hour": value.hour,
        "minute": value.minute,
        "second": value.second,
    }


def main():
    payload = json.loads(sys.stdin.read() or "{}")
    op = payload.get("op", "")

    pythoncom.CoInitialize()

    outlook = None
    namespace = None

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        if op == "calendar_list":
            calendar = namespace.GetDefaultFolder(9)
            items = calendar.Items
            items.Sort("[Start]")
            items.IncludeRecurrences = True

            start = datetime.fromisoformat(payload["start"])
            end = datetime.fromisoformat(payload["end"])

            restriction = (
                "[Start] >= '"
                + start.strftime("%m/%d/%Y %I:%M %p")
                + "' AND [Start] <= '"
                + end.strftime("%m/%d/%Y %I:%M %p")
                + "'"
            )

            restricted = items.Restrict(restriction)
            results = []

            for item in restricted:
                results.append({
                    "entry_id": str(getattr(item, "EntryID", "") or ""),
                    "subject": str(getattr(item, "Subject", "") or "(no subject)"),
                    "start": dt_obj(item.Start),
                    "end": dt_obj(item.End),
                    "location": str(getattr(item, "Location", "") or ""),
                    "duration": int(getattr(item, "Duration", 30) or 30),
                    "meeting_status": int(getattr(item, "MeetingStatus", 0) or 0),
                })

            print(json.dumps({"ok": True, "items": results}))
            return

        if op == "directory_search":
            needle = str(payload.get("search", "")).lower().strip()
            results = []
            seen = set()

            for address_list in namespace.AddressLists:
                if address_list.Name not in (
                    "Global Address List",
                    "Company Address List",
                ):
                    continue

                for entry in address_list.AddressEntries:
                    name = str(getattr(entry, "Name", "") or "")

                    if needle not in name.lower():
                        continue

                    email = ""

                    try:
                        exchange_user = entry.GetExchangeUser()
                        if exchange_user:
                            email = str(exchange_user.PrimarySmtpAddress or "")
                    except Exception:
                        pass

                    if not email:
                        try:
                            email = str(entry.Address or "")
                        except Exception:
                            email = ""

                    key = (name.lower(), email.lower())

                    if key in seen:
                        continue

                    seen.add(key)

                    results.append({
                        "name": name,
                        "email": email,
                    })

            print(json.dumps({"ok": True, "items": results}))
            return

        if op == "create":
            appointment = outlook.CreateItem(1)
            appointment.Subject = payload["subject"]
            start = datetime.fromisoformat(payload["start"])
            appointment.Start = start.strftime("%m/%d/%Y %I:%M %p")
            appointment.Duration = int(payload.get("duration", 30))
            appointment.BusyStatus = 2

            attendee = str(payload.get("attendee_email", "") or "").strip()

            if attendee:
                appointment.MeetingStatus = 1
                recipient = appointment.Recipients.Add(attendee)
                recipient.Type = 1

                if not appointment.Recipients.ResolveAll():
                    print(json.dumps({
                        "ok": False,
                        "error": "Could not resolve attendee.",
                    }))
                    return

                appointment.Send()
                print(json.dumps({
                    "ok": True,
                    "sent_invite": True,
                }))
                return

            appointment.Save()
            print(json.dumps({
                "ok": True,
                "sent_invite": False,
            }))
            return

        if op == "delete":
            item = namespace.GetItemFromID(payload["entry_id"])
            subject = str(getattr(item, "Subject", "") or "(no subject)")
            item.Delete()
            print(json.dumps({
                "ok": True,
                "subject": subject,
            }))
            return

        if op == "reschedule":
            item = namespace.GetItemFromID(payload["entry_id"])
            subject = str(getattr(item, "Subject", "") or "(no subject)")
            start = datetime.fromisoformat(payload["start"])
            item.Start = start.strftime("%m/%d/%Y %I:%M %p")
            item.Duration = int(payload.get("duration", 30))
            meeting_status = int(getattr(item, "MeetingStatus", 0) or 0)

            item.Save()

            sent_update = False

            if meeting_status != 0:
                try:
                    item.Send()
                    sent_update = True
                except Exception:
                    sent_update = False

            print(json.dumps({
                "ok": True,
                "subject": subject,
                "sent_update": sent_update,
                "was_meeting": meeting_status != 0,
            }))
            return

        print(json.dumps({
            "ok": False,
            "error": "Unknown Outlook worker operation.",
        }))

    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
        }))

    finally:
        namespace = None
        outlook = None
        gc.collect()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
"""


def _run_outlook_worker(payload, timeout=OUTLOOK_WORKER_TIMEOUT):

    kwargs = {
        "input": json.dumps(payload),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                OUTLOOK_WORKER_CODE,
            ],
            **kwargs,
        )

    except subprocess.TimeoutExpired:
        log(
            f"Outlook worker timed out during {payload.get('op')}"
        )
        return {
            "ok": False,
            "error": "Outlook timed out.",
            "timeout": True,
        }

    except Exception as exc:
        log(
            f"Outlook worker launch error: {exc}"
        )
        return {
            "ok": False,
            "error": str(exc),
        }

    output = result.stdout.strip()

    if result.returncode != 0:
        log(
            "Outlook worker process error: "
            + (result.stderr.strip() or output)[:1000]
        )
        return {
            "ok": False,
            "error": "Outlook worker failed.",
        }

    try:
        data = json.loads(output)
    except Exception:
        log(
            "Outlook worker returned invalid output: "
            + output[:1000]
        )
        return {
            "ok": False,
            "error": "Outlook returned an invalid response.",
        }

    if not data.get("ok"):
        log(
            "Outlook worker operation failed: "
            + str(data.get("error", "Unknown error"))
        )

    return data


def _datetime_from_worker(value):

    if not isinstance(value, dict):
        return None

    try:
        return datetime(
            int(value["year"]),
            int(value["month"]),
            int(value["day"]),
            int(value["hour"]),
            int(value["minute"]),
            int(value.get("second", 0)),
        )
    except Exception:
        return None


def _worker_calendar_list(start, end):

    result = _run_outlook_worker(
        {
            "op": "calendar_list",
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    )

    if not result.get("ok"):
        return None

    converted = []

    for item in result.get("items", []):
        converted.append(
            {
                **item,
                "start": _datetime_from_worker(
                    item.get("start")
                ),
                "end": _datetime_from_worker(
                    item.get("end")
                ),
            }
        )

    return converted


def _python_datetime(value):

    if value is None:
        return None

    try:
        return datetime(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
        )
    except Exception:
        return None


def _outlook_local_start(item):

    start = _python_datetime(
        getattr(item, "Start", None)
    )

    if start is None:
        return None

    try:
        start_utc = getattr(item, "StartUTC", None)

        if start_utc is not None:
            utc_dt = _python_datetime(start_utc)

            if utc_dt is not None:
                from datetime import timezone

                local_dt = (
                    utc_dt.replace(tzinfo=timezone.utc)
                    .astimezone()
                    .replace(tzinfo=None)
                )

                if abs((start - local_dt).total_seconds()) >= 60:
                    return local_dt

    except Exception:
        pass

    return start


def _day_range_from_command(command):

    now = datetime.now()
    lower = command.lower()

    # Today
    if "today" in lower:
        start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return start, start.replace(
            hour=23,
            minute=59,
            second=59,
        ), "today"

    # Tomorrow
    if "tomorrow" in lower:
        start = (
            now
            + __import__("datetime").timedelta(days=1)
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return start, start.replace(
            hour=23,
            minute=59,
            second=59,
        ), "tomorrow"

    # Named weekday
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    for name, weekday in weekdays.items():

        if name in lower:

            days_ahead = (
                weekday - now.weekday()
            ) % 7

            if days_ahead == 0:
                days_ahead = 7

            target = (
                now
                + __import__("datetime").timedelta(
                    days=days_ahead
                )
            )

            start = target.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            return (
                start,
                start.replace(
                    hour=23,
                    minute=59,
                    second=59,
                ),
                name.capitalize(),
            )

    # Default: next 7 days.
    return (
        now,
        now + __import__("datetime").timedelta(
            days=7
        ),
        "the next seven days",
    )


def _apply_daypart(start, end, command):

    lower = command.lower()

    if "morning" in lower:
        return (
            start.replace(
                hour=6,
                minute=0,
                second=0,
            ),
            start.replace(
                hour=12,
                minute=0,
                second=0,
            ),
        )

    if "afternoon" in lower:
        return (
            start.replace(
                hour=12,
                minute=0,
                second=0,
            ),
            start.replace(
                hour=17,
                minute=0,
                second=0,
            ),
        )

    if "evening" in lower or "tonight" in lower:
        return (
            start.replace(
                hour=17,
                minute=0,
                second=0,
            ),
            start.replace(
                hour=23,
                minute=59,
                second=59,
            ),
        )

    return start, end


def get_calendar_items(command):

    start, end, label = (
        _day_range_from_command(
            command
        )
    )

    start, end = _apply_daypart(
        start,
        end,
        command,
    )

    appointments = _worker_calendar_list(
        start,
        end,
    )

    if appointments is None:
        return None, None, None

    return appointments, start, end


def _spoken_time(dt):

    if dt is None:
        return ""

    text = dt.strftime(
        "%I:%M %p"
    ).lstrip("0")

    return text.replace(
        ":00 ",
        " ",
    )


def handle_fast_calendar_command(text):

    command = clean_transcription(
        text
    )

    lower = command.lower()

    write_words = (
        "cancel" in lower
        or "delete" in lower
        or "reschedule" in lower
        or lower.startswith("move ")
        or " move my " in lower
    )

    agent_task_words = (
        re.match(
            r"^(?:deploy|deploying|start|starting|launch|launching|send|sending|have|having|tell|telling)\s+(?:(?:an|a|another)\s+)?agent\b",
            lower,
            flags=re.IGNORECASE,
        )
        is not None
        or "background agent" in lower
    )

    calendar_terms = (
        not write_words
        and not agent_task_words
        and (
            "calendar" in lower
            or ("schedule" in lower and "reschedule" not in lower)
            or "what do i have" in lower
            or "what's on" in lower
            or "whats on" in lower
            or "am i free" in lower
            or "do i have anything" in lower
            or "what appointments" in lower
        )
    )

    if not calendar_terms:
        return False, None

    started = time.perf_counter()

    appointments, start, end = (
        get_calendar_items(
            command
        )
    )

    if appointments is None:
        return (
            True,
            "I couldn't access your Outlook calendar right now.",
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"Fast calendar lookup: {elapsed:.1f}s"
    )

    asking_free = (
        "am i free" in lower
        or "do i have anything" in lower
    )

    if not appointments:

        if asking_free:
            return (
                True,
                "Yes. I don't see anything scheduled in that time window.",
            )

        return (
            True,
            "You don't have anything scheduled in that time window.",
        )

    if asking_free:

        if len(appointments) == 1:
            first = appointments[0]
            return (
                True,
                (
                    "You're not completely free. "
                    f"You have {first['subject']} "
                    f"at {_spoken_time(first['start'])}."
                ),
            )

        return (
            True,
            (
                f"You're not completely free. "
                f"You have {len(appointments)} appointments "
                "in that time window."
            ),
        )

    pieces = []

    for appt in appointments[:5]:

        item = (
            f"{appt['subject']} at "
            f"{_spoken_time(appt['start'])}"
        )

        if appt["location"]:
            item += (
                f" at {appt['location']}"
            )

        pieces.append(
            item
        )

    if len(appointments) == 1:
        return (
            True,
            "You have one appointment: "
            + pieces[0]
            + ".",
        )

    response = (
        f"You have {len(appointments)} appointments. "
        + "; ".join(pieces)
    )

    if len(appointments) > 5:
        response += (
            f"; and {len(appointments) - 5} more."
        )
    else:
        response += "."

    return True, response


def lookup_exchange_directory(search_text):

    result = _run_outlook_worker(
        {
            "op": "directory_search",
            "search": search_text,
        }
    )

    if not result.get("ok"):
        return []

    return result.get(
        "items",
        [],
    )


def _extract_contact_search_term(command):

    cleaned = clean_transcription(command).strip()

    patterns = [
        # "find Dean's email address"
        r"^(?:find|look up|lookup|get|show me)\s+(.+?)(?:'s|s')\s+(?:email|email address)$",

        # "what is Dean's email address" / "what's Dean's email"
        r"^what(?:'s| is)\s+(.+?)(?:'s|s')\s+(?:email|email address)$",

        # "email address for Dean" / "email for Dean"
        r"^(?:find\s+)?(?:the\s+)?(?:email address|email)\s+for\s+(.+)$",

        # "look up Dean in the company directory"
        r"^(?:find|look up|lookup)\s+(.+?)\s+in\s+(?:the\s+)?(?:company\s+)?directory$",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:

            term = (
                match.group(1)
                .strip(" ,.?")
            )

            # Defensive cleanup in case transcription leaves a
            # possessive suffix attached to the captured name.
            term = re.sub(
                r"(?:'s|s')$",
                "",
                term,
                flags=re.IGNORECASE,
            ).strip()

            return term

    return ""


def handle_fast_contact_command(text):

    command = clean_transcription(
        text
    )

    lower = command.lower()

    contact_terms = (
        "email address" in lower
        or "company directory" in lower
        or "look up" in lower
        or "lookup" in lower
    )

    if not contact_terms:
        return False, None

    search_term = (
        _extract_contact_search_term(
            command
        )
    )

    if not search_term:
        return False, None

    started = time.perf_counter()

    results = lookup_exchange_directory(
        search_term
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        f"Fast directory lookup: {elapsed:.1f}s"
    )

    if not results:
        return (
            True,
            f"I couldn't find {search_term} in the company directory.",
        )

    if len(results) == 1:
        person = results[0]

        return (
            True,
            (
                f"{person['name']}'s email address "
                f"is {person['email']}."
            ),
        )

    first = results[:3]

    choices = "; ".join(
        f"{person['name']}, {person['email']}"
        for person in first
    )

    return (
        True,
        (
            f"I found multiple matches for {search_term}: "
            f"{choices}."
        ),
    )



# ============================================================
# CONFIRMATION / WRITE ACTION ENGINE
# ============================================================

YES_PHRASES = (
    "yes",
    "yeah",
    "yep",
    "confirm",
    "confirmed",
    "do it",
    "send it",
    "go ahead",
    "yes send it",
    "yes do it",
    "yes please",
)

NO_PHRASES = (
    "no",
    "nope",
    "cancel",
    "cancel it",
    "don't",
    "do not",
    "never mind",
    "nevermind",
    "stop",
)


def _normalize_confirmation(text):

    return re.sub(
        r"[^a-z0-9\s']",
        "",
        clean_transcription(text).lower(),
    ).strip()


def _is_yes(text):

    normalized = _normalize_confirmation(
        text
    )

    return (
        normalized in YES_PHRASES
        or normalized.startswith("yes ")
        or normalized.startswith("yeah ")
        or normalized.startswith("yep ")
        or normalized.startswith("go ahead")
    )


def _is_no(text):

    normalized = _normalize_confirmation(
        text
    )

    return (
        normalized in NO_PHRASES
        or normalized.startswith("no ")
        or normalized.startswith("cancel")
        or normalized.startswith("never mind")
    )


def _spoken_email_address(address):

    # ElevenLabs generally handles email addresses well, but spacing
    # around punctuation makes confirmations more understandable.
    return (
        address
        .replace("@", " at ")
        .replace(".", " dot ")
    )


def _resolve_one_person(name):

    results = lookup_exchange_directory(
        name
    )

    if not results:
        return None, (
            f"I couldn't find {name} in the company directory."
        )

    if len(results) > 1:
        names = ", ".join(
            item["name"]
            for item in results[:3]
        )

        return None, (
            f"I found multiple matches for {name}: {names}. "
            "Please say the full name."
        )

    return results[0], None


def run_himalaya_with_input(
    args,
    input_text,
    timeout=HIMALAYA_TIMEOUT,
):

    command = [
        "himalaya",
        "--account",
        WORK_EMAIL_ACCOUNT,
        *args,
    ]

    kwargs = {
        "input": input_text,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            command,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        return False, "", "Himalaya timed out."
    except Exception as exc:
        return False, "", str(exc)

    return (
        result.returncode == 0,
        result.stdout.strip(),
        result.stderr.strip(),
    )


def send_work_email(
    to_address,
    subject,
    body,
):

    message = (
        f"From: {WORK_EMAIL_ADDRESS}\n"
        f"To: {to_address}\n"
        f"Subject: {subject}\n"
        "\n"
        f"{body}\n"
    )

    ok, output, error = run_himalaya_with_input(
        [
            "message",
            "send",
        ],
        message,
        timeout=30,
    )

    if not ok:
        log(
            f"Email send failed: {error or output}"
        )
        return False

    return True


COMMON_EMAIL_DOMAIN_ALIASES = {
    "gmail.com": "gmail.com",
    "g mail.com": "gmail.com",
    "gmail dot com": "gmail.com",
    "gml.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmial.com": "gmail.com",
    "outlook.com": "outlook.com",
    "outlook dot com": "outlook.com",
    "hotmail.com": "hotmail.com",
    "hotmail dot com": "hotmail.com",
    "yahoo.com": "yahoo.com",
    "yahoo dot com": "yahoo.com",
    "icloud.com": "icloud.com",
    "icloud dot com": "icloud.com",
}

KNOWN_EMAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "icloud.com",
    "afdllc.com",
}


def _normalize_email_domain(domain):

    cleaned = domain.lower().strip()
    cleaned = re.sub(r"\s+dot\s+", ".", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)

    return COMMON_EMAIL_DOMAIN_ALIASES.get(
        cleaned,
        cleaned,
    )


def _domain_looks_suspicious(domain):

    domain = domain.lower().strip()

    if domain in KNOWN_EMAIL_DOMAINS:
        return False

    # Obvious malformed / uncommon speech-recognition artifacts.
    if "." not in domain:
        return True

    tld = domain.rsplit(".", 1)[-1]

    if len(tld) < 2:
        return True

    return False


def normalize_spoken_email_address(text):

    """
    Convert common Whisper voice transcriptions such as:
      "Sheldon sharp 1 1 2 4 at gmail.com"
      "sheldon sharp 1124 at gmail dot com"
      "sheldonsharp1124 at gml.com"
    into a normalized address.

    Returns None when the text does not look like an email address.
    """

    if not text:
        return None

    value = clean_transcription(text).strip().lower()

    value = re.sub(r"\s+at\s+", "@", value)
    value = re.sub(r"\s+dot\s+", ".", value)
    value = re.sub(r"\s*@\s*", "@", value)
    value = re.sub(r"\s*\.\s*", ".", value)

    if "@" not in value:
        return None

    local_part, domain = value.split("@", 1)

    # Email local parts cannot contain spaces; spoken digits and names often do.
    local_part = re.sub(r"\s+", "", local_part)
    domain = _normalize_email_domain(domain)

    value = f"{local_part}@{domain}".rstrip(" ,;:!?")

    if re.fullmatch(
        r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}",
        value,
        flags=re.IGNORECASE,
    ):
        return value

    return None


def _extract_email_action(command):

    """
    Supported examples:
      email Dean and tell him I finished the report
      email Dean and tell her the report is ready
      send Dean an email saying I finished the report
      send an email to Dean saying I finished the report
      send an email to example@example.com. Tell him this is a test
    """

    cleaned = clean_transcription(command).strip()

    # Normalize sentence punctuation between the recipient and the
    # "tell/say" clause so natural speech still matches.
    cleaned = re.sub(
        r"[.!?]+\s*(?=(?:tell|telling|say|saying|that says)\b)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    patterns = [
        # "email Dean and tell him ..."
        r"^(?:send\s+)?email\s+(.+?)\s+and\s+tell\s+(?:him|her|them)\s+(.+)$",

        # "send Dean an email saying ..."
        r"^send\s+(.+?)\s+an\s+email\s+(?:saying|that says|telling\s+(?:him|her|them))\s+(.+)$",

        # "send an email to Dean saying ..."
        r"^send\s+an\s+email\s+to\s+(.+?)\s+(?:saying|that says|telling\s+(?:him|her|them))\s+(.+)$",

        # "send an email to Dean tell him ..."
        r"^send\s+an\s+email\s+to\s+(.+?)\s+tell\s+(?:him|her|them)\s+(.+)$",

        # "email Dean saying ..."
        r"^email\s+(.+?)\s+(?:saying|that says)\s+(.+)$",

        # "email Dean tell him ..."
        r"^email\s+(.+?)\s+tell\s+(?:him|her|them)\s+(.+)$",
    ]

    for pattern in patterns:

        match = re.match(
            pattern,
            cleaned,
            flags=re.IGNORECASE,
        )

        if match:
            return (
                match.group(1).strip(" ,.?"),
                match.group(2).strip(" ,.?"),
            )

    return None


def _extract_reply_body(command):

    patterns = [
        r"^(?:reply|respond)\s+and\s+tell\s+(?:him|her|them)\s+(.+)$",
        r"^(?:reply|respond)\s+(?:saying|that|with)\s+(.+)$",
        r"^(?:reply|respond)\s+to\s+(?:it|that|the email)\s+and\s+(?:say|tell\s+(?:him|her|them))\s+(.+)$",
        r"^(?:reply|respond)\s+to\s+(?:it|that|the email)\s+(?:saying|that|with)\s+(.+)$",
        r"^(?:reply|respond)\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, command.strip(), flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ,.?")

    return ""


def handle_email_reply_request(text):

    global pending_action

    command = clean_transcription(text)
    lower = command.lower().strip()

    normalized = re.sub(
        r"^(?:(?:can you|could you|would you|please|jarvis|hey jarvis)\s+|"
        r"(?:go ahead and|go ahead|actually|okay|ok)\s+)+",
        "",
        lower,
        flags=re.IGNORECASE,
    ).strip()

    if not (
        normalized.startswith("reply")
        or normalized.startswith("respond")
    ):
        return False, None

    if not last_email_context:
        return True, "I don't have an email in context yet. Ask me to check or read an email first."

    body = _extract_reply_body(normalized)

    if not body:
        return True, "Tell me what you want the reply to say."

    recipient = (
        last_email_context.get("sender_email")
        or extract_email_address(last_email_context.get("from", ""))
    )

    if not recipient:
        return True, "I couldn't determine the sender's email address safely."

    original_subject = last_email_context.get("subject") or "(no subject)"
    subject = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"

    domain = recipient.rsplit("@", 1)[-1]
    if _domain_looks_suspicious(domain):
        return True, "The sender address looks unusual, so I won't prepare that reply automatically."

    pending_action = {
        "type": "send_email",
        "recipient_name": last_email_context.get("from") or recipient,
        "recipient_email": recipient,
        "subject": subject,
        "body": body,
        "suspicious_domain": False,
    }

    return (
        True,
        f"I have a reply ready to {last_email_context.get('from') or recipient}. "
        f"It says: {body}. Do you want me to send it?"
    )


def handle_email_write_request(text):

    global pending_action

    command = clean_transcription(
        text
    )

    lower = command.lower()

    write_intent = (
        lower.startswith("email ")
        or lower.startswith("send email ")
        or lower.startswith("send an email ")
        or (
            lower.startswith("send ")
            and " email " in f" {lower} "
        )
    )

    if not write_intent:
        return False, None

    parsed = _extract_email_action(
        command
    )

    if not parsed:
        return (
            True,
            (
                "I can send that, but I need the recipient and the message. "
                "For example, say: email Dean and tell him I finished the report."
            ),
        )

    recipient_text, body = parsed

    # Accept both typed addresses and natural speech transcriptions such as
    # "Sheldon sharp 1 1 2 4 at gmail.com".
    normalized_email = normalize_spoken_email_address(
        recipient_text
    )

    if normalized_email:

        recipient_name = normalized_email
        recipient_email = normalized_email

    else:

        person, error = _resolve_one_person(
            recipient_text
        )

        if error:
            return True, error

        recipient_name = person["name"]
        recipient_email = person["email"]

    subject = "Quick note"

    suspicious_domain = False

    if normalized_email:
        domain = recipient_email.rsplit("@", 1)[-1]
        suspicious_domain = _domain_looks_suspicious(
            domain
        )

    pending_action = {
        "type": "send_email",
        "recipient_name": recipient_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "suspicious_domain": suspicious_domain,
    }

    spoken_recipient = (
        _spoken_email_address(recipient_email)
        if normalized_email
        else recipient_name
    )

    if suspicious_domain:
        return (
            True,
            (
                f"I heard the address as {spoken_recipient}. "
                "That domain looks unusual, so I will not send anything yet. "
                "Please repeat the email address clearly."
            ),
        )

    return (
        True,
        (
            f"I have an email ready for {spoken_recipient}. "
            f"It says: {body}. "
            "Do you want me to send it?"
        ),
    )


def _parse_duration_minutes(command):

    lower = command.lower()

    match = re.search(
        r"\bfor\s+(\d+)\s*(?:minute|minutes|min)\b",
        lower,
    )

    if match:
        return max(
            5,
            min(
                480,
                int(match.group(1)),
            ),
        )

    match = re.search(
        r"\bfor\s+(?:an|one|1)\s+hour\b",
        lower,
    )

    if match:
        return 60

    match = re.search(
        r"\bfor\s+(\d+)\s*hours?\b",
        lower,
    )

    if match:
        return max(
            15,
            min(
                480,
                int(match.group(1)) * 60,
            ),
        )

    return 30


def _parse_calendar_datetime(command):

    lower = command.lower()
    now = datetime.now()

    # Date
    if "tomorrow" in lower:
        date = (
            now + timedelta(days=1)
        ).date()

    elif "today" in lower:
        date = now.date()

    else:
        weekday_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        date = None

        for name, weekday in weekday_map.items():

            if name in lower:

                days_ahead = (
                    weekday - now.weekday()
                ) % 7

                if days_ahead == 0:
                    days_ahead = 7

                date = (
                    now + timedelta(
                        days=days_ahead
                    )
                ).date()

                break

        if date is None:
            return None

    # Time such as 10, 10:30, 10 AM, 2:15 PM
    time_match = re.search(
        r"\b(?:at|for|to)\s+(\d{1,2})(?:(?:[:.]|\s+)(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b",
        lower,
    )

    if not time_match:
        return None

    hour = int(
        time_match.group(1)
    )

    minute = int(
        time_match.group(2) or 0
    )

    meridiem = (
        time_match.group(3) or ""
    ).replace(".", "")

    if meridiem:

        if meridiem == "pm" and hour < 12:
            hour += 12

        elif meridiem == "am" and hour == 12:
            hour = 0

    else:
        # Natural voice heuristic. The confirmation repeats the
        # interpreted time, so the user can reject a bad guess.
        if "afternoon" in lower or "evening" in lower or "tonight" in lower:
            if hour < 12:
                hour += 12

        elif 1 <= hour <= 6:
            # "at 2" is usually 2 PM in calendar conversation.
            hour += 12

    if not (
        0 <= hour <= 23
        and 0 <= minute <= 59
    ):
        return None

    return datetime(
        date.year,
        date.month,
        date.day,
        hour,
        minute,
    )


def _extract_meeting_person(command):

    match = re.search(
        r"\bwith\s+(.+?)(?=\s+(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\s+at\s+\d|\s+for\s+\d|\s+for\s+(?:an|one)\s+hour|$)",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    return match.group(1).strip(" ,.?") 


def _extract_calendar_subject(command, person_name=""):

    lower = command.lower()

    if "meeting" in lower and person_name:
        return f"Meeting with {person_name}"

    # Remove the action verb, then stop the title before scheduling details.
    subject = re.sub(
        r"^(?:schedule|add|create|make|put|leave)\s+(?:a|an)?\s*",
        "",
        command.strip(),
        flags=re.IGNORECASE,
    )

    subject = re.split(
        r"\s+(?=(?:(?:at|for|to)\s+\d{1,2}(?:[:.]\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?|"
        r"today\b|tomorrow\b|monday\b|tuesday\b|wednesday\b|thursday\b|"
        r"friday\b|saturday\b|sunday\b|for\s+\d+\s*(?:minutes?|mins?|hours?)\b|"
        r"for\s+(?:an|one)\s+hour\b))",
        subject,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    subject = subject.strip(" ,.?")

    return subject[:120] if subject else "Appointment"


def _format_confirmation_datetime(value):

    return (
        value.strftime(
            "%A, %B %d at %I:%M %p"
        )
        .replace(" 0", " ")
        .replace(" at 0", " at ")
    )


def _calendar_change_window(command):

    start, end, _ = _day_range_from_command(command)
    lower = command.lower()

    if any(day in lower for day in (
        "today", "tomorrow", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday"
    )):
        return start, end

    now = datetime.now()
    return now - timedelta(hours=1), now + timedelta(days=30)


def _extract_event_search_subject(command):

    cleaned = clean_transcription(command).strip()

    cleaned = re.sub(
        r"^(?:(?:can you|could you|would you|please|jarvis|hey jarvis)\s+|"
        r"(?:go ahead and|go ahead|actually|okay|ok)\s+)+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^(?:cancel|delete|move|reschedule)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^(?:all|both)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^(?:my|the|of my|of the)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Remove chained second-event wording; bulk/two-event logic handles it.
    cleaned = re.split(
        r"\s+(?:and\s+also|and)\s+",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    # For moves, remove destination time first.
    cleaned = re.sub(
        r"\s+\bto\s+\d{1,2}(?:(?:[:.]|\s+)\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Remove source time/date/duration tail.
    cleaned = re.split(
        r"\s+(?=(?:today\b|tomorrow\b|monday\b|tuesday\b|wednesday\b|"
        r"thursday\b|friday\b|saturday\b|sunday\b|"
        r"(?:at|for)\s+(?:\d{1,2}(?:(?:[:.]|\s+)\d{2})?|\d{3,4})\s*(?:a\.?m\.?|p\.?m\.?)?\b|"
        r"for\s+\d+\s*(?:minutes?|mins?|hours?)\b))",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    return cleaned.strip(" ,.?")


def find_calendar_events_for_change(command):

    query = _extract_event_search_subject(
        command
    )

    if not query:
        return []

    start, end = _calendar_change_window(
        command
    )

    events = _worker_calendar_list(
        start,
        end,
    )

    if events is None:
        return None

    query_tokens = [
        token
        for token in re.findall(
            r"[a-z0-9]+",
            query.lower(),
        )
        if token not in {
            "appointment",
            "appointments",
            "event",
            "events",
            "meeting",
            "meetings",
        }
    ]

    matches = []

    for event in events:
        subject_lower = (
            event.get("subject", "")
            .lower()
        )

        if query_tokens and not all(
            token in subject_lower
            for token in query_tokens
        ):
            continue

        if not event.get("entry_id"):
            continue

        matches.append(
            {
                "entry_id": event["entry_id"],
                "subject": event.get(
                    "subject",
                    "(no subject)",
                ),
                "start": event.get("start"),
                "duration": int(
                    event.get("duration", 30)
                    or 30
                ),
                "meeting_status": int(
                    event.get("meeting_status", 0)
                    or 0
                ),
            }
        )

    return matches


def _describe_calendar_match(item):

    return f"{item['subject']} on {_format_confirmation_datetime(item['start'])}"


def execute_calendar_cancel(action):

    result = _run_outlook_worker(
        {
            "op": "delete",
            "entry_id": action["entry_id"],
        }
    )

    if not result.get("ok"):
        if result.get("timeout"):
            return (
                False,
                "Outlook took too long to respond, so I stopped the calendar action.",
            )

        return (
            False,
            "I couldn't cancel that calendar event.",
        )

    return (
        True,
        f"I canceled {result.get('subject') or action.get('subject', 'the appointment')}.",
    )


def execute_calendar_reschedule(action):

    result = _run_outlook_worker(
        {
            "op": "reschedule",
            "entry_id": action["entry_id"],
            "start": action["new_start"].isoformat(),
            "duration": int(
                action.get("duration", 30)
                or 30
            ),
        }
    )

    if not result.get("ok"):
        if result.get("timeout"):
            return (
                False,
                "Outlook took too long to respond, so I stopped the reschedule attempt.",
            )

        return (
            False,
            "I couldn't reschedule that calendar event.",
        )

    if result.get("was_meeting"):
        if result.get("sent_update"):
            return (
                True,
                f"I moved {action['subject']} and sent the meeting update.",
            )

        return (
            True,
            f"I moved {action['subject']}, but Outlook could not send the meeting update.",
        )

    return (
        True,
        f"I moved {action['subject']} to {_format_confirmation_datetime(action['new_start'])}.",
    )


def find_all_calendar_events_in_window(command):

    start, end, _ = _day_range_from_command(
        command
    )

    events = _worker_calendar_list(
        start,
        end,
    )

    if events is None:
        return None

    return [
        {
            "entry_id": event["entry_id"],
            "subject": event.get("subject", "(no subject)"),
            "start": event.get("start"),
            "duration": int(event.get("duration", 30) or 30),
            "meeting_status": int(event.get("meeting_status", 0) or 0),
        }
        for event in events
        if event.get("entry_id")
    ]


def execute_bulk_calendar_cancel(action):

    deleted = 0
    failed = 0

    for event in action.get("events", []):

        result = _run_outlook_worker(
            {
                "op": "delete",
                "entry_id": event["entry_id"],
            }
        )

        if result.get("ok"):
            deleted += 1
        else:
            failed += 1

    if failed:
        return (
            deleted > 0,
            f"I deleted {deleted} appointment{'s' if deleted != 1 else ''}, "
            f"but {failed} could not be deleted.",
        )

    return (
        True,
        f"I deleted all {deleted} appointment{'s' if deleted != 1 else ''}.",
    )


def _extract_spoken_times(command):

    lower = clean_transcription(command).lower()

    matches = re.findall(
        r"\b(?:at|to)\s+(\d{1,2})(?:(?:[:.]|\s+)(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b",
        lower,
        flags=re.IGNORECASE,
    )

    values = []

    for hour_text, minute_text, meridiem in matches:
        hour = int(hour_text)
        minute = int(minute_text or 0)
        meridiem = meridiem.replace(".", "").lower()

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        values.append((hour, minute))

    return values


def _filter_events_by_times(events, times):

    if not times:
        return events

    filtered = []

    for event in events:
        start = event.get("start")

        if start is None:
            continue

        if any(
            start.hour == hour and start.minute == minute
            for hour, minute in times
        ):
            filtered.append(event)

    return filtered


def find_matching_events_for_bulk_cancel(command):

    # Start with subject/day matching.
    events = find_calendar_events_for_change(command)

    if events is None:
        return None

    # If exact source times were spoken, restrict to those.
    times = _extract_spoken_times(command)

    if times:
        events = _filter_events_by_times(events, times)

    return events


def _extract_calendar_time_mentions(command):

    lower = clean_transcription(command).lower()

    values = []

    # Normal explicit times:
    # 3 PM, 3:15 PM, 3.15 PM, 3 15 PM
    matches = re.findall(
        r"\b(\d{1,2})(?:(?:[:.]|\s+)(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b",
        lower,
        flags=re.IGNORECASE,
    )

    for hour_text, minute_text, meridiem in matches:
        hour = int(hour_text)
        minute = int(minute_text or 0)
        meridiem = meridiem.replace(".", "").lower()

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            values.append((hour, minute))

    # Whisper sometimes collapses "three fifteen" into "315".
    # Treat a standalone 3- or 4-digit number immediately before
    # "appointment/event/meeting" as a compact clock time.
    compact_matches = re.findall(
        r"\b(\d{3,4})\s+(?:appointment|event|meeting)\b",
        lower,
        flags=re.IGNORECASE,
    )

    for compact in compact_matches:

        if len(compact) == 3:
            hour = int(compact[0])
            minute = int(compact[1:])
        else:
            hour = int(compact[:2])
            minute = int(compact[2:])

        if not (1 <= hour <= 12 and 0 <= minute <= 59):
            continue

        # Infer AM/PM from a destination time when possible.
        # For the common "315 appointment ... to 4 PM" case,
        # source and destination are assumed to be in the same half-day.
        explicit_meridiems = re.findall(
            r"\b\d{1,2}(?:(?:[:.]|\s+)\d{2})?\s*(a\.?m\.?|p\.?m\.?)\b",
            lower,
            flags=re.IGNORECASE,
        )

        meridiem = (
            explicit_meridiems[-1].replace(".", "").lower()
            if explicit_meridiems
            else ""
        )

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        compact_value = (hour, minute)

        if compact_value not in values:
            values.insert(0, compact_value)

    return values


def _find_calendar_events_by_day_and_time(command, hour, minute):

    start, end, _ = _day_range_from_command(
        command
    )

    events = _worker_calendar_list(
        start,
        end,
    )

    if events is None:
        return None

    matches = []

    for event in events:
        start_dt = event.get("start")

        if start_dt is None:
            continue

        if (
            start_dt.hour != hour
            or start_dt.minute != minute
        ):
            continue

        if not event.get("entry_id"):
            continue

        matches.append(
            {
                "entry_id": event["entry_id"],
                "subject": event.get(
                    "subject",
                    "(no subject)",
                ),
                "start": start_dt,
                "duration": int(
                    event.get("duration", 30)
                    or 30
                ),
                "meeting_status": int(
                    event.get("meeting_status", 0)
                    or 0
                ),
            }
        )

    return matches


def _command_has_explicit_calendar_day(command):

    lower = clean_transcription(command).lower()

    return any(
        token in lower
        for token in (
            "today",
            "tomorrow",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    )


def _datetime_on_requested_day(
    command,
    hour,
    minute,
    fallback_date=None,
):

    if (
        fallback_date is not None
        and not _command_has_explicit_calendar_day(command)
    ):
        start = fallback_date
    else:
        start, _, _ = _day_range_from_command(
            command
        )

    return start.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def _try_time_based_calendar_change(command, normalized):

    global pending_action

    is_cancel = (
        normalized.startswith("cancel ")
        or normalized.startswith("delete ")
        or " cancel " in f" {normalized} "
        or " delete " in f" {normalized} "
    )

    is_move = (
        normalized.startswith("move ")
        or normalized.startswith("reschedule ")
        or " reschedule " in f" {normalized} "
        or " move " in f" {normalized} "
    )

    if not (is_cancel or is_move):
        return False, None

    times = _extract_calendar_time_mentions(
        command
    )

    # "delete/cancel the one at 4 PM"
    if is_cancel and not is_move and times:
        source_hour, source_minute = times[0]

        events = _find_calendar_events_by_day_and_time(
            command,
            source_hour,
            source_minute,
        )

        if events is None:
            return True, "I couldn't access your calendar right now."

        if not events:
            return (
                True,
                "I couldn't find an appointment at that time. Nothing was changed.",
            )

        if len(events) > 1:
            choices = "; ".join(
                _describe_calendar_match(event)
                for event in events[:3]
            )

            return (
                True,
                f"I found multiple appointments at that time: {choices}. "
                "Please tell me which one you mean.",
            )

        event = events[0]

        pending_action = {
            "type": "cancel_calendar",
            **event,
        }

        return (
            True,
            f"I found {_describe_calendar_match(event)}. "
            "Do you want me to cancel it?",
        )

    # "reschedule my 3:15 appointment to 4 PM"
    if is_move and len(times) >= 2:
        source_hour, source_minute = times[0]
        dest_hour, dest_minute = times[-1]

        events = _find_calendar_events_by_day_and_time(
            command,
            source_hour,
            source_minute,
        )

        if events is None:
            return True, "I couldn't access your calendar right now."

        if not events:
            return (
                True,
                "I couldn't find an appointment at the original time. "
                "Nothing was changed.",
            )

        if len(events) > 1:
            choices = "; ".join(
                _describe_calendar_match(event)
                for event in events[:3]
            )

            return (
                True,
                f"I found multiple appointments at the original time: {choices}. "
                "Please tell me which one you mean.",
            )

        event = events[0]

        new_start = _datetime_on_requested_day(
            command,
            dest_hour,
            dest_minute,
            fallback_date=event["start"],
        )

        pending_action = {
            "type": "reschedule_calendar",
            **event,
            "new_start": new_start,
        }

        return (
            True,
            f"I found {_describe_calendar_match(event)}. "
            f"I'll move it to {_format_confirmation_datetime(new_start)}. "
            "Do you want me to do that?",
        )

    return False, None


def handle_calendar_write_request(text):

    global pending_action

    command = clean_transcription(
        text
    )

    lower = command.lower().strip()

    normalized = re.sub(
        r"^(?:can you|could you|would you|please|jarvis|hey jarvis)\s+",
        "",
        lower,
        flags=re.IGNORECASE,
    ).strip()

    # One destructive action at a time. Do not guess how to sequence
    # "delete X and reschedule Y" in a single utterance.
    if (
        ("delete" in normalized or "cancel" in normalized)
        and ("reschedule" in normalized or "move" in normalized)
    ):
        return (
            True,
            "I heard two calendar changes in one command. "
            "Please give me the delete and reschedule commands one at a time.",
        )

    calendar_nouns = (
        "appointment", "meeting", "event", "calendar", "reminder",
        "call", "lunch", "dinner", "check-in", "check in",
    )
    has_calendar_noun = any(noun in normalized for noun in calendar_nouns)
    has_calendar_time = (
        bool(re.search(
            r"\b(?:today|tomorrow|tonight|monday|tuesday|wednesday|thursday|"
            r"friday|saturday|sunday)\b",
            normalized,
            flags=re.IGNORECASE,
        ))
        or bool(re.search(
            r"\b\d{1,2}(?:(?:[:.]|\s+)\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b",
            normalized,
            flags=re.IGNORECASE,
        ))
    )

    create_intent = (
        normalized.startswith("schedule ")
        or "schedule a meeting" in normalized
        or "set up a meeting" in normalized
        or (
            normalized.startswith(("add ", "create ", "make ", "put ", "leave "))
            and has_calendar_noun
            and has_calendar_time
        )
    )

    cancel_intent = (
        normalized.startswith("cancel ")
        or normalized.startswith("delete ")
        or "cancel my " in normalized
        or "delete my " in normalized
        or " cancel " in f" {normalized} "
        or " delete " in f" {normalized} "
    )

    move_intent = (
        normalized.startswith("move ")
        or normalized.startswith("reschedule ")
        or " reschedule " in f" {normalized} "
        or " move " in f" {normalized} "
    )

    if not (
        create_intent
        or cancel_intent
        or move_intent
    ):
        return False, None

    # Try explicit source/destination-time handling first.
    time_handled, time_answer = (
        _try_time_based_calendar_change(
            command,
            normalized,
        )
    )

    if time_handled:
        return True, time_answer

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    if create_intent:

        start = _parse_calendar_datetime(
            command
        )

        if start is None:
            return (
                True,
                (
                    "I can schedule that, but I need a day and time. "
                    "For example: schedule a test appointment tomorrow at 3 15 P M."
                ),
            )

        duration = _parse_duration_minutes(
            command
        )

        person_name = _extract_meeting_person(
            command
        )

        attendee = None

        if person_name:
            attendee, error = _resolve_one_person(
                person_name
            )

            if error:
                return True, error

        subject = _extract_calendar_subject(
            command,
            attendee["name"] if attendee else "",
        )

        pending_action = {
            "type": "create_calendar",
            "subject": subject,
            "start": start,
            "duration": duration,
            "attendee_name": attendee["name"] if attendee else "",
            "attendee_email": attendee["email"] if attendee else "",
        }

        attendee_text = (
            f" with {attendee['name']}"
            if attendee
            else ""
        )

        invite_text = (
            " This will send them a meeting invitation."
            if attendee
            else ""
        )

        return (
            True,
            (
                f"I have {subject}{attendee_text} ready for "
                f"{_format_confirmation_datetime(start)}, "
                f"for {duration} minutes."
                f"{invite_text} Do you want me to create it?"
            ),
        )

    # --------------------------------------------------------
    # BULK CANCEL
    # --------------------------------------------------------
    cancel_all_day = (
        cancel_intent
        and any(
            phrase in normalized
            for phrase in (
                "all my appointments",
                "all appointments",
                "all of my appointments",
                "all of those appointments",
                "everything on my calendar",
                "everything on the calendar",
                "everything from my calendar",
                "clear my calendar",
                "clear the calendar",
            )
        )
    )

    cancel_multiple_matching = (
        cancel_intent
        and (
            normalized.startswith("cancel both ")
            or normalized.startswith("delete both ")
            or " both my " in f" {normalized} "
            or " and also " in normalized
        )
    )

    if cancel_all_day or cancel_multiple_matching:

        if cancel_all_day:
            events = find_all_calendar_events_in_window(
                command
            )
        else:
            events = find_matching_events_for_bulk_cancel(
                command
            )

        if events is None:
            return True, "I couldn't access your calendar right now."

        if not events:
            return (
                True,
                "I couldn't find matching appointments. Nothing was changed.",
            )

        summary = "; ".join(
            _describe_calendar_match(event)
            for event in events[:5]
        )

        more = (
            f"; and {len(events) - 5} more"
            if len(events) > 5
            else ""
        )

        pending_action = {
            "type": "bulk_cancel_calendar",
            "events": events,
        }

        return (
            True,
            f"I found {len(events)} appointments: {summary}{more}. "
            "Do you want me to delete all of them?"
        )

    # --------------------------------------------------------
    # TITLE-BASED CANCEL / MOVE FALLBACK
    # --------------------------------------------------------
    matches = find_calendar_events_for_change(
        command
    )

    if matches is None:
        return True, "I couldn't access your calendar right now."

    if not matches:
        return (
            True,
            "I couldn't find a matching calendar event. Nothing was changed.",
        )

    if len(matches) > 1:
        choices = "; ".join(
            _describe_calendar_match(item)
            for item in matches[:3]
        )

        return (
            True,
            f"I found multiple matching events: {choices}. "
            "Please tell me which one you mean.",
        )

    event = matches[0]

    if cancel_intent:
        pending_action = {
            "type": "cancel_calendar",
            **event,
        }

        return (
            True,
            f"I found {_describe_calendar_match(event)}. "
            "Do you want me to cancel it?",
        )

    new_start = _parse_calendar_datetime(
        command
    )

    if new_start is None:
        return (
            True,
            "I found the event, but I need the new day and time.",
        )

    # If the user only supplied a new clock time, keep the event
    # on its existing calendar date.
    if (
        event.get("start") is not None
        and not _command_has_explicit_calendar_day(command)
    ):
        new_start = event["start"].replace(
            hour=new_start.hour,
            minute=new_start.minute,
            second=0,
            microsecond=0,
        )

    pending_action = {
        "type": "reschedule_calendar",
        **event,
        "new_start": new_start,
    }

    return (
        True,
        f"I found {_describe_calendar_match(event)}. "
        f"I'll move it to {_format_confirmation_datetime(new_start)}. "
        "Do you want me to do that?",
    )




def create_outlook_calendar_item(action):

    result = _run_outlook_worker(
        {
            "op": "create",
            "subject": action["subject"],
            "start": action["start"].isoformat(),
            "duration": int(
                action.get("duration", 30)
                or 30
            ),
            "attendee_email": action.get(
                "attendee_email",
                "",
            ),
        }
    )

    if not result.get("ok"):

        if result.get("timeout"):
            return (
                False,
                "Outlook took too long to respond, so I stopped the calendar action.",
            )

        return (
            False,
            "I couldn't create the calendar event.",
        )

    if result.get("sent_invite"):
        return (
            True,
            f"I scheduled {action['subject']} and sent the meeting invitation.",
        )

    return (
        True,
        f"I added {action['subject']} to your calendar.",
    )


def execute_pending_action():

    global pending_action

    action = pending_action

    # Clear BEFORE executing so a retry cannot accidentally fire twice.
    pending_action = None

    if not action:
        return (
            False,
            "There isn't an action waiting for confirmation.",
        )

    if action["type"] == "restart_jarvis_stack":
        return _schedule_jarvis_stack_restart()

    if action["type"] == "send_email":

        if action.get("suspicious_domain"):
            return (
                False,
                "I canceled that send because the email domain looked unusual.",
            )

        ok = send_work_email(
            action["recipient_email"],
            action["subject"],
            action["body"],
        )

        if ok:
            return (
                True,
                f"I sent the email to {action['recipient_name']}.",
            )

        return (
            False,
            "I couldn't send the email.",
        )

    if action["type"] == "create_calendar":

        return create_outlook_calendar_item(
            action
        )

    if action["type"] == "cancel_calendar":

        return execute_calendar_cancel(
            action
        )

    if action["type"] == "bulk_cancel_calendar":

        return execute_bulk_calendar_cancel(
            action
        )

    if action["type"] == "reschedule_calendar":

        return execute_calendar_reschedule(
            action
        )

    return (
        False,
        "I don't recognize the pending action.",
    )


def handle_pending_confirmation(text):

    global pending_action

    if pending_action is None:
        return False, None

    # A pending reschedule can be corrected conversationally before
    # confirmation. Example:
    # "Keep it on Saturday, but at 4 PM."
    if pending_action.get("type") == "reschedule_calendar":

        correction = clean_transcription(text)
        correction_lower = correction.lower()

        mentions_day = _command_has_explicit_calendar_day(
            correction
        )

        correction_times = _extract_calendar_time_mentions(
            correction
        )

        looks_like_correction = (
            mentions_day
            or bool(correction_times)
            or "keep it" in correction_lower
            or "instead" in correction_lower
            or "change it" in correction_lower
        )

        if looks_like_correction and not _is_yes(correction) and not _is_no(correction):

            current_start = pending_action["new_start"]

            if correction_times:
                new_hour, new_minute = correction_times[-1]
            else:
                new_hour = current_start.hour
                new_minute = current_start.minute

            if mentions_day:
                corrected_start = _datetime_on_requested_day(
                    correction,
                    new_hour,
                    new_minute,
                    fallback_date=pending_action.get("start"),
                )
            else:
                # No new day was spoken: preserve the pending/original date.
                base = (
                    pending_action.get("start")
                    or current_start
                )

                corrected_start = base.replace(
                    hour=new_hour,
                    minute=new_minute,
                    second=0,
                    microsecond=0,
                )

            pending_action["new_start"] = corrected_start

            return (
                True,
                (
                    f"Okay. I'll keep {pending_action['subject']} on "
                    f"{_format_confirmation_datetime(corrected_start)}. "
                    "Do you want me to make that change?"
                ),
            )

    if _is_yes(text):

        print(
            "Confirmation accepted."
        )

        success, answer = execute_pending_action()

        return True, answer

    if _is_no(text):

        pending_action = None

        print(
            "Confirmation declined."
        )

        return (
            True,
            "Okay. I canceled it.",
        )

    # While a destructive/external action is waiting, do not reinterpret
    # unrelated speech as a new command.
    return (
        True,
        (
            "I still need a yes or no before I do that. "
            "Say yes to confirm or no to cancel."
        ),
    )


def expire_pending_action():

    global pending_action

    if pending_action is not None:
        pending_action = None
        print(
            "Confirmation timed out. Pending action canceled."
        )


# ============================================================
# SHORT / ORPHANED FRAGMENT GUARD
# ============================================================


def _github_repo_from_command(command):
    text = clean_transcription(command)
    m = re.search(
        r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[\s/]|$)",
        text, flags=re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.search(
        r"\b(?:github\s+(?:repo|repository|project)|repo(?:sitory)?\s+on\s+github)\s+"
        r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b",
        text, flags=re.IGNORECASE,
    )
    return m.group(1) if m else None


def _materialize_github_project(repo_slug):
    repo_slug = str(repo_slug or "").strip().strip("/")
    if "/" not in repo_slug:
        return None, "Invalid GitHub repository."
    repo_name = repo_slug.split("/")[-1]
    os.makedirs(MANAGED_PROJECTS_ROOT, exist_ok=True)
    destination = os.path.join(MANAGED_PROJECTS_ROOT, repo_name)
    if os.path.isdir(destination):
        return destination, None
    gh = shutil.which("gh")
    git = shutil.which("git")
    if not gh and not git:
        return None, "GitHub CLI or Git is required to clone repositories."
    try:
        args = [gh, "repo", "clone", repo_slug, destination] if gh else [
            git, "clone", f"https://github.com/{repo_slug}.git", destination
        ]
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=240
        )
        if result.returncode != 0:
            detail=(result.stderr or result.stdout or "").strip()[-700:]
            return None, f"Clone failed: {detail}"
        return destination, None
    except Exception as exc:
        return None, f"Clone failed: {exc}"


def _resolve_project_from_command(command):
    lower = command.lower()

    github_repo = _github_repo_from_command(command)
    if github_repo:
        path, error = _materialize_github_project(github_repo)
        if path:
            return path, github_repo
        if error:
            log(error)

    for alias, path in sorted(PROJECT_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in lower:
            candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
            if os.path.isdir(candidate):
                return candidate, alias

    path_match = re.search(r"([a-zA-Z]:\\[^\n\r\"']+)", command)
    if path_match:
        candidate = path_match.group(1).strip(' "\'.,')
        candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(candidate)))
        if os.path.isdir(candidate):
            return candidate, candidate

    named = _extract_named_project(command)
    if named:
        discovered = _discover_project_by_name(named)
        if discovered:
            return discovered, named

    return None, None

LAST_CODING_CONTEXT = {
    "command": "",
    "project_path": "",
    "project_name": "",
    "timestamp": 0.0,
}

def _looks_like_coding_followup(command):
    """Recognize short repair follow-ups after a coding task."""
    lower = clean_transcription(command).strip().lower()
    if not LAST_CODING_CONTEXT.get("project_path"):
        return False
    if time.time() - float(LAST_CODING_CONTEXT.get("timestamp") or 0) > 1800:
        return False
    followups = (
        "fix it", "fix that", "repair it", "repair that", "debug it",
        "debug that", "find the issue", "find issue", "find the problem",
        "it's not working", "its not working", "it is not working",
        "doesn't work", "doesnt work", "get it working", "make it work",
        "work on it", "work on that", "try again", "keep working on it",
        "figure out why", "figure out the issue",
    )
    return any(p in lower for p in followups)

def _looks_like_coding_request(command):

    lower = command.lower()

    coding_phrases = (
        "bug",
        "bugs",
        "debug",
        "edit the ui",
        "edit ui",
        "modify the ui",
        "modify ui",
        "change the ui",
        "change ui",
        "update the ui",
        "update ui",
        "redesign the ui",
        "redesign ui",
        "dashboard ui",
        "command center ui",
        "ui panel",
        "ui panels",
        "dashboard panel",
        "dashboard panels",
        "make the panels",
        "make all the panels",
        "make panels",
        "resize the panels",
        "resize panels",
        "adjustable panels",
        "make them adjustable",
        "make it adjustable",
        "draggable panels",
        "make them draggable",
        "make it draggable",
        "move the panels",
        "move panels",
        "change their size",
        "change the size",
        "frontend",
        "front end",
        "layout",
        "fix the code",
        "fix this code",
        "fix my code",
        "edit the code",
        "edit this code",
        "change the code",
        "modify the code",
        "implement this feature",
        "implement a feature",
        "add this feature",
        "add a feature",
        "make this change",
        "update the project",
        "edit the project",
        "fix the project",
        "fix this project",
        "fix jarvis",
        "repair jarvis",
        "work on jarvis",
        "improve jarvis",
        "improve yourself",
        "make yourself better",
        "upgrade yourself",
        "work on yourself",
        "optimize yourself",
        "work on the project",
        "inspect the project",
        "inspect the code",
        "review the code",
        "check the code",
        "code review",
        "refactor",
        "run the tests",
        "run tests",
        "build the project",
        "build a jarvis desktop dashboard",
        "build the jarvis desktop dashboard",
        "jarvis desktop dashboard",
        "jarvis dashboard",
        "desktop dashboard",
        "build the ui",
        "build a ui",
        "flutter analyze",
        "py_compile",
        "syntax check",
    )

    if any(phrase in lower for phrase in coding_phrases):
        return True

    jarvis_targets = (
        "jarvis", "yourself", "your system", "your ui", "your dashboard",
        "your command center", "your air touch", "air touch", "gesture lab",
        "wake word", "voice engine", "sidebar", "left menu", "left sidebar",
    )
    development_verbs = (
        "fix", "change", "edit", "modify", "update", "add", "remove",
        "improve", "repair", "implement", "build", "create", "redesign",
        "refactor", "debug", "test", "optimize", "make it", "make the",
        "get it working", "make sure",
    )
    if (any(t in lower for t in jarvis_targets)
            and any(v in lower for v in development_verbs)):
        return True

    code_targets = (
        "codebase", "source code", "source files", "project files",
        "live codebase", "live source", "repository", " repo ",
        ".py", ".js", ".html", ".css", ".dart", ".cpp", ".cs",
    )
    code_actions = (
        "inspect", "review", "analyze", "analyse", "fix", "repair", "edit",
        "change", "modify", "improve", "implement", "refactor", "test",
        "validate", "debug", "find one", "make the change", "make a change",
    )
    explicit_windows_path = bool(re.search(r"\b[a-z]:\\", command, flags=re.IGNORECASE))
    if (
        (any(target in lower for target in code_targets) or explicit_windows_path)
        and any(action in lower for action in code_actions)
    ):
        return True

    if any(phrase in lower for phrase in (
        "find one small safe improvement",
        "find a small safe improvement",
        "make one small safe improvement",
        "inspect your own live codebase",
        "inspect my live codebase",
    )):
        return True

    # Natural-language UI edit requests often do not contain the words
    # "code", "project", or "Jarvis". Treat a command as a coding task when
    # it combines a software/UI target with an edit verb.
    software_targets = (
        "ui", "dashboard", "command center", "panel", "panels",
        "widget", "widgets", "sidebar", "frontend", "front end",
        "layout", "button", "buttons", "hud",
    )
    edit_verbs = (
        "make", "change", "edit", "modify", "update", "resize",
        "move", "add", "remove", "fix", "redesign", "adjust",
        "create", "implement", "build",
    )

    return (
        any(target in lower for target in software_targets)
        and any(re.search(rf"\b{re.escape(verb)}\b", lower) for verb in edit_verbs)
    )


def _coding_request_is_read_only(command):

    lower = command.lower()

    return any(
        phrase in lower
        for phrase in (
            "do not change anything",
            "don't change anything",
            "dont change anything",
            "don't edit anything",
            "do not edit anything",
            "read only",
            "read-only",
            "inspect only",
            "just inspect",
            "only inspect",
            "tell me what you find",
        )
    )


def _coding_request_needs_confirmation(command):
    lower = clean_transcription(command).lower().strip()
    lower = re.sub(
        r"^(?:deploy|deploying|launch|launching|start|starting|send|sending)\s+(?:(?:an|a|another)\s+)?agent\b",
        "agent",
        lower,
        flags=re.IGNORECASE,
    )
    dangerous = (
        "force push", "force-push", "push --force", "git reset --hard",
        "clean -fd", "delete the repo", "delete repository", "delete the project",
        "delete branch", "remove branch", "rotate credential",
        "change api key", "change the api key", "change secret", "update secret",
        "overwrite remote history", "delete remote",
    )
    return any(p in lower for p in dangerous)


def handle_ai_provider_request(text):
    command=clean_transcription(text)
    provider,task=extract_provider_request(command)
    if provider is None:
        lower=command.lower().strip()
        if lower in {"what ai providers are available","what ai models are available","which ai providers are configured","which ai is configured","ai provider status"}:
            status=provider_status()
            pieces=["Local Qwen is online." if status.get("qwen") else "Local Qwen is offline.", "Gemini through Hermes is available."]
            pieces.append("OpenAI is configured." if status.get("openai") else "OpenAI still needs an API key.")
            pieces.append("Claude is configured." if status.get("claude") else "Claude still needs an Anthropic API key.")
            return True," ".join(pieces)
        return False,None
    if not task:return True,f"Tell me what you want {provider} to do."
    if _looks_like_coding_request(task):
        if _coding_request_needs_confirmation(task):
            return True,(
                "That coding request includes a destructive or sensitive action. "
                "Ordinary edits/tests are allowed, but force-pushes, project deletion, and credential changes require confirmation."
            )
        project_path,_=_resolve_project_from_command(task)
        if project_path is None and any(p in task.lower() for p in ("jarvis","yourself","your code","your project","this project")):
            project_path=SELF_WORKSPACE
        if project_path is None:
            return True,"Which project should that provider work on? Give me its local path/name or GitHub URL."
        started,message=_start_background_agent(command)
        return True,message
    if provider=="gemini":return True,ask_hermes(task)
    if provider=="qwen" and qwen_project_busy.is_set():
        return True,(
            "Local Qwen is busy building a project right now. "
            "Use AUTO for an immediate Hermes fallback, or wait for the Qwen project to finish."
        )
    print();print(f"Jarvis is asking {provider.title()}...")
    started=time.perf_counter()
    ok,answer=ask_provider(provider,task,JARVIS_INSTRUCTIONS)
    print(f"{provider.title()} response: {time.perf_counter()-started:.1f}s")
    return True,answer


def _restart_after_success_authorized(command):
    lower = clean_transcription(command).lower()
    if _restart_explicitly_forbidden(lower):
        return False

    restart_terms = (
        "shutdown and restart all systems",
        "shut down and restart all systems",
        "shutdown and reboot all systems",
        "shut down and reboot all systems",
        "restart all systems",
        "reboot all systems",
        "restart everything",
        "reboot everything",
        "then restart",
        "then reboot",
    )
    completion_terms = (
        "when you're done", "when youre done", "when your done",
        "when finished", "after you finish", "after finishing",
        "after the edit", "after editing", "after the changes",
        "if validation passes", "if tests pass", "after tests pass",
        "once you're done", "once youre done",
    )
    return (
        any(term in lower for term in restart_terms)
        and any(term in lower for term in completion_terms)
    )


def _mark_latest_agent_restart_after_success():
    with agent_jobs_lock:
        if not agent_jobs:
            return None
        job_id = max(agent_jobs)
        job = agent_jobs.get(job_id)
        if not job:
            return None
        job["restart_after_success"] = True
        job["restart_authorized_at"] = datetime.now().isoformat(timespec="seconds")
    _save_agent_jobs()
    return job_id


def handle_direct_coding_request(text):
    command = clean_transcription(text).strip()
    followup = _looks_like_coding_followup(command)

    if not _looks_like_coding_request(command) and not followup:
        return False, None

    if _coding_request_needs_confirmation(command):
        return True, (
            "That coding request includes a destructive or sensitive action. "
            "Ordinary local edits and tests are allowed, but force-pushes, "
            "project deletion, and credential changes require explicit confirmation."
        )

    project_path, project_name = _resolve_project_from_command(command)

    if project_path is None and followup:
        project_path = LAST_CODING_CONTEXT.get("project_path") or None
        project_name = LAST_CODING_CONTEXT.get("project_name") or "Jarvis"

    if project_path is None:
        lower = f" {command.lower()} "
        if any(p in lower for p in (
            " yourself ", " your code ", " your project ", " jarvis ",
            " this project ", " the ui ", " ui ", " dashboard ",
            " command center ", " panel ", " panels ", " widget ",
            " widgets ", " sidebar ", " hud "
        )):
            project_path = SELF_WORKSPACE
            project_name = "Jarvis"
        else:
            return True, (
                "Which project should I work on? Give me its name, "
                "full local path, or GitHub repository URL."
            )

    read_only = _coding_request_is_read_only(command)
    provider, _task = extract_provider_request(command)
    # Free-first coding policy: explicit provider wins. Otherwise prefer NVIDIA
    # NIM when configured, then Gemini/Hermes. Paid OpenAI is never the implicit default.
    if not provider:
        if provider_status().get("nvidia"):
            provider = "nvidia"
        else:
            provider = "gemini"
    auto_restart = _restart_after_success_authorized(command)

    scoped = (
        f"using {provider} work on project {project_path}. "
        + (
            "READ ONLY. Do not change anything. "
            if read_only
            else "Local source edits and tests are authorized. "
        )
        + "Treat current files on disk as the source of truth. Inspect first, "
          "preserve unrelated changes, use backups, complete exactly the user's "
          "requested coding/UI task, run appropriate validation, inspect the final "
          "diff, and report exact files changed and test results. "
          "Never modify secrets/credentials or force-push. "
    )

    if auto_restart:
        scoped += (
            "The user already authorized a full Jarvis restart AFTER successful "
            "validation. Do NOT perform the restart from inside the coding agent. "
            "Finish the edit and validation normally; the Jarvis orchestrator will "
            "handle the restart after your successful result. "
        )

    scoped += "User request: " + command

    # Pass the untouched user command to the safety classifier. The scoped
    # prompt intentionally contains prohibitions like "Never ... force-push";
    # those instructions must never be mistaken for requested actions.
    LAST_CODING_CONTEXT.update({
        "command": command,
        "project_path": project_path,
        "project_name": project_name,
        "timestamp": time.time(),
    })

    started, message = _start_background_agent(
        scoped,
        safety_text=command,
        restart_after_success=auto_restart,
    )

    if started and auto_restart:
        job_id = _mark_latest_agent_restart_after_success()
        if job_id:
            message = (
                f"Agent {job_id} is making that change in the background. "
                "You already authorized the full restart, so if validation passes "
                "I will report what changed and automatically restart all systems."
            )

    return True, message



def handle_dashboard_widget_command(text):

    command = clean_transcription(text).strip()
    lower = command.lower()

    verbs = (
        "show", "open", "pull up", "bring up", "display", "launch",
    )

    if not any(lower.startswith(v) for v in verbs):
        return False, None

    widget_map = (
        (("calculator", "calc"), "calculator", "Opening the calculator widget."),
        (("email", "mail", "inbox", "work email"), "email", "Pulling your work email into view."),
        (("calendar", "schedule"), "calendar", "Pulling your calendar into view."),
        (("agents", "agent activity", "background agents"), "agents", "Showing background agent activity."),
        (("projects", "local projects"), "projects", "Showing your projects."),
        (("controls", "system controls"), "controls", "Opening system controls."),
        (("apps", "applications", "app launcher"), "apps", "Opening the application launcher."),
    )

    for aliases, widget, answer in widget_map:
        if any(alias in lower for alias in aliases):
            request_dashboard_widget(widget)
            return True, answer

    app_map = {
        "word": "word",
        "microsoft word": "word",
        "outlook": "outlook",
        "excel": "excel",
        "powerpoint": "powerpoint",
        "notepad": "notepad",
        "file explorer": "explorer",
        "explorer": "explorer",
        "command prompt": "cmd",
        "terminal": "terminal",
        "settings": "settings",
        "chrome":"chrome","google chrome":"chrome","steam":"steam",
        "visual studio":"visualstudio","vs code":"vscode","visual studio code":"vscode",
        "android studio":"androidstudio","unreal":"unreal","unreal engine":"unreal",
        "blender":"blender","discord":"discord","epic games":"epic","obs":"obs",
    }

    for alias, app_name in app_map.items():
        if alias in lower:
            request_dashboard_widget("launch_app", {"app": app_name})
            return True, f"Opening {alias}."

    return False, None


def handle_orphaned_fragment(text):

    command = clean_transcription(text).strip()
    lower = command.lower().strip(" .?!,")

    if not lower:
        return True, "I didn't catch a complete command."

    confirmation_words = {
        "yes", "yeah", "yep", "no", "nope",
        "confirm", "cancel", "do it", "go ahead",
        "go ahead and do it", "go ahead and make it",
        "send it", "never mind", "nevermind",
    }

    if lower in confirmation_words:
        return (
            True,
            "There isn't anything waiting for confirmation right now.",
        )

    if re.fullmatch(
        r"\d{1,2}(?:(?:[:.]|\s+)\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)",
        lower,
        flags=re.IGNORECASE,
    ):
        return (
            True,
            "I heard the time, but I need the rest of the command too.",
        )

    if re.fullmatch(r"\d{1,2}", lower):
        return (
            True,
            "I heard a number, but I need the complete command.",
        )


    # Random one-word transcriptions are usually clipped/background speech.
    # Do not send them to Hermes as brand-new requests.
    words = re.findall(r"[a-z0-9']+", lower)

    safe_single_word_commands = {
        "mute",
        "unmute",
        "status",
        "help",
        "stop",
    }

    if (
        len(words) == 1
        and words[0] not in safe_single_word_commands
    ):
        return (
            True,
            "I only caught one word. Please say the full command again.",
        )

    if lower in {
        "today", "tomorrow", "tonight",
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
        "morning", "afternoon", "evening",
        "thanks", "thank you", "okay", "ok", "got it",
    }:
        if lower in {"thanks", "thank you", "okay", "ok", "got it"}:
            return True, "You're welcome."

        return (
            True,
            "I heard that, but I need the complete command.",
        )

    # Never send incomplete calendar fragments such as
    # "tomorrow to 4 PM" to Hermes.
    has_date_word = any(
        word in lower
        for word in (
            "today", "tomorrow", "tonight",
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        )
    )

    has_clock_time = bool(
        re.search(
            r"\b\d{1,2}(?:(?:[:.]|\s+)\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b",
            lower,
            flags=re.IGNORECASE,
        )
    )

    has_action_verb = any(
        verb in lower
        for verb in (
            "schedule", "add", "create", "make", "put",
            "cancel", "delete", "move", "reschedule",
        )
    )

    # Only treat a bare date/time fragment as an incomplete calendar command.
    # Ordinary questions such as "what's the weather today?" must continue to
    # Hermes instead of being swallowed by the calendar fragment guard.
    looks_like_question = (
        "?" in command
        or lower.startswith((
            "what ", "what's ", "whats ", "who ", "where ", "when ",
            "why ", "how ", "is ", "are ", "can ", "could ", "tell me ",
            "give me ", "show me ", "search ", "research ", "look up ",
        ))
    )

    non_calendar_topics = (
        "weather", "temperature", "forecast", "news", "sports", "score",
        "stock", "market", "traffic", "sunrise", "sunset",
    )

    if (
        (has_date_word or has_clock_time)
        and not has_action_verb
        and not looks_like_question
        and not any(topic in lower for topic in non_calendar_topics)
    ):
        return (
            True,
            "I heard a calendar time, but I need the complete command.",
        )

    return False, None


# ============================================================
# PROCESS COMMAND
# ============================================================


# ============================================================
# AIR TOUCH LOCAL VOICE COMMANDS
# ============================================================
AIRTOUCH_SETTINGS_FILE = os.path.join(JARVIS_DIR, "airtouch_settings.json")
AIRTOUCH_TARGET_FILE = os.path.join(JARVIS_DIR, "airtouch_target.json")
airtouch_lock = threading.RLock()

def _airtouch_settings():
    defaults = {
        "enabled": False, "cameraEnabled": False, "paused": False,
        "externalControl": False, "sensitivity": 1.0,
    }
    try:
        with open(AIRTOUCH_SETTINGS_FILE, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, dict):
            defaults.update(value)
    except Exception:
        pass
    return defaults

def _reset_airtouch_startup_state():
    """Start each Jarvis voice-engine session with Air Touch powered off."""
    settings = _airtouch_settings()
    settings["enabled"] = False
    settings["cameraEnabled"] = False
    return _save_airtouch_settings(settings)

def _save_airtouch_settings(value):
    try:
        with airtouch_lock:
            temp = AIRTOUCH_SETTINGS_FILE + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
            os.replace(temp, AIRTOUCH_SETTINGS_FILE)
        return True
    except Exception:
        return False

def _airtouch_target():
    try:
        with open(AIRTOUCH_TARGET_FILE, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def _airtouch_ui_action(action, **payload):
    update_live_state(
        ui_action={
            "id": uuid.uuid4().hex,
            "widget": "airtouch",
            "payload": {"type": "airtouch", "action": action, **payload},
        }
    )

def handle_airtouch_command(text):
    lower = clean_transcription(text).strip().lower()

    # IMPORTANT: This handler is for OPERATING Air Touch, not modifying its code.
    # Development/debug language must fall through to the coding router.
    development_words = (
        "fix", "debug", "repair", "change", "edit", "modify", "update",
        "implement", "improve", "code", "codebase", "project", "source",
        "not working", "doesn't work", "doesnt work", "find the issue",
        "find issue", "trace the", "test the change",
    )
    if any(word in lower for word in development_words):
        return False, None

    pointing_phrases = (
        "what am i pointing at", "click this", "open this", "expand this",
        "minimize this", "close this", "move this left", "move this right",
        "scroll this up", "scroll this down", "type here", "read this",
    )
    operational_airtouch = (
        "enable air touch", "turn on air touch", "start air touch",
        "disable air touch", "turn off air touch", "stop air touch",
        "pause air touch", "resume air touch", "unpause air touch",
        "calibrate air touch", "air touch status", "air touch state",
        "open air touch keyboard", "close air touch keyboard",
        "increase air touch sensitivity", "decrease air touch sensitivity",
        "enable desktop control", "disable desktop control",
    )

    if not any(p in lower for p in pointing_phrases + operational_airtouch):
        return False, None

    settings = _airtouch_settings()

    if any(x in lower for x in ("enable air touch", "turn on air touch", "start air touch")):
        settings["enabled"] = True
        settings["cameraEnabled"] = True
        settings["paused"] = False
        _save_airtouch_settings(settings); _airtouch_ui_action("enable")
        return True, "Air Touch enabled. Camera tracking is starting locally."

    if any(x in lower for x in ("disable air touch", "turn off air touch", "stop air touch")):
        settings["enabled"] = False
        settings["cameraEnabled"] = False
        settings["externalControl"] = False
        _save_airtouch_settings(settings); _airtouch_ui_action("disable")
        return True, "Air Touch disabled and camera tracking stopped."

    if "pause air touch" in lower:
        settings["paused"] = True; _save_airtouch_settings(settings); _airtouch_ui_action("pause")
        return True, "Air Touch paused."

    if any(x in lower for x in ("resume air touch", "unpause air touch")):
        settings["paused"] = False; _save_airtouch_settings(settings); _airtouch_ui_action("resume")
        return True, "Air Touch resumed."

    if "calibrate air touch" in lower:
        _airtouch_ui_action("calibrate")
        return True, "Opening Air Touch calibration."

    if "open" in lower and "keyboard" in lower:
        _airtouch_ui_action("keyboard_open")
        return True, "Opening the Air Touch keyboard."

    if "close" in lower and "keyboard" in lower:
        _airtouch_ui_action("keyboard_close")
        return True, "Closing the Air Touch keyboard."

    if "enable desktop control" in lower:
        settings["externalControl"] = True; _save_airtouch_settings(settings)
        return True, "External desktop Air Touch control is active. Use Control Alt Shift X for emergency stop."

    if "disable desktop control" in lower:
        settings["externalControl"] = False; _save_airtouch_settings(settings)
        return True, "External desktop Air Touch control is disabled."

    if "increase" in lower and "sensitivity" in lower:
        settings["sensitivity"] = min(2.0, float(settings.get("sensitivity", 1.0)) + 0.1)
        _save_airtouch_settings(settings); _airtouch_ui_action("sensitivity_up")
        return True, f"Air Touch sensitivity is now {settings['sensitivity']:.1f}."

    if "decrease" in lower and "sensitivity" in lower:
        settings["sensitivity"] = max(0.5, float(settings.get("sensitivity", 1.0)) - 0.1)
        _save_airtouch_settings(settings); _airtouch_ui_action("sensitivity_down")
        return True, f"Air Touch sensitivity is now {settings['sensitivity']:.1f}."

    target = _airtouch_target()
    if "what am i pointing at" in lower:
        if not target:
            return True, "I do not have a stable Air Touch target right now."
        return True, f"You are pointing at {target.get('widget') or target.get('id') or 'a dashboard control'}."

    action_map = {
        "click this": "click", "open this": "open", "expand this": "maximize",
        "minimize this": "minimize", "move this left": "move_left",
        "move this right": "move_right", "scroll this up": "scroll_up",
        "scroll this down": "scroll_down", "type here": "type",
    }
    for phrase, action in action_map.items():
        if phrase in lower:
            if not target:
                return True, "I do not have a stable Air Touch target."
            _airtouch_ui_action("target_action", payload={"action": action})
            return True, f"Acting on {target.get('widget') or target.get('id') or 'the current target'}."

    if "air touch" in lower and any(x in lower for x in ("status", "state", "doing")):
        return True, (
            f"Air Touch is {'enabled' if settings.get('enabled') else 'off'}, "
            f"{'paused' if settings.get('paused') else 'ready'}, and external desktop control is "
            f"{'active' if settings.get('externalControl') else 'off'}."
        )
    return False, None


def _restart_explicitly_forbidden(text):
    lower = clean_transcription(text).lower()
    negative_patterns = (
        r"\bdo\s+not\s+(?:shut\s*down\s+and\s+)?(?:restart|reboot)\b",
        r"\bdon['’]?t\s+(?:shut\s*down\s+and\s+)?(?:restart|reboot)\b",
        r"\bdont\s+(?:shut\s*down\s+and\s+)?(?:restart|reboot)\b",
        r"\bwithout\s+(?:a\s+)?(?:restart|reboot)\b",
        r"\bno\s+(?:restart|reboot)\b",
        r"\bnot\s+(?:restart|reboot)(?:ing)?\b",
        r"\b(?:restart|reboot)\s+later\b",
        r"\b(?:restart|reboot)\s+yet\b",
        r"\bbefore\s+(?:restarting|rebooting)\b",
        r"\bask\s+me\s+before\s+(?:restarting|rebooting)\b",
    )
    return any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in negative_patterns)


def _is_pure_restart_intent(text):
    lower = clean_transcription(text).strip().lower()
    lower = re.sub(r"\s+", " ", lower).strip(" .!?\"'”")

    if _restart_explicitly_forbidden(lower):
        return False

    exact = {
        "shutdown and restart all systems",
        "shut down and restart all systems",
        "shutdown and reboot all systems",
        "shut down and reboot all systems",
        "shutdown and restart everything",
        "shut down and restart everything",
        "shutdown and reboot everything",
        "shut down and reboot everything",
        "shutdown and restart",
        "shut down and restart",
        "shutdown and reboot",
        "shut down and reboot",
        "restart all systems",
        "reboot all systems",
        "restart everything",
        "reboot everything",
        "restart jarvis",
        "reboot jarvis",
        "restart yourself",
        "reboot yourself",
        "hard restart jarvis",
        "hard reboot jarvis",
        "full restart",
        "full system restart",
        "restart",
        "reboot",
    }
    if lower in exact:
        return True

    starts_with_restart = bool(re.match(
        r"^(?:please\s+)?(?:go ahead and\s+)?(?:shut\s*down\s+and\s+)?(?:restart|reboot)\b",
        lower,
    ))
    target = any(x in lower for x in (
        "jarvis", "all systems", "everything", "yourself",
        "command center", "dashboard", "whole system", "full system",
    ))
    return starts_with_restart and target and len(lower.split()) <= 12



def handle_voice_lab_command(text):
    lower = str(text or "").lower().strip()

    m = re.match(r"preview voice provider\s+(\w+)\s+voice\s+([^\s]+)\s+phrase\s+(.+)", str(text), re.IGNORECASE)
    if m:
        provider=m.group(1).lower()
        voice=m.group(2)
        phrase=m.group(3)
        settings=_load_voice_settings()
        settings["provider"]=provider
        if provider=="kokoro":
            settings["kokoro_voice"]=voice
        elif provider=="piper":
            settings["piper_voice"]=voice
        elif provider=="elevenlabs":
            settings["elevenlabs_voice_id"]=voice
        _save_voice_settings(settings)
        ok, detail = preview_voice(provider, voice, phrase)
        return True, "Voice preview played and selected." if ok else f"Voice preview failed: {detail}"

    if any(x in lower for x in ("open voice lab", "voice settings", "voice provider settings")):
        update_live_state("STANDBY", ui_action={"id": uuid.uuid4().hex, "widget": "voice_lab", "payload": {}})
        return True, "Opening Voice Lab."

    if lower.startswith("use kokoro voice "):
        voice = str(text)[len("use kokoro voice "):].strip()
        settings = _load_voice_settings()
        settings["provider"] = "kokoro"
        settings["kokoro_voice"] = voice
        _save_voice_settings(settings)
        return True, f"Kokoro is now the primary voice using {voice}."

    if lower.startswith("use piper voice "):
        voice = str(text)[len("use piper voice "):].strip()
        settings = _load_voice_settings()
        settings["provider"] = "piper"
        settings["piper_voice"] = voice
        _save_voice_settings(settings)
        return True, f"Piper is now the primary voice using {voice}."

    if lower in {"use kokoro", "use kokoro tts"}:
        settings = _load_voice_settings()
        settings["provider"] = "kokoro"
        _save_voice_settings(settings)
        return True, "Kokoro is now the primary voice provider."

    if lower in {"use piper", "use piper tts"}:
        settings = _load_voice_settings()
        settings["provider"] = "piper"
        _save_voice_settings(settings)
        return True, "Piper is now the primary voice provider."

    if lower in {"use elevenlabs", "use eleven labs", "use elevenlabs tts"}:
        settings = _load_voice_settings()
        settings["provider"] = "elevenlabs"
        _save_voice_settings(settings)
        return True, "ElevenLabs is now the primary voice provider."

    return False, None


def handle_restart_command(text):
    if not _is_pure_restart_intent(text):
        return False, None
    success, answer = _schedule_jarvis_stack_restart()
    return True, answer




def _active_agent_status_request(text):
    lower=clean_transcription(text).lower().strip()
    phrases=(
        "what are you doing",
        "what're you doing",
        "what are you working on",
        "what are you working on right now",
        "what is jarvis doing",
        "what's jarvis doing",
        "whats jarvis doing",
        "what's going on",
        "whats going on",
        "are you working",
        "are you still working",
        "how is the task going",
        "how's the task going",
        "hows the task going",
        "current task",
        "current work",
        "work status",
    )
    return any(p in lower for p in phrases)


def _has_active_background_agent():
    with agent_jobs_lock:
        return any(job.get("status") in {"queued","running"} for job in agent_jobs.values())


def _fast_command_response(command, answer, speak=True):
    """Return a quick foreground response without blocking on TTS."""
    print()
    print(f"You: {command}")
    print()
    print(f"Jarvis: {answer}")
    print()
    log(f"USER: {command}")
    log(f"JARVIS: {answer}")
    update_live_state(
        "SPEAKING" if speak else "STANDBY",
        last_user=command,
        last_answer=answer,
        active_command="",
    )
    if speak and answer:
        def _speak_fast():
            try:
                speak_text(_spoken_version(answer))
            except Exception as exc:
                log(f"Fast response speech error: {exc}")
        threading.Thread(
            target=_speak_fast,
            daemon=True,
            name="JarvisFastReplySpeech",
        ).start()
    return answer


def process_command(command):
    # Dashboard metadata is transport control, not user/project requirements. Newer dashboard
    # builds can append these markers to the SAME LINE as the user sentence, so extract our
    # robust inline form before the legacy qwen_model_manager helper and before transcription
    # cleanup can collapse the boundaries.
    command, inline_qwen_profile = _inline_qwen_profile_marker(command)
    command, legacy_qwen_profile = extract_profile_marker(command)
    requested_qwen_profile = inline_qwen_profile or legacy_qwen_profile
    if requested_qwen_profile:
        save_selected_profile(requested_qwen_profile)
    attachment_clean_command, preattached_zip, zip_marker_seen = _first_attached_zip(command)
    command = clean_transcription(attachment_clean_command)

    if zip_marker_seen and preattached_zip is None:
        return _fast_command_response(
            command or "Attached project ZIP",
            "I received a project ZIP marker, but the uploaded ZIP could not be found at the dashboard path. "
            "I will not start a new project from that sentence. Reattach the ZIP and send the request again.",
            speak=False,
        )

    if not command:
        return None

    # Private dashboard control: interrupt the active local-Qwen stream and let
    # the project worker package only its last accepted workspace. This command
    # must return immediately so it never waits behind the project generation.
    if command.strip().lower() == "__jarvis_stop_project_and_checkpoint__":
        outcome = request_project_stop("User pressed STOP + CHECKPOINT in the Jarvis dashboard.")
        stopped_job_id = outcome.get("job_id")
        with agent_jobs_lock:
            live = agent_jobs.get(stopped_job_id) if stopped_job_id is not None else None
            if live and live.get("job_type") == "qwen_project":
                live["status"] = "stopping"
                live["stage"] = "checkpoint"
                live["activity"] = "Stop accepted; saving the best accepted workspace."
            elif not outcome.get("ok"):
                # A very early click can arrive while the worker is still queued.
                queued = next((row for row in agent_jobs.values()
                               if row.get("job_type") == "qwen_project" and row.get("status") == "queued"), None)
                if queued:
                    queued["status"] = "stopped"
                    queued["stage"] = "stopped"
                    queued["activity"] = "Stopped before project generation began; no checkpoint was needed."
                    queued["finished_at"] = datetime.now().isoformat(timespec="seconds")
                    outcome = {"ok": True, "message": queued["activity"], "job_id": queued.get("id")}
        _save_agent_jobs()
        return _fast_command_response(
            "Stop project and save checkpoint",
            str(outcome.get("message") or "Stop request processed."),
            speak=False,
        )

    # v2.74.1 persistent model selector. The dashboard sends this private command
    # immediately when the user changes the dropdown. It only switches the single
    # local llama.cpp model; it never invokes a chat model or silently falls back.
    if command.strip().lower() == "__jarvis_switch_qwen_only__":
        selection = normalize_profile(requested_qwen_profile or "auto")
        save_selected_profile(selection)
        if qwen_project_busy.is_set():
            return _fast_command_response(
                "Local Qwen model selection",
                f"{selection.upper()} is saved. The current Qwen project is still running, so I will switch models after it finishes rather than interrupting it.",
                speak=False,
            )
        if selection == "auto":
            # AUTO is a hybrid project policy. Keep the fast 9B resident for ordinary
            # conversation/standby; project architecture will promote to the new
            # Qwen3.8 27B Aggressive Q2_K_P specialist automatically.
            ok, detail = ensure_qwen_profile("auto", persist_selection=False)
            if ok:
                detail = (f"AUTO HYBRID selected; {active_profile()} is ready. Qwen3.5 9B is the fast standby/worker; "
                          "the new Qwen3.8 27B HauhauCS Aggressive Q2_K_P is used automatically "
                          "for architecture, hard diagnostics, repeated repairs, subsystem reconciliation, and global convergence.")
        else:
            ok, detail = ensure_qwen_profile(selection)
        return _fast_command_response(
            "Local Qwen model selection",
            detail if ok else f"Model selection was saved, but the switch did not complete: {detail}",
            speak=False,
        )

    # Any new command is an instruction to yield the floor immediately.
    interrupt_current_speech()

    # STATUS MUST STAY RESPONSIVE WHILE AGENTS WORK.
    # Do this before foreground_command_lock so "what are you doing?" can be
    # answered even if another foreground/API operation is still busy.
    if _active_agent_status_request(command):
        if _has_active_background_agent():
            return _fast_command_response(command, _agent_status_text())
        # If there is no active agent, still give a useful immediate answer.
        return _fast_command_response(
            command,
            "I don't have a background coding task running right now. I'm ready for your next command.",
        )

    # DASHBOARD FILE ATTACHMENTS / EXISTING PROJECT ZIP EDITOR (v2.62).
    # The dashboard stores uploads locally and injects opaque file markers into the
    # IPC command.  A ZIP is routed to the same background Qwen project worker, but
    # Any attached ZIP is deterministically routed to the EXISTING-project editor. It is never
    # sent through new-project generation; original structure is snapshotted and preserved.
    clean_attachment_command, attached_zip = command, preattached_zip
    if attached_zip is not None:
        started, message = _start_qwen_project_job(clean_attachment_command, source_zip=attached_zip, qwen_profile=requested_qwen_profile or "auto")
        return AttachmentCommandResult(_fast_command_response(clean_attachment_command, message), started)

    # DOWNLOADABLE PROJECT GENERATION RUNS AS A TRUE BACKGROUND JOB.
    # The local Qwen server has one slot, but Jarvis itself remains responsive.
    if wants_project_zip(command):
        started, message = _start_qwen_project_job(command, qwen_profile=requested_qwen_profile or "auto")
        return _fast_command_response(command, message)

    # DIRECT CODING/EDIT TASKS ALSO DISPATCH BEFORE THE FOREGROUND LOCK.
    # This prevents a Jarvis self-edit request from falling through to Hermes
    # and sitting in THINKING instead of launching an Agent.
    coding_followup = _looks_like_coding_followup(command)
    if _looks_like_coding_request(command) or coding_followup:
        handled, response = handle_direct_coding_request(command)
        if handled:
            return _fast_command_response(command, response or "The coding task could not be started.")

    # "stop" is a transport-level command. It must not generate another spoken
    # response or route through Hermes, because that would restart TTS.
    if _is_stop_speech_command(command):
        print()
        print(f"You: {command}")
        print("Jarvis: Speech stopped.")
        log(f"USER: {command}")
        log("JARVIS: Speech stopped.")
        update_live_state(
            "LISTENING" if FOLLOW_UP_MODE else "STANDBY",
            last_user=command,
            last_answer="Speech stopped.",
            active_command="",
        )
        return "Speech stopped."

    # Threaded dashboard requests are serialized here. The newer request has
    # already cancelled existing audio, and now waits until the older command
    # finishes its current non-cancellable API/tool operation.
    with foreground_command_lock:
        print()
        print(f"You: {command}")
        log(f"USER: {command}")
        update_live_state(
            "THINKING",
            last_user=command,
            active_command=command,
        )

        # v2.74 dashboard model selector: one RTX 4070 cannot keep both GGUFs
        # resident, so switch the single llama.cpp server before provider routing.
        # Never interrupt an active background Qwen project.
        qwen_switch_error = ""
        if requested_qwen_profile and not qwen_project_busy.is_set():
            switch_ok, switch_detail = ensure_qwen_profile(requested_qwen_profile)
            if not switch_ok:
                qwen_switch_error = switch_detail
                log(f"Qwen model switch failed: {switch_detail}")

        # Route actionable coding/edit requests BEFORE generic restart intent.
        # A composite command such as "edit the UI, test it, then restart all
        # systems" is one workflow: the coding agent owns the edit/test phase
        # and the orchestrator performs the already-authorized restart only
        # after successful validation. Pure restart commands still fall through
        # to handle_restart_command below.
        handlers = [
            handle_pending_confirmation,
            # Coding/edit requests must get first shot before operational feature
            # handlers. Otherwise a sentence like "fix Air Touch" gets mistaken
            # for an Air Touch status/control command.
            handle_self_improvement_command,
            handle_airtouch_command,
            handle_background_agent_command,
            handle_ai_provider_request,
            handle_voice_lab_command,
            handle_restart_command,
            handle_email_reply_request,
            handle_email_write_request,
            handle_calendar_write_request,
            handle_browser_command,
            handle_pc_automation_command,
            handle_dashboard_widget_command,
            handle_local_command,
            handle_fast_email_command,
            handle_fast_calendar_command,
            handle_fast_contact_command,
            handle_orphaned_fragment,
        ]

        answer = None

        if qwen_switch_error and requested_qwen_profile in {"8b", "9b35", "27b38q2", "27b"}:
            answer = qwen_switch_error

        for handler in handlers:
            if answer:
                break
            handled, response = handler(command)
            if handled:
                answer = response
                break

        if not answer:
            # Local-first conversational routing. During a background Qwen project
            # build, do NOT queue normal chat behind the one local model slot; use
            # Hermes immediately so Jarvis stays conversational.
            if qwen_project_busy.is_set():
                log("Qwen is busy with a background project; AUTO routed this turn to Hermes.")
                answer = ask_hermes(command)
            else:
                ok, qwen_answer = ask_provider("qwen", command, "")
                if ok and qwen_answer:
                    answer = qwen_answer
                else:
                    if qwen_answer:
                        log(f"Qwen fallback reason: {qwen_answer}")
                    answer = ask_hermes(command)

        if not answer:
            return None

        print()
        print(f"Jarvis: {answer}")
        print()

        log(f"JARVIS: {answer}")
        update_live_state(
            "SPEAKING",
            last_answer=answer,
            active_command="",
        )

        speak_text(_spoken_version(answer))
        return answer





# ============================================================
# VOICE ENGINE HEALTH
# ============================================================
VOICE_HEALTH_FILE = os.path.join(JARVIS_DIR, "voice_health.json")

def _write_voice_health(state="online", detail=""):
    try:
        payload = {
            "pid": os.getpid(),
            "state": state,
            "detail": detail,
            "jarvis_root": JARVIS_DIR,
            "python": sys.executable,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        tmp = VOICE_HEALTH_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.replace(tmp, VOICE_HEALTH_FILE)
    except Exception:
        pass


# ============================================================
# HERMES HEALTH CHECK
# ============================================================

def test_hermes_api():

    headers = {
        "Authorization":
            f"Bearer {HERMES_API_KEY}",
    }


    try:

        response = requests.get(
            HERMES_MODELS_URL,
            headers=headers,
            timeout=10,
        )


        if response.status_code != 200:

            print(
                "Hermes API returned "
                f"{response.status_code}."
            )

            return False


        # Verify our permanent Jarvis session exists too.
        session_response = requests.get(
            HERMES_SESSION_INFO_URL,
            headers=headers,
            timeout=10,
        )


        if session_response.status_code != 200:

            print()
            print(
                "Hermes is online, but the "
                "permanent Jarvis session could "
                "not be found."
            )

            print(
                "Session ID:"
            )

            print(
                HERMES_SESSION_ID
            )

            return False


        print(
            "Hermes API connected."
        )

        print(
            "Persistent Jarvis session connected."
        )

        return True


    except requests.RequestException:

        print()
        print(
            "Hermes API is not running."
        )

        print()
        print(
            "Start it in another "
            "PowerShell window with:"
        )

        print()
        print(
            "    hermes gateway"
        )

        print()

        return False


# ============================================================
# MAIN LOOP
# ============================================================

def run_jarvis():

    print()
    print("=" * 68)
    print("JARVIS ONLINE")
    print("=" * 68)
    print()

    print(
        'Wake phrase: "Hey Jarvis"'
    )

    print(
        "Persistent memory: ON"
    )

    print(
        "Persistent conversation: ON"
    )

    print(
        "Follow-up conversation: "
        + (
            "ON"
            if FOLLOW_UP_MODE
            else "OFF"
        )
    )

    print(
        "Confirmed email/calendar actions: ON"
    )

    print(
        "Project coding/debugging: ON"
    )

    if _v42_runtime is not None:
        try:
            print("Developer runtime: " + _v42_runtime.startup_summary(wait_seconds=0.2))
        except Exception:
            print("Developer runtime: V42.3 progressive convergence command broker ON")
    else:
        print("Developer runtime: capability scan will initialize on first project")

    _provider_state = provider_status()
    print(
        f"AI providers: Qwen {'ON' if _provider_state.get('qwen') else 'OFF'} | Gemini/Hermes ON | "
        f"OpenAI {'ON' if _provider_state.get('openai') else 'needs key'} | "
        f"Claude {'ON' if _provider_state.get('claude') else 'needs key'}"
    )

    print(
        "Outlook isolated worker mode: ON"
    )

    print(
        f"Background agents: ON (max {AGENT_MAX_CONCURRENT})"
    )

    print(
        "Press CTRL+C to shut down."
    )

    print()
    update_live_state(
        "STANDBY",
        system="ONLINE",
        version="2.33",
        ui_action=None,
    )
    _write_voice_health("online", "wake word and microphone ready")


    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=WAKE_BLOCK_SIZE,
    ) as stream:


        while True:

            _write_voice_health("ready", "wake word, microphone, and command loop ready")
            print(
                "Jarvis standing by..."
            )
            update_live_state("STANDBY")
            _write_voice_health("listening", "waiting for Hey Jarvis")


            initial_audio = (
                wait_for_wake_word(
                    stream
                )
            )


            command = (
                capture_after_wake(
                    stream,
                    initial_audio,
                )
            )


            if not command:

                print(
                    "Listening for command..."
                )

                command = (
                    capture_followup(
                        stream,
                        COMMAND_START_TIMEOUT,
                    )
                )


            if not command:

                print(
                    "No command detected."
                )

                wake_model.reset()

                continue


            answer = process_command(
                command
            )


            wake_model.reset()

            # No post-speech cooldown here: start follow-up capture immediately
            # so the first words after Jarvis finishes speaking are preserved.

            # =================================================
            # NATURAL FOLLOW-UP MODE
            # =================================================

            if (
                FOLLOW_UP_MODE
                and answer
            ):

                follow_count = 0


                while (
                    follow_count
                    < MAX_FOLLOW_UPS
                ):

                    print()
                    print(
                        "Listening briefly "
                        "for a follow-up..."
                    )
                    update_live_state("LISTENING")


                    follow_timeout = (
                        CONFIRMATION_TIMEOUT
                        if pending_action is not None
                        else (6.0 if speech_was_interrupted else FOLLOW_UP_SECONDS)
                    )


                    follow_up = (
                        capture_followup(
                            stream,
                            follow_timeout,
                        )
                    )


                    if not follow_up:

                        if pending_action is not None:
                            expire_pending_action()

                        break


                    if (
                        pending_action is None
                        and not speech_was_interrupted
                        and not is_likely_followup(
                            follow_up
                        )
                    ):

                        print(
                            "Background speech ignored."
                        )

                        break


                    if is_followup_cancel(
                        follow_up
                    ):

                        print(
                            "Conversation ended."
                        )

                        break


                    follow_count += 1


                    process_command(
                        follow_up
                    )


                    # Immediately reopen the follow-up window after Jarvis speaks.


                print()


            wake_model.reset()

            # Return to wake-word monitoring immediately.


# ============================================================
# MAIN
# ============================================================

def main():

    # Runtime power/camera state is never carried into a new Jarvis session.
    # All other Air Touch preferences remain exactly as saved.
    _reset_airtouch_startup_state()

    log(
        "Jarvis V42.56.0 starting"
    )


    try:

        if not test_hermes_api():
            return


        calibrate_microphone()
        start_jarvis_ipc_server()


        run_jarvis()


    except KeyboardInterrupt:

        sd.stop()

        print()
        print()
        print(
            "Jarvis offline."
        )

        log(
            "Jarvis stopped"
        )


    except Exception as exc:

        sd.stop()

        print()
        print(
            f"Fatal error: {exc}"
        )

        log(
            f"FATAL: {exc}"
        )


if __name__ == "__main__":
    main()

