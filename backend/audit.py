"""Append-only audit trail at output/audit_trail.json.

The file is a JSON array. Each write reads the existing records, appends, and
atomically replaces the file, so earlier runs are never lost. If the file is
unreadable it is moved aside (never deleted) and a new array is started.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from .config import AUDIT_PATH

_lock = threading.Lock()
MAX_FIELD_CHARS = 4000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _clip(value: Any) -> Any:
    """Keep records readable: long payloads are truncated, not dropped."""
    if value is None:
        return None
    try:
        text = json.dumps(value, default=str)
    except TypeError:
        text = json.dumps(str(value))
    if len(text) <= MAX_FIELD_CHARS:
        return json.loads(text)
    return text[:MAX_FIELD_CHARS] + "...[truncated]"


def _load() -> list[dict]:
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    backup = AUDIT_PATH.with_name(f"{AUDIT_PATH.stem}.corrupt-{datetime.now():%Y%m%d%H%M%S}.json")
    AUDIT_PATH.replace(backup)
    return []


def read_all() -> list[dict]:
    """Read every record without side effects (an unreadable file reads as empty)."""
    with _lock:
        if not AUDIT_PATH.exists():
            return []
        try:
            data = json.loads(AUDIT_PATH.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


def record(
    *,
    run_id: str,
    agent: str,
    action: str,
    ticket_id: int | None = None,
    tool: str | None = None,
    delegation_target: str | None = None,
    inputs: Any = None,
    outputs: Any = None,
    status: str = "ok",
    error: str | None = None,
    usage: dict | None = None,
) -> None:
    entry = {
        "timestamp": _now(),
        "run_id": run_id,
        "ticket_id": ticket_id,
        "agent": agent,
        "action": action,
        "tool": tool,
        "delegation_target": delegation_target,
        "inputs": _clip(inputs),
        "outputs": _clip(outputs),
        "status": status,
        "error": error,
    }
    if usage is not None:
        entry["usage"] = usage  # tokens/requests used by this step (delegations: the delegate's whole subtree)
    with _lock:
        records = _load()
        records.append(entry)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)
