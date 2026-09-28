"""Build per-repository detail JSON files from cached data.

Assembles all cached categories into a single rich JSON per repo,
suitable for feeding to an LLM for summary generation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from spark.cache import APICache
from spark.logger import get_logger
from spark.time_utils import sanitize_timestamp_for_filename

logger = get_logger()

# Categories to include in the detail JSON
DETAIL_CATEGORIES = [
    "languages",
    "readme",
    "quality_indicators",
    "dependency_files",
    "community_health",
    "pull_request_summary",
    "security_summary",
    "web_signals",
]


def build_repo_detail(
    cache: APICache,
    username: str,
    repo: Dict[str, Any],
) -> Dict[str, Any]:
    """Assemble all cached data for a single repo into a detail dict.

    Args:
        cache: The API cache instance
        username: GitHub username/owner
        repo: Repository dict from fetcher (must have 'name', 'pushed_at')

    Returns:
        Consolidated detail dict with all available signals
    """
    repo_name = repo["name"]
    pushed_at_str = repo.get("pushed_at")
    if pushed_at_str:
        pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
        if pushed_at.tzinfo is None:
            pushed_at = pushed_at.replace(tzinfo=timezone.utc)
        cache_key = sanitize_timestamp_for_filename(pushed_at)
    else:
        cache_key = None

    # Start with base repo metadata from fetcher
    detail: Dict[str, Any] = {
        "metadata": {
            "owner": username,
            "repo": repo_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1.0.0",
        },
        "base": {
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "primary_language": repo.get("language"),
            "stars": repo.get("stars", 0),
            "forks": repo.get("forks", 0),
            "watchers": repo.get("watchers", 0),
            "size_kb": repo.get("size", 0),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
            "homepage": repo.get("homepage"),
            "has_pages": repo.get("has_pages", False),
            "is_archived": repo.get("is_archived", False),
        },
    }

    # Load each cached category
    for category in DETAIL_CATEGORIES:
        data = cache.get(category, username, repo=repo_name, week=cache_key)
        if data is not None:
            detail[category] = data
        else:
            detail[category] = None

    # Trim readme to first 3000 chars for LLM context efficiency
    if detail.get("readme") and isinstance(detail["readme"], str):
        if len(detail["readme"]) > 3000:
            detail["readme"] = (
                detail["readme"][:3000] + "\n\n[... truncated for LLM context ...]"
            )

    return detail


def write_repo_details(
    cache: APICache,
    username: str,
    repos: List[Dict[str, Any]],
    output_dir: str = "data/users/{username}/repos",
) -> List[str]:
    """Build and write detail JSON files for all repos.

    Args:
        cache: The API cache instance
        username: GitHub username/owner
        repos: List of repository dicts from fetcher
        output_dir: Output directory template (supports {username} placeholder)

    Returns:
        List of written file paths
    """
    out_path = Path(output_dir.format(username=username))
    out_path.mkdir(parents=True, exist_ok=True)

    written = []
    for repo in repos:
        repo_name = repo["name"]
        detail = build_repo_detail(cache, username, repo)

        file_path = out_path / f"{repo_name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(detail, f, indent=2, default=str)

        written.append(str(file_path))
        logger.info(
            f"  Wrote {file_path.name} ({os.path.getsize(file_path) // 1024}KB)"
        )

    return written
