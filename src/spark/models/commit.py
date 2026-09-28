"""Commit history entity model for repository analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class CommitHistory:
    """Represents commit history and activity patterns for a repository.

    This model captures temporal commit data used for activity scoring
    and pattern analysis in the ranking algorithm.

    Attributes:
        repository_name: Name of the repository
        total_commits: Total lifetime commits
        recent_90d: Commits in last 90 days
        recent_180d: Commits in last 180 days
        recent_365d: Commits in last 365 days
        last_commit_date: Timestamp of most recent commit
        patterns: Detected activity patterns (e.g., "active", "sporadic", "stale")
        commit_frequency: Average commits per month (recent 90d)
        consistency_score: 0-100 score for commit regularity
    """

    repository_name: str
    total_commits: int = 0
    recent_90d: int = 0
    recent_180d: int = 0
    recent_365d: int = 0
    last_commit_date: Optional[datetime] = None
    patterns: List[str] = field(default_factory=list)
    commit_frequency: float = 0.0
    consistency_score: int = 0

    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.commit_frequency = self._calculate_frequency()
        self.patterns = self._detect_patterns()

    def _calculate_frequency(self) -> float:
        """Calculate average commits per month based on recent 90-day window.

        Returns:
            Average commits per month (float)
        """
        if self.recent_90d == 0:
            return 0.0
        # 90 days ≈ 3 months
        return round(self.recent_90d / 3, 2)

    def _detect_patterns(self) -> List[str]:
        """Detect activity patterns from commit data.

        Returns:
            List of pattern descriptors (e.g., ["active", "consistent"])
        """
        patterns = []

        # Activity level classification
        if self.recent_90d >= 30:
            patterns.append("highly_active")
        elif self.recent_90d >= 10:
            patterns.append("active")
        elif self.recent_90d >= 1:
            patterns.append("maintained")
        elif self.recent_365d >= 1:
            patterns.append("minimal_activity")
        else:
            patterns.append("stale")

        # Recency classification
        if self.last_commit_date:
            from datetime import timezone

            now = datetime.now(timezone.utc)
            last_commit = (
                self.last_commit_date
                if self.last_commit_date.tzinfo
                else self.last_commit_date.replace(tzinfo=timezone.utc)
            )
            days_ago = (now - last_commit).days
            if days_ago <= 7:
                patterns.append("recently_updated")
            elif days_ago <= 30:
                patterns.append("current")
            elif days_ago > 365:
                patterns.append("outdated")

        # Consistency analysis (compare 90d vs 180d vs 365d)
        if self.recent_180d > 0:
            # Check if commit rate is consistent across time windows
            rate_90 = self.recent_90d / 90
            rate_180 = self.recent_180d / 180
            self.recent_365d / 365 if self.recent_365d > 0 else 0

            # If rates are similar (within 20%), activity is consistent
            if rate_180 > 0 and abs(rate_90 - rate_180) / rate_180 < 0.2:
                patterns.append("consistent")
            elif rate_90 > rate_180 * 1.5:
                patterns.append("accelerating")
            elif rate_90 < rate_180 * 0.5:
                patterns.append("declining")

        return patterns

    @property
    def activity_rate(self) -> float:
        """Calculate commits per day over the last 90 days.

        Returns:
            Commits per day (float)
        """
        return round(self.recent_90d / 90, 3) if self.recent_90d > 0 else 0.0

    @property
    def days_since_last_commit(self) -> Optional[int]:
        """Calculate days since last commit.

        Returns:
            Days since last commit, or None if no commits
        """
        if not self.last_commit_date:
            return None
        from datetime import timezone

        now = datetime.now(timezone.utc)
        # Ensure both datetimes are timezone-aware
        last_commit = (
            self.last_commit_date
            if self.last_commit_date.tzinfo
            else self.last_commit_date.replace(tzinfo=timezone.utc)
        )
        delta = now - last_commit
        return max(0, delta.days)

    @classmethod
    def from_dict(cls, data: dict) -> "CommitHistory":
        """Create CommitHistory from dictionary (e.g., from API cache).

        Args:
            data: Dictionary with commit history data

        Returns:
            CommitHistory instance
        """
        last_commit_date = None
        if data.get("last_commit_date"):
            last_commit_date = datetime.fromisoformat(data["last_commit_date"])

        return cls(
            repository_name=data.get("repository_name", ""),
            total_commits=data.get("total", 0),
            recent_90d=data.get("recent_90d", 0),
            recent_180d=data.get("recent_180d", 0),
            recent_365d=data.get("recent_365d", 0),
            last_commit_date=last_commit_date,
            patterns=data.get("patterns", []),
            commit_frequency=data.get("commit_frequency", 0.0),
            consistency_score=data.get("consistency_score", 0),
        )

    def to_dict(self) -> dict:
        """Serialize commit history to dictionary format.

        Returns:
            Dictionary with all commit history fields
        """
        return {
            "repository_name": self.repository_name,
            "total_commits": self.total_commits,
            "recent_90d": self.recent_90d,
            "recent_180d": self.recent_180d,
            "recent_365d": self.recent_365d,
            "last_commit_date": (
                self.last_commit_date.isoformat() if self.last_commit_date else None
            ),
            "patterns": self.patterns,
            "commit_frequency": self.commit_frequency,
            "consistency_score": self.consistency_score,
            "activity_rate": self.activity_rate,
            "days_since_last_commit": self.days_since_last_commit,
        }
