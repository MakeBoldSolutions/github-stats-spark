"""Category-specific cache refresh execution helpers."""

import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from github import GithubException

from spark.dependencies.analyzer import RepositoryDependencyAnalyzer
from spark.logger import get_logger
from spark.models.commit import CommitHistory
from spark.models.repository import Repository
from spark.summarizer import RepositorySummarizer
from spark.time_utils import sanitize_timestamp_for_filename


@dataclass
class RefreshResult:
    """Result of a cache refresh operation."""

    repo_name: str
    category: str
    was_cached: bool
    refreshed: bool
    error: Optional[str] = None


class CacheRefreshExecutor:
    """Executes per-category cache refresh work for a repository."""

    def __init__(
        self,
        github_client,
        cache,
        summarizer: Optional[RepositorySummarizer] = None,
        fetcher=None,
        ai_model: Optional[str] = None,
    ):
        self.github = github_client
        self.cache = cache
        self.logger = get_logger()
        self._api_calls = 0
        self._api_calls_lock = threading.Lock()
        self.summarizer = summarizer
        self.ai_model = ai_model
        self.dependency_analyzer = RepositoryDependencyAnalyzer()
        self.fetcher = fetcher
        self._repo_cache: Dict[str, Any] = {}
        self._repo_cache_lock = threading.Lock()

    def _get_repo(self, username: str, repo_name: str):
        """Get a PyGithub repo object, reusing a cached instance when available."""
        key = f"{username}/{repo_name}"
        with self._repo_cache_lock:
            if key in self._repo_cache:
                return self._repo_cache[key]
        self._increment_api_calls()
        repo = self.github.get_repo(key)
        with self._repo_cache_lock:
            self._repo_cache[key] = repo
        return repo

    @property
    def api_calls(self) -> int:
        return self._api_calls

    @api_calls.setter
    def api_calls(self, value: int) -> None:
        self._api_calls = value

    def _increment_api_calls(self, count: int = 1) -> None:
        with self._api_calls_lock:
            self._api_calls += count

    @staticmethod
    def _sanitize_language_stats(language_stats: Any) -> Dict[str, int]:
        """Normalize language payload to numeric byte counts only."""
        if not isinstance(language_stats, dict):
            return {}

        sanitized: Dict[str, int] = {}
        for language, raw_value in language_stats.items():
            try:
                bytes_count = int(raw_value)
            except (TypeError, ValueError):
                continue

            if bytes_count >= 0:
                sanitized[language] = bytes_count

        return sanitized

    # ------------------------------------------------------------------
    # GraphQL batch query — fetches languages, README, quality indicators,
    # and dependency file contents in a single API call, replacing ~15+
    # individual REST calls.
    # ------------------------------------------------------------------
    _REPO_METADATA_QUERY = """
query RepoMetadata($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    licenseInfo { spdxId }
    homepageUrl
    description
    stargazerCount
    forkCount
    watchers { totalCount }
    issues(states: OPEN) { totalCount }
    closedIssues: issues(states: CLOSED) { totalCount }
    discussions { totalCount }
    releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      nodes { tagName publishedAt }
    }
    repositoryTopics(first: 10) {
      nodes { topic { name } }
    }
    languages(first: 30, orderBy: {field: SIZE, direction: DESC}) {
      edges {
        node { name }
        size
      }
    }
    readmeDefault: object(expression: "HEAD:README.md") {
      ... on Blob { text }
    }
    readmeLower: object(expression: "HEAD:readme.md") {
      ... on Blob { text }
    }
    rootEntries: object(expression: "HEAD:") {
      ... on Tree {
        entries { name type }
      }
    }
    workflowEntries: object(expression: "HEAD:.github/workflows") {
      ... on Tree {
        entries { name }
      }
    }
    packageJson: object(expression: "HEAD:package.json") {
      ... on Blob { text }
    }
    requirementsTxt: object(expression: "HEAD:requirements.txt") {
      ... on Blob { text }
    }
    pyprojectToml: object(expression: "HEAD:pyproject.toml") {
      ... on Blob { text }
    }
    gemfile: object(expression: "HEAD:Gemfile") {
      ... on Blob { text }
    }
    goMod: object(expression: "HEAD:go.mod") {
      ... on Blob { text }
    }
    pomXml: object(expression: "HEAD:pom.xml") {
      ... on Blob { text }
    }
    cargoToml: object(expression: "HEAD:Cargo.toml") {
      ... on Blob { text }
    }
    composerJson: object(expression: "HEAD:composer.json") {
      ... on Blob { text }
    }
  }
}
"""

    # GraphQL alias → dependency filename mapping
    _DEP_FILE_MAP = {
        "packageJson": "package.json",
        "requirementsTxt": "requirements.txt",
        "pyprojectToml": "pyproject.toml",
        "gemfile": "Gemfile",
        "goMod": "go.mod",
        "pomXml": "pom.xml",
        "cargoToml": "Cargo.toml",
        "composerJson": "composer.json",
    }

    def batch_refresh_repo_metadata(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> List[RefreshResult]:
        """Fetch languages, readme, quality indicators, and dependency files in one GraphQL call.

        Replaces ~15+ individual REST API calls with a single GraphQL query.
        Populates four cache categories: languages, readme, quality_indicators,
        dependency_files.
        """
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        results: List[RefreshResult] = []

        # Check which categories still need a refresh
        batch_categories = [
            "languages",
            "readme",
            "quality_indicators",
            "dependency_files",
            "community_health",
        ]
        needed = []
        for cat in batch_categories:
            cached = self.cache.get(cat, username, repo=repo_name, week=cache_key)
            if cached is not None:
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category=cat,
                        was_cached=True,
                        refreshed=False,
                    )
                )
            else:
                needed.append(cat)

        if not needed:
            return results

        if self.fetcher is None:
            for cat in needed:
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category=cat,
                        was_cached=False,
                        refreshed=False,
                        error="Fetcher required for batch metadata",
                    )
                )
            return results

        try:
            self._increment_api_calls()
            data = self.fetcher.graphql_query(
                self._REPO_METADATA_QUERY,
                {"owner": username, "name": repo_name},
            )
            repo_data = data.get("repository")
            if not repo_data:
                for cat in needed:
                    results.append(
                        RefreshResult(
                            repo_name=repo_name,
                            category=cat,
                            was_cached=False,
                            refreshed=False,
                            error="GraphQL returned no repository data",
                        )
                    )
                return results

            meta_base = {
                "repository": {"owner": username, "name": repo_name},
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }

            # --- Languages ---
            if "languages" in needed:
                lang_edges = (repo_data.get("languages") or {}).get("edges") or []
                languages: Dict[str, int] = {}
                for edge in lang_edges:
                    name = edge.get("node", {}).get("name")
                    size = edge.get("size", 0)
                    if name and isinstance(size, (int, float)) and size >= 0:
                        languages[name] = int(size)
                self.cache.set(
                    "languages",
                    username,
                    languages,
                    repo=repo_name,
                    week=cache_key,
                    metadata={**meta_base, "category": "languages"},
                )
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category="languages",
                        was_cached=False,
                        refreshed=True,
                    )
                )

            # --- README ---
            if "readme" in needed:
                readme_content = ""
                for key in ("readmeDefault", "readmeLower"):
                    blob = repo_data.get(key)
                    if blob and blob.get("text"):
                        readme_content = blob["text"]
                        break
                self.cache.set(
                    "readme",
                    username,
                    readme_content,
                    repo=repo_name,
                    week=cache_key,
                    metadata={**meta_base, "category": "readme"},
                )
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category="readme",
                        was_cached=False,
                        refreshed=True,
                    )
                )

            # --- Quality Indicators ---
            if "quality_indicators" in needed:
                has_license = repo_data.get("licenseInfo") is not None

                workflow_tree = repo_data.get("workflowEntries")
                has_ci_cd = bool(workflow_tree and workflow_tree.get("entries"))

                root_tree = repo_data.get("rootEntries")
                root_entries = (root_tree.get("entries") or []) if root_tree else []

                test_dirs = {"test", "tests", "spec", "specs", "__tests__"}
                doc_dirs = {"docs", "doc", "documentation"}
                doc_files = {"contributing.md", "changelog.md"}

                has_tests = False
                has_docs = False
                for entry in root_entries:
                    name_lower = entry.get("name", "").lower()
                    entry_type = entry.get("type", "")
                    if entry_type == "tree":
                        if name_lower in test_dirs:
                            has_tests = True
                        if name_lower in doc_dirs:
                            has_docs = True
                    elif entry_type == "blob" and name_lower in doc_files:
                        has_docs = True

                self.cache.set(
                    "quality_indicators",
                    username,
                    {
                        "has_license": has_license,
                        "has_ci_cd": has_ci_cd,
                        "has_tests": has_tests,
                        "has_docs": has_docs,
                    },
                    repo=repo_name,
                    week=cache_key,
                    metadata={**meta_base, "category": "quality_indicators"},
                )
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category="quality_indicators",
                        was_cached=False,
                        refreshed=True,
                    )
                )

            # --- Dependency Files ---
            if "dependency_files" in needed:
                dependency_files: Dict[str, str] = {}
                for gql_key, filename in self._DEP_FILE_MAP.items():
                    blob = repo_data.get(gql_key)
                    if blob and blob.get("text"):
                        dependency_files[filename] = blob["text"]

                # Handle *.csproj: check root tree for .csproj files
                root_tree = repo_data.get("rootEntries")
                if root_tree:
                    for entry in root_tree.get("entries") or []:
                        if entry.get("type") == "blob" and entry.get(
                            "name", ""
                        ).endswith(".csproj"):
                            try:
                                repo_obj = self._get_repo(username, repo_name)
                                self._increment_api_calls()
                                file_content = repo_obj.get_contents(entry["name"])
                                dependency_files[entry["name"]] = (
                                    file_content.decoded_content.decode("utf-8")
                                )
                            except Exception:
                                pass

                self.cache.set(
                    "dependency_files",
                    username,
                    dependency_files,
                    repo=repo_name,
                    week=cache_key,
                    metadata={**meta_base, "category": "dependency_files"},
                )
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category="dependency_files",
                        was_cached=False,
                        refreshed=True,
                    )
                )

            # --- Community Health ---
            if "community_health" in needed:
                # Releases
                releases_data = repo_data.get("releases") or {}
                release_count = releases_data.get("totalCount", 0)
                release_nodes = releases_data.get("nodes") or []
                latest_release = None
                latest_release_tag = None
                if release_nodes:
                    latest_release = release_nodes[0].get("publishedAt")
                    latest_release_tag = release_nodes[0].get("tagName")

                # Issues
                open_issues = (repo_data.get("issues") or {}).get("totalCount", 0)
                closed_issues = (repo_data.get("closedIssues") or {}).get(
                    "totalCount", 0
                )
                total_issues = open_issues + closed_issues
                issue_close_ratio = (
                    round(closed_issues / total_issues, 2) if total_issues > 0 else None
                )

                # Social signals
                stargazer_count = repo_data.get("stargazerCount", 0)
                fork_count = repo_data.get("forkCount", 0)
                watcher_count = (repo_data.get("watchers") or {}).get("totalCount", 0)

                # Discussions
                has_discussions = (repo_data.get("discussions") or {}).get(
                    "totalCount", 0
                ) > 0

                # Topics
                topics_data = (repo_data.get("repositoryTopics") or {}).get(
                    "nodes"
                ) or []
                topics = [
                    n.get("topic", {}).get("name")
                    for n in topics_data
                    if n.get("topic", {}).get("name")
                ]

                # Description
                description = repo_data.get("description") or ""

                # Homepage
                homepage_url = repo_data.get("homepageUrl") or ""

                # Community files (from root tree already fetched)
                root_tree = repo_data.get("rootEntries")
                root_entries = (root_tree.get("entries") or []) if root_tree else []
                has_code_of_conduct = False
                has_contributing = False
                has_security_policy = False
                for entry in root_entries:
                    name_lower = entry.get("name", "").lower()
                    if name_lower in {"code_of_conduct.md", "code_of_conduct"}:
                        has_code_of_conduct = True
                    if name_lower in {"contributing.md", "contributing"}:
                        has_contributing = True
                    if name_lower in {"security.md", "security"}:
                        has_security_policy = True

                # README quality score (derived from already-fetched content)
                readme_score = self._compute_readme_quality_score(repo_data)

                # Homepage health check (lightweight HEAD request)
                homepage_status = None
                homepage_response_ms = None
                if homepage_url and homepage_url.startswith("http"):
                    homepage_status, homepage_response_ms = self._check_homepage(
                        homepage_url
                    )

                community_health = {
                    "stargazer_count": stargazer_count,
                    "fork_count": fork_count,
                    "watcher_count": watcher_count,
                    "open_issues": open_issues,
                    "closed_issues": closed_issues,
                    "issue_close_ratio": issue_close_ratio,
                    "has_discussions": has_discussions,
                    "topics": topics,
                    "description": description,
                    "homepage_url": homepage_url,
                    "homepage_status": homepage_status,
                    "homepage_response_ms": homepage_response_ms,
                    "release_count": release_count,
                    "latest_release_tag": latest_release_tag,
                    "latest_release_date": latest_release,
                    "has_code_of_conduct": has_code_of_conduct,
                    "has_contributing": has_contributing,
                    "has_security_policy": has_security_policy,
                    "readme_quality_score": readme_score,
                }

                self.cache.set(
                    "community_health",
                    username,
                    community_health,
                    repo=repo_name,
                    week=cache_key,
                    metadata={**meta_base, "category": "community_health"},
                )
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category="community_health",
                        was_cached=False,
                        refreshed=True,
                    )
                )

            return results
        except Exception as error:
            self.logger.warning(
                f"Batch metadata refresh failed for {repo_name}: {error}"
            )
            for cat in needed:
                results.append(
                    RefreshResult(
                        repo_name=repo_name,
                        category=cat,
                        was_cached=False,
                        refreshed=False,
                        error=str(error),
                    )
                )
            return results

    def _fetch_commit_activity_with_retry(
        self, repo, repo_name: str, max_retries: int = 4
    ):
        """Fetch commit activity stats via direct REST to avoid PyGithub's infinite 202 retry.

        PyGithub internally retries 202 responses recursively with no limit,
        which can block for minutes.  This method uses the REST endpoint
        directly with controlled exponential backoff: 1s, 2s, 4s, 8s.

        Returns a list of dicts with keys: week (int), total (int), days (list[int]).
        """
        import time

        if self.fetcher is None:
            self.logger.warning(f"No fetcher available for commit_activity {repo_name}")
            return None

        full_name = repo.full_name if hasattr(repo, "full_name") else str(repo)

        for attempt in range(max_retries):
            backoff = 2**attempt  # 1, 2, 4, 8
            try:
                self._increment_api_calls()
                resp = self.fetcher._rest_get(
                    f"/repos/{full_name}/stats/commit_activity",
                    include_version=True,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        return data
                    return None
                if resp.status_code == 202:
                    self.logger.debug(
                        f"Commit activity stats not ready for {repo_name}, "
                        f"retry {attempt + 1}/{max_retries} in {backoff}s"
                    )
                elif resp.status_code == 403:
                    self.logger.warning(
                        f"Secondary rate limit (403) fetching commit_activity for {repo_name} "
                        f"(attempt {attempt + 1}/{max_retries}); retrying in {backoff}s"
                    )
                else:
                    self.logger.warning(
                        f"Unexpected status {resp.status_code} fetching commit_activity for {repo_name}"
                    )
                    return None
            except Exception as exc:
                self.logger.warning(
                    f"Error fetching commit_activity for {repo_name}: {exc}"
                )
                return None
            time.sleep(backoff)
        return None

    def _count_commits_via_pagination(self, repo, repo_name: str):
        """Count commits by paginating /repos/{owner}/{repo}/commits.

        Used as a fallback when GitHub's /stats/commit_activity endpoint
        returns 202 (still computing) or an empty payload — common for
        brand-new repositories. Caps at 1000 commits to limit API usage.

        Returns dict with total / recent_90d / recent_180d / recent_365d /
        last_commit_date, or None on failure.
        """
        from datetime import timedelta

        try:
            now = datetime.now(timezone.utc)
            day_90_ago = now - timedelta(days=90)
            day_180_ago = now - timedelta(days=180)
            day_365_ago = now - timedelta(days=365)

            total_commits = 0
            commits_90d = 0
            commits_180d = 0
            commits_365d = 0
            last_commit_date = None
            daily_commits: dict = {}

            self._increment_api_calls()
            commits = repo.get_commits()
            for commit in commits:
                if total_commits >= 1000:
                    break
                total_commits += 1
                try:
                    commit_date = (
                        commit.commit.author.date
                        if commit.commit and commit.commit.author
                        else None
                    )
                except (AttributeError, IndexError):
                    continue
                if not commit_date:
                    continue
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=timezone.utc)
                if last_commit_date is None or commit_date > last_commit_date:
                    last_commit_date = commit_date
                if commit_date >= day_90_ago:
                    commits_90d += 1
                if commit_date >= day_180_ago:
                    commits_180d += 1
                if commit_date >= day_365_ago:
                    commits_365d += 1
                day_key = commit_date.strftime("%Y-%m-%d")
                daily_commits[day_key] = daily_commits.get(day_key, 0) + 1

            return {
                "total": total_commits,
                "recent_90d": commits_90d,
                "recent_180d": commits_180d,
                "recent_365d": commits_365d,
                "last_commit_date": last_commit_date,
                "daily_commits": daily_commits,
            }
        except Exception as exc:
            self.logger.warning(
                f"Pagination fallback for commit_counts failed for {repo_name}: {exc}"
            )
            return None

    def refresh_commit_counts(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "commit_counts"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached:
            # If the cached entry already has daily_commits (new format), use it
            if isinstance(cached.get("daily_commits"), dict):
                return RefreshResult(
                    repo_name=repo_name,
                    category=category,
                    was_cached=True,
                    refreshed=False,
                )
            # Older cache entries lack daily_commits — re-fetch to upgrade format
            self.logger.info(
                f"Upgrading {repo_name}/commit_counts cache to include daily_commits"
            )

        try:
            repo = self._get_repo(username, repo_name)

            # Use GitHub Statistics API — returns 52 weekly buckets in 1 call
            # instead of iterating individual commits (~34 paginated API calls).
            weekly_stats = self._fetch_commit_activity_with_retry(repo, repo_name)

            now = datetime.now(timezone.utc)
            total_commits = 0
            commits_90d = 0
            commits_180d = 0
            commits_365d = 0
            last_commit_date = None
            daily_commits: dict = {}  # "YYYY-MM-DD" -> commit count

            if weekly_stats:
                for week_stat in weekly_stats:
                    # REST returns dicts; PyGithub returns objects — support both
                    w = week_stat if isinstance(week_stat, dict) else week_stat.__dict__
                    week_ts = (
                        w.get("week", 0)
                        if isinstance(w, dict)
                        else getattr(week_stat, "week", 0)
                    )
                    week_total = (
                        w.get("total", 0)
                        if isinstance(w, dict)
                        else getattr(week_stat, "total", 0)
                    )
                    days_list = (
                        w.get("days", [])
                        if isinstance(w, dict)
                        else getattr(week_stat, "days", [])
                    )
                    week_start = datetime.fromtimestamp(week_ts, tz=timezone.utc)
                    total_commits += week_total

                    age_days = (now - week_start).days
                    if age_days <= 90:
                        commits_90d += week_total
                    if age_days <= 180:
                        commits_180d += week_total
                    if age_days <= 365:
                        commits_365d += week_total

                    # Build daily_commits map and find last commit date
                    # days[] has Sun=0..Sat=6 counts
                    for day_offset, day_count in enumerate(days_list[:7]):
                        if day_count > 0:
                            day = week_start + timedelta(days=day_offset)
                            day_key = day.strftime("%Y-%m-%d")
                            daily_commits[day_key] = (
                                daily_commits.get(day_key, 0) + day_count
                            )
                            if last_commit_date is None or day > last_commit_date:
                                last_commit_date = day
            else:
                # GitHub's /stats/commit_activity returned empty/202 — fall back to
                # paginated commit walk so we never persist zero counts for a repo
                # that actually has commits (GitHub computes stats lazily).
                self.logger.warning(
                    f"Commit activity stats unavailable for {repo_name}; "
                    f"falling back to paginated commit walk"
                )
                fallback = self._count_commits_via_pagination(repo, repo_name)
                if fallback is not None:
                    total_commits = fallback["total"]
                    commits_90d = fallback["recent_90d"]
                    commits_180d = fallback["recent_180d"]
                    commits_365d = fallback["recent_365d"]
                    last_commit_date = fallback["last_commit_date"]
                    daily_commits = fallback.get("daily_commits", {})
                else:
                    self.logger.warning(
                        f"Pagination fallback also failed for {repo_name}; using zero counts"
                    )

            result = {
                "total": total_commits,
                "recent_90d": commits_90d,
                "recent_180d": commits_180d,
                "recent_365d": commits_365d,
                "last_commit_date": (
                    last_commit_date.isoformat()
                    if isinstance(last_commit_date, datetime)
                    else last_commit_date
                ),
                "daily_commits": daily_commits,
            }
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                result,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_commits_stats(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "commits_stats"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        if self.fetcher is None:
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error="Fetcher is required for commit stats refresh",
            )

        try:
            self.fetcher.fetch_commits_with_stats(
                username=username,
                repo_name=repo_name,
                repo_pushed_at=pushed_at,
                force_refresh=True,
            )
            refreshed_cache = self.cache.get(
                category, username, repo=repo_name, week=cache_key
            )
            if refreshed_cache is None:
                return RefreshResult(
                    repo_name=repo_name,
                    category=category,
                    was_cached=False,
                    refreshed=False,
                    error="Commit stats were not written to cache",
                )

            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_languages(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "languages"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        try:
            repo = self._get_repo(username, repo_name)
            self._increment_api_calls()
            languages = self._sanitize_language_stats(repo.get_languages())
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                languages,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_readme(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "readme"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        try:
            repo = self._get_repo(username, repo_name)
            self._increment_api_calls()
            content = ""
            try:
                readme = repo.get_readme()
                content = readme.decoded_content.decode("utf-8")
            except GithubException as error:
                if getattr(error, "status", None) != 404:
                    raise

            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                content,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_quality_indicators(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "quality_indicators"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        try:
            repo = self._get_repo(username, repo_name)

            has_license = False
            try:
                repo.get_license()
                has_license = True
            except GithubException as error:
                if getattr(error, "status", None) != 404:
                    raise

            has_ci_cd = False
            try:
                workflows = repo.get_workflows()
                has_ci_cd = workflows.totalCount > 0
            except GithubException:
                pass

            has_tests = False
            has_docs = False
            test_dirs = {"test", "tests", "spec", "specs", "__tests__"}
            doc_dirs = {"docs", "doc", "documentation"}
            doc_files = {"contributing.md", "changelog.md"}

            try:
                contents = repo.get_contents("")
                for item in contents:
                    name_lower = item.name.lower()
                    if item.type == "dir":
                        if name_lower in test_dirs:
                            has_tests = True
                        if name_lower in doc_dirs:
                            has_docs = True
                    elif item.type == "file" and name_lower in doc_files:
                        has_docs = True
            except GithubException:
                pass

            quality_data = {
                "has_license": has_license,
                "has_ci_cd": has_ci_cd,
                "has_tests": has_tests,
                "has_docs": has_docs,
            }
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                quality_data,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_dependency_files(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "dependency_files"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        dependency_files: Dict[str, str] = {}
        target_files = [
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Gemfile",
            "go.mod",
            "pom.xml",
            "*.csproj",
            "Cargo.toml",
            "composer.json",
        ]

        try:
            repo = self._get_repo(username, repo_name)
            for filename in target_files:
                try:
                    if "*" in filename:
                        contents = repo.get_contents("")
                        pattern = filename.replace("*", "")
                        for item in contents:
                            if item.name.endswith(pattern):
                                dependency_files[item.name] = (
                                    item.decoded_content.decode("utf-8")
                                )
                    else:
                        file_content = repo.get_contents(filename)
                        dependency_files[filename] = (
                            file_content.decoded_content.decode("utf-8")
                        )
                except GithubException as error:
                    if getattr(error, "status", None) == 404:
                        continue
                    raise
                except Exception:
                    continue

            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                dependency_files,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_ai_summary(
        self, username: str, repo_data: Dict[str, Any], pushed_at: datetime
    ) -> RefreshResult:
        repo_name = repo_data["name"]
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "ai_summary"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        if self.summarizer is None:
            if self.ai_model is None:
                from spark.exceptions import ConfigurationError

                raise ConfigurationError(
                    "CacheRefreshExecutor requires ai_model for AI summary generation. "
                    "Set analyzer.ai_model in spark.yml.",
                    field="analyzer.ai_model",
                )
            self.summarizer = RepositorySummarizer(
                cache=self.cache, model=self.ai_model
            )

        try:
            commit_data = self.cache.get(
                "commit_counts", username, repo=repo_name, week=cache_key
            )
            if commit_data is None:
                self.refresh_commit_counts(username, repo_name, pushed_at)
                commit_data = (
                    self.cache.get(
                        "commit_counts", username, repo=repo_name, week=cache_key
                    )
                    or {}
                )

            language_stats = self.cache.get(
                "languages", username, repo=repo_name, week=cache_key
            )
            if language_stats is None:
                self.refresh_languages(username, repo_name, pushed_at)
                language_stats = (
                    self.cache.get(
                        "languages", username, repo=repo_name, week=cache_key
                    )
                    or {}
                )
            language_stats = self._sanitize_language_stats(language_stats)

            readme_content = self.cache.get(
                "readme", username, repo=repo_name, week=cache_key
            )
            if readme_content is None:
                self.refresh_readme(username, repo_name, pushed_at)
                readme_content = (
                    self.cache.get("readme", username, repo=repo_name, week=cache_key)
                    or ""
                )

            dependency_files = self.cache.get(
                "dependency_files", username, repo=repo_name, week=cache_key
            )
            if dependency_files is None:
                self.refresh_dependency_files(username, repo_name, pushed_at)
                dependency_files = (
                    self.cache.get(
                        "dependency_files", username, repo=repo_name, week=cache_key
                    )
                    or {}
                )

            tech_stack = None
            if dependency_files:
                dep_report = self.dependency_analyzer.analyze_repository(
                    dependency_files
                )
                if dep_report.total_dependencies > 0:
                    tech_stack = self.dependency_analyzer.build_technology_stack(
                        repository_name=repo_name,
                        report=dep_report,
                    )

            repo = Repository.from_dict(repo_data)
            repo.language_stats = language_stats or {}
            repo.language_count = len(repo.language_stats)
            repo.has_readme = bool(readme_content)

            commit_data["repository_name"] = repo_name
            commit_history = (
                CommitHistory.from_dict(commit_data) if commit_data else None
            )

            summary = self.summarizer.summarize_repository(
                repo=repo,
                readme_content=readme_content or None,
                commit_history=commit_history,
                language_stats=language_stats,
                tech_stack=tech_stack,
                repository_owner=username,
                repo_pushed_at=pushed_at,
                write_cache=False,
            )

            if summary.ai_summary:
                cache_payload = {
                    "ai_summary": summary.ai_summary,
                    "generation_method": summary.generation_method,
                    "generation_timestamp": (
                        summary.generation_timestamp.isoformat()
                        if summary.generation_timestamp
                        else datetime.now().isoformat()
                    ),
                    "model_used": summary.model_used,
                    "tokens_used": summary.tokens_used,
                    "confidence_score": summary.confidence_score,
                }
                metadata = self.summarizer._build_cache_metadata(
                    repo_name=repo_name,
                    repository_owner=username,
                    cache_date=pushed_at,
                )
                self.cache.set(
                    category,
                    username,
                    cache_payload,
                    repo=repo_name,
                    week=cache_key,
                    metadata=metadata,
                )
                return RefreshResult(
                    repo_name=repo_name,
                    category=category,
                    was_cached=False,
                    refreshed=True,
                )

            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_pull_request_summary(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "pull_request_summary"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        if self.fetcher is None:
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error="Fetcher is required for pull request enrichment refresh",
            )

        try:
            summary = self.fetcher.fetch_pull_request_summary(
                username=username,
                repo_name=repo_name,
                repo_pushed_at=pushed_at,
                force_refresh=True,
            )
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                summary,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            self._increment_api_calls()
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_security_summary(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "security_summary"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        if self.fetcher is None:
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error="Fetcher is required for security enrichment refresh",
            )

        try:
            summary = self.fetcher.fetch_security_summary(
                username=username,
                repo_name=repo_name,
                repo_pushed_at=pushed_at,
                force_refresh=True,
            )
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                summary,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            self._increment_api_calls()
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_diagnostics_summary(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "diagnostics_summary"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        if self.fetcher is None:
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error="Fetcher is required for diagnostics enrichment refresh",
            )

        try:
            summary = self.fetcher.fetch_diagnostics_summary(
                username=username,
                repo_name=repo_name,
                repo_pushed_at=pushed_at,
                force_refresh=True,
            )
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                summary,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            self._increment_api_calls()
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    # ------------------------------------------------------------------
    # Web scraping — extracts signals from public GitHub pages without
    # consuming API rate limits.
    # ------------------------------------------------------------------

    def refresh_web_signals(
        self, username: str, repo_name: str, pushed_at: datetime
    ) -> RefreshResult:
        """Scrape the public GitHub page for signals not in the API."""
        from spark.web_scraper import scrape_repo_signals

        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "web_signals"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        try:
            signals = scrape_repo_signals(username, repo_name)
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                signals,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    def refresh_homepage_health(
        self, username: str, repo_name: str, pushed_at: datetime, homepage_url: str
    ) -> RefreshResult:
        """Check the health of a repository's homepage URL."""
        from spark.web_scraper import check_homepage_health

        cache_key = sanitize_timestamp_for_filename(pushed_at)
        category = "homepage_health"
        cached = self.cache.get(category, username, repo=repo_name, week=cache_key)
        if cached is not None:
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=True, refreshed=False
            )

        try:
            health = check_homepage_health(homepage_url)
            metadata = {
                "repository": {"owner": username, "name": repo_name},
                "category": category,
                "pushed_at": pushed_at.isoformat(),
                "ttl_enforced": False,
            }
            self.cache.set(
                category,
                username,
                health,
                repo=repo_name,
                week=cache_key,
                metadata=metadata,
            )
            return RefreshResult(
                repo_name=repo_name, category=category, was_cached=False, refreshed=True
            )
        except Exception as error:
            self.logger.warning(
                f"Failed to refresh {category} for {repo_name}: {error}"
            )
            return RefreshResult(
                repo_name=repo_name,
                category=category,
                was_cached=False,
                refreshed=False,
                error=str(error),
            )

    # ------------------------------------------------------------------
    # Derived scores — computed from already-cached data, no API calls.
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_readme_quality_score(repo_data: dict) -> dict:
        """Compute a quality score from README content (already in GraphQL response).

        Scoring (0-100):
          - Length: up to 20 points (1pt per 200 chars, max 4000+)
          - Headings: up to 20 points (4pt per heading, max 5+)
          - Code blocks: up to 15 points (5pt per block, max 3+)
          - Links: up to 15 points (3pt per link, max 5+)
          - Images/badges: up to 15 points (5pt per image, max 3+)
          - Has install/usage section: 15 points
        """
        import re as _re

        readme_text = ""
        for key in ("readmeDefault", "readmeLower"):
            blob = repo_data.get(key)
            if blob and blob.get("text"):
                readme_text = blob["text"]
                break

        if not readme_text:
            return {
                "score": 0,
                "length": 0,
                "has_headings": False,
                "has_code_blocks": False,
                "has_images": False,
                "has_install_section": False,
            }

        length = len(readme_text)
        headings = len(_re.findall(r"^#{1,3}\s+", readme_text, _re.MULTILINE))
        code_blocks = len(_re.findall(r"```", readme_text)) // 2
        links = len(_re.findall(r"\[([^\]]+)\]\(([^)]+)\)", readme_text))
        images = len(_re.findall(r"!\[", readme_text))

        install_keywords = {
            "install",
            "getting started",
            "usage",
            "quick start",
            "setup",
        }
        has_install = any(kw in readme_text.lower() for kw in install_keywords)

        score = 0
        score += min(20, length // 200)
        score += min(20, headings * 4)
        score += min(15, code_blocks * 5)
        score += min(15, links * 3)
        score += min(15, images * 5)
        if has_install:
            score += 15

        return {
            "score": min(100, score),
            "length": length,
            "has_headings": headings > 0,
            "has_code_blocks": code_blocks > 0,
            "has_images": images > 0,
            "has_install_section": has_install,
        }

    @staticmethod
    def _check_homepage(url: str) -> tuple:
        """Quick HEAD check on a URL. Returns (status_code, response_ms)."""
        import time as _time
        import requests as _requests

        try:
            t0 = _time.time()
            resp = _requests.head(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
                allow_redirects=True,
            )
            elapsed_ms = int((_time.time() - t0) * 1000)
            return resp.status_code, elapsed_ms
        except Exception:
            return None, None
