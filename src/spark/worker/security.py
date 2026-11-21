"""Scheduled Dependabot refresh: its own cadence, independent of collection.

Alerts change without a push, so this re-reads every public repository on a
timer instead of waiting for ``pushed_at`` to move.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

from spark.registry import Registry
from spark.registry.connections import resolve_token
from spark.registry.secrets import SecretBox, SecretError
from spark.security.dependabot import (
    UNAUTHORIZED,
    AlertCollection,
    collect_dependabot_alerts,
)
from spark.security.export import write_dependabot
from spark.worker.settings import WorkerSettings

Collector = Callable[..., AlertCollection]


@dataclass
class SecurityRunResult:
    checked: int = 0  # repositories a check was attempted for
    read: int = 0  # repositories whose alerts were read
    skipped: int = 0  # repositories left for the next run (rate limit, shutdown)
    open_alerts: int = 0
    stopped_reason: str = ""

    @property
    def outcome(self) -> str:
        if self.checked == 0:
            return "skipped" if self.skipped else "success"
        if self.read == 0:
            return "failed"
        if self.read < self.checked or self.skipped:
            return "partial"
        return "success"


def _repository_tokens(
    registry: Registry, box: SecretBox, default_token: str
) -> List[tuple]:
    """(repository, token) for each public repository an enabled source reaches.

    A repository reached by several sources uses the first one whose
    connection can be used; ``None`` when none can."""
    sources = {s["id"]: s for s in registry.list_sources(enabled_only=True)}
    pairs = []
    for repo in registry.list_repositories(include_excluded=False):
        if repo["is_private"]:
            continue
        reaching = [sources[s["id"]] for s in repo["sources"] if s["id"] in sources]
        if not reaching:
            continue
        token: Optional[str] = None
        for source in reaching:
            try:
                token = resolve_token(registry, box, source, default=default_token)
                break
            except SecretError:
                continue
        pairs.append((repo, token))
    return pairs


def refresh_dependabot(
    settings: WorkerSettings,
    box: SecretBox,
    default_token: str,
    *,
    collect: Collector = collect_dependabot_alerts,
    stop_event: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda msg: print(msg, flush=True),
    on_progress: Callable[[], None] = lambda: None,
) -> SecurityRunResult:
    """Check every public repository and rewrite ``security/dependabot.json``."""
    stop_event = stop_event or threading.Event()
    result = SecurityRunResult()
    registry = Registry.open(settings.registry_path)
    try:
        pairs = _repository_tokens(registry, box, default_token)
        for index, (repo, token) in enumerate(pairs):
            if stop_event.is_set():
                result.skipped += len(pairs) - index
                result.stopped_reason = "stopped during shutdown"
                break
            on_progress()
            if token is None:
                # Every connection that reaches it is unusable (expired or
                # unreadable). Say so rather than leaving it unchecked.
                result.checked += 1
                registry.save_dependabot_result(
                    repo["full_name"],
                    AlertCollection(status=UNAUTHORIZED, reason="connection_unusable"),
                    repo["client_id"],
                )
                continue
            collection = collect(repo["owner"], repo["name"], token)
            result.checked += 1
            registry.save_dependabot_result(
                repo["full_name"], collection, repo["client_id"]
            )
            if collection.read_alerts:
                result.read += 1
            if (
                collection.rate_remaining is not None
                and collection.rate_remaining < settings.min_rate_remaining
            ):
                result.skipped += len(pairs) - index - 1
                result.stopped_reason = (
                    f"GitHub rate limit low ({collection.rate_remaining} remaining)"
                )
                break
        write_dependabot(
            registry, settings.data_dir, settings.security_interval_seconds
        )
        result.open_alerts = _open_total(registry)
    finally:
        registry.close()
    log(
        f"Dependabot refresh {result.outcome}: {result.read}/{result.checked} "
        f"repositories read, {result.open_alerts} open alert(s)"
        + (f" ({result.stopped_reason})" if result.stopped_reason else "")
    )
    return result


def _open_total(registry: Registry) -> int:
    row = registry.conn.execute(
        "SELECT COUNT(*) FROM dependabot_alert WHERE state = 'open'"
    ).fetchone()
    return int(row[0])
