"""Regression coverage for unified workflow theme handling."""

from datetime import datetime, timezone

import pytest

from spark.cache import APICache
from spark.themes.spark_light import SparkLightTheme
from spark.time_utils import sanitize_timestamp_for_filename
from spark.unified_report_workflow import UnifiedReportWorkflow


def test_workflow_uses_configured_builtin_theme(spark_config_factory, tmp_path):
    config = spark_config_factory(theme="spark-light")

    workflow = UnifiedReportWorkflow(
        config, cache=APICache(cache_dir=str(tmp_path / ".cache"))
    )

    assert isinstance(workflow.theme, SparkLightTheme)
    assert workflow.visualizer.theme is workflow.theme


def test_workflow_uses_configured_custom_theme(spark_config_factory, tmp_path):
    config = spark_config_factory(
        theme="ocean",
        custom_themes={
            "ocean": {
                "colors": {
                    "primary": "#06B6D4",
                    "accent": "#8B5CF6",
                    "background": "#0C4A6E",
                    "text": "#E0F2FE",
                    "border": "#075985",
                },
                "effects": {"glow": True, "gradient": True, "animations": False},
            }
        },
    )

    workflow = UnifiedReportWorkflow(
        config, cache=APICache(cache_dir=str(tmp_path / ".cache"))
    )

    assert workflow.theme.name == "ocean"
    assert workflow.visualizer.theme.primary_color == "#06B6D4"


def test_workflow_rejects_unknown_theme(spark_config_factory, tmp_path):
    config = spark_config_factory(
        theme="unknown-theme", custom_themes={"ocean": {"colors": {}, "effects": {}}}
    )

    with pytest.raises(ValueError):
        UnifiedReportWorkflow(
            config, cache=APICache(cache_dir=str(tmp_path / ".cache"))
        )


class _MemoryCache:
    def __init__(self, records):
        self.records = records

    def get(self, category, username, repo=None, week=None):
        return self.records.get((category, username, repo, week))


class _NoopFetcher:
    def fetch_user_profile(self, username):
        raise AssertionError("Profile should have been served from cache")

    def fetch_repositories(
        self, username, exclude_private=True, exclude_forks=True, exclude_archived=True
    ):
        raise AssertionError("Repositories should have been served from cache")

    def fetch_commit_counts(self, username, repo_name, repo_pushed_at=None):
        return {
            "total": 3,
            "recent_90d": 2,
            "recent_180d": 3,
            "recent_365d": 3,
            "last_commit_date": "2026-03-01T00:00:00+00:00",
        }


def test_workflow_tracks_cache_hit_count(spark_config_factory, tmp_path):
    config = spark_config_factory(theme="spark-light")
    workflow = UnifiedReportWorkflow(
        config, cache=APICache(cache_dir=str(tmp_path / ".cache")), cache_only=False
    )

    pushed_at = "2026-03-01T00:00:00+00:00"
    cache_key = sanitize_timestamp_for_filename(datetime.fromisoformat(pushed_at))
    username = "markhazleton"
    variant = "list_True_True_True"

    cached_repo = {
        "name": "repo-one",
        "full_name": "markhazleton/repo-one",
        "description": "cached",
        "language": "Python",
        "stars": 1,
        "forks": 0,
        "watchers": 0,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-03-01T00:00:00+00:00",
        "pushed_at": pushed_at,
        "is_fork": False,
        "is_private": False,
        "is_archived": False,
    }

    cache_records = {
        ("user_profile", username, None, None): {
            "username": username,
            "public_repos": 1,
        },
        ("repositories", username, variant, None): [cached_repo],
        ("commit_counts", username, "repo-one", cache_key): {
            "total": 10,
            "recent_90d": 4,
            "recent_180d": 6,
            "recent_365d": 8,
            "last_commit_date": datetime.now(timezone.utc).isoformat(),
        },
    }

    workflow.cache = _MemoryCache(cache_records)
    workflow.fetcher = _NoopFetcher()

    github_data = workflow._fetch_github_data(username)

    assert github_data.cache_hit_count == 3
