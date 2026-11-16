"""JSON export of the registry for the app. The database stays the source of
truth; this file is a derived, rebuildable view."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from spark.registry.store import Registry, now_iso

SCHEMA_VERSION = 1

_SOURCE_FIELDS = (
    "id",
    "type",
    "identifier",
    "enabled",
    "state",
    "error_code",
    "error_message",
    "repository_count",
    "last_discovery_at",
)
_REPO_FIELDS = (
    "full_name",
    "description",
    "language",
    "html_url",
    "default_branch",
    "pushed_at",
    "is_fork",
    "is_private",
    "is_archived",
    "client",
    "project",
    "application",
    "first_seen_at",
    "last_seen_at",
)


def build_portfolio(registry: Registry) -> Dict[str, Any]:
    """One de-duplicated repository list plus per-source status.

    A repository appears once however many sources reach it. Excluded
    repositories and repositories reached only by disabled sources or by no
    source are left out of the list but retained in the database.
    """
    sources = registry.list_sources()
    enabled_ids = {s["id"] for s in sources if s["enabled"]}
    repositories: List[Dict[str, Any]] = []
    for repo in registry.list_repositories(include_excluded=False):
        reached_by = [s for s in repo["sources"] if s["id"] in enabled_ids]
        if not reached_by:
            continue
        item = {key: repo[key] for key in _REPO_FIELDS}
        for flag in ("is_fork", "is_private", "is_archived"):
            item[flag] = bool(item[flag])
        item["sources"] = [f"{s['type']}:{s['identifier']}" for s in reached_by]
        repositories.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "repository_count": len(repositories),
        "sources": [
            {**{k: s[k] for k in _SOURCE_FIELDS}, "enabled": bool(s["enabled"])}
            for s in sources
        ],
        "repositories": repositories,
    }


def write_portfolio(registry: Registry, path: Path) -> Dict[str, Any]:
    payload = build_portfolio(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return payload
