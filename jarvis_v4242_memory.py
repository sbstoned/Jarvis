"""Jarvis V42.46 shared, evidence-oriented memory.

Hermes owns conversational memory.  This module supplies the missing durable
coordination plane for Jarvis workers and project builders: a local SQLite/WAL
event store with explicit scope, project identity, repository revision,
provenance, and validation status.

The database stays beside Jarvis and is never copied into generated projects.
Projects receive a bounded JSON context snapshot containing only project repair
evidence, so personal conversation history cannot leak into output ZIPs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "42.49.0"
ENGINE = "SHARED_EVIDENCE_MEMORY_V4242"
DEFAULT_DB_NAME = "jarvis_shared_memory.sqlite3"
PROJECT_SNAPSHOT_FILE = "JARVIS_V4242_SHARED_CONTEXT.json"

_STORES: dict[str, "SharedMemoryStore"] = {}
_STORES_LOCK = threading.RLock()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _redact(value: object) -> str:
    """Remove common credential shapes before durable storage."""
    text = str(value or "")
    patterns = (
        (r"(?i)\b(authorization\s*:\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]"),
        (r"(?i)\b(api[_-]?key|secret|password|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]"),
        (r"\bsk-[A-Za-z0-9_-]{16,}\b", "[REDACTED_API_KEY]"),
        (r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b", "[REDACTED_TOKEN]"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def _safe_payload(payload: object, maximum: int = 65536) -> object:
    """Return JSON-safe, bounded, redacted data."""
    try:
        rendered = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        rendered = json.dumps({"value": str(payload)}, ensure_ascii=False)
    rendered = _redact(rendered)
    if len(rendered) > maximum:
        rendered = rendered[:maximum] + "…[truncated]"
    try:
        return json.loads(rendered)
    except Exception:
        return {"value": rendered}


def project_key(project_path: object) -> str:
    raw = str(project_path or "").strip()
    if not raw:
        return ""
    try:
        raw = str(Path(raw).expanduser().resolve())
    except Exception:
        pass
    normalized = raw.replace("\\", "/").rstrip("/").casefold()
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:24]


class SharedMemoryStore:
    """Thread-safe SQLite event/fact store using short independent connections."""

    def __init__(self, database: Path | str):
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database), timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    project_key TEXT NOT NULL DEFAULT '',
                    run_id TEXT NOT NULL DEFAULT '',
                    worker_id TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL,
                    repository_token TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_project
                    ON events(project_key, id DESC);
                CREATE INDEX IF NOT EXISTS idx_events_scope
                    ON events(scope, id DESC);
                CREATE TABLE IF NOT EXISTS facts (
                    scope TEXT NOT NULL,
                    project_key TEXT NOT NULL DEFAULT '',
                    fact_key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source_event_id INTEGER,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(scope, project_key, fact_key),
                    FOREIGN KEY(source_event_id) REFERENCES events(id)
                );
                """
            )

    def append_event(
        self,
        kind: str,
        payload: object,
        *,
        scope: str = "global",
        project: object = "",
        run_id: object = "",
        worker_id: object = "",
        repository_token: object = "",
        status: object = "",
        confidence: float = 1.0,
    ) -> int:
        safe = _safe_payload(payload)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO events(
                    created_at, scope, project_key, run_id, worker_id, kind,
                    repository_token, status, confidence, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_stamp(), str(scope or "global")[:32], project_key(project),
                    str(run_id or "")[:128], str(worker_id or "")[:128],
                    str(kind or "event")[:128], str(repository_token or "")[:128],
                    str(status or "")[:64], max(0.0, min(1.0, float(confidence))),
                    json.dumps(safe, ensure_ascii=False, default=str),
                ),
            )
            return int(cursor.lastrowid)

    def upsert_fact(
        self,
        fact_key: str,
        value: object,
        *,
        scope: str = "global",
        project: object = "",
        confidence: float = 1.0,
        source_event_id: int | None = None,
    ) -> None:
        safe = _safe_payload(value, maximum=16384)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO facts(scope, project_key, fact_key, value_json,
                                  confidence, source_event_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, project_key, fact_key) DO UPDATE SET
                    value_json=excluded.value_json,
                    confidence=excluded.confidence,
                    source_event_id=excluded.source_event_id,
                    updated_at=excluded.updated_at
                """,
                (
                    str(scope or "global")[:32], project_key(project),
                    str(fact_key or "fact")[:160],
                    json.dumps(safe, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, float(confidence))), source_event_id, _utc_stamp(),
                ),
            )

    def recent_events(self, *, project: object = "", limit: int = 20) -> list[dict]:
        key = project_key(project)
        bounded = max(1, min(100, int(limit)))
        with self._lock, self._connect() as connection:
            if key:
                rows = connection.execute(
                    "SELECT * FROM events WHERE project_key IN ('', ?) ORDER BY id DESC LIMIT ?",
                    (key, bounded),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM events WHERE project_key='' ORDER BY id DESC LIMIT ?",
                    (bounded,),
                ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json"))
            except Exception:
                item["payload"] = {"value": item.pop("payload_json", "")}
            result.append(item)
        return result

    def facts(self, *, project: object = "", limit: int = 40) -> list[dict]:
        key = project_key(project)
        bounded = max(1, min(100, int(limit)))
        with self._lock, self._connect() as connection:
            if key:
                rows = connection.execute(
                    "SELECT * FROM facts WHERE project_key IN ('', ?) ORDER BY updated_at DESC LIMIT ?",
                    (key, bounded),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM facts WHERE project_key='' ORDER BY updated_at DESC LIMIT ?",
                    (bounded,),
                ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["value"] = json.loads(item.pop("value_json"))
            except Exception:
                item["value"] = item.pop("value_json", "")
            result.append(item)
        return result

    def context_packet(self, *, project: object = "", limit: int = 12, max_chars: int = 6000) -> str:
        """Produce compact, provenance-labelled context for a worker."""
        wanted_key = project_key(project)
        rows = []
        for fact in self.facts(project=project, limit=12):
            rows.append({
                "kind": "fact", "scope": fact.get("scope"),
                "key": fact.get("fact_key"), "value": fact.get("value"),
                "confidence": fact.get("confidence"), "updated_at": fact.get("updated_at"),
            })
        for event in self.recent_events(project=project, limit=max(limit * 3, limit)):
            # Raw personal conversation events stay with the primary assistant.
            # Project workers receive project events plus explicitly global
            # coordination events/facts, never the full personal transcript.
            if wanted_key and not (
                event.get("project_key") == wanted_key
                or (not event.get("project_key") and event.get("scope") == "global")
            ):
                continue
            rows.append({
                "kind": event.get("kind"), "scope": event.get("scope"),
                "status": event.get("status"), "repository_token": event.get("repository_token"),
                "created_at": event.get("created_at"), "payload": event.get("payload"),
            })
            if sum(1 for row in rows if row.get("kind") != "fact") >= limit:
                break
        rendered = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
        if len(rendered) > max_chars:
            rendered = rendered[-max_chars:]
        return rendered

    def export_project_snapshot(self, project_path: Path | str, *, extra: dict | None = None) -> Path:
        root = Path(project_path).resolve()
        wanted_key = project_key(root)
        facts = [row for row in self.facts(project=root, limit=100) if row.get("project_key") == wanted_key]
        events = [row for row in self.recent_events(project=root, limit=100) if row.get("project_key") == wanted_key]
        payload = {
            "version": "V" + VERSION,
            "engine": ENGINE,
            "updated_at": _utc_stamp(),
            "project_key": wanted_key,
            "facts": facts[-30:],
            "recent_events": events[-40:],
        }
        if extra:
            payload["current"] = _safe_payload(extra, maximum=32768)
        target = root / PROJECT_SNAPSHOT_FILE
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        return target


def default_store(jarvis_root: Path | str | None = None) -> SharedMemoryStore:
    base = Path(jarvis_root or Path(__file__).resolve().parent).resolve()
    configured = str(os.getenv("JARVIS_SHARED_MEMORY_DB", "")).strip()
    database = Path(configured).expanduser().resolve() if configured else base / "memory" / DEFAULT_DB_NAME
    key = str(database).casefold()
    with _STORES_LOCK:
        store = _STORES.get(key)
        if store is None:
            store = SharedMemoryStore(database)
            _STORES[key] = store
        return store


def worker_context_contract(task: object, project_path: object, worker_id: object = "") -> str:
    """Return shared context plus the structured handoff every worker must produce."""
    try:
        context = default_store().context_packet(project=project_path, limit=14, max_chars=6500)
    except Exception:
        context = "[]"
    try:
        from jarvis_v4242_mcp_registry import capability_context
        capabilities = capability_context(Path(__file__).resolve().parent, max_chars=3500)
    except Exception:
        capabilities = "{}"
    return (
        "\n\nJARVIS V42.46 SHARED WORKER CONTEXT (evidence may be stale; current files and validators remain authoritative):\n"
        + context
        + "\n\nJARVIS V42.46 MCP CAPABILITY REGISTRY (configured availability must be checked before use):\n"
        + capabilities
        + "\n\nWORKER HANDOFF CONTRACT:\n"
        + "Return: root_cause, files_inspected, files_changed, commands_run, validation_before, "
          "validation_after, repository_revision, unresolved, and recommended_next_action. "
          "Never report a change or passing command without tool evidence. If the repository "
          "revision changed after this task began, stop and request replanning instead of overwriting newer work."
        + (f" Worker id: {worker_id}." if worker_id else "")
        + f" Assigned task: {_redact(task)[:2000]}"
    )


def safe_event(kind: str, payload: object, **fields: Any) -> int | None:
    try:
        return default_store().append_event(kind, payload, **fields)
    except Exception:
        return None
