"""Targeted tests to raise coverage on audit-flagged core modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from github import GithubException

from spark.cache import APICache
from spark.fetcher import GitHubFetcher
from spark.models import (
    CommitHistory,
    GitHubData,
    Repository,
    RepositorySummary,
    UserProfile,
)
from spark.models.report import UnifiedReport
from spark.models.tech_stack import TechnologyStack
from spark.summarizer import RepositorySummarizer, UserProfileGenerator
from spark.unified_report_workflow import UnifiedReportWorkflow


@pytest.fixture
def sample_repo() -> Repository:
    now = datetime.now(timezone.utc)
    return Repository(
        name="repo-one",
        description="Repository for tests",
        url="https://github.com/markhazleton/repo-one",
        created_at=now - timedelta(days=365),
        updated_at=now - timedelta(days=1),
        pushed_at=now - timedelta(days=1),
        primary_language="Python",
        language_stats={"Python": 1000},
        stars=10,
        forks=2,
        watchers=3,
        open_issues=1,
        is_archived=False,
        is_fork=False,
        is_private=False,
        size_kb=10,
        has_readme=True,
    )


@pytest.fixture
def sample_commit_history() -> CommitHistory:
    return CommitHistory(
        repository_name="repo-one",
        total_commits=20,
        recent_90d=10,
        recent_180d=15,
        recent_365d=18,
        last_commit_date=datetime.now(timezone.utc) - timedelta(days=1),
    )


def test_fetcher_static_helpers_and_dependency_error_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    fetcher = GitHubFetcher(cache=APICache(cache_dir=str(tmp_path / "cache")))

    assert fetcher._parse_iso_datetime("2026-01-01T00:00:00Z") is not None
    assert fetcher._parse_iso_datetime("not-a-date") is None
    assert fetcher._map_failure_reason(401) == "permission_denied"
    assert fetcher._map_failure_reason(404) == "not_supported"
    assert fetcher._map_failure_reason(0) == "unknown"
    assert fetcher._map_failure_reason(500) == "api_error"

    # Repo access failure branch
    monkeypatch.setattr(
        fetcher.github,
        "get_repo",
        lambda _: (_ for _ in ()).throw(GithubException(404, {}, None)),
    )
    assert fetcher.fetch_dependency_files("markhazleton", "repo-one") == {}


def test_fetcher_commit_counts_handles_invalid_commit_objects(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    fetcher = GitHubFetcher(cache=APICache(cache_dir=str(tmp_path / "cache")))

    # First object has missing commit attr; second is valid.
    invalid = SimpleNamespace()
    valid = SimpleNamespace(
        commit=SimpleNamespace(
            author=SimpleNamespace(date=datetime.now(timezone.utc) - timedelta(days=5))
        )
    )
    repo = SimpleNamespace(get_commits=lambda: [invalid, valid])
    monkeypatch.setattr(fetcher.github, "get_repo", lambda _: repo)

    counts = fetcher.fetch_commit_counts("markhazleton", "repo-one")
    assert counts["total"] == 2
    assert counts["recent_90d"] >= 1


def test_fetcher_readme_decode_and_rate_limit_branches(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    fetcher = GitHubFetcher(cache=APICache(cache_dir=str(tmp_path / "cache")))

    class _BadReadme:
        decoded_content = b"\xff"

    repo = SimpleNamespace(get_readme=lambda: _BadReadme())
    monkeypatch.setattr(fetcher.github, "get_repo", lambda _: repo)
    assert fetcher.fetch_readme("markhazleton", "repo-one") is None

    class _Rate:
        remaining = 0
        reset = datetime.now() + timedelta(seconds=1)

    monkeypatch.setattr(
        fetcher.github, "get_rate_limit", lambda: SimpleNamespace(core=_Rate())
    )
    sleep_calls = []
    monkeypatch.setattr(
        "spark.fetcher.time.sleep", lambda seconds: sleep_calls.append(seconds)
    )
    fetcher.handle_rate_limit()
    assert sleep_calls


def test_fetcher_rest_get_fallback_and_success(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    fetcher = GitHubFetcher(
        cache=APICache(cache_dir=str(tmp_path / "cache")),
        api_version_settings={
            "enabled": True,
            "version": "2026-03-10",
            "fallback_to_default": True,
        },
    )

    calls = []

    class _Resp:
        def __init__(self, status):
            self.status_code = status

    def _fake_get(url, headers, params, timeout):
        calls.append((url, headers, params, timeout))
        if len(calls) == 1:
            return _Resp(404)
        return _Resp(200)

    monkeypatch.setattr("spark.fetcher.requests.get", _fake_get)

    resp = fetcher._rest_get(
        "/repos/markhazleton/github-stats-spark", params={"p": 1}, include_version=True
    )
    assert resp.status_code == 200
    assert len(calls) == 2
    assert "X-GitHub-Api-Version" in calls[0][1]
    assert "X-GitHub-Api-Version" not in calls[1][1]

    calls.clear()

    def _ok_get(url, headers, params, timeout):
        calls.append((url, headers))
        return _Resp(200)

    monkeypatch.setattr("spark.fetcher.requests.get", _ok_get)
    resp = fetcher._rest_get(
        "/repos/markhazleton/github-stats-spark", include_version=False
    )
    assert resp.status_code == 200
    assert "X-GitHub-Api-Version" not in calls[0][1]


def test_cache_integrity_and_migration_paths(tmp_path):
    cache_dir = tmp_path / "cache"
    cache = APICache(cache_dir=str(cache_dir))

    # Repo-specific entries require explicit week.
    with pytest.raises(ValueError):
        cache.set("commit_counts", "markhazleton", {"x": 1}, repo="repo-one")

    cache.set("cat", "markhazleton", {"v": 1}, repo="repo-one", week="2026W01")
    assert cache.has_entry("cat", "markhazleton", repo="repo-one") is True
    assert (
        cache.has_entry("cat", "markhazleton", repo="repo-one", week="2026W01") is True
    )
    assert (
        cache.has_entry("cat", "markhazleton", repo="repo-one", week="2026W99") is False
    )

    # Corrupt file path handling.
    corrupt_path = cache_dir / "markhazleton" / "repo-one" / "cat" / "2026W02.json"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("not-json", encoding="utf-8")
    cache.manifest.update_entry("markhazleton/repo-one/cat", "2026W02")
    cache.manifest.save()
    assert cache.get("cat", "markhazleton", repo="repo-one", week="2026W02") is None

    # Hash mismatch handling.
    bad_hash_path = cache_dir / "markhazleton" / "repo-one" / "cat" / "2026W03.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value": {"a": 1},
        "hash": "bad-hash",
        "metadata": {},
        "category": "cat",
        "owner": "markhazleton",
        "repo": "repo-one",
        "week": "2026W03",
    }
    import json

    bad_hash_path.write_text(json.dumps(payload), encoding="utf-8")
    cache.manifest.update_entry("markhazleton/repo-one/cat", "2026W03")
    cache.manifest.save()
    assert cache.get("cat", "markhazleton", repo="repo-one", week="2026W03") is None

    # Migration path for ai_summary key format.
    cache.set(
        "ai_summary",
        "markhazleton",
        {"ai_summary": "x"},
        repo="repo-one",
        week="2026-03-01T10-00-00+00-00_abcd",
    )
    result = cache.migrate_ai_summary_cache_keys()
    assert result["moved"] >= 1

    cleared = cache.clear_repository_cache("markhazleton", "repo-one")
    assert cleared >= 1


def test_summarizer_cache_hit_prompt_and_profile_generation(
    tmp_path, sample_repo, sample_commit_history
):
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    summarizer = RepositorySummarizer(cache=cache, enable_ai=False)

    # Cache-hit branch in _generate_ai_summary.
    cache_key = (
        sample_repo.pushed_at.replace(microsecond=0).isoformat().replace(":", "-")
    )
    cache.set(
        "ai_summary",
        "markhazleton",
        {
            "ai_summary": "cached summary",
            "generation_method": "claude-haiku-4-5",
            "generation_timestamp": datetime.now().isoformat(),
            "model_used": "claude-haiku-4-5",
            "tokens_used": 10,
            "confidence_score": 90,
        },
        repo=sample_repo.name,
        week=cache_key,
    )

    summary = summarizer._generate_ai_summary(
        sample_repo,
        "# README\ncontent",
        sample_commit_history,
        repository_owner="markhazleton",
        repo_pushed_at=sample_repo.pushed_at,
    )
    assert summary.ai_summary == "cached summary"

    prompt = summarizer._build_repository_prompt(
        sample_repo,
        "# README\ncontent",
        sample_commit_history,
        language_stats={"Python": 1000, "JavaScript": 200},
        tech_stack=TechnologyStack(repository_name=sample_repo.name),
    )
    assert "Repository: repo-one" in prompt
    assert "Languages:" in prompt

    assert "Feature A" in summarizer._extract_features(
        "## Features\n- Feature A\n- Feature B"
    )
    assert summarizer._extract_description("# Title\n\nFirst paragraph.")

    before = summarizer.total_cost
    summarizer._track_cost(1000)
    assert summarizer.total_cost > before
    usage = summarizer.get_usage_stats()
    assert "cache_hits" in usage

    # UserProfileGenerator branch coverage.
    profile_gen = UserProfileGenerator(summarizer)
    repositories = [sample_repo]
    histories = {sample_repo.name: sample_commit_history}
    tech_stacks = {sample_repo.name: TechnologyStack(repository_name=sample_repo.name)}
    profile = profile_gen.generate_profile(
        "markhazleton", repositories, histories, tech_stacks
    )
    assert profile.username == "markhazleton"
    assert profile.total_repos == 1


def test_summarizer_ai_generation_and_model_fallback(
    tmp_path, sample_repo, sample_commit_history
):
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    summarizer = RepositorySummarizer(cache=cache, enable_ai=False)

    class _NotFound(Exception):
        pass

    class _Usage:
        input_tokens = 100
        output_tokens = 40

    class _Response:
        content = [SimpleNamespace(text="ai summary")]
        usage = _Usage()

    class _Messages:
        def __init__(self):
            self.calls = 0

        def create(self, model, max_tokens, messages):
            self.calls += 1
            if self.calls == 1:
                raise _NotFound("model not found")
            return _Response()

    summarizer.anthropic = SimpleNamespace(messages=_Messages())
    from spark import summarizer as summarizer_module

    original_not_found = summarizer_module.NotFoundError
    summarizer_module.NotFoundError = _NotFound
    try:
        summary = summarizer._generate_ai_summary(
            sample_repo,
            "# README\ncontent",
            sample_commit_history,
            repository_owner="markhazleton",
            repo_pushed_at=sample_repo.pushed_at,
        )
    finally:
        summarizer_module.NotFoundError = original_not_found

    assert summary.ai_summary == "ai summary"
    assert summarizer.total_tokens_used == 140


def test_summarizer_fallback_methods_and_truncation(sample_repo, sample_commit_history):
    summarizer = RepositorySummarizer(enable_ai=False)

    enhanced = summarizer._generate_enhanced_fallback(
        sample_repo,
        "# Title\n\nGreat project.\n\n## Features\n- Fast\n- Reliable\n",
        sample_commit_history,
    )
    assert enhanced.generation_method == "enhanced-template"
    assert "Built with" in enhanced.fallback_summary

    plain_repo = Repository(
        name="plain",
        description=None,
        url="https://github.com/markhazleton/plain",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        pushed_at=datetime.now(timezone.utc),
        primary_language=None,
        stars=0,
        forks=0,
        watchers=0,
        open_issues=0,
        is_archived=False,
        is_fork=False,
        is_private=False,
        size_kb=1,
    )
    basic = summarizer._generate_basic_fallback(plain_repo, None)
    assert basic.generation_method == "basic-template"
    assert "repository" in basic.fallback_summary

    long_readme = "# T\n\n" + ("x" * (summarizer.MAX_README_LENGTH + 200))
    truncated = summarizer._truncate_readme(long_readme)
    assert len(truncated) <= summarizer.MAX_README_LENGTH


def test_summarizer_summarize_repository_branching(sample_repo, sample_commit_history):
    summarizer = RepositorySummarizer(enable_ai=False)

    # readme available -> enhanced fallback
    summary = summarizer.summarize_repository(
        sample_repo, "# Title\n\nDesc", sample_commit_history, allow_ai=False
    )
    assert summary.generation_method == "enhanced-template"

    # readme missing -> basic fallback
    summary_no_readme = summarizer.summarize_repository(
        sample_repo, None, sample_commit_history, allow_ai=False
    )
    assert summary_no_readme.generation_method == "basic-template"


def test_user_profile_generator_detects_patterns_and_template_text(sample_repo):
    summarizer = RepositorySummarizer(enable_ai=False)
    profile_gen = UserProfileGenerator(summarizer)

    now = datetime.now(timezone.utc)
    repos = []
    histories = {}
    tech_stacks = {}
    for i in range(3):
        repo = Repository(
            name=f"repo-{i}",
            description="repo",
            url=f"https://github.com/markhazleton/repo-{i}",
            created_at=now - timedelta(days=100 + i),
            updated_at=now - timedelta(days=2),
            pushed_at=now - timedelta(days=2),
            primary_language="Python",
            language_stats={"Python": 1000, "JavaScript": 700, "Go": 500, "Rust": 400},
            stars=5,
            forks=1,
            watchers=2,
            open_issues=0,
            is_archived=False,
            is_fork=False,
            is_private=False,
            size_kb=5,
            has_readme=True,
        )
        repos.append(repo)
        histories[repo.name] = CommitHistory(
            repository_name=repo.name,
            total_commits=50,
            recent_90d=30,
            recent_180d=60,
            recent_365d=120,
            last_commit_date=now - timedelta(days=1),
        )
        tech_stacks[repo.name] = TechnologyStack(
            repository_name=repo.name, frameworks=["react", "pytest"]
        )

    profile = profile_gen.generate_profile(
        "markhazleton", repos, histories, tech_stacks
    )
    assert profile.activity_patterns
    template = profile_gen._generate_template_impression(profile)
    assert "markhazleton" in template


def test_user_profile_generator_ai_impression_success_and_fallback(sample_repo):
    summarizer = RepositorySummarizer(enable_ai=False)
    profile_gen = UserProfileGenerator(summarizer)

    profile = UserProfile(
        username="markhazleton",
        total_repos=1,
        active_repos=1,
        primary_languages={"Python": 1000},
        framework_usage={"pytest": 1},
        commit_frequency=3.0,
    )

    # AI success path
    summarizer.anthropic = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                content=[SimpleNamespace(text="AI profile impression")]
            )
        )
    )
    assert (
        profile_gen._generate_ai_impression(profile, [sample_repo])
        == "AI profile impression"
    )

    # AI failure fallback path in generate_profile
    summarizer.anthropic = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        )
    )
    history = CommitHistory(
        repository_name=sample_repo.name,
        total_commits=5,
        recent_90d=3,
        recent_180d=4,
        recent_365d=5,
        last_commit_date=datetime.now(timezone.utc),
    )
    generated = profile_gen.generate_profile(
        "markhazleton",
        [sample_repo],
        {sample_repo.name: history},
        {sample_repo.name: TechnologyStack(repository_name=sample_repo.name)},
    )
    assert generated.overall_impression


def test_unified_workflow_fetch_generate_report_paths(
    spark_config_factory, tmp_path, sample_repo, sample_commit_history
):
    config = spark_config_factory(theme="spark-light")
    workflow = UnifiedReportWorkflow(
        config, cache=APICache(cache_dir=str(tmp_path / ".cache")), cache_only=False
    )

    username = "markhazleton"
    (sample_repo.pushed_at.replace(microsecond=0).isoformat().replace(":", "-"))

    class _Cache:
        def get(self, category, owner, repo=None, week=None):
            if category == "user_profile":
                return {"username": username, "public_repos": 1}
            if category == "repositories":
                return [
                    {
                        "name": sample_repo.name,
                        "full_name": f"{username}/{sample_repo.name}",
                        "description": sample_repo.description,
                        "language": "Python",
                        "stars": 1,
                        "forks": 0,
                        "watchers": 0,
                        "created_at": sample_repo.created_at.isoformat(),
                        "updated_at": sample_repo.updated_at.isoformat(),
                        "pushed_at": sample_repo.pushed_at.isoformat(),
                        "is_fork": False,
                        "is_private": False,
                        "is_archived": False,
                    }
                ]
            if category == "commit_counts":
                return {
                    "total": 10,
                    "recent_90d": 5,
                    "recent_180d": 7,
                    "recent_365d": 10,
                    "last_commit_date": datetime.now(timezone.utc).isoformat(),
                }
            if category == "commits":
                return [
                    {
                        "date": datetime.now(timezone.utc).isoformat(),
                        "repo": sample_repo.name,
                    }
                ]
            if category == "languages":
                return {"Python": 1000}
            return None

    workflow.cache = _Cache()
    workflow.fetcher = SimpleNamespace(
        fetch_commit_counts=lambda *args, **kwargs: {
            "total": 0,
            "recent_90d": 0,
            "recent_180d": 0,
            "recent_365d": 0,
            "last_commit_date": None,
        }
    )

    data = workflow._fetch_github_data(username)
    assert data.cache_hit_count >= 3

    workflow.visualizer = SimpleNamespace(
        generate_overview=lambda **kwargs: "<svg/>",
        generate_heatmap=lambda **kwargs: "<svg/>",
        generate_streaks=lambda **kwargs: "<svg/>",
        generate_release_cadence=lambda **kwargs: "<svg/>",
        generate_languages=lambda **kwargs: "<svg/>",
        generate_fun_stats=lambda **kwargs: "<svg/>",
    )
    workflow.config.get_enabled_stats = lambda: [
        "overview",
        "heatmap",
        "streaks",
        "release",
        "languages",
        "fun",
    ]
    workflow.output_dir = Path(tmp_path / "output")
    generated = workflow._generate_svgs(username, data)
    assert len(generated) == 6

    report = workflow._generate_unified_report(username, data, ["overview"], [])
    assert report.username == username


def test_unified_workflow_execute_and_internal_branches(
    spark_config_factory, tmp_path, sample_repo, sample_commit_history
):
    config = spark_config_factory(theme="spark-light")
    workflow = UnifiedReportWorkflow(
        config, cache=APICache(cache_dir=str(tmp_path / ".cache")), cache_only=False
    )

    github_data = GitHubData(
        username="markhazleton",
        profile=UserProfile.from_dict({"username": "markhazleton", "public_repos": 1}),
        repositories=[sample_repo],
        commit_histories={sample_repo.name: sample_commit_history},
        fetch_timestamp=datetime.now(timezone.utc),
        api_call_count=1,
        cache_hit_count=1,
    )

    # Cover execute with partial-failure handling branches.
    workflow._fetch_github_data = lambda username: github_data
    workflow._generate_svgs = lambda username, data: (_ for _ in ()).throw(
        RuntimeError("svg failure")
    )
    workflow._analyze_repositories = lambda username, repos, commits: (
        _ for _ in ()
    ).throw(RuntimeError("analysis failure"))
    workflow._generate_unified_report = lambda **kwargs: UnifiedReport(
        username="markhazleton",
        timestamp=datetime.now(timezone.utc),
        repositories=[],
        available_svgs=[],
    )

    report = workflow.execute("markhazleton")
    assert any("SVG generation failed" in w for w in report.warnings)
    assert any("Repository analysis failed" in w for w in report.warnings)

    workflow._analyze_repositories = (
        UnifiedReportWorkflow._analyze_repositories.__get__(
            workflow,
            UnifiedReportWorkflow,
        )
    )

    # Cover _generate_single_svg dispatch and unknown branch.
    workflow.visualizer = SimpleNamespace(
        generate_overview=lambda **kwargs: "<svg/>",
        generate_heatmap=lambda **kwargs: "<svg/>",
        generate_streaks=lambda **kwargs: "<svg/>",
        generate_release_cadence=lambda **kwargs: "<svg/>",
        generate_languages=lambda **kwargs: "<svg/>",
        generate_fun_stats=lambda **kwargs: "<svg/>",
    )
    for svg_type in ["overview", "heatmap", "streaks", "release", "languages", "fun"]:
        assert workflow._generate_single_svg(svg_type, "markhazleton", {}) == "<svg/>"
    with pytest.raises(ValueError):
        workflow._generate_single_svg("unknown", "markhazleton", {})

    # Cover analyze path with cached summary present.
    workflow.ranker = SimpleNamespace(
        rank_repositories=lambda repos, histories, top_n=50: [(sample_repo, 88.5)]
    )
    workflow.dependency_analyzer = SimpleNamespace(
        analyze_repository=lambda files: {},
        build_technology_stack=lambda repository_name, report: TechnologyStack(
            repository_name=repository_name
        ),
    )
    workflow.summarizer = SimpleNamespace(
        summarize_repository=lambda **kwargs: RepositorySummary(
            repo_id=sample_repo.name, fallback_summary="fallback"
        )
    )

    class _MapCache:
        def __init__(self, key):
            self.key = key

        def get(self, category, username, repo=None, week=None):
            if category == "readme":
                return "# README"
            if category == "languages":
                return {"Python": 1000}
            if category == "dependency_files":
                return {"requirements.txt": "requests"}
            if category == "ai_summary":
                return {
                    "ai_summary": "cached",
                    "generation_method": "cached",
                    "generation_timestamp": datetime.now().isoformat(),
                    "model_used": "claude-haiku-4-5",
                    "tokens_used": 5,
                    "confidence_score": 90,
                }
            return None

    workflow.cache = _MapCache(sample_repo.pushed_at)
    analyses = workflow._analyze_repositories(
        "markhazleton", [sample_repo], {sample_repo.name: sample_commit_history}
    )
    assert len(analyses) == 1
    assert analyses[0].summary.ai_summary == "cached"
