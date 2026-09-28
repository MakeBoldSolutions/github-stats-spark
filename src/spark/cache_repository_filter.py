"""Helpers for filtering repositories during cache refresh."""

from typing import Any, Dict, Iterable, List


def is_excluded_repo(repo_data: Dict[str, Any]) -> bool:
    """Return True when a repository should not participate in refresh."""
    is_private = repo_data.get("is_private")
    if is_private is None:
        is_private = repo_data.get("private", False)

    is_fork = repo_data.get("is_fork")
    if is_fork is None:
        is_fork = repo_data.get("fork", False)

    is_archived = repo_data.get("is_archived")
    if is_archived is None:
        is_archived = repo_data.get("archived", False)

    return bool(is_private) or bool(is_fork) or bool(is_archived)


def filter_refreshable_repositories(
    repo_list: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter out repositories excluded by constitution or repo flags."""
    return [repo for repo in repo_list if not is_excluded_repo(repo)]
