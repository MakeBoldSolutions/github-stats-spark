"""Durable registry of GitHub sources and the portfolio they produce."""

from __future__ import annotations

from typing import Iterable, List

from spark.registry.store import Registry


def seed_users(registry: Registry, users: Iterable[str]) -> int:
    """Seed ``user`` sources on first start only, when the registry has none.

    After that the registry is the source of truth and the seed list is
    ignored, so removing a source is not undone by a restart.
    """
    if registry.list_sources():
        return 0
    added = 0
    for user in users:
        registry.add_source("user", user)
        added += 1
    return added


def collection_users(registry: Registry) -> List[str]:
    """Logins the per-user collection pipeline should run for."""
    return [
        s["identifier"]
        for s in registry.list_sources(enabled_only=True)
        if s["type"] == "user"
    ]


__all__ = ["Registry", "seed_users", "collection_users"]
