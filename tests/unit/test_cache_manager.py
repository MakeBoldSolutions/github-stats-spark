"""Regression coverage for cache manager delegation boundaries."""

from datetime import datetime, timezone

from spark.cache_manager import CacheManager, RefreshResult
import spark.cache_manager as cache_manager_module
from spark.cache_refresh_strategy import get_refresh_categories


class DummyCache:
    """Minimal cache stub for CacheManager tests."""

    def get(self, *args, **kwargs):
        return None


def test_refresh_user_data_uses_repository_filter(monkeypatch, remediation_repo_list):
    manager = CacheManager(github_client=object(), cache=DummyCache())
    calls = {}

    def fake_filter(repo_list):
        calls["filtered_names"] = [repo["name"] for repo in repo_list]
        return [repo_list[0]]

    monkeypatch.setattr(
        cache_manager_module, "filter_refreshable_repositories", fake_filter
    )
    monkeypatch.setattr(
        cache_manager_module, "should_refresh_repository", lambda *args, **kwargs: False
    )

    summary = manager.refresh_user_data("markhazleton", remediation_repo_list)

    assert calls["filtered_names"] == [repo["name"] for repo in remediation_repo_list]
    assert summary.total_repos == 1
    assert summary.repos_unchanged == 1


def test_refresh_user_data_uses_refresh_strategy(monkeypatch):
    manager = CacheManager(github_client=object(), cache=DummyCache())
    calls = {}
    repo_list = [{"name": "public-repo", "pushed_at": "2026-03-01T12:00:00+00:00"}]

    monkeypatch.setattr(
        cache_manager_module,
        "filter_refreshable_repositories",
        lambda repo_list: repo_list,
    )

    def fake_strategy(
        needs_refresh, username, repo_name, pushed_at, include_ai_summaries=False
    ):
        calls["args"] = {
            "username": username,
            "repo_name": repo_name,
            "include_ai_summaries": include_ai_summaries,
        }
        return True

    monkeypatch.setattr(
        cache_manager_module, "should_refresh_repository", fake_strategy
    )
    monkeypatch.setattr(
        manager,
        "refresh_repository",
        lambda *args, **kwargs: [
            RefreshResult(
                repo_name="public-repo",
                category="commit_counts",
                was_cached=False,
                refreshed=True,
            )
        ],
    )

    summary = manager.refresh_user_data(
        "markhazleton", repo_list, include_ai_summaries=True
    )

    assert calls["args"] == {
        "username": "markhazleton",
        "repo_name": "public-repo",
        "include_ai_summaries": True,
    }
    assert summary.repos_refreshed == 1


def test_refresh_categories_include_enrichment_summaries():
    categories = get_refresh_categories(include_ai_summaries=False)

    assert "pull_request_summary" in categories
    assert "security_summary" in categories
    assert "languages" in categories
    assert "quality_indicators" in categories
    assert "commit_counts" in categories
    # Removed — too costly, use other signals
    assert "contributor_stats" not in categories
    assert "code_frequency" not in categories
    assert "commits_stats" not in categories


def test_refresh_repository_includes_commit_stats(monkeypatch):
    manager = CacheManager(github_client=object(), cache=DummyCache(), fetcher=object())
    calls = []

    pushed_at = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        manager,
        "refresh_commit_counts",
        lambda username, repo_name, pushed_at: calls.append("commit_counts")
        or RefreshResult(repo_name, "commit_counts", False, True),
    )
    monkeypatch.setattr(
        manager,
        "refresh_commits_stats",
        lambda username, repo_name, pushed_at: calls.append("commits_stats")
        or RefreshResult(repo_name, "commits_stats", False, True),
    )

    # Only pass non-batch categories (languages/readme/quality/deps handled by batch)
    manager.refresh_repository(
        username="markhazleton",
        repo_name="repo-one",
        pushed_at=pushed_at,
        categories={"commit_counts", "commits_stats"},
    )

    assert calls == ["commit_counts", "commits_stats"]
