"""Shared fixtures for remediation-focused unit tests."""

from datetime import datetime, timezone

import pytest
import yaml

from spark.config import SparkConfig
from spark.models.dashboard_data import DashboardRepository


@pytest.fixture
def remediation_repo_list():
    """Repository payloads covering public, private, fork, and archived cases."""
    return [
        {"name": "public-repo", "pushed_at": "2026-03-01T12:00:00+00:00"},
        {
            "name": "private-repo",
            "private": True,
            "pushed_at": "2026-03-01T12:00:00+00:00",
        },
        {"name": "fork-repo", "fork": True, "pushed_at": "2026-03-01T12:00:00+00:00"},
        {
            "name": "archived-repo",
            "archived": True,
            "pushed_at": "2026-03-01T12:00:00+00:00",
        },
    ]


@pytest.fixture(autouse=True)
def github_token_env(monkeypatch):
    """Provide a dummy GitHub token for constructor-only unit tests."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")


@pytest.fixture
def dashboard_repositories():
    """Dashboard repositories with deterministic totals for profile tests."""
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    last_commit_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
    return [
        DashboardRepository(
            name="alpha",
            language="Python",
            created_at=created_at,
            last_commit_date=last_commit_date,
            commit_count=12,
            url="https://github.com/markhazleton/alpha",
            stars=7,
            forks=3,
        ),
        DashboardRepository(
            name="beta",
            language="JavaScript",
            created_at=created_at,
            last_commit_date=last_commit_date,
            commit_count=8,
            url="https://github.com/markhazleton/beta",
            stars=5,
            forks=2,
        ),
    ]


@pytest.fixture
def spark_config_factory(tmp_path):
    """Create and load SparkConfig instances for workflow/config tests."""

    def factory(theme="spark-dark", custom_themes=None):
        config_path = tmp_path / "spark.yml"
        themes_path = tmp_path / "themes.yml"

        config_data = {
            "users": ["testuser"],
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
                "theme": theme,
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
        themes_data = {"custom_themes": custom_themes or {}}

        config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")
        themes_path.write_text(yaml.safe_dump(themes_data), encoding="utf-8")

        config = SparkConfig(str(config_path))
        config.load()
        return config

    return factory
