"""Integration tests for partial/unavailable enrichment propagation."""

from datetime import datetime, timezone

import yaml

from spark.cache import APICache
from spark.cache_manager import RefreshSummary
from spark.config import SparkConfig
from spark.unified_data_generator import UnifiedDataGenerator


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
                    "exclude_forks": True,
                    "exclude_archived": True,
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


def test_unified_data_generator_preserves_unavailable_states(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    config = _create_config(tmp_path)
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    generator = UnifiedDataGenerator(
        username="markhazleton",
        config=config,
        output_dir=tmp_path / "data",
        cache=cache,
        force_refresh=False,
    )

    now = datetime.now(timezone.utc).isoformat()
    repo = {
        "name": "repo-unavailable",
        "description": "repo",
        "url": "https://github.com/markhazleton/repo-unavailable",
        "created_at": now,
        "updated_at": now,
        "pushed_at": now,
        "language": "Python",
        "stars": 0,
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

    # Pre-populate cache with enrichment data so Phase 3 reads them
    from spark.time_utils import sanitize_timestamp_for_filename

    push_key = sanitize_timestamp_for_filename(datetime.fromisoformat(now))
    cache.set(
        "pull_request_summary",
        "markhazleton",
        {
            "availability": "unavailable",
            "reason": "permission_denied",
            "has_open_pull_requests": False,
            "total_open": 0,
            "draft_count": 0,
            "review_requested_count": 0,
            "oldest_open_age_days": None,
            "source": "rest.pulls.list",
        },
        repo="repo-unavailable",
        week=push_key,
    )
    cache.set(
        "security_summary",
        "markhazleton",
        {
            "availability": "partial",
            "reason": "api_error",
            "overall_state": "clear",
            "feature_status": {
                "advanced_security": "unknown",
                "secret_scanning": "unknown",
                "secret_scanning_push_protection": "unknown",
                "dependency_alerts": "disabled",
                "automated_security_fixes": "disabled",
            },
            "active_alert_counts": {
                "total_open": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "sources": ["rest.repos.get"],
        },
        repo="repo-unavailable",
        week=push_key,
    )

    monkeypatch.setattr(generator, "_fetch_repository_list", lambda: [repo])
    monkeypatch.setattr(
        generator.cache_manager,
        "refresh_user_data",
        lambda **kwargs: RefreshSummary(
            total_repos=1,
            repos_refreshed=1,
            repos_unchanged=0,
            repos_failed=0,
            results=[],
            api_calls_made=2,
        ),
    )

    unified = generator.generate()

    repo_payload = unified["repositories"][0]
    assert repo_payload["pull_request_summary"]["availability"] == "unavailable"
    assert repo_payload["pull_request_summary"]["reason"] == "permission_denied"
    assert repo_payload["security_summary"]["availability"] == "partial"
    assert repo_payload["security_summary"]["reason"] == "api_error"
