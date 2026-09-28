"""Repository entity model for GitHub repository analysis.

# SIZE JUSTIFICATION (Constitution I — ~522 LOC as of 2026-04-02):
# The Repository dataclass accumulates schema 2.x enrichment fields
# (attention metrics, security summary, pull request summary, bus factor,
# tech stack) in one model to keep the data contract between the backend
# pipeline and the frontend JSON schema in a single, diffable location.
# Each schema version bump adds new optional fields here; splitting would
# scatter the schema contract across files.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, List


@dataclass
class RepositoryPullRequestSummary:
    """Compact pull request signal for a repository."""

    availability: str = "unavailable"
    reason: str = "not_requested"
    has_open_pull_requests: bool = False
    total_open: int = 0
    draft_count: int = 0
    review_requested_count: int = 0
    oldest_open_age_days: Optional[int] = None
    source: str = "rest.pulls.list"

    def to_dict(self) -> Dict:
        return {
            "availability": self.availability,
            "reason": self.reason,
            "has_open_pull_requests": self.has_open_pull_requests,
            "total_open": self.total_open,
            "draft_count": self.draft_count,
            "review_requested_count": self.review_requested_count,
            "oldest_open_age_days": self.oldest_open_age_days,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "RepositoryPullRequestSummary":
        payload = data or {}
        return cls(
            availability=payload.get("availability", "unavailable"),
            reason=payload.get("reason", "not_requested"),
            has_open_pull_requests=payload.get("has_open_pull_requests", False),
            total_open=payload.get("total_open", 0),
            draft_count=payload.get("draft_count", 0),
            review_requested_count=payload.get("review_requested_count", 0),
            oldest_open_age_days=payload.get("oldest_open_age_days"),
            source=payload.get("source", "rest.pulls.list"),
        )


@dataclass
class RepositorySecuritySummary:
    """Compact security posture and alert summary for a repository."""

    availability: str = "unavailable"
    reason: str = "not_requested"
    overall_state: str = "unavailable"
    feature_status: Dict[str, str] = field(
        default_factory=lambda: {
            "advanced_security": "unavailable",
            "secret_scanning": "unavailable",
            "secret_scanning_push_protection": "unavailable",
            "dependency_alerts": "unavailable",
            "automated_security_fixes": "unavailable",
        }
    )
    active_alert_counts: Dict[str, int] = field(
        default_factory=lambda: {
            "total_open": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
    )
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "availability": self.availability,
            "reason": self.reason,
            "overall_state": self.overall_state,
            "feature_status": self.feature_status,
            "active_alert_counts": self.active_alert_counts,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "RepositorySecuritySummary":
        payload = data or {}
        return cls(
            availability=payload.get("availability", "unavailable"),
            reason=payload.get("reason", "not_requested"),
            overall_state=payload.get("overall_state", "unavailable"),
            feature_status=payload.get("feature_status")
            or {
                "advanced_security": "unavailable",
                "secret_scanning": "unavailable",
                "secret_scanning_push_protection": "unavailable",
                "dependency_alerts": "unavailable",
                "automated_security_fixes": "unavailable",
            },
            active_alert_counts=payload.get("active_alert_counts")
            or {
                "total_open": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            sources=payload.get("sources", []),
        )


@dataclass
class RepositoryDiagnosticsSummary:
    """Consolidated operational diagnostics for a repository."""

    availability: str = "unavailable"
    reason: str = "not_requested"
    pull_requests: Dict[str, Any] = field(default_factory=dict)
    issues: Dict[str, Any] = field(default_factory=dict)
    security: Dict[str, Any] = field(default_factory=dict)
    actions: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "availability": self.availability,
            "reason": self.reason,
            "pull_requests": self.pull_requests,
            "issues": self.issues,
            "security": self.security,
            "actions": self.actions,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "RepositoryDiagnosticsSummary":
        payload = data or {}
        return cls(
            availability=payload.get("availability", "unavailable"),
            reason=payload.get("reason", "not_requested"),
            pull_requests=payload.get("pull_requests") or {},
            issues=payload.get("issues") or {},
            security=payload.get("security") or {},
            actions=payload.get("actions") or {},
            sources=payload.get("sources", []),
        )


@dataclass
class Repository:
    """Represents a GitHub repository with metadata and statistics.

    This model contains all essential information about a repository needed
    for ranking, analysis, and report generation.

    Attributes:
        name: Repository name (without owner prefix)
        description: Repository description from GitHub
        url: Full HTTPS URL to the repository
        created_at: Repository creation timestamp
        updated_at: Last update timestamp (any change)
        pushed_at: Last push timestamp (code changes)
        primary_language: Primary programming language
        language_stats: Dictionary of languages to bytes of code
        stars: Star count
        forks: Fork count
        watchers: Watcher count
        open_issues: Count of open issues
        is_archived: Whether repository is archived
        is_fork: Whether repository is a fork
        fork_info: For forks, commits ahead/behind parent (optional)
        has_readme: Whether a README file exists
        size_kb: Repository size in kilobytes
        is_private: Whether repository is private (should always be False per constitution)
        contributors_count: Number of contributors (Tier 1)
        language_count: Number of distinct programming languages (Tier 1)
        has_ci_cd: Whether repository has CI/CD workflows (Quality Focus)
        has_tests: Whether repository has tests directory (Quality Focus)
        has_license: Whether repository has LICENSE file (Quality Focus)
        has_docs: Whether repository has documentation (Quality Focus)
        release_count: Total number of releases (Activity Focus)
        latest_release_date: Date of most recent release (Activity Focus)
        commit_velocity: Commits per month trend (Activity Focus)
        homepage: Custom website URL set in repository settings (optional)
        has_pages: Whether GitHub Pages is enabled for this repository
    """

    name: str
    description: Optional[str]
    url: str
    created_at: datetime
    updated_at: datetime
    pushed_at: Optional[datetime]
    primary_language: Optional[str]
    language_stats: Dict[str, int] = field(default_factory=dict)
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    is_archived: bool = False
    is_fork: bool = False
    fork_info: Optional[Dict[str, int]] = (
        None  # {"commits_ahead": X, "commits_behind": Y}
    )
    has_readme: bool = False
    size_kb: int = 0
    is_private: bool = False
    # Tier 1 - Quick Enhancement
    contributors_count: int = 0
    language_count: int = 0
    # Quality Focus
    has_ci_cd: bool = False
    has_tests: bool = False
    has_license: bool = False
    has_docs: bool = False
    # Activity Focus
    release_count: int = 0
    latest_release_date: Optional[datetime] = None
    commit_velocity: Optional[float] = None  # commits per month
    # Website URLs
    homepage: Optional[str] = None  # Custom website URL from repo settings
    has_pages: bool = False  # GitHub Pages enabled
    pull_request_summary: RepositoryPullRequestSummary = field(
        default_factory=RepositoryPullRequestSummary
    )
    security_summary: RepositorySecuritySummary = field(
        default_factory=RepositorySecuritySummary
    )
    diagnostics_summary: RepositoryDiagnosticsSummary = field(
        default_factory=RepositoryDiagnosticsSummary
    )

    def __post_init__(self):
        """Validate that private repositories are never processed."""
        if self.is_private:
            raise ValueError(
                f"Privacy violation: Attempted to process private repository '{self.name}'. "
                "Only public repositories are allowed per constitution III."
            )

    @property
    def age_days(self) -> int:
        """Calculate repository age in days from creation."""
        if not self.created_at:
            return 0
        from datetime import timezone

        now = datetime.now(timezone.utc)
        # Ensure both datetimes are timezone-aware
        created = (
            self.created_at
            if self.created_at.tzinfo
            else self.created_at.replace(tzinfo=timezone.utc)
        )
        delta = now - created
        return max(0, delta.days)

    @property
    def days_since_last_push(self) -> Optional[int]:
        """Calculate days since last push."""
        if not self.pushed_at:
            return None
        from datetime import timezone

        now = datetime.now(timezone.utc)
        # Ensure both datetimes are timezone-aware
        pushed = (
            self.pushed_at
            if self.pushed_at.tzinfo
            else self.pushed_at.replace(tzinfo=timezone.utc)
        )
        delta = now - pushed
        return max(0, delta.days)

    @property
    def is_empty(self) -> bool:
        """Check if repository appears empty (no commits, minimal size)."""
        return self.pushed_at is None and self.size_kb < 10

    @property
    def pages_url(self) -> Optional[str]:
        """Construct GitHub Pages URL if pages are enabled.

        Returns:
            GitHub Pages URL in format https://{owner}.github.io/{repo}/ or None
        """
        if not self.has_pages:
            return None
        # Extract owner from URL: https://github.com/owner/repo
        if self.url and "github.com/" in self.url:
            parts = self.url.split("github.com/")[-1].split("/")
            if len(parts) >= 2:
                owner = parts[0]
                return f"https://{owner}.github.io/{self.name}/"
        return None

    @property
    def website_url(self) -> Optional[str]:
        """Get the best available website URL for the repository.

        Priority: homepage > pages_url

        Returns:
            Website URL or None if no website is available
        """
        return self.homepage or self.pages_url

    def to_dict(self) -> dict:
        """Serialize repository to dictionary format.

        Returns:
            Dictionary with all repository fields, with datetimes as ISO strings
        """
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "pushed_at": self.pushed_at.isoformat() if self.pushed_at else None,
            "primary_language": self.primary_language,
            "language_stats": self.language_stats,
            "stars": self.stars,
            "forks": self.forks,
            "watchers": self.watchers,
            "open_issues": self.open_issues,
            "is_archived": self.is_archived,
            "is_fork": self.is_fork,
            "fork_info": self.fork_info,
            "has_readme": self.has_readme,
            "size_kb": self.size_kb,
            "is_private": self.is_private,
            "age_days": self.age_days,
            "days_since_last_push": self.days_since_last_push,
            # Tier 1
            "contributors_count": self.contributors_count,
            "language_count": self.language_count,
            # Quality Focus
            "has_ci_cd": self.has_ci_cd,
            "has_tests": self.has_tests,
            "has_license": self.has_license,
            "has_docs": self.has_docs,
            # Activity Focus
            "release_count": self.release_count,
            "latest_release_date": (
                self.latest_release_date.isoformat()
                if self.latest_release_date
                else None
            ),
            "commit_velocity": self.commit_velocity,
            # Website URLs
            "homepage": self.homepage,
            "has_pages": self.has_pages,
            "pages_url": self.pages_url,
            "website_url": self.website_url,
            "pull_request_summary": self.pull_request_summary.to_dict(),
            "security_summary": self.security_summary.to_dict(),
            "diagnostics_summary": self.diagnostics_summary.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Repository":
        """Create Repository from dictionary (e.g., from API cache).

        Args:
            data: Dictionary with repository data

        Returns:
            Repository instance

        Raises:
            ValueError: If repository is private (constitution violation)
        """
        from datetime import datetime

        # Parse datetime strings
        created_at = (
            datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now()
        )
        updated_at = (
            datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else datetime.now()
        )
        pushed_at = (
            datetime.fromisoformat(data["pushed_at"]) if data.get("pushed_at") else None
        )

        return cls(
            name=data.get("name", ""),
            description=data.get("description"),
            url=data.get("url", f"https://github.com/{data.get('full_name', '')}"),
            created_at=created_at,
            updated_at=updated_at,
            pushed_at=pushed_at,
            primary_language=data.get("language"),
            language_stats={},  # Will be populated separately
            stars=data.get("stars", 0),
            forks=data.get("forks", 0),
            watchers=data.get("watchers", 0),
            open_issues=data.get("open_issues", 0),
            is_archived=data.get("is_archived", False),
            is_fork=data.get("is_fork", False),
            fork_info=data.get("fork_info"),
            has_readme=data.get("has_readme", False),
            size_kb=data.get("size", 0),
            is_private=data.get("is_private", False),
            contributors_count=data.get("contributors_count", 0),
            language_count=data.get("language_count", 0),
            has_ci_cd=data.get("has_ci_cd", False),
            has_tests=data.get("has_tests", False),
            has_license=data.get("has_license", False),
            has_docs=data.get("has_docs", False),
            release_count=data.get("release_count", 0),
            latest_release_date=None,
            commit_velocity=data.get("commit_velocity"),
            homepage=data.get("homepage"),
            has_pages=data.get("has_pages", False),
            pull_request_summary=RepositoryPullRequestSummary.from_dict(
                data.get("pull_request_summary")
            ),
            security_summary=RepositorySecuritySummary.from_dict(
                data.get("security_summary")
            ),
            diagnostics_summary=RepositoryDiagnosticsSummary.from_dict(
                data.get("diagnostics_summary")
            ),
        )

    @classmethod
    def from_github_repo(cls, github_repo) -> "Repository":
        """Create Repository from PyGithub Repository object.

        Args:
            github_repo: PyGithub Repository instance

        Returns:
            Repository instance with data extracted from GitHub API

        Raises:
            ValueError: If repository is private (constitution violation)
        """
        # Check README existence (basic check)
        has_readme = False
        try:
            github_repo.get_readme()
            has_readme = True
        except Exception:
            pass

        # Extract fork info if applicable
        fork_info = None
        if github_repo.fork and github_repo.parent:
            # Note: commits_ahead/behind requires comparison API call
            # This will be populated by fetcher.py if needed
            fork_info = {"commits_ahead": 0, "commits_behind": 0}

        # Tier 1 - Get contributors count
        contributors_count = 0
        try:
            contributors_count = github_repo.get_contributors().totalCount
        except Exception:
            pass

        # Quality Focus - Check for CI/CD workflows
        has_ci_cd = False
        try:
            workflows = github_repo.get_workflows()
            has_ci_cd = workflows.totalCount > 0
        except Exception:
            pass

        # Quality Focus - Check for tests directory
        has_tests = False
        try:
            contents = github_repo.get_contents("")
            for item in contents:
                if item.type == "dir" and item.name.lower() in [
                    "test",
                    "tests",
                    "spec",
                    "specs",
                    "__tests__",
                ]:
                    has_tests = True
                    break
        except Exception:
            pass

        # Quality Focus - Check for LICENSE file
        has_license = False
        try:
            github_repo.get_license()
            has_license = True
        except Exception:
            pass

        # Quality Focus - Check for documentation
        has_docs = False
        try:
            contents = github_repo.get_contents("")
            for item in contents:
                if item.type == "dir" and item.name.lower() in [
                    "docs",
                    "doc",
                    "documentation",
                ]:
                    has_docs = True
                    break
                if item.type == "file" and item.name.upper() in [
                    "CONTRIBUTING.md",
                    "CHANGELOG.md",
                ]:
                    has_docs = True
                    break
        except Exception:
            pass

        # Activity Focus - Get release information
        release_count = 0
        latest_release_date = None
        try:
            releases = github_repo.get_releases()
            release_count = releases.totalCount
            if release_count > 0:
                latest_release = releases[0]
                latest_release_date = latest_release.created_at
        except Exception:
            pass

        return cls(
            name=github_repo.name,
            description=github_repo.description,
            url=github_repo.html_url,
            created_at=github_repo.created_at,
            updated_at=github_repo.updated_at,
            pushed_at=github_repo.pushed_at,
            primary_language=github_repo.language,
            language_stats={},  # Will be populated by fetcher.get_languages()
            stars=github_repo.stargazers_count,
            forks=github_repo.forks_count,
            watchers=github_repo.watchers_count,
            open_issues=github_repo.open_issues_count,
            is_archived=github_repo.archived,
            is_fork=github_repo.fork,
            fork_info=fork_info,
            has_readme=has_readme,
            size_kb=github_repo.size,
            is_private=github_repo.private,
            # Tier 1
            contributors_count=contributors_count,
            language_count=0,  # Will be set after language_stats populated
            # Quality Focus
            has_ci_cd=has_ci_cd,
            has_tests=has_tests,
            has_license=has_license,
            has_docs=has_docs,
            # Activity Focus
            release_count=release_count,
            latest_release_date=latest_release_date,
            commit_velocity=None,  # Will be calculated from commit history
            homepage=github_repo.homepage,
            has_pages=github_repo.has_pages,
            pull_request_summary=RepositoryPullRequestSummary(),
            security_summary=RepositorySecuritySummary(),
            diagnostics_summary=RepositoryDiagnosticsSummary(),
        )

    def to_dashboard_dict(self) -> Dict:
        """Convert Repository to dictionary for dashboard JSON serialization.

        Returns a subset of repository data optimized for the dashboard frontend.
        This method is used by DashboardGenerator to create the dashboard JSON.

        Returns:
            Dictionary with dashboard-relevant repository fields

        Note:
            This is a lightweight representation focused on display metrics,
            not the full repository analysis data.
        """
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "homepage": self.homepage,
            "has_pages": self.has_pages,
            "pages_url": self.pages_url,
            "website_url": self.website_url,
            "language": self.primary_language or "Unknown",
            "created_at": (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime)
                else self.created_at
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if isinstance(self.updated_at, datetime)
                else self.updated_at
            ),
            "pushed_at": (
                self.pushed_at.isoformat()
                if self.pushed_at and isinstance(self.pushed_at, datetime)
                else self.pushed_at
            ),
            "stars": self.stars,
            "forks": self.forks,
            "watchers": self.watchers,
            "open_issues": self.open_issues,
            "is_archived": self.is_archived,
            "is_fork": self.is_fork,
            "has_readme": self.has_readme,
            "has_license": self.has_license,
            "has_ci_cd": self.has_ci_cd,
            "has_tests": self.has_tests,
            "release_count": self.release_count,
            "latest_release_date": (
                self.latest_release_date.isoformat()
                if self.latest_release_date
                and isinstance(self.latest_release_date, datetime)
                else self.latest_release_date
            ),
            "pull_request_summary": self.pull_request_summary.to_dict(),
            "security_summary": self.security_summary.to_dict(),
            "diagnostics_summary": self.diagnostics_summary.to_dict(),
        }
