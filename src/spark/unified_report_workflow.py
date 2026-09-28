"""Unified report workflow orchestration.

# SIZE JUSTIFICATION (Constitution I — ~694 LOC as of 2026-04-02):
# This module is the top-level pipeline orchestrator: it coordinates the
# fetcher, cache manager, data generator, SVG visualizer, and report
# generator with partial-failure isolation and structured logging.  Keeping
# all orchestration in one place minimises cross-cutting concerns (retry
# policy, progress reporting, error context) and makes end-to-end tracing
# straightforward for GitHub Actions debugging (§III Fail Fast, Fail Loud).
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from github import RateLimitExceededException

from spark.config import SparkConfig
from spark.fetcher import GitHubFetcher
from spark.calculator import StatsCalculator
from spark.visualizer import StatisticsVisualizer
from spark.ranker import RepositoryRanker
from spark.summarizer import RepositorySummarizer
from spark.cache import APICache
from spark.models.summary import RepositorySummary
from spark.time_utils import sanitize_timestamp_for_filename
from spark.dependencies.analyzer import RepositoryDependencyAnalyzer
from spark.models import (
    UnifiedReport,
    GitHubData,
    RepositoryAnalysis,
    UserProfile,
    Repository,
    CommitHistory,
)
from spark.exceptions import WorkflowError
from spark.logger import get_logger
from spark.visualizer import get_theme


class UnifiedReportWorkflow:
    """Orchestrates unified report generation with partial failure handling.

    This workflow combines SVG visualization generation with repository analysis
    into a single unified profile report, handling partial failures gracefully.

    Workflow stages:
        1. Fetch GitHub data (required - fails entire workflow if unsuccessful)
        2. Generate SVGs (optional - continues with warnings if fails)
        3. Analyze repositories (optional - continues with warnings if fails)
        4. Generate unified report (required - uses available data)
    """

    def __init__(
        self,
        config: SparkConfig,
        cache: Optional[APICache] = None,
        output_dir: str = "output",
        cache_only: bool = True,
    ):
        """Initialize unified report workflow.

        Args:
            config: Spark configuration instance
            cache: API cache instance (creates new if not provided)
            output_dir: Base output directory for SVGs and reports
        """
        self.logger = get_logger()
        self.config = config
        self.cache = cache or APICache()
        self.output_dir = Path(output_dir)
        self.cache_only = cache_only
        self.runtime_budget_seconds = 300

        # Initialize components
        api_version_config = self.config.get_github_api_version_config()
        self.fetcher = GitHubFetcher(
            cache=self.cache,
            api_version_settings=api_version_config,
        )
        self.theme = self._resolve_theme()
        self.visualizer = self._create_visualizer()
        self.ranker, self.summarizer, self.dependency_analyzer = (
            self._create_analysis_components()
        )

        # Track errors and warnings
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.start_time: float = 0.0
        self.api_calls: int = 0

        # Read max_repositories from config (single source of truth — no fallback)
        self.max_repos = self.config.require(
            "dashboard.data_generation.max_repositories"
        )

        self.logger.info(
            "GitHub REST API version staging: "
            f"enabled={api_version_config.get('enabled')} "
            f"target={api_version_config.get('version')} "
            f"fallback_to_default={api_version_config.get('fallback_to_default')}"
        )

    def _resolve_theme(self):
        """Resolve the configured theme using shared validation rules."""
        return get_theme(self.config.get_theme(), self.config.themes_config)

    def _create_visualizer(self) -> StatisticsVisualizer:
        """Create the SVG visualizer for the resolved theme."""
        return StatisticsVisualizer(self.theme, enable_effects=True)

    def _create_analysis_components(self):
        """Create workflow collaborators used during ranking and summarization."""
        ranker = RepositoryRanker(config=self.config.get_ranking_weights())
        summarizer = RepositorySummarizer(
            cache=self.cache,
            enable_ai=False,
            model=self.config.get_ai_model(),
        )
        dependency_analyzer = RepositoryDependencyAnalyzer()
        return ranker, summarizer, dependency_analyzer

    def execute(self, username: str, repository: Optional[str] = None) -> UnifiedReport:
        """Execute unified report workflow with partial failure handling.

        Args:
            username: GitHub username to analyze
            repository: Optional single repository to run for

        Returns:
            UnifiedReport with generated content and error metadata

        Raises:
            WorkflowError: If critical stages fail (data fetching, report generation)
        """
        self.start_time = time.time()
        self.logger.info(f"Starting unified report workflow for {username}")
        if repository:
            self.logger.info(f"Running in single-repository mode for: {repository}")

        # Stage 1: Fetch GitHub data (REQUIRED)
        try:
            if repository:
                github_data = self._fetch_github_data(username, repository)
            else:
                github_data = self._fetch_github_data(username)
        except Exception as e:
            self.logger.error(f"Failed to fetch GitHub data: {e}")
            raise WorkflowError(
                "Cannot proceed without GitHub data", stage="fetch_github_data", cause=e
            ) from e

        # Stage 1b: Cache garbage collection — remove orphaned entries
        if not repository:  # Skip GC in single-repo mode
            try:
                active_names = [r.name for r in github_data.repositories]
                gc_result = self.cache.collect_garbage(username, active_names)
                if gc_result["removed_repos"]:
                    self.logger.info(
                        f"Cache GC removed {len(gc_result['removed_repos'])} orphaned repos: "
                        f"{', '.join(gc_result['removed_repos'])}"
                    )
                # Clean orphaned screenshot files
                screenshots_dir = self.output_dir / "screenshots"
                if screenshots_dir.exists():
                    active_set = set(active_names)
                    for png in screenshots_dir.glob("*.png"):
                        repo_name = png.stem
                        if repo_name not in active_set:
                            png.unlink()
                            self.logger.info(
                                f"Cache GC: removed orphaned screenshot '{png.name}'"
                            )
            except Exception as e:
                self.logger.warning(f"Cache garbage collection failed (non-fatal): {e}")

        # Stage 2: Generate SVGs (OPTIONAL - FR-011)
        available_svgs = []
        try:
            available_svgs = self._generate_svgs(username, github_data)
        except Exception as e:
            self.logger.warning(f"SVG generation failed: {e}")
            self.warnings.append(f"SVG generation failed: {str(e)}")
            # Continue workflow - report will note missing visualizations

        # Stage 3: Analyze repositories (OPTIONAL - FR-012)
        repository_analyses = []
        try:
            repository_analyses = self._analyze_repositories(
                username, github_data.repositories, github_data.commit_histories
            )
        except Exception as e:
            self.logger.warning(f"Repository analysis failed: {e}")
            self.warnings.append(f"Repository analysis failed: {str(e)}")
            # Continue workflow - report will show available data only

        # Stage 4: Generate unified report (REQUIRED)
        report = self._generate_unified_report(
            username=username,
            github_data=github_data,
            available_svgs=available_svgs,
            repository_analyses=repository_analyses,
            single_repository_mode=bool(repository),
        )

        generation_time = time.time() - self.start_time
        if generation_time > self.runtime_budget_seconds:
            over_budget_by = generation_time - self.runtime_budget_seconds
            warning = (
                f"Runtime budget exceeded by {over_budget_by:.1f}s. "
                "Mitigation: reduce max repos or run with warmed cache/without force refresh."
            )
            self.warnings.append(warning)
            self.logger.warning(warning)
        report.generation_time = generation_time
        report.errors = self.errors
        report.warnings = self.warnings

        self.logger.info(
            f"Unified report workflow completed in {generation_time:.1f}s "
            f"(success rate: {report.success_rate}%)"
        )

        return report

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RateLimitExceededException),
    )
    def _fetch_github_data(
        self, username: str, repository: Optional[str] = None
    ) -> GitHubData:
        """Fetch all required data from GitHub API with retries.

        Args:
            username: GitHub username
            repository: Optional single repository to fetch

        Returns:
            GitHubData object with profile, repositories, and commits
        """
        self.logger.info("Fetching GitHub data...")

        cache_hits = 0

        profile_data = self.cache.get("user_profile", username)
        if profile_data:
            cache_hits += 1
        else:
            profile_fetch = getattr(
                self.fetcher,
                "get_user_profile",
                getattr(self.fetcher, "fetch_user_profile", None),
            )
            if profile_fetch is None:
                raise AttributeError("Fetcher does not support user profile retrieval")
            profile_data = profile_fetch(username)
            self.api_calls += getattr(self.fetcher, "api_calls", 0)

        exclude_private = self.config.get("repositories.exclude_private", True)
        exclude_forks = self.config.get("repositories.exclude_forks", True)
        exclude_archived = self.config.get("repositories.exclude_archived", True)
        repo_variant = f"list_{exclude_private}_{exclude_forks}_{exclude_archived}"
        if repository:
            repos_data = self.cache.get("repositories", username, repo=repo_variant)
            if repos_data:
                cache_hits += 1
            else:
                repositories_fetch = getattr(
                    self.fetcher,
                    "get_repositories",
                    getattr(self.fetcher, "fetch_repositories", None),
                )
                if repositories_fetch is None:
                    raise AttributeError(
                        "Fetcher does not support repository retrieval"
                    )
                repos_data = repositories_fetch(
                    username,
                    exclude_private=exclude_private,
                    exclude_forks=exclude_forks,
                    exclude_archived=exclude_archived,
                )
                self.api_calls += getattr(self.fetcher, "api_calls", 0)
            repos_data = [repo for repo in repos_data if repo.get("name") == repository]
        else:
            repos_data = self.cache.get("repositories", username, repo=repo_variant)
            if repos_data:
                cache_hits += 1
            else:
                repositories_fetch = getattr(
                    self.fetcher,
                    "get_repositories",
                    getattr(self.fetcher, "fetch_repositories", None),
                )
                if repositories_fetch is None:
                    raise AttributeError(
                        "Fetcher does not support repository retrieval"
                    )
                repos_data = repositories_fetch(
                    username,
                    exclude_private=exclude_private,
                    exclude_forks=exclude_forks,
                    exclude_archived=exclude_archived,
                )
                self.api_calls += getattr(self.fetcher, "api_calls", 0)
            repos_data = repos_data[: self.max_repos]

        # Filter out private repositories (Constitutional Requirement)
        public_repos_data = [r for r in repos_data if not r.get("is_private")]
        if len(repos_data) != len(public_repos_data):
            private_count = len(repos_data) - len(public_repos_data)
            self.logger.info(f"Filtered out {private_count} private repositories")

        # Fetch commit history for each public repository
        commit_histories = {}
        for repo in public_repos_data:
            repo_name = repo["name"]
            try:
                cache_key = sanitize_timestamp_for_filename(repo.get("pushed_at"))
                commit_counts = self.cache.get(
                    "commit_counts",
                    username,
                    repo=repo_name,
                    week=cache_key,
                )
                if commit_counts:
                    cache_hits += 1
                else:
                    commit_fetch = getattr(
                        self.fetcher,
                        "get_commit_history",
                        getattr(self.fetcher, "fetch_commit_counts", None),
                    )
                    if commit_fetch is None:
                        raise AttributeError(
                            "Fetcher does not support commit history retrieval"
                        )
                    commit_counts = commit_fetch(
                        username,
                        repo_name,
                        repo_pushed_at=repo.get("pushed_at"),
                    )
                    self.api_calls += getattr(self.fetcher, "api_calls", 0)
                commit_counts = {**commit_counts, "repository_name": repo_name}
                commit_histories[repo_name] = CommitHistory.from_dict(commit_counts)
            except Exception as e:
                self.logger.warning(
                    f"Could not fetch commit history for {repo_name}: {e}"
                )
                commit_histories[repo_name] = CommitHistory(repository_name=repo_name)

        return GitHubData(
            username=username,
            profile=UserProfile.from_dict(profile_data),
            repositories=[Repository.from_dict(r) for r in public_repos_data],
            commit_histories=commit_histories,
            fetch_timestamp=datetime.now(timezone.utc),
            api_call_count=self.api_calls,
            cache_hit_count=cache_hits,
        )

    def _log_enrichment_availability(self, repos_data: List[Dict[str, Any]]) -> None:
        """Log compact availability counters for enrichment status visibility."""
        if not repos_data:
            return

        pr_partial = 0
        pr_unavailable = 0
        sec_partial = 0
        sec_unavailable = 0
        diag_partial = 0
        diag_unavailable = 0

        for repo in repos_data:
            pr = repo.get("pull_request_summary") or {}
            sec = repo.get("security_summary") or {}
            diag = repo.get("diagnostics_summary") or {}

            pr_availability = pr.get("availability")
            sec_availability = sec.get("availability")
            diag_availability = diag.get("availability")

            if pr_availability == "partial":
                pr_partial += 1
            elif pr_availability == "unavailable":
                pr_unavailable += 1

            if sec_availability == "partial":
                sec_partial += 1
            elif sec_availability == "unavailable":
                sec_unavailable += 1

            if diag_availability == "partial":
                diag_partial += 1
            elif diag_availability == "unavailable":
                diag_unavailable += 1

        if any(
            [
                pr_partial,
                pr_unavailable,
                sec_partial,
                sec_unavailable,
                diag_partial,
                diag_unavailable,
            ]
        ):
            self.logger.warning(
                "Repository enrichment availability summary: "
                f"pr_partial={pr_partial} "
                f"pr_unavailable={pr_unavailable} "
                f"security_partial={sec_partial} "
                f"security_unavailable={sec_unavailable} "
                f"diagnostics_partial={diag_partial} "
                f"diagnostics_unavailable={diag_unavailable}"
            )

    def _generate_svgs(self, username: str, github_data: GitHubData) -> List[str]:
        """Generate SVG visualizations (FR-011: continue if fails).

        Args:
            username: GitHub username
            github_data: Fetched GitHub data

        Returns:
            List of successfully generated SVG types (ordered per FR-017)
        """
        self.logger.info("[generate_svgs] Generating SVG visualizations")
        available_svgs = []

        # FR-017 ordering
        svg_types = ["overview", "heatmap", "streaks", "release", "languages", "fun"]
        enabled_stats = self.config.get_enabled_stats()

        # Initialize calculator with fetched data
        profile_dict = github_data.profile.to_dict() if github_data.profile else {}
        repos_dict = []
        for repo in github_data.repositories:
            repo_dict = repo.to_dict()
            commit_history = github_data.commit_histories.get(repo.name)
            if commit_history:
                repo_dict["commit_history"] = commit_history.to_dict()
                if commit_history.last_commit_date:
                    repo_dict["last_commit_date"] = (
                        commit_history.last_commit_date.isoformat()
                    )
            repos_dict.append(repo_dict)
        calculator = StatsCalculator(
            profile_dict,
            repos_dict,
            thresholds=self.config.require("stats.thresholds"),
        )

        # Pre-fetch data for all repositories once
        self.logger.info(
            f"[generate_svgs] Pre-fetching detailed stats for {len(github_data.repositories)} repositories"
        )

        for repo in github_data.repositories:
            try:
                cache_key = sanitize_timestamp_for_filename(repo.pushed_at)

                # Read actual commits from cache only (needed for heatmaps, time patterns, etc.)
                commits = self.cache.get(
                    "commits",
                    username,
                    repo=repo.name,
                    week=cache_key,
                )
                if commits:
                    calculator.add_commits(commits)
                else:
                    commit_stats = self.cache.get(
                        "commits_stats",
                        username,
                        repo=repo.name,
                        week=cache_key,
                    )
                    if commit_stats:
                        calculator.add_commits(commit_stats)

                # Read language statistics from cache only
                languages = self.cache.get(
                    "languages",
                    username,
                    repo=repo.name,
                    week=cache_key,
                )
                if languages:
                    calculator.add_languages(languages)

            except Exception as e:
                self.logger.debug(
                    f"Could not fetch detailed stats for {repo.name}: {e}"
                )

        # Calculate statistics once
        stats = calculator.calculate_statistics()

        for svg_type in svg_types:
            if svg_type not in enabled_stats:
                self.logger.debug(f"Skipping disabled SVG: {svg_type}")
                continue

            try:
                svg_content = self._generate_single_svg(svg_type, username, stats)
                svg_path = self.output_dir / f"{svg_type}.svg"
                svg_path.parent.mkdir(parents=True, exist_ok=True)

                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(svg_content)

                available_svgs.append(svg_type)
                self.logger.info(f"Generated {svg_type}.svg")

            except Exception as e:
                self.logger.warning(f"Failed to generate {svg_type}.svg: {e}")
                self.warnings.append(f"SVG generation failed: {svg_type}")
                # Continue to next SVG (FR-011: partial failures OK)

        self.logger.info(
            f"[generate_svgs] Generated {len(available_svgs)}/{len(svg_types)} SVGs"
        )
        return available_svgs

    def _generate_single_svg(
        self, svg_type: str, username: str, stats: Dict[str, Any]
    ) -> str:
        """Generate a single SVG visualization.

        Args:
            svg_type: Type of SVG to generate
            username: GitHub username
            stats: Calculated statistics dictionary

        Returns:
            SVG content as string

        Raises:
            Exception: If SVG generation fails
        """
        # Generate appropriate SVG based on type
        if svg_type == "overview":
            return self.visualizer.generate_overview(
                username=username,
                spark_score=stats.get("spark_score", {}),
                total_commits=stats.get("total_commits", 0),
                languages=stats.get("languages", []),
                time_pattern=stats.get("time_pattern", {}),
            )
        elif svg_type == "heatmap":
            return self.visualizer.generate_heatmap(
                commits_by_date=stats.get("commits_by_day", {}),
                username=username,
            )
        elif svg_type == "streaks":
            return self.visualizer.generate_streaks(
                streaks=stats.get("streaks", {}),
                username=username,
            )
        elif svg_type == "release":
            return self.visualizer.generate_release_cadence(
                cadence=stats.get("release_cadence", {}),
                username=username,
            )
        elif svg_type == "languages":
            return self.visualizer.generate_languages(
                languages=stats.get("languages", []),
                username=username,
            )
        elif svg_type == "fun":
            return self.visualizer.generate_fun_stats(
                stats=stats.get("fun_stats", {}),
                username=username,
            )
        else:
            raise ValueError(f"Unknown SVG type: {svg_type}")

    def _analyze_repositories(
        self,
        username: str,
        repositories: List[Repository],
        commit_histories: Dict[str, CommitHistory],
    ) -> List[RepositoryAnalysis]:
        """Analyze repositories (FR-012: individual repo failures don't block report).

        Args:
            username: GitHub username
            repositories: List of repositories to analyze
            commit_histories: Commit data by repository name

        Returns:
            List of RepositoryAnalysis objects (top 50, ranked by composite score)
        """
        self.logger.info(
            f"[analyze_repositories] Analyzing {len(repositories)} repositories"
        )
        analyses = []

        # Rank repositories
        top_n = self.config.get("analyzer.top_repositories", 50)
        ranked = self.ranker.rank_repositories(
            repositories, commit_histories, top_n=top_n
        )

        for rank, (repo, score) in enumerate(ranked, 1):
            try:
                cache_key = sanitize_timestamp_for_filename(repo.pushed_at)

                # Read README from cache only
                readme_content = self.cache.get(
                    "readme",
                    username,
                    repo=repo.name,
                    week=cache_key,
                )

                # Read language statistics from cache only
                language_stats = self.cache.get(
                    "languages",
                    username,
                    repo=repo.name,
                    week=cache_key,
                )

                # Update repository with language stats
                if language_stats:
                    repo.language_stats = language_stats
                    repo.language_count = len(language_stats)

                # Analyze dependencies and tech stack (before summary)
                tech_stack = None
                try:
                    # Read dependency files from cache only
                    dependency_files = self.cache.get(
                        "dependency_files",
                        username,
                        repo=repo.name,
                        week=cache_key,
                    )

                    if dependency_files:
                        # Analyze dependencies if files were found
                        dep_report = self.dependency_analyzer.analyze_repository(
                            dependency_files
                        )

                        # Convert to TechnologyStack model (if needed)
                        tech_stack = self.dependency_analyzer.build_technology_stack(
                            repository_name=repo.name,
                            report=dep_report,
                        )
                except Exception as e:
                    self.logger.debug(
                        f"Dependency analysis skipped for {repo.name}: {e}"
                    )

                # Use cached AI summary if available; otherwise fallback without AI
                cached_summary = self.cache.get(
                    "ai_summary",
                    username,
                    repo=repo.name,
                    week=cache_key,
                )
                if cached_summary:
                    summary = RepositorySummary(
                        repo_id=repo.name,
                        ai_summary=cached_summary.get("ai_summary"),
                        generation_method=cached_summary.get(
                            "generation_method", "cached"
                        ),
                        generation_timestamp=(
                            datetime.fromisoformat(
                                cached_summary["generation_timestamp"]
                            )
                            if cached_summary.get("generation_timestamp")
                            else None
                        ),
                        model_used=cached_summary.get("model_used"),
                        tokens_used=cached_summary.get("tokens_used", 0),
                        confidence_score=cached_summary.get("confidence_score", 0),
                    )
                else:
                    summary = self.summarizer.summarize_repository(
                        repo=repo,
                        readme_content=readme_content,
                        commit_history=commit_histories.get(repo.name),
                        language_stats=language_stats,
                        tech_stack=tech_stack,
                        repository_owner=username,
                        repo_pushed_at=repo.pushed_at,
                        write_cache=False,
                        allow_ai=False,
                    )

                analysis = RepositoryAnalysis(
                    repository=repo,
                    commit_history=commit_histories.get(repo.name),
                    summary=summary,
                    tech_stack=tech_stack,
                    rank=rank,
                    composite_score=score,
                )
                analyses.append(analysis)

            except Exception as e:
                self.logger.warning(f"Failed to analyze {repo.name}: {e}")
                self.errors.append(f"Repository analysis failed: {repo.name}")
                # Continue to next repository (FR-012: partial results OK)

        self.logger.info(
            f"[analyze_repositories] Successfully analyzed {len(analyses)}/{len(ranked)} repositories"
        )
        return analyses

    def _generate_unified_report(
        self,
        username: str,
        github_data: GitHubData,
        available_svgs: List[str],
        repository_analyses: List[RepositoryAnalysis],
        single_repository_mode: bool = False,
    ) -> UnifiedReport:
        """Generate the final unified report object."""
        self.logger.info("Generating unified report...")

        report = UnifiedReport(
            username=username,
            timestamp=datetime.now(timezone.utc),
            repositories=repository_analyses,
            available_svgs=available_svgs,
            total_api_calls=github_data.api_call_count,
            total_ai_tokens=sum(
                a.summary.tokens_used if a.summary else 0 for a in repository_analyses
            ),
            ai_model=RepositorySummarizer.DEFAULT_MODEL,
            errors=list(self.errors),
            warnings=list(self.warnings),
        )

        # Validate report structure
        validation_errors = report.validate()
        if validation_errors:
            self.logger.warning(
                f"Report validation warnings: {', '.join(validation_errors)}"
            )
            self.warnings.extend(validation_errors)
            report.warnings.extend(validation_errors)

        return report
