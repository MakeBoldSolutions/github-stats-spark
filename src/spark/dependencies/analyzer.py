"""Repository dependency analyzer for technology stack identification."""

import logging
import re
from dataclasses import dataclass
from typing import TypedDict, Dict, List, Optional, Tuple

import requests
from packaging.version import InvalidVersion, Version

from .parser import DependencyParser, Dependency


@dataclass
class DependencyStatus:
    """Status of a single dependency."""

    name: str
    current_version: str
    ecosystem: str
    latest_version: Optional[str] = None
    versions_behind: int = 0
    is_outdated: bool = False
    status: str = "unknown"
    version_requirement: Optional[str] = None
    current_version_known: bool = True
    latest_version_status: str = "not_requested"
    latest_version_source: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class RepositoryDependencyReport:
    """Dependency analysis report for a repository."""

    total_dependencies: int
    ecosystems: List[str]
    details: List[DependencyStatus]


class VersionLookupSettings(TypedDict):
    """Validated dependency registry lookup options."""

    enabled: bool
    max_dependencies: int
    timeout_seconds: float
    supported_ecosystems: set[str]


class RepositoryDependencyAnalyzer:
    """Analyze repository dependencies for technology stack identification."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize analyzer.

        Args:
            config: Configuration dictionary with analyzer settings
        """
        self.parser = DependencyParser()
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self._registry_cache: Dict[
            Tuple[str, str], Tuple[Optional[str], str, Optional[str]]
        ] = {}
        self._session = requests.Session()

    def _version_lookup_settings(self) -> VersionLookupSettings:
        lookup = self.config.get("dependency_version_lookup", {})
        supported = lookup.get(
            "supported_ecosystems", ["npm", "pypi", "rubygems", "nuget"]
        )
        return {
            "enabled": lookup.get("enabled", True),
            "max_dependencies": int(lookup.get("max_dependencies", 25)),
            "timeout_seconds": float(lookup.get("timeout_seconds", 2.0)),
            "supported_ecosystems": set(supported),
        }

    def _normalize_current_version(
        self, version_constraint: str
    ) -> Tuple[str, bool, Optional[str]]:
        raw_value = (version_constraint or "").strip()
        if not raw_value:
            return "unknown", False, None

        if raw_value.lower() in {"latest", "*"}:
            return raw_value, False, raw_value

        try:
            Version(raw_value)
            return raw_value, True, raw_value
        except InvalidVersion:
            match = re.search(r"\d+(?:\.\d+)*(?:[-+._]?[A-Za-z0-9]+)*", raw_value)
            if match:
                candidate = match.group(0)
                try:
                    Version(candidate)
                    return candidate, True, raw_value
                except InvalidVersion:
                    pass

        return raw_value, False, raw_value

    def _fetch_latest_version(
        self,
        ecosystem: str,
        dependency_name: str,
        timeout_seconds: float,
    ) -> Tuple[Optional[str], str, Optional[str]]:
        cache_key = (ecosystem, dependency_name.lower())
        if cache_key in self._registry_cache:
            return self._registry_cache[cache_key]

        result: Tuple[Optional[str], str, Optional[str]]
        try:
            if ecosystem == "npm":
                response = self._session.get(
                    f"https://registry.npmjs.org/{dependency_name}/latest",
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                result = (payload.get("version"), "resolved", "npm")
            elif ecosystem == "pypi":
                response = self._session.get(
                    f"https://pypi.org/pypi/{dependency_name}/json",
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                result = (payload.get("info", {}).get("version"), "resolved", "pypi")
            elif ecosystem == "rubygems":
                response = self._session.get(
                    f"https://rubygems.org/api/v1/gems/{dependency_name}.json",
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                result = (payload.get("version"), "resolved", "rubygems")
            elif ecosystem == "nuget":
                response = self._session.get(
                    f"https://api.nuget.org/v3-flatcontainer/{dependency_name.lower()}/index.json",
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                versions = payload.get("versions") or []
                result = (
                    versions[-1] if versions else None,
                    "resolved" if versions else "not_found",
                    "nuget",
                )
            else:
                result = (None, "unsupported_ecosystem", None)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                result = (None, "not_found", None)
            else:
                result = (None, "lookup_failed", None)
        except requests.RequestException:
            result = (None, "lookup_failed", None)

        self._registry_cache[cache_key] = result
        return result

    def _compare_versions(
        self,
        current_version: str,
        latest_version: Optional[str],
        current_version_known: bool,
    ) -> Tuple[bool, int, str]:
        if not current_version_known or not latest_version:
            return False, 0, "unknown"

        try:
            current = Version(current_version)
            latest = Version(latest_version)
        except InvalidVersion:
            return False, 0, "unknown"

        if current >= latest:
            return False, 0, "current"

        current_major = current.release[0] if current.release else 0
        latest_major = latest.release[0] if latest.release else 0
        versions_behind = max(0, latest_major - current_major)
        if versions_behind > 0:
            return True, versions_behind, "major_outdated"

        return True, 0, "minor_outdated"

    def _build_dependency_status(
        self,
        dep: Dependency,
        source_file: Optional[str],
        lookup_enabled: bool,
        settings: VersionLookupSettings,
    ) -> DependencyStatus:
        current_version, current_version_known, version_requirement = (
            self._normalize_current_version(dep.version_constraint)
        )

        latest_version = None
        latest_version_status = "not_requested"
        latest_version_source = None
        if dep.ecosystem not in settings["supported_ecosystems"]:
            latest_version_status = "unsupported_ecosystem"
        elif lookup_enabled:
            latest_version, latest_version_status, latest_version_source = (
                self._fetch_latest_version(
                    dep.ecosystem,
                    dep.name,
                    settings["timeout_seconds"],
                )
            )
        else:
            latest_version_status = "skipped_limit"

        is_outdated, versions_behind, status = self._compare_versions(
            current_version,
            latest_version,
            current_version_known,
        )

        return DependencyStatus(
            name=dep.name,
            current_version=current_version,
            ecosystem=dep.ecosystem,
            latest_version=latest_version,
            versions_behind=versions_behind,
            is_outdated=is_outdated,
            status=status,
            version_requirement=version_requirement,
            current_version_known=current_version_known,
            latest_version_status=latest_version_status,
            latest_version_source=latest_version_source,
            source_file=source_file,
        )

    def analyze_repository(
        self, dependency_files: Dict[str, str]
    ) -> RepositoryDependencyReport:
        """Parse dependencies from repository files.

        Args:
            dependency_files: Dict mapping filename to file content

        Returns:
            RepositoryDependencyReport with parsed dependencies
        """
        ecosystems: set[str] = set()
        settings = self._version_lookup_settings()
        parsed_dependencies: List[Tuple[str, Dependency]] = []

        # Parse all dependency files
        for filename, content in dependency_files.items():
            deps = self.parser.parse_file(filename, content)
            parsed_dependencies.extend((filename, dep) for dep in deps)
            ecosystems.update(dep.ecosystem for dep in deps)

        if not parsed_dependencies:
            return RepositoryDependencyReport(
                total_dependencies=0, ecosystems=[], details=[]
            )

        lookup_enabled = (
            bool(settings["enabled"])
            and len(parsed_dependencies) <= settings["max_dependencies"]
        )

        # Convert to status objects
        statuses = []
        for source_file, dep in parsed_dependencies:
            status = self._build_dependency_status(
                dep,
                source_file=source_file,
                lookup_enabled=lookup_enabled,
                settings=settings,
            )
            statuses.append(status)

        return RepositoryDependencyReport(
            total_dependencies=len(parsed_dependencies),
            ecosystems=sorted(list(ecosystems)),
            details=statuses,
        )

    def get_dependency_summary(self, report: RepositoryDependencyReport) -> str:
        """Generate human-readable summary of dependencies.

        Args:
            report: Dependency report

        Returns:
            Formatted summary string
        """
        if report.total_dependencies == 0:
            return "No dependencies found"

        lines = []
        lines.append(f"Total Dependencies: {report.total_dependencies}")
        lines.append(f"Ecosystems: {', '.join(report.ecosystems)}")

        # Group by ecosystem
        by_ecosystem: Dict[str, List[DependencyStatus]] = {}
        for dep in report.details:
            if dep.ecosystem not in by_ecosystem:
                by_ecosystem[dep.ecosystem] = []
            by_ecosystem[dep.ecosystem].append(dep)

        for ecosystem, deps in sorted(by_ecosystem.items()):
            lines.append(f"\n{ecosystem.upper()} ({len(deps)}):")
            for dep in sorted(deps, key=lambda x: x.name):
                if dep.latest_version_status == "resolved" and dep.latest_version:
                    lines.append(
                        f"  - {dep.name} ({dep.current_version} -> {dep.latest_version}, {dep.status})"
                    )
                else:
                    lines.append(f"  - {dep.name} ({dep.current_version})")

        return "\n".join(lines)

    def build_technology_stack(
        self,
        repository_name: str,
        report: RepositoryDependencyReport,
        dependency_file_type: Optional[str] = None,
        languages: Optional[Dict[str, int]] = None,
    ):
        """Convert a dependency report into a TechnologyStack model."""
        from spark.models.tech_stack import TechnologyStack, DependencyInfo

        return TechnologyStack(
            repository_name=repository_name,
            dependencies=[
                DependencyInfo(
                    name=detail.name,
                    current_version=detail.current_version,
                    latest_version=detail.latest_version,
                    ecosystem=detail.ecosystem,
                    versions_behind=detail.versions_behind,
                    is_outdated=detail.is_outdated,
                    status=detail.status,
                    version_requirement=detail.version_requirement,
                    current_version_known=detail.current_version_known,
                    latest_version_status=detail.latest_version_status,
                    latest_version_source=detail.latest_version_source,
                    source_file=detail.source_file,
                )
                for detail in report.details
            ],
            dependency_file_type=dependency_file_type,
            languages=languages or {},
        )

    def analyze_github_repository(self, github_repo):
        """Analyze dependencies from a PyGithub repository object.

        Args:
            github_repo: PyGithub Repository instance

        Returns:
            TechnologyStack object with dependency analysis, or None if no dependencies
        """

        # Known dependency files to check
        dependency_files_to_check = [
            "package.json",  # NPM
            "requirements.txt",  # PyPI
            "pyproject.toml",  # PyPI (modern)
            "Gemfile",  # RubyGems
            "go.mod",  # Go
            "pom.xml",  # Maven
        ]

        dependency_files = {}

        # Try to fetch each dependency file
        for filename in dependency_files_to_check:
            try:
                file_content = github_repo.get_contents(filename)
                if file_content and hasattr(file_content, "decoded_content"):
                    content = file_content.decoded_content.decode("utf-8")
                    dependency_files[filename] = content
                    self.logger.debug(f"Found dependency file: {filename}")
            except Exception as e:
                # File doesn't exist or error fetching, skip
                self.logger.debug(f"Skipping {filename}: {e}")
                continue

        # Look for .csproj files (can be anywhere in root directory)
        try:
            contents = github_repo.get_contents("")
            for item in contents:
                if item.name.endswith(".csproj") and item.type == "file":
                    try:
                        file_content = github_repo.get_contents(item.name)
                        if file_content and hasattr(file_content, "decoded_content"):
                            content = file_content.decoded_content.decode("utf-8")
                            dependency_files[item.name] = content
                            self.logger.debug(f"Found .NET project file: {item.name}")
                            break  # Only process first .csproj found
                    except Exception as e:
                        self.logger.debug(f"Error reading {item.name}: {e}")
        except Exception as e:
            self.logger.debug(f"Error listing repository contents: {e}")

        if not dependency_files:
            self.logger.debug(f"No dependency files found in {github_repo.name}")
            return None

        # Analyze dependencies
        report = self.analyze_repository(dependency_files)

        if report.total_dependencies == 0:
            return None

        # Convert to TechnologyStack
        # Get primary dependency file type
        primary_file = list(dependency_files.keys())[0] if dependency_files else None

        tech_stack = self.build_technology_stack(
            repository_name=github_repo.name,
            report=report,
            dependency_file_type=primary_file,
        )

        return tech_stack
