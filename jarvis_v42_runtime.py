"""Jarvis V42 capability, environment and command-broker runtime.

This module intentionally keeps the model away from raw process execution.  It is
not a VM security boundary; it is a controlled project workspace/runtime layer
with capability discovery, per-project caches, structured command evidence and
optional stronger Docker/WSL backends.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

V42_RUNTIME_VERSION = "42.49.0"
V42_RUNTIME_ENGINE = "REVISION_SCOPED_CONVERGENCE_COMMAND_BROKER_V4242"
CAPABILITY_FILE = "JARVIS_V42_CAPABILITIES.json"
READINESS_FILE = "JARVIS_V42_TOOLCHAIN_READINESS.json"
ENVIRONMENT_FILE = "JARVIS_V42_ENVIRONMENT.json"
COMMAND_LOG_FILE = "JARVIS_V42_COMMANDS.jsonl"
POLICY_FILE = "V42_RUNTIME_POLICY.json"

_TRUE = {"1", "true", "yes", "on"}

def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in _TRUE


def _atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _safe_text(value: object, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


# Executable aliases. The first resolvable executable wins.
_TOOL_ALIASES: Dict[str, List[str]] = {
    "python": ["python", "python3", "py"], "pip": ["pip", "pip3"],
    "node": ["node"], "npm": ["npm", "npm.cmd"], "npx": ["npx", "npx.cmd"],
    "pnpm": ["pnpm", "pnpm.cmd"], "yarn": ["yarn", "yarn.cmd"], "bun": ["bun"],
    "cargo": ["cargo"], "rustc": ["rustc"], "rustup": ["rustup"],
    "git": ["git"], "cmake": ["cmake"], "ctest": ["ctest"], "ninja": ["ninja"],
    "make": ["make", "mingw32-make", "nmake"], "clang": ["clang"], "clang++": ["clang++"],
    "gcc": ["gcc"], "g++": ["g++"], "cl": ["cl.exe", "cl"],
    "dotnet": ["dotnet"], "msbuild": ["msbuild", "MSBuild.exe"],
    "java": ["java"], "javac": ["javac"], "gradle": ["gradle", "gradle.bat"],
    "maven": ["mvn", "mvn.cmd"], "go": ["go"], "flutter": ["flutter", "flutter.bat"],
    "dart": ["dart", "dart.exe"], "adb": ["adb", "adb.exe"], "sdkmanager": ["sdkmanager", "sdkmanager.bat"],
    "swift": ["swift"], "xcodebuild": ["xcodebuild"], "godot": ["godot", "godot4", "godot.exe"],
    "unity": ["Unity.exe", "Unity"], "unrealbuildtool": ["UnrealBuildTool.exe", "UnrealBuildTool"],
    "docker": ["docker", "docker.exe"], "wsl": ["wsl", "wsl.exe"],
    "sqlite3": ["sqlite3"], "psql": ["psql"], "mysql": ["mysql"],
    "composer": ["composer", "composer.bat"], "php": ["php"], "ruby": ["ruby"], "bundle": ["bundle", "bundle.bat"],
    "zig": ["zig"], "nim": ["nim"], "nimble": ["nimble"], "odin": ["odin"],
    "elixir": ["elixir"], "mix": ["mix"], "erl": ["erl"], "rebar3": ["rebar3"],
    "ghc": ["ghc"], "cabal": ["cabal"], "ocaml": ["ocaml"], "dune": ["dune"], "sbt": ["sbt"],
    "lua": ["lua"], "luac": ["luac"], "perl": ["perl"], "rscript": ["Rscript"], "julia": ["julia"],
    "terraform": ["terraform"], "pio": ["pio"], "idf.py": ["idf.py"], "xmake": ["xmake"],
    "rg": ["rg"], "fd": ["fd", "fdfind"], "jq": ["jq"], "curl": ["curl"], "7zip": ["7z", "7zz"],
    "winget": ["winget", "winget.exe"], "choco": ["choco", "choco.exe"], "scoop": ["scoop", "scoop.cmd"],
    "deno": ["deno", "deno.exe"], "corepack": ["corepack", "corepack.cmd"],
    "pwsh": ["pwsh", "pwsh.exe"], "powershell": ["powershell", "powershell.exe"], "bash": ["bash", "bash.exe"],
    "kubectl": ["kubectl", "kubectl.exe"], "helm": ["helm", "helm.exe"], "podman": ["podman", "podman.exe"],
    "uv": ["uv", "uv.exe"], "poetry": ["poetry", "poetry.exe"], "pytest": ["pytest", "pytest.exe"],
    "ruff": ["ruff", "ruff.exe"], "mypy": ["mypy", "mypy.exe"],
    "clojure": ["clojure", "clojure.exe"], "lein": ["lein", "lein.bat"], "bb": ["bb", "bb.exe"],
    "crystal": ["crystal", "crystal.exe"], "racket": ["racket", "racket.exe"], "raco": ["raco", "raco.exe"],
    "nvcc": ["nvcc", "nvcc.exe"], "gfortran": ["gfortran", "gfortran.exe"],
    "wasm-pack": ["wasm-pack", "wasm-pack.exe"], "wasm-bindgen": ["wasm-bindgen", "wasm-bindgen.exe"],
}

_VERSION_ARGS: Dict[str, List[str]] = {
    "python": ["--version"], "pip": ["--version"], "node": ["--version"], "npm": ["--version"],
    "pnpm": ["--version"], "yarn": ["--version"], "cargo": ["--version"], "rustc": ["--version"],
    "git": ["--version"], "cmake": ["--version"], "ninja": ["--version"], "clang": ["--version"],
    "gcc": ["--version"], "dotnet": ["--version"], "java": ["-version"], "javac": ["-version"],
    "gradle": ["--version"], "maven": ["--version"], "go": ["version"], "flutter": ["--version"],
    "dart": ["--version"], "adb": ["version"], "docker": ["--version"], "wsl": ["--version"],
    "sqlite3": ["--version"], "php": ["--version"], "ruby": ["--version"], "zig": ["version"],
    "terraform": ["version"], "rg": ["--version"], "fd": ["--version"], "jq": ["--version"],
    "deno": ["--version"], "pwsh": ["--version"], "powershell": ["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
    "kubectl": ["version", "--client"], "helm": ["version", "--short"], "podman": ["--version"],
    "uv": ["--version"], "poetry": ["--version"], "pytest": ["--version"], "ruff": ["--version"], "mypy": ["--version"],
    "clojure": ["-Sdescribe"], "lein": ["version"], "bb": ["--version"], "crystal": ["--version"], "racket": ["--version"],
    "nvcc": ["--version"], "gfortran": ["--version"], "wasm-pack": ["--version"],
}

_HEAVY_TOOLS = {"unity", "unrealbuildtool", "xcodebuild", "android sdk", "msvc", "visual studio", "flutter"}


def _windows_program_roots() -> List[Path]:
    vals: List[Path] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        v = os.getenv(key)
        if v:
            vals.append(Path(v))
    vals.extend([Path("C:/Program Files"), Path("C:/Program Files (x86)")])
    out: List[Path] = []
    seen = set()
    for p in vals:
        key = str(p).lower()
        if key not in seen:
            seen.add(key); out.append(p)
    return out


def _find_common_install(name: str) -> str:
    low = name.lower()
    if os.name != "nt":
        return ""
    env_map = {
        "unity": ("JARVIS_UNITY_EDITOR", "UNITY_EDITOR", "UNITY_PATH"),
        "unrealbuildtool": ("JARVIS_UNREAL_BUILD_TOOL", "UNREAL_BUILD_TOOL"),
        "android sdk": ("ANDROID_SDK_ROOT", "ANDROID_HOME"),
    }
    for key in env_map.get(low, ()):
        value = os.getenv(key, "").strip()
        if value and Path(value).exists():
            return str(Path(value))
    try:
        if low == "unity":
            candidates: List[Path] = []
            for root in _windows_program_roots():
                hub = root / "Unity" / "Hub" / "Editor"
                if hub.exists():
                    for ver in sorted(hub.iterdir(), reverse=True):
                        candidates.append(ver / "Editor" / "Unity.exe")
            return str(next((p for p in candidates if p.is_file()), ""))
        if low == "unrealbuildtool":
            candidates = []
            for root in _windows_program_roots():
                epic = root / "Epic Games"
                if epic.exists():
                    for ue in sorted(epic.glob("UE_*"), reverse=True):
                        candidates.extend([
                            ue / "Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe",
                            ue / "Engine/Binaries/DotNET/UnrealBuildTool.exe",
                        ])
            return str(next((p for p in candidates if p.is_file()), ""))
        if low in {"cl", "msvc"}:
            vswhere = Path(os.getenv("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
            if vswhere.is_file():
                try:
                    proc = subprocess.run([str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], capture_output=True, text=True, timeout=2)
                    base = Path((proc.stdout or "").strip())
                    if base.exists():
                        found = sorted(base.glob("VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"), reverse=True)
                        if found: return str(found[0])
                except Exception:
                    pass
        if low == "android sdk":
            defaults = [Path(os.getenv("LOCALAPPDATA", "")) / "Android/Sdk", Path.home() / "AppData/Local/Android/Sdk"]
            return str(next((p for p in defaults if p.exists()), ""))
    except Exception:
        return ""
    return ""


def _resolve_tool(name: str) -> str:
    key = str(name or "").strip().lower()
    aliases = _TOOL_ALIASES.get(key, [name])
    for alias in aliases:
        p = shutil.which(alias)
        if p:
            return str(Path(p))
    return _find_common_install(key)


def _probe_version(tool: str, path: str) -> str:
    if not path or Path(path).is_dir():
        return ""
    args = _VERSION_ARGS.get(tool.lower())
    if not args:
        return ""
    try:
        proc = subprocess.run([path, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2)
        text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return _safe_text(text.splitlines()[0] if text else "", 240)
    except Exception:
        return ""


def discover_capabilities(probe_versions: bool = False, only: Optional[Iterable[str]] = None) -> dict:
    names = list(dict.fromkeys([str(x).strip().lower() for x in (only or _TOOL_ALIASES.keys()) if str(x).strip()]))
    tools: Dict[str, dict] = {}

    def one(name: str) -> Tuple[str, dict]:
        path = _resolve_tool(name)
        version = _probe_version(name, path) if probe_versions and path else ""
        return name, {"available": bool(path), "path": path, "version": version}

    workers = min(12, max(1, len(names)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for name, row in pool.map(one, names):
            tools[name] = row

    # Virtual capabilities aggregate concrete tools/install roots.
    tools["c compiler"] = {"available": any(tools.get(x, {}).get("available") for x in ("cl","clang","gcc")), "path":"", "version":""}
    tools["c++ compiler"] = {"available": any(tools.get(x, {}).get("available") for x in ("cl","clang++","g++")), "path":"", "version":""}
    tools["compiler"] = {"available": bool(tools["c compiler"]["available"] or tools["c++ compiler"]["available"]), "path":"", "version":""}
    android = _find_common_install("android sdk") or os.getenv("ANDROID_SDK_ROOT", "") or os.getenv("ANDROID_HOME", "")
    tools["android sdk"] = {"available": bool(android and Path(android).exists()), "path": android, "version":""}
    tools["xcode"] = {"available": bool(tools.get("xcodebuild",{}).get("available")), "path": tools.get("xcodebuild",{}).get("path", ""), "version":""}
    tools["unreal engine"] = {"available": bool(tools.get("unrealbuildtool",{}).get("available")), "path": tools.get("unrealbuildtool",{}).get("path", ""), "version":""}
    tools["qt"] = {"available": bool(os.getenv("QTDIR") or shutil.which("qmake") or shutil.which("qtpaths")), "path": os.getenv("QTDIR", ""), "version":""}

    available = sorted(k for k,v in tools.items() if v.get("available"))
    return {
        "version": V42_RUNTIME_VERSION,
        "engine": V42_RUNTIME_ENGINE,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "host": {
            "os": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python": sys.version.split()[0], "cwd": str(Path.cwd()),
        },
        "tools": tools,
        "available_count": len(available),
        "known_count": len(tools),
        "available": available,
        "sandbox_backends": {
            "native_controlled": True,
            "docker": bool(tools.get("docker",{}).get("available")),
            "wsl": bool(tools.get("wsl",{}).get("available")),
        },
    }


def write_capability_report(directory: Path, probe_versions: bool = False, only: Optional[Iterable[str]] = None) -> dict:
    data = discover_capabilities(probe_versions=probe_versions, only=only)
    _atomic_json(Path(directory) / CAPABILITY_FILE, data)
    return data


_cached_lock = threading.RLock()
_cached_capabilities: Optional[dict] = None
_startup_thread: Optional[threading.Thread] = None


def get_cached_capabilities(refresh: bool = False, probe_versions: bool = False) -> dict:
    global _cached_capabilities
    with _cached_lock:
        if refresh or _cached_capabilities is None:
            _cached_capabilities = discover_capabilities(probe_versions=probe_versions)
        return json.loads(json.dumps(_cached_capabilities))


def _startup_scan_worker(jarvis_dir: Path) -> None:
    global _cached_capabilities
    try:
        data = discover_capabilities(probe_versions=False)
        with _cached_lock:
            _cached_capabilities = data
        _atomic_json(Path(jarvis_dir) / CAPABILITY_FILE, data)
    except Exception:
        pass


def start_background_startup_scan(jarvis_dir: Path) -> threading.Thread:
    global _startup_thread
    with _cached_lock:
        if _startup_thread and _startup_thread.is_alive():
            return _startup_thread
        _startup_thread = threading.Thread(target=_startup_scan_worker, args=(Path(jarvis_dir),), daemon=True, name="JarvisV42CapabilityScan")
        _startup_thread.start()
        return _startup_thread


def startup_summary(wait_seconds: float = 0.0) -> str:
    t = _startup_thread
    if t and wait_seconds > 0:
        t.join(timeout=wait_seconds)
    with _cached_lock:
        data = _cached_capabilities
    if not data:
        return "developer capability scan running"
    backends = data.get("sandbox_backends") or {}
    extra = []
    if backends.get("docker"): extra.append("Docker")
    if backends.get("wsl"): extra.append("WSL")
    suffix = (" + " + "/".join(extra)) if extra else ""
    return f"{data.get('available_count',0)}/{data.get('known_count',0)} developer capabilities detected; controlled native sandbox{suffix}"


_REQUIREMENT_ALIASES = {
    "gradle/gradlew": ["gradle"], "maven": ["maven"], "xcode": ["xcodebuild"],
    "unreal engine": ["unreal engine"], "unrealbuildtool": ["unrealbuildtool"], "unity": ["unity"],
    "qt": ["qt"], "c compiler": ["c compiler"], "c++ compiler": ["c++ compiler"], "compiler": ["compiler"],
}


def manifest_required_tools(manifest: dict, toolchains: Optional[dict] = None) -> List[str]:
    req: List[str] = []
    def add(x: object) -> None:
        v = str(x or "").strip().lower()
        if v and v not in req: req.append(v)
    for x in (manifest or {}).get("required_tools") or []: add(x)
    adapters = []
    primary = str((manifest or {}).get("toolchain_adapter") or "").strip()
    if primary: adapters.append(primary)
    for comp in (manifest or {}).get("components") or []:
        if isinstance(comp, dict):
            a = str(comp.get("toolchain_adapter") or "").strip()
            if a and a not in adapters: adapters.append(a)
            for x in comp.get("required_tools") or []: add(x)
    if isinstance(toolchains, dict):
        adapters_map = toolchains.get("adapters") if "adapters" in toolchains else toolchains
        for a in adapters:
            spec = (adapters_map or {}).get(a) or {}
            for x in spec.get("required_tools") or []: add(x)
    return req


def resolve_requirements(manifest: dict, capabilities: dict, toolchains: Optional[dict] = None) -> dict:
    reqs = manifest_required_tools(manifest, toolchains=toolchains)
    tools = capabilities.get("tools") or {}
    rows = []
    for req in reqs:
        aliases = _REQUIREMENT_ALIASES.get(req, [req])
        hits = [a for a in aliases if (tools.get(a) or {}).get("available")]
        rows.append({"requirement": req, "available": bool(hits), "providers": hits, "heavy": req in _HEAVY_TOOLS})
    missing = [x["requirement"] for x in rows if not x["available"]]
    return {
        "version": V42_RUNTIME_VERSION, "engine": V42_RUNTIME_ENGINE,
        "status": "READY" if not missing else "HOST_MISSING_TOOLS",
        "requirements": rows, "missing": missing,
        "sandbox_backends": capabilities.get("sandbox_backends") or {},
    }


def planner_capability_context(max_chars: int = 4200) -> str:
    data = get_cached_capabilities(refresh=False, probe_versions=False)
    avail = data.get("available") or []
    important = [x for x in avail if x in {
        "python","pip","node","npm","pnpm","cargo","rustc","git","cmake","ninja","cl","clang","gcc",
        "dotnet","java","gradle","maven","go","flutter","dart","adb","android sdk","docker","wsl",
        "unreal engine","unrealbuildtool","unity","godot","sqlite3"
    }]
    back = data.get("sandbox_backends") or {}
    text = (
        "V42 HOST CAPABILITY EVIDENCE (authoritative for local verification; do not change the requested stack):\n"
        f"Host: {data.get('host',{}).get('os')} {data.get('host',{}).get('machine')}\n"
        f"Available developer capabilities: {', '.join(important) if important else 'none detected yet'}\n"
        f"Execution backends: native-controlled=yes, docker={'yes' if back.get('docker') else 'no'}, wsl={'yes' if back.get('wsl') else 'no'}.\n"
        "If a requested SDK is missing, keep the requested ecosystem and mark that build path HOST UNVERIFIED; never substitute Python or another unrelated stack."
    )
    return text[:max_chars]


@dataclass
class CommandResult:
    ok: bool
    returncode: int
    command: List[str]
    cwd: str
    duration_ms: int
    stdout: str
    stderr: str
    timed_out: bool = False
    blocked: bool = False
    reason: str = ""
    backend: str = "native_controlled"

    @property
    def combined(self) -> str:
        return ((self.stdout or "") + "\n" + (self.stderr or "")).strip()


class CommandBroker:
    """Controlled process runner for generated-project commands.

    The broker never invokes a shell, blocks destructive host-management tools,
    gives every command a timeout, records structured evidence, and supplies
    project-local cache/build directories.  It is deliberately compatible with
    native Windows compilers/SDKs; Docker/WSL are optional stronger backends.
    """
    BLOCKED_BASENAMES = {
        "format", "format.com", "diskpart", "shutdown", "shutdown.exe", "reboot", "halt",
        "reg", "reg.exe", "bcdedit", "cipher", "takeown", "icacls",
    }
    BLOCKED_PATTERNS = [
        re.compile(r"(?i)(?:^|\s)(?:rm|del|erase)\s+.*(?:-rf|-r\s+-f|/s\s+/q).*(?:\\|/)(?:\s|$)"),
    ]

    def __init__(self, workspace: Path, log_path: Optional[Path] = None, backend: Optional[str] = None):
        self.workspace = Path(workspace).resolve()
        self.runtime_dir = self.workspace / ".jarvis_runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        # Build/dependency caches are shared across disposable resume trials.  Keeping
        # them under each trial caused multi-gigabyte duplicate Cargo trees.  State
        # and command logs remain trial-local; only rebuildable cache is shared.
        explicit_cache = os.getenv("JARVIS_SHARED_BUILD_CACHE", "").strip()
        if explicit_cache:
            self.cache_root = Path(explicit_cache).resolve()
        elif self.workspace.name == "working" or re.fullmatch(r"trial_\d+", self.workspace.name or ""):
            self.cache_root = (self.workspace.parent / ".jarvis_shared_build_cache").resolve()
        else:
            self.cache_root = (self.workspace / ".jarvis_runtime" / "build-cache").resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.log_path = Path(log_path) if log_path else self.runtime_dir / COMMAND_LOG_FILE
        requested = str(backend or os.getenv("JARVIS_SANDBOX_BACKEND", "native")).strip().lower()
        self.backend = {"native":"native_controlled","native_controlled":"native_controlled","wsl":"wsl","docker":"docker"}.get(requested, "native_controlled")

    def _prepare_env(self, env: Optional[dict] = None) -> dict:
        out = dict(os.environ)
        if env: out.update({str(k): str(v) for k,v in env.items()})
        # Generated projects do not automatically inherit Jarvis/provider credentials.
        # Private dependency workflows can opt in explicitly when those credentials are truly required.
        if not _flag("JARVIS_SANDBOX_INHERIT_PROVIDER_SECRETS", False):
            passthrough = {
                value.strip().upper()
                for value in os.getenv("JARVIS_SANDBOX_PASSTHROUGH_ENV", "").split(",")
                if value.strip()
            }
            secret_names = {
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "ELEVENLABS_API_KEY", "HF_TOKEN", "HUGGINGFACE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
            }
            for key in list(out):
                if str(key).upper() in secret_names and str(key).upper() not in passthrough:
                    out.pop(key, None)
            # Provider names are not exhaustive. Generated build scripts should
            # not inherit arbitrary API keys, tokens, passwords, or credential
            # blobs merely because a new provider was added after this release.
            # Explicit comma-separated passthrough is available for private
            # dependency workflows without weakening the safe default.
            sensitive = re.compile(r"(?:^|_)(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?)(?:$|_)", re.I)
            for key in list(out):
                if str(key).upper() not in passthrough and sensitive.search(str(key)):
                    out.pop(key, None)
        cache = self.cache_root / "cache"; cache.mkdir(parents=True, exist_ok=True)
        out.setdefault("PIP_CACHE_DIR", str(cache / "pip"))
        out.setdefault("npm_config_cache", str(cache / "npm"))
        out.setdefault("YARN_CACHE_FOLDER", str(cache / "yarn"))
        out.setdefault("COREPACK_HOME", str(cache / "corepack"))
        out.setdefault("BUN_INSTALL_CACHE_DIR", str(cache / "bun"))
        out.setdefault("CARGO_TARGET_DIR", str(self.cache_root / "cargo-target"))
        out.setdefault("GRADLE_USER_HOME", str(self.cache_root / "gradle"))
        out.setdefault("NUGET_PACKAGES", str(cache / "nuget"))
        out.setdefault("GOMODCACHE", str(cache / "go-mod"))
        out.setdefault("GOCACHE", str(cache / "go-build"))
        # Validation builds do not need debug symbols or Cargo incremental object
        # duplication. These defaults materially reduce Tauri/Rust disk churn while
        # preserving compiler/test correctness. Projects can override explicitly.
        out.setdefault("CARGO_INCREMENTAL", "0")
        out.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
        out.setdefault("CARGO_PROFILE_TEST_DEBUG", "0")
        out.setdefault("CARGO_TERM_COLOR", "never")
        out.setdefault("NO_COLOR", "1")
        out["JARVIS_PROJECT_SANDBOX"] = "1"
        out["JARVIS_V42_RUNTIME"] = V42_RUNTIME_VERSION
        return out

    @staticmethod
    def _listify(command: Sequence[object] | str) -> List[str]:
        if isinstance(command, str):
            return shlex.split(command, posix=(os.name != "nt"))
        return [str(x) for x in command]

    def _policy(self, command: List[str], cwd: Path) -> Tuple[bool, str]:
        if not command: return False, "empty command"
        if not cwd.exists(): return False, "working directory does not exist"
        if not _flag("JARVIS_SANDBOX_ALLOW_EXTERNAL_CWD", False):
            try:
                cwd.resolve().relative_to(self.workspace)
            except Exception:
                return False, "working directory escapes the project sandbox root"
        # subprocess is direct/no-shell. Still reject shell-control tokens copied by a model.
        if any(x in {"&&","||",";","|",">",">>","<"} for x in command):
            return False, "shell control operators are not allowed through the command broker"
        base = Path(command[0]).name.lower()
        if not _flag("JARVIS_SANDBOX_ALLOW_DIRECT_SHELL", False):
            if base in {"cmd", "cmd.exe"} and any(str(x).lower() in {"/c", "/k"} for x in command[1:]):
                return False, "direct cmd shell execution is blocked by the project sandbox"
            if base in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"} and any(str(x).lower() in {"-command", "-c", "-encodedcommand", "-enc"} for x in command[1:]):
                return False, "direct PowerShell command execution is blocked by the project sandbox"
            if base in {"bash", "bash.exe", "sh", "sh.exe", "zsh", "zsh.exe"} and any(str(x) == "-c" for x in command[1:]):
                return False, "direct shell -c execution is blocked by the project sandbox"
        if base in self.BLOCKED_BASENAMES:
            return False, f"host-management command {base!r} is blocked"
        rendered = " ".join(command)
        for pat in self.BLOCKED_PATTERNS:
            if pat.search(rendered): return False, "destructive command pattern blocked"
        return True, ""

    def _resolve_command(self, cmd: List[str], run_cwd: Path) -> List[str]:
        """Resolve logical/project-local executables to concrete paths before CreateProcess.

        This is especially important on Windows where npm/npx are commonly .cmd
        shims and where a project-local tsc/vite should outrank an unrelated global
        executable. Resolution never changes arguments or escapes the workspace.
        """
        if not cmd:
            return cmd
        first = str(cmd[0])
        p = Path(first)
        if p.is_absolute() and p.exists():
            return list(cmd)
        logical = p.name.lower()
        local_map = {
            "tsc": ("node_modules/.bin/tsc.cmd", "node_modules/.bin/tsc"),
            "vite": ("node_modules/.bin/vite.cmd", "node_modules/.bin/vite"),
            "vitest": ("node_modules/.bin/vitest.cmd", "node_modules/.bin/vitest"),
            "eslint": ("node_modules/.bin/eslint.cmd", "node_modules/.bin/eslint"),
            "pnpm": ("node_modules/.bin/pnpm.cmd", "node_modules/.bin/pnpm"),
            "yarn": ("node_modules/.bin/yarn.cmd", "node_modules/.bin/yarn"),
            "bun": ("node_modules/.bin/bun.exe", "node_modules/.bin/bun"),
            "pytest": (".venv/Scripts/pytest.exe", ".venv/bin/pytest", "venv/Scripts/pytest.exe", "venv/bin/pytest"),
            "python": (".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python"),
            "cargo": (".cargo/bin/cargo.exe", ".cargo/bin/cargo"),
            "rustc": (".cargo/bin/rustc.exe", ".cargo/bin/rustc"),
            "dotnet": (".dotnet/dotnet.exe", ".dotnet/dotnet"),
            "composer": ("vendor/bin/composer.bat", "vendor/bin/composer"),
            "bundle": ("bin/bundle.bat", "bin/bundle"),
            "gradle": ("gradlew.bat", "gradlew"),
            "mvn": ("mvnw.cmd", "mvnw.bat", "mvnw"),
            "maven": ("mvnw.cmd", "mvnw.bat", "mvnw"),
        }
        for base in (run_cwd, self.workspace):
            for rel in local_map.get(logical, ()):
                hit = base / rel
                if hit.is_file():
                    out = list(cmd); out[0] = str(hit.resolve()); return out
        key = {"mvn":"maven"}.get(logical, logical)
        resolved = _resolve_tool(key)
        if resolved:
            out = list(cmd); out[0] = resolved; return out
        return list(cmd)

    @staticmethod
    def _batch_payload_safe(cmd: List[str]) -> Tuple[bool, str]:
        """Constrain the one internal shell exception needed for Windows .cmd/.bat shims.

        The model still cannot request cmd /c directly.  This guard also rejects
        cmd metacharacters embedded inside an argument before the trusted wrapper
        is introduced, preventing an npm.cmd-style launch from becoming a shell
        injection escape hatch.
        """
        if not cmd:
            return False, "empty batch command"
        for arg in cmd[1:]:
            if re.search(r"[\r\n&|<>^%()]", str(arg)):
                return False, "Windows batch shim argument contains blocked cmd metacharacters"
        return True, ""

    @staticmethod
    def _windows_batch_argv(cmd: List[str], comspec: Optional[str] = None) -> List[str]:
        """Build the constrained argv used to invoke a trusted Windows batch shim.

        Kept OS-independent so regression tests can validate Windows quoting from
        non-Windows CI. The caller is responsible for only using it for .cmd/.bat.
        """
        safe,reason=CommandBroker._batch_payload_safe(cmd)
        if not safe:
            raise ValueError(reason)
        if not cmd or re.search(r"[\r\n&|<>^%]", str(cmd[0])):
            raise ValueError("Windows batch shim executable path contains blocked cmd metacharacters")
        shell = comspec or os.environ.get("ComSpec") or os.environ.get("COMSPEC") or "cmd.exe"
        return [shell, "/d", "/s", "/c", "call", *cmd]

    @staticmethod
    def _windows_batch_wrap(cmd: List[str]) -> List[str]:
        if os.name != "nt" or not cmd:
            return cmd
        suffix = Path(str(cmd[0])).suffix.lower()
        if suffix not in {".cmd", ".bat"}:
            return cmd
        # IMPORTANT: do not pass a pre-quoted command string as one /c argument.
        # On Windows, cmd /s strips/retains those quotes differently for paths with
        # spaces and V42.19 produced: '"C:\Program Files\nodejs\npm.CMD" is not recognized'.
        # `call <batch-path> <args...>` keeps the batch path a normal argv token;
        # Python quotes only that token when constructing CreateProcess's command line.
        # Direct model-requested cmd /c remains blocked by _policy().
        return CommandBroker._windows_batch_argv(cmd)

    def _backend_wrap(self, cmd: List[str], run_cwd: Path) -> Tuple[List[str], Path, str]:
        """Return the actual process command for the selected backend.

        Docker requires JARVIS_DOCKER_IMAGE because a generic image cannot contain
        every compiler/SDK. WSL uses modern `wsl --cd` and is therefore opt-in.
        """
        if self.backend == "wsl":
            wsl = shutil.which("wsl") or shutil.which("wsl.exe")
            if not wsl:
                raise RuntimeError("WSL backend requested but wsl.exe is unavailable")
            return [wsl, "--cd", str(run_cwd), "--", *cmd], run_cwd, "wsl"
        if self.backend == "docker":
            docker = shutil.which("docker") or shutil.which("docker.exe")
            image = os.getenv("JARVIS_DOCKER_IMAGE", "").strip()
            if not docker:
                raise RuntimeError("Docker backend requested but docker is unavailable")
            if not image:
                raise RuntimeError("Docker backend requested but JARVIS_DOCKER_IMAGE is not set")
            logical = list(cmd)
            # Host absolute executable paths are meaningless inside a container.
            if logical and Path(logical[0]).is_absolute():
                logical[0] = Path(logical[0]).name
            mount = f"{str(self.workspace)}:/workspace"
            try:
                rel = run_cwd.relative_to(self.workspace).as_posix()
                container_cwd = "/workspace" if rel == "." else "/workspace/" + rel
            except Exception:
                container_cwd = "/workspace"
            return [docker, "run", "--rm", "-v", mount, "-w", container_cwd, image, *logical], self.workspace, "docker"
        return cmd, run_cwd, "native_controlled"

    def _log(self, result: CommandResult) -> None:
        try:
            row = asdict(result)
            row["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            row["stdout"] = row["stdout"][-4000:]
            row["stderr"] = row["stderr"][-4000:]
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f: f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _terminate_process_tree(self, proc: subprocess.Popen) -> None:
        try:
            if proc.poll() is not None:
                return
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            else:
                import signal
                try: os.killpg(proc.pid, signal.SIGKILL)
                except Exception: proc.kill()
        except Exception:
            try: proc.kill()
            except Exception: pass

    def _popen(self, actual_cmd: List[str], actual_cwd: Path, env: Optional[dict]) -> subprocess.Popen:
        kwargs = dict(
            cwd=str(actual_cwd), env=self._prepare_env(env), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False,
        )
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(actual_cmd, **kwargs)

    def run(self, command: Sequence[object] | str, cwd: Optional[Path] = None, timeout: int = 180, env: Optional[dict] = None) -> CommandResult:
        cmd = self._listify(command)
        run_cwd = Path(cwd or self.workspace).resolve()
        allowed, reason = self._policy(cmd, run_cwd)
        if not allowed:
            result = CommandResult(False, -1, cmd, str(run_cwd), 0, "", "", blocked=True, reason=reason, backend=self.backend)
            self._log(result); return result
        start = time.monotonic(); proc = None
        try:
            resolved_cmd = self._resolve_command(cmd, run_cwd)
            actual_cmd, actual_cwd, backend = self._backend_wrap(resolved_cmd, run_cwd)
            if backend == "native_controlled":
                actual_cmd = self._windows_batch_wrap(actual_cmd)
            proc = self._popen(actual_cmd, actual_cwd, env)
            stdout, stderr = proc.communicate(timeout=max(1, int(timeout)))
            result = CommandResult(proc.returncode == 0, int(proc.returncode or 0), cmd, str(run_cwd), int((time.monotonic()-start)*1000), stdout or "", stderr or "", backend=backend)
        except subprocess.TimeoutExpired as exc:
            if proc is not None:
                self._terminate_process_tree(proc)
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                except Exception:
                    stdout, stderr = str(exc.stdout or ""), str(exc.stderr or "")
            else:
                stdout, stderr = str(exc.stdout or ""), str(exc.stderr or "")
            result = CommandResult(False, -1, cmd, str(run_cwd), int((time.monotonic()-start)*1000), stdout or "", stderr or "", timed_out=True, reason=f"timeout after {timeout}s", backend=self.backend)
        except Exception as exc:
            if proc is not None: self._terminate_process_tree(proc)
            result = CommandResult(False, -1, cmd, str(run_cwd), int((time.monotonic()-start)*1000), "", "", reason=str(exc), backend=self.backend)
        self._log(result); return result

    def startup_smoke(self, command: Sequence[object] | str, cwd: Optional[Path] = None, timeout: int = 15, probe_url: str = "", env: Optional[dict] = None) -> CommandResult:
        """Launch a built app/server briefly, prove it survives startup (and optionally answers localhost HTTP), then kill its process tree."""
        cmd = self._listify(command); run_cwd = Path(cwd or self.workspace).resolve()
        allowed, reason = self._policy(cmd, run_cwd)
        if not allowed:
            result = CommandResult(False, -1, cmd, str(run_cwd), 0, "", "", blocked=True, reason=reason, backend=self.backend); self._log(result); return result
        start=time.monotonic(); proc=None; stdout=""; stderr=""
        try:
            resolved_cmd=self._resolve_command(cmd,run_cwd); actual_cmd,actual_cwd,backend=self._backend_wrap(resolved_cmd,run_cwd)
            if backend=="native_controlled": actual_cmd=self._windows_batch_wrap(actual_cmd)
            proc=self._popen(actual_cmd,actual_cwd,env)
            deadline=time.monotonic()+max(2,int(timeout)); answered=not bool(probe_url)
            while time.monotonic()<deadline:
                if proc.poll() is not None:
                    stdout,stderr=proc.communicate(timeout=1)
                    result=CommandResult(False,int(proc.returncode or 0),cmd,str(run_cwd),int((time.monotonic()-start)*1000),stdout or "",stderr or "",reason="process exited during startup smoke",backend=backend);self._log(result);return result
                if probe_url and not answered:
                    try:
                        import urllib.request
                        with urllib.request.urlopen(probe_url, timeout=1.0) as response:
                            answered=200 <= int(getattr(response,"status",200)) < 500
                    except Exception:
                        answered=False
                if answered and time.monotonic()-start>=1.0:
                    self._terminate_process_tree(proc)
                    try: stdout,stderr=proc.communicate(timeout=2)
                    except Exception: pass
                    result=CommandResult(True,0,cmd,str(run_cwd),int((time.monotonic()-start)*1000),stdout or "",stderr or "",reason="startup smoke passed",backend=backend);self._log(result);return result
                time.sleep(0.2)
            self._terminate_process_tree(proc)
            try: stdout,stderr=proc.communicate(timeout=2)
            except Exception: pass
            result=CommandResult(False,-1,cmd,str(run_cwd),int((time.monotonic()-start)*1000),stdout or "",stderr or "",timed_out=True,reason="startup smoke did not become healthy before timeout",backend=backend);self._log(result);return result
        except Exception as exc:
            if proc is not None:self._terminate_process_tree(proc)
            result=CommandResult(False,-1,cmd,str(run_cwd),int((time.monotonic()-start)*1000),stdout,stderr,reason=str(exc),backend=self.backend);self._log(result);return result


def refresh_process_path_from_windows_registry() -> bool:
    """Refresh PATH after winget/choco installs without requiring a Jarvis restart."""
    if os.name != "nt": return False
    try:
        import winreg
        parts=[]
        locations=[
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]
        for hive,key in locations:
            try:
                with winreg.OpenKey(hive,key) as h:
                    value,_=winreg.QueryValueEx(h,"Path")
                    if value: parts.append(str(value))
            except OSError:
                pass
        if parts:
            os.environ["PATH"]=os.pathsep.join(parts)
            return True
    except Exception:
        pass
    return False


_LIGHT_INSTALLERS = {
    "git": ("Git.Git", "git"), "cmake": ("Kitware.CMake", "cmake"), "ninja": ("Ninja-build.Ninja", "ninja"),
    "jq": ("jqlang.jq", "jq"), "rg": ("BurntSushi.ripgrep.MSVC", "ripgrep"), "7zip": ("7zip.7zip", "7zip"),
    "go": ("GoLang.Go", "go"), "zig": ("zig.zig", "zig"), "node": ("OpenJS.NodeJS.LTS", "nodejs-lts"),
}


def bootstrap_missing_tools(readiness: dict, workspace: Path) -> dict:
    """Optionally install lightweight trusted tools. Disabled unless explicitly enabled.

    Large SDKs/engines are never auto-installed by this function.
    """
    result = {"attempted": [], "installed": [], "skipped": [], "enabled": _flag("JARVIS_AUTO_INSTALL_TOOLS", False)}
    if not result["enabled"]: return result
    if os.name != "nt":
        result["skipped"] = list(readiness.get("missing") or []); return result
    winget = shutil.which("winget")
    choco = shutil.which("choco")
    broker = CommandBroker(Path(workspace))
    for tool in readiness.get("missing") or []:
        key = tool.lower()
        if key in _HEAVY_TOOLS or key not in _LIGHT_INSTALLERS:
            result["skipped"].append(tool); continue
        wid, cid = _LIGHT_INSTALLERS[key]
        if winget:
            cmd = [winget, "install", "--id", wid, "--exact", "--silent", "--accept-source-agreements", "--accept-package-agreements"]
        elif choco:
            cmd = [choco, "install", cid, "-y", "--no-progress"]
        else:
            result["skipped"].append(tool); continue
        result["attempted"].append(tool)
        r = broker.run(cmd, cwd=workspace, timeout=900)
        if r.ok: result["installed"].append(tool)
        else: result["skipped"].append(tool)
    if result["installed"]:
        refresh_process_path_from_windows_registry()
    return result


def write_environment_manifest(workspace: Path, manifest: dict, readiness: dict) -> dict:
    workspace = Path(workspace)
    runtime_dir = workspace / ".jarvis_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    backends = readiness.get("sandbox_backends") or {}
    platform_text = " ".join(str((manifest or {}).get(k) or "").lower() for k in ("platform","framework","toolchain_adapter"))
    windows_native = any(x in platform_text for x in ("windows","wpf","winforms","tauri","unity","unreal"))
    backend = "native_controlled"
    if _flag("JARVIS_SANDBOX_PREFER_DOCKER", False) and backends.get("docker") and not windows_native:
        backend = "docker_available"
    elif _flag("JARVIS_SANDBOX_PREFER_WSL", False) and backends.get("wsl") and not windows_native:
        backend = "wsl_available"
    data = {
        "version": V42_RUNTIME_VERSION, "engine": V42_RUNTIME_ENGINE,
        "workspace": str(workspace.resolve()), "backend": backend,
        "security_boundary": "controlled process/workspace isolation; native mode is not a VM security boundary",
        "project_local_state": str(runtime_dir),
        "network_dependency_commands_allowed": True,
        "automatic_tool_install": _flag("JARVIS_AUTO_INSTALL_TOOLS", False),
        "readiness_status": readiness.get("status"), "missing_tools": readiness.get("missing") or [],
    }
    _atomic_json(workspace / ENVIRONMENT_FILE, data)
    return data


def load_toolchains(jarvis_dir: Path) -> dict:
    p = Path(jarvis_dir) / "project_builder_skills" / "toolchains.json"
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}


_PROJECT_LOCAL_TOOL_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "gradle": ("gradlew", "gradlew.bat"),
    "maven": ("mvnw", "mvnw.cmd", "mvnw.bat"),
    "python": (".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python"),
    "pip": (".venv/Scripts/pip.exe", ".venv/bin/pip", "venv/Scripts/pip.exe", "venv/bin/pip"),
    "pytest": (".venv/Scripts/pytest.exe", ".venv/bin/pytest", "venv/Scripts/pytest.exe", "venv/bin/pytest"),
    "typescript": ("node_modules/.bin/tsc.cmd", "node_modules/.bin/tsc"),
    "tsc": ("node_modules/.bin/tsc.cmd", "node_modules/.bin/tsc"),
    "vite": ("node_modules/.bin/vite.cmd", "node_modules/.bin/vite"),
    "vitest": ("node_modules/.bin/vitest.cmd", "node_modules/.bin/vitest"),
    "eslint": ("node_modules/.bin/eslint.cmd", "node_modules/.bin/eslint"),
    "pnpm": ("node_modules/.bin/pnpm.cmd", "node_modules/.bin/pnpm"),
    "yarn": ("node_modules/.bin/yarn.cmd", "node_modules/.bin/yarn"),
    "bun": ("node_modules/.bin/bun.exe", "node_modules/.bin/bun"),
    "cargo": (".cargo/bin/cargo.exe", ".cargo/bin/cargo"),
    "rustc": (".cargo/bin/rustc.exe", ".cargo/bin/rustc"),
    "dotnet": (".dotnet/dotnet.exe", ".dotnet/dotnet"),
    "composer": ("vendor/bin/composer.bat", "vendor/bin/composer"),
    "bundle": ("bin/bundle.bat", "bin/bundle"),
}


def discover_project_tools(workspace: Path, manifest: Optional[dict] = None, capabilities: Optional[dict] = None) -> dict:
    """Discover wrappers and environment-local tools shipped with the project.

    These are often the most reproducible command paths: Gradle/Maven wrappers, a
    checked project virtualenv, and package-local Node CLIs.  A wrapper is only
    advertised as usable when its required host runtime (Java/Node) is present.
    """
    root = Path(workspace).resolve()
    roots: List[Path] = [root]
    for comp in (manifest or {}).get("components") or []:
        if not isinstance(comp, dict):
            continue
        rel = str(comp.get("root") or ".").replace("\\", "/").strip() or "."
        try:
            croot = (root / rel).resolve()
            croot.relative_to(root)
        except Exception:
            continue
        if croot not in roots:
            roots.append(croot)
    host_tools = ((capabilities or {}).get("tools") or {})
    found: Dict[str, dict] = {}
    for name, candidates in _PROJECT_LOCAL_TOOL_CANDIDATES.items():
        for base in roots:
            hit = next((base / rel for rel in candidates if (base / rel).is_file()), None)
            if not hit:
                continue
            usable = True
            reason = ""
            if name in {"gradle", "maven"} and not (host_tools.get("java") or {}).get("available"):
                usable = False; reason = "project wrapper found but Java runtime is unavailable"
            if name in {"typescript", "tsc", "vite", "vitest", "eslint", "pnpm", "yarn"} and not (host_tools.get("node") or {}).get("available"):
                usable = False; reason = "project-local Node CLI found but Node runtime is unavailable"
            found[name] = {
                "available": bool(usable), "path": str(hit),
                "root": str(base), "source": "project_local", "reason": reason,
            }
            break
    return found


def _apply_project_local_tools(readiness: dict, local_tools: dict) -> dict:
    rows = list(readiness.get("requirements") or [])
    for row in rows:
        if row.get("available"):
            continue
        req = str(row.get("requirement") or "").lower()
        aliases = _REQUIREMENT_ALIASES.get(req, [req])
        hits = [a for a in aliases if (local_tools.get(a) or {}).get("available")]
        if hits:
            row["available"] = True
            row["providers"] = [f"project:{local_tools[a]['path']}" for a in hits]
            row["project_local"] = True
    missing = [str(x.get("requirement") or "") for x in rows if not x.get("available")]
    readiness["requirements"] = rows
    readiness["missing"] = missing
    readiness["status"] = "READY" if not missing else "HOST_MISSING_TOOLS"
    readiness["project_local_tools"] = local_tools
    return readiness


def preflight_for_manifest(jarvis_dir: Path, workspace: Path, manifest: dict, try_bootstrap: bool = True) -> dict:
    caps = get_cached_capabilities(refresh=True, probe_versions=False)
    toolchains = load_toolchains(jarvis_dir)
    readiness = resolve_requirements(manifest, caps, toolchains=toolchains)
    readiness = _apply_project_local_tools(readiness, discover_project_tools(Path(workspace), manifest, caps))
    install = bootstrap_missing_tools(readiness, Path(workspace)) if try_bootstrap else {"enabled":False,"attempted":[],"installed":[],"skipped":[]}
    if install.get("installed"):
        caps = get_cached_capabilities(refresh=True, probe_versions=False)
        readiness = resolve_requirements(manifest, caps, toolchains=toolchains)
        readiness = _apply_project_local_tools(readiness, discover_project_tools(Path(workspace), manifest, caps))
    readiness["bootstrap"] = install
    _atomic_json(Path(workspace) / CAPABILITY_FILE, caps)
    _atomic_json(Path(workspace) / READINESS_FILE, readiness)
    write_environment_manifest(Path(workspace), manifest, readiness)
    return readiness


# Common feature signals used only to ask for a stricter plan review. They do not
# hard-code implementation language/framework and do not synthesize source code.
_FEATURE_SIGNALS = [
    ("csv_import_export", re.compile(r"(?i)\bcsv\b|\bimport\b.*\bexport\b|\bexport\b.*\bimport\b"), ("csv","import","export")),
    ("tests", re.compile(r"(?i)\b(?:real\s+)?tests?\b|\btest suite\b"), ("test","spec")),
    ("checkout", re.compile(r"(?i)\bcheck[- ]?out\b|\bcheck[- ]?in\b|\bcheckout history\b"), ("checkout","check_out","checkin","check-in","check-out")),
    ("search_filter", re.compile(r"(?i)\bsearch\b|\bfilter\b"), ("search","filter")),
    ("dashboard", re.compile(r"(?i)\bdashboard\b"), ("dashboard",)),
    ("categories", re.compile(r"(?i)\bcategor(?:y|ies)\b"), ("categor",)),
    ("authentication", re.compile(r"(?i)\bauth(?:entication)?\b|\blog[ -]?in\b|\bsign[ -]?in\b"), ("auth","login","sign in")),
    ("notifications", re.compile(r"(?i)\bnotifications?\b|\breminders?\b"), ("notif","remind")),
    ("settings", re.compile(r"(?i)\bsettings?\b|\bpreferences?\b"), ("setting","preference")),
    ("upload_download", re.compile(r"(?i)\bupload\b|\bdownload\b"), ("upload","download")),
    ("persistence", re.compile(r"(?i)\bpersist(?:ence|ent)?\b|\bdatabase\b|\bsqlite\b|\blocal\s+db\b"), ("database","storage","repository","persist","sqlite","db")),
    ("history", re.compile(r"(?i)\bhistory\b|\baudit\s+log\b"), ("history","audit","activity")),
    ("api", re.compile(r"(?i)\brest\s*api\b|\bapi\s+endpoint|\bendpoints?\b|\bgraphql\b|\bgrpc\b"), ("api","route","endpoint","controller","graphql","grpc")),
    ("background_jobs", re.compile(r"(?i)\bbackground\s+(?:job|task|worker)s?\b|\bqueue\b|\bscheduler\b"), ("worker","queue","job","scheduler")),
]


def plan_coverage_gaps(user_request: str, manifest: dict) -> List[str]:
    rows = [x for x in (manifest or {}).get("files") or [] if isinstance(x, dict)]
    implementation_blobs = []
    for x in rows:
        rel = str(x.get("path") or "").replace("\\","/").lower()
        purpose = str(x.get("purpose") or "").lower()
        # Coverage is based on implementation ownership (path + purpose), not on
        # dependency/contract strings. A root App importing Category or CheckoutEvent
        # does not mean category management or checkout workflows were implemented.
        blob = f"{rel} {purpose}"
        # Domain/contracts/config demonstrate data shape, not end-user behavior.
        is_contract_only = any(tag in f"/{rel}/" for tag in ("/domain/","/types/","/contracts/","/schema/")) or Path(rel).name.lower() in {"package.json","cargo.toml","tsconfig.json","tsconfig.node.json","vite.config.ts","tauri.conf.json"}
        implementation_blobs.append((blob, is_contract_only, rel))
    gaps: List[str] = []
    for name, trigger, needles in _FEATURE_SIGNALS:
        if not trigger.search(str(user_request or "")): continue
        if name == "tests":
            ok = any((
                "test" in Path(rel).name.lower() or "spec" in Path(rel).name.lower()
                or "/tests/" in f"/{rel}/" or "/test/" in f"/{rel}/"
                or "/spec/" in f"/{rel}/" or "/specs/" in f"/{rel}/"
                or " test " in (" " + blob + " ") or " unit test" in blob or "integration test" in blob
            ) for blob,_,rel in implementation_blobs)
        elif name == "csv_import_export":
            ok = any((not contract_only) and (("csv" in blob) or ("import" in blob and "export" in blob)) for blob,contract_only,_ in implementation_blobs)
        else:
            ok = any((not contract_only) and any(n in blob for n in needles) for blob,contract_only,_ in implementation_blobs)
        if not ok: gaps.append(name)
    return gaps


def plan_coverage_instruction(user_request: str, manifest: dict) -> str:
    gaps = plan_coverage_gaps(user_request, manifest)
    if not gaps: return ""
    return (
        "V42 PLAN COVERAGE RE-REVIEW REQUIRED. The current architecture does not contain implementation/test files "
        f"for these explicitly requested behavior clusters: {', '.join(gaps)}. Expand the plan before implementation. "
        "A domain type/schema mentioning a feature does NOT count as implementing the behavior. Every requested behavior needs an executable owner/consumer path and requested tests need actual test files."
    )
