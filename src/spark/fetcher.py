"""GitHub API data fetching with rate limiting and caching.

# SIZE JUSTIFICATION (Constitution I — ~834 LOC as of 2026-04-02):
# This module consolidates REST fallback logic, caching integration, rate-limit
# handling, and all fetch paths (commits, languages, PRs, security, dependencies)
# in one place to keep the GitHub interaction surface unified and testable as a
# single unit.  Planned split: fetch_commits.py, fetch_security.py,
# fetch_pull_requests.py — tracked in CAP-2026-001.
"""

import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import requests

from github import Auth, Github, GithubException
from github.Repository import Repository

from spark.cache import APICache
from spark.cache_status import CacheStatusTracker
from spark.logger import get_logger
from spark.time_utils import sanitize_timestamp_for_filename


class GitHubFetcher:
    """Fetches GitHub user data with rate limiting and caching."""

    def __init__(
        self,
        token: Optional[str] = None,
        cache: Optional[APICache] = None,
        max_repos: int = 500,
        use_cache_status: bool = True,
        api_version_settings: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the GitHub API fetcher.

        Args:
            token: GitHub Personal Access Token (uses GITHUB_TOKEN env var if not provided)
            cache: API cache instance (creates new if not provided)
            max_repos: Maximum number of repositories to process
            use_cache_status: Whether to use cache status tracking to skip cached repos
        """
        self.logger = get_logger()
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GitHub token required (GITHUB_TOKEN environment variable or token parameter)"
            )

        self.github = Github(auth=Auth.Token(self.token), timeout=30)
        self.cache = cache or APICache()
        self.cache_status_tracker = CacheStatusTracker(
            cache_dir=str(self.cache.cache_dir)
        )
        self.max_repos = max_repos
        self.use_cache_status = use_cache_status
        self.api_version_settings: Dict[str, Any] = {
            "enabled": False,
            "version": "2026-03-10",
            "fallback_to_default": True,
        }
        if api_version_settings:
            self.api_version_settings.update(api_version_settings)

    def _build_rest_headers(self, include_version: bool = True) -> Dict[str, str]:
        """Build headers for direct REST API calls."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }
        if include_version and self.api_version_settings.get("enabled", False):
            headers["X-GitHub-Api-Version"] = self.api_version_settings.get(
                "version", "2026-03-10"
            )
        return headers

    def _rest_get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        include_version: bool = True,
    ) -> requests.Response:
        """Issue direct REST API GET request with optional version-header fallback."""
        url = f"https://api.github.com{path}"
        response = requests.get(
            url,
            headers=self._build_rest_headers(include_version=include_version),
            params=params,
            timeout=30,
        )
        if response.status_code < 400:
            return response

        # Fallback once to default API version when staged version is enabled.
        if (
            include_version
            and self.api_version_settings.get("enabled", False)
            and self.api_version_settings.get("fallback_to_default", True)
            and response.status_code in {400, 404, 415, 422}
        ):
            self.logger.warning(
                f"API version request failed for {path} ({response.status_code}); retrying without explicit version header"
            )
            fallback = requests.get(
                url,
                headers=self._build_rest_headers(include_version=False),
                params=params,
                timeout=30,
            )
            return fallback

        return response

    def graphql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GitHub GraphQL API query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            The ``data`` portion of the response, or an empty dict on error.
        """
        url = "https://api.github.com/graphql"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )
        if response.status_code >= 400:
            self.logger.warning(
                f"GraphQL request failed ({response.status_code}): "
                f"{response.text[:200]}"
            )
            return {}
        result = response.json()
        if "errors" in result:
            self.logger.warning(f"GraphQL errors: {result['errors'][:3]}")
        return result.get("data", {})

    @staticmethod
    def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _map_failure_reason(status_code: int) -> str:
        if status_code in {401, 403}:
            return "permission_denied"
        if status_code == 404:
            return "not_supported"
        if status_code == 0:
            return "unknown"
        return "api_error"

    def _build_repo_metadata(
        self,
        username: str,
        repo_name: str,
        repo_pushed_at: Optional[datetime],
        category: str,
    ) -> Dict[str, Any]:
        """Create metadata for repository cache entries."""

        pushed_at_iso = None
        if repo_pushed_at:
            pushed_at_iso = repo_pushed_at.isoformat()

        return {
            "repository": {"owner": username, "name": repo_name},
            "category": category,
            "pushed_at": pushed_at_iso,
            "ttl_enforced": False,
        }

    @staticmethod
    def _should_include_repository(
        repo: Repository,
        exclude_private: bool,
        exclude_forks: bool,
        exclude_archived: bool,
    ) -> bool:
        """Apply repository include/exclude policy checks."""
        if exclude_private and repo.private:
            return False
        if exclude_forks and repo.fork:
            return False
        if exclude_archived and repo.archived:
            return False
        return True

    @staticmethod
    def _serialize_repository(repo: Repository) -> Dict[str, Any]:
        """Normalize PyGithub repository object into cache-friendly dictionary."""
        return {
            "name": repo.name,
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "watchers": repo.watchers_count,
            "size": repo.size,
            "created_at": repo.created_at.isoformat() if repo.created_at else None,
            "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
            "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
            "is_fork": repo.fork,
            "is_private": repo.private,
            "is_archived": repo.archived,
            "homepage": repo.homepage,
            "has_pages": repo.has_pages,
        }

    @staticmethod
    def _sanitize_language_stats(language_stats: Any) -> Dict[str, int]:
        """Keep only numeric language-byte entries from GitHub language payloads.

        Some API/client versions may include metadata keys (for example ``url``)
        in the same dictionary as language byte counts. This normalizes the
        payload so downstream consumers only see ``{language_name: int_bytes}``.
        """
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

    def get_user(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Get GitHub user information (alias for fetch_user_profile for backwards compatibility).

        Args:
            username: GitHub username (optional, uses authenticated user if not provided)

        Returns:
            User profile data dictionary
        """
        # If no username provided, get authenticated user
        if not username:
            try:
                user = self.github.get_user()
                return {
                    "login": user.login,
                    "name": user.name or user.login,
                    "bio": user.bio,
                    "avatar_url": user.avatar_url,
                    "html_url": user.html_url,
                    "public_repos": user.public_repos,
                    "followers": user.followers,
                    "following": user.following,
                }
            except GithubException as e:
                self.logger.error(f"Failed to fetch authenticated user: {e}")
                raise

        return self.fetch_user_profile(username)

    def fetch_user_profile(self, username: str) -> Dict[str, Any]:
        """Fetch GitHub user profile information.

        Args:
            username: GitHub username

        Returns:
            User profile data dictionary
        """
        cached = self.cache.get("user_profile", username)
        if cached:
            self.logger.debug(f"Using cached user profile for {username}")
            return cached

        self.logger.info(f"Fetching user profile for {username}")

        try:
            user = self.github.get_user(username)

            profile_data = {
                "login": user.login,
                "username": user.login,
                "name": user.name or user.login,
                "bio": user.bio,
                "company": user.company,
                "location": user.location,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "html_url": user.html_url,
                "public_repos": user.public_repos,
                "followers": user.followers,
                "following": user.following,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            }

            # Cache writes now handled by CacheManager
            return profile_data

        except GithubException as e:
            self.logger.error(f"Failed to fetch user profile for {username}: {e}")
            raise

    def fetch_repositories(
        self,
        username: str,
        exclude_private: bool = True,
        exclude_forks: bool = True,
        exclude_archived: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch user repositories with pagination.

        Args:
            username: GitHub username
            exclude_private: Exclude private repositories
            exclude_forks: Exclude forked repositories
            exclude_archived: Exclude archived repositories

        Returns:
            List of repository data dictionaries
        """
        variant = f"list_{exclude_private}_{exclude_forks}_{exclude_archived}"
        cached = self.cache.get("repositories", username, repo=variant)
        if cached:
            self.logger.debug(f"Using cached repositories for {username}")
            return cached

        self.logger.info(f"Fetching repositories for {username}")

        try:
            user = self.github.get_user(username)
            repos: List[Dict[str, Any]] = []

            for repo in user.get_repos():
                if not self._should_include_repository(
                    repo,
                    exclude_private=exclude_private,
                    exclude_forks=exclude_forks,
                    exclude_archived=exclude_archived,
                ):
                    continue

                # Stop if we've hit the max
                if len(repos) >= self.max_repos:
                    self.logger.warning(
                        f"Reached maximum repository limit ({self.max_repos})"
                    )
                    break

                repos.append(self._serialize_repository(repo))

            # Cache writes now handled by CacheManager
            self.logger.info(f"Fetched {len(repos)} repositories")
            return repos

        except GithubException as e:
            self.logger.error(f"Failed to fetch repositories for {username}: {e}")
            raise

    def fetch_commits(
        self,
        username: str,
        repo_name: str,
        max_commits: int = 200,
        repo_pushed_at: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch commits for a repository.

        Args:
            username: Repository owner username
            repo_name: Repository name
            max_commits: Maximum commits to fetch per repository
            repo_pushed_at: Last push date (for cache invalidation)

        Returns:
            List of commit data dictionaries
        """
        # Use pushed_at hash for cache key (change-based invalidation, not time-based)
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        self.logger.debug(
            f"fetch_commits cache lookup: {username}/{repo_name} with key={push_key}"
        )
        cached = self.cache.get("commits", username, repo=repo_name, week=push_key)
        if cached:
            self.logger.debug(f"Cache HIT for commits: {username}/{repo_name}")
            return cached

        self.logger.debug(
            f"Cache MISS for commits: {username}/{repo_name}, fetching from GitHub..."
        )
        self.logger.debug(f"Fetching commits for {username}/{repo_name}")

        try:
            repo = self.github.get_repo(f"{username}/{repo_name}")
            commits: List[Dict[str, Any]] = []

            for commit in repo.get_commits(author=username):
                if len(commits) >= max_commits:
                    break

                commit_data = {
                    "sha": commit.sha,
                    "message": commit.commit.message,
                    "author": (
                        commit.commit.author.name if commit.commit.author else username
                    ),
                    "date": (
                        commit.commit.author.date.isoformat()
                        if commit.commit.author
                        else None
                    ),
                    "repo": repo_name,
                }
                commits.append(commit_data)

            # Cache writes now handled by CacheManager
            return commits

        except GithubException as e:
            self.logger.debug(f"Could not fetch commits for {repo_name}: {e}")
            return []

    def fetch_commits_with_stats(
        self,
        username: str,
        repo_name: str,
        max_commits: int = 50,
        repo_pushed_at: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch a sample of commits with detailed statistics for dashboard metrics.

        Fetches commit data including files changed, lines added, and lines
        deleted.  Defaults to 50 commits (enough for commit-size distribution
        sampling) to limit API calls.

        Args:
            username: Repository owner username
            repo_name: Repository name
            max_commits: Maximum commits to fetch per repository (default 50)
            repo_pushed_at: Last push date (for cache invalidation)
            force_refresh: Force refresh even if cache is valid

        Returns:
            List of commit dictionaries with 'stats' field containing:
            - total: Number of files changed
            - additions: Lines added
            - deletions: Lines deleted
        """
        # Include push date in cache key for smart invalidation
        # Use pushed_at hash for cache key (change-based invalidation, not time-based)
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)

        # Check cache status if enabled and not forcing refresh
        if self.use_cache_status and not force_refresh:
            pushed_at_str = repo_pushed_at.isoformat() if repo_pushed_at else None
            cache_status = self.cache_status_tracker.get_repository_cache_status(
                username=username,
                repo_name=repo_name,
                pushed_at=pushed_at_str,
            )

            # If refresh not needed and cache exists, return cached data
            if not cache_status.get("refresh_needed", True):
                cached = self.cache.get(
                    "commits_stats", username, repo=repo_name, week=push_key
                )
                if cached:
                    self.logger.info(
                        f"Skipping {repo_name} - cache is up-to-date (age: {cache_status.get('cache_age_hours', 0):.1f}h)"
                    )
                    return cached

        cached = self.cache.get(
            "commits_stats", username, repo=repo_name, week=push_key
        )
        if cached:
            self.logger.debug(
                f"Using cached commit stats for {username}/{repo_name} (pushed_at: {push_key})"
            )
            return cached

        self.logger.info(
            f"Fetching commit statistics for {username}/{repo_name} (max: {max_commits})"
        )

        try:
            repo = self.github.get_repo(f"{username}/{repo_name}")
            commits_with_stats: List[Dict[str, Any]] = []

            # Get commits - do not filter by author here as GitHub API's author parameter is flaky
            for i, commit in enumerate(repo.get_commits()):
                if len(commits_with_stats) >= max_commits:
                    break

                try:
                    # Fetch detailed commit data with stats
                    # Note: commit.stats may be None for some commits
                    files_count = 0
                    additions = 0
                    deletions = 0

                    try:
                        if hasattr(commit, "stats") and commit.stats:
                            additions = commit.stats.additions
                            deletions = commit.stats.deletions
                            # Files count is the sum of changed files
                            files_count = (
                                commit.stats.total
                                if hasattr(commit.stats, "total")
                                else 0
                            )
                    except Exception as stats_err:
                        self.logger.debug(
                            f"Could not fetch stats for commit {commit.sha}: {stats_err}"
                        )

                    commit_data = {
                        "sha": commit.sha,
                        "commit": {
                            "author": {
                                "name": (
                                    commit.commit.author.name
                                    if commit.commit.author
                                    else username
                                ),
                                "date": (
                                    commit.commit.author.date.isoformat()
                                    if commit.commit.author
                                    and commit.commit.author.date
                                    else None
                                ),
                            },
                            "message": commit.commit.message if commit.commit else "",
                        },
                        "stats": {
                            "total": files_count,
                            "additions": additions,
                            "deletions": deletions,
                        },
                        "repo": repo_name,
                    }
                    commits_with_stats.append(commit_data)

                    # Log progress every 10 commits
                    if (i + 1) % 10 == 0:
                        self.logger.debug(
                            f"  Processed {i + 1}/{max_commits} commits for {repo_name}"
                        )

                except GithubException as e:
                    self.logger.warning(
                        f"Failed to fetch stats for commit {commit.sha}: {e}"
                    )
                    continue

            self.logger.info(
                f"Fetched {len(commits_with_stats)} commits with stats for {repo_name}"
            )
            metadata = self._build_repo_metadata(
                username, repo_name, repo_pushed_at, "commits_stats"
            )
            self.cache.set(
                "commits_stats",
                username,
                commits_with_stats,
                repo=repo_name,
                week=push_key,
                metadata=metadata,
            )
            return commits_with_stats

        except GithubException as e:
            self.logger.error(f"Could not fetch commit stats for {repo_name}: {e}")
            return []

    def fetch_languages(
        self, username: str, repo_name: str, repo_pushed_at: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Fetch language statistics for a repository.

        Args:
            username: Repository owner username
            repo_name: Repository name
            repo_pushed_at: Last push date (for cache invalidation)

        Returns:
            Dictionary mapping language names to byte counts
        """
        # Use pushed_at hash for cache key (change-based invalidation, not time-based)
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        cached = self.cache.get("languages", username, repo=repo_name, week=push_key)
        if cached:
            return self._sanitize_language_stats(cached)

        try:
            repo = self.github.get_repo(f"{username}/{repo_name}")
            languages = self._sanitize_language_stats(repo.get_languages())

            # Cache writes now handled by CacheManager
            return languages

        except GithubException as e:
            self.logger.debug(f"Could not fetch languages for {repo_name}: {e}")
            return {}

    def fetch_readme(
        self, username: str, repo_name: str, repo_pushed_at: Optional[datetime] = None
    ) -> Optional[str]:
        """Fetch README content for a repository.

        Args:
            username: Repository owner username
            repo_name: Repository name
            repo_pushed_at: Last push date (for cache invalidation)

        Returns:
            README content as string, or None if not found
        """
        # Use pushed_at hash for cache key (change-based invalidation, not time-based)
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        cached = self.cache.get("readme", username, repo=repo_name, week=push_key)
        if cached is not None:
            return cached

        try:
            repo = self.github.get_repo(f"{username}/{repo_name}")
            readme = repo.get_readme()

            # Decode content from base64
            content = readme.decoded_content.decode("utf-8")

            # Cache writes now handled by CacheManager
            return content

        except GithubException as e:
            self.logger.debug(f"Could not fetch README for {repo_name}: {e}")
            return None
        except Exception as e:
            self.logger.debug(f"Error decoding README for {repo_name}: {e}")
            return None

    def fetch_dependency_files(
        self, username: str, repo_name: str, repo_pushed_at: Optional[datetime] = None
    ) -> Dict[str, str]:
        """Fetch dependency files from a repository.

        Looks for common dependency files like package.json, requirements.txt, etc.

        Args:
            username: Repository owner username
            repo_name: Repository name
            repo_pushed_at: Last push date (for cache invalidation)

        Returns:
            Dictionary mapping filename to file content
        """
        # Use pushed_at hash for cache key (change-based invalidation, not time-based)
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        cached = self.cache.get(
            "dependency_files", username, repo=repo_name, week=push_key
        )
        if cached is not None:
            return cached

        dependency_files = {}

        # Common dependency file names to look for
        target_files = [
            "package.json",  # npm/JavaScript
            "requirements.txt",  # pip/Python
            "pyproject.toml",  # Python poetry/modern
            "Gemfile",  # Ruby
            "go.mod",  # Go
            "pom.xml",  # Maven/Java
            "*.csproj",  # .NET C#
            "Cargo.toml",  # Rust
            "composer.json",  # PHP
        ]

        try:
            repo = self.github.get_repo(f"{username}/{repo_name}")

            # Try to get each file
            for filename in target_files:
                try:
                    if "*" in filename:
                        # Handle wildcard patterns like *.csproj
                        contents = repo.get_contents("")
                        pattern = filename.replace("*", "")
                        if not isinstance(contents, list):
                            continue
                        for item in contents:
                            if item.name.endswith(pattern):
                                content = item.decoded_content.decode("utf-8")
                                dependency_files[item.name] = content
                    else:
                        file_content = repo.get_contents(filename)
                        if isinstance(file_content, list):
                            continue
                        content = file_content.decoded_content.decode("utf-8")
                        dependency_files[filename] = content
                except GithubException:
                    # File doesn't exist, continue
                    continue
                except Exception as e:
                    self.logger.debug(
                        f"Error fetching {filename} from {repo_name}: {e}"
                    )
                    continue

            # Cache writes now handled by CacheManager
            return dependency_files

        except GithubException as e:
            self.logger.debug(f"Could not access repository {repo_name}: {e}")
            return {}
        except Exception as e:
            self.logger.debug(f"Error fetching dependency files for {repo_name}: {e}")
            return {}

    def fetch_commit_counts(
        self, username: str, repo_name: str, repo_pushed_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Fetch time-windowed commit counts for ranking algorithm.

        Returns commits in multiple time windows:
        - total: All-time commits
        - recent_90d: Last 90 days
        - recent_180d: Last 180 days
        - recent_365d: Last 365 days

        Args:
            username: Repository owner username
            repo_name: Repository name
            repo_pushed_at: Last push date (for cache invalidation)

        Returns:
            Dictionary with commit counts by time window
        """
        # Use pushed_at hash for cache key (change-based invalidation, not time-based)
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        cached = self.cache.get(
            "commit_counts", username, repo=repo_name, week=push_key
        )
        if cached:
            return cached

        try:
            repo = self.github.get_repo(f"{username}/{repo_name}")

            # Use timezone-aware datetime to match GitHub API
            from datetime import timedelta, timezone

            now = datetime.now(timezone.utc)

            # Calculate time window boundaries
            day_90_ago = now - timedelta(days=90)
            day_180_ago = now - timedelta(days=180)
            day_365_ago = now - timedelta(days=365)

            # Fetch commits and count by time window
            total_commits = 0
            commits_90d = 0
            commits_180d = 0
            commits_365d = 0
            last_commit_date = None

            # Note: We limit to 1000 commits to stay within API limits
            # For repos with >1000 commits, this gives us a representative sample
            commits = repo.get_commits()

            for commit in commits:
                # Stop after 1000 commits to avoid rate limits
                if total_commits >= 1000:
                    break

                total_commits += 1

                # Safely access commit author date
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

                # Track most recent commit
                if not last_commit_date or commit_date > last_commit_date:
                    last_commit_date = commit_date

                # Count in time windows
                if commit_date >= day_90_ago:
                    commits_90d += 1
                if commit_date >= day_180_ago:
                    commits_180d += 1
                if commit_date >= day_365_ago:
                    commits_365d += 1

            result = {
                "total": total_commits,
                "recent_90d": commits_90d,
                "recent_180d": commits_180d,
                "recent_365d": commits_365d,
                "last_commit_date": (
                    last_commit_date.isoformat() if last_commit_date else None
                ),
            }

            # Cache writes now handled by CacheManager
            return result

        except (GithubException, IndexError, AttributeError) as e:
            self.logger.debug(f"Could not fetch commit counts for {repo_name}: {e}")
            return {
                "total": 0,
                "recent_90d": 0,
                "recent_180d": 0,
                "recent_365d": 0,
                "last_commit_date": None,
            }

    def fetch_pull_request_summary(
        self,
        username: str,
        repo_name: str,
        repo_pushed_at: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Fetch compact open pull request summary for a repository."""
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        if not force_refresh:
            cached = self.cache.get(
                "pull_request_summary", username, repo=repo_name, week=push_key
            )
            if cached:
                return cached

        total_open = 0
        draft_count = 0
        review_requested_count = 0
        oldest_open: Optional[datetime] = None
        page = 1
        availability = "available"
        reason = "none"

        try:
            while page <= 3:
                response = self._rest_get(
                    f"/repos/{username}/{repo_name}/pulls",
                    params={"state": "open", "per_page": 100, "page": page},
                    include_version=True,
                )
                if response.status_code >= 400:
                    availability = "unavailable"
                    reason = self._map_failure_reason(response.status_code)
                    break

                payload = response.json() or []
                if not isinstance(payload, list):
                    availability = "unavailable"
                    reason = "api_error"
                    break

                for pr in payload:
                    total_open += 1
                    if pr.get("draft"):
                        draft_count += 1
                    if pr.get("requested_reviewers") or pr.get("requested_teams"):
                        review_requested_count += 1
                    created_at = self._parse_iso_datetime(pr.get("created_at"))
                    if created_at and (oldest_open is None or created_at < oldest_open):
                        oldest_open = created_at

                if len(payload) < 100:
                    break

                page += 1

            if page > 3 and availability == "available":
                # Runtime protection: capped page scan can undercount very large PR queues.
                availability = "partial"
                reason = "not_requested"

            oldest_open_age_days = None
            if oldest_open is not None:
                oldest_open_age_days = max(
                    0, (datetime.now(timezone.utc) - oldest_open).days
                )

            if availability == "unavailable":
                total_open = 0
                draft_count = 0
                review_requested_count = 0
                oldest_open_age_days = None

            return {
                "availability": availability,
                "reason": reason,
                "has_open_pull_requests": total_open > 0,
                "total_open": total_open,
                "draft_count": draft_count,
                "review_requested_count": review_requested_count,
                "oldest_open_age_days": oldest_open_age_days,
                "source": "rest.pulls.list",
            }
        except Exception as error:
            self.logger.warning(
                f"Failed to fetch pull request summary for {username}/{repo_name}: {error}"
            )
            return {
                "availability": "unavailable",
                "reason": "api_error",
                "has_open_pull_requests": False,
                "total_open": 0,
                "draft_count": 0,
                "review_requested_count": 0,
                "oldest_open_age_days": None,
                "source": "rest.pulls.list",
            }

    def fetch_security_summary(
        self,
        username: str,
        repo_name: str,
        repo_pushed_at: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Fetch compact repository security summary from multiple REST sources."""
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        if not force_refresh:
            cached = self.cache.get(
                "security_summary", username, repo=repo_name, week=push_key
            )
            if cached:
                return cached

        feature_status = {
            "advanced_security": "unavailable",
            "secret_scanning": "unavailable",
            "secret_scanning_push_protection": "unavailable",
            "dependency_alerts": "unavailable",
            "automated_security_fixes": "unavailable",
        }
        counts = {"total_open": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
        sources = []
        any_success = False
        any_failure = False
        first_reason = "none"

        def mark_failure(status_code: int) -> None:
            nonlocal any_failure, first_reason
            any_failure = True
            mapped = self._map_failure_reason(status_code)
            if first_reason == "none":
                first_reason = mapped

        try:
            repo_response = self._rest_get(
                f"/repos/{username}/{repo_name}", include_version=True
            )
            if repo_response.status_code < 400:
                any_success = True
                sources.append("rest.repos.get")
                repo_payload = repo_response.json() or {}
                security_and_analysis = repo_payload.get("security_and_analysis") or {}
                advanced_security = security_and_analysis.get(
                    "advanced_security", {}
                ).get("status")
                secret_scanning = security_and_analysis.get("secret_scanning", {}).get(
                    "status"
                )
                push_protection = security_and_analysis.get(
                    "secret_scanning_push_protection", {}
                ).get("status")
                feature_status["advanced_security"] = advanced_security or "unknown"
                feature_status["secret_scanning"] = secret_scanning or "unknown"
                feature_status["secret_scanning_push_protection"] = (
                    push_protection or "unknown"
                )
            else:
                mark_failure(repo_response.status_code)

            vuln_response = self._rest_get(
                f"/repos/{username}/{repo_name}/vulnerability-alerts",
                include_version=True,
            )
            if vuln_response.status_code in {200, 204}:
                any_success = True
                sources.append("rest.repos.vulnerability-alerts")
                feature_status["dependency_alerts"] = "enabled"
            elif vuln_response.status_code == 404:
                any_success = True
                sources.append("rest.repos.vulnerability-alerts")
                feature_status["dependency_alerts"] = "disabled"
            else:
                mark_failure(vuln_response.status_code)

            fixes_response = self._rest_get(
                f"/repos/{username}/{repo_name}/automated-security-fixes",
                include_version=True,
            )
            if fixes_response.status_code in {200, 204}:
                any_success = True
                sources.append("rest.repos.automated-security-fixes")
                feature_status["automated_security_fixes"] = "enabled"
            elif fixes_response.status_code == 404:
                any_success = True
                sources.append("rest.repos.automated-security-fixes")
                feature_status["automated_security_fixes"] = "disabled"
            else:
                mark_failure(fixes_response.status_code)

            alerts_response = self._rest_get(
                f"/repos/{username}/{repo_name}/dependabot/alerts",
                params={"state": "open", "per_page": 100},
                include_version=True,
            )
            if alerts_response.status_code < 400:
                any_success = True
                sources.append("rest.dependabot.alerts")
                alerts_payload = alerts_response.json() or []
                if isinstance(alerts_payload, list):
                    for alert in alerts_payload:
                        counts["total_open"] += 1
                        severity = (
                            (alert.get("security_vulnerability") or {}).get("severity")
                            or (alert.get("security_advisory") or {}).get("severity")
                            or ""
                        ).lower()
                        if severity in {"critical", "high", "medium", "low"}:
                            counts[severity] += 1
            else:
                mark_failure(alerts_response.status_code)

            if any_success and any_failure:
                availability = "partial"
                reason = first_reason if first_reason != "none" else "unknown"
            elif any_success:
                availability = "available"
                reason = "none"
            else:
                availability = "unavailable"
                reason = first_reason if first_reason != "none" else "unknown"

            if counts["total_open"] > 0:
                overall_state = "warning_present"
            elif availability in {"available", "partial"}:
                overall_state = "clear"
            else:
                overall_state = "unavailable"

            return {
                "availability": availability,
                "reason": reason,
                "overall_state": overall_state,
                "feature_status": feature_status,
                "active_alert_counts": counts,
                "sources": sources,
            }
        except Exception as error:
            self.logger.warning(
                f"Failed to fetch security summary for {username}/{repo_name}: {error}"
            )
            return {
                "availability": "unavailable",
                "reason": "api_error",
                "overall_state": "unavailable",
                "feature_status": feature_status,
                "active_alert_counts": counts,
                "sources": sources,
            }

    def fetch_diagnostics_summary(
        self,
        username: str,
        repo_name: str,
        repo_pushed_at: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Fetch a consolidated diagnostics summary for a repository."""
        push_key = sanitize_timestamp_for_filename(repo_pushed_at)
        if not force_refresh:
            cached = self.cache.get(
                "diagnostics_summary", username, repo=repo_name, week=push_key
            )
            if cached:
                return cached

        pr_summary: Dict[str, Any] = {
            "availability": "unavailable",
            "reason": "not_requested",
            "total_open": 0,
            "oldest_open_age_days": None,
        }
        issues_summary: Dict[str, Any] = {
            "availability": "unavailable",
            "reason": "not_requested",
            "total_open": 0,
            "oldest_open_age_days": None,
            "stale_over_30d": 0,
            "stale_over_90d": 0,
        }
        security_summary: Dict[str, Any] = {
            "availability": "unavailable",
            "reason": "not_requested",
            "dependabot": {
                "total_open": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "code_scanning": {"total_open": 0, "error": 0, "warning": 0, "note": 0},
        }
        actions_summary: Dict[str, Any] = {
            "availability": "unavailable",
            "reason": "not_requested",
            "recent_runs": 0,
            "success_count": 0,
            "failure_count": 0,
            "last_run_status": None,
            "last_run_conclusion": None,
            "last_run_age_days": None,
        }
        sources: List[str] = []
        any_success = False
        any_failure = False
        first_reason = "none"

        def mark_failure(status_code: int) -> None:
            nonlocal any_failure, first_reason
            any_failure = True
            mapped = self._map_failure_reason(status_code)
            if first_reason == "none":
                first_reason = mapped

        # Pull requests diagnostics.
        try:
            response = self._rest_get(
                f"/repos/{username}/{repo_name}/pulls",
                params={"state": "open", "per_page": 100},
                include_version=True,
            )
            if response.status_code < 400:
                any_success = True
                sources.append("rest.pulls.list")
                payload = response.json() or []
                oldest_open = None
                pr_summary["availability"] = "available"
                pr_summary["reason"] = "none"
                if isinstance(payload, list):
                    pr_summary["total_open"] = len(payload)
                    for pr in payload:
                        created_at = self._parse_iso_datetime(pr.get("created_at"))
                        if created_at and (
                            oldest_open is None or created_at < oldest_open
                        ):
                            oldest_open = created_at
                if oldest_open is not None:
                    pr_summary["oldest_open_age_days"] = max(
                        0, (datetime.now(timezone.utc) - oldest_open).days
                    )
            else:
                mark_failure(response.status_code)
                pr_summary["reason"] = self._map_failure_reason(response.status_code)
        except Exception:
            any_failure = True
            if first_reason == "none":
                first_reason = "api_error"
            pr_summary["reason"] = "api_error"

        # Issues diagnostics.
        try:
            response = self._rest_get(
                f"/repos/{username}/{repo_name}/issues",
                params={"state": "open", "per_page": 100},
                include_version=True,
            )
            if response.status_code < 400:
                any_success = True
                sources.append("rest.issues.list")
                payload = response.json() or []
                oldest_open = None
                stale_30 = 0
                stale_90 = 0
                issues_summary["availability"] = "available"
                issues_summary["reason"] = "none"
                if isinstance(payload, list):
                    for issue in payload:
                        # GitHub issues endpoint includes PRs; exclude those for issue hygiene.
                        if "pull_request" in issue:
                            continue
                        issues_summary["total_open"] += 1
                        created_at = self._parse_iso_datetime(issue.get("created_at"))
                        if created_at is None:
                            continue
                        age_days = max(
                            0, (datetime.now(timezone.utc) - created_at).days
                        )
                        if oldest_open is None or created_at < oldest_open:
                            oldest_open = created_at
                        if age_days >= 30:
                            stale_30 += 1
                        if age_days >= 90:
                            stale_90 += 1
                issues_summary["stale_over_30d"] = stale_30
                issues_summary["stale_over_90d"] = stale_90
                if oldest_open is not None:
                    issues_summary["oldest_open_age_days"] = max(
                        0, (datetime.now(timezone.utc) - oldest_open).days
                    )
            else:
                mark_failure(response.status_code)
                issues_summary["reason"] = self._map_failure_reason(
                    response.status_code
                )
        except Exception:
            any_failure = True
            if first_reason == "none":
                first_reason = "api_error"
            issues_summary["reason"] = "api_error"

        # Security diagnostics (Dependabot + code scanning).
        try:
            dep_response = self._rest_get(
                f"/repos/{username}/{repo_name}/dependabot/alerts",
                params={"state": "open", "per_page": 100},
                include_version=True,
            )
            if dep_response.status_code < 400:
                any_success = True
                sources.append("rest.dependabot.alerts")
                dep_payload = dep_response.json() or []
                security_summary["availability"] = "available"
                security_summary["reason"] = "none"
                if isinstance(dep_payload, list):
                    for alert in dep_payload:
                        security_summary["dependabot"]["total_open"] += 1
                        severity = (
                            (alert.get("security_vulnerability") or {}).get("severity")
                            or (alert.get("security_advisory") or {}).get("severity")
                            or ""
                        ).lower()
                        if severity in {"critical", "high", "medium", "low"}:
                            security_summary["dependabot"][severity] += 1
            else:
                mark_failure(dep_response.status_code)
                security_summary["reason"] = self._map_failure_reason(
                    dep_response.status_code
                )

            code_response = self._rest_get(
                f"/repos/{username}/{repo_name}/code-scanning/alerts",
                params={"state": "open", "per_page": 100},
                include_version=True,
            )
            if code_response.status_code < 400:
                any_success = True
                sources.append("rest.code-scanning.alerts")
                code_payload = code_response.json() or []
                if isinstance(code_payload, list):
                    for alert in code_payload:
                        security_summary["code_scanning"]["total_open"] += 1
                        severity = (alert.get("rule") or {}).get("severity") or ""
                        severity = severity.lower()
                        if severity in {"error", "warning", "note"}:
                            security_summary["code_scanning"][severity] += 1
            elif code_response.status_code in {403, 404}:
                # Code scanning endpoints are often unavailable due to feature/permission state.
                if security_summary["availability"] == "available":
                    security_summary["availability"] = "partial"
                    security_summary["reason"] = self._map_failure_reason(
                        code_response.status_code
                    )
                else:
                    mark_failure(code_response.status_code)
                    security_summary["reason"] = self._map_failure_reason(
                        code_response.status_code
                    )
            else:
                mark_failure(code_response.status_code)
                security_summary["reason"] = self._map_failure_reason(
                    code_response.status_code
                )
        except Exception:
            any_failure = True
            if first_reason == "none":
                first_reason = "api_error"
            if security_summary["availability"] == "unavailable":
                security_summary["reason"] = "api_error"

        # Actions diagnostics.
        try:
            response = self._rest_get(
                f"/repos/{username}/{repo_name}/actions/runs",
                params={"per_page": 20},
                include_version=True,
            )
            if response.status_code < 400:
                any_success = True
                sources.append("rest.actions.runs")
                payload = response.json() or {}
                runs = payload.get("workflow_runs") if isinstance(payload, dict) else []
                if not isinstance(runs, list):
                    runs = []

                actions_summary["availability"] = "available"
                actions_summary["reason"] = "none"
                actions_summary["recent_runs"] = len(runs)
                for run in runs:
                    conclusion = (run.get("conclusion") or "").lower()
                    if conclusion == "success":
                        actions_summary["success_count"] += 1
                    elif conclusion in {
                        "failure",
                        "timed_out",
                        "cancelled",
                        "action_required",
                        "startup_failure",
                    }:
                        actions_summary["failure_count"] += 1

                if runs:
                    latest = runs[0]
                    actions_summary["last_run_status"] = latest.get("status")
                    actions_summary["last_run_conclusion"] = latest.get("conclusion")
                    created_at = self._parse_iso_datetime(latest.get("created_at"))
                    if created_at:
                        actions_summary["last_run_age_days"] = max(
                            0, (datetime.now(timezone.utc) - created_at).days
                        )
            else:
                mark_failure(response.status_code)
                actions_summary["reason"] = self._map_failure_reason(
                    response.status_code
                )
        except Exception:
            any_failure = True
            if first_reason == "none":
                first_reason = "api_error"
            actions_summary["reason"] = "api_error"

        if any_success and any_failure:
            availability = "partial"
            reason = first_reason if first_reason != "none" else "unknown"
        elif any_success:
            availability = "available"
            reason = "none"
        else:
            availability = "unavailable"
            reason = first_reason if first_reason != "none" else "unknown"

        return {
            "availability": availability,
            "reason": reason,
            "pull_requests": pr_summary,
            "issues": issues_summary,
            "security": security_summary,
            "actions": actions_summary,
            "sources": sources,
        }

    def handle_rate_limit(self, max_retries: int = 3) -> None:
        """Handle rate limiting with exponential backoff.

        Args:
            max_retries: Maximum number of retry attempts
        """
        rate_limit = self.github.get_rate_limit()

        # Handle different PyGithub API versions
        if hasattr(rate_limit, "core"):
            core_rate = rate_limit.core
        else:
            core_rate = rate_limit.resources.core

        if core_rate.remaining == 0:
            reset_time = core_rate.reset
            sleep_time = (reset_time - datetime.now()).total_seconds() + 10

            self.logger.warning(
                f"Rate limit exceeded. Sleeping for {sleep_time:.0f} seconds until reset."
            )
            time.sleep(sleep_time)

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status.

        Returns:
            Dictionary with rate limit information
        """
        rate_limit = self.github.get_rate_limit()

        # Handle different PyGithub API versions
        if hasattr(rate_limit, "core"):
            core_rate = rate_limit.core
        else:
            # Newer PyGithub version uses dict-like access
            core_rate = rate_limit.resources.core

        return {
            "limit": core_rate.limit,
            "remaining": core_rate.remaining,
            "reset": core_rate.reset.isoformat(),
            "used": core_rate.limit - core_rate.remaining,
        }
