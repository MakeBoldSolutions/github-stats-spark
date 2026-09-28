"""Unit tests for enrichment-focused UnifiedDataGenerator behavior."""

from datetime import datetime, timezone

import pytest
import yaml

from spark.cache import APICache
from spark.cache_manager import RefreshSummary
from spark.config import SparkConfig
from spark.unified_data_generator import UnifiedDataGenerator
from spark.time_utils import sanitize_timestamp_for_filename


def _create_config(tmp_path):
    config_path = tmp_path / "spark.yml"
    themes_path = tmp_path / "themes.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "users": ["markhazleton"],
                "stats": {
                    "enabled": [
                        "overview",
                        "heatmap",
                        "languages",
                        "fun",
                        "streaks",
                        "release",
                    ],
                    "thresholds": {
                        "graveyard_months": 6,
                        "starter_commits": 50,
                        "power_user_commits": 1000,
                        "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                        "early_bird_hours": [5, 6, 7, 8, 9],
                    },
                },
                "visualization": {
                    "theme": "spark-dark",
                    "effects": {"glow": True, "gradient": True},
                },
                "cache": {"enabled": True, "directory": str(tmp_path / ".cache")},
                "repositories": {
                    "max_count": 500,
                    "exclude_private": True,
                    "exclude_forks": False,
                    "exclude_archived": False,
                },
                "analyzer": {
                    "top_n": 50,
                    "ai_provider": "anthropic",
                    "ai_model": "claude-haiku-4-5",
                    "ranking_weights": {
                        "popularity": 0.30,
                        "activity": 0.45,
                        "health": 0.25,
                    },
                },
                "github": {
                    "api_version": {
                        "enabled": False,
                        "version": "2026-03-10",
                        "fallback_to_default": True,
                    }
                },
                "dashboard": {
                    "enabled": True,
                    "output_dir": str(tmp_path / "data"),
                    "data_generation": {
                        "include_commit_metrics": True,
                        "include_language_stats": True,
                        "include_ai_summaries": False,
                        "max_commits_per_repo": 500,
                        "max_repositories": 50,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    themes_path.write_text(yaml.safe_dump({"custom_themes": {}}), encoding="utf-8")

    config = SparkConfig(str(config_path))
    config.load()
    return config


def _build_repo_payload(name="repo-one", pushed_at=None):
    now = datetime.now(timezone.utc)
    pushed = pushed_at if pushed_at is not None else now.isoformat()
    return {
        "name": name,
        "description": "repo",
        "url": f"https://github.com/markhazleton/{name}",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "pushed_at": pushed,
        "language": "Python",
        "stars": 1,
        "forks": 0,
        "watchers": 0,
        "open_issues": 0,
        "is_archived": False,
        "is_fork": False,
        "is_private": False,
        "homepage": None,
        "has_pages": False,
        "size": 10,
    }


@pytest.fixture
def generator(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    config = _create_config(tmp_path)
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    return UnifiedDataGenerator(
        username="markhazleton",
        config=config,
        output_dir=tmp_path / "data",
        cache=cache,
        force_refresh=False,
    )


def test_fetch_repository_list_uses_configured_filters(generator, monkeypatch):
    calls = {}

    def fake_fetch_repositories(**kwargs):
        calls.update(kwargs)
        return []

    monkeypatch.setattr(
        generator.fetcher, "fetch_repositories", fake_fetch_repositories
    )

    result = generator._fetch_repository_list()

    assert result == []
    assert calls["exclude_private"] is True
    assert calls["exclude_forks"] is False
    assert calls["exclude_archived"] is False


def test_generate_skips_invalid_repository_payload_and_continues(
    generator, monkeypatch
):
    valid_repo = _build_repo_payload("repo-valid")
    invalid_repo = {"name": "repo-invalid", "created_at": "not-a-date"}

    monkeypatch.setattr(
        generator, "_fetch_repository_list", lambda: [invalid_repo, valid_repo]
    )
    monkeypatch.setattr(
        generator.cache_manager,
        "refresh_user_data",
        lambda **kwargs: RefreshSummary(
            total_repos=2,
            repos_refreshed=0,
            repos_unchanged=2,
            repos_failed=0,
            results=[],
            api_calls_made=0,
        ),
    )

    unified = generator.generate()

    assert len(unified["repositories"]) == 1
    assert unified["repositories"][0]["name"] == "repo-valid"


def test_generate_uses_cached_ai_summary_and_handles_invalid_commit_dates(
    generator, monkeypatch
):
    repo = _build_repo_payload("repo-cached")
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    cache_key = sanitize_timestamp_for_filename(pushed_at)

    generator.cache.set(
        "commit_counts",
        "markhazleton",
        {
            "total": 3,
            "recent_90d": 3,
            "recent_180d": 3,
            "recent_365d": 3,
            "last_commit_date": repo["pushed_at"],
        },
        repo=repo["name"],
        week=cache_key,
    )
    generator.cache.set(
        "languages", "markhazleton", {"Python": 100}, repo=repo["name"], week=cache_key
    )
    generator.cache.set(
        "commits_stats",
        "markhazleton",
        [
            {
                "commit": {"author": {"date": "2026-03-01T00:00:00Z"}},
                "stats": {"total": 1, "additions": 2, "deletions": 1},
            },
            {
                "commit": {"author": {"date": "invalid-date"}},
                "stats": {"total": 1, "additions": 1, "deletions": 0},
            },
        ],
        repo=repo["name"],
        week=cache_key,
    )
    generator.cache.set(
        "ai_summary",
        "markhazleton",
        {
            "ai_summary": "cached-ai-summary",
            "generation_method": "claude",
            "generation_timestamp": "2026-03-01T00:00:00Z",
            "model_used": "haiku",
            "tokens_used": 100,
            "confidence_score": 0.9,
        },
        repo=repo["name"],
        week=cache_key,
    )

    monkeypatch.setattr(generator, "_fetch_repository_list", lambda: [repo])
    monkeypatch.setattr(
        generator.cache_manager,
        "refresh_user_data",
        lambda **kwargs: RefreshSummary(
            total_repos=1,
            repos_refreshed=0,
            repos_unchanged=1,
            repos_failed=0,
            results=[],
            api_calls_made=0,
        ),
    )

    unified = generator.generate()

    assert unified["repositories"][0]["summary"]["text"] == "cached-ai-summary"
    assert unified["repositories"][0]["ai_summary"] == "cached-ai-summary"


def test_generate_emits_diagnostics_summary(generator, monkeypatch):
    repo = _build_repo_payload("repo-diagnostics")
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    cache_key = sanitize_timestamp_for_filename(pushed_at)

    generator.cache.set(
        "commit_counts",
        "markhazleton",
        {
            "total": 1,
            "recent_90d": 1,
            "recent_180d": 1,
            "recent_365d": 1,
            "last_commit_date": repo["pushed_at"],
        },
        repo=repo["name"],
        week=cache_key,
    )
    generator.cache.set(
        "languages", "markhazleton", {"Python": 100}, repo=repo["name"], week=cache_key
    )
    generator.cache.set(
        "diagnostics_summary",
        "markhazleton",
        {
            "availability": "available",
            "reason": "none",
            "pull_requests": {
                "availability": "available",
                "reason": "none",
                "total_open": 2,
            },
            "issues": {
                "availability": "available",
                "reason": "none",
                "total_open": 3,
                "stale_over_90d": 1,
            },
            "security": {
                "availability": "partial",
                "reason": "not_supported",
                "dependabot": {
                    "total_open": 1,
                    "critical": 0,
                    "high": 1,
                    "medium": 0,
                    "low": 0,
                },
                "code_scanning": {"total_open": 0, "error": 0, "warning": 0, "note": 0},
            },
            "actions": {
                "availability": "available",
                "reason": "none",
                "recent_runs": 5,
                "failure_count": 1,
            },
            "sources": ["rest.pulls.list", "rest.issues.list"],
        },
        repo=repo["name"],
        week=cache_key,
    )

    monkeypatch.setattr(generator, "_fetch_repository_list", lambda: [repo])
    monkeypatch.setattr(
        generator.cache_manager,
        "refresh_user_data",
        lambda **kwargs: RefreshSummary(
            total_repos=1,
            repos_refreshed=0,
            repos_unchanged=1,
            repos_failed=0,
            results=[],
            api_calls_made=0,
        ),
    )

    unified = generator.generate()

    assert (
        unified["repositories"][0]["diagnostics_summary"]["availability"] == "available"
    )
    assert (
        unified["repositories"][0]["diagnostics_summary"]["issues"]["total_open"] == 3
    )


def test_save_writes_output_and_uses_generate_when_input_missing(
    generator, monkeypatch
):
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "profile": {
            "username": "markhazleton",
            "total_repositories": 0,
            "total_stars": 0,
            "total_forks": 0,
            "total_commits": 0,
        },
        "repositories": [],
        "metadata": {
            "generated_at": now,
            "schema_version": "2.2.0",
            "generator": "test",
        },
    }
    monkeypatch.setattr(generator, "generate", lambda: payload)

    output_path, skipped = generator.save()

    assert output_path.name == "repositories.json"
    assert output_path.exists()
    assert skipped is False


def test_save_raises_if_write_fails(generator, monkeypatch):
    payload = {
        "profile": {
            "username": "markhazleton",
            "total_repositories": 0,
            "total_stars": 0,
            "total_forks": 0,
            "total_commits": 0,
        },
        "repositories": [],
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "2.2.0",
            "generator": "test",
        },
    }

    def fail_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", fail_open)

    with pytest.raises(OSError):
        generator.save(unified_data=payload)
