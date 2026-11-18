"""status.json: what the dashboard shows about collection health.

Holds only timestamps, outcomes, counts and short sanitized reasons. It never
contains tokens or raw API responses.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA_VERSION = 1
_TOKEN_PATTERNS = re.compile(
    r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{10,})"
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(timezone.utc).isoformat() if value else None


def sanitize(message: str, limit: int = 200) -> str:
    """Strip anything token-shaped and bound the length."""
    cleaned = _TOKEN_PATTERNS.sub("[redacted]", message or "").strip()
    return cleaned[:limit]


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class StatusStore:
    """Keeps the in-memory status and writes it atomically on every change."""

    def __init__(self, path: Path, interval_seconds: int, users: list):
        self.path = path
        self.state: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "state": "idle",
            "users": list(users),
            "interval_seconds": interval_seconds,
            "last_success_at": None,
            "consecutive_failures": 0,
            "last_attempt": None,
            "next_run_at": None,
            "rate_limit": None,
            "updated_at": iso(utcnow()),
        }
        self._load_previous()

    def _load_previous(self) -> None:
        """Keep last-success history across worker restarts."""
        try:
            previous = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key in (
            "last_success_at",
            "consecutive_failures",
            "last_attempt",
            "backup",
            "security",
        ):
            if key in previous:
                self.state[key] = previous[key]

    def _save(self) -> None:
        self.state["updated_at"] = iso(utcnow())
        atomic_write_json(self.path, self.state)

    def schedule(self, next_run: Optional[datetime]) -> None:
        """Publish the planned next run time."""
        self.state["next_run_at"] = iso(next_run)
        self._save()

    def record_backup(
        self,
        *,
        ok: bool,
        at: datetime,
        interval_seconds: int,
        reason: str = "",
        sources: Optional[int] = None,
        repositories: Optional[int] = None,
    ) -> None:
        """Publish the outcome of the latest database backup (no paths or secrets)."""
        previous = self.state.get("backup") or {}
        self.state["backup"] = {
            "ok": ok,
            "last_attempt_at": iso(at),
            "last_success_at": iso(at) if ok else previous.get("last_success_at"),
            "interval_seconds": interval_seconds,
            "reason": "" if ok else sanitize(reason),
            "sources": sources if ok else previous.get("sources"),
            "repositories": repositories if ok else previous.get("repositories"),
        }
        self._save()

    def record_security(
        self,
        *,
        at: datetime,
        outcome: str,
        interval_seconds: int,
        checked: int = 0,
        read: int = 0,
        open_alerts: int = 0,
        reason: str = "",
    ) -> None:
        """Publish the latest Dependabot refresh (counts and a short reason)."""
        previous = self.state.get("security") or {}
        succeeded = outcome in ("success", "partial")
        self.state["security"] = {
            "outcome": outcome,
            "last_attempt_at": iso(at),
            "last_success_at": (
                iso(at) if succeeded else previous.get("last_success_at")
            ),
            "interval_seconds": interval_seconds,
            "repositories_checked": checked,
            "repositories_read": read,
            "open_alerts": open_alerts,
            "reason": sanitize(reason),
        }
        self._save()

    def mark_running(self, started: datetime) -> None:
        self.state["state"] = "running"
        self.state["running_since"] = iso(started)
        self._save()

    def record_attempt(
        self,
        *,
        started: datetime,
        finished: datetime,
        outcome: str,
        reason: str = "",
        error_count: int = 0,
        exit_code: Optional[int] = None,
        next_run: Optional[datetime] = None,
        rate_limit: Optional[Dict[str, Any]] = None,
    ) -> None:
        """outcome: success | partial | failed | skipped."""
        self.state["state"] = "idle"
        self.state.pop("running_since", None)
        self.state["last_attempt"] = {
            "started_at": iso(started),
            "finished_at": iso(finished),
            "duration_seconds": round((finished - started).total_seconds(), 1),
            "outcome": outcome,
            "reason": sanitize(reason),
            "error_count": error_count,
            "exit_code": exit_code,
        }
        if outcome in ("success", "partial"):
            self.state["last_success_at"] = iso(finished)
            self.state["consecutive_failures"] = 0
        elif outcome == "failed":
            self.state["consecutive_failures"] += 1
        if rate_limit is not None:
            self.state["rate_limit"] = rate_limit
        self.state["next_run_at"] = iso(next_run)
        self._save()
