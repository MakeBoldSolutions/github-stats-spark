"""Repository ranking algorithm with composite scoring.

This module implements the ranking algorithm specified in research.md:
- Composite Score = 30% Popularity + 45% Activity + 25% Health
- Logarithmic scaling for popularity to prevent mega-repo dominance
- Multi-window time decay for activity (90d/180d/365d)
- Edge case handling for archived repos, forks, and empty repos
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from spark.exceptions import ConfigurationError
from spark.models.repository import Repository
from spark.models.commit import CommitHistory
from spark.logger import get_logger


class RepositoryRanker:
    """Ranks repositories using composite scoring algorithm."""

    # Ranking weights (must sum to 1.0)
    WEIGHT_POPULARITY = 0.30
    WEIGHT_ACTIVITY = 0.45
    WEIGHT_HEALTH = 0.25

    # Activity time windows (days)
    WINDOW_90D = 90
    WINDOW_180D = 180
    WINDOW_365D = 365

    # Activity window weights (must sum to 1.0)
    WEIGHT_90D = 0.50
    WEIGHT_180D = 0.30
    WEIGHT_365D = 0.20

    # Recency bonus thresholds (days)
    RECENCY_EXCELLENT = 7
    RECENCY_GOOD = 30
    RECENCY_FAIR = 90

    def __init__(self, config: Optional[Dict] = None):
        """Initialize repository ranker.

        Args:
            config: Ranking weights dict with keys: popularity, activity, health.
                    Must be provided — raises ConfigurationError if missing or incomplete.
        """
        self.logger = get_logger()

        if not config:
            raise ConfigurationError(
                "RepositoryRanker requires ranking weights config "
                "(analyzer.ranking_weights in spark.yml)",
                field="analyzer.ranking_weights",
            )

        # Each weight must be explicitly in config — no silent fallback to class constants
        for key in ("popularity", "activity", "health"):
            if config.get(key) is None:
                raise ConfigurationError(
                    f"Missing required ranking weight 'analyzer.ranking_weights.{key}' in spark.yml",
                    field=f"analyzer.ranking_weights.{key}",
                )

        self.weight_popularity = config["popularity"]
        self.weight_activity = config["activity"]
        self.weight_health = config["health"]

    def rank_repositories(
        self,
        repositories: List[Repository],
        commit_histories: Dict[str, CommitHistory],
        top_n: int = 50,
    ) -> List[Tuple[Repository, float]]:
        """Rank repositories by composite score.

        Args:
            repositories: List of Repository objects
            commit_histories: Map of repo name to CommitHistory
            top_n: Number of top repositories to return

        Returns:
            List of (Repository, score) tuples, sorted by score descending
        """
        self.logger.info(f"Ranking {len(repositories)} repositories")

        scored_repos = []
        for repo in repositories:
            # Skip private repositories (privacy filter - constitution requirement)
            if repo.is_private:
                self.logger.warning(
                    f"Privacy filter: Skipping private repository {repo.name}"
                )
                continue

            # Skip empty repositories
            if repo.is_empty:
                self.logger.debug(f"Skipping empty repository {repo.name}")
                continue

            commit_history = commit_histories.get(repo.name)
            if not commit_history:
                self.logger.debug(
                    f"No commit history for {repo.name}, using zero activity"
                )
                commit_history = CommitHistory(repository_name=repo.name)

            score = self._calculate_composite_score(repo, commit_history)
            scored_repos.append((repo, score))

        # Sort by score descending
        scored_repos.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        top_repos = scored_repos[:top_n]

        if top_repos:
            self.logger.info(
                f"Ranked top {len(top_repos)} repositories "
                f"(scores: {top_repos[0][1]:.1f} to {top_repos[-1][1]:.1f})"
            )
        else:
            self.logger.info("No repositories to rank")

        return top_repos

    def _calculate_composite_score(
        self, repo: Repository, commit_history: CommitHistory
    ) -> float:
        """Calculate composite ranking score for a repository.

        Args:
            repo: Repository object
            commit_history: CommitHistory object

        Returns:
            Composite score (0-100)
        """
        popularity = self._calculate_popularity_score(repo)
        activity = self._calculate_activity_score(repo, commit_history)
        health = self._calculate_health_score(repo, commit_history)

        composite = (
            popularity * self.weight_popularity
            + activity * self.weight_activity
            + health * self.weight_health
        )

        # Apply edge case penalties
        composite = self._apply_edge_case_penalties(
            repo, composite, activity, popularity
        )

        return round(composite, 2)

    def _calculate_popularity_score(self, repo: Repository) -> float:
        """Calculate popularity score using logarithmic scaling.

        Uses log scaling to prevent mega-repos from dominating:
        - 10 stars = ~32 points
        - 100 stars = ~64 points
        - 1000 stars = ~80 points
        - 10000 stars = ~96 points

        Args:
            repo: Repository object

        Returns:
            Popularity score (0-100)
        """
        # Weighted popularity metric
        # Stars are most important, followed by forks, then watchers
        popularity_value = repo.stars * 1.0 + repo.forks * 0.5 + repo.watchers * 0.3

        if popularity_value == 0:
            return 0.0

        # Logarithmic scaling: log10(value + 1) * 32
        # +1 to handle zero case, *32 to scale to 0-100 range
        # log10(10) = 1 → 32, log10(100) = 2 → 64, log10(1000) = 3 → 96
        score = math.log10(popularity_value + 1) * 32

        return min(100.0, score)

    def _calculate_activity_score(
        self, repo: Repository, commit_history: CommitHistory
    ) -> float:
        """Calculate activity score with multi-window time decay.

        Uses three time windows:
        - 90 days (3 months): 50% weight - most recent activity
        - 180 days (6 months): 30% weight - medium-term trends
        - 365 days (1 year): 20% weight - long-term consistency

        Plus recency bonus based on last commit date.

        Args:
            repo: Repository object
            commit_history: CommitHistory object

        Returns:
            Activity score (0-100)
        """
        # Multi-window activity calculation
        activity_rate = (
            (commit_history.recent_90d / 90) * self.WEIGHT_90D
            + (commit_history.recent_180d / 180) * self.WEIGHT_180D
            + (commit_history.recent_365d / 365) * self.WEIGHT_365D
        )

        # Normalize to 0-100 scale (assume 1 commit/day = 100)
        activity_score = min(100.0, activity_rate * 100)

        # Apply recency bonus
        recency_bonus = self._calculate_recency_bonus(repo)
        activity_score = min(100.0, activity_score + recency_bonus)

        return activity_score

    def _calculate_recency_bonus(self, repo: Repository) -> float:
        """Calculate bonus points based on last commit recency.

        Args:
            repo: Repository object

        Returns:
            Bonus points (0-30)
        """
        days_since = repo.days_since_last_push
        if days_since is None:
            return 0.0

        if days_since <= self.RECENCY_EXCELLENT:  # < 7 days
            return 30.0
        elif days_since <= self.RECENCY_GOOD:  # 7-30 days
            return 20.0
        elif days_since <= self.RECENCY_FAIR:  # 30-90 days
            return 10.0
        elif days_since <= 180:
            return 0.0
        elif days_since <= 365:
            return -20.0
        else:
            return -50.0

    def _calculate_health_score(
        self, repo: Repository, commit_history: CommitHistory
    ) -> float:
        """Calculate repository health score.

        Health factors:
        - Documentation (README presence): 30 points
        - Maturity (age and commit count): 30 points
        - Issue management (open issues ratio): 20 points
        - Community (forks/stars ratio): 20 points

        Args:
            repo: Repository object
            commit_history: CommitHistory object

        Returns:
            Health score (0-100)
        """
        health = 0.0

        # Documentation (30 points)
        if repo.has_readme:
            health += 30.0

        # Maturity (30 points)
        # Based on age and total commits
        age_score = min(15.0, repo.age_days / 365 * 5)  # Max 15 points for 3+ years
        commit_score = min(
            15.0, commit_history.total_commits / 100
        )  # Max 15 points for 100+ commits
        health += age_score + commit_score

        # Issue management (20 points)
        # Lower open issues relative to activity = better health
        if commit_history.recent_90d > 0:
            issue_ratio = repo.open_issues / max(1, commit_history.recent_90d)
            issue_score = max(
                0, 20 - issue_ratio * 5
            )  # Penalty for high issue/commit ratio
            health += issue_score
        else:
            # No recent activity but issues present = unhealthy
            health += 10.0 if repo.open_issues == 0 else 0.0

        # Community engagement (20 points)
        # Healthy fork/star ratio indicates community interest
        if repo.stars > 0:
            fork_ratio = repo.forks / repo.stars
            # Ideal ratio is 0.1-0.3 (10-30% fork rate)
            if 0.1 <= fork_ratio <= 0.3:
                health += 20.0
            elif fork_ratio < 0.1:
                health += 10.0
            else:
                health += 15.0
        else:
            health += 5.0 if repo.forks > 0 else 0.0

        return min(100.0, health)

    def _apply_edge_case_penalties(
        self, repo: Repository, composite: float, activity: float, popularity: float
    ) -> float:
        """Apply penalties for edge cases.

        Edge cases:
        - Archived repos: -50% popularity, -90% activity
        - Forks: -70% all scores (unless significant ahead commits)
        - Zero-star active repos: Boost by activity-popularity difference

        Args:
            repo: Repository object
            composite: Current composite score
            activity: Activity score
            popularity: Popularity score

        Returns:
            Adjusted composite score
        """
        # Archived repositories
        if repo.is_archived:
            self.logger.debug(f"Applying archive penalty to {repo.name}")
            # Keep highly starred archives (historical significance)
            if repo.stars < 1000:
                composite *= 0.1  # 90% penalty
            else:
                composite *= 0.5  # 50% penalty for popular archives

        # Forked repositories
        if repo.is_fork and repo.fork_info:
            commits_ahead = repo.fork_info.get("commits_ahead", 0)
            commits_behind = repo.fork_info.get("commits_behind", 0)

            # Significant ahead commits = active fork development
            if commits_ahead > 10 and commits_ahead > commits_behind:
                # Reduce penalty for active forks
                composite *= 0.7
            else:
                # Heavy penalty for inactive forks
                composite *= 0.3

        # Zero-star but active repositories (new projects)
        if repo.stars == 0 and activity > 70:
            # Boost score by activity-popularity difference
            boost = (activity - popularity) * 0.3
            composite += boost
            self.logger.debug(f"Applying activity boost to {repo.name}: +{boost:.1f}")

        return max(0.0, composite)

    def get_ranking_breakdown(
        self, repo: Repository, commit_history: CommitHistory
    ) -> Dict[str, Any]:
        """Get detailed scoring breakdown for a repository.

        Useful for debugging and transparency.

        Args:
            repo: Repository object
            commit_history: CommitHistory object

        Returns:
            Dictionary with score components
        """
        popularity = self._calculate_popularity_score(repo)
        activity = self._calculate_activity_score(repo, commit_history)
        health = self._calculate_health_score(repo, commit_history)
        composite = self._calculate_composite_score(repo, commit_history)

        return {
            "repository": repo.name,
            "composite_score": composite,
            "popularity_score": popularity,
            "activity_score": activity,
            "health_score": health,
            "popularity_weight": self.weight_popularity,
            "activity_weight": self.weight_activity,
            "health_weight": self.weight_health,
            "weighted_popularity": popularity * self.weight_popularity,
            "weighted_activity": activity * self.weight_activity,
            "weighted_health": health * self.weight_health,
            "is_archived": repo.is_archived,
            "is_fork": repo.is_fork,
            "stars": repo.stars,
            "recent_90d_commits": commit_history.recent_90d,
            "days_since_push": repo.days_since_last_push,
        }
