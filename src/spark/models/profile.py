"""User profile entity model for overall developer analysis."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActivityPattern:
    """Represents an observed activity pattern in a developer's work.

    Attributes:
        pattern_type: Type of pattern (e.g., "technology_focus", "commit_consistency", "project_diversity")
        description: Human-readable description of the pattern
        evidence: Supporting data (e.g., language counts, commit stats)
        confidence: 0-100 confidence in pattern detection
    """

    pattern_type: str
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: int = 0

    def to_dict(self) -> dict:
        """Serialize pattern to dictionary."""
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass
class UserProfile:
    """Represents overall developer profile and activity analysis.

    This model aggregates insights across all repositories to provide
    a holistic view of the developer's skills, focus, and activity.

    Attributes:
        username: GitHub username
        total_repos: Total number of public repositories analyzed
        active_repos: Number of recently active repositories (90d activity)
        tech_diversity: Technology diversity score (0-100)
        primary_languages: Top languages by total bytes across all repos
        framework_usage: Frameworks and libraries detected
        activity_patterns: List of detected ActivityPattern objects
        overall_impression: AI-generated overall developer impression
        contribution_classification: Developer type (e.g., "active_maintainer", "hobbyist", "specialist")
        commit_frequency: Average commits per month across active repos
        repository_health_avg: Average health score across all repos
    """

    username: str
    total_repos: int = 0
    active_repos: int = 0
    tech_diversity: int = 0
    primary_languages: Dict[str, int] = field(
        default_factory=dict
    )  # language -> total bytes
    framework_usage: Dict[str, int] = field(
        default_factory=dict
    )  # framework -> repo count
    activity_patterns: List[ActivityPattern] = field(default_factory=list)
    overall_impression: Optional[str] = None
    contribution_classification: str = "unknown"
    commit_frequency: float = 0.0
    repository_health_avg: float = 0.0

    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.tech_diversity = self._calculate_tech_diversity()
        self.contribution_classification = self._classify_contribution_style()

    def _calculate_tech_diversity(self) -> int:
        """Calculate technology diversity score.

        Diversity considers:
        - Number of distinct languages (weighted by usage)
        - Number of frameworks
        - Balance of language usage (not dominated by one)

        Returns:
            Score from 0-100
        """
        if not self.primary_languages:
            return 0

        # Language count score (more languages = higher diversity)
        language_count = len(self.primary_languages)
        language_score = min(100, language_count * 15)  # Max 7 languages for full score

        # Balance score (how evenly distributed are the languages)
        total_bytes = sum(self.primary_languages.values())
        if total_bytes == 0:
            balance_score = 0
        else:
            # Calculate Herfindahl index (lower = more diverse)
            herfindahl = sum(
                (bytes / total_bytes) ** 2 for bytes in self.primary_languages.values()
            )
            balance_score = int((1 - herfindahl) * 100)

        # Framework diversity
        framework_score = min(100, len(self.framework_usage) * 10)  # Max 10 frameworks

        # Weighted average: 40% language count, 40% balance, 20% frameworks
        diversity = int(
            language_score * 0.4 + balance_score * 0.4 + framework_score * 0.2
        )
        return min(100, diversity)

    def _classify_contribution_style(self) -> str:
        """Classify developer based on activity patterns.

        Returns:
            Classification string (active_maintainer, hobbyist, specialist, etc.)
        """
        # Active maintainer: high commit frequency, many active repos
        if self.commit_frequency > 50 and self.active_repos >= 5:
            return "active_maintainer"

        # Specialist: focused on specific language/framework, deep expertise
        if self.tech_diversity < 30 and self.total_repos >= 10:
            return "specialist"

        # Polyglot: high diversity, many languages
        if self.tech_diversity > 70:
            return "polyglot"

        # Hobbyist: moderate activity, diverse projects
        if self.commit_frequency < 20 and self.total_repos >= 5:
            return "hobbyist"

        # Experimenter: many repos, low activity per repo
        if self.total_repos > 20 and self.active_repos < self.total_repos * 0.3:
            return "experimenter"

        return "developer"

    def add_pattern(self, pattern: ActivityPattern) -> None:
        """Add an activity pattern to the profile.

        Args:
            pattern: ActivityPattern instance to add
        """
        self.activity_patterns.append(pattern)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        """Create UserProfile from dictionary (e.g., from GitHub API data).

        Args:
            data: Dictionary with user profile data

        Returns:
            UserProfile instance
        """
        return cls(
            username=data.get("username", ""),
            total_repos=data.get("public_repos", 0),
            active_repos=0,  # Will be calculated later
            tech_diversity=0,  # Will be calculated in __post_init__
            primary_languages={},
            framework_usage={},
            activity_patterns=[],
            overall_impression=None,
            contribution_classification="unknown",
            commit_frequency=0.0,
            repository_health_avg=0.0,
        )

    @property
    def top_languages(self) -> List[str]:
        """Get top 3 languages by bytes.

        Returns:
            List of language names in descending order
        """
        sorted_langs = sorted(
            self.primary_languages.items(), key=lambda x: x[1], reverse=True
        )
        return [lang for lang, _ in sorted_langs[:3]]

    @property
    def activity_ratio(self) -> float:
        """Calculate ratio of active to total repositories.

        Returns:
            Ratio from 0.0 to 1.0
        """
        if self.total_repos == 0:
            return 0.0
        return round(self.active_repos / self.total_repos, 2)

    def to_dict(self) -> dict:
        """Serialize user profile to dictionary format.

        Returns:
            Dictionary with all profile fields
        """
        return {
            "username": self.username,
            "total_repos": self.total_repos,
            "active_repos": self.active_repos,
            "tech_diversity": self.tech_diversity,
            "primary_languages": self.primary_languages,
            "framework_usage": self.framework_usage,
            "activity_patterns": [
                pattern.to_dict() for pattern in self.activity_patterns
            ],
            "overall_impression": self.overall_impression,
            "contribution_classification": self.contribution_classification,
            "commit_frequency": self.commit_frequency,
            "repository_health_avg": self.repository_health_avg,
            "top_languages": self.top_languages,
            "activity_ratio": self.activity_ratio,
        }
