"""Centralized cache management with explicit refresh operations.

This module provides a clean separation between:
1. Cache validation - determining what needs refresh
2. Cache refresh - updating stale data from GitHub API
3. Cache reading - consuming cached data (in fetcher.py)

NO cache writes happen during data reading/assembly.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any

from spark.cache import APICache
from spark.cache_refresh_executor import CacheRefreshExecutor, RefreshResult
from spark.cache_refresh_strategy import (
    get_refresh_categories,
    should_refresh_repository,
)
from spark.cache_repository_filter import (
    filter_refreshable_repositories,
    is_excluded_repo,
)
from spark.time_utils import sanitize_timestamp_for_filename
from spark.logger import get_logger
from spark.summarizer import RepositorySummarizer


class RefreshSummary:
    """Summary of cache refresh for all repositories."""

    def __init__(
        self,
        total_repos: int,
        repos_refreshed: int,
        repos_unchanged: int,
        repos_failed: int,
        results: List[RefreshResult],
        api_calls_made: int,
    ):
        self.total_repos = total_repos
        self.repos_refreshed = repos_refreshed
        self.repos_unchanged = repos_unchanged
        self.repos_failed = repos_failed
        self.results = results
        self.api_calls_made = api_calls_made


class CacheManager:
    """Manages cache validation and refresh operations."""

    def __init__(
        self,
        github_client,
        cache: APICache,
        summarizer: Optional[RepositorySummarizer] = None,
        fetcher: Optional[Any] = None,
        ai_model: Optional[str] = None,
    ):
        """Initialize cache manager.

        Args:
            github_client: PyGithub client instance
            cache: APICache instance
            summarizer: Optional pre-initialized RepositorySummarizer for AI summary refresh
            ai_model: AI model name from config (used when summarizer is not pre-provided)
        """
        self.github = github_client
        self.cache = cache
        self.logger = get_logger()
        self.summarizer = summarizer
        self.refresh_executor = CacheRefreshExecutor(
            github_client,
            cache,
            summarizer=summarizer,
            fetcher=fetcher,
            ai_model=ai_model,
        )

    @property
    def api_calls(self) -> int:
        return self.refresh_executor.api_calls

    @api_calls.setter
    def api_calls(self, value: int) -> None:
        self.refresh_executor.api_calls = value

    def needs_refresh(
        self, username: str, repo_name: str, category: str, current_pushed_at: datetime
    ) -> bool:
        """Check if a cache entry needs refresh based on repo's pushed_at.

        Args:
            username: Repository owner
            repo_name: Repository name
            category: Cache category (e.g., "commit_counts")
            current_pushed_at: Current pushed_at timestamp from GitHub

        Returns:
            True if cache is missing or stale
        """
        if not current_pushed_at:
            return True

        # Generate cache key for this repo's current state
        cache_key = sanitize_timestamp_for_filename(current_pushed_at)

        # Check if cache exists for this exact pushed_at
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)

        if cached is None:
            return True

        # Upgrade: commit_counts entries missing daily_commits must be re-fetched
        if category == "commit_counts" and not isinstance(
            cached.get("daily_commits"), dict
        ):
            return True

        return False

    def refresh_commit_counts(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_commit_counts(
            username, repo_name, pushed_at
        )

    def refresh_languages(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_languages(username, repo_name, pushed_at)

    def refresh_commits_stats(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_commits_stats(
            username, repo_name, pushed_at
        )

    def refresh_readme(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_readme(username, repo_name, pushed_at)

    def refresh_quality_indicators(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_quality_indicators(
            username, repo_name, pushed_at
        )

    def refresh_dependency_files(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_dependency_files(
            username, repo_name, pushed_at
        )

    def refresh_ai_summary(
        self, username: str, repo_data: Dict[str, Any], pushed_at: datetime
    ) -> RefreshResult:
        return self.refresh_executor.refresh_ai_summary(username, repo_data, pushed_at)

    def refresh_pull_request_summary(
        self,
        username: str,
        repo_name: str,
        pushed_at: datetime,
    ) -> RefreshResult:
        return self.refresh_executor.refresh_pull_request_summary(
            username, repo_name, pushed_at
        )

    def refresh_security_summary(
        self,
        username: str,
        repo_name: str,
        pushed_at: datetime,
    ) -> RefreshResult:
        return self.refresh_executor.refresh_security_summary(
            username, repo_name, pushed_at
        )

    def refresh_diagnostics_summary(
        self,
        username: str,
        repo_name: str,
        pushed_at: datetime,
    ) -> RefreshResult:
        return self.refresh_executor.refresh_diagnostics_summary(
            username, repo_name, pushed_at
        )

    def refresh_web_signals(
        self,
        username: str,
        repo_name: str,
        pushed_at: datetime,
    ) -> RefreshResult:
        return self.refresh_executor.refresh_web_signals(username, repo_name, pushed_at)

    def refresh_repository(
        self,
        username: str,
        repo_name: str,
        pushed_at: datetime,
        categories: Optional[Set[str]] = None,
        repo_data: Optional[Dict[str, Any]] = None,
        include_ai_summaries: bool = False,
    ) -> List[RefreshResult]:
        """Refresh all cache categories for a repository.

        Args:
            username: Repository owner
            repo_name: Repository name
            pushed_at: Repository's pushed_at timestamp
            categories: Specific categories to refresh (None = all)

        Returns:
            List of RefreshResult for each category
        """
        if categories is None:
            categories = get_refresh_categories(
                include_ai_summaries=include_ai_summaries
            )

        if include_ai_summaries:
            categories = set(categories) | {"readme", "dependency_files"}

        from time import time as _time, sleep as _sleep

        results = []

        def _timed_refresh(category, fn, *args, **kwargs):
            t0 = _time()
            result = fn(*args, **kwargs)
            elapsed = _time() - t0
            status = (
                "cached"
                if result.was_cached
                else ("ok" if result.refreshed else "fail")
            )
            self.logger.info(f"  {repo_name}/{category}: {status} ({elapsed:.1f}s)")
            results.append(result)
            # Pace API calls to avoid GitHub secondary rate limits.
            if not result.was_cached:
                _sleep(0.5)

        # --- Batch: languages, readme, quality_indicators, dependency_files ---
        # A single GraphQL call replaces ~15 individual REST calls.
        batch_cats = {
            "languages",
            "readme",
            "quality_indicators",
            "dependency_files",
        } & categories
        if batch_cats:
            t0 = _time()
            batch_results = self.refresh_executor.batch_refresh_repo_metadata(
                username, repo_name, pushed_at
            )
            elapsed = _time() - t0
            for r in batch_results:
                status = "cached" if r.was_cached else ("ok" if r.refreshed else "fail")
                self.logger.info(
                    f"  {repo_name}/{r.category}: {status} (batch {elapsed:.1f}s)"
                )
                results.append(r)
            if any(not r.was_cached for r in batch_results):
                _sleep(0.5)

        if "commit_counts" in categories:
            _timed_refresh(
                "commit_counts",
                self.refresh_commit_counts,
                username,
                repo_name,
                pushed_at,
            )

        if "commits_stats" in categories:
            _timed_refresh(
                "commits_stats",
                self.refresh_commits_stats,
                username,
                repo_name,
                pushed_at,
            )

        if "pull_request_summary" in categories:
            _timed_refresh(
                "pull_request_summary",
                self.refresh_pull_request_summary,
                username,
                repo_name,
                pushed_at,
            )

        if "security_summary" in categories:
            _timed_refresh(
                "security_summary",
                self.refresh_security_summary,
                username,
                repo_name,
                pushed_at,
            )

        if "diagnostics_summary" in categories:
            _timed_refresh(
                "diagnostics_summary",
                self.refresh_diagnostics_summary,
                username,
                repo_name,
                pushed_at,
            )

        # --- Phase 2b: Web scraping (no API quota, separate rate limit) ---
        if "web_signals" in categories:
            _timed_refresh(
                "web_signals", self.refresh_web_signals, username, repo_name, pushed_at
            )

        return results

    def refresh_user_data(
        self,
        username: str,
        repo_list: List[Dict],
        force_refresh: bool = False,
        include_ai_summaries: bool = False,
    ) -> RefreshSummary:
        """Refresh cache for all repositories of a user.

        This is the main entry point for cache refresh operations.

        Args:
            username: GitHub username
            repo_list: List of repository dicts with 'name' and 'pushed_at'
            force_refresh: If True, refresh all repos regardless of cache state

        Returns:
            RefreshSummary with results
        """
        eligible_repos = filter_refreshable_repositories(repo_list)
        self.logger.info(
            f"Starting cache refresh for {len(eligible_repos)} repositories"
        )
        self.api_calls = 0

        # Build work items: (index, repo_data, pushed_at) for repos that need refresh
        work_items = []
        repos_unchanged = 0

        for i, repo_data in enumerate(eligible_repos, 1):
            repo_name = repo_data["name"]
            pushed_at_str = repo_data.get("pushed_at")

            if not pushed_at_str:
                self.logger.debug(
                    f"[{i}/{len(repo_list)}] Skipping {repo_name} - no pushed_at"
                )
                continue

            try:
                pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
                if pushed_at.tzinfo is None:
                    pushed_at = pushed_at.replace(tzinfo=timezone.utc)
            except Exception as e:
                self.logger.warning(f"Failed to parse pushed_at for {repo_name}: {e}")
                continue

            if not force_refresh:
                needs_update = should_refresh_repository(
                    self.needs_refresh,
                    username,
                    repo_name,
                    pushed_at,
                    include_ai_summaries=include_ai_summaries,
                )
                if not needs_update:
                    self.logger.debug(
                        f"[{i}/{len(eligible_repos)}] OK {repo_name} - cache valid"
                    )
                    repos_unchanged += 1
                    continue

            work_items.append((i, repo_data, pushed_at))

        all_results: List[RefreshResult] = []
        repos_refreshed = 0
        repos_failed = 0

        def _refresh_one(item):
            idx, repo_data, pushed_at = item
            repo_name = repo_data["name"]
            self.logger.info(f"[{idx}/{len(eligible_repos)}] Refreshing {repo_name}")
            return self.refresh_repository(
                username,
                repo_name,
                pushed_at,
                repo_data=repo_data,
                include_ai_summaries=include_ai_summaries,
            )

        max_workers = min(2, len(work_items)) if work_items else 1
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_refresh_one, item): item for item in work_items}
            for future in as_completed(futures):
                try:
                    repo_results = future.result()
                    all_results.extend(repo_results)
                    if any(r.error for r in repo_results):
                        repos_failed += 1
                    else:
                        repos_refreshed += 1
                except Exception as exc:
                    idx, repo_data, _ = futures[future]
                    self.logger.warning(
                        f"Refresh failed for {repo_data['name']}: {exc}"
                    )
                    repos_failed += 1

        self.logger.info("Cache refresh complete:")
        self.logger.info(f"  Refreshed: {repos_refreshed}")
        self.logger.info(f"  Unchanged: {repos_unchanged}")
        self.logger.info(f"  Failed: {repos_failed}")
        self.logger.info(f"  API calls: {self.api_calls}")

        return RefreshSummary(
            total_repos=len(eligible_repos),
            repos_refreshed=repos_refreshed,
            repos_unchanged=repos_unchanged,
            repos_failed=repos_failed,
            results=all_results,
            api_calls_made=self.api_calls,
        )

    def generate_ai_summaries(
        self,
        username: str,
        repo_list: List[Dict],
    ) -> List[RefreshResult]:
        """Generate AI summaries for repositories that need them.

        This runs as a dedicated phase AFTER all GitHub API data has been
        cached, so the LLM call can read readme/dependency/commit data
        from cache without triggering any network fetches.

        Args:
            username: GitHub username
            repo_list: Repository dicts (must have 'name' and 'pushed_at')

        Returns:
            List of RefreshResult for the ai_summary category
        """
        eligible_repos = filter_refreshable_repositories(repo_list)

        # Build work items, skipping repos with cached summaries
        work_items = []
        cached = 0

        for i, repo_data in enumerate(eligible_repos, 1):
            repo_name = repo_data["name"]
            pushed_at_str = repo_data.get("pushed_at")
            if not pushed_at_str:
                continue

            try:
                pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
                if pushed_at.tzinfo is None:
                    pushed_at = pushed_at.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            cache_key = sanitize_timestamp_for_filename(pushed_at)
            if (
                self.cache.get("ai_summary", username, repo=repo_name, week=cache_key)
                is not None
            ):
                cached += 1
                continue

            work_items.append((i, repo_data, pushed_at))

        results: List[RefreshResult] = []
        generated = 0

        def _summarize_one(item):
            idx, repo_data, pushed_at = item
            self.logger.info(
                f"[{idx}/{len(eligible_repos)}] Generating AI summary for {repo_data['name']}"
            )
            return self.refresh_ai_summary(username, repo_data, pushed_at)

        max_workers = min(2, len(work_items)) if work_items else 1
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_summarize_one, item): item for item in work_items}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if result.refreshed:
                        generated += 1
                except Exception as exc:
                    _, repo_data, _ = futures[future]
                    self.logger.warning(
                        f"AI summary failed for {repo_data['name']}: {exc}"
                    )
                    results.append(
                        RefreshResult(
                            repo_name=repo_data["name"],
                            category="ai_summary",
                            was_cached=False,
                            refreshed=False,
                            error=str(exc),
                        )
                    )

        self.logger.info(
            f"AI summaries: {generated} generated, {cached} cached, {len(results) - generated} failed"
        )
        return results

    @staticmethod
    def _is_excluded_repo(repo_data: Dict[str, Any]) -> bool:
        return is_excluded_repo(repo_data)
