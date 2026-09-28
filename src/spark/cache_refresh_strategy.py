"""Helpers for coordinating cache refresh categories and decisions."""

from collections.abc import Callable
from datetime import datetime
from typing import Set

BASE_REFRESH_CATEGORIES = frozenset(
    {
        "commit_counts",
        "languages",
        "quality_indicators",
        "pull_request_summary",
        "security_summary",
        "diagnostics_summary",
        "web_signals",
        "community_health",
    }
)
# Data-gathering categories needed before AI summaries can be generated.
# These are GitHub API calls, not LLM calls, so they belong in Phase 2.
AI_DATA_CATEGORIES = frozenset({"readme", "dependency_files"})
# LLM summary generation runs in its own phase (Phase 2c) after all
# GitHub API data is cached, so it is never included in refresh_repository.
AI_SUMMARY_CATEGORY = "ai_summary"


def get_refresh_categories(include_ai_summaries: bool = False) -> Set[str]:
    """Return the cache categories that participate in a cache refresh run.

    Note: ``ai_summary`` is intentionally excluded here.  LLM generation
    runs in a dedicated phase after all GitHub data is cached.
    """
    categories = set(BASE_REFRESH_CATEGORIES)
    if include_ai_summaries:
        categories.update(AI_DATA_CATEGORIES)
    return categories


def should_refresh_repository(
    needs_refresh: Callable[[str, str, str, datetime], bool],
    username: str,
    repo_name: str,
    pushed_at: datetime,
    include_ai_summaries: bool = False,
) -> bool:
    """Determine whether any relevant category is missing or stale."""
    return any(
        needs_refresh(username, repo_name, category, pushed_at)
        for category in get_refresh_categories(include_ai_summaries)
    )
