"""Live local Qwen benchmark for Jarvis v2.74.

Streams output so the window never looks frozen, reports time-to-first-token and
approximate decode throughput, and shows the active runtime/model profile. Run it
only when Jarvis is not already generating because the local llama.cpp server has
one inference slot.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
BASE = os.getenv("JARVIS_QWEN_BASE_URL", "http://127.0.0.1:8081").rstrip("/")
URL = BASE + "/v1/chat/completions"
MODEL = os.getenv("JARVIS_QWEN_MODEL", "qwen-local") or "qwen-local"
RUNTIME = ROOT / "qwen_runtime_profile.json"
PROMPT = (
    "Write a concise Python function fibonacci(n) with input validation, then give "
    "two one-line usage examples. Do not explain beyond the code and examples."
)
MAX_TOKENS = int(os.getenv("JARVIS_QWEN_BENCHMARK_TOKENS", "64"))


def active_profile():
    try:
        data = json.loads(RUNTIME.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def run_once(number: int):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "repeat_penalty": 1.15,
        "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "stream": True,
    }
    started = time.perf_counter()
    first_token_at = None
    text_parts = []
    completion_tokens = 0
    server_tps = None

    print(f"\n--- Run {number} ---")
    with requests.post(URL, json=payload, stream=True, timeout=(15, 300)) as response:
        response.raise_for_status()
        for raw in response.iter_lines(decode_unicode=True):
            if not raw:
                continue
            line = str(raw).strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                data = json.loads(body)
            except Exception:
                continue
            choice = (data.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            piece = delta.get("content") or ""
            if piece:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                text_parts.append(piece)
                print(piece, end="", flush=True)
            usage = data.get("usage") or {}
            if usage.get("completion_tokens") is not None:
                try:
                    completion_tokens = max(completion_tokens, int(usage.get("completion_tokens") or 0))
                except Exception:
                    pass
            timings = data.get("timings") or {}
            for key in ("predicted_per_second", "tokens_per_second"):
                if timings.get(key) is not None:
                    try:
                        server_tps = float(timings[key])
                    except Exception:
                        pass

    finished = time.perf_counter()
    full_text = "".join(text_parts)
    if completion_tokens <= 0:
        # A conservative display-only estimate when llama.cpp does not stream usage.
        completion_tokens = max(1, round(len(full_text) / 4))
    ttft = (first_token_at - started) if first_token_at is not None else finished - started
    decode_elapsed = max(0.001, finished - (first_token_at or started))
    wall_elapsed = max(0.001, finished - started)
    decode_tps = completion_tokens / decode_elapsed

    print("\n")
    print(f"Time to first token : {ttft:.2f}s")
    print(f"Wall time           : {wall_elapsed:.2f}s")
    print(f"Completion tokens   : {completion_tokens} {'(estimated)' if not full_text else ''}")
    print(f"Approx decode speed : {decode_tps:.2f} tok/s")
    if server_tps is not None:
        print(f"llama.cpp reported  : {server_tps:.2f} tok/s")
    return {"ttft": ttft, "wall": wall_elapsed, "tokens": completion_tokens, "tps": decode_tps, "server_tps": server_tps}


def main():
    try:
        r = requests.get(BASE + "/health", timeout=3)
        r.raise_for_status()
    except Exception as exc:
        print(f"Local Qwen is not reachable at {BASE}: {exc}")
        print("Start Jarvis/START_QWEN_LOCAL.bat first.")
        raise SystemExit(1)

    profile = active_profile()
    print(f"Local Qwen: {BASE}")
    if profile:
        print(f"Active model : {profile.get('model','unknown')}")
        print(f"Profile      : {profile.get('profile','unknown')}")
        print(f"Context      : {profile.get('context','?')}")
        print(f"GPU layers   : {profile.get('gpu_layers','auto')}")
        print(f"Load mode    : {profile.get('load_mode','?')}")
        print(f"KV location  : {profile.get('kv_location','?')}")
        print(f"KV cache     : {profile.get('kv_cache','?')}")
        print(f"Prompt cache : {profile.get('prompt_cache','server/default')}")
    print(f"\nRunning two identical {MAX_TOKENS}-token streaming checks.")
    print("The second run can reuse the prompt cache. Do not run Jarvis generation at the same time.")

    first = run_once(1)
    second = run_once(2)

    print("=== Comparison ===")
    print(f"Run 1: TTFT {first['ttft']:.2f}s | ~{first['tps']:.2f} tok/s")
    print(f"Run 2: TTFT {second['ttft']:.2f}s | ~{second['tps']:.2f} tok/s")
    if first["ttft"] > 0:
        improvement = (first["ttft"] - second["ttft"]) / first["ttft"] * 100.0
        print(f"Prompt-cache TTFT change: {improvement:+.1f}% (positive means faster on run 2)")
    print("\nFor Qwen3.5 V32, low single-digit tok/s or very high TTFT usually means the server fell back to CPU KV; check qwen_runtime_profile.json.")


if __name__ == "__main__":
    main()
