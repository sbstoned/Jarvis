"""Safe discovery and worker routing for Hermes/Jarvis MCP capabilities.

This module does not install servers, alter Hermes configuration, or expose
credentials.  It reads explicitly configured MCP registries, reports whether
local command transports are launchable, and gives workers a bounded capability
summary.  External connections still require the user's normal authentication.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


VERSION = "42.49.0"
ENGINE = "MCP_CAPABILITY_REGISTRY_V4242"
CATALOG_FILE = "JARVIS_MCP_TOOL_CATALOG.json"
REPORT_FILE = "JARVIS_MCP_CAPABILITY_REPORT.json"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _redact(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{16,}\b", "[REDACTED_API_KEY]", text)
    return text


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {} if default is None else default


def config_candidates(jarvis_root: Path | str | None = None) -> list[Path]:
    root = Path(jarvis_root or Path(__file__).resolve().parent).resolve()
    candidates = []
    explicit = str(os.getenv("JARVIS_MCP_CONFIG", "")).strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend([root / "mcp_servers.json", root / "hermes_mcp_servers.json", root / ".mcp.json"])
    local = str(os.getenv("LOCALAPPDATA", "")).strip()
    if local:
        candidates.extend([Path(local) / "hermes" / "mcp.json", Path(local) / "hermes" / "mcp_servers.json"])
    unique = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved not in unique:
            unique.append(resolved)
    return unique


def configured_servers(jarvis_root: Path | str | None = None) -> dict:
    selected = None
    payload = {}
    for candidate in config_candidates(jarvis_root):
        if candidate.is_file():
            candidate_payload = _load(candidate, {})
            if isinstance(candidate_payload, dict):
                selected = candidate
                payload = candidate_payload
                break
    raw_servers = payload.get("mcpServers") or payload.get("servers") or {}
    servers = []
    if isinstance(raw_servers, dict):
        for name, row in sorted(raw_servers.items()):
            row = row if isinstance(row, dict) else {}
            command = str(row.get("command") or "")
            transport = str(row.get("transport") or ("stdio" if command else "http" if row.get("url") else "unknown"))
            executable = shutil.which(command) if command and not Path(command).is_file() else command
            servers.append({
                "name": str(name), "transport": transport,
                "configured": True, "disabled": bool(row.get("disabled")),
                "command_available": bool(executable) if command else None,
                "command": _redact(Path(command).name if command else ""),
                "has_remote_url": bool(row.get("url")),
            })
    return {
        "version": "V" + VERSION, "engine": ENGINE, "updated_at": _utc_stamp(),
        "config_found": selected is not None,
        "config_file": selected.name if selected else "",
        "servers": servers,
        "available_count": sum(1 for row in servers if not row["disabled"] and row["command_available"] is not False),
    }


def catalog(jarvis_root: Path | str | None = None) -> dict:
    root = Path(jarvis_root or Path(__file__).resolve().parent).resolve()
    return _load(root / CATALOG_FILE, {"version": VERSION, "capabilities": []})


def capability_context(jarvis_root: Path | str | None = None, max_chars: int = 5000) -> str:
    root = Path(jarvis_root or Path(__file__).resolve().parent).resolve()
    report = configured_servers(root)
    recommended = []
    for item in catalog(root).get("capabilities") or []:
        if not isinstance(item, dict):
            continue
        recommended.append({
            "id": item.get("id"), "purpose": item.get("purpose"),
            "priority": item.get("priority"), "write_policy": item.get("write_policy"),
        })
    payload = {"configured": report, "catalog": recommended[:12]}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    return rendered[:max_chars]


def write_report(jarvis_root: Path | str | None = None) -> Path:
    root = Path(jarvis_root or Path(__file__).resolve().parent).resolve()
    target = root / REPORT_FILE
    payload = configured_servers(root)
    payload["catalog"] = catalog(root).get("capabilities") or []
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target
