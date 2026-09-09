import os
import sys
import json
import time
import subprocess
import shutil
import email
import imaplib
import urllib.parse
import urllib.request
import webbrowser
import threading
import uuid
import re
import socket
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

JARVIS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UI_DIR = os.path.dirname(os.path.abspath(__file__))
_REQUESTED_DASHBOARD_PORT = int(os.environ.get('JARVIS_DASHBOARD_PORT', '8080'))
_QWEN_SERVER_PORT = int(os.environ.get('JARVIS_QWEN_PORT', '8081') or '8081')
# Never let an inherited/mistyped environment variable point the dashboard at
# llama.cpp's port. The dashboard owns 8080; Qwen owns 8081 by default.
PORT = 8080 if _REQUESTED_DASHBOARD_PORT == _QWEN_SERVER_PORT else _REQUESTED_DASHBOARD_PORT
DASHBOARD_BUILD_ID = 'v42.55.0-exact-model-protocol'
DASHBOARD_LAYOUT_VERSION = 2
DASHBOARD_STARTED_AT = datetime.now().isoformat(timespec='milliseconds')
IPC_URL = 'http://127.0.0.1:8765'
LIVE_STATE_FILE = os.path.join(JARVIS_DIR, 'live_state.json')
AGENT_JOB_FILE = os.path.join(JARVIS_DIR, 'agent_jobs.json')
VOICE_SETTINGS_FILE = os.path.join(JARVIS_DIR, 'voice_settings.json')
DASHBOARD_LAYOUT_FILE = os.path.join(JARVIS_DIR, 'dashboard_layout.json')
RESTART_STATUS_FILE = os.path.join(JARVIS_DIR, 'restart_status.json')
DASHBOARD_ENDPOINT_FILE = os.path.join(JARVIS_DIR, 'dashboard_endpoint.json')
GENERATED_PROJECTS_DIR = os.path.join(JARVIS_DIR, 'generated_projects')
os.makedirs(GENERATED_PROJECTS_DIR, exist_ok=True)
UPLOADS_DIR = os.path.join(JARVIS_DIR, 'chat_uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)
MAX_UPLOAD_BYTES = int(os.environ.get('JARVIS_CHAT_UPLOAD_MAX_BYTES', str(4 * 1024 * 1024 * 1024)))
ALLOWED_UPLOAD_EXTENSIONS = {'.zip','.txt','.md','.json','.yaml','.yml','.toml','.ini','.cfg','.py','.js','.jsx','.ts','.tsx','.html','.css','.csv','.xml','.sql','.ps1','.bat','.cmd','.dart','.java','.cpp','.h','.cs','.go','.rs'}
DASHBOARD_LAYOUT_LOCK = threading.RLock()
DIAGNOSTICS_DIR = os.path.join(JARVIS_DIR, 'logs')
os.makedirs(DIAGNOSTICS_DIR, exist_ok=True)
DASHBOARD_HTTP_LOG = os.path.join(DIAGNOSTICS_DIR, 'dashboard_http.log')
FRONTEND_LOG = os.path.join(DIAGNOSTICS_DIR, 'dashboard_frontend.log')
LOG_LOCK = threading.RLock()

def _append_log(path, message):
    try:
        stamp = datetime.now().isoformat(timespec='milliseconds')
        with LOG_LOCK:
            with open(path, 'a', encoding='utf-8') as fh:
                fh.write(f'[{stamp}] {message}\n')
    except Exception:
        pass

def log_http(message):
    _append_log(DASHBOARD_HTTP_LOG, message)

def log_frontend(message):
    _append_log(FRONTEND_LOG, message)


COMMAND_JOBS = {}
COMMAND_JOBS_LOCK = threading.RLock()

def _command_job_worker(job_id, command, attachments=None, qwen_profile=''):
    with COMMAND_JOBS_LOCK:
        job = COMMAND_JOBS.get(job_id)
        if not job:
            return
        job["status"] = "running"
        job["started_at"] = datetime.now().isoformat(timespec="milliseconds")
    try:
        command_for_jarvis = str(command or '')
        qwen_profile = str(qwen_profile or '').strip().lower()
        if qwen_profile in {'auto','8b','9b35','27b38q2','27b'}:
            command_for_jarvis = f"[JARVIS_QWEN_PROFILE] {qwen_profile}\n" + command_for_jarvis
        for item in (attachments or []):
            path = str(item.get('path') or '').strip()
            if path:
                command_for_jarvis += f"\n[JARVIS_ATTACHED_FILE] {path}"
        answer = send_command_to_jarvis(command_for_jarvis, with_metadata=True)
        response = str(answer.get('response') or answer.get('error') or '') if isinstance(answer, dict) else str(answer)
        attachment_accepted = answer.get('attachment_accepted') if isinstance(answer, dict) else None
        status, error = "completed", ""
        if isinstance(answer, dict) and answer.get('status') == 'error':
            status, error = 'failed', str(answer.get('error') or response)
    except Exception as exc:
        response, status, error = "", "failed", str(exc)
        attachment_accepted = False
    with COMMAND_JOBS_LOCK:
        job = COMMAND_JOBS.get(job_id)
        if not job:
            return
        job["status"] = status
        job["response"] = response
        job["error"] = error
        job['attachment_accepted'] = attachment_accepted
        job["finished_at"] = datetime.now().isoformat(timespec="milliseconds")

def queue_dashboard_command(command, attachments=None, qwen_profile=''):
    job_id = uuid.uuid4().hex
    with COMMAND_JOBS_LOCK:
        COMMAND_JOBS[job_id] = {
            "id": job_id,
            "command": command,
            "attachments": list(attachments or []),
            "qwen_profile": str(qwen_profile or ''),
            "status": "queued",
            "response": "",
            "error": "",
            "created_at": datetime.now().isoformat(timespec="milliseconds"),
        }
    threading.Thread(
        target=_command_job_worker,
        args=(job_id, command, list(attachments or []), str(qwen_profile or '')),
        daemon=True,
        name=f"DashboardCommand-{job_id[:8]}",
    ).start()
    return job_id

def get_command_job(job_id):
    with COMMAND_JOBS_LOCK:
        job = COMMAND_JOBS.get(job_id)
        return dict(job) if job else None

if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)

from ui.project_uploads import ProjectUploads, UploadError, CHUNK_BYTES, needs_project_zip, validate_zip
PROJECT_UPLOADS = ProjectUploads(UPLOADS_DIR, MAX_UPLOAD_BYTES)

# IMPORTANT:
# Never import jarvis.py inside the dashboard process.
# jarvis.py owns the voice-engine singleton and initializes Whisper/openWakeWord
# at module import time. The dashboard communicates with Jarvis strictly over IPC.
jarvis_core = None
IMPORT_ERROR = ''

try:
    import pythoncom
    import win32com.client as win32_client
except Exception:
    pythoncom = None
    win32_client = None

try:
    import psutil
except Exception:
    psutil = None


def safe_json_file(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return default



AIRTOUCH_DIR = os.path.join(UI_DIR, 'airtouch')
AIRTOUCH_SETTINGS_FILE = os.path.join(JARVIS_DIR, 'airtouch_settings.json')
AIRTOUCH_TARGET_FILE = os.path.join(JARVIS_DIR, 'airtouch_target.json')
AIRTOUCH_LOCK = threading.RLock()
AIRTOUCH_DEFAULTS = {
    "enabled": False, "cameraEnabled": False, "paused": False,
    "externalControl": False, "mirrored": True, "sensitivity": 1.0,
    "smoothing": 0.32, "pinchStart": 0.052, "pinchRelease": 0.075,
    "confirmationFrames": 2, "gestureCooldownMs": 220,
    "scrollSensitivity": 1.0, "swipeSensitivity": 1.0,
    "dwellTyping": False, "dwellDurationMs": 850,
    "targetSnapping": False, "cameraPreview": False, "debug": False,
    "cursorVisible": True, "preferredHand": "Any", "resolution": "640x480",
    "cameraId": "", "autoKeyboard": False, "calibration": None,
}
AIRTOUCH_EXTERNAL_LAST = 0.0

def get_airtouch_settings():
    value = safe_json_file(AIRTOUCH_SETTINGS_FILE, {})
    return {**AIRTOUCH_DEFAULTS, **(value if isinstance(value, dict) else {})}

def reset_airtouch_startup_state():
    """Disable only Air Touch runtime state at each dashboard process launch."""
    with AIRTOUCH_LOCK:
        value = safe_json_file(AIRTOUCH_SETTINGS_FILE, {})
        settings = {**AIRTOUCH_DEFAULTS, **(value if isinstance(value, dict) else {})}
        settings["enabled"] = False
        settings["cameraEnabled"] = False
        temp = f"{AIRTOUCH_SETTINGS_FILE}.startup.{os.getpid()}.tmp"
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump(settings, handle, indent=2)
        os.replace(temp, AIRTOUCH_SETTINGS_FILE)
    return settings

def save_airtouch_settings(settings):
    clean = {**AIRTOUCH_DEFAULTS}
    if isinstance(settings, dict):
        for key in clean:
            if key in settings:
                clean[key] = settings[key]
    temp = AIRTOUCH_SETTINGS_FILE + '.tmp'
    with AIRTOUCH_LOCK:
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump(clean, handle, indent=2)
        os.replace(temp, AIRTOUCH_SETTINGS_FILE)
    return clean

def get_airtouch_target():
    value = safe_json_file(AIRTOUCH_TARGET_FILE, {})
    return value if isinstance(value, dict) else {}

def save_airtouch_target(target):
    safe = {
        "id": str(target.get("id", ""))[:100],
        "widget": str(target.get("widget", ""))[:100],
        "type": str(target.get("type", ""))[:40],
        "interactive": bool(target.get("interactive", False)),
        "actions": [str(x)[:40] for x in (target.get("actions") or [])[:12]],
        "updated_at": datetime.now().isoformat(timespec='milliseconds'),
    }
    temp = AIRTOUCH_TARGET_FILE + '.tmp'
    with AIRTOUCH_LOCK:
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump(safe, handle, indent=2)
        os.replace(temp, AIRTOUCH_TARGET_FILE)
    return safe

def airtouch_emergency_stop():
    settings = get_airtouch_settings()
    settings["paused"] = True
    settings["externalControl"] = False
    save_airtouch_settings(settings)
    try:
        import desktop_automation
        p = desktop_automation._pyautogui()
        if p:
            p.mouseUp()
    except Exception:
        pass
    return settings

def _airtouch_external_action(data):
    global AIRTOUCH_EXTERNAL_LAST
    settings = get_airtouch_settings()
    if not settings.get("externalControl"):
        return False, "External Air Touch control is disabled."
    now = time.monotonic()
    action = str(data.get("action", "")).lower()
    if action == "move" and now - AIRTOUCH_EXTERNAL_LAST < 0.012:
        return True, "rate-limited"
    AIRTOUCH_EXTERNAL_LAST = now
    try:
        import desktop_automation
        p = desktop_automation._pyautogui()
        if not p:
            return False, "PyAutoGUI is not installed."
        if action == "move":
            x = max(0.0, min(1.0, float(data.get("x", 0.5))))
            y = max(0.0, min(1.0, float(data.get("y", 0.5))))
            w, h = p.size()
            p.moveTo(int(x * (w - 1)), int(y * (h - 1)), duration=0)
        elif action == "down":
            p.mouseDown()
        elif action == "up":
            p.mouseUp()
        elif action == "click":
            p.click()
        elif action == "double_click":
            p.doubleClick(interval=0.09)
        elif action == "scroll":
            p.scroll(int(data.get("amount", 0)))
        else:
            return False, "Unsupported external Air Touch action."
        return True, "ok"
    except Exception as exc:
        return False, str(exc)

def _airtouch_hotkey_loop():
    if os.name != 'nt':
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        MOD_ALT, MOD_CONTROL, MOD_SHIFT = 0x0001, 0x0002, 0x0004
        HOTKEY_ID, VK_X = 0xA17, 0x58
        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT | MOD_CONTROL | MOD_SHIFT, VK_X):
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                airtouch_emergency_stop()
        user32.UnregisterHotKey(None, HOTKEY_ID)
    except Exception:
        return

threading.Thread(target=_airtouch_hotkey_loop, daemon=True, name="AirTouchEmergencyHotkey").start()

def _validated_dashboard_layout(layout):
    """Return a bounded, JSON-safe panel layout or raise ValueError."""
    if not isinstance(layout, dict) or not isinstance(layout.get('panels', {}), dict):
        raise ValueError('Layout must contain a panels object.')
    if layout.get('version') != DASHBOARD_LAYOUT_VERSION:
        raise ValueError('Layout belongs to an older dashboard and must be reset.')

    panels = layout.get('panels', {})
    if len(panels) > 200:
        raise ValueError('Layout contains too many panels.')

    clean_panels = {}
    for panel_id, geometry in panels.items():
        panel_id = str(panel_id)
        if not panel_id or len(panel_id) > 100 or not isinstance(geometry, dict):
            raise ValueError('Invalid panel layout entry.')
        clean_geometry = {}
        for key in ('x', 'y', 'width', 'height'):
            if key not in geometry:
                continue
            value = geometry[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'Invalid {key} for {panel_id}.')
            if not -10000 <= value <= 10000:
                raise ValueError(f'Out-of-range {key} for {panel_id}.')
            clean_geometry[key] = value
        clean_panels[panel_id] = clean_geometry
    return {'version': DASHBOARD_LAYOUT_VERSION, 'panels': clean_panels}


def get_dashboard_layout():
    with DASHBOARD_LAYOUT_LOCK:
        layout = safe_json_file(DASHBOARD_LAYOUT_FILE, {})
        if not layout:
            return {}
        try:
            return _validated_dashboard_layout(layout)
        except ValueError:
            return {}


def save_dashboard_layout(layout):
    clean_layout = _validated_dashboard_layout(layout)
    temporary_file = DASHBOARD_LAYOUT_FILE + '.tmp'
    with DASHBOARD_LAYOUT_LOCK:
        os.makedirs(os.path.dirname(DASHBOARD_LAYOUT_FILE), exist_ok=True)
        with open(temporary_file, 'w', encoding='utf-8') as handle:
            json.dump(clean_layout, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_file, DASHBOARD_LAYOUT_FILE)
    return clean_layout


def reset_dashboard_layout():
    with DASHBOARD_LAYOUT_LOCK:
        try:
            os.remove(DASHBOARD_LAYOUT_FILE)
        except FileNotFoundError:
            pass
        try:
            os.remove(DASHBOARD_LAYOUT_FILE + '.tmp')
        except FileNotFoundError:
            pass


def get_live_state():
    state = safe_json_file(LIVE_STATE_FILE, {})
    if not state:
        state = {
            'state': 'OFFLINE',
            'system': 'WAITING FOR JARVIS',
            'updated_at': '',
            'last_user': '',
            'last_answer': '',
            'ui_action': None,
        }
    return state


def get_voice_state():
    return {
        "state": "STANDBY",
        "engine": "ElevenLabs / Whisper",
        "wake_word": "Jarvis",
        "microphone": "Array Active"
    }


def get_system_status():
    return {
        'host': os.environ.get('COMPUTERNAME', 'JARVIS-CORE'),
        'user': os.environ.get('USERNAME', 'gunsh'),
        'python_version': sys.version.split()[0],
        'time': datetime.now().isoformat(timespec='seconds'),
        'status': get_live_state().get('state', 'UNKNOWN'),
        'voice_engine': 'ElevenLabs + Faster-Whisper',
        'email_account': os.getenv('JARVIS_WORK_EMAIL_ADDRESS', ''),
        'calendar_backend': 'Outlook isolated worker',
        'hud_mode': 'Jarvis Command Center v5.0',
        'ipc': 'ONLINE' if ipc_is_online() else 'OFFLINE',
    }


_CPU_SAMPLE_LOCK = threading.RLock()
_CPU_SAMPLE_PREVIOUS = None
_TEMP_CACHE = {"at": 0.0, "cpu": None, "ram": None, "source": "Unavailable"}


def _windows_cpu_times():
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        idle = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        def ft(value):
            return (value.dwHighDateTime << 32) | value.dwLowDateTime
        return ft(idle), ft(kernel), ft(user)
    except Exception:
        return None


def _windows_cpu_percent():
    global _CPU_SAMPLE_PREVIOUS

    if psutil:
        try:
            return round(float(psutil.cpu_percent(interval=0.12)), 1)
        except Exception:
            pass

    current = _windows_cpu_times()
    if not current:
        return 0.0

    with _CPU_SAMPLE_LOCK:
        previous = _CPU_SAMPLE_PREVIOUS
        if previous is None:
            _CPU_SAMPLE_PREVIOUS = current
            time.sleep(0.12)
            current = _windows_cpu_times()
            previous = _CPU_SAMPLE_PREVIOUS
        _CPU_SAMPLE_PREVIOUS = current

    if not previous or not current:
        return 0.0

    idle_delta = current[0] - previous[0]
    kernel_delta = current[1] - previous[1]
    user_delta = current[2] - previous[2]
    total = kernel_delta + user_delta

    if total <= 0:
        return 0.0

    busy = max(0, total - idle_delta)
    return round(max(0.0, min(100.0, busy * 100.0 / total)), 1)


def _windows_memory_stats():
    if os.name != 'nt':
        return None
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong),
                ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong),
                ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong),
                ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None

        total = int(status.ullTotalPhys)
        available = int(status.ullAvailPhys)
        used = max(0, total - available)
        return {'total': total, 'used': used, 'percent': round(float(status.dwMemoryLoad), 1)}
    except Exception:
        return None


def _powershell_json(script, timeout=3):
    if os.name != 'nt':
        return None
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout.strip())
    except Exception:
        return None


HARDWARE_HELPER_EXE = os.path.join(
    JARVIS_DIR, 'tools', 'JarvisHardwareSensors', 'JarvisHardwareSensors.exe'
)
HARDWARE_HELPER_VERSION = '2.19'
HARDWARE_HELPER_STAMP = os.path.join(
    JARVIS_DIR, 'tools', 'JarvisHardwareSensors', 'helper.version'
)
HARDWARE_HELPER_BUILD = os.path.join(JARVIS_DIR, 'BUILD_HARDWARE_HELPER.bat')
HARDWARE_SENSOR_CACHE = os.path.join(JARVIS_DIR, 'hardware_sensor_snapshot.json')
_HARDWARE_BUILD_LOCK = threading.RLock()
_HARDWARE_BUILD_STARTED = False
_HARDWARE_BUILD_FINISHED = False
_HARDWARE_BUILD_MESSAGE = ''


def _hardware_build_worker():
    global _HARDWARE_BUILD_FINISHED, _HARDWARE_BUILD_MESSAGE
    try:
        result = subprocess.run(
            ['cmd.exe', '/c', HARDWARE_HELPER_BUILD],
            cwd=JARVIS_DIR,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode == 0 and os.path.exists(HARDWARE_HELPER_EXE):
            _HARDWARE_BUILD_MESSAGE = 'Hardware helper built successfully.'
        else:
            combined = (result.stdout or '') + '\n' + (result.stderr or '')
            _HARDWARE_BUILD_MESSAGE = combined.strip()[-1200:] or 'Hardware helper build failed.'
    except Exception as exc:
        _HARDWARE_BUILD_MESSAGE = f'Hardware helper build error: {exc}'
    finally:
        _HARDWARE_BUILD_FINISHED = True


def _ensure_hardware_helper():
    global _HARDWARE_BUILD_STARTED
    current=False
    if os.path.exists(HARDWARE_HELPER_EXE) and os.path.exists(HARDWARE_HELPER_STAMP):
        try:
            current=Path(HARDWARE_HELPER_STAMP).read_text(encoding="utf-8",errors="replace").strip()==HARDWARE_HELPER_VERSION
        except Exception:current=False
    if current:
        return True
    if not os.path.exists(HARDWARE_HELPER_BUILD):
        return False

    with _HARDWARE_BUILD_LOCK:
        if not _HARDWARE_BUILD_STARTED:
            _HARDWARE_BUILD_STARTED = True
            threading.Thread(
                target=_hardware_build_worker,
                daemon=True,
                name='JarvisHardwareHelperBuild',
            ).start()
    return False


def _run_hardware_helper():
    if not _ensure_hardware_helper():
        return None
    try:
        result = subprocess.run(
            [HARDWARE_HELPER_EXE],
            cwd=os.path.dirname(HARDWARE_HELPER_EXE),
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        output = (result.stdout or '').strip()
        if not output:
            return {
                'ok': False,
                'error': (result.stderr or '').strip() or 'Hardware helper returned no data.',
            }
        return json.loads(output.splitlines()[-1])
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def get_hardware_snapshot():
    # Preferred path: elevated long-running sensor bridge writes a fresh JSON cache.
    try:
        if os.path.exists(HARDWARE_SENSOR_CACHE):
            age = time.time() - os.path.getmtime(HARDWARE_SENSOR_CACHE)
            if age < 12:
                with open(HARDWARE_SENSOR_CACHE, 'r', encoding='utf-8', errors='replace') as f:
                    cached = json.load(f)
                cached['source'] = (cached.get('source') or 'JarvisHardwareSensors .NET 10') + ' elevated bridge'
                return cached
    except Exception:
        pass

    # Fallback: direct unelevated query. This still provides sensors that do not
    # require the LibreHardwareMonitor kernel driver.
    payload = _run_hardware_helper()
    if payload:
        if payload.get('ok') and not payload.get('isAdministrator'):
            payload['source'] = (payload.get('source') or 'JarvisHardwareSensors .NET 10') + ' standard user'
        return payload

    status = 'building' if _HARDWARE_BUILD_STARTED and not _HARDWARE_BUILD_FINISHED else 'unavailable'
    return {
        'ok': False,
        'status': status,
        'source': 'JarvisHardwareSensors .NET 10',
        'error': _HARDWARE_BUILD_MESSAGE or (
            'The .NET 10 hardware helper is being built automatically.' if status == 'building'
            else 'Hardware helper is unavailable.'
        ),
        'sensors': [],
        'summary': {},
    }


def _read_hardware_temperatures():
    global _TEMP_CACHE

    now = time.monotonic()
    if now - _TEMP_CACHE.get('at', 0) < 4:
        return dict(_TEMP_CACHE)

    payload = get_hardware_snapshot()
    summary = payload.get('summary') or {}

    cpu_package = summary.get('cpuPackageTempC')
    cpu_core_max = summary.get('cpuCoreMaxTempC')
    gpu_core = summary.get('gpuCoreTempC')
    gpu_hotspot = summary.get('gpuHotspotTempC')
    ram_temp = summary.get('ramTempC')
    motherboard_temp = summary.get('motherboardTempC')
    storage_temp = summary.get('storageTempC')
    fan_rpm = summary.get('fanRpm') or []

    source = payload.get('source') or 'JarvisHardwareSensors .NET 10'
    detail = (
        f"{len(payload.get('sensors') or [])} sensors available"
        if payload.get('ok')
        else payload.get('error') or payload.get('status') or 'Unavailable'
    )

    _TEMP_CACHE = {
        'at': now,
        'cpu': cpu_package if cpu_package is not None else cpu_core_max,
        'cpu_package': cpu_package,
        'cpu_core_max': cpu_core_max,
        'ram': ram_temp,
        'gpu': gpu_core,
        'gpu_hotspot': gpu_hotspot,
        'motherboard': motherboard_temp,
        'storage': storage_temp,
        'fan_rpm': fan_rpm,
        'source': source,
        'detail': detail,
        'helper_ok': bool(payload.get('ok')),
    }
    return dict(_TEMP_CACHE)


def get_telemetry():
    try:
        cpu_value = _windows_cpu_percent()

        if psutil:
            try:
                vm = psutil.virtual_memory()
                memory_total = int(vm.total)
                memory_used = int(vm.used)
                memory_percent = round(float(vm.percent), 1)
            except Exception:
                memory = _windows_memory_stats()
                memory_total = memory['total'] if memory else 0
                memory_used = memory['used'] if memory else 0
                memory_percent = memory['percent'] if memory else 0.0
        else:
            memory = _windows_memory_stats()
            memory_total = memory['total'] if memory else 0
            memory_used = memory['used'] if memory else 0
            memory_percent = memory['percent'] if memory else 0.0

        try:
            disk_root = os.environ.get('SystemDrive', 'C:') + '\\'
            usage = shutil.disk_usage(disk_root)
            disk_total = int(usage.total)
            disk_used = int(usage.used)
            disk_percent = round((disk_used / disk_total * 100.0), 1) if disk_total else 0.0
        except Exception:
            disk_total = disk_used = 0
            disk_percent = 0.0

        network_sent = network_recv = 0.0
        if psutil:
            try:
                net = psutil.net_io_counters()
                network_sent = round(net.bytes_sent / (1024**2), 1)
                network_recv = round(net.bytes_recv / (1024**2), 1)
            except Exception:
                pass

        temps = _read_hardware_temperatures()

        return {
            'cpu_usage': f'{cpu_value:.0f}%',
            'cpu_value': cpu_value,
            'memory_usage': (
                f'{memory_used / (1024**3):.1f} / {memory_total / (1024**3):.1f} GB'
                if memory_total else 'Unavailable'
            ),
            'memory_percent': memory_percent,
            'disk_usage': (
                f'{disk_used / (1024**3):.0f} / {disk_total / (1024**3):.0f} GB'
                if disk_total else 'Unavailable'
            ),
            'disk_percent': disk_percent,
            'network_sent_mb': network_sent,
            'network_recv_mb': network_recv,
            'network_latency': 'LOCAL',
            'active_threads': threading.active_count(),
            'cpu_temp_c': temps.get('cpu'),
            'cpu_package_temp_c': temps.get('cpu_package'),
            'cpu_core_max_temp_c': temps.get('cpu_core_max'),
            'ram_temp_c': temps.get('ram'),
            'gpu_temp_c': temps.get('gpu'),
            'gpu_hotspot_temp_c': temps.get('gpu_hotspot'),
            'motherboard_temp_c': temps.get('motherboard'),
            'storage_temp_c': temps.get('storage'),
            'fan_rpm': temps.get('fan_rpm', []),
            'temperature_source': temps.get('source', 'Unavailable'),
            'temperature_detail': temps.get('detail', ''),
            'hardware_helper_ok': temps.get('helper_ok', False),
            'telemetry_source': 'Windows native API' + (' + psutil' if psutil else ''),
        }
    except Exception as exc:
        return {
            'cpu_usage': '—',
            'cpu_value': 0,
            'memory_usage': 'Unavailable',
            'memory_percent': 0,
            'disk_usage': 'Unavailable',
            'disk_percent': 0,
            'network_sent_mb': 0,
            'network_recv_mb': 0,
            'network_latency': 'LOCAL',
            'active_threads': threading.active_count(),
            'cpu_temp_c': None,
            'cpu_package_temp_c': None,
            'cpu_core_max_temp_c': None,
            'ram_temp_c': None,
            'gpu_temp_c': None,
            'gpu_hotspot_temp_c': None,
            'motherboard_temp_c': None,
            'storage_temp_c': None,
            'fan_rpm': [],
            'temperature_source': 'Unavailable',
            'temperature_detail': '',
            'hardware_helper_ok': False,
            'telemetry_source': f'Error: {exc}',
        }


def _provider_env_values():
    values = dict(os.environ)
    provider_file = os.path.join(JARVIS_DIR, 'ai_providers.env')
    if os.path.exists(provider_file):
        try:
            with open(provider_file, 'r', encoding='utf-8') as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        except Exception:
            pass
    return values



NVIDIA_SELECTION_FILE = os.path.join(JARVIS_DIR, "nvidia_model_selection.json")
NVIDIA_CACHE_FILE = os.path.join(JARVIS_DIR, "nvidia_models_cache.json")

def _nvidia_env():
    return _provider_env_values()

def _nvidia_selection():
    data=safe_json_file(NVIDIA_SELECTION_FILE,{})
    return str(data.get("model","auto") or "auto")

def save_nvidia_selection(model):
    model=str(model or "auto").strip() or "auto"
    payload={"model":model,"updated_at":datetime.now().isoformat(timespec="seconds")}
    temp=NVIDIA_SELECTION_FILE+".tmp"
    with open(temp,"w",encoding="utf-8") as handle:
        json.dump(payload,handle,indent=2)
    os.replace(temp,NVIDIA_SELECTION_FILE)
    return payload

def get_nvidia_models_dashboard(force=False):
    env=_nvidia_env()
    key=env.get("NVIDIA_API_KEY","")
    cache=safe_json_file(NVIDIA_CACHE_FILE,{})
    models=cache.get("models") if isinstance(cache,dict) else []
    fetched=float(cache.get("fetched_epoch",0) or 0) if isinstance(cache,dict) else 0
    if models and not force and time.time()-fetched < 21600:
        return {"configured":bool(key),"selection":_nvidia_selection(),"models":models,"count":len(models),"cached":True}
    if not key:
        return {"configured":False,"selection":_nvidia_selection(),"models":models or [],"count":len(models or []),"cached":True}
    try:
        req=urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization":"Bearer "+key,"Accept":"application/json"},
        )
        with urllib.request.urlopen(req,timeout=20) as response:
            data=json.loads(response.read().decode("utf-8"))
        models=sorted({str(x.get("id","")).strip() for x in data.get("data",[]) if str(x.get("id","")).strip()},key=str.lower)
        payload={"models":models,"fetched_epoch":time.time(),"fetched_at":datetime.now().isoformat(timespec="seconds"),"source":"NVIDIA /v1/models"}
        temp=NVIDIA_CACHE_FILE+".tmp"
        with open(temp,"w",encoding="utf-8") as handle: json.dump(payload,handle,indent=2)
        os.replace(temp,NVIDIA_CACHE_FILE)
        return {"configured":True,"selection":_nvidia_selection(),"models":models,"count":len(models),"cached":False}
    except Exception as exc:
        return {"configured":True,"selection":_nvidia_selection(),"models":models or [],"count":len(models or []),"cached":True,"error":str(exc)}


def _voice_settings_dashboard():
    data = safe_json_file(VOICE_SETTINGS_FILE, {})
    defaults = {
        "provider": "kokoro",
        "kokoro_voice": "af_heart",
        "piper_voice": "en_US-lessac-medium",
        "elevenlabs_voice_id": "",
        "fallback_order": ["kokoro", "piper", "elevenlabs"],
    }
    if isinstance(data, dict):
        defaults.update(data)
    return defaults

def save_voice_settings_dashboard(data):
    current = _voice_settings_dashboard()
    for key in ("provider", "kokoro_voice", "piper_voice", "elevenlabs_voice_id", "fallback_order"):
        if key in data:
            current[key] = data[key]
    tmp = VOICE_SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    os.replace(tmp, VOICE_SETTINGS_FILE)
    return current

def get_voice_catalog_dashboard():
    kokoro = [
        "af_heart","af_alloy","af_aoede","af_bella","af_jessica","af_kore","af_nicole","af_nova",
        "af_river","af_sarah","af_sky","am_adam","am_echo","am_eric","am_fenrir","am_liam",
        "am_michael","am_onyx","am_puck","am_santa","bf_alice","bf_emma","bf_isabella","bf_lily",
        "bm_daniel","bm_fable","bm_george","bm_lewis"
    ]
    piper = [
        "en_US-lessac-medium","en_US-amy-medium","en_US-ryan-high","en_US-hfc_female-medium",
        "en_US-hfc_male-medium","en_GB-alba-medium","en_GB-jenny_dioco-medium"
    ]
    try:
        import importlib.util
        kokoro_ok = importlib.util.find_spec("kokoro_onnx") is not None
    except Exception:
        kokoro_ok = False
    return {
        "settings": _voice_settings_dashboard(),
        "providers": {
            "kokoro": {"configured": kokoro_ok, "voices": kokoro},
            "piper": {"configured": bool(shutil.which("piper")), "voices": piper},
            "elevenlabs": {"configured": True, "voices": [{"id": _voice_settings_dashboard().get("elevenlabs_voice_id",""), "name": "Current ElevenLabs voice"}]},
        },
    }

def _qwen_active_model_label_dashboard():
    runtime = safe_json_file(os.path.join(JARVIS_DIR, 'qwen_runtime_profile.json'), {})
    model_path = str((runtime or {}).get('model') or '').strip()
    if model_path:
        name = os.path.basename(model_path)
        low = name.lower()
        if 'qwen3.5' in low or 'qwen35' in low or 'qwen3_5' in low:
            return 'Qwen3.5-9B HauhauCS Aggressive Q4_K_M'
        if 'qwen3.8-27b-uncensored-hauhaucs-aggressive' in low and 'q2_k_p' in low:
            return 'Qwen3.8-27B HauhauCS Aggressive Q2_K_P'
        if 'qwen3_8b' in low or 'qwen3-8b' in low:
            return 'Qwen3-8B Abliterated Q4_K_M'
        if '27b' in low:
            return 'Qwen3.8-27B OBLITERATED Q4_K_M'
        return name
    return ''


def get_provider_status():
    env = _provider_env_values()
    live = get_live_state()
    qwen_base = env.get('JARVIS_QWEN_BASE_URL', f"http://127.0.0.1:{int(env.get('JARVIS_QWEN_PORT', '8081') or '8081')}").rstrip('/')
    qwen_online = False
    try:
        with urllib.request.urlopen(qwen_base + '/health', timeout=0.8) as response:
            qwen_online = response.status == 200
    except Exception:
        pass
    return [
        {
            'id': 'qwen',
            'name': 'Qwen Local',
            'configured': True,
            'status': 'ONLINE' if qwen_online else 'OFFLINE',
            'model': _qwen_active_model_label_dashboard() or env.get('JARVIS_QWEN_MODEL', 'Qwen3.8-27B-OBLITERATED Q4_K_M'),
        },
        {
            'id': 'gemini',
            'name': 'Gemini / Hermes',
            'configured': True,
            'status': 'ONLINE' if live.get('state') != 'OFFLINE' else 'OFFLINE',
            'model': env.get('GEMINI_MODEL', 'Hermes configured model'),
        },
        {
            'id': 'nvidia',
            'name': 'NVIDIA NIM Model Team',
            'configured': bool(env.get('NVIDIA_API_KEY')),
            'status': 'READY' if env.get('NVIDIA_API_KEY') else 'NOT CONFIGURED',
            'model': _nvidia_selection(),
        },
        {
            'id': 'openai',
            'name': 'OpenAI',
            'configured': bool(env.get('OPENAI_API_KEY')),
            'status': 'READY' if env.get('OPENAI_API_KEY') else 'NOT CONFIGURED',
            'model': env.get('OPENAI_MODEL', 'gpt-5.6-sol'),
        },
        {
            'id': 'claude',
            'name': 'Claude',
            'configured': bool(env.get('ANTHROPIC_API_KEY')),
            'status': 'CONFIGURED' if env.get('ANTHROPIC_API_KEY') else 'NOT CONFIGURED',
            'model': env.get('CLAUDE_MODEL', 'claude-sonnet'),
        },
    ]


def normalize_agents():
    # Runtime threads, not restored JSON, determine whether a job is active.
    # Keep file history available during outages without calling it live work.
    confirmed = False
    try:
        with urllib.request.urlopen(IPC_URL + '/agents', timeout=1.0) as response:
            snapshot = json.load(response)
        if snapshot.get('service') != 'jarvis-core' or not isinstance(snapshot.get('agents'), list):
            raise ValueError('Invalid core agent snapshot')
        raw = snapshot['agents']
        confirmed = True
    except Exception:
        raw = safe_json_file(AGENT_JOB_FILE, {})
    jobs = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            job = dict(value)
            job.setdefault('id', int(key) if str(key).isdigit() else key)
            jobs.append(job)
    elif isinstance(raw, list):
        jobs = [dict(job) for job in raw if isinstance(job, dict)]
    for job in jobs:
        job['runtime_confirmed'] = confirmed
        if not confirmed and job.get('status') in {'queued', 'running', 'stopping'}:
            job['last_known_status'] = job['status']
            job['status'] = 'unconfirmed'
            job['activity'] = 'Saved agent record; waiting for the Jarvis core to confirm its current status.'
    jobs.sort(key=lambda x: int(x.get('id', 0)) if str(x.get('id', '')).isdigit() else 0)
    return jobs


def get_calendar_events():
    """Read the next 14 days from Outlook safely from an HTTP worker thread."""
    if win32_client is None or pythoncom is None:
        return []

    pythoncom.CoInitialize()
    namespace = None
    outlook = None
    try:
        outlook = win32_client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        calendar = namespace.GetDefaultFolder(9)
        items = calendar.Items
        items.Sort("[Start]")
        items.IncludeRecurrences = True

        now = datetime.now()
        end = now + timedelta(days=14)
        start_text = now.strftime("%m/%d/%Y %I:%M %p")
        end_text = end.strftime("%m/%d/%Y %I:%M %p")
        restricted = items.Restrict(
            f"[Start] >= '{start_text}' AND [Start] <= '{end_text}'"
        )

        events = []
        for item in restricted:
            try:
                start = getattr(item, "Start", None)
                finish = getattr(item, "End", None)
                events.append({
                    "subject": str(getattr(item, "Subject", "") or "(no subject)"),
                    "start": start.strftime("%a %b %d • %I:%M %p") if start else "",
                    "end": finish.strftime("%I:%M %p") if finish else "",
                    "location": str(getattr(item, "Location", "") or ""),
                })
                if len(events) >= 20:
                    break
            except Exception:
                continue
        return events
    except Exception as exc:
        return [{
            "subject": f"Calendar unavailable: {exc}",
            "start": "",
            "end": "",
            "location": "",
        }]
    finally:
        namespace = None
        outlook = None
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def get_work_emails(limit=8):
    emails = []
    try:
        secret_script = os.path.expandvars(r'%APPDATA%\himalaya\get-mail-password.ps1')
        result = subprocess.run(
            ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', secret_script],
            capture_output=True,
            text=True,
            timeout=7,
        )
        password = result.stdout.strip()
        if not password:
            raise RuntimeError('mail password helper returned no password')
        mail = imaplib.IMAP4_SSL('east.EXCH129.serverdata.net', 993)
        mail.login(os.getenv('JARVIS_WORK_EMAIL_ADDRESS', ''), password)
        mail.select('INBOX')
        status, messages = mail.search(None, 'ALL')
        if status == 'OK':
            ids = messages[0].split()
            for msg_id in reversed(ids[-limit:]):
                _, msg_data = mail.fetch(msg_id, '(RFC822.HEADER)')
                for part in msg_data:
                    if isinstance(part, tuple):
                        msg = email.message_from_bytes(part[1])
                        emails.append({
                            'id': msg_id.decode('utf-8', errors='ignore'),
                            'subject': str(msg.get('Subject') or '(No Subject)'),
                            'from': str(msg.get('From') or 'Unknown'),
                            'date': str(msg.get('Date') or ''),
                        })
        mail.logout()
    except Exception as exc:
        emails.append({'id': '0', 'subject': f'Email unavailable: {exc}', 'from': 'System', 'date': ''})
    return emails


def get_projects():
    roots = [
        os.path.join(os.path.expanduser('~'), 'Jarvis'),
        os.path.join(os.path.expanduser('~'), 'Documents'),
        os.path.join(os.path.expanduser('~'), 'GitHub'),
    ]
    projects = []
    seen = set()
    preferred = {'Jarvis', 'DailyBreadpluzx', 'Scan2Cookz'}
    for root in roots:
        if not os.path.exists(root):
            continue
        if os.path.basename(root) == 'Jarvis':
            candidates = [root]
        else:
            try:
                candidates = [os.path.join(root, item) for item in os.listdir(root)]
            except Exception:
                candidates = []
        for full in candidates:
            if not os.path.isdir(full):
                continue
            name = os.path.basename(full)
            if root != os.path.join(os.path.expanduser('~'), 'Jarvis') and name not in preferred and not os.path.isdir(os.path.join(full, '.git')):
                continue
            key = os.path.normcase(full)
            if key in seen:
                continue
            seen.add(key)
            projects.append({
                'name': 'Jarvis Core OS' if name == 'Jarvis' else name,
                'path': full,
                'type': 'Primary AI Assistant' if name == 'Jarvis' else 'Managed Project',
                'status': 'ACTIVE' if name == 'Jarvis' else 'READY',
                'last_modified': time.ctime(os.path.getmtime(full)),
            })
    return projects


def ipc_is_online():
    try:
        with urllib.request.urlopen(IPC_URL + '/state', timeout=0.35) as response:
            return response.status == 200
    except Exception:
        return False


def send_command_to_jarvis(command_text, with_metadata=False):
    payload = json.dumps({'command': command_text}).encode('utf-8')

    def _request_once():
        request = urllib.request.Request(
            IPC_URL + '/command',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=1800) as response:
            data = json.loads(response.read().decode('utf-8'))
            if with_metadata:
                return data
            return data.get('response') or data.get('error') or 'Command completed.'

    last_error = None
    for attempt in range(2):
        try:
            return _request_once()
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.20)

    lower = str(command_text or '').lower()
    negative_restart = any(x in lower for x in (
        "do not restart", "don't restart", "dont restart",
        "without restart", "without restarting", "restart yet",
    ))
    restartish = (
        not negative_restart
        and ("restart" in lower or "reboot" in lower)
        and any(x in lower for x in ("jarvis", "all systems", "everything", "shutdown", "shut down"))
    )
    if restartish:
        return "Jarvis accepted the restart command. Waiting for the fresh stack to come online."

    message = f'Jarvis IPC is offline: {last_error}'
    if with_metadata:
        return {'status': 'error', 'error': message, 'attachment_accepted': False}
    return message


APP_COMMANDS={
'calculator':[['calc.exe']],'outlook':[['cmd.exe','/c','start','','outlook']],
'word':[['cmd.exe','/c','start','','winword']],'excel':[['cmd.exe','/c','start','','excel']],
'powerpoint':[['cmd.exe','/c','start','','powerpnt']],'notepad':[['notepad.exe']],
'explorer':[['explorer.exe']],'cmd':[['cmd.exe']],'terminal':[['powershell.exe']],
'settings':[['cmd.exe','/c','start','','ms-settings:']],
'chrome':[[r'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'],[r'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'],['cmd.exe','/c','start','','chrome']],
'vscode':[['cmd.exe','/c','start','','code']],
'steam':[[r'C:\\Program Files (x86)\\Steam\\steam.exe'],[r'C:\\Program Files\\Steam\\steam.exe'],['cmd.exe','/c','start','','steam']],
'visualstudio':[[r'C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\Common7\\IDE\\devenv.exe'],[r'C:\\Program Files\\Microsoft Visual Studio\\2022\\Professional\\Common7\\IDE\\devenv.exe']],
'androidstudio':[[r'C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe']],
'unreal':[[r'C:\\Program Files\\Epic Games\\UE_5.7\\Engine\\Binaries\\Win64\\UnrealEditor.exe'],[r'C:\\Program Files\\Epic Games\\UE_5.6\\Engine\\Binaries\\Win64\\UnrealEditor.exe'],[r'C:\\Program Files\\Epic Games\\UE_5.5\\Engine\\Binaries\\Win64\\UnrealEditor.exe']],
'blender':[[r'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe'],[r'C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe'],[r'C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe'],[r'C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe'],['cmd.exe','/c','start','','blender']],
'discord':[[os.path.expandvars(r'%LOCALAPPDATA%\\Discord\\Update.exe'),'--processStart','Discord.exe']],
'epic':[[r'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe']],
'obs':[[r'C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe']],
'edge':[[r'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe']]}

def _candidate_works(command):
    if not command:return False
    exe=str(command[0])
    return os.path.exists(exe) if os.path.isabs(exe) else True



def _dashboard_spawn(command):
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
            )
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            **kwargs,
        )
    except Exception:
        pass


def launch_app(app_name):
    key = str(app_name or "").lower().strip()
    candidates = APP_COMMANDS.get(key)

    if not candidates:
        return False, f"Unknown application: {app_name}"

    for command in candidates:
        if not _candidate_works(command):
            continue

        # Never make the dashboard wait for a heavy app like Blender,
        # Android Studio, Steam, Unreal, or Visual Studio to finish booting.
        threading.Thread(
            target=_dashboard_spawn,
            args=(command,),
            daemon=True,
            name=f"DashboardLaunch-{key}",
        ).start()
        return True, f"{key.title()} is opening."

    return False, (
        f"I could not find {key}. "
        "The application may be installed in a different location."
    )


class DashboardHandler(BaseHTTPRequestHandler):
    def _upload_error(self, exc):
        if isinstance(exc, UploadError):
            error = exc
        elif isinstance(exc, (TimeoutError, socket.timeout)):
            error = UploadError('The upload connection timed out. Press Retry to continue from the saved bytes.', 408, 'upload_timeout')
        elif isinstance(exc, OSError):
            error = UploadError('Could not save the attachment: ' + str(exc), 507, 'upload_storage_error')
        else:
            error = UploadError('Invalid upload request: ' + str(exc), 400, 'invalid_upload')
        log_http(f'upload_error code={error.code} detail={error}')
        return self.send_json(error.payload(), error.status)

    def _read_upload_body(self, length, maximum):
        if length < 0 or length > maximum:
            raise UploadError('Upload request exceeds its allowed chunk size.', 413, 'invalid_chunk')
        previous = self.connection.gettimeout()
        self.connection.settimeout(45)
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise UploadError('The connection ended during upload. Press Retry to continue.', 408, 'upload_interrupted')
            return body
        finally:
            self.connection.settimeout(previous)

    def _project_upload_post(self, path, length):
        try:
            match = re.fullmatch(r'/api/uploads/([a-f0-9]{32})/(chunk|complete|cancel)', path)
            if match and match[2] == 'chunk':
                body = self._read_upload_body(length, CHUNK_BYTES)
                try:
                    offset = int(self.headers.get('X-Upload-Offset', '-1'))
                except ValueError:
                    raise UploadError('Invalid upload offset.')
                data = PROJECT_UPLOADS.chunk(match[1], offset, body)
            else:
                body = self._read_upload_body(length, 64 * 1024)
                payload = json.loads(body or b'{}')
                if path == '/api/uploads':
                    data = PROJECT_UPLOADS.create(payload)
                elif match and match[2] == 'complete':
                    data = PROJECT_UPLOADS.complete(match[1])
                    log_http(f'project_attachment_ready id={data["id"]} bytes={data["size"]} entries={data.get("zip_entries")}')
                elif match and match[2] == 'cancel':
                    data = PROJECT_UPLOADS.cancel(match[1])
                else:
                    raise UploadError('Unknown upload endpoint.', 404, 'upload_not_found')
            return self.send_json(data)
        except (UploadError, OSError, ValueError, TypeError) as exc:
            return self._upload_error(exc)

    def log_message(self, format, *args):
        log_http(f'{self.client_address[0]} {self.command} {self.path} :: ' + (format % args))

    def send_json(self, data, status=200):
        content = json.dumps(data, default=str).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def send_file(self, path, content_type, head_only=False):
        if not os.path.exists(path):
            self.send_error(404)
            return
        content_length = os.path.getsize(path)
        content = None
        if not head_only:
            with open(path, 'rb') as handle:
                content = handle.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-Length', str(content_length))
        self.end_headers()
        if content is not None:
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

    def do_HEAD(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith('/airtouch/'):
            return self.send_error(404)
        relative = path[len('/airtouch/'):].replace('\\', '/')
        normalized = os.path.normpath(relative)
        if normalized.startswith('..') or os.path.isabs(normalized):
            return self.send_error(403)
        file_path = os.path.join(AIRTOUCH_DIR, normalized)
        extension = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.js': 'application/javascript; charset=utf-8',
            '.mjs': 'application/javascript; charset=utf-8',
            '.wasm': 'application/wasm',
            '.task': 'application/octet-stream',
            '.json': 'application/json; charset=utf-8',
        }
        return self.send_file(
            file_path,
            content_types.get(extension, 'application/octet-stream'),
            head_only=True,
        )

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ('/', '/index.html'):
            return self.send_file(os.path.join(UI_DIR, 'index.html'), 'text/html; charset=utf-8')
        if path == '/styles.css':
            return self.send_file(os.path.join(UI_DIR, 'styles.css'), 'text/css; charset=utf-8')
        if path == '/app.js':
            return self.send_file(os.path.join(UI_DIR, 'app.js'), 'application/javascript; charset=utf-8')
        if path == '/project-upload.js':
            return self.send_file(os.path.join(UI_DIR, 'project-upload.js'), 'application/javascript; charset=utf-8')
        if re.fullmatch(r'/api/uploads/[a-f0-9]{32}', path):
            try:
                return self.send_json(PROJECT_UPLOADS.status(path.rsplit('/', 1)[-1]))
            except (UploadError, OSError, ValueError) as exc:
                return self._upload_error(exc)
        if path.startswith('/airtouch/'):
            relative = path[len('/airtouch/'):].replace('\\', '/')
            normalized = os.path.normpath(relative)
            if normalized.startswith('..') or os.path.isabs(normalized):
                return self.send_error(403)
            file_path = os.path.join(AIRTOUCH_DIR, normalized)
            extension = os.path.splitext(file_path)[1].lower()
            content_types = {
                '.js': 'application/javascript; charset=utf-8',
                '.mjs': 'application/javascript; charset=utf-8',
                '.wasm': 'application/wasm',
                '.task': 'application/octet-stream',
                '.json': 'application/json; charset=utf-8',
            }
            return self.send_file(file_path, content_types.get(extension, 'application/octet-stream'))
        if path == '/api/airtouch/settings':
            return self.send_json(get_airtouch_settings())
        if path == '/api/airtouch/target':
            return self.send_json(get_airtouch_target())
        if path == '/api/live_state':
            return self.send_json(get_live_state())
        if path == '/api/nvidia/model':
            try:
                return self.send_json({'status':'ok', **save_nvidia_selection(data.get('model','auto'))})
            except Exception as exc:
                return self.send_json({'status':'error','error':str(exc)},400)

        if path == '/api/layout':
            return self.send_json(get_dashboard_layout())
        if path.startswith('/api/command/'):
            job_id = path.rsplit('/', 1)[-1]
            job = get_command_job(job_id)
            if job is None:
                return self.send_json({'status': 'error', 'error': 'Unknown command job.'}, 404)
            return self.send_json(job)
        if path == '/api/diagnostics/logs':
            def _tail(path_name, limit=120):
                try:
                    with open(path_name, 'r', encoding='utf-8', errors='replace') as fh:
                        return fh.readlines()[-limit:]
                except Exception as exc:
                    return [f'log unavailable: {exc}\n']
            return self.send_json({
                'ok': True,
                'http_log': ''.join(_tail(DASHBOARD_HTTP_LOG)),
                'frontend_log': ''.join(_tail(FRONTEND_LOG)),
            })

        if path == '/api/health':
            # Deliberately cheap liveness probe for the browser/startup watchdog.
            # Never call IPC, hardware sensors, providers, Qwen, or cloud APIs here.
            return self.send_json({
                'ok': True,
                'service': 'jarvis-dashboard',
                'build_id': DASHBOARD_BUILD_ID,
                'pid': os.getpid(),
                'started_at': DASHBOARD_STARTED_AT,
                'project_uploads': {'protocol': 2, 'max_bytes': MAX_UPLOAD_BYTES, 'chunk_bytes': CHUNK_BYTES},
                'time': datetime.now().isoformat(timespec='milliseconds'),
            })
        if path == '/api/status':
            return self.send_json(get_system_status())
        if path == '/api/restart/status':
            status = safe_json_file(RESTART_STATUS_FILE, {'stage':'idle','success':False})
            # A stale restart_status.json must never blank a healthy dashboard.
            # Only report an active restart while the supervisor flag exists.
            status['active'] = bool(os.path.exists(os.path.join(JARVIS_DIR, 'restart_in_progress.flag')))
            return self.send_json(status)
        if path == '/api/telemetry':
            return self.send_json(get_telemetry())
        if path == '/api/voice_state':
            return self.send_json(get_voice_state())
        if path == '/api/hardware':
            return self.send_json(get_hardware_snapshot())
        if path.startswith('/downloads/'):
            filename = os.path.basename(urllib.parse.unquote(path[len('/downloads/'):]))
            candidate = os.path.abspath(os.path.join(GENERATED_PROJECTS_DIR, filename))
            root_abs = os.path.abspath(GENERATED_PROJECTS_DIR)
            if not filename.lower().endswith('.zip') or os.path.dirname(candidate) != root_abs or not os.path.isfile(candidate):
                return self.send_error(404)
            try:
                size = os.path.getsize(candidate)
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Content-Length', str(size))
                self.end_headers()
                with open(candidate, 'rb') as handle:
                    shutil.copyfileobj(handle, self.wfile)
                return
            except Exception:
                return self.send_error(500)
        if path == '/api/providers':
            return self.send_json(get_provider_status())
        if path == '/api/voice/catalog':
            return self.send_json(get_voice_catalog_dashboard())
        if path == '/api/nvidia/models':
            query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            force=str((query.get('refresh') or ['0'])[0]).lower() in {'1','true','yes'}
            return self.send_json(get_nvidia_models_dashboard(force=force))
        if path == '/api/agents':
            return self.send_json(normalize_agents())
        if path == '/api/calendar':
            return self.send_json(get_calendar_events())
        if path == '/api/email':
            return self.send_json(get_work_emails())
        if path == '/api/projects':
            return self.send_json(get_projects())
        if path == '/api/apps':
            return self.send_json(sorted(APP_COMMANDS.keys()))
        self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length < 0:
                raise ValueError('negative length')
        except ValueError:
            return self.send_json({'status': 'error', 'error': 'Invalid Content-Length.'}, 400)

        if path == '/api/uploads' or path.startswith('/api/uploads/'):
            return self._project_upload_post(path, length)

        # v2.60 chat attachments use a raw-body upload to avoid multipart parser
        # dependencies on Python 3.13. The browser sends the original name in a
        # dedicated header; Jarvis stores a UUID-prefixed local copy.
        if path == '/api/upload':
            if length <= 0:
                return self.send_json({'status':'error','error':'Empty upload.'},400)
            if length > MAX_UPLOAD_BYTES:
                return self.send_json({'status':'error','error':f'File exceeds {MAX_UPLOAD_BYTES//(1024*1024)} MB upload limit.'},413)
            raw_name = urllib.parse.unquote(str(self.headers.get('X-Filename','upload.bin')))
            safe_name = os.path.basename(raw_name.replace('\\','/')).strip() or 'upload.bin'
            safe_name = ''.join(ch for ch in safe_name if ch.isalnum() or ch in ' ._()-[]')[:180]
            ext = os.path.splitext(safe_name)[1].lower()
            if ext not in ALLOWED_UPLOAD_EXTENSIONS:
                return self.send_json({'status':'error','error':f'Unsupported attachment type: {ext or "no extension"}'},415)
            upload_id = uuid.uuid4().hex
            stored_name = f'{upload_id}_{safe_name}'
            target = os.path.abspath(os.path.join(UPLOADS_DIR, stored_name))
            if not target.startswith(os.path.abspath(UPLOADS_DIR) + os.sep):
                return self.send_json({'status':'error','error':'Unsafe upload name.'},400)
            remaining=length
            try:
                with open(target,'wb') as fh:
                    while remaining>0:
                        chunk=self.rfile.read(min(1024*1024,remaining))
                        if not chunk: break
                        fh.write(chunk); remaining-=len(chunk)
                if remaining != 0:
                    raise IOError('Upload ended before Content-Length bytes were received.')
                if ext == '.zip':
                    validate_zip(target)
            except Exception as exc:
                try: os.remove(target)
                except Exception: pass
                return self._upload_error(exc)
            log_http(f'chat_upload name={safe_name!r} bytes={length} stored={target!r}')
            return self.send_json({'status':'ok','id':upload_id,'name':safe_name,'path':target,'size':length,'kind':'zip' if ext=='.zip' else 'file'})

        if length > 1024 * 1024:
            return self.send_json({'status': 'error', 'error': 'JSON request is too large.'}, 413)
        try:
            data = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
            if not isinstance(data, dict):
                raise ValueError('JSON object required')
        except Exception:
            return self.send_json({'status': 'error', 'error': 'Invalid JSON request.'}, 400)

        if path == '/api/voice/settings':
            try:
                settings = save_voice_settings_dashboard(data)
                return self.send_json({'status':'ok','settings':settings})
            except Exception as exc:
                return self.send_json({'status':'error','error':str(exc)},400)

        if path == '/api/voice/preview':
            provider = str(data.get('provider','')).strip().lower()
            voice = str(data.get('voice','')).strip()
            phrase = str(data.get('phrase','Hello, sir. Jarvis voice preview online.')).strip()
            if provider not in {'kokoro','piper','elevenlabs'} or not voice:
                return self.send_json({'status':'error','error':'Invalid provider or voice.'},400)
            # Save the clicked voice BEFORE previewing it so the previewed voice
            # becomes Jarvis's active voice, exactly as the UI promises.
            settings_payload = {'provider': provider}
            if provider == 'kokoro':
                settings_payload['kokoro_voice'] = voice
            elif provider == 'piper':
                settings_payload['piper_voice'] = voice
            else:
                settings_payload['elevenlabs_voice_id'] = voice
            settings = save_voice_settings_dashboard(settings_payload)

            command = f"preview voice provider {provider} voice {voice} phrase {phrase}"
            response = send_command_to_jarvis(command)
            ok = bool(response) and 'failed' not in str(response).lower() and 'error' not in str(response).lower()
            return self.send_json({
                'status':'ok' if ok else 'error',
                'message':response or 'No response from Jarvis voice engine.',
                'settings':settings,
                'provider':provider,
                'voice':voice,
            },200 if ok else 503)

        if path == '/api/layout':
            try:
                layout = save_dashboard_layout(data)
            except (OSError, ValueError) as exc:
                return self.send_json({'status': 'error', 'error': str(exc)}, 400)
            return self.send_json(layout)

        if path == '/api/airtouch/settings':
            return self.send_json(save_airtouch_settings(data))
        if path == '/api/airtouch/target':
            return self.send_json(save_airtouch_target(data))
        if path == '/api/airtouch/emergency_stop':
            return self.send_json({'status': 'ok', 'settings': airtouch_emergency_stop()})
        if path == '/api/airtouch/external':
            ok, message = _airtouch_external_action(data)
            return self.send_json({'status': 'ok' if ok else 'error', 'message': message}, 200 if ok else 403)
        if path == '/api/client-log':
            event = str(data.get('event', 'client')).strip()[:120]
            detail = str(data.get('detail', '')).replace('\r',' ').replace('\n',' ')[:4000]
            meta = data.get('meta', {})
            try:
                meta_text = json.dumps(meta, default=str)[:4000]
            except Exception:
                meta_text = '{}'
            log_frontend(f'{event} | {detail} | meta={meta_text}')
            return self.send_json({'ok': True})

        if path == '/api/command':
            command = str(data.get('command', '')).strip()
            try:
                supplied = data.get('attachments', [])
                require_zip = data.get('require_project_zip') is True or (not supplied and needs_project_zip(command))
                attachments = PROJECT_UPLOADS.resolve_attachments(supplied, require_zip=require_zip)
            except (UploadError, OSError, ValueError) as exc:
                return self._upload_error(exc)
            if not command:
                return self.send_json({'status': 'error', 'response': 'Type a command first.'}, 400)
            qwen_profile = str(data.get('qwen_profile') or '').strip().lower()
            if qwen_profile not in {'auto','8b','9b35','27b38q2','27b'}:
                qwen_profile = ''
            job_id = queue_dashboard_command(command, attachments=attachments, qwen_profile=qwen_profile)
            return self.send_json({
                'status': 'accepted',
                'command': command,
                'job_id': job_id,
            }, 202)

        if path == '/api/apps/launch':
            ok, message = launch_app(data.get('app'))
            return self.send_json({'status': 'ok' if ok else 'error', 'message': message}, 200 if ok else 400)

        if path == '/api/controls/action':
            action = str(data.get('action', ''))
            if action == 'ping':
                return self.send_json({'status': 'ok', 'message': 'Jarvis dashboard and local API are online.'})
            if action == 'test_speech':
                response = send_command_to_jarvis('Say dashboard voice test successful.')
                return self.send_json({'status': 'ok', 'message': response})
            if action == 'open_apps':
                return self.send_json({'status': 'ok', 'message': 'Application launcher opened.'})
            return self.send_json({'status': 'ok', 'message': f'Action {action} acknowledged.'})

        self.send_error(404)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/layout':
            reset_dashboard_layout()
            return self.send_json({'status': 'ok'})
        self.send_error(404)


def _dashboard_auto_open_enabled():
    value = str(os.environ.get('JARVIS_DASHBOARD_AUTO_OPEN', '1')).strip().lower()
    return value not in {'0', 'false', 'no', 'off'}


def _dashboard_browser_candidates():
    """Return installed Chromium browsers in standalone-window preference order."""
    raw = []
    local = os.environ.get('LOCALAPPDATA', '')
    program = os.environ.get('ProgramFiles', '')
    program_x86 = os.environ.get('ProgramFiles(x86)', '')
    for base, tail in (
        (local, ('Google', 'Chrome', 'Application', 'chrome.exe')),
        (program, ('Google', 'Chrome', 'Application', 'chrome.exe')),
        (program_x86, ('Google', 'Chrome', 'Application', 'chrome.exe')),
        (program_x86, ('Microsoft', 'Edge', 'Application', 'msedge.exe')),
        (program, ('Microsoft', 'Edge', 'Application', 'msedge.exe')),
        (local, ('Microsoft', 'Edge', 'Application', 'msedge.exe')),
    ):
        if base:
            raw.append(os.path.join(base, *tail))
    raw.extend(filter(None, (shutil.which('chrome.exe'), shutil.which('chrome'),
                             shutil.which('msedge.exe'), shutil.which('msedge'))))
    found = []
    seen = set()
    for path in raw:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized not in seen and os.path.isfile(path):
            seen.add(normalized)
            found.append(path)
    return found


def _open_dashboard_window(url):
    """Open the verified Jarvis HUD, never an unverified llama.cpp endpoint."""
    clean_url = str(url or '').rstrip('/')
    ready = False
    for _attempt in range(40):
        try:
            request = urllib.request.Request(
                clean_url + '/api/health?launcher=' + urllib.parse.quote(DASHBOARD_BUILD_ID),
                headers={'Cache-Control': 'no-cache'},
            )
            with urllib.request.urlopen(request, timeout=0.45) as response:
                health = json.loads(response.read().decode('utf-8'))
            ready = (
                health.get('ok') is True
                and health.get('service') == 'jarvis-dashboard'
                and health.get('build_id') == DASHBOARD_BUILD_ID
            )
            if ready:
                break
        except Exception:
            pass
        time.sleep(0.10)
    if not ready:
        log_http(f'AUTO_OPEN refused unverified endpoint url={clean_url}')
        return False

    launch_url = clean_url + '/index.html?jarvis_dashboard=' + urllib.parse.quote(DASHBOARD_BUILD_ID)
    if os.name == 'nt':
        profile_root = os.path.join(
            os.environ.get('LOCALAPPDATA') or JARVIS_DIR,
            'JarvisDashboard', 'BrowserProfileV2',
        )
        try:
            os.makedirs(profile_root, exist_ok=True)
        except Exception:
            profile_root = ''
        for browser in _dashboard_browser_candidates():
            try:
                command = [browser, f'--app={launch_url}', '--start-maximized', '--new-window', '--no-first-run']
                if profile_root:
                    command.append(f'--user-data-dir={profile_root}')
                subprocess.Popen(
                    command,
                    cwd=JARVIS_DIR,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
                log_http(f'AUTO_OPEN browser={os.path.basename(browser)} mode=standalone')
                return True
            except Exception as exc:
                log_http(f'AUTO_OPEN candidate_failed browser={browser} error={exc}')
        try:
            os.startfile(launch_url)
            log_http('AUTO_OPEN browser=windows-default mode=url')
            return True
        except Exception as exc:
            log_http(f'AUTO_OPEN windows_default_failed error={exc}')
    try:
        opened = bool(webbrowser.open(launch_url, new=1, autoraise=True))
        log_http(f'AUTO_OPEN browser=python-default opened={opened}')
        return opened
    except Exception as exc:
        log_http(f'AUTO_OPEN failed error={exc}')
        return False


def _dashboard_port_candidates():
    candidates = []
    for candidate in (PORT, 8080, 8079, 8082, 8090):
        if candidate == _QWEN_SERVER_PORT or candidate in candidates:
            continue
        if 1 <= int(candidate) <= 65535:
            candidates.append(int(candidate))
    return candidates


def _create_dashboard_server():
    failures = []
    for candidate in _dashboard_port_candidates():
        try:
            return ThreadingHTTPServer(('127.0.0.1', candidate), DashboardHandler)
        except OSError as exc:
            failures.append(f'{candidate}: {exc}')
            log_http(f'PORT_UNAVAILABLE port={candidate} error={exc}')
    raise OSError('No Jarvis dashboard port was available. ' + '; '.join(failures))


def _write_dashboard_endpoint(url, port):
    payload = {
        'service': 'jarvis-dashboard', 'build_id': DASHBOARD_BUILD_ID,
        'url': url, 'port': int(port), 'pid': os.getpid(),
        'started_at': DASHBOARD_STARTED_AT,
    }
    temporary = DASHBOARD_ENDPOINT_FILE + '.tmp'
    try:
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)
        os.replace(temporary, DASHBOARD_ENDPOINT_FILE)
    except Exception as exc:
        log_http(f'ENDPOINT_FILE_FAILED error={exc}')


def run_server(open_browser=True):
    # A fresh dashboard process is a fresh Air Touch session. Never restore the
    # prior master/camera runtime state, but leave every preference untouched.
    reset_airtouch_startup_state()
    server = _create_dashboard_server()
    actual_port = int(server.server_address[1])
    url = f'http://127.0.0.1:{actual_port}'
    _write_dashboard_endpoint(url, actual_port)
    print(f'Jarvis Command Center v5.2 ({DASHBOARD_BUILD_ID}) running at {url}')
    log_http(f'START pid={os.getpid()} build={DASHBOARD_BUILD_ID} url={url}')
    if IMPORT_ERROR:
        print(f'Jarvis backend import warning: {IMPORT_ERROR}')
    if open_browser:
        opener = threading.Timer(0.35, _open_dashboard_window, args=(url,))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down dashboard.')
    finally:
        server.server_close()


if __name__ == '__main__':
    run_server(open_browser=_dashboard_auto_open_enabled())

