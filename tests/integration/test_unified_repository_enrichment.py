"""Integration tests for unified repository enrichment payload assembly."""

from datetime import datetime, timezone

import yaml

from spark.cache import APICache
from spark.cache_manager import RefreshSummary
from spark.config import SparkConfig
from spark.unified_data_generator import UnifiedDataGenerator
from spark.time_utils import sanitize_timestamp_for_filename


def _build_repo_payload(name="repo-one"):
    now = datetime.now(timezone.utc)
    return {
        "name": name,
        "description": "repo",
        "url": f"https://github.com/markhazleton/{name}",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "pushed_at": now.isoformat(),
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


def test_unified_data_generator_emits_enrichment_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    config = _create_config(tmp_path)
    cache = APICache(cache_dir=str(tmp_path / "cache"))
    generator = UnifiedDataGenerator(
        username="markhazleton",
        config=config,
        output_dir=tmp_path / "data",
        cache=cache,
    )

    repo = _build_repo_payload()
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    cache_key = sanitize_timestamp_for_filename(pushed_at)

    cache.set(
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
    cache.set(
        "languages", "markhazleton", {"Python": 100}, repo=repo["name"], week=cache_key
    )
    cache.set(
        "quality_indicators",
        "markhazleton",
        {"has_license": True, "has_ci_cd": True, "has_tests": True, "has_docs": False},
        repo=repo["name"],
        week=cache_key,
    )
    cache.set(
        "pull_request_summary",
        "markhazleton",
        {
            "availability": "available",
            "reason": "none",
            "has_open_pull_requests": True,
            "total_open": 2,
            "draft_count": 1,
            "review_requested_count": 1,
            "oldest_open_age_days": 7,
            "source": "rest.pulls.list",
        },
        repo=repo["name"],
        week=cache_key,
    )
    cache.set(
        "security_summary",
        "markhazleton",
        {
            "availability": "partial",
            "reason": "permission_denied",
            "overall_state": "warning_present",
            "feature_status": {
                "advanced_security": "unavailable",
                "secret_scanning": "unavailable",
                "secret_scanning_push_protection": "unavailable",
                "dependency_alerts": "enabled",
                "automated_security_fixes": "enabled",
            },
            "active_alert_counts": {
                "total_open": 1,
                "critical": 1,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "sources": ["rest.dependabot.alerts"],
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

    assert unified["metadata"]["schema_version"] == "2.3.0"
    assert unified["metadata"]["attention_formula_version"] == "1.0"
    assert "pull_request_summary" in unified["repositories"][0]
    assert "security_summary" in unified["repositories"][0]
    assert "attention_metrics" in unified["repositories"][0]
    assert unified["repositories"][0]["attention_rank"] == 1
    assert unified["repositories"][0]["pull_request_summary"]["total_open"] == 2
