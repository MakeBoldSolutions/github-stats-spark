"""Regression coverage for dashboard generator profile aggregation."""

import yaml
import pytest

from spark.config import SparkConfig
from spark.dashboard_generator import DashboardGenerator


class StubFetcher:
    """Simple fetcher stub for dashboard tests."""

    def get_user(self):
        return {
            "login": "markhazleton",
            "avatar_url": "https://example.com/avatar.png",
            "public_repos": 2,
            "html_url": "https://github.com/markhazleton",
        }


@pytest.fixture
def full_config(tmp_path) -> SparkConfig:
    """Create a SparkConfig with all required keys for DashboardGenerator tests."""
    config_data = {
        "users": ["markhazleton"],
        "stats": {
            "enabled": ["overview"],
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
        "analyzer": {
            "top_n": 50,
            "ai_provider": "anthropic",
            "ai_model": "claude-haiku-4-5",
            "ranking_weights": {"popularity": 0.30, "activity": 0.45, "health": 0.25},
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
    cfg_file = tmp_path / "spark.yml"
    cfg_file.write_text(yaml.dump(config_data))
    cfg = SparkConfig(str(cfg_file))
    cfg.load()
    return cfg


def test_generate_user_profile_aggregates_included_repository_totals(
    full_config, dashboard_repositories
):
    generator = DashboardGenerator(full_config, "markhazleton")
    generator.fetcher = StubFetcher()

    profile = generator.generate_user_profile(dashboard_repositories)

    assert profile.total_commits == 20
    assert profile.total_stars == 12
    assert profile.total_forks == 5


def test_generate_uses_repository_set_for_profile_totals(
    monkeypatch, full_config, dashboard_repositories
):
    generator = DashboardGenerator(full_config, "markhazleton")
    generator.fetcher = StubFetcher()
    monkeypatch.setattr(
        generator, "generate_dashboard_data", lambda: dashboard_repositories
    )

    dashboard_data = generator.generate()

    assert dashboard_data.metadata.repository_count == 2
    assert dashboard_data.profile.total_stars == 12
    assert dashboard_data.profile.total_forks == 5
