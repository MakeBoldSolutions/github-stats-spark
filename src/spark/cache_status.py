"""Cache status tracking and validation for repository data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from spark.cache import APICache
from spark.time_utils import sanitize_timestamp_for_filename


class CacheStatusTracker:
    """Tracks cache status for repositories and determines refresh needs."""

    def __init__(self, cache_dir: str = ".cache"):
        """Initialize cache status tracker.

        Args:
            cache_dir: Directory where cache files are stored
        """
        self.cache = APICache(cache_dir)

    def get_repository_cache_status(
        self,
        username: str,
        repo_name: str,
        pushed_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive cache status for a repository."""

        # Determine expected cache key from pushed_at timestamp
        if pushed_at:
            pushed_date = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            if pushed_date.tzinfo is None:
                pushed_date = pushed_date.replace(tzinfo=timezone.utc)
            cache_key = sanitize_timestamp_for_filename(pushed_date)
        else:
            pushed_date = None
            cache_key = None

        cache_types = [
            "commits_stats",
            "commit_counts",
            "languages",
            "dependency_files",
            "readme",
            "ai_summary",
        ]

        essential_types = ["commits_stats", "commit_counts", "languages"]

        cache_files = {}
        oldest_timestamp = None
        newest_timestamp = None
        all_caches_exist = True

        for cache_type in cache_types:
            entry_info = self.cache.get_entry_info(cache_type, username, repo_name)
            exists = False
            timestamp = None

            if entry_info:
                weeks = entry_info.get("weeks", [])
                # Check if we have a matching cache key (timestamp-based)
                if cache_key and cache_key in weeks:
                    exists = True
                elif not cache_key and entry_info.get("latest_week"):
                    exists = True

                # Manifest updated_at is when the cache was written.
                # That's what we want for "cache age".
                timestamp_str = entry_info.get("updated_at")
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str)

            if exists and timestamp:
                if oldest_timestamp is None or timestamp < oldest_timestamp:
                    oldest_timestamp = timestamp
                if newest_timestamp is None or timestamp > newest_timestamp:
                    newest_timestamp = timestamp

            cache_files[cache_type] = {
                "exists": exists,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "age_hours": (
                    (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
                    if timestamp
                    else None
                ),
            }

            if not exists and cache_type in essential_types:
                all_caches_exist = False

        # Determine if refresh is needed
        refresh_needed = False
        refresh_reasons = []

        if not all_caches_exist:
            refresh_needed = True
            refresh_reasons.append("missing_cache_files")

        # Refresh only when repository push timestamp advances beyond cached metadata
        if pushed_date and all_caches_exist and newest_timestamp:
            if pushed_date > newest_timestamp:
                refresh_needed = True
                refresh_reasons.append("repo_has_new_commits")

        return {
            "has_cache": all_caches_exist,
            "cache_date": newest_timestamp.isoformat() if newest_timestamp else None,
            "cache_age_hours": (
                (datetime.now(timezone.utc) - newest_timestamp).total_seconds() / 3600
                if newest_timestamp
                else None
            ),
            "refresh_needed": refresh_needed,
            "refresh_reasons": refresh_reasons,
            "cache_files": cache_files,
            "cache_key": cache_key,
        }

    def update_repositories_cache_with_status(
        self,
        username: str,
        exclude_private: bool = True,
        exclude_forks: bool = True,
        exclude_archived: bool = True,
        fetch_fresh: bool = False,
    ) -> Dict[str, Any]:
        """Update repositories cache file with cache status for each repo.

        Args:
            username: GitHub username
            exclude_private: Exclude private repositories
            exclude_forks: Exclude forked repositories
            exclude_archived: Exclude archived repositories
            fetch_fresh: If True, fetch fresh data from GitHub API before updating status

        Returns:
            Dictionary with updated repos and metadata
        """
        variant = f"list_{exclude_private}_{exclude_forks}_{exclude_archived}"

        if fetch_fresh:
            # Clear cached repository list to force fresh fetch from GitHub API
            from pathlib import Path

            cache_dir = Path(self.cache.cache_dir) / username / variant / "repositories"
            if cache_dir.exists():
                import shutil

                shutil.rmtree(cache_dir)

            # Fetch fresh repository data from GitHub (1 API call)
            from spark.fetcher import GitHubFetcher

            fetcher = GitHubFetcher(cache=self.cache)
            repos = fetcher.fetch_repositories(
                username=username,
                exclude_private=exclude_private,
                exclude_forks=exclude_forks,
                exclude_archived=exclude_archived,
            )
        else:
            # Try to use cached repositories
            repos = self.cache.get("repositories", username, repo=variant) or []

            if not repos:
                # Cache doesn't exist, fetch fresh data automatically
                from spark.fetcher import GitHubFetcher

                fetcher = GitHubFetcher(cache=self.cache)
                repos = fetcher.fetch_repositories(
                    username=username,
                    exclude_private=exclude_private,
                    exclude_forks=exclude_forks,
                    exclude_archived=exclude_archived,
                )

        repos = [
            repo
            for repo in repos
            if not self._is_excluded_repo(
                repo, exclude_private, exclude_forks, exclude_archived
            )
        ]

        # Add cache status to each repository
        for repo in repos:
            repo_name = repo["name"]
            pushed_at = repo.get("pushed_at")

            cache_status = self.get_repository_cache_status(
                username=username,
                repo_name=repo_name,
                pushed_at=pushed_at,
            )

            repo["cache_status"] = cache_status

        # Update the cache
        self.cache.set("repositories", username, repos, repo=variant)

        from datetime import datetime

        return {"value": repos, "cache_status_updated": datetime.now().isoformat()}

    def get_repositories_needing_refresh(
        self,
        username: str,
        exclude_private: bool = True,
        exclude_forks: bool = True,
        exclude_archived: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get list of repositories that need cache refresh."""
        variant = f"list_{exclude_private}_{exclude_forks}_{exclude_archived}"
        repos = self.cache.get("repositories", username, repo=variant) or []

        if not repos:
            raise FileNotFoundError("Repositories cache not found")

        repos = [
            repo
            for repo in repos
            if not self._is_excluded_repo(
                repo, exclude_private, exclude_forks, exclude_archived
            )
        ]

        return [
            repo
            for repo in repos
            if repo.get("cache_status", {}).get("refresh_needed", True)
        ]

    def get_cache_statistics(
        self,
        username: str,
        exclude_private: bool = True,
        exclude_forks: bool = True,
        exclude_archived: bool = True,
    ) -> Dict[str, Any]:
        """Get overall cache statistics for a user's repositories."""
        variant = f"list_{exclude_private}_{exclude_forks}_{exclude_archived}"
        repos = self.cache.get("repositories", username, repo=variant) or []

        if not repos:
            return {
                "total_repositories": 0,
                "cached_repositories": 0,
                "needs_refresh": 0,
                "up_to_date": 0,
                "cache_hit_rate": "0%",
                "refresh_rate": "0%",
            }

        repos = [
            repo
            for repo in repos
            if not self._is_excluded_repo(
                repo, exclude_private, exclude_forks, exclude_archived
            )
        ]

        total = len(repos)
        cached = sum(
            1 for repo in repos if repo.get("cache_status", {}).get("has_cache", False)
        )
        needs_refresh = sum(
            1
            for repo in repos
            if repo.get("cache_status", {}).get("refresh_needed", True)
        )
        up_to_date = total - needs_refresh

        return {
            "total_repositories": total,
            "cached_repositories": cached,
            "needs_refresh": needs_refresh,
            "up_to_date": up_to_date,
            "cache_hit_rate": f"{(cached / total * 100):.1f}%" if total > 0 else "0%",
            "refresh_rate": (
                f"{(needs_refresh / total * 100):.1f}%" if total > 0 else "0%"
            ),
        }

    @staticmethod
    def _is_excluded_repo(
        repo: Dict[str, Any],
        exclude_private: bool,
        exclude_forks: bool,
        exclude_archived: bool,
    ) -> bool:
        is_private = repo.get("is_private")
        if is_private is None:
            is_private = repo.get("private", False)

        is_fork = repo.get("is_fork")
        if is_fork is None:
            is_fork = repo.get("fork", False)

        is_archived = repo.get("is_archived")
        if is_archived is None:
            is_archived = repo.get("archived", False)

        return (
            (exclude_private and bool(is_private))
            or (exclude_forks and bool(is_fork))
            or (exclude_archived and bool(is_archived))
        )
