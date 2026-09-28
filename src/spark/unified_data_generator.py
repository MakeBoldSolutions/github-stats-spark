"""
Unified Data Generator - Clean 4-Phase Architecture

# SIZE JUSTIFICATION (Constitution I — ~831 LOC as of 2026-04-02):
# The 4-phase pipeline (fetch → refresh → assemble → output) must live in a
# single module to enforce the constitutional rule that cache reads are
# strictly separated from API writes (§IV Change-Driven Caching).  Splitting
# phases into separate modules would require complex inter-module state
# threading and risk violating the zero-API-call guarantee on second runs.
# Planned refactor into phase-specific helpers once boundary contracts are
# stabilized — tracked in CAP-2026-003.

Phase 1: Fetch repository list from GitHub
Phase 2: Validate & refresh caches (GitHub API only)
Phase 2c: AI summary generation (LLM calls, after all API data cached)
Phase 3: Assemble data from cache (read-only)
Phase 4: Write outputs (handled by caller)

Constitutional Requirements:
- NO time-based TTL logic
- Cache ONLY invalidated when repo pushed_at changes
- Clear separation: fetch -> refresh -> assemble -> output
- Zero API calls on second run if no repos changed
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from spark.cache import APICache
from spark.calculator import StatsCalculator
from spark.cache_manager import CacheManager
from spark.config import SparkConfig
from spark.dependencies.analyzer import RepositoryDependencyAnalyzer
from spark.fetcher import GitHubFetcher
from spark.logger import get_logger
from spark.models import (
    CommitHistory,
    Repository,
)
from spark.models.tech_stack import TechnologyStack
from spark.ranker import RepositoryRanker
from spark.summarizer import RepositorySummarizer
from spark.time_utils import sanitize_timestamp_for_filename

# Initialize logger
logger = get_logger(__name__)


class UnifiedDataGenerator:
    """Generates unified repository data using clean 4-phase architecture.

    Clean Architecture:
    1. Fetch: Get current repository list from GitHub
    2. Refresh: Update caches for repos with changes
    3. Assemble: Read all data from cache (no writes)
    4. Output: Write JSON/SVG files (no cache operations)
    """

    def __init__(
        self,
        username: str,
        config: SparkConfig,
        output_dir: Path,
        force_refresh: bool = False,
        cache: Optional[APICache] = None,
        include_ai_summaries: bool = False,
    ):
        """Initialize unified data generator.

        Args:
            username: GitHub username
            config: SparkConfig instance
            output_dir: Directory for output files
            force_refresh: Force refresh all caches
            cache: Optional shared cache instance
            include_ai_summaries: Whether to generate AI summaries
        """
        self.username = username
        self.config = config
        self.output_dir = Path(output_dir)
        self.force_refresh = force_refresh

        # All values come from config (no fallbacks — raise if missing)
        self.max_repositories = config.require(
            "dashboard.data_generation.max_repositories"
        )
        self.top_n_repos = config.require("analyzer.top_n")
        self.include_ai_summaries = include_ai_summaries or config.require(
            "dashboard.data_generation.include_ai_summaries"
        )

        # Initialize components
        self.cache = (
            cache if cache is not None else APICache(cache_dir=config.get_cache_dir())
        )
        self.fetcher = GitHubFetcher(
            cache=self.cache,
            max_repos=self.max_repositories,
            api_version_settings=self.config.get_github_api_version_config(),
        )
        self.ranker = RepositoryRanker(config=config.get_ranking_weights())

        logger.info(f"UnifiedDataGenerator initialized for user: {username}")
        logger.info(f"Max repositories: {self.max_repositories}")
        logger.info(f"Include AI summaries: {self.include_ai_summaries}")

        # Initialize cache manager for Phase 2 (pass ai_model for lazy summarizer creation)
        self.cache_manager = CacheManager(
            self.fetcher.github,
            self.cache,
            fetcher=self.fetcher,
            ai_model=config.get_ai_model(),
        )

    @staticmethod
    def _derive_weekly_activity(
        activity_calendar: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        """Derive weekly_activity array from activity_calendar for trailing 52 weeks."""
        from datetime import timedelta, date as date_type

        today = datetime.now(timezone.utc).date()
        # Start from Monday of 52 weeks ago
        start = today - timedelta(weeks=52)
        start = start - timedelta(days=start.weekday())  # align to Monday

        weeks: Dict[str, Dict[str, Any]] = {}
        current = start
        while current <= today:
            iso_year, iso_week, _ = current.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            if week_key not in weeks:
                # Cross-platform label: "Jan 6" (no leading zero, no %-d dependency)
                label = current.strftime("%b") + " " + str(current.day)
                weeks[week_key] = {
                    "week": week_key,
                    "label": label,
                    "commits": 0,
                    "active_repos": 0,
                }
            current += timedelta(days=1)

        for day_str, count in activity_calendar.items():
            try:
                d = date_type.fromisoformat(day_str)
            except (ValueError, TypeError):
                continue
            if d < start or d > today:
                continue
            iso_year, iso_week, _ = d.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            if week_key in weeks:
                weeks[week_key]["commits"] += count
                if count > 0:
                    weeks[week_key][
                        "active_repos"
                    ] += 1  # approximation: 1 active repo per day with commits

        return sorted(weeks.values(), key=lambda w: w["week"])

    @staticmethod
    def _calculate_staleness_score(days_since_last_push: Optional[int]) -> float:
        if days_since_last_push is None:
            return 60.0
        if days_since_last_push <= 14:
            return 0.0
        if days_since_last_push <= 30:
            return 12.0
        if days_since_last_push <= 90:
            return 35.0
        if days_since_last_push <= 180:
            return 65.0
        if days_since_last_push <= 365:
            return 85.0
        return 100.0

    @staticmethod
    def _calculate_pull_request_pressure(repo: Repository) -> Dict[str, Any]:
        summary = repo.pull_request_summary
        if summary.availability != "available":
            return {
                "score": 0.0,
                "availability": summary.availability,
                "reason": summary.reason,
                "total_open": summary.total_open,
                "draft_count": summary.draft_count,
                "review_requested_count": summary.review_requested_count,
                "oldest_open_age_days": summary.oldest_open_age_days,
            }

        oldest_open_age_days = summary.oldest_open_age_days or 0
        score = min(
            100.0,
            summary.total_open * 12.0
            + summary.draft_count * 4.0
            + summary.review_requested_count * 8.0
            + min(oldest_open_age_days, 180) * 0.35,
        )
        return {
            "score": round(score, 1),
            "availability": summary.availability,
            "reason": summary.reason,
            "total_open": summary.total_open,
            "draft_count": summary.draft_count,
            "review_requested_count": summary.review_requested_count,
            "oldest_open_age_days": summary.oldest_open_age_days,
        }

    @staticmethod
    def _calculate_security_attention(repo: Repository) -> Dict[str, Any]:
        summary = repo.security_summary
        alert_counts = summary.active_alert_counts or {}
        weighted_alerts = (
            alert_counts.get("critical", 0) * 45
            + alert_counts.get("high", 0) * 30
            + alert_counts.get("medium", 0) * 15
            + alert_counts.get("low", 0) * 8
        )
        availability_penalty = 0
        if summary.availability == "partial":
            availability_penalty = 10
        elif summary.availability != "available":
            availability_penalty = 20

        score = min(100.0, float(weighted_alerts + availability_penalty))
        return {
            "score": round(score, 1),
            "availability": summary.availability,
            "reason": summary.reason,
            "overall_state": summary.overall_state,
            "active_alert_counts": alert_counts,
        }

    @staticmethod
    def _calculate_dependency_attention(
        tech_stack: Optional[TechnologyStack],
    ) -> Dict[str, Any]:
        if not tech_stack:
            return {
                "score": 0.0,
                "total_dependencies": 0,
                "outdated_count": 0,
                "outdated_percentage": 0.0,
                "currency_score": 100,
                "version_coverage_percentage": 100.0,
                "latest_version_coverage_percentage": 100.0,
                "unknown_versions_count": 0,
            }

        unknown_pressure = max(0.0, 100.0 - tech_stack.version_coverage_percentage)
        currency_pressure = max(0.0, 100.0 - float(tech_stack.currency_score))
        score = min(
            100.0,
            currency_pressure * 0.65 + unknown_pressure * 0.35,
        )
        return {
            "score": round(score, 1),
            "total_dependencies": tech_stack.total_dependencies,
            "outdated_count": tech_stack.outdated_count,
            "outdated_percentage": tech_stack.outdated_percentage,
            "currency_score": tech_stack.currency_score,
            "version_coverage_percentage": tech_stack.version_coverage_percentage,
            "latest_version_coverage_percentage": tech_stack.latest_version_coverage_percentage,
            "unknown_versions_count": tech_stack.unknown_versions_count,
        }

    def _build_attention_metrics(
        self,
        repo: Repository,
        tech_stack: Optional[TechnologyStack],
        recent_commits_90d: int,
    ) -> Dict[str, Any]:
        pull_requests = self._calculate_pull_request_pressure(repo)
        security = self._calculate_security_attention(repo)
        dependency_health = self._calculate_dependency_attention(tech_stack)
        staleness_score = self._calculate_staleness_score(repo.days_since_last_push)
        if repo.open_issues > 0 and recent_commits_90d == 0:
            staleness_score = min(100.0, staleness_score + 10.0)

        components = {
            "pull_requests": pull_requests,
            "security": security,
            "staleness": {
                "score": round(staleness_score, 1),
                "days_since_last_push": repo.days_since_last_push,
                "recent_commits_90d": recent_commits_90d,
                "open_issues": repo.open_issues,
            },
            "dependencies": dependency_health,
        }

        score = round(
            pull_requests["score"] * 0.25
            + security["score"] * 0.35
            + staleness_score * 0.25
            + dependency_health["score"] * 0.15,
            1,
        )

        if score >= 70:
            tier = "critical"
        elif score >= 45:
            tier = "elevated"
        elif score >= 20:
            tier = "watch"
        else:
            tier = "healthy"

        reasons = []
        if security["score"] >= 20:
            reasons.append("security")
        if pull_requests["score"] >= 20:
            reasons.append("pull_requests")
        if staleness_score >= 35:
            reasons.append("staleness")
        if dependency_health["score"] >= 20:
            reasons.append("dependencies")

        return {
            "score": score,
            "tier": tier,
            "needs_attention": score >= 20,
            "reasons": reasons,
            "components": components,
        }

    def generate(self, single_repository: Optional[str] = None) -> Dict[str, Any]:
        """Generate unified data using clean 4-phase architecture.

        Phase 1: Fetch repository list
        Phase 2: Validate & refresh caches (GitHub API)
        Phase 2c: AI summary generation (LLM, runs only when enabled)
        Phase 3: Assemble data from cache
        Phase 4: (handled by caller - output generation)

        Args:
            single_repository: Optional name of a single repository to process.

        Returns:
            Dict with profile, repositories, and metadata
        """
        from time import time

        logger.info("=" * 70)
        logger.info("Starting Unified Data Generation")
        logger.info("=" * 70)
        logger.info(f"Force refresh mode: {self.force_refresh}")
        logger.info(f"AI summaries: {self.include_ai_summaries}")
        logger.info(f"Max repositories: {self.max_repositories}")
        if single_repository:
            logger.info(f"Single repository mode: {single_repository}")

        total_start = time()

        # PHASE 1: Fetch repository list from GitHub
        logger.info("\n[Phase 1] Fetching Repository List")
        phase1_start = time()
        raw_repos = self._fetch_repository_list()
        if single_repository:
            raw_repos = [r for r in raw_repos if r.get("name") == single_repository]
            logger.info(f"Filtered to single repository: {single_repository}")
        phase1_time = time() - phase1_start
        logger.info(f"Found {len(raw_repos)} repositories ({phase1_time:.2f}s)")

        # PHASE 2: Validate & refresh caches (GitHub API only, no LLM calls)
        logger.info("\n[Phase 2] Cache Validation & Refresh")
        phase2_start = time()
        refresh_summary = self.cache_manager.refresh_user_data(
            username=self.username,
            repo_list=raw_repos,
            force_refresh=self.force_refresh,
            include_ai_summaries=self.include_ai_summaries,
        )
        phase2_time = time() - phase2_start
        logger.info(
            f"Refreshed: {refresh_summary.repos_refreshed}, "
            f"Unchanged: {refresh_summary.repos_unchanged}, "
            f"API calls: {refresh_summary.api_calls_made} ({phase2_time:.2f}s)"
        )

        # PHASE 2b: Cache garbage collection — remove orphaned entries
        # Skip GC in single-repository mode to avoid removing other repos' caches.
        if not single_repository:
            try:
                active_names = [str(r["name"]) for r in raw_repos if r.get("name")]
                gc_result = self.cache.collect_garbage(self.username, active_names)
                if gc_result["removed_repos"]:
                    logger.info(
                        f"Cache GC: removed {len(gc_result['removed_repos'])} orphaned repos: "
                        f"{', '.join(gc_result['removed_repos'])}"
                    )
            except Exception as e:
                logger.warning(f"Cache garbage collection failed (non-fatal): {e}")

        # PHASE 2c: AI summary generation (LLM calls, separate from GitHub API)
        phase2c_time = 0.0
        if self.include_ai_summaries:
            logger.info("\n[Phase 2c] AI Summary Generation")
            phase2c_start = time()
            ai_results = self.cache_manager.generate_ai_summaries(
                username=self.username,
                repo_list=raw_repos,
            )
            phase2c_time = time() - phase2c_start
            ai_generated = sum(1 for r in ai_results if r.refreshed)
            ai_failed = sum(1 for r in ai_results if r.error)
            logger.info(
                f"AI summaries: {ai_generated} generated, {ai_failed} failed ({phase2c_time:.2f}s)"
            )

        # PHASE 3: Assemble data from cache
        logger.info("\n[Phase 3] Assembling Data from Cache")
        phase3_start = time()
        unified_data = self._assemble_data(raw_repos)
        phase3_time = time() - phase3_start
        logger.info(
            f"Assembled data for {len(unified_data['repositories'])} repositories ({phase3_time:.2f}s)"
        )

        total_time = time() - total_start
        logger.info("\n" + "=" * 70)
        logger.info(f"Data Generation Complete: {total_time:.2f}s total")
        logger.info(f"  Phase 1 (Fetch): {phase1_time:.2f}s")
        logger.info(f"  Phase 2 (Refresh): {phase2_time:.2f}s")
        if self.include_ai_summaries:
            logger.info(f"  Phase 2c (AI Summaries): {phase2c_time:.2f}s")
        logger.info(f"  Phase 3 (Assemble): {phase3_time:.2f}s")
        logger.info("=" * 70)

        return unified_data

    def _fetch_repository_list(self) -> List[Dict]:
        """Phase 1: Fetch current repository list from GitHub.

        Returns:
            List of repository dicts with metadata
        """
        repos_config = self.config.config.get("repositories", {})
        exclude_forks = repos_config.get("exclude_forks", True)
        exclude_archived = repos_config.get("exclude_archived", True)
        return self.fetcher.fetch_repositories(
            username=self.username,
            exclude_private=True,
            exclude_forks=exclude_forks,
            exclude_archived=exclude_archived,
        )

    def _assemble_data(self, raw_repos: List[Dict]) -> Dict[str, Any]:
        """Phase 3: Assemble unified data by reading from cache.

        This phase ONLY reads from cache, never writes.

        Args:
            raw_repos: List of repository dicts from Phase 1

        Returns:
            Dict with 'profile', 'repositories', 'metadata' keys
        """
        repositories = []
        commit_histories = {}
        repo_daily_commits: Dict[str, Dict[str, int]] = (
            {}
        )  # repo_name -> {"YYYY-MM-DD": count}
        repo_cache: Dict[str, Dict[str, Any]] = {}
        dependency_analyzer = RepositoryDependencyAnalyzer(
            config=self.config.config.get("analyzer", {})
        )
        summarizer = RepositorySummarizer(
            cache=self.cache, enable_ai=False, model=self.config.get_ai_model()
        )

        total_repos = min(len(raw_repos), self.max_repositories)
        assembled_ok = 0
        assemble_started_at = datetime.now(timezone.utc)
        logger.info(f"Phase 3 cache assembly progress: 0/{total_repos} repositories")

        for i, repo_data in enumerate(raw_repos[: self.max_repositories], 1):
            repo_name = repo_data["name"]
            logger.debug(
                f"[{i}/{min(len(raw_repos), self.max_repositories)}] Assembling {repo_name}"
            )

            if i == 1 or i % 10 == 0 or i == total_repos:
                elapsed_seconds = int(
                    (datetime.now(timezone.utc) - assemble_started_at).total_seconds()
                )
                logger.info(
                    f"Phase 3 cache assembly progress: {i}/{total_repos} "
                    f"(assembled={assembled_ok}, elapsed={elapsed_seconds}s) - loading {repo_name}"
                )

            try:
                # Parse pushed_at
                pushed_at_str = repo_data.get("pushed_at")
                if pushed_at_str:
                    pushed_at = datetime.fromisoformat(
                        pushed_at_str.replace("Z", "+00:00")
                    )
                    if pushed_at.tzinfo is None:
                        pushed_at = pushed_at.replace(tzinfo=timezone.utc)
                else:
                    pushed_at = None

                cache_key = (
                    sanitize_timestamp_for_filename(pushed_at) if pushed_at else None
                )

                # Read commit counts from cache
                commit_data = self.fetcher.fetch_commit_counts(
                    self.username, repo_name, repo_pushed_at=pushed_at
                )

                if commit_data:
                    commit_histories[repo_name] = CommitHistory(
                        repository_name=repo_name,
                        total_commits=commit_data.get("total", 0),
                        recent_90d=commit_data.get("recent_90d", 0),
                        recent_180d=commit_data.get("recent_180d", 0),
                        recent_365d=commit_data.get("recent_365d", 0),
                        last_commit_date=(
                            datetime.fromisoformat(commit_data["last_commit_date"])
                            if commit_data.get("last_commit_date")
                            else None
                        ),
                    )
                    if isinstance(commit_data.get("daily_commits"), dict):
                        repo_daily_commits[repo_name] = commit_data["daily_commits"]

                # Read language stats from cache
                language_stats = (
                    self.fetcher.fetch_languages(
                        self.username, repo_name, repo_pushed_at=pushed_at
                    )
                    or {}
                )

                # Read cached AI summary, README, dependency files, and commit stats
                readme_content = ""
                dependency_files: Dict[str, str] = {}
                commit_stats = None
                cached_summary = None

                if cache_key:
                    readme_content = (
                        self.cache.get(
                            "readme", self.username, repo=repo_name, week=cache_key
                        )
                        or ""
                    )
                    dependency_files = (
                        self.cache.get(
                            "dependency_files",
                            self.username,
                            repo=repo_name,
                            week=cache_key,
                        )
                        or {}
                    )
                    commit_stats = self.cache.get(
                        "commits_stats", self.username, repo=repo_name, week=cache_key
                    )
                    cached_summary = self.cache.get(
                        "ai_summary", self.username, repo=repo_name, week=cache_key
                    )
                    # Read quality indicators from cache
                    quality_indicators = self.cache.get(
                        "quality_indicators",
                        self.username,
                        repo=repo_name,
                        week=cache_key,
                    )
                    pull_request_summary = self.cache.get(
                        "pull_request_summary",
                        self.username,
                        repo=repo_name,
                        week=cache_key,
                    )
                    security_summary = self.cache.get(
                        "security_summary",
                        self.username,
                        repo=repo_name,
                        week=cache_key,
                    )
                    diagnostics_summary = self.cache.get(
                        "diagnostics_summary",
                        self.username,
                        repo=repo_name,
                        week=cache_key,
                    )
                    if quality_indicators:
                        repo_data["has_license"] = quality_indicators.get(
                            "has_license", False
                        )
                        repo_data["has_ci_cd"] = quality_indicators.get(
                            "has_ci_cd", False
                        )
                        repo_data["has_tests"] = quality_indicators.get(
                            "has_tests", False
                        )
                        repo_data["has_docs"] = quality_indicators.get(
                            "has_docs", False
                        )
                    if pull_request_summary:
                        repo_data["pull_request_summary"] = pull_request_summary
                    if security_summary:
                        repo_data["security_summary"] = security_summary
                    if diagnostics_summary:
                        repo_data["diagnostics_summary"] = diagnostics_summary

                if "pull_request_summary" not in repo_data:
                    logger.debug(
                        f"No cached pull_request_summary for {repo_name}; using unavailable default"
                    )
                    repo_data["pull_request_summary"] = {
                        "availability": "unavailable",
                        "reason": "not_cached",
                        "has_open_pull_requests": False,
                        "total_open": 0,
                        "draft_count": 0,
                        "review_requested_count": 0,
                        "oldest_open_age_days": None,
                        "source": "rest.pulls.list",
                    }
                if "security_summary" not in repo_data:
                    logger.debug(
                        f"No cached security_summary for {repo_name}; using unavailable default"
                    )
                    repo_data["security_summary"] = {
                        "availability": "unavailable",
                        "reason": "not_cached",
                        "overall_state": "unavailable",
                        "feature_status": {
                            "advanced_security": "unavailable",
                            "secret_scanning": "unavailable",
                            "secret_scanning_push_protection": "unavailable",
                            "dependency_alerts": "unavailable",
                            "automated_security_fixes": "unavailable",
                        },
                        "active_alert_counts": {
                            "total_open": 0,
                            "critical": 0,
                            "high": 0,
                            "medium": 0,
                            "low": 0,
                        },
                        "sources": [],
                    }
                if "diagnostics_summary" not in repo_data:
                    logger.debug(
                        f"No cached diagnostics_summary for {repo_name}; using unavailable default"
                    )
                    repo_data["diagnostics_summary"] = {
                        "availability": "unavailable",
                        "reason": "not_cached",
                        "pull_requests": {
                            "availability": "unavailable",
                            "reason": "not_cached",
                            "total_open": 0,
                            "oldest_open_age_days": None,
                        },
                        "issues": {
                            "availability": "unavailable",
                            "reason": "not_cached",
                            "total_open": 0,
                            "oldest_open_age_days": None,
                            "stale_over_30d": 0,
                            "stale_over_90d": 0,
                        },
                        "security": {
                            "availability": "unavailable",
                            "reason": "not_cached",
                            "dependabot": {
                                "total_open": 0,
                                "critical": 0,
                                "high": 0,
                                "medium": 0,
                                "low": 0,
                            },
                            "code_scanning": {
                                "total_open": 0,
                                "error": 0,
                                "warning": 0,
                                "note": 0,
                            },
                        },
                        "actions": {
                            "availability": "unavailable",
                            "reason": "not_cached",
                            "recent_runs": 0,
                            "success_count": 0,
                            "failure_count": 0,
                            "last_run_status": None,
                            "last_run_conclusion": None,
                            "last_run_age_days": None,
                        },
                        "sources": [],
                    }

                if cached_summary is None:
                    cached_summary = self.cache.get(
                        "ai_summary", self.username, repo=repo_name
                    )

                # Create Repository object
                repo_data["language_stats"] = language_stats
                repo_data["language_count"] = len(language_stats)
                repo = Repository.from_dict(repo_data)
                repo.has_readme = bool(readme_content)
                repositories.append(repo)
                assembled_ok += 1
                repo_cache[repo_name] = {
                    "readme_content": readme_content,
                    "dependency_files": dependency_files,
                    "commit_stats": commit_stats,
                    "cached_summary": cached_summary,
                }

            except Exception as e:
                logger.warn(f"Failed to assemble {repo_name}: {e}")
                continue

        total_elapsed_seconds = int(
            (datetime.now(timezone.utc) - assemble_started_at).total_seconds()
        )
        logger.info(
            f"Phase 3 cache assembly complete: assembled {assembled_ok}/{total_repos} "
            f"repositories in {total_elapsed_seconds}s"
        )

        # Rank repositories
        logger.info(f"Ranking {len(repositories)} repositories...")
        ranked_repos = self.ranker.rank_repositories(
            repositories, commit_histories, top_n=self.top_n_repos
        )

        # Create repository dicts
        unified_repos = []
        for rank, (repo, score) in enumerate(ranked_repos, 1):
            commit_history = commit_histories.get(repo.name)
            repo_extras = repo_cache.get(repo.name, {})
            readme_content = repo_extras.get("readme_content", "")
            dependency_files = repo_extras.get("dependency_files", {})
            commit_stats = repo_extras.get("commit_stats")
            cached_summary = repo_extras.get("cached_summary")
            commit_history_dict = commit_history.to_dict() if commit_history else None
            commit_metrics = None
            avg_commit_size = None
            largest_commit = None
            smallest_commit = None
            first_commit_date = repo.created_at

            if commit_stats:
                metrics = StatsCalculator.calculate_repository_commit_metrics(
                    commit_stats
                )
                commit_metrics = {
                    "avg_size": metrics.get("avg_commit_size", 0.0),
                    "largest_commit": metrics.get("largest_commit"),
                    "smallest_commit": metrics.get("smallest_commit"),
                    "total_commits": metrics.get("total_commits", 0),
                    "commit_size_distribution": metrics.get("commit_size_distribution"),
                }
                avg_commit_size = commit_metrics["avg_size"]
                largest_commit = commit_metrics["largest_commit"]
                smallest_commit = commit_metrics["smallest_commit"]

                commit_dates = []
                for commit in commit_stats:
                    date_str = commit.get("commit", {}).get("author", {}).get("date")
                    if not date_str:
                        continue
                    try:
                        commit_dates.append(
                            datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        )
                    except ValueError:
                        continue
                if commit_dates:
                    first_commit_date = min(commit_dates)

            if commit_history_dict is not None:
                commit_history_dict["first_commit_date"] = (
                    first_commit_date.isoformat() if first_commit_date else None
                )

            tech_stack = None
            if dependency_files:
                dep_report = dependency_analyzer.analyze_repository(dependency_files)
                if dep_report.total_dependencies > 0:
                    tech_stack = dependency_analyzer.build_technology_stack(
                        repository_name=repo.name,
                        report=dep_report,
                        dependency_file_type=next(iter(dependency_files.keys()), None),
                        languages=repo.language_stats or {},
                    )

            attention_metrics = self._build_attention_metrics(
                repo,
                tech_stack,
                commit_history.recent_90d if commit_history else 0,
            )

            summary_payload = None
            if cached_summary and cached_summary.get("ai_summary"):
                summary_payload = {
                    "text": cached_summary.get("ai_summary"),
                    "ai_generated": True,
                    "generation_method": cached_summary.get("generation_method"),
                    "generated_at": cached_summary.get("generation_timestamp"),
                    "model_used": cached_summary.get("model_used"),
                    "tokens_used": cached_summary.get("tokens_used"),
                    "confidence_score": cached_summary.get("confidence_score"),
                }
            else:
                fallback_summary = summarizer.summarize_repository(
                    repo=repo,
                    readme_content=readme_content or None,
                    commit_history=commit_history,
                    language_stats=repo.language_stats,
                    tech_stack=tech_stack,
                    repository_owner=self.username,
                    repo_pushed_at=repo.pushed_at,
                    write_cache=False,
                    allow_ai=False,
                )
                summary_payload = {
                    "text": fallback_summary.summary,
                    "ai_generated": fallback_summary.is_ai_generated,
                    "generation_method": fallback_summary.generation_method,
                    "generated_at": (
                        fallback_summary.generation_timestamp.isoformat()
                        if fallback_summary.generation_timestamp
                        else None
                    ),
                    "model_used": fallback_summary.model_used,
                    "tokens_used": fallback_summary.tokens_used,
                    "confidence_score": fallback_summary.confidence_score,
                }

            ai_summary_text = (
                summary_payload.get("text")
                if summary_payload and summary_payload.get("ai_generated")
                else None
            )

            repo_dict = {
                "name": repo.name,
                "description": repo.description,
                "summary": summary_payload,
                "url": repo.url,
                "homepage": repo.homepage,  # Custom website URL from repo settings
                "has_pages": repo.has_pages,  # GitHub Pages enabled
                "pages_url": repo.pages_url,  # Constructed GitHub Pages URL
                "website_url": repo.website_url,  # Best available website (homepage or pages_url)
                "stars": repo.stars,
                "forks": repo.forks,
                "watchers": repo.watchers,
                "language": repo.primary_language,
                "language_stats": repo.language_stats,
                "languages": repo.language_stats,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                "total_commits": commit_history.total_commits if commit_history else 0,
                "recent_commits_90d": (
                    commit_history.recent_90d if commit_history else 0
                ),
                "first_commit_date": (
                    first_commit_date.isoformat() if first_commit_date else None
                ),
                "last_commit_date": (
                    commit_history.last_commit_date.isoformat()
                    if commit_history and commit_history.last_commit_date
                    else (repo.pushed_at.isoformat() if repo.pushed_at else None)
                ),
                "commit_history": commit_history_dict,
                "commit_metrics": commit_metrics,
                "avg_commit_size": avg_commit_size,
                "largest_commit": largest_commit,
                "smallest_commit": smallest_commit,
                "commit_velocity": (
                    commit_history.commit_frequency if commit_history else None
                ),
                "tech_stack": tech_stack.to_dict() if tech_stack else None,
                "has_readme": repo.has_readme,
                "has_license": repo.has_license,
                "has_ci_cd": repo.has_ci_cd,
                "has_tests": repo.has_tests,
                "has_docs": repo.has_docs,
                "language_count": repo.language_count,
                "size_kb": repo.size_kb,
                "is_fork": repo.is_fork,
                "is_private": repo.is_private,
                "is_archived": repo.is_archived,
                "age_days": repo.age_days,
                "days_since_last_push": repo.days_since_last_push,
                "ai_summary": ai_summary_text,
                "attention_score": attention_metrics["score"],
                "attention_metrics": attention_metrics,
                "rank": rank,
                "composite_score": score,
                "pull_request_summary": repo.pull_request_summary.to_dict(),
                "security_summary": repo.security_summary.to_dict(),
                "diagnostics_summary": repo.diagnostics_summary.to_dict(),
            }
            unified_repos.append(repo_dict)

        attention_sorted = sorted(
            unified_repos,
            key=lambda item: item.get("attention_score", 0),
            reverse=True,
        )
        for attention_rank, repo_dict in enumerate(attention_sorted, 1):
            repo_dict["attention_rank"] = attention_rank

        # Build activity_calendar (T002): aggregate daily_commits across all repos
        # Primary source: daily_commits captured from commit_counts cache during the assembly loop above
        # Fallback source: per-commit dates from commits_stats cache (sparse, only fetched when present)
        activity_calendar: Dict[str, int] = {}
        for repo_name, daily in repo_daily_commits.items():
            for day_key, count in daily.items():
                activity_calendar[day_key] = activity_calendar.get(day_key, 0) + count
        # Also pick up any commits_stats data present in repo_cache (legacy/sparse)
        for repo_name, extras in repo_cache.items():
            for commit in extras.get("commit_stats") or []:
                date_str = commit.get("commit", {}).get("author", {}).get("date")
                if date_str:
                    try:
                        day_key = date_str[:10]  # "YYYY-MM-DD"
                        activity_calendar[day_key] = (
                            activity_calendar.get(day_key, 0) + 1
                        )
                    except Exception:
                        pass

        # Derive weekly_activity (T003) from activity_calendar for trailing 52 weeks
        weekly_activity = self._derive_weekly_activity(activity_calendar)

        # Create user profile
        profile = {
            "username": self.username,
            "total_repositories": len(repositories),
            "total_stars": sum(r.stars for r in repositories),
            "total_forks": sum(r.forks for r in repositories),
            "total_commits": sum(ch.total_commits for ch in commit_histories.values()),
            "activity_calendar": activity_calendar,
            "weekly_activity": weekly_activity,
        }

        # Create metadata
        metadata = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "2.3.0",
            "generator": "unified_data_generator",
            "schema_features": [
                "attention_metrics",
                "dependency_version_coverage",
                "activity_calendar",
            ],
            "attention_formula_version": "1.0",
        }

        return {"profile": profile, "repositories": unified_repos, "metadata": metadata}

    def save(self, unified_data: Optional[Dict[str, Any]] = None) -> tuple[Path, bool]:
        """Generate and save unified data to repositories.json file.

        Phase 4: Output generation (no cache operations).

        Args:
            unified_data: Optional pre-generated data dict.
                         If None, will call generate().

        Returns:
            Tuple of (Path to saved JSON file, generation skipped flag)
        """
        if unified_data is None:
            unified_data = self.generate()

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write JSON file
        output_path = self.output_dir / "repositories.json"
        logger.info(f"Writing unified data to {output_path}...")

        try:
            import json

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(unified_data, f, indent=2, ensure_ascii=False)

            file_size = output_path.stat().st_size
            file_size_kb = file_size / 1024
            logger.info(f"Unified data written successfully ({file_size_kb:.2f} KB)")

            return output_path, False

        except Exception as e:
            logger.error(f"Failed to write unified data: {e}")
            raise
