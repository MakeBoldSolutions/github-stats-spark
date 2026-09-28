"""Dashboard data generator for repository comparison dashboard.

This module generates JSON data files for the GitHub Stats Spark interactive
dashboard. It fetches repository data, calculates commit metrics, and exports
structured JSON for frontend consumption.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
import os

from spark.fetcher import GitHubFetcher
from spark.calculator import StatsCalculator
from spark.models.dashboard_data import (
    DashboardData,
    DashboardRepository,
    DashboardMetadata,
    UserProfile,
    CommitMetric,
)
from spark.config import SparkConfig

logger = logging.getLogger(__name__)


class DashboardGenerator:
    """Generates dashboard JSON data from GitHub repository analysis.

    This class coordinates the data collection, metric calculation, and JSON
    export process for the repository comparison dashboard.

    Attributes:
        config: Configuration object with dashboard settings
        fetcher: GitHub API data fetcher
        calculator: Metrics calculator for commit analysis
        output_dir: Directory path for JSON output files
    """

    def __init__(self, config: SparkConfig, username: str):
        """Initialize the DashboardGenerator.

        Args:
            config: SparkConfig instance (all values read from spark.yml)
            username: GitHub username to analyze
        """
        self.config = config
        self.username = username

        # Initialize fetcher with token from environment
        token = os.getenv("GITHUB_TOKEN")
        max_repos = config.require("dashboard.data_generation.max_repositories")

        self.fetcher = GitHubFetcher(token=token, max_repos=max_repos)

        # Get dashboard configuration (all required — raise if missing)
        self.output_dir = Path(config.require("dashboard.output_dir"))
        self.data_dir = self.output_dir

        # Dashboard feature flags
        self.enabled = config.require("dashboard.enabled")
        self.include_commit_metrics = config.require(
            "dashboard.data_generation.include_commit_metrics"
        )
        self.include_language_stats = config.require(
            "dashboard.data_generation.include_language_stats"
        )
        self.include_ai_summaries = config.require(
            "dashboard.data_generation.include_ai_summaries"
        )
        self.max_repositories = max_repos

        logger.info(
            f"DashboardGenerator initialized (output: {self.data_dir}, "
            f"max_repos: {self.max_repositories})"
        )

    def generate(self) -> DashboardData:
        """Generate complete dashboard data.

        This is the main entry point for dashboard data generation. It orchestrates
        the entire process: fetch repositories, calculate metrics, build data structure.

        Returns:
            DashboardData object containing all dashboard information

        Raises:
            Exception: If dashboard generation is disabled or fails
        """
        if not self.enabled:
            logger.warning("Dashboard generation is disabled in configuration")
            raise ValueError("Dashboard generation is disabled in config")

        logger.info("Starting dashboard data generation...")

        # Fetch repository data
        repositories = self.generate_dashboard_data()

        # Fetch user profile
        profile = self.generate_user_profile(repositories)

        # Create metadata
        metadata = DashboardMetadata(
            generated_at=datetime.now(),
            schema_version="1.0.0",
            repository_count=len(repositories),
            data_source="GitHub API",
        )

        # Build dashboard data structure
        dashboard_data = DashboardData(
            repositories=repositories,
            profile=profile,
            metadata=metadata,
        )

        logger.info(
            f"Dashboard data generation complete: {len(repositories)} repositories"
        )
        return dashboard_data

    def generate_dashboard_data(self) -> List[DashboardRepository]:
        """Fetch all public repositories and prepare dashboard data.

        Returns:
            List of DashboardRepository objects with metrics
        """
        logger.info(f"Fetching repositories for {self.username}...")

        # Fetch all public repositories
        repos_config = self.config.get("repositories", {})
        exclude_forks = repos_config.get("exclude_forks", True)
        exclude_archived = repos_config.get("exclude_archived", True)

        raw_repos = self.fetcher.fetch_repositories(
            username=self.username,
            exclude_private=True,  # Always exclude private per constitution
            exclude_forks=exclude_forks,
            exclude_archived=exclude_archived,
        )

        logger.info(f"Found {len(raw_repos)} repositories")

        # Apply max_repositories limit
        if len(raw_repos) > self.max_repositories:
            logger.warning(
                f"Limiting to {self.max_repositories} repositories (found {len(raw_repos)})"
            )
            raw_repos = raw_repos[: self.max_repositories]

        # Convert to DashboardRepository objects with metrics
        dashboard_repos = []
        for i, repo_data in enumerate(raw_repos, 1):
            repo_name = repo_data.get("name", "unknown")
            logger.info(f"Processing repository {i}/{len(raw_repos)}: {repo_name}")

            try:
                # Calculate commit metrics for this repository
                commit_metrics = self.calculate_commit_metrics(
                    repo_name, pushed_at=repo_data.get("pushed_at")
                )

                # Extract dates
                created_at = repo_data.get("created_at")
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )

                updated_at = repo_data.get("updated_at")
                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(
                        updated_at.replace("Z", "+00:00")
                    )

                pushed_at = repo_data.get("pushed_at")
                if isinstance(pushed_at, str):
                    pushed_at = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))

                # Build DashboardRepository
                dashboard_repo = DashboardRepository(
                    name=repo_name,
                    language=repo_data.get("language") or "Unknown",
                    created_at=created_at,
                    last_commit_date=pushed_at or updated_at,
                    first_commit_date=commit_metrics.get("first_commit_date"),
                    commit_count=commit_metrics.get("total_commits", 0),
                    avg_commit_size=commit_metrics.get("avg_commit_size", 0.0),
                    largest_commit=commit_metrics.get("largest_commit"),
                    smallest_commit=commit_metrics.get("smallest_commit"),
                    stars=repo_data.get("stargazers_count", 0),
                    forks=repo_data.get("forks_count", 0),
                    url=repo_data.get("html_url", ""),
                    description=repo_data.get("description"),
                    updated_at=updated_at,
                )
                dashboard_repos.append(dashboard_repo)

            except Exception as e:
                logger.error(f"Failed to process repository {repo_name}: {e}")
                continue

        return dashboard_repos

    def calculate_commit_metrics(
        self, repo_name: str, pushed_at: Optional[str] = None
    ) -> Dict:
        """Calculate commit size metrics for a repository.

        Fetches commits with detailed statistics and calculates aggregate metrics
        including average commit size, largest commit, and smallest commit.

        Args:
            repo_name: Repository name
            pushed_at: Last push date (ISO format string, for cache invalidation)

        Returns:
            Dictionary containing:
            - first_commit_date: Date of first commit (datetime or None)
            - total_commits: Total number of commits analyzed
            - avg_commit_size: Average commit size (files + lines changed)
            - largest_commit: CommitMetric for largest commit
            - smallest_commit: CommitMetric for smallest commit
        """
        logger.debug(f"Calculating commit metrics for {repo_name}...")

        # Parse pushed_at for cache management
        repo_pushed_at = None
        if pushed_at:
            try:
                repo_pushed_at = datetime.fromisoformat(
                    pushed_at.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Fetch commits with detailed stats
        max_commits = (
            self.config.get("dashboard", {})
            .get("data_generation", {})
            .get("max_commits_per_repo", 200)
        )
        commits_with_stats = self.fetcher.fetch_commits_with_stats(
            username=self.username,
            repo_name=repo_name,
            max_commits=max_commits,
            repo_pushed_at=repo_pushed_at,
        )

        if not commits_with_stats:
            logger.warning(f"No commits found for {repo_name}")
            return {
                "first_commit_date": None,
                "total_commits": 0,
                "avg_commit_size": 0.0,
                "largest_commit": None,
                "smallest_commit": None,
            }

        # Use StatsCalculator to calculate repository metrics
        metrics = StatsCalculator.calculate_repository_commit_metrics(
            commits_with_stats
        )

        # Extract first commit date
        first_commit_date = None
        if commits_with_stats:
            # Commits are in reverse chronological order, so last commit is first
            first_commit = commits_with_stats[-1]
            date_str = first_commit.get("commit", {}).get("author", {}).get("date")
            if date_str:
                try:
                    first_commit_date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError) as e:
                    logger.warning(
                        f"Failed to parse first commit date for {repo_name}: {e}"
                    )

        # Convert largest/smallest to CommitMetric objects
        largest_commit = None
        if metrics.get("largest_commit"):
            largest = metrics["largest_commit"]
            largest_commit = CommitMetric(
                sha=largest["sha"],
                date=(
                    datetime.fromisoformat(largest["date"].replace("Z", "+00:00"))
                    if largest.get("date")
                    else None
                ),
                size=largest["size"],
                files_changed=largest.get("files_changed", 0),
                lines_added=largest.get("lines_added", 0),
                lines_deleted=largest.get("lines_deleted", 0),
            )

        smallest_commit = None
        if metrics.get("smallest_commit"):
            smallest = metrics["smallest_commit"]
            smallest_commit = CommitMetric(
                sha=smallest["sha"],
                date=(
                    datetime.fromisoformat(smallest["date"].replace("Z", "+00:00"))
                    if smallest.get("date")
                    else None
                ),
                size=smallest["size"],
                files_changed=smallest.get("files_changed", 0),
                lines_added=smallest.get("lines_added", 0),
                lines_deleted=smallest.get("lines_deleted", 0),
            )

        return {
            "first_commit_date": first_commit_date,
            "total_commits": metrics["total_commits"],
            "avg_commit_size": metrics["avg_commit_size"],
            "largest_commit": largest_commit,
            "smallest_commit": smallest_commit,
        }

    def generate_user_profile(
        self, repositories: Optional[List[DashboardRepository]] = None
    ) -> UserProfile:
        """Generate user profile information for dashboard header.

        Returns:
            UserProfile object with user statistics

        Note:
            Uses fetcher to get user data from GitHub API
        """
        logger.info("Generating user profile...")
        user_data = self.fetcher.get_user()

        repositories = repositories or []
        total_stars = sum(repo.stars for repo in repositories)
        total_forks = sum(repo.forks for repo in repositories)
        total_commits = sum(repo.commit_count for repo in repositories)

        return UserProfile(
            username=user_data.get("login", "unknown"),
            avatar_url=user_data.get("avatar_url", ""),
            public_repos_count=user_data.get("public_repos", 0),
            profile_url=user_data.get("html_url", ""),
            total_commits=total_commits,
            total_stars=total_stars,
            total_forks=total_forks,
        )

    def write_json_output(
        self, dashboard_data: DashboardData, filename: str = "repositories.json"
    ) -> Path:
        """Write dashboard data to JSON file.

        This method ensures the output directory exists and writes the dashboard
        data to a JSON file with proper formatting.

        Args:
            dashboard_data: DashboardData object to serialize
            filename: Output filename (default: repositories.json)

        Returns:
            Path to written JSON file
        """
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Output directory ensured: {self.data_dir}")

        # Build output file path
        output_path = self.data_dir / filename
        logger.info(f"Writing dashboard data to {output_path}...")

        try:
            # Use the model's built-in save_to_file method
            dashboard_data.save_to_file(str(output_path), indent=2)

            # Log file size
            file_size = output_path.stat().st_size
            file_size_kb = file_size / 1024
            logger.info(f"Dashboard data written successfully ({file_size_kb:.2f} KB)")

            return output_path

        except Exception as e:
            logger.error(f"Failed to write dashboard data to {output_path}: {e}")
            raise

    def save(self, dashboard_data: Optional[DashboardData] = None) -> Path:
        """Generate and save dashboard data to JSON file.

        Args:
            dashboard_data: Optional pre-generated dashboard data.
                           If None, will generate new data.

        Returns:
            Path to saved JSON file
        """
        if dashboard_data is None:
            dashboard_data = self.generate()

        output_path = self.write_json_output(dashboard_data)
        logger.info(f"Dashboard data saved successfully to {output_path}")
        return output_path
