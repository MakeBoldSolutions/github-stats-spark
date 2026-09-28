"""Technology stack entity model for dependency analysis."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DependencyInfo:
    """Information about a single dependency.

    Attributes:
        name: Package/gem/module name
        current_version: Version currently specified or resolved from the manifest
        latest_version: Latest available version from registry
        ecosystem: Package ecosystem (npm, pypi, rubygems, go, maven)
        versions_behind: Number of major versions behind
        is_outdated: Whether dependency is outdated
        status: Currency status (current, minor_outdated, major_outdated, unknown)
    """

    name: str
    current_version: str
    latest_version: Optional[str] = None
    ecosystem: str = "unknown"
    versions_behind: int = 0
    is_outdated: bool = False
    status: str = "unknown"  # current, minor_outdated, major_outdated, unknown
    version_requirement: Optional[str] = None
    current_version_known: bool = True
    latest_version_status: str = "not_requested"
    latest_version_source: Optional[str] = None
    source_file: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize dependency to dictionary."""
        return {
            "name": self.name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "ecosystem": self.ecosystem,
            "versions_behind": self.versions_behind,
            "is_outdated": self.is_outdated,
            "status": self.status,
            "version_requirement": self.version_requirement,
            "current_version_known": self.current_version_known,
            "latest_version_status": self.latest_version_status,
            "latest_version_source": self.latest_version_source,
            "source_file": self.source_file,
        }


@dataclass
class TechnologyStack:
    """Represents the technology stack of a repository.

    This model captures programming languages, frameworks, and dependency
    information for currency assessment.

    Attributes:
        repository_name: Name of the repository
        languages: Dictionary mapping language names to bytes of code
        frameworks: Detected frameworks/libraries (e.g., React, Django, Rails)
        dependencies: List of DependencyInfo objects
        version_info: Additional version information (e.g., Node version, Python version)
        dependency_file_type: Type of dependency file found (package.json, requirements.txt, etc.)
        currency_score: 0-100 score for overall dependency currency
        outdated_count: Number of outdated dependencies
        total_dependencies: Total number of dependencies analyzed
    """

    repository_name: str
    languages: Dict[str, int] = field(default_factory=dict)
    frameworks: List[str] = field(default_factory=list)
    dependencies: List[DependencyInfo] = field(default_factory=list)
    version_info: Dict[str, str] = field(default_factory=dict)
    dependency_file_type: Optional[str] = None
    currency_score: int = 0
    outdated_count: int = 0
    total_dependencies: int = 0
    known_versions_count: int = 0
    resolved_latest_versions_count: int = 0
    unknown_versions_count: int = 0

    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.total_dependencies = len(self.dependencies)
        self.outdated_count = sum(1 for dep in self.dependencies if dep.is_outdated)
        self.known_versions_count = sum(
            1 for dep in self.dependencies if dep.current_version_known
        )
        self.resolved_latest_versions_count = sum(
            1 for dep in self.dependencies if dep.latest_version_status == "resolved"
        )
        self.unknown_versions_count = (
            self.total_dependencies - self.known_versions_count
        )
        self.currency_score = self._calculate_currency_score()

    def _calculate_currency_score(self) -> int:
        """Calculate currency score based on dependency status.

        Returns:
            Score from 0-100, where 100 is all dependencies current
        """
        if self.total_dependencies == 0:
            return 100  # No dependencies = perfectly current

        # Count dependencies by status
        current_count = sum(1 for dep in self.dependencies if dep.status == "current")
        minor_outdated = sum(
            1 for dep in self.dependencies if dep.status == "minor_outdated"
        )
        major_outdated = sum(
            1 for dep in self.dependencies if dep.status == "major_outdated"
        )

        # Weighted scoring:
        # - Current: 100% credit
        # - Minor outdated: 70% credit
        # - Major outdated: 30% credit
        # - Unknown: 50% credit
        total_score = (
            current_count * 100
            + minor_outdated * 70
            + major_outdated * 30
            + (
                self.total_dependencies
                - current_count
                - minor_outdated
                - major_outdated
            )
            * 50
        )

        return min(100, int(total_score / self.total_dependencies))

    @property
    def primary_language(self) -> Optional[str]:
        """Get the primary language by bytes of code.

        Returns:
            Language name with most bytes, or None if no languages
        """
        if not self.languages:
            return None
        return max(self.languages.items(), key=lambda x: x[1])[0]

    @property
    def language_diversity(self) -> int:
        """Count of distinct languages used.

        Returns:
            Number of different languages
        """
        return len(self.languages)

    @property
    def outdated_percentage(self) -> float:
        """Percentage of dependencies that are outdated.

        Returns:
            Percentage (0-100) of outdated dependencies
        """
        if self.total_dependencies == 0:
            return 0.0
        return round((self.outdated_count / self.total_dependencies) * 100, 1)

    @property
    def version_coverage_percentage(self) -> float:
        """Percentage of dependencies with a concrete current version."""
        if self.total_dependencies == 0:
            return 100.0
        return round((self.known_versions_count / self.total_dependencies) * 100, 1)

    @property
    def latest_version_coverage_percentage(self) -> float:
        """Percentage of dependencies with registry-backed latest version data."""
        if self.total_dependencies == 0:
            return 100.0
        return round(
            (self.resolved_latest_versions_count / self.total_dependencies) * 100,
            1,
        )

    def add_dependency(self, dependency: DependencyInfo) -> None:
        """Add a dependency to the stack.

        Args:
            dependency: DependencyInfo instance to add
        """
        self.dependencies.append(dependency)
        self.total_dependencies = len(self.dependencies)
        self.outdated_count = sum(1 for dep in self.dependencies if dep.is_outdated)
        self.known_versions_count = sum(
            1 for dep in self.dependencies if dep.current_version_known
        )
        self.resolved_latest_versions_count = sum(
            1 for dep in self.dependencies if dep.latest_version_status == "resolved"
        )
        self.unknown_versions_count = (
            self.total_dependencies - self.known_versions_count
        )
        self.currency_score = self._calculate_currency_score()

    @classmethod
    def from_dict(cls, data: dict) -> "TechnologyStack":
        """Restore nested dependency models and recalculate derived scores."""
        values = {
            key: value for key, value in data.items() if key in cls.__dataclass_fields__
        }
        values["dependencies"] = [
            DependencyInfo(
                **{
                    key: value
                    for key, value in item.items()
                    if key in DependencyInfo.__dataclass_fields__
                }
            )
            for item in data.get("dependencies", [])
        ]
        return cls(**values)

    def to_dict(self) -> dict:
        """Serialize technology stack to dictionary format.

        Returns:
            Dictionary with all tech stack fields
        """
        return {
            "repository_name": self.repository_name,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "version_info": self.version_info,
            "dependency_file_type": self.dependency_file_type,
            "currency_score": self.currency_score,
            "outdated_count": self.outdated_count,
            "total_dependencies": self.total_dependencies,
            "known_versions_count": self.known_versions_count,
            "resolved_latest_versions_count": self.resolved_latest_versions_count,
            "unknown_versions_count": self.unknown_versions_count,
            "primary_language": self.primary_language,
            "language_diversity": self.language_diversity,
            "outdated_percentage": self.outdated_percentage,
            "version_coverage_percentage": self.version_coverage_percentage,
            "latest_version_coverage_percentage": self.latest_version_coverage_percentage,
        }
