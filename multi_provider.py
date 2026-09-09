# JARVIS MULTI PROVIDER V42.49.0 - cancellable progress-aware local-Qwen streaming
import os
import sys
import re
import json
import time
import shutil
import shlex
import fnmatch
import subprocess
import threading
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv

JARVIS_DIR = Path(__file__).resolve().parent
HERMES_ENV = Path(os.path.expandvars(r"%LOCALAPPDATA%\hermes\.env"))
LOCAL_ENV = JARVIS_DIR / "ai_providers.env"

if HERMES_ENV.exists():
    load_dotenv(HERMES_ENV, override=False)
if LOCAL_ENV.exists():
    load_dotenv(LOCAL_ENV, override=False)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()

OPENAI_MODEL = os.getenv("JARVIS_OPENAI_MODEL", "gpt-5.6-sol").strip()
ANTHROPIC_MODEL = os.getenv("JARVIS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
NVIDIA_MODEL = os.getenv("JARVIS_NVIDIA_MODEL", "deepseek-ai/deepseek-v4-flash-0731").strip()
NVIDIA_BASE_URL = os.getenv("JARVIS_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
QWEN_BASE_URL = os.getenv("JARVIS_QWEN_BASE_URL", f"http://127.0.0.1:{int(os.getenv('JARVIS_QWEN_PORT', '8081') or '8081')}").rstrip("/")
QWEN_CHAT_URL = f"{QWEN_BASE_URL}/v1/chat/completions"
QWEN_MODEL = os.getenv("JARVIS_QWEN_MODEL", "qwen-local").strip() or "qwen-local"
QWEN_TIMEOUT = int(os.getenv("JARVIS_QWEN_TIMEOUT", "900"))  # legacy non-stream fallback
QWEN_STREAM_IDLE_TIMEOUT = int(os.getenv("JARVIS_QWEN_STREAM_IDLE_TIMEOUT", "600"))
# V42.57: no absolute wall-clock cutoff for an actively streaming local model.
# A value >0 can still be supplied explicitly through the environment for users
# who want a ceiling. The idle/read timeout below remains authoritative for a
# dead connection, and Jarvis Stop can cooperatively close the active stream.
QWEN_STREAM_HARD_TIMEOUT = max(0, int(os.getenv("JARVIS_QWEN_STREAM_HARD_TIMEOUT", "0")))
QWEN_STREAM_PROGRESS_EXTENSION = max(
    15, int(os.getenv("JARVIS_QWEN_STREAM_PROGRESS_EXTENSION", "120"))
)
QWEN_STREAM_HARD_TIMEOUT_MULTIPLIER = max(
    1.0, min(6.0, float(os.getenv("JARVIS_QWEN_STREAM_HARD_TIMEOUT_MULTIPLIER", "3.0")))
)

_ACTIVE_QWEN_STREAM_LOCK = threading.RLock()
_ACTIVE_QWEN_STREAM = None


def cancel_active_qwen_stream():
    """Cooperatively interrupt the one active local-Qwen HTTP stream."""
    global _ACTIVE_QWEN_STREAM
    with _ACTIVE_QWEN_STREAM_LOCK:
        response = _ACTIVE_QWEN_STREAM
        _ACTIVE_QWEN_STREAM = None
    if response is None:
        return False
    try:
        response.close()
    except Exception:
        pass
    return True

# Exact upstream recommendations for mlabonne/Qwen3-8B-abliterated, including
# the mradermacher imatrix Q4_K_M GGUF used by Jarvis. The model author recommends
# temperature=0.6, top_k=20, top_p=0.95, min_p=0. No repeat/presence penalty is
# prescribed by that model card, so both default to neutral values and remain overridable.
QWEN_EXACT_TEMPERATURE = float(os.getenv("JARVIS_QWEN_TEMPERATURE", "0.6"))
QWEN_EXACT_TOP_P = float(os.getenv("JARVIS_QWEN_TOP_P", "0.95"))
QWEN_EXACT_TOP_K = int(os.getenv("JARVIS_QWEN_TOP_K", "20"))
QWEN_EXACT_MIN_P = float(os.getenv("JARVIS_QWEN_MIN_P", "0"))
QWEN_EXACT_REPEAT_PENALTY = float(os.getenv("JARVIS_QWEN_REPEAT_PENALTY", "1.0"))
QWEN_EXACT_PRESENCE_PENALTY = float(os.getenv("JARVIS_QWEN_PRESENCE_PENALTY", "0.0"))
QWEN_DEFAULT_THINKING = os.getenv("JARVIS_QWEN_ENABLE_THINKING", "0").strip().lower() in {"1", "true", "yes", "on"}
QWEN_RUNTIME_CONTEXT_FALLBACK = max(4096, int(os.getenv("JARVIS_QWEN_CONTEXT_TOKENS", "8192")))
_QWEN_RUNTIME_CONTEXT_CACHE = {"time": 0.0, "tokens": 0, "profile_key": ""}
DEFAULT_CODING_PROVIDER = os.getenv("JARVIS_CODING_PROVIDER", "auto").strip().lower()

NVIDIA_MODEL_CACHE_FILE = JARVIS_DIR / "nvidia_models_cache.json"
NVIDIA_MODEL_SELECTION_FILE = JARVIS_DIR / "nvidia_model_selection.json"
NVIDIA_MODEL_CACHE_SECONDS = int(os.getenv("JARVIS_NVIDIA_MODEL_CACHE_SECONDS", "21600"))

PROVIDER_TIMEOUT = int(os.getenv("JARVIS_PROVIDER_TIMEOUT", "180"))
MAX_AGENT_TURNS = int(os.getenv("JARVIS_CODING_MAX_TURNS", "50"))
MAX_FILE_CHARS = 120000


SENSITIVE_FILE_NAMES = {
    ".env", "ai_providers.env", "credentials.json", "secrets.json",
    "auth.json", "id_rsa", "id_ed25519",
}




def _read_json_file(path, default):
    try:
        value=json.loads(Path(path).read_text(encoding="utf-8"))
        return value
    except Exception:
        return default


def _write_json_file(path, value):
    try:
        p=Path(path)
        tmp=p.with_suffix(p.suffix+".tmp")
        tmp.write_text(json.dumps(value,indent=2),encoding="utf-8")
        os.replace(tmp,p)
        return True
    except Exception:
        return False


def get_nvidia_model_preference():
    data=_read_json_file(NVIDIA_MODEL_SELECTION_FILE,{})
    value=str(data.get("model","auto") or "auto").strip()
    return value or "auto"


def set_nvidia_model_preference(model):
    model=str(model or "auto").strip() or "auto"
    _write_json_file(NVIDIA_MODEL_SELECTION_FILE,{"model":model,"updated_at":datetime.now().isoformat(timespec="seconds")})
    return model


def get_nvidia_models(force=False):
    """Discover models currently exposed to this NVIDIA API key.

    NVIDIA's hosted catalog changes over time, so Jarvis treats /v1/models as
    the source of truth instead of hard-coding a giant stale list.
    """
    cached=_read_json_file(NVIDIA_MODEL_CACHE_FILE,{})
    if not force:
        try:
            age=time.time()-float(cached.get("fetched_epoch",0))
            models=cached.get("models") or []
            if models and age < NVIDIA_MODEL_CACHE_SECONDS:
                return models
        except Exception:
            pass

    if not NVIDIA_API_KEY:
        return cached.get("models") or []

    try:
        r=requests.get(
            f"{NVIDIA_BASE_URL}/models",
            headers={"Authorization":f"Bearer {NVIDIA_API_KEY}"},
            timeout=min(PROVIDER_TIMEOUT,30),
        )
        if r.status_code==200:
            data=r.json()
            models=[]
            for item in data.get("data",[]):
                mid=str(item.get("id","") or "").strip()
                if mid and mid not in models:
                    models.append(mid)
            models=sorted(models,key=str.lower)
            _write_json_file(NVIDIA_MODEL_CACHE_FILE,{
                "models":models,
                "fetched_epoch":time.time(),
                "fetched_at":datetime.now().isoformat(timespec="seconds"),
                "source":f"{NVIDIA_BASE_URL}/models",
            })
            return models
    except Exception:
        pass
    return cached.get("models") or []


def _find_available_model(available, preferred_fragments):
    """Return the first available NVIDIA model matching a preferred fragment."""
    available=list(available or [])
    for fragment in preferred_fragments:
        fragment=str(fragment).lower()
        for model in available:
            if fragment in str(model).lower():
                return model
    return ""


def _nvidia_task_class(prompt="", purpose="chat"):
    text=str(prompt or "").lower()
    if purpose=="coding":
        # Explicitly distinguish long-running terminal/agent work.
        if any(x in text for x in (
            "long-running","long running","long-horizon","long horizon",
            "terminal agent","many files","large refactor","repo-wide","repository-wide",
            "autonomous coding","work for a while",
        )):
            return "long_coding"
        return "coding"

    if any(x in text for x in (
        "image","screenshot","photo","picture","vision","camera frame",
        "analyze this screen","analyse this screen","multimodal",
    )):
        return "vision"

    if purpose=="reasoning" or any(x in text for x in (
        "very hard","deep reasoning","complex reasoning","architecture",
        "strategic plan","strategy","analyze deeply","analyse deeply",
        "multi-step plan","difficult problem",
    )):
        return "hard_reasoning"

    return "general"


def choose_nvidia_model(prompt="", purpose="chat"):
    """AUTO BEST: choose an available NVIDIA specialist for the current task.

    Priority:
      general/chat -> DeepSeek V4 Flash 0731
      normal coding -> DeepSeek V4 Flash 0731
      hard reasoning -> Nemotron 3 Ultra, then DeepSeek V4 Pro
      long-horizon coding -> Laguna XS 2.1
      vision -> best discovered vision/multimodal endpoint
    """
    preference=get_nvidia_model_preference()
    available=get_nvidia_models(force=False)

    if preference.lower()!="auto":
        if not available or preference in available:
            return preference
        # A selected model can disappear/EOL; recover through AUTO instead.

    task_class=_nvidia_task_class(prompt,purpose)

    priorities={
        "general":(
            "deepseek-v4-flash-0731",
            "deepseek-v4-flash",
            "nemotron-3.5-lightning",
            "nemotron-3-super",
        ),
        "coding":(
            "deepseek-v4-flash-0731",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "laguna-xs-2.1",
            "laguna",
            "minimax-m3",
        ),
        "hard_reasoning":(
            "nemotron-3-ultra",
            "deepseek-v4-pro",
            "minimax-m3",
            "deepseek-v4-flash-0731",
        ),
        "long_coding":(
            "laguna-xs-2.1",
            "laguna",
            "deepseek-v4-flash-0731",
            "deepseek-v4-pro",
            "minimax-m3",
        ),
        "vision":(
            "inkling",
            "vision",
            "vl",
            "multimodal",
            "nemotron-nano-vl",
        ),
    }

    selected=_find_available_model(available,priorities.get(task_class,priorities["general"]))
    if selected:
        return selected

    # Known working default remains the fallback when discovery is empty or no
    # specialist match is currently hosted for this API key.
    if NVIDIA_MODEL and (not available or NVIDIA_MODEL in available):
        return NVIDIA_MODEL

    # Prefer a plausible chat/agent model over embeddings/rerank/safety/etc.
    specialty=("embed","rerank","translate","asr","tts","safety","guard","video","flux","stable-diffusion")
    for model in available:
        low=model.lower()
        if not any(x in low for x in specialty):
            return model
    return available[0] if available else NVIDIA_MODEL


def nvidia_model_team_status(force=False):
    models=get_nvidia_models(force=force)
    return {
        "configured":bool(NVIDIA_API_KEY),
        "selection":get_nvidia_model_preference(),
        "auto_chat":choose_nvidia_model("general conversation","chat") if NVIDIA_API_KEY else "",
        "auto_coding":choose_nvidia_model("coding and debugging","coding") if NVIDIA_API_KEY else "",
        "auto_reasoning":choose_nvidia_model("very hard complex reasoning and architecture","reasoning") if NVIDIA_API_KEY else "",
        "auto_long_coding":choose_nvidia_model("long-horizon terminal agent coding task","coding") if NVIDIA_API_KEY else "",
        "auto_vision":choose_nvidia_model("analyze this screenshot with vision","chat") if NVIDIA_API_KEY else "",
        "models":models,
        "count":len(models),
    }


def qwen_status(timeout=1.5):
    """Return True when the local llama.cpp Qwen server is reachable."""
    try:
        r = requests.get(f"{QWEN_BASE_URL}/health", timeout=timeout)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    try:
        r = requests.get(f"{QWEN_BASE_URL}/v1/models", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def qwen_runtime_context_tokens(default=None, timeout=1.5, cache_seconds=60):
    """Discover the *live* llama.cpp context without leaking an old model's cache.

    V32 keys the cache to qwen_runtime_profile.json. Switching from the 8B
    40,960-token server to Qwen3.5 therefore invalidates the old value immediately.
    When /props is temporarily unavailable, the freshly written runtime profile is
    preferred over the legacy generic fallback.
    """
    runtime_profile = _read_json_file(JARVIS_DIR / "qwen_runtime_profile.json", {})
    profile_context = 0
    try:
        profile_context = int(runtime_profile.get("context") or 0)
    except Exception:
        profile_context = 0
    profile_key = "|".join((
        str(runtime_profile.get("generated_at") or ""),
        str(runtime_profile.get("model") or ""),
        str(runtime_profile.get("profile") or ""),
        str(profile_context),
        str(runtime_profile.get("pid") or ""),
        str(runtime_profile.get("status") or ""),
    ))

    if default is None:
        joined = " ".join((
            str(runtime_profile.get("model_family") or ""),
            str(runtime_profile.get("model") or ""),
            str(runtime_profile.get("profile") or ""),
        )).lower()
        is_qwen38 = ("qwen3.8" in joined or "qwen38" in joined or "27b38q2" in joined)
        is_qwen35 = ("qwen3.5" in joined or "qwen35" in joined)
        minimum_recorded = 8192 if is_qwen38 else (16384 if is_qwen35 else 4096)
        if profile_context >= minimum_recorded:
            fallback = profile_context
        else:
            fallback = 40960 if is_qwen38 or is_qwen35 else QWEN_RUNTIME_CONTEXT_FALLBACK
    else:
        fallback = max(4096, int(default))

    now = time.monotonic()
    cached = int(_QWEN_RUNTIME_CONTEXT_CACHE.get("tokens") or 0)
    cached_at = float(_QWEN_RUNTIME_CONTEXT_CACHE.get("time") or 0.0)
    cached_key = str(_QWEN_RUNTIME_CONTEXT_CACHE.get("profile_key") or "")
    if cached >= 4096 and cached_key == profile_key and now - cached_at < max(1, int(cache_seconds)):
        return cached

    def valid_context(value):
        try:
            iv = int(value)
        except Exception:
            return 0
        return iv if 4096 <= iv <= 2_000_000 else 0

    def context_from_props(payload):
        if not isinstance(payload, dict):
            return 0

        # llama.cpp documents default_generation_settings.n_ctx as the active
        # per-slot target context. Prefer it over recursive metadata. Qwen3.8 MTP
        # payloads can contain smaller draft/speculative context values; taking
        # the minimum of every n_ctx-looking field made Jarvis falsely display
        # 6,144 while the target server was actually at 262,144.
        default_settings = payload.get("default_generation_settings")
        if isinstance(default_settings, dict):
            ctx = valid_context(default_settings.get("n_ctx"))
            if ctx:
                return ctx

        for key in ("n_ctx_slot", "n_ctx", "ctx_size", "context_size"):
            ctx = valid_context(payload.get(key))
            if ctx:
                return ctx

        candidates = []
        def collect_candidates(value, path=()):
            if isinstance(value, dict):
                for key, item in value.items():
                    low = str(key).lower()
                    next_path = path + (low,)
                    if isinstance(item, (int, float)) and not isinstance(item, bool):
                        ctx = valid_context(item)
                        if ctx:
                            draft = any(any(tag in part for tag in ("draft", "spec", "mtp")) for part in next_path)
                            if low in {"n_ctx", "n_ctx_slot", "ctx_size", "context_size"}:
                                candidates.append((3 if draft else 0, ctx))
                            elif low in {"context_length", "n_ctx_train", "max_position_embeddings", "max_context_length"}:
                                candidates.append((4 if draft else 2, ctx))
                    collect_candidates(item, next_path)
            elif isinstance(value, list):
                for item in value:
                    collect_candidates(item, path)
        collect_candidates(payload)
        if not candidates:
            return 0
        best_priority = min(priority for priority, _ in candidates)
        return max(ctx for priority, ctx in candidates if priority == best_priority)

    try:
        r = requests.get(f"{QWEN_BASE_URL}/props", timeout=timeout)
        if r.status_code == 200:
            tokens = context_from_props(r.json())
            if tokens:
                _QWEN_RUNTIME_CONTEXT_CACHE.update({"time": now, "tokens": tokens, "profile_key": profile_key})
                return tokens
    except Exception:
        pass

    _QWEN_RUNTIME_CONTEXT_CACHE.update({"time": now, "tokens": fallback, "profile_key": profile_key})
    return fallback


def qwen_runtime_model_family():
    """Return a small stable family tag for the active local GGUF."""
    try:
        data = _read_json_file(JARVIS_DIR / "qwen_runtime_profile.json", {})
        joined = " ".join((
            str(data.get("model_family") or ""),
            str(data.get("model") or ""),
            str(data.get("profile") or ""),
        )).lower()
        if "qwen3.8" in joined or "qwen38" in joined or "27b38q2" in joined:
            return "qwen38"
        if "qwen3.5" in joined or "qwen35" in joined or "qwen3_5" in joined:
            return "qwen35"
    except Exception:
        pass
    return "qwen3"


def provider_status():
    return {
        "qwen": qwen_status(),
        "qwen_model": QWEN_MODEL,
        "qwen_base_url": QWEN_BASE_URL,
        "qwen_context_tokens": qwen_runtime_context_tokens(),
        "qwen_sampler": {
            "temperature": QWEN_EXACT_TEMPERATURE,
            "top_p": QWEN_EXACT_TOP_P,
            "top_k": QWEN_EXACT_TOP_K,
            "min_p": QWEN_EXACT_MIN_P,
            "repeat_penalty": QWEN_EXACT_REPEAT_PENALTY,
            "presence_penalty": QWEN_EXACT_PRESENCE_PENALTY,
        },
        "openai": bool(OPENAI_API_KEY),
        "claude": bool(ANTHROPIC_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "nvidia": bool(NVIDIA_API_KEY),
        "openai_model": OPENAI_MODEL,
        "claude_model": ANTHROPIC_MODEL,
        "nvidia_model": NVIDIA_MODEL,
        "nvidia_selection": get_nvidia_model_preference(),
        "nvidia_model_count": len(get_nvidia_models(force=False)),
        "coding_provider": DEFAULT_CODING_PROVIDER,
    }


def extract_provider_request(text):
    raw = str(text or "").strip()
    low = raw.lower()
    aliases = {
        "openai": ("openai", "open ai", "gpt"),
        "claude": ("claude", "anthropic"),
        "gemini": ("gemini", "google ai"),
        "nvidia": ("nvidia", "nim", "nvidia nim"),
        "qwen": ("qwen", "local qwen", "qwen local"),
    }

    # Explicit natural-language forms.
    patterns = [
        r"^(?:ask|use|have|tell|let)\s+(open\s*ai|openai|gpt|claude|anthropic|gemini|google\s+ai|nvidia|nvidia\s+nim|nim|qwen|local\s+qwen|qwen\s+local)\s+(?:to\s+)?(.+)$",
        r"^(open\s*ai|openai|gpt|claude|anthropic|gemini|google\s+ai|nvidia|nvidia\s+nim|nim|qwen|local\s+qwen|qwen\s+local)\s*[:,]\s*(.+)$",
        r"^(.+?)\s+(?:using|with)\s+(open\s*ai|openai|gpt|claude|anthropic|gemini|google\s+ai|nvidia|nvidia\s+nim|nim|qwen|local\s+qwen|qwen\s+local)$",
    ]
    for idx, pattern in enumerate(patterns):
        m = re.match(pattern, raw, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            continue
        if idx < 2:
            provider_text, task = m.group(1), m.group(2)
        else:
            task, provider_text = m.group(1), m.group(2)
        p = provider_text.lower().replace(" ", "")
        if p in {"openai", "gpt"}:
            return "openai", task.strip()
        if p in {"claude", "anthropic"}:
            return "claude", task.strip()
        if p in {"nvidia", "nvidianim", "nim"}:
            return "nvidia", task.strip()
        if p in {"qwen", "localqwen", "qwenlocal"}:
            return "qwen", task.strip()
        return "gemini", task.strip()

    # Provider mention anywhere in an agent/coding request.
    for provider, names in aliases.items():
        for name in names:
            if re.search(rf"\b{re.escape(name)}\b", low):
                cleaned = re.sub(
                    rf"\b(?:using|with|via)?\s*{re.escape(name)}\b",
                    "",
                    raw,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip(" ,.-")
                return provider, cleaned or raw
    return None, raw


def _extract_openai_text(data):
    if isinstance(data, dict):
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()
        chunks = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(str(content["text"]))
        return "\n".join(chunks).strip()
    return ""


def ask_openai(prompt, system=""):
    if not OPENAI_API_KEY:
        return False, "OpenAI is not configured yet. Add OPENAI_API_KEY to the Hermes .env or Jarvis ai_providers.env file."
    payload = {
        "model": OPENAI_MODEL,
        "input": prompt,
        "reasoning": {"effort": "medium"},
    }
    if system:
        payload["instructions"] = system
    try:
        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=PROVIDER_TIMEOUT,
        )
        if r.status_code != 200:
            return False, f"OpenAI API error {r.status_code}: {r.text[:350]}"
        text = _extract_openai_text(r.json())
        return (True, text) if text else (False, "OpenAI returned no readable text.")
    except requests.Timeout:
        return False, "OpenAI took too long to respond."
    except Exception as exc:
        return False, f"OpenAI connection error: {exc}"


def ask_claude(prompt, system=""):
    if not ANTHROPIC_API_KEY:
        return False, "Claude is not configured yet. Add ANTHROPIC_API_KEY to Jarvis ai_providers.env."
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=PROVIDER_TIMEOUT,
        )
        if r.status_code != 200:
            return False, f"Claude API error {r.status_code}: {r.text[:350]}"
        data = r.json()
        text = "\n".join(
            str(block.get("text", ""))
            for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip()
        return (True, text) if text else (False, "Claude returned no readable text.")
    except requests.Timeout:
        return False, "Claude took too long to respond."
    except Exception as exc:
        return False, f"Claude connection error: {exc}"



class QwenResponse(str):
    """Backward-compatible text with per-call transport evidence (no globals)."""
    def __new__(cls, text, metadata=None, partial_text=''):
        value = super().__new__(cls, text)
        value.metadata = dict(metadata or {})
        value.partial_text = partial_text
        return value


def ask_qwen(
    prompt,
    system="",
    progress_callback=None,
    hard_timeout=None,
    temperature=None,
    max_tokens=None,
    repetition_penalty=None,
    profile="chat",
    top_p=None,
    top_k=None,
    min_p=None,
    presence_penalty=None,
    enable_thinking=None,
    response_format=None,
    json_schema=None,
    extra_body=None,
    **provider_kwargs,
):
    """Ask the currently selected local Qwen GGUF through llama.cpp.

    The active runtime profile is inspected so Qwen3-8B keeps its proven sampler while
    Qwen3.5-9B receives the official mode-specific Qwen3.5 defaults. Callers can still
    override every sampling field explicitly; local_qwen_project.py does so for its
    strict generation/audit stages.
    """
    messages = [{"role": "user", "content": str(prompt or "")}]
    use_system = os.getenv("JARVIS_QWEN_USE_SYSTEM_PROMPT", "0").strip().lower() in {"1", "true", "yes", "on"}
    if system and use_system:
        messages.insert(0, {"role": "system", "content": str(system)})

    token_profiles = {
        "chat": 2048,
        "plan": 2048,
        "generate": 8192,
        "repair": 4096,
        "audit": 2048,
    }
    profile_name = str(profile or "chat").strip().lower()
    selected_max_tokens = token_profiles.get(profile_name, token_profiles["chat"])
    if max_tokens is not None:
        try:
            selected_max_tokens = max(64, int(max_tokens))
        except Exception:
            pass

    family = qwen_runtime_model_family()
    if enable_thinking is None:
        # Qwen3.5 is a hybrid-reasoning model and thinks by default. The older 8B
        # profile keeps Jarvis's existing non-thinking default for compatibility.
        selected_thinking = True if family in {"qwen35", "qwen38"} else QWEN_DEFAULT_THINKING
    else:
        selected_thinking = bool(enable_thinking)

    if family == "qwen35":
        if selected_thinking:
            precise = profile_name in {"plan", "generate", "repair", "audit"}
            default_temperature = 0.6 if precise else 1.0
            default_top_p = 0.95
            default_presence = 0.0 if precise else 1.5
        else:
            default_temperature = 0.7
            default_top_p = 0.8
            default_presence = 1.5
        default_top_k = 20
        default_min_p = 0.0
        default_repeat = 1.0
    elif family == "qwen38":
        # Official Qwen3.8 defaults from the model card.
        if selected_thinking:
            default_temperature = 1.0
            default_top_p = 0.95
            default_presence = 0.0
        else:
            default_temperature = 0.7
            default_top_p = 0.8
            default_presence = 1.5
        default_top_k = 20
        default_min_p = 0.0
        default_repeat = 1.0
    else:
        default_temperature = QWEN_EXACT_TEMPERATURE
        default_top_p = QWEN_EXACT_TOP_P
        default_top_k = QWEN_EXACT_TOP_K
        default_min_p = QWEN_EXACT_MIN_P
        default_repeat = QWEN_EXACT_REPEAT_PENALTY
        default_presence = QWEN_EXACT_PRESENCE_PENALTY

    selected_temperature = default_temperature if temperature is None else float(temperature)
    selected_top_p = default_top_p if top_p is None else float(top_p)
    selected_top_k = default_top_k if top_k is None else int(top_k)
    selected_min_p = default_min_p if min_p is None else float(min_p)
    selected_repeat = default_repeat if repetition_penalty is None else float(repetition_penalty)
    selected_presence = default_presence if presence_penalty is None else float(presence_penalty)

    # V42.60: the model's native context capability is not the live KV-cache
    # allocation. Keep 27B output requests inside the verified runtime slot so a
    # 40,960-token healthy server is never asked for a 65K completion. Connected
    # convergence already supports incremental owner subsets when a repair is large.
    if family == "qwen38":
        try:
            live_ctx = int(qwen_runtime_context_tokens(cache_seconds=1))
        except Exception:
            live_ctx = 40960
        if live_ctx < 16384:
            live_ctx = 40960
        safe_output = max(4096, min(20480, live_ctx // 2))
        selected_max_tokens = min(selected_max_tokens, safe_output)

    payload = {
        "model": QWEN_MODEL,
        "messages": messages,
        "temperature": selected_temperature,
        "top_p": selected_top_p,
        "top_k": selected_top_k,
        "min_p": selected_min_p,
        "max_tokens": selected_max_tokens,
        "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": selected_thinking},
        "stream": True,
    }

    # Penalties are model/mode-aware defaults and remain caller-overridable.
    payload["repeat_penalty"] = selected_repeat
    payload["presence_penalty"] = selected_presence

    # llama.cpp accepts OpenAI-compatible response_format. V24 also supplies json_schema
    # through extra_body as a compatibility path for builds/wrappers that expose it.
    if response_format is not None:
        payload["response_format"] = response_format
    if json_schema is not None:
        payload["json_schema"] = json_schema
    if isinstance(extra_body, dict):
        for key, value in extra_body.items():
            if key not in {"model", "messages", "stream"}:
                payload[key] = value

    # Allow future llama.cpp knobs without requiring another signature edit, while
    # preventing callers from replacing the essential routing/stream fields.
    for key, value in dict(provider_kwargs or {}).items():
        if value is not None and key not in {"model", "messages", "stream"}:
            payload[key] = value

    if hard_timeout is None:
        hard_timeout = QWEN_STREAM_HARD_TIMEOUT
    try:
        hard_timeout = int(hard_timeout or 0)
    except Exception:
        hard_timeout = 0

    started = time.monotonic()
    # A local model can be slow while still making real progress.  The previous
    # wall-clock-only watchdog killed valid 9B/27B edits after 90/150 seconds,
    # often after tokens had already begun arriving.  Start with the requested
    # deadline, extend it only when a real content/reasoning token arrives, and
    # retain an absolute bound so a stream still cannot monopolize Jarvis.
    progress_deadline = started + hard_timeout if hard_timeout > 0 else 0.0
    absolute_deadline = (
        started + max(float(hard_timeout), float(hard_timeout) * QWEN_STREAM_HARD_TIMEOUT_MULTIPLIER)
        if hard_timeout > 0 else 0.0
    )
    stream_idle_timeout = QWEN_STREAM_IDLE_TIMEOUT
    if hard_timeout > 0:
        stream_idle_timeout = min(QWEN_STREAM_IDLE_TIMEOUT, max(30, hard_timeout))
    content_chunks = []
    reasoning_chunks = []
    approx_tokens = 0
    received_chars = 0
    last_report = 0.0
    finish_reason = None
    done = False
    usage = {}

    def result(ok, message):
        return ok, QwenResponse(message, {
            'finish_reason': finish_reason, 'done': done, 'max_tokens': selected_max_tokens,
            'received_chars': received_chars, 'usage': usage,
            'elapsed_seconds': round(time.monotonic() - started, 2),
        }, '' if ok else ''.join(content_chunks))

    try:
        with requests.post(
            QWEN_CHAT_URL,
            json=payload,
            stream=True,
            timeout=(15, stream_idle_timeout),
        ) as r:
            global _ACTIVE_QWEN_STREAM
            with _ACTIVE_QWEN_STREAM_LOCK:
                _ACTIVE_QWEN_STREAM = r
            try:
                if r.status_code != 200:
                    return result(False, f"Local Qwen error {r.status_code}: {r.text[:500]}")
                for raw_line in r.iter_lines(decode_unicode=True):
                    now = time.monotonic()
                    elapsed = now - started
                    if not raw_line:
                        if progress_deadline and now > progress_deadline:
                            minutes = max(1, int((elapsed + 59) // 60))
                            return result(False, f"Local Qwen made no useful stream progress before the {minutes}-minute watchdog.")
                        continue
                    line = (raw_line.decode('utf-8') if isinstance(raw_line,bytes) else str(raw_line)).strip()
                    if not line.startswith("data:"):
                        if progress_deadline and now > progress_deadline:
                            minutes = max(1, int((elapsed + 59) // 60))
                            return result(False, f"Local Qwen made no useful stream progress before the {minutes}-minute watchdog.")
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        done = True
                        break
                    try:
                        data = json.loads(data_text)
                        if data.get('error'):
                            return result(False, 'Local Qwen stream error: ' + str(data['error'])[:1500])
                        if isinstance(data.get('usage'), dict): usage = data['usage']
                        choice = (data.get("choices") or [{}])[0]
                        if choice.get('finish_reason') is not None:
                            finish_reason = choice['finish_reason']
                        delta = choice.get("delta") or {}
                        content_piece = delta.get("content") or ""
                        reasoning_piece = delta.get("reasoning_content") or delta.get("reasoning") or ""
                    except Exception as exc:
                        return result(False, 'Local Qwen returned an invalid streaming frame: ' + str(exc)[:300])
                    if reasoning_piece:
                        reasoning_piece = str(reasoning_piece)
                        reasoning_chunks.append(reasoning_piece)
                        received_chars += len(reasoning_piece)
                    if content_piece:
                        content_piece = str(content_piece)
                        content_chunks.append(content_piece)
                        received_chars += len(content_piece)
                    if content_piece or reasoning_piece:
                        now = time.monotonic()
                        if progress_deadline:
                            progress_deadline = min(
                                absolute_deadline,
                                max(progress_deadline, now + QWEN_STREAM_PROGRESS_EXTENSION),
                            )
                        approx_tokens = max(approx_tokens, received_chars // 4)
                        if progress_callback and (now - last_report >= 2.0):
                            try:
                                progress_callback({
                                    "streaming": True,
                                    "generated_tokens_estimate": approx_tokens,
                                    "elapsed_seconds": int(elapsed),
                                    "thinking": selected_thinking,
                                    "message": f"Qwen is generating… ~{approx_tokens:,} tokens received ({int(elapsed)//60}m {int(elapsed)%60:02d}s).",
                                })
                            except Exception:
                                pass
                            last_report = now
                    elif progress_deadline and now > progress_deadline:
                        minutes = max(1, int((elapsed + 59) // 60))
                        return result(False, f"Local Qwen made no useful stream progress before the {minutes}-minute watchdog.")
                    if absolute_deadline and now > absolute_deadline:
                        minutes = max(1, int(((now - started) + 59) // 60))
                        return result(False, f"Local Qwen exceeded the bounded {minutes}-minute maximum stream window.")
            finally:
                with _ACTIVE_QWEN_STREAM_LOCK:
                    if _ACTIVE_QWEN_STREAM is r:
                        _ACTIVE_QWEN_STREAM = None
    except requests.exceptions.ReadTimeout:
        return result(False, f"Local Qwen stopped streaming for {stream_idle_timeout} seconds.")
    except requests.Timeout:
        return result(False, "Local Qwen connection timed out before streaming began.")
    except Exception as exc:
        return result(False, f"Local Qwen connection error: {exc}")

    content_text = "".join(content_chunks).strip()
    reasoning_text = "".join(reasoning_chunks).strip()

    # In thinking mode llama.cpp may expose chain-of-thought separately and still emit a
    # normal final answer. Prefer the final answer. If a build exposes only reasoning,
    # return it so Jarvis's reasoning-brief call still receives useful analysis.
    text = content_text or (reasoning_text if selected_thinking else "")
    if finish_reason == 'length':
        return result(False, f"Local Qwen reached the {selected_max_tokens}-token output limit; the incomplete response was not applied. Return a smaller complete transaction.")
    if finish_reason not in {None, 'stop'}:
        return result(False, f"Local Qwen ended without a final text answer (finish_reason={finish_reason}).")
    if not done and finish_reason is None:
        return result(False, "Local Qwen stream ended before a completion marker; the incomplete response was not applied.")
    return result(True, text) if text else result(False, "Local Qwen returned no readable text.")


def ask_nvidia(prompt, system=""):
    if not NVIDIA_API_KEY:
        return False, "NVIDIA NIM is not configured yet. Add NVIDIA_API_KEY first."
    messages=[]
    if system:
        messages.append({"role":"system","content":system})
    messages.append({"role":"user","content":prompt})
    try:
        r=requests.post(
            f"{NVIDIA_BASE_URL}/chat/completions",
            headers={"Authorization":f"Bearer {NVIDIA_API_KEY}","Content-Type":"application/json"},
            json={"model":choose_nvidia_model(prompt,"reasoning" if any(x in str(prompt).lower() for x in ("reason","analy","plan","architecture")) else "chat"),"messages":messages,"temperature":0.2,"max_tokens":4096},
            timeout=PROVIDER_TIMEOUT,
        )
    except Exception as exc:
        return False,f"NVIDIA NIM connection error: {exc}"
    if r.status_code!=200:
        return False,f"NVIDIA NIM error {r.status_code}: {r.text[:500]}"
    try:
        data=r.json()
        text=data["choices"][0]["message"]["content"]
        return True,str(text or "").strip()
    except Exception as exc:
        return False,f"NVIDIA NIM returned an unreadable response: {exc}"


def ask_nvidia_json(prompt, system=""):
    """Ask NVIDIA NIM and return parsed JSON, or (False, error)."""
    ok, text = ask_nvidia(prompt, system)
    if not ok:
        return False, text
    try:
        return True, json.loads(text)
    except Exception as exc:
        return False, f"NVIDIA NIM returned invalid JSON: {exc}"

def ask_provider(provider, prompt, system=""):
    provider = (provider or "").lower()
    if provider == "qwen":
        return ask_qwen(prompt, system)
    if provider == "openai":
        return ask_openai(prompt, system)
    if provider == "claude":
        return ask_claude(prompt, system)
    if provider == "nvidia":
        return ask_nvidia(prompt, system)
    return False, "Gemini is handled by Jarvis's persistent Hermes session."


class ProjectTools:
    def __init__(self, project_root, read_only=False, allow_git_write=False):
        raw_root = os.path.expandvars(os.path.expanduser(str(project_root or ""))).strip()
        requested = Path(raw_root).resolve() if raw_root else None
        module_root = Path(__file__).resolve().parent

        # v2.75: an explicitly requested workspace is authoritative even when it is
        # empty.  New-project agents must be able to create their first file there;
        # silently falling back to the Jarvis source directory can edit the wrong
        # project and makes empty-bootstrap recovery impossible.
        if requested is not None:
            if not requested.exists() or not requested.is_dir():
                raise RuntimeError(f"Requested project workspace does not exist or is not a directory: {requested}")
            selected = requested
        elif module_root.exists() and module_root.is_dir():
            selected = module_root
        else:
            selected = None

        if selected is None:
            raise RuntimeError(
                f"No usable project workspace was found. Requested: {requested}; Jarvis module root: {module_root}"
            )

        self.root = selected.resolve()
        self.requested_root = requested
        self.read_only = bool(read_only)
        self.allow_git_write = bool(allow_git_write)
        self.changed = set()
        self.backup_root = self.root / ".jarvis_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")

    def workspace_info(self):
        files = self.list_files(".").get("files", [])
        info = {
            "root": str(self.root),
            "requested_root": str(self.requested_root) if self.requested_root else "",
            "file_count_sampled": len(files),
            "git_repository": (self.root / ".git").exists(),
        }
        if info["git_repository"]:
            status = self.git_status()
            info["git_status"] = status.get("stdout", "") if isinstance(status, dict) else ""
            branch = self.git_branch()
            info["git_branch"] = branch.get("stdout", "").strip() if isinstance(branch, dict) else ""
        return info

    def _is_sensitive(self, path):
        name = Path(path).name.lower()
        if name in {x.lower() for x in SENSITIVE_FILE_NAMES}:
            return True
        low = str(path).lower().replace("\\", "/")
        return "/.ssh/" in low or "/.aws/" in low or "/.config/gcloud/" in low

    def _path(self, rel):
        rel = str(rel or "").strip().replace("/", os.sep)
        target = (self.root / rel).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("Path escapes the project root.")
        return target

    def list_files(self, path=".", pattern=""):
        base = self._path(path)
        if not base.exists():
            return {"error": "Path does not exist."}
        items = []
        iterable = base.rglob("*") if base.is_dir() else [base]
        ignored = {".git", ".venv", "node_modules", "build", ".jarvis_build", ".dart_tool", "__pycache__", ".jarvis_backups"}
        for p in iterable:
            if any(part in ignored for part in p.parts):
                continue
            if not p.is_file():
                continue
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            if pattern:
                pattern_lower = pattern.lower().replace("\\", "/")
                rel_lower = rel.lower()
                if any(char in pattern_lower for char in "*?["):
                    if not fnmatch.fnmatchcase(rel_lower, pattern_lower):
                        continue
                elif pattern_lower not in rel_lower:
                    continue
            items.append(rel)
            if len(items) >= 300:
                break
        return {"files": items}

    def read_file(self, path, start_line=1, end_line=0):
        p = self._path(path)
        if not p.is_file():
            return {"error": "File does not exist."}
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        start = max(1, int(start_line or 1))
        end = int(end_line or 0)
        if end <= 0:
            end = min(len(lines), start + 500)
        selected = "\n".join(f"{i+1}: {lines[i]}" for i in range(start-1, min(end, len(lines))))
        return {"path": str(p.relative_to(self.root)), "content": selected[:MAX_FILE_CHARS], "total_lines": len(lines)}

    def search_text(self, query, path="."):
        query = str(query or "")
        if not query:
            return {"error": "Empty query."}
        results = []
        files = self.list_files(path).get("files", [])
        for rel in files:
            try:
                lines = self._path(rel).read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if query.lower() in line.lower():
                    results.append({"path": rel, "line": i, "text": line[:500]})
                    if len(results) >= 100:
                        return {"matches": results}
        return {"matches": results}

    def _backup(self, p):
        if not p.exists() or not p.is_file():
            return
        rel = p.relative_to(self.root)
        dst = self.backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)

    def replace_text(self, path, old, new, count=1):
        if self.read_only:
            return {"error": "Read-only mode: edits are disabled."}
        if self._is_sensitive(path):
            return {"error": "Sensitive credential/config files are protected from autonomous edits."}
        p = self._path(path)
        if not p.is_file():
            return {"error": "File does not exist."}
        text = p.read_text(encoding="utf-8", errors="replace")
        occurrences = text.count(old)
        if occurrences == 0:
            return {"error": "Target text was not found."}
        self._backup(p)
        n = int(count or 1)
        updated = text.replace(old, new, n if n > 0 else occurrences)
        p.write_text(updated, encoding="utf-8")
        self.changed.add(str(p.relative_to(self.root)).replace("\\", "/"))
        return {"ok": True, "replacements": min(occurrences, n if n > 0 else occurrences)}

    def write_file(self, path, content):
        if self.read_only:
            return {"error": "Read-only mode: edits are disabled."}
        if self._is_sensitive(path):
            return {"error": "Sensitive credential/config files are protected from autonomous edits."}
        p = self._path(path)
        if p.exists():
            self._backup(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding="utf-8")
        self.changed.add(str(p.relative_to(self.root)).replace("\\", "/"))
        return {"ok": True, "path": str(p.relative_to(self.root))}

    def delete_file(self, path):
        if self.read_only:
            return {"error": "Read-only mode: edits are disabled."}
        if self._is_sensitive(path):
            return {"error": "Sensitive credential/config files are protected from autonomous edits."}
        p = self._path(path)
        if not p.exists() or not p.is_file():
            return {"error": "File does not exist."}
        self._backup(p)
        rel = str(p.relative_to(self.root)).replace("\\", "/")
        p.unlink()
        self.changed.add(rel)
        return {"ok": True, "deleted": rel}

    def move_file(self, source, destination):
        if self.read_only:
            return {"error": "Read-only mode: edits are disabled."}
        if self._is_sensitive(source) or self._is_sensitive(destination):
            return {"error": "Sensitive credential/config files are protected from autonomous edits."}
        src = self._path(source)
        dst = self._path(destination)
        if not src.exists() or not src.is_file():
            return {"error": "Source file does not exist."}
        if src == dst:
            return {"error": "Source and destination are the same file."}
        self._backup(src)
        if dst.exists():
            if not dst.is_file():
                return {"error": "Destination exists and is not a file."}
            self._backup(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        src_rel = str(src.relative_to(self.root)).replace("\\", "/")
        dst_rel = str(dst.relative_to(self.root)).replace("\\", "/")
        self.changed.add(src_rel)
        self.changed.add(dst_rel)
        return {"ok": True, "source": src_rel, "destination": dst_rel}

    def _run_validation_args(self, args, command_label=None, timeout=180, kind="validation"):
        """Execute a pre-tokenized validation command without a shell.

        Validation never uses shell=True, never performs package installation/downloads,
        and records whether the step was syntax/build/test evidence.  Keeping this helper
        centralized lets the project generator enforce real build evidence instead of
        trusting model prose.
        """
        args = [str(x) for x in (args or []) if str(x) != ""]
        if not args:
            return {"kind": kind, "error": "Empty command."}
        try:
            result = subprocess.run(
                args,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(timeout or 180)),
                shell=False,
            )
            return {
                "kind": kind,
                "command": str(command_label or " ".join(args)),
                "returncode": result.returncode,
                "stdout": result.stdout[-12000:],
                "stderr": result.stderr[-12000:],
            }
        except subprocess.TimeoutExpired:
            return {"kind": kind, "command": str(command_label or " ".join(args)), "error": "Validation timed out."}
        except Exception as exc:
            return {"kind": kind, "command": str(command_label or " ".join(args)), "error": str(exc)}

    def _path_validation_command(self, path):
        """Translate a common model mistake (run_validation(path=...)) into a safe check."""
        rel = str(path or "").strip().replace("\\", "/")
        if not rel:
            return None
        p = self._path(rel)
        if not p.is_file():
            return {"kind": "syntax", "path": rel, "error": "Validation path does not exist."}
        suffix = p.suffix.lower()
        if suffix in {".py", ".pyw"}:
            return self._run_validation_args([sys.executable, "-m", "py_compile", str(p)], f"python -m py_compile {rel}", kind="syntax")
        if suffix in {".js", ".mjs", ".cjs"}:
            node = shutil.which("node")
            if not node:
                return {"kind": "syntax", "path": rel, "error": "node was not found for JavaScript syntax validation."}
            return self._run_validation_args([node, "--check", str(p)], f"node --check {rel}", kind="syntax")
        if suffix in {".c", ".cc", ".cpp", ".cxx"}:
            is_cpp = suffix != ".c"
            compiler = (
                shutil.which("g++" if is_cpp else "gcc")
                or shutil.which("clang++" if is_cpp else "clang")
                or shutil.which("cl")
            )
            if not compiler:
                return {"kind": "syntax", "path": rel, "error": "No C/C++ compiler was found for syntax validation."}
            exe = Path(compiler).name.lower()
            if exe in {"cl", "cl.exe"}:
                args = [compiler, "/nologo", "/EHsc", "/Zs", str(p)] if is_cpp else [compiler, "/nologo", "/Zs", str(p)]
            else:
                args = [compiler, "-std=c++17", "-fsyntax-only", str(p)] if is_cpp else [compiler, "-std=c11", "-fsyntax-only", str(p)]
            return self._run_validation_args(args, f"{Path(compiler).name} syntax-check {rel}", kind="syntax")
        if suffix == ".json":
            try:
                json.loads(p.read_text(encoding="utf-8"))
                return {"kind": "syntax", "command": f"parse JSON {rel}", "returncode": 0, "stdout": "", "stderr": ""}
            except Exception as exc:
                return {"kind": "syntax", "command": f"parse JSON {rel}", "error": str(exc)}
        return {"kind": "syntax", "path": rel, "error": f"No deterministic file validator is configured for {suffix or 'this file type'}."}

    def run_validation(self, command="", path=""):
        """Run one explicitly requested safe validation command.

        v2.76 also accepts ``path`` because small local models frequently emit
        ``run_validation({"path": "src/main.cpp"})`` despite the tool schema.
        Jarvis converts that mistake into a real syntax check instead of throwing a
        Python signature error and letting the model continue as if validation passed.
        """
        command = str(command or "").strip()
        if not command and path:
            return self._path_validation_command(path)
        if not command:
            return {"error": "Empty command."}
        forbidden = re.compile(r"[|;&><`]|\b(push|commit|deploy|publish|install|add|update|rm|del|rmdir|remove-item|curl|wget|invoke-webrequest)\b", re.I)
        if forbidden.search(command):
            return {"error": "That command is not allowed in validation mode."}
        try:
            args = shlex.split(command, posix=False)
        except Exception as exc:
            return {"error": str(exc)}
        if not args:
            return {"error": "Empty command."}
        args = [a.strip('"') if i == 0 else a.strip('"') for i, a in enumerate(args)]
        exe = Path(args[0]).name.lower()
        allowed = {
            "python", "python.exe", "pytest", "pytest.exe",
            "node", "node.exe", "npm", "npm.cmd", "npx", "npx.cmd",
            "flutter", "flutter.bat", "dart", "dart.exe",
            "dotnet", "dotnet.exe", "msbuild", "msbuild.exe",
            "cmake", "cmake.exe", "ctest", "ctest.exe", "ninja", "ninja.exe",
            "make", "make.exe", "mingw32-make", "mingw32-make.exe",
            "gradle", "gradle.bat", "gradlew", "gradlew.bat",
            "mvn", "mvn.cmd", "mvnw", "mvnw.cmd", "javac", "javac.exe",
            "go", "go.exe", "cargo", "cargo.exe", "rustc", "rustc.exe",
            "gcc", "gcc.exe", "g++", "g++.exe", "clang", "clang.exe", "clang++", "clang++.exe", "cl", "cl.exe",
            "unrealbuildtool", "unrealbuildtool.exe",
            "git", "git.exe",
        }
        if exe not in allowed:
            return {"error": f"Validation executable not allowed: {exe}"}
        if exe.startswith("git") and (len(args) < 2 or args[1].lower() not in {"status", "diff"}):
            return {"error": "Only git status and git diff are allowed."}
        kind = "build" if exe in {
            "cmake", "cmake.exe", "ninja", "ninja.exe", "make", "make.exe", "mingw32-make", "mingw32-make.exe",
            "dotnet", "dotnet.exe", "msbuild", "msbuild.exe", "gradle", "gradle.bat", "gradlew", "gradlew.bat",
            "mvn", "mvn.cmd", "mvnw", "mvnw.cmd", "go", "go.exe", "cargo", "cargo.exe",
            "gcc", "gcc.exe", "g++", "g++.exe", "clang", "clang.exe", "clang++", "clang++.exe", "cl", "cl.exe",
            "unrealbuildtool", "unrealbuildtool.exe",
        } else "validation"
        return self._run_validation_args(args, command, timeout=180, kind=kind)
    def _run_git(self, args, timeout=120):
        if not (self.root / ".git").exists():
            return {"error": f"Not a Git repository: {self.root}"}
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=str(self.root),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout,
                shell=False,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[-16000:],
                "stderr": result.stderr[-16000:],
            }
        except Exception as exc:
            return {"error": str(exc)}

    def git_status(self):
        return self._run_git(["status", "--short", "--branch"])

    def git_diff(self):
        return self._run_git(["diff", "--", "."])

    def git_log(self, count=10):
        count = max(1, min(50, int(count or 10)))
        return self._run_git(["log", f"-{count}", "--oneline", "--decorate"])

    def git_branch(self):
        return self._run_git(["branch", "--show-current"])

    def git_remote(self):
        return self._run_git(["remote", "-v"])

    def git_pull(self, remote="origin", branch=""):
        if self.read_only or not self.allow_git_write:
            return {"error": "Git write actions were not explicitly authorized by the current user request."}
        args = ["pull", "--ff-only", str(remote or "origin")]
        if branch:
            args.append(str(branch))
        return self._run_git(args, timeout=180)

    def git_commit(self, message):
        if self.read_only or not self.allow_git_write:
            return {"error": "Git commit was not explicitly authorized by the current user request."}
        message = str(message or "").strip()
        if not message:
            return {"error": "Commit message is required."}
        paths = [p for p in sorted(self.changed) if not self._is_sensitive(p)]
        if not paths:
            return {"error": "This coding session has no changed files to commit."}
        add = self._run_git(["add", "--"] + paths)
        if add.get("returncode") != 0:
            return {"error": "git add failed", "details": add}
        return self._run_git(["commit", "-m", message], timeout=180)

    def git_push(self, remote="origin", branch=""):
        if self.read_only or not self.allow_git_write:
            return {"error": "Git push was not explicitly authorized by the current user request."}
        if not branch:
            current = self.git_branch()
            if current.get("returncode") == 0:
                branch = current.get("stdout", "").strip()
        args = ["push", str(remote or "origin")]
        if branch:
            args.append(str(branch))
        return self._run_git(args, timeout=240)

    def auto_validate(self, manifest=None, project_wide=False):
        """Run deterministic local validation, including real builds when applicable.

        ``project_wide=False`` preserves the lightweight coding-agent behavior for
        ordinary edits.  The project ZIP acceptance gate calls with project_wide=True
        so a compiled/typed project cannot be marked verified from file existence alone.
        """
        manifest = manifest or {}
        results = []
        listing = self.list_files(".")
        all_files = sorted(list(listing.get("files") or [])) if isinstance(listing, dict) else []
        files = all_files if project_wide else sorted(self.changed)

        # Python syntax: compile every relevant source in one deterministic command.
        py_files = [f for f in files if f.lower().endswith((".py", ".pyw")) and self._path(f).is_file()]
        if py_files:
            args = [sys.executable, "-m", "py_compile"] + [str(self._path(f)) for f in py_files]
            results.append(self._run_validation_args(args, "python -m py_compile " + " ".join(py_files), timeout=120, kind="syntax"))

        # JSON parsing does not need an external runtime.
        for rel in [f for f in files if f.lower().endswith(".json") and self._path(f).is_file()]:
            try:
                json.loads(self._path(rel).read_text(encoding="utf-8"))
                results.append({"kind": "syntax", "command": f"parse JSON {rel}", "returncode": 0, "stdout": "", "stderr": ""})
            except Exception as exc:
                results.append({"kind": "syntax", "command": f"parse JSON {rel}", "error": str(exc)})

        # JavaScript syntax can be checked without executing application code.
        js_files = [f for f in files if f.lower().endswith((".js", ".mjs", ".cjs")) and self._path(f).is_file()]
        if js_files:
            node = shutil.which("node")
            if node:
                for rel in js_files[:80]:
                    results.append(self._run_validation_args([node, "--check", str(self._path(rel))], f"node --check {rel}", timeout=60, kind="syntax"))
            elif project_wide:
                results.append({"kind": "syntax", "error": "node was not found; JavaScript syntax could not be validated."})

        if not project_wide:
            return results

        lower = {f.lower(): f for f in all_files}
        suffixes = {Path(f).suffix.lower() for f in all_files}
        build_dir = self.root / ".jarvis_build"

        # CMake is the preferred deterministic C/C++ build path. Configure and build
        # are separate subprocesses so no shell chaining is needed.
        if "cmakelists.txt" in lower:
            cmake = shutil.which("cmake")
            if not cmake:
                results.append({"kind": "build", "error": "CMakeLists.txt exists but cmake was not found."})
            else:
                build_dir.mkdir(parents=True, exist_ok=True)
                cfg = self._run_validation_args([cmake, "-S", str(self.root), "-B", str(build_dir)], "cmake -S . -B .jarvis_build", timeout=240, kind="build")
                results.append(cfg)
                if cfg.get("returncode") == 0:
                    results.append(self._run_validation_args([cmake, "--build", str(build_dir), "--config", "Release"], "cmake --build .jarvis_build --config Release", timeout=300, kind="build"))

        cpp_files = [f for f in all_files if f.lower().endswith((".cc", ".cpp", ".cxx"))]
        c_files = [f for f in all_files if f.lower().endswith(".c")]
        if (cpp_files or c_files) and "cmakelists.txt" not in lower:
            # A compact single-language project can still be truly compiled without
            # forcing Qwen to invent a fake .exe. Multi-file/platform-specific projects
            # should create CMakeLists.txt so libraries/flags are explicit.
            is_cpp = bool(cpp_files)
            sources = cpp_files if is_cpp else c_files
            compiler = (
                shutil.which("g++" if is_cpp else "gcc")
                or shutil.which("clang++" if is_cpp else "clang")
                or shutil.which("cl")
            )
            if not compiler:
                results.append({"kind": "build", "error": "C/C++ source exists but no compiler or CMake build path was found."})
            else:
                build_dir.mkdir(parents=True, exist_ok=True)
                exe_name = "jarvis_project.exe" if os.name == "nt" else "jarvis_project"
                output = build_dir / exe_name
                compiler_name = Path(compiler).name.lower()
                src_paths = [str(self._path(f)) for f in sources]
                if compiler_name in {"cl", "cl.exe"}:
                    args = [compiler, "/nologo", "/EHsc"] + src_paths + [f"/Fe:{output}"]
                else:
                    std = "-std=c++17" if is_cpp else "-std=c11"
                    args = [compiler, std] + src_paths + ["-o", str(output)]
                results.append(self._run_validation_args(args, f"{Path(compiler).name} project build", timeout=300, kind="build"))

        # .NET
        csproj = [f for f in all_files if f.lower().endswith((".csproj", ".sln"))]
        if csproj:
            dotnet = shutil.which("dotnet")
            msbuild = shutil.which("msbuild")
            target = csproj[0]
            if dotnet:
                results.append(self._run_validation_args([dotnet, "build", str(self._path(target)), "--nologo"], f"dotnet build {target} --nologo", timeout=300, kind="build"))
            elif msbuild:
                results.append(self._run_validation_args([msbuild, str(self._path(target)), "/nologo", "/p:Configuration=Release"], f"msbuild {target}", timeout=300, kind="build"))
            else:
                results.append({"kind": "build", "error": ".NET project exists but dotnet/msbuild was not found."})

        # Node/TypeScript build only when the project explicitly defines one. npx is
        # always --no-install so validation cannot fetch packages from the network.
        package_rel = lower.get("package.json")
        if package_rel:
            try:
                package = json.loads(self._path(package_rel).read_text(encoding="utf-8"))
            except Exception:
                package = {}
            scripts = package.get("scripts") if isinstance(package, dict) else {}
            scripts = scripts if isinstance(scripts, dict) else {}
            npm = shutil.which("npm")
            if scripts.get("build"):
                if npm:
                    results.append(self._run_validation_args([npm, "run", "build"], "npm run build", timeout=300, kind="build"))
                else:
                    results.append({"kind": "build", "error": "package.json defines a build script but npm was not found."})
            if "tsconfig.json" in lower:
                npx = shutil.which("npx")
                if npx:
                    results.append(self._run_validation_args([npx, "--no-install", "tsc", "--noEmit"], "npx --no-install tsc --noEmit", timeout=240, kind="build"))
                else:
                    results.append({"kind": "build", "error": "TypeScript project exists but npx was not found."})

        # Maven/Gradle Java/Kotlin projects. Prefer checked-in wrappers when present.
        if "pom.xml" in lower:
            mvnw_cmd = self.root / "mvnw.cmd"
            mvnw = self.root / "mvnw"
            mvn = str(mvnw_cmd) if os.name == "nt" and mvnw_cmd.is_file() else (str(mvnw) if mvnw.is_file() and os.access(mvnw, os.X_OK) else shutil.which("mvn"))
            if mvn:
                results.append(self._run_validation_args([mvn, "test"], "mvn test", timeout=300, kind="test"))
                results.append(self._run_validation_args([mvn, "package", "-DskipTests"], "mvn package -DskipTests", timeout=300, kind="build"))
            else:
                results.append({"kind": "build", "error": "pom.xml exists but Maven/mvnw was not found."})

        gradle_project = any(name in lower for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"))
        if gradle_project:
            gradlew_cmd = self.root / "gradlew.bat"
            gradlew = self.root / "gradlew"
            gradle = str(gradlew_cmd) if os.name == "nt" and gradlew_cmd.is_file() else (str(gradlew) if gradlew.is_file() and os.access(gradlew, os.X_OK) else shutil.which("gradle"))
            if gradle:
                results.append(self._run_validation_args([gradle, "build", "--no-daemon"], "gradle build --no-daemon", timeout=360, kind="build"))
            else:
                results.append({"kind": "build", "error": "Gradle project exists but gradle/gradlew was not found."})

        # Go and Rust have deterministic project-wide compile/test commands.
        if "go.mod" in lower:
            go = shutil.which("go")
            if go:
                results.append(self._run_validation_args([go, "test", "./..."], "go test ./...", timeout=300, kind="test"))
                results.append(self._run_validation_args([go, "build", "./..."], "go build ./...", timeout=300, kind="build"))
            else:
                results.append({"kind": "build", "error": "go.mod exists but Go was not found."})
        if "cargo.toml" in lower:
            cargo = shutil.which("cargo")
            if cargo:
                results.append(self._run_validation_args([cargo, "check"], "cargo check", timeout=300, kind="build"))
                results.append(self._run_validation_args([cargo, "test"], "cargo test", timeout=300, kind="test"))
            else:
                results.append({"kind": "build", "error": "Cargo.toml exists but cargo was not found."})

        # Flutter/Dart analysis is treated as build-quality evidence. Full mobile builds
        # are platform-signing dependent and are intentionally not launched automatically.
        if "pubspec.yaml" in lower:
            flutter = shutil.which("flutter")
            dart = shutil.which("dart")
            if flutter:
                results.append(self._run_validation_args([flutter, "analyze"], "flutter analyze", timeout=300, kind="build"))
            elif dart:
                results.append(self._run_validation_args([dart, "analyze"], "dart analyze", timeout=240, kind="build"))
            else:
                results.append({"kind": "build", "error": "pubspec.yaml exists but Flutter/Dart was not found."})

        return results
    def dispatch(self, name, args):
        table = {
            "workspace_info": self.workspace_info,
            "list_files": self.list_files,
            "read_file": self.read_file,
            "search_text": self.search_text,
            "replace_text": self.replace_text,
            "write_file": self.write_file,
            "delete_file": self.delete_file,
            "move_file": self.move_file,
            "run_validation": self.run_validation,
            "git_status": self.git_status,
            "git_diff": self.git_diff,
            "git_log": self.git_log,
            "git_branch": self.git_branch,
            "git_remote": self.git_remote,
            "git_pull": self.git_pull,
            "git_commit": self.git_commit,
            "git_push": self.git_push,
        }
        if name not in table:
            return {"error": f"Unknown tool: {name}"}
        try:
            return table[name](**(args or {}))
        except Exception as exc:
            return {"error": str(exc)}


def _tool_defs_openai():
    def fn(name, description, properties, required=None):
        return {"type": "function", "name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}}
    return [
        fn("workspace_info", "Show the exact mounted project root, sampled file count, and whether it is a Git repository.", {}),
        fn("list_files", "List project files.", {"path": {"type": "string"}, "pattern": {"type": "string"}}),
        fn("read_file", "Read a text file with line numbers.", {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, ["path"]),
        fn("search_text", "Search for text within project files.", {"query": {"type": "string"}, "path": {"type": "string"}}, ["query"]),
        fn("replace_text", "Replace exact text in a project file. Use targeted replacements.", {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "count": {"type": "integer"}}, ["path", "old", "new"]),
        fn("write_file", "Create or overwrite a project text file.", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
        fn("delete_file", "Delete one project file after making a Jarvis backup. Directories and sensitive files are not allowed.", {"path": {"type": "string"}}, ["path"]),
        fn("move_file", "Rename or move one project file inside the workspace, preserving a Jarvis backup.", {"source": {"type": "string"}, "destination": {"type": "string"}}, ["source", "destination"]),
        fn("run_validation", "Run a safe local validation/build command such as py_compile, pytest, node --check, npm test, npx tsc, flutter analyze, dart test, dotnet build/test, cmake/ctest, Gradle/Maven, go test, cargo test/check, UnrealBuildTool, or git diff/status.", {"command": {"type": "string"}}, ["command"]),
        fn("git_status", "Show Git status for the selected repository.", {}),
        fn("git_diff", "Show uncommitted Git diff.", {}),
        fn("git_log", "Show recent Git commits.", {"count": {"type": "integer"}}),
        fn("git_branch", "Show current Git branch.", {}),
        fn("git_remote", "Show configured Git remotes.", {}),
        fn("git_pull", "Fast-forward pull. Requires explicit Git-write authorization.", {"remote": {"type": "string"}, "branch": {"type": "string"}}),
        fn("git_commit", "Commit only files changed by this coding session. Requires explicit authorization.", {"message": {"type": "string"}}, ["message"]),
        fn("git_push", "Push current branch without force. Requires explicit authorization.", {"remote": {"type": "string"}, "branch": {"type": "string"}}),
    ]


def _tool_defs_claude():
    defs = _tool_defs_openai()
    out = []
    for d in defs:
        out.append({"name": d["name"], "description": d["description"], "input_schema": d["parameters"]})
    return out


def _coding_system(project_root, read_only, allow_git_write=False):
    project_root = str(Path(project_root).resolve())
    mode = "READ ONLY: never edit files." if read_only else "EDIT MODE: local source edits are authorized."
    git_mode = (
        "Normal Git pull/commit/push is authorized because this user request explicitly asked for it."
        if allow_git_write
        else "Git write operations are NOT authorized. Git status/diff/log/remotes are allowed."
    )
    return f"""You are a careful coding agent operating on the user's real Windows computer.
WORKSPACE_ROOT: {project_root}
{mode}
{git_mode}

Your FIRST tool call must be workspace_info, followed by list_files on ".".
Treat those tool results as ground truth. Never claim the project is empty unless
workspace_info/list_files actually prove that.

You may inspect/edit/create/validate files inside WORKSPACE_ROOT according to mode.
Never force-push, rewrite Git history, delete repositories/projects, alter API keys,
or edit protected secret files.

When WORKSPACE_ROOT is Jarvis itself:
- inspect Git status before editing;
- preserve unrelated user changes;
- use per-file backups before edits;
- validate changed Python/JavaScript files before declaring success;
- never modify ai_providers.env, credentials, tokens, or API keys;
- never commit or push unless the current user request explicitly authorizes it.
- never force-reset, clean, checkout over, or delete unrelated working-tree changes;
- treat current files and current Git state as authoritative over remembered/previous results;

Finish with: workspace used, root cause, files changed, validations, Git actions,
and remaining risks."""


def _git_write_requested(task):
    lower = str(task or "").lower()
    return any(
        p in lower for p in (
            "git commit", "commit the changes", "commit these changes",
            "push to github", "push the changes", "git push",
            "commit and push", "git pull", "pull the changes",
        )
    )


def run_openai_coding_agent(task, project_root, read_only=False, progress_callback=None):
    if not OPENAI_API_KEY:
        return False, "OpenAI is not configured yet. Add OPENAI_API_KEY first."
    selected_model = choose_nvidia_model(task, "coding")
    allow_git_write = _git_write_requested(task)
    try:
        tools = ProjectTools(project_root, read_only, allow_git_write=allow_git_write)
    except Exception as exc:
        return False, f"OpenAI coding workspace error: {exc}"

    def progress(message, turn=0, tool=""):
        if progress_callback:
            try:
                progress_callback({"message":str(message),"turn":int(turn or 0),"max_turns":MAX_AGENT_TURNS,"tool":str(tool or ""),"workspace":str(tools.root)})
            except Exception:
                pass

    progress(f"Workspace verified: {tools.root}",0,"workspace_info")
    payload={"model":OPENAI_MODEL,"instructions":_coding_system(project_root,read_only,allow_git_write),
             "input":"First call workspace_info, then list_files on '.'. After verifying the real workspace, perform this task: "+task,
             "tools":_tool_defs_openai(),"tool_choice":"auto","reasoning":{"effort":"high"}}
    previous_id=None
    seen={}
    for turn in range(1,MAX_AGENT_TURNS+1):
        progress("OpenAI is analyzing the project.",turn)
        if previous_id:
            payload={"model":OPENAI_MODEL,"previous_response_id":previous_id,"input":payload["input"],
                     "tools":_tool_defs_openai(),"tool_choice":"auto"}
        try:
            r=requests.post("https://api.openai.com/v1/responses",
                headers={"Authorization":f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"},
                json=payload,timeout=PROVIDER_TIMEOUT)
        except Exception as exc:
            return False,f"OpenAI coding agent connection error: {exc}"
        if r.status_code!=200:
            return False,f"OpenAI coding agent error {r.status_code}: {r.text[:500]}"
        data=r.json(); previous_id=data.get("id")
        calls=[x for x in data.get("output",[]) if x.get("type")=="function_call"]
        if not calls:
            text=_extract_openai_text(data); validations=tools.auto_validate()
            suffix=f"\n\nWorkspace: {tools.root}\nTool turns used: {turn}/{MAX_AGENT_TURNS}"
            if tools.changed: suffix+=f"\nChanged files: {sorted(tools.changed)}"
            if validations: suffix+=f"\nAutomatic validation: {json.dumps(validations)}"
            failed=any(
                isinstance(v,dict) and (
                    v.get("error") or
                    (v.get("returncode") is not None and int(v.get("returncode") or 0)!=0)
                ) for v in validations
            )
            if failed:
                progress("Automatic validation failed; task is not restart-ready.",turn)
                return False,(text or "Changes were made, but automatic validation failed.")+suffix
            if (tools.root/".git").exists():
                diff=tools.git_diff()
                if isinstance(diff,dict) and diff.get("stdout"):suffix+="\nGit diff inspected: yes"
            progress("OpenAI coding task completed and validated.",turn)
            return True,(text or "OpenAI coding agent completed.")+suffix

        sig=json.dumps([(str(c.get("name","")),str(c.get("arguments",""))[:2000]) for c in calls],sort_keys=True)
        seen[sig]=seen.get(sig,0)+1
        if seen[sig]>=4:
            progress("Repeated tool loop detected; stopping safely.",turn)
            return False,(f"OpenAI repeated the same coding-tool batch four times, so Jarvis stopped the job after {turn} turns "
                          f"to protect API usage. Workspace: {tools.root}")

        outputs=[]
        for call in calls:
            try: args=json.loads(call.get("arguments") or "{}")
            except Exception: args={}
            tool=call.get("name","")
            progress(f"Running coding tool: {tool}",turn,tool)
            result=tools.dispatch(tool,args)
            outputs.append({"type":"function_call_output","call_id":call.get("call_id"),"output":json.dumps(result)})
        payload["input"]=outputs

    progress("Tool-turn limit reached; returning a partial result.", MAX_AGENT_TURNS)
    return False, (
        f"OpenAI reached the {MAX_AGENT_TURNS}-turn coding budget. "
        f"Workspace: {tools.root}. Jarvis stopped the job to prevent runaway API usage. "
        f"Changed files so far: {sorted(tools.changed) if tools.changed else 'none'}. "
        "Review Agent Activity and the current Git diff before continuing."
    )


def run_claude_coding_agent(task, project_root, read_only=False, progress_callback=None):
    if not ANTHROPIC_API_KEY:
        return False, "Claude is not configured yet. Add ANTHROPIC_API_KEY first."
    allow_git_write = _git_write_requested(task)
    try:
        tools = ProjectTools(project_root, read_only, allow_git_write=allow_git_write)
    except Exception as exc:
        return False, f"Claude coding workspace error: {exc}"
    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_AGENT_TURNS):
        payload = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 8192,
            "system": _coding_system(project_root, read_only, allow_git_write),
            "messages": messages,
            "tools": _tool_defs_claude(),
        }
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=payload, timeout=PROVIDER_TIMEOUT)
        except Exception as exc:
            return False, f"Claude coding agent connection error: {exc}"
        if r.status_code != 200:
            return False, f"Claude coding agent error {r.status_code}: {r.text[:500]}"
        data = r.json()
        content = data.get("content", [])
        tool_calls = [b for b in content if b.get("type") == "tool_use"]
        if not tool_calls:
            text = "\n".join(str(b.get("text", "")) for b in content if b.get("type") == "text").strip()
            validations = tools.auto_validate()
            suffix = ""
            if tools.changed:
                suffix += f"\n\nChanged files: {sorted(tools.changed)}"
            if validations:
                suffix += f"\nAutomatic validation: {json.dumps(validations)}"
            failed = any(
                isinstance(v, dict) and (
                    v.get("error") or
                    (v.get("returncode") is not None and int(v.get("returncode") or 0) != 0)
                ) for v in validations
            )
            if failed:
                return False, (text or "Changes were made, but automatic validation failed.") + suffix
            return True, (text or "Claude coding agent completed.") + suffix
        messages.append({"role": "assistant", "content": content})
        tool_results = []
        for call in tool_calls:
            result = tools.dispatch(call.get("name", ""), call.get("input") or {})
            tool_results.append({"type": "tool_result", "tool_use_id": call.get("id"), "content": json.dumps(result)})
        messages.append({"role": "user", "content": tool_results})
    return False, "Claude coding agent reached the maximum number of tool turns."



def run_nvidia_coding_agent(task, project_root, read_only=False, progress_callback=None):
    """Tool-driven NVIDIA NIM coding agent using Jarvis's protected ProjectTools."""
    if not NVIDIA_API_KEY:
        return False, "NVIDIA NIM is not configured yet. Add NVIDIA_API_KEY first."

    allow_git_write = _git_write_requested(task)
    try:
        tools = ProjectTools(project_root, read_only, allow_git_write=allow_git_write)
    except Exception as exc:
        return False, f"NVIDIA coding workspace error: {exc}"

    task_low = str(task or "").lower()
    small_markers = (
        "small improvement", "very small", "one small", "tiny change",
        "single change", "simple fix", "quick fix", "minor fix",
    )
    nvidia_max_turns = min(
        MAX_AGENT_TURNS,
        18 if any(marker in task_low for marker in small_markers) else MAX_AGENT_TURNS,
    )

    def progress(message, turn=0, tool=""):
        if progress_callback:
            try:
                progress_callback({
                    "message": str(message),
                    "turn": int(turn or 0),
                    "max_turns": nvidia_max_turns,
                    "tool": str(tool or ""),
                    "workspace": str(tools.root),
                })
            except Exception:
                pass

    history = [
        {
            "role": "system",
            "content": (
                _coding_system(project_root, read_only, allow_git_write)
                + "\nYou control a protected project tool API. Reply ONLY as JSON. "
                  'Tool action: {"action":"tool","tool":"list_files|read_file|search_text|replace_text|write_file|run_command|git_status|git_diff|workspace_info","args":{...}}. '
                  'Finish action: {"action":"finish","summary":"..."}. '
                  "Inspect first, make the smallest necessary edit, validate it, inspect the final diff, then finish. "
                  "Never repeat an identical tool call after Jarvis already returned its result unless project state changed."
            ),
        },
        {
            "role": "user",
            "content": "First inspect workspace_info and the project, then complete: " + task,
        },
    ]

    repeat_counts = {}
    last_results = {}
    forced_validation = False

    def finalize_work(summary, turn):
        validations = tools.auto_validate()
        failed = any(
            isinstance(v, dict) and (
                v.get("error")
                or (
                    v.get("returncode") is not None
                    and int(v.get("returncode") or 0) != 0
                )
            )
            for v in validations
        )
        suffix = f"\n\nNVIDIA model: {selected_model}\nWorkspace: {tools.root}\nTool turns used: {turn}/{nvidia_max_turns}"
        if tools.changed:
            suffix += f"\nChanged files: {sorted(tools.changed)}"
        if validations:
            suffix += f"\nAutomatic validation: {json.dumps(validations)}"
        if (tools.root / ".git").exists():
            try:
                diff = tools.git_diff()
                if isinstance(diff, dict) and diff.get("stdout"):
                    suffix += "\nGit diff inspected: yes"
            except Exception:
                pass

        if failed:
            return False, summary + "\nAutomatic validation failed." + suffix
        if tools.changed:
            return True, summary + "\nCompleted edits were preserved and automatic validation passed." + suffix
        return False, summary + "\nNo source edits were completed." + suffix

    for turn in range(1, nvidia_max_turns + 1):
        progress(f"NVIDIA NIM ({selected_model}) is analyzing the project.", turn)

        try:
            response = requests.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": selected_model,
                    "messages": history,
                    "temperature": 0.1,
                    "max_tokens": 2500,
                },
                timeout=PROVIDER_TIMEOUT,
            )
        except Exception as exc:
            return False, f"NVIDIA coding agent connection error: {exc}"

        if response.status_code != 200:
            return False, f"NVIDIA coding agent error {response.status_code}: {response.text[:500]}"

        try:
            content = str(response.json()["choices"][0]["message"]["content"]).strip()
        except Exception as exc:
            return False, f"NVIDIA coding agent unreadable response: {exc}"

        cleaned = content.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()

        try:
            action = json.loads(cleaned)
        except Exception:
            history.append({"role":"assistant","content":content})
            history.append({"role":"user","content":"Invalid format. Reply with exactly one JSON action object."})
            continue

        if action.get("action") == "finish":
            return finalize_work(str(action.get("summary") or "NVIDIA coding task completed."), turn)

        if action.get("action") != "tool":
            history.append({"role":"assistant","content":content})
            history.append({"role":"user","content":"Choose exactly one action: tool or finish."})
            continue

        tool = str(action.get("tool") or "")
        args = action.get("args") or {}
        signature = json.dumps([tool, args], sort_keys=True, default=str)
        repeat_counts[signature] = repeat_counts.get(signature, 0) + 1
        repeat = repeat_counts[signature]

        if repeat >= 2:
            cached = last_results.get(signature, {"note":"No cached result."})
            history.append({"role":"assistant","content":content})

            if repeat == 2:
                progress("Repeated tool action detected; returning cached result and requesting a different next step.", turn, tool)
                history.append({
                    "role":"user",
                    "content": (
                        "That exact tool action already completed. Previous result:\n"
                        + json.dumps(cached, default=str)[:12000]
                        + "\nDo NOT repeat it. Choose the next different action needed to finish."
                    ),
                })
                continue

            if repeat == 3:
                progress("Second repeat detected; forcing validation and final-diff phase.", turn, tool)
                forced_validation = True
                history.append({
                    "role":"user",
                    "content": (
                        "You repeated the same completed action again. Stop exploring. "
                        "Move to validation and final-diff inspection now using a DIFFERENT action, then finish."
                    ),
                })
                continue

            progress("Repeat loop persisted; validating completed work and finishing safely.", turn, tool)
            return finalize_work(
                "NVIDIA entered a repeated-tool loop, so Jarvis stopped further repeated calls safely.",
                turn,
            )

        progress(f"Running coding tool: {tool}", turn, tool)
        result = tools.dispatch(tool, args)
        last_results[signature] = result
        history.append({"role":"assistant","content":content})
        history.append({
            "role":"user",
            "content": (
                "TOOL RESULT:\n"
                + json.dumps(result, default=str)
                + "\nContinue with one JSON action. Do not repeat this exact action unless project state changed."
            ),
        })

        if forced_validation and tool in {"run_command", "git_diff"}:
            history.append({
                "role":"user",
                "content": (
                    "Validation/final-diff phase is sufficient. "
                    'If acceptable, respond now with {"action":"finish","summary":"..."} instead of exploring more.'
                ),
            })

    return finalize_work(
        f"NVIDIA reached the focused {nvidia_max_turns}-turn budget.",
        nvidia_max_turns,
    )

def run_provider_coding_agent(provider, task, project_root, read_only=False, progress_callback=None):
    provider=(provider or "").lower()
    if provider=="openai":
        return run_openai_coding_agent(task,project_root,read_only,progress_callback=progress_callback)
    if provider=="claude":
        return run_claude_coding_agent(task,project_root,read_only,progress_callback=progress_callback)
    if provider=="nvidia":
        return run_nvidia_coding_agent(task,project_root,read_only,progress_callback=progress_callback)
    return False,"Gemini coding continues through Hermes, which already has local coding tools."
