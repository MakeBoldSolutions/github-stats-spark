"""Unit tests for GitHubFetcher enrichment and API-version behavior."""

from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from spark.cache import APICache
from spark.fetcher import GitHubFetcher
from spark.time_utils import sanitize_timestamp_for_filename


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def fetcher(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    return GitHubFetcher(
        cache=cache, api_version_settings={"enabled": True, "version": "2026-03-10"}
    )


def test_fetch_pull_request_summary_available(fetcher, monkeypatch):
    now = datetime.now(timezone.utc)

    def fake_rest_get(path, params=None, include_version=True):
        assert path.endswith("/pulls")
        return FakeResponse(
            200,
            [
                {
                    "draft": True,
                    "created_at": (now.replace(day=max(1, now.day - 3))).isoformat(),
                    "requested_reviewers": [{"id": 1}],
                    "requested_teams": [],
                },
                {
                    "draft": False,
                    "created_at": (now.replace(day=max(1, now.day - 1))).isoformat(),
                    "requested_reviewers": [],
                    "requested_teams": [],
                },
            ],
        )

    monkeypatch.setattr(fetcher, "_rest_get", fake_rest_get)

    summary = fetcher.fetch_pull_request_summary(
        "markhazleton", "github-stats-spark", force_refresh=True
    )

    assert summary["availability"] == "available"
    assert summary["reason"] == "none"
    assert summary["total_open"] == 2
    assert summary["draft_count"] == 1
    assert summary["review_requested_count"] == 1
    assert summary["has_open_pull_requests"] is True


def test_fetch_pull_request_summary_permission_denied(fetcher, monkeypatch):
    monkeypatch.setattr(
        fetcher,
        "_rest_get",
        lambda *args, **kwargs: FakeResponse(403, {"message": "forbidden"}),
    )

    summary = fetcher.fetch_pull_request_summary(
        "markhazleton", "github-stats-spark", force_refresh=True
    )

    assert summary["availability"] == "unavailable"
    assert summary["reason"] == "permission_denied"
    assert summary["total_open"] == 0


def test_fetch_security_summary_partial(fetcher, monkeypatch):
    responses = {
        "/repos/markhazleton/github-stats-spark": FakeResponse(
            200,
            {
                "security_and_analysis": {
                    "advanced_security": {"status": "enabled"},
                    "secret_scanning": {"status": "enabled"},
                    "secret_scanning_push_protection": {"status": "enabled"},
                }
            },
        ),
        "/repos/markhazleton/github-stats-spark/vulnerability-alerts": FakeResponse(
            200, None
        ),
        "/repos/markhazleton/github-stats-spark/automated-security-fixes": FakeResponse(
            403, {"message": "forbidden"}
        ),
        "/repos/markhazleton/github-stats-spark/dependabot/alerts": FakeResponse(
            200,
            [
                {"security_vulnerability": {"severity": "critical"}},
                {"security_vulnerability": {"severity": "medium"}},
            ],
        ),
    }

    def fake_rest_get(path, params=None, include_version=True):
        return responses[path]

    monkeypatch.setattr(fetcher, "_rest_get", fake_rest_get)

    summary = fetcher.fetch_security_summary(
        "markhazleton", "github-stats-spark", force_refresh=True
    )

    assert summary["availability"] == "partial"
    assert summary["reason"] == "permission_denied"
    assert summary["overall_state"] == "warning_present"
    assert summary["active_alert_counts"]["total_open"] == 2
    assert summary["active_alert_counts"]["critical"] == 1
    assert summary["active_alert_counts"]["medium"] == 1


def test_fetch_security_summary_unavailable(fetcher, monkeypatch):
    monkeypatch.setattr(
        fetcher,
        "_rest_get",
        lambda *args, **kwargs: FakeResponse(403, {"message": "forbidden"}),
    )

    summary = fetcher.fetch_security_summary(
        "markhazleton", "github-stats-spark", force_refresh=True
    )

    assert summary["availability"] == "unavailable"
    assert summary["reason"] == "permission_denied"
    assert summary["overall_state"] == "unavailable"


def test_fetch_diagnostics_summary_partial(fetcher, monkeypatch):
    now = datetime.now(timezone.utc)
    older = (now - timedelta(days=45)).isoformat()
    recent = (now - timedelta(days=2)).isoformat()

    responses = {
        "/repos/markhazleton/github-stats-spark/pulls": FakeResponse(
            200,
            [
                {
                    "created_at": older,
                    "draft": False,
                    "requested_reviewers": [],
                    "requested_teams": [],
                },
                {
                    "created_at": recent,
                    "draft": False,
                    "requested_reviewers": [],
                    "requested_teams": [],
                },
            ],
        ),
        "/repos/markhazleton/github-stats-spark/issues": FakeResponse(
            200,
            [
                {"created_at": older},
                {
                    "created_at": recent,
                    "pull_request": {"url": "https://api.github.com/..."},
                },
            ],
        ),
        "/repos/markhazleton/github-stats-spark/dependabot/alerts": FakeResponse(
            200,
            [{"security_vulnerability": {"severity": "high"}}],
        ),
        "/repos/markhazleton/github-stats-spark/code-scanning/alerts": FakeResponse(
            404, {"message": "not found"}
        ),
        "/repos/markhazleton/github-stats-spark/actions/runs": FakeResponse(
            200,
            {
                "workflow_runs": [
                    {
                        "status": "completed",
                        "conclusion": "failure",
                        "created_at": recent,
                    },
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": older,
                    },
                ]
            },
        ),
    }

    def fake_rest_get(path, params=None, include_version=True):
        return responses[path]

    monkeypatch.setattr(fetcher, "_rest_get", fake_rest_get)

    summary = fetcher.fetch_diagnostics_summary(
        "markhazleton", "github-stats-spark", force_refresh=True
    )

    assert summary["availability"] == "available"
    assert summary["security"]["availability"] == "partial"
    assert summary["pull_requests"]["total_open"] == 2
    assert summary["issues"]["total_open"] == 1
    assert summary["issues"]["stale_over_30d"] == 1
    assert summary["security"]["dependabot"]["high"] == 1
    assert summary["actions"]["failure_count"] == 1


def test_fetch_repositories_excludes_private(fetcher, monkeypatch):
    class Repo:
        def __init__(self, name, private):
            self.name = name
            self.full_name = f"markhazleton/{name}"
            self.description = "repo"
            self.language = "Python"
            self.stargazers_count = 1
            self.forks_count = 1
            self.watchers_count = 1
            self.size = 10
            self.created_at = datetime.now(timezone.utc)
            self.updated_at = datetime.now(timezone.utc)
            self.pushed_at = datetime.now(timezone.utc)
            self.fork = False
            self.private = private
            self.archived = False
            self.homepage = None
            self.has_pages = False

    class User:
        @staticmethod
        def get_repos():
            return [Repo("public-repo", False), Repo("private-repo", True)]

    monkeypatch.setattr(fetcher.github, "get_user", lambda username: User())

    repos = fetcher.fetch_repositories("markhazleton", exclude_private=True)

    assert [repo["name"] for repo in repos] == ["public-repo"]


def test_get_user_without_username_uses_authenticated_user(fetcher, monkeypatch):
    user = SimpleNamespace(
        login="markhazleton",
        name="Mark",
        bio="bio",
        avatar_url="https://example/avatar.png",
        html_url="https://github.com/markhazleton",
        public_repos=10,
        followers=5,
        following=2,
    )

    monkeypatch.setattr(fetcher.github, "get_user", lambda: user)

    profile = fetcher.get_user()

    assert profile["login"] == "markhazleton"
    assert profile["name"] == "Mark"


def test_get_user_with_username_delegates_to_fetch_user_profile(fetcher, monkeypatch):
    monkeypatch.setattr(
        fetcher, "fetch_user_profile", lambda username: {"username": username}
    )

    profile = fetcher.get_user("markhazleton")

    assert profile == {"username": "markhazleton"}


def test_fetch_user_profile_reads_from_cache(fetcher):
    fetcher.cache.set("user_profile", "markhazleton", {"username": "cached"})

    profile = fetcher.fetch_user_profile("markhazleton")

    assert profile["username"] == "cached"


def test_fetch_user_profile_from_github(fetcher, monkeypatch):
    now = datetime.now(timezone.utc)
    user = SimpleNamespace(
        login="markhazleton",
        name=None,
        bio="bio",
        company="company",
        location="location",
        email="email@example.com",
        avatar_url="https://example/avatar.png",
        html_url="https://github.com/markhazleton",
        public_repos=3,
        followers=1,
        following=2,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(fetcher.github, "get_user", lambda username: user)

    profile = fetcher.fetch_user_profile("markhazleton")

    assert profile["username"] == "markhazleton"
    assert profile["name"] == "markhazleton"
    assert profile["created_at"] is not None


def test_fetch_repositories_respects_max_repos(fetcher, monkeypatch):
    fetcher.max_repos = 1

    class Repo:
        def __init__(self, name):
            self.name = name
            self.full_name = f"markhazleton/{name}"
            self.description = "repo"
            self.language = "Python"
            self.stargazers_count = 1
            self.forks_count = 0
            self.watchers_count = 0
            self.size = 1
            self.created_at = datetime.now(timezone.utc)
            self.updated_at = datetime.now(timezone.utc)
            self.pushed_at = datetime.now(timezone.utc)
            self.fork = False
            self.private = False
            self.archived = False
            self.homepage = None
            self.has_pages = False

    class User:
        @staticmethod
        def get_repos():
            return [Repo("one"), Repo("two")]

    monkeypatch.setattr(fetcher.github, "get_user", lambda username: User())

    repos = fetcher.fetch_repositories("markhazleton", exclude_private=True)

    assert len(repos) == 1
    assert repos[0]["name"] == "one"


def test_fetch_commits_returns_data(fetcher, monkeypatch):
    commit = SimpleNamespace(
        sha="abc",
        commit=SimpleNamespace(
            message="msg",
            author=SimpleNamespace(
                name="markhazleton", date=datetime.now(timezone.utc)
            ),
        ),
    )
    repo = SimpleNamespace(get_commits=lambda author=None: [commit])
    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

    commits = fetcher.fetch_commits("markhazleton", "repo-one")

    assert commits[0]["sha"] == "abc"
    assert commits[0]["repo"] == "repo-one"


def test_fetch_readme_decodes_content(fetcher, monkeypatch):
    readme = SimpleNamespace(decoded_content=b"# title")
    repo = SimpleNamespace(get_readme=lambda: readme)
    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

    content = fetcher.fetch_readme("markhazleton", "repo-one")

    assert content == "# title"


def test_fetch_dependency_files_supports_wildcard(fetcher, monkeypatch):
    root_contents = [
        SimpleNamespace(name="app.csproj", type="file", decoded_content=b"<Project />")
    ]

    class Repo:
        @staticmethod
        def get_contents(path):
            if path == "":
                return root_contents
            raise RuntimeError("unexpected path")

    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: Repo())

    files = fetcher.fetch_dependency_files("markhazleton", "repo-one")

    assert "app.csproj" in files


def test_fetch_commit_counts_computes_windows(fetcher, monkeypatch):
    now = datetime.now(timezone.utc)

    def make_commit(days_ago):
        return SimpleNamespace(
            commit=SimpleNamespace(
                author=SimpleNamespace(date=now.replace(day=max(1, now.day - days_ago)))
            )
        )

    repo = SimpleNamespace(
        get_commits=lambda: [make_commit(1), make_commit(10), make_commit(40)]
    )
    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

    result = fetcher.fetch_commit_counts("markhazleton", "repo-one")

    assert result["total"] == 3
    assert result["recent_90d"] >= 1


def test_get_rate_limit_status_handles_core_and_resources(fetcher, monkeypatch):
    core_rate = SimpleNamespace(
        limit=5000, remaining=4999, reset=datetime.now(timezone.utc)
    )
    monkeypatch.setattr(
        fetcher.github, "get_rate_limit", lambda: SimpleNamespace(core=core_rate)
    )
    direct = fetcher.get_rate_limit_status()

    assert direct["limit"] == 5000

    resources_rate = SimpleNamespace(resources=SimpleNamespace(core=core_rate))
    monkeypatch.setattr(fetcher.github, "get_rate_limit", lambda: resources_rate)
    nested = fetcher.get_rate_limit_status()

    assert nested["remaining"] == 4999


def test_handle_rate_limit_sleeps_when_exhausted(fetcher, monkeypatch):
    class Rate:
        def __init__(self):
            self.remaining = 0
            self.reset = datetime.now() + timedelta(seconds=1)

    monkeypatch.setattr(
        fetcher.github, "get_rate_limit", lambda: SimpleNamespace(core=Rate())
    )
    sleep_calls = []
    monkeypatch.setattr(
        "spark.fetcher.time.sleep", lambda seconds: sleep_calls.append(seconds)
    )

    fetcher.handle_rate_limit()

    assert len(sleep_calls) == 1


def test_init_without_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    cache = APICache(cache_dir=str(tmp_path / "cache-no-token"))

    with pytest.raises(ValueError, match="GitHub token required"):
        GitHubFetcher(token=None, cache=cache)


def test_fetch_commits_with_stats_returns_cached_when_cache_status_valid(
    fetcher, monkeypatch
):
    fetcher.use_cache_status = True
    pushed_at = datetime.now(timezone.utc)
    cached_payload = [{"sha": "cached"}]

    fetcher.cache_status_tracker.get_repository_cache_status = lambda **kwargs: {
        "refresh_needed": False,
        "cache_age_hours": 1.0,
    }
    fetcher.cache.set(
        "commits_stats",
        "markhazleton",
        cached_payload,
        repo="repo-one",
        week=sanitize_timestamp_for_filename(pushed_at),
    )

    result = fetcher.fetch_commits_with_stats(
        "markhazleton",
        "repo-one",
        repo_pushed_at=pushed_at,
        force_refresh=False,
    )

    assert result == cached_payload


def test_fetch_commits_with_stats_builds_stats_payload(fetcher, monkeypatch):
    fetcher.use_cache_status = False

    commit = SimpleNamespace(
        sha="abc",
        commit=SimpleNamespace(
            author=SimpleNamespace(
                name="markhazleton", date=datetime.now(timezone.utc)
            ),
            message="message",
        ),
        stats=SimpleNamespace(total=5, additions=3, deletions=2),
    )
    repo = SimpleNamespace(get_commits=lambda: [commit])
    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

    result = fetcher.fetch_commits_with_stats(
        "markhazleton", "repo-one", force_refresh=True
    )

    assert len(result) == 1
    assert result[0]["stats"]["additions"] == 3
    assert result[0]["stats"]["deletions"] == 2


def test_fetch_languages_returns_mapping(fetcher, monkeypatch):
    repo = SimpleNamespace(get_languages=lambda: {"Python": 123})
    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

    languages = fetcher.fetch_languages("markhazleton", "repo-one")

    assert languages == {"Python": 123}


def test_fetch_languages_filters_non_numeric_entries(fetcher, monkeypatch):
    repo = SimpleNamespace(
        get_languages=lambda: {
            "Python": 123,
            "TypeScript": "456",
            "url": "https://api.github.com/repos/example/repo/languages",
        }
    )
    monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

    languages = fetcher.fetch_languages("markhazleton", "repo-one")

    assert languages == {"Python": 123, "TypeScript": 456}


def test_fetch_pull_request_summary_marks_partial_after_page_cap(fetcher, monkeypatch):
    payload = [
        {
            "draft": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requested_reviewers": [],
            "requested_teams": [],
        }
    ] * 100

    monkeypatch.setattr(
        fetcher, "_rest_get", lambda *args, **kwargs: FakeResponse(200, payload)
    )

    summary = fetcher.fetch_pull_request_summary(
        "markhazleton", "repo-one", force_refresh=True
    )

    assert summary["availability"] == "partial"
    assert summary["reason"] == "not_requested"


# ---------------------------------------------------------------------------
# Static helper method tests
# ---------------------------------------------------------------------------


class TestParseIsoDatetime:
    """Test GitHubFetcher._parse_iso_datetime."""

    def test_valid_iso(self):
        result = GitHubFetcher._parse_iso_datetime("2026-03-15T12:00:00+00:00")
        assert result.year == 2026

    def test_github_z_suffix(self):
        result = GitHubFetcher._parse_iso_datetime("2026-01-01T00:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_none_input(self):
        assert GitHubFetcher._parse_iso_datetime(None) is None

    def test_empty_string(self):
        assert GitHubFetcher._parse_iso_datetime("") is None

    def test_invalid_string(self):
        assert GitHubFetcher._parse_iso_datetime("not-a-date") is None


class TestMapFailureReason:
    """Test GitHubFetcher._map_failure_reason."""

    def test_401(self):
        assert GitHubFetcher._map_failure_reason(401) == "permission_denied"

    def test_403(self):
        assert GitHubFetcher._map_failure_reason(403) == "permission_denied"

    def test_404(self):
        assert GitHubFetcher._map_failure_reason(404) == "not_supported"

    def test_zero(self):
        assert GitHubFetcher._map_failure_reason(0) == "unknown"

    def test_500(self):
        assert GitHubFetcher._map_failure_reason(500) == "api_error"


class TestShouldIncludeRepository:
    """Test GitHubFetcher._should_include_repository."""

    def _repo(self, private=False, fork=False, archived=False):
        return SimpleNamespace(private=private, fork=fork, archived=archived)

    def test_public_active_original(self):
        assert (
            GitHubFetcher._should_include_repository(self._repo(), True, True, True)
            is True
        )

    def test_exclude_private(self):
        assert (
            GitHubFetcher._should_include_repository(
                self._repo(private=True), True, False, False
            )
            is False
        )

    def test_include_private_when_not_excluded(self):
        assert (
            GitHubFetcher._should_include_repository(
                self._repo(private=True), False, False, False
            )
            is True
        )

    def test_exclude_fork(self):
        assert (
            GitHubFetcher._should_include_repository(
                self._repo(fork=True), False, True, False
            )
            is False
        )

    def test_exclude_archived(self):
        assert (
            GitHubFetcher._should_include_repository(
                self._repo(archived=True), False, False, True
            )
            is False
        )

    def test_all_flags_false_includes_everything(self):
        r = self._repo(private=True, fork=True, archived=True)
        assert GitHubFetcher._should_include_repository(r, False, False, False) is True


class TestBuildRestHeaders:
    """Test _build_rest_headers version-header logic."""

    def test_version_enabled(self, fetcher):
        headers = fetcher._build_rest_headers(include_version=True)
        assert "X-GitHub-Api-Version" in headers
        assert headers["X-GitHub-Api-Version"] == "2026-03-10"

    def test_version_disabled(self, fetcher):
        headers = fetcher._build_rest_headers(include_version=False)
        assert "X-GitHub-Api-Version" not in headers

    def test_version_setting_off(self, fetcher):
        fetcher.api_version_settings["enabled"] = False
        headers = fetcher._build_rest_headers(include_version=True)
        assert "X-GitHub-Api-Version" not in headers


class TestBuildRepoMetadata:
    """Test _build_repo_metadata helper."""

    def test_with_pushed_at(self, fetcher):
        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        meta = fetcher._build_repo_metadata("user", "repo", pushed, "commits")
        assert meta["repository"] == {"owner": "user", "name": "repo"}
        assert meta["category"] == "commits"
        assert meta["pushed_at"] is not None

    def test_without_pushed_at(self, fetcher):
        meta = fetcher._build_repo_metadata("user", "repo", None, "readme")
        assert meta["pushed_at"] is None


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------


class TestFetcherErrorPaths:
    """Test error handling across fetcher methods."""

    @pytest.fixture
    def fetcher(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        cache = APICache(cache_dir=str(tmp_path / "cache"))
        return GitHubFetcher(cache=cache)

    def test_fetch_commits_github_exception(self, fetcher, monkeypatch):
        from github import GithubException

        repo = SimpleNamespace(
            get_commits=lambda author=None: (_ for _ in ()).throw(
                GithubException(403, "forbidden", None)
            )
        )
        monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

        result = fetcher.fetch_commits("user", "repo")
        assert result == []

    def test_fetch_languages_github_exception(self, fetcher, monkeypatch):
        from github import GithubException

        repo = SimpleNamespace(
            get_languages=lambda: (_ for _ in ()).throw(
                GithubException(403, "forbidden", None)
            )
        )
        monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

        result = fetcher.fetch_languages("user", "repo")
        assert result == {}

    def test_fetch_readme_github_exception(self, fetcher, monkeypatch):
        from github import GithubException

        repo = SimpleNamespace(
            get_readme=lambda: (_ for _ in ()).throw(
                GithubException(404, "not found", None)
            )
        )
        monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

        result = fetcher.fetch_readme("user", "repo")
        assert result is None

    def test_fetch_readme_decode_error(self, fetcher, monkeypatch):
        SimpleNamespace(decoded_content=b"\x80\x81\x82")
        # Force decode to fail by mocking
        repo = SimpleNamespace(get_readme=lambda: SimpleNamespace(decoded_content=None))
        monkeypatch.setattr(fetcher.github, "get_repo", lambda full_name: repo)

        result = fetcher.fetch_readme("user", "repo")
        assert result is None

    def test_fetch_user_profile_github_exception(self, fetcher, monkeypatch):
        from github import GithubException

        monkeypatch.setattr(
            fetcher.github,
            "get_user",
            lambda username: (_ for _ in ()).throw(
                GithubException(404, "not found", None)
            ),
        )

        with pytest.raises(GithubException):
            fetcher.fetch_user_profile("nobody")

    def test_fetch_repositories_github_exception(self, fetcher, monkeypatch):
        from github import GithubException

        class FailUser:
            @staticmethod
            def get_repos():
                raise GithubException(500, "server error", None)

        monkeypatch.setattr(fetcher.github, "get_user", lambda username: FailUser())

        with pytest.raises(GithubException):
            fetcher.fetch_repositories("user")

    def test_fetch_commit_counts_exception(self, fetcher, monkeypatch):
        from github import GithubException

        monkeypatch.setattr(
            fetcher.github,
            "get_repo",
            lambda full: (_ for _ in ()).throw(GithubException(403, "denied", None)),
        )

        result = fetcher.fetch_commit_counts("user", "repo")
        assert result["total"] == 0
        assert result["last_commit_date"] is None

    def test_fetch_commits_with_stats_github_exception(self, fetcher, monkeypatch):
        from github import GithubException

        monkeypatch.setattr(
            fetcher.github,
            "get_repo",
            lambda full: (_ for _ in ()).throw(GithubException(500, "err", None)),
        )
        fetcher.use_cache_status = False

        result = fetcher.fetch_commits_with_stats("user", "repo", force_refresh=True)
        assert result == []

    def test_fetch_dependency_files_exception(self, fetcher, monkeypatch):
        from github import GithubException

        monkeypatch.setattr(
            fetcher.github,
            "get_repo",
            lambda full: (_ for _ in ()).throw(GithubException(404, "missing", None)),
        )

        result = fetcher.fetch_dependency_files("user", "repo")
        assert result == {}

    def test_pr_summary_exception_returns_unavailable(self, fetcher, monkeypatch):
        monkeypatch.setattr(
            fetcher,
            "_rest_get",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network")),
        )

        result = fetcher.fetch_pull_request_summary("user", "repo", force_refresh=True)
        assert result["availability"] == "unavailable"
        assert result["reason"] == "api_error"

    def test_security_summary_exception_returns_unavailable(self, fetcher, monkeypatch):
        monkeypatch.setattr(
            fetcher,
            "_rest_get",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network")),
        )

        result = fetcher.fetch_security_summary("user", "repo", force_refresh=True)
        assert result["availability"] == "unavailable"
        assert result["reason"] == "api_error"


# ---------------------------------------------------------------------------
# Cache-hit path tests
# ---------------------------------------------------------------------------


class TestFetcherCacheHits:
    """Test that cache hits skip API calls."""

    @pytest.fixture
    def fetcher(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        cache = APICache(cache_dir=str(tmp_path / "cache"))
        return GitHubFetcher(cache=cache)

    def test_fetch_commits_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        fetcher.cache.set(
            "commits", "user", [{"sha": "cached"}], repo="my-repo", week=key
        )

        result = fetcher.fetch_commits("user", "my-repo", repo_pushed_at=pushed)
        assert result == [{"sha": "cached"}]

    def test_fetch_languages_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        fetcher.cache.set("languages", "user", {"Go": 999}, repo="my-repo", week=key)

        result = fetcher.fetch_languages("user", "my-repo", repo_pushed_at=pushed)
        assert result == {"Go": 999}

    def test_fetch_languages_cache_hit_filters_non_numeric_entries(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        fetcher.cache.set(
            "languages",
            "user",
            {
                "Go": 999,
                "url": "https://api.github.com/repos/user/my-repo/languages",
                "Rust": "123",
            },
            repo="my-repo",
            week=key,
        )

        result = fetcher.fetch_languages("user", "my-repo", repo_pushed_at=pushed)
        assert result == {"Go": 999, "Rust": 123}

    def test_fetch_readme_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        fetcher.cache.set("readme", "user", "# Cached", repo="my-repo", week=key)

        result = fetcher.fetch_readme("user", "my-repo", repo_pushed_at=pushed)
        assert result == "# Cached"

    def test_fetch_commit_counts_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        fetcher.cache.set(
            "commit_counts", "user", {"total": 42}, repo="my-repo", week=key
        )

        result = fetcher.fetch_commit_counts("user", "my-repo", repo_pushed_at=pushed)
        assert result == {"total": 42}

    def test_fetch_dependency_files_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        fetcher.cache.set(
            "dependency_files", "user", {"package.json": "{}"}, repo="my-repo", week=key
        )

        result = fetcher.fetch_dependency_files(
            "user", "my-repo", repo_pushed_at=pushed
        )
        assert result == {"package.json": "{}"}

    def test_fetch_repositories_cache_hit(self, fetcher):
        variant = "list_True_True_True"
        fetcher.cache.set(
            "repositories", "user", [{"name": "cached-repo"}], repo=variant
        )

        result = fetcher.fetch_repositories("user")
        assert result == [{"name": "cached-repo"}]

    def test_pr_summary_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        cached = {"availability": "available", "total_open": 5}
        fetcher.cache.set(
            "pull_request_summary", "user", cached, repo="my-repo", week=key
        )

        result = fetcher.fetch_pull_request_summary(
            "user", "my-repo", repo_pushed_at=pushed
        )
        assert result == cached

    def test_security_summary_cache_hit(self, fetcher):
        from spark.time_utils import sanitize_timestamp_for_filename

        pushed = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = sanitize_timestamp_for_filename(pushed)
        cached = {"availability": "available", "overall_state": "clear"}
        fetcher.cache.set("security_summary", "user", cached, repo="my-repo", week=key)

        result = fetcher.fetch_security_summary(
            "user", "my-repo", repo_pushed_at=pushed
        )
        assert result == cached


class TestRestGetFallback:
    """Test _rest_get API version fallback behavior."""

    @pytest.fixture
    def fetcher(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        cache = APICache(cache_dir=str(tmp_path / "cache"))
        return GitHubFetcher(
            cache=cache, api_version_settings={"enabled": True, "version": "2026-03-10"}
        )

    def test_fallback_on_415(self, fetcher, monkeypatch):
        calls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(headers.get("X-GitHub-Api-Version"))
            if "X-GitHub-Api-Version" in headers:
                return FakeResponse(415)
            return FakeResponse(200, {"ok": True})

        monkeypatch.setattr("spark.fetcher.requests.get", fake_get)

        resp = fetcher._rest_get("/test")
        assert resp.status_code == 200
        assert len(calls) == 2  # initial versioned + fallback

    def test_no_fallback_on_success(self, fetcher, monkeypatch):
        calls = []

        def fake_get(url, headers=None, params=None, timeout=None):
            calls.append(1)
            return FakeResponse(200, {"ok": True})

        monkeypatch.setattr("spark.fetcher.requests.get", fake_get)

        resp = fetcher._rest_get("/test")
        assert resp.status_code == 200
        assert len(calls) == 1


class TestSecuritySummaryAllSuccess:
    """Test security summary when all endpoints succeed."""

    @pytest.fixture
    def fetcher(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        cache = APICache(cache_dir=str(tmp_path / "cache"))
        return GitHubFetcher(
            cache=cache, api_version_settings={"enabled": True, "version": "2026-03-10"}
        )

    def test_all_clear(self, fetcher, monkeypatch):
        responses = {
            "/repos/user/repo": FakeResponse(
                200,
                {
                    "security_and_analysis": {
                        "advanced_security": {"status": "enabled"},
                        "secret_scanning": {"status": "enabled"},
                        "secret_scanning_push_protection": {"status": "enabled"},
                    }
                },
            ),
            "/repos/user/repo/vulnerability-alerts": FakeResponse(200, None),
            "/repos/user/repo/automated-security-fixes": FakeResponse(200, None),
            "/repos/user/repo/dependabot/alerts": FakeResponse(200, []),
        }
        monkeypatch.setattr(fetcher, "_rest_get", lambda path, **kw: responses[path])

        result = fetcher.fetch_security_summary("user", "repo", force_refresh=True)
        assert result["availability"] == "available"
        assert result["overall_state"] == "clear"
        assert result["active_alert_counts"]["total_open"] == 0


# ---------------------------------------------------------------------------
# _serialize_repository tests
# ---------------------------------------------------------------------------


class TestSerializeRepository:
    """Test GitHubFetcher._serialize_repository."""

    def _make_repo(self, **overrides):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        defaults = dict(
            name="my-repo",
            full_name="user/my-repo",
            description="A repo",
            language="Python",
            stargazers_count=5,
            forks_count=2,
            watchers_count=3,
            size=100,
            created_at=now,
            updated_at=now,
            pushed_at=now,
            fork=False,
            private=False,
            archived=False,
            homepage="https://example.com",
            has_pages=True,
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_all_fields_present(self):
        repo = self._make_repo()
        result = GitHubFetcher._serialize_repository(repo)
        assert result["name"] == "my-repo"
        assert result["full_name"] == "user/my-repo"
        assert result["language"] == "Python"
        assert result["stars"] == 5
        assert result["forks"] == 2
        assert result["watchers"] == 3
        assert result["size"] == 100
        assert result["is_fork"] is False
        assert result["is_private"] is False
        assert result["is_archived"] is False
        assert result["has_pages"] is True
        assert result["homepage"] == "https://example.com"
        assert result["pushed_at"] is not None

    def test_none_timestamps_produce_none(self):
        repo = self._make_repo(created_at=None, updated_at=None, pushed_at=None)
        result = GitHubFetcher._serialize_repository(repo)
        assert result["created_at"] is None
        assert result["updated_at"] is None
        assert result["pushed_at"] is None

    def test_private_repo_serializes_correctly(self):
        repo = self._make_repo(private=True)
        result = GitHubFetcher._serialize_repository(repo)
        assert result["is_private"] is True

    def test_fork_repo_serializes_correctly(self):
        repo = self._make_repo(fork=True)
        result = GitHubFetcher._serialize_repository(repo)
        assert result["is_fork"] is True
