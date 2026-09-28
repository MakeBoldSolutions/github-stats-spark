"""Dashboard data model for repository comparison dashboard JSON structure."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional
import json


@dataclass
class CommitMetric:
    """Represents a single commit metric (largest/smallest commit).

    Attributes:
        sha: Git commit SHA hash
        date: Commit timestamp
        size: Commit size (files_changed + lines_added + lines_deleted)
        files_changed: Number of files modified in commit
        lines_added: Number of lines added
        lines_deleted: Number of lines deleted
    """

    sha: str
    date: Optional[datetime]
    size: int
    files_changed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0

    def to_dict(self) -> Dict:
        """Convert CommitMetric to dictionary for JSON serialization."""
        return {
            "sha": self.sha,
            "date": (
                self.date.isoformat() if isinstance(self.date, datetime) else self.date
            ),
            "size": self.size,
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
        }


@dataclass
class DashboardRepository:
    """Repository data structure optimized for dashboard display.

    This model contains the essential metrics needed for the dashboard
    table view, visualizations, and comparison features.

    Attributes:
        name: Repository name (without owner prefix)
        language: Primary programming language (or "Unknown")
        created_at: Repository creation timestamp (ISO 8601)
        last_commit_date: Timestamp of most recent commit (ISO 8601)
        first_commit_date: Timestamp of first commit (ISO 8601)
        commit_count: Total number of commits
        avg_commit_size: Average commit size (mean of all commits)
        largest_commit: Largest commit by size (files + lines)
        smallest_commit: Smallest commit by size (files + lines)
        stars: Star count (for popularity sorting)
        forks: Fork count (for popularity sorting)
        url: Full HTTPS URL to repository
        description: Brief repository description (optional)
        updated_at: Last repository update timestamp (ISO 8601)
    """

    name: str
    language: str
    created_at: Optional[datetime]
    last_commit_date: Optional[datetime]
    commit_count: int
    url: str

    # Optional fields with defaults
    first_commit_date: Optional[datetime] = None
    avg_commit_size: float = 0.0
    largest_commit: Optional[CommitMetric] = None
    smallest_commit: Optional[CommitMetric] = None
    stars: int = 0
    forks: int = 0
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert DashboardRepository to dictionary for JSON serialization.

        Returns:
            Dictionary representation with ISO 8601 datetime formatting
        """
        return {
            "name": self.name,
            "language": self.language or "Unknown",
            "created_at": (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime)
                else self.created_at
            ),
            "last_commit_date": (
                self.last_commit_date.isoformat()
                if isinstance(self.last_commit_date, datetime)
                else self.last_commit_date
            ),
            "first_commit_date": (
                self.first_commit_date.isoformat()
                if self.first_commit_date
                and isinstance(self.first_commit_date, datetime)
                else self.first_commit_date
            ),
            "commit_count": self.commit_count,
            "avg_commit_size": round(self.avg_commit_size, 2),
            "largest_commit": (
                self.largest_commit.to_dict() if self.largest_commit else None
            ),
            "smallest_commit": (
                self.smallest_commit.to_dict() if self.smallest_commit else None
            ),
            "stars": self.stars,
            "forks": self.forks,
            "url": self.url,
            "description": self.description,
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at and isinstance(self.updated_at, datetime)
                else self.updated_at
            ),
        }


@dataclass
class UserProfile:
    """User profile information for dashboard header.

    Attributes:
        username: GitHub username
        avatar_url: URL to user avatar image
        public_repos_count: Total public repositories
        total_commits: Total commits across all repositories (optional)
        total_stars: Total stars received (optional)
        total_forks: Total forks across all repositories (optional)
        profile_url: GitHub profile URL
    """

    username: str
    avatar_url: str
    public_repos_count: int
    profile_url: str
    total_commits: Optional[int] = None
    total_stars: Optional[int] = None
    total_forks: Optional[int] = None

    def to_dict(self) -> Dict:
        """Convert UserProfile to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class DashboardMetadata:
    """Metadata about dashboard data generation.

    Attributes:
        generated_at: Timestamp when data was generated (ISO 8601)
        schema_version: Semantic version of dashboard data schema
        repository_count: Total repositories included
        data_source: Source of data (e.g., "GitHub API")
        cache_hit_rate: Percentage of API requests served from cache (optional)
    """

    generated_at: datetime
    schema_version: str = "1.0.0"
    repository_count: int = 0
    data_source: str = "GitHub API"
    cache_hit_rate: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert DashboardMetadata to dictionary for JSON serialization."""
        return {
            "generated_at": (
                self.generated_at.isoformat()
                if isinstance(self.generated_at, datetime)
                else self.generated_at
            ),
            "schema_version": self.schema_version,
            "repository_count": self.repository_count,
            "data_source": self.data_source,
            "cache_hit_rate": (
                round(self.cache_hit_rate, 2)
                if self.cache_hit_rate is not None
                else None
            ),
        }


@dataclass
class DashboardData:
    """Complete dashboard data structure for JSON export.

    This is the root data structure that gets serialized to
    docs/data/repositories.json for frontend consumption.

    Attributes:
        repositories: List of repository data for dashboard
        profile: User profile information
        metadata: Generation metadata and versioning
    """

    repositories: List[DashboardRepository] = field(default_factory=list)
    profile: Optional[UserProfile] = None
    metadata: Optional[DashboardMetadata] = None

    def to_dict(self) -> Dict:
        """Convert DashboardData to dictionary for JSON serialization.

        Returns:
            Complete dashboard data structure as dictionary
        """
        return {
            "repositories": [repo.to_dict() for repo in self.repositories],
            "profile": self.profile.to_dict() if self.profile else None,
            "metadata": self.metadata.to_dict() if self.metadata else None,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize DashboardData to JSON string.

        Args:
            indent: Number of spaces for JSON indentation (default: 2)

        Returns:
            JSON string representation of dashboard data
        """
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, filepath: str, indent: int = 2) -> None:
        """Save dashboard data to JSON file.

        Args:
            filepath: Path to output JSON file
            indent: Number of spaces for JSON indentation (default: 2)
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json(indent=indent))

    @classmethod
    def from_dict(cls, data: Dict) -> "DashboardData":
        """Create DashboardData from dictionary.

        Args:
            data: Dictionary containing dashboard data

        Returns:
            DashboardData instance
        """
        repositories = [
            DashboardRepository(**repo) for repo in data.get("repositories", [])
        ]
        profile = UserProfile(**data["profile"]) if data.get("profile") else None
        metadata = (
            DashboardMetadata(**data["metadata"]) if data.get("metadata") else None
        )

        return cls(
            repositories=repositories,
            profile=profile,
            metadata=metadata,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "DashboardData":
        """Create DashboardData from JSON string.

        Args:
            json_str: JSON string representation

        Returns:
            DashboardData instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def load_from_file(cls, filepath: str) -> "DashboardData":
        """Load dashboard data from JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            DashboardData instance
        """
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())
