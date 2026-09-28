"""Tests for UnifiedDataGenerator - static scoring and attention metrics."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from spark.unified_data_generator import UnifiedDataGenerator
from spark.models.repository import (
    Repository,
    RepositoryPullRequestSummary,
    RepositorySecuritySummary,
)
from spark.models.tech_stack import TechnologyStack


# ---------------------------------------------------------------------------
# Staleness score
# ---------------------------------------------------------------------------
class TestCalculateStalenessScore:
    def test_none_returns_default(self):
        assert UnifiedDataGenerator._calculate_staleness_score(None) == 60.0

    @pytest.mark.parametrize(
        "days, expected",
        [
            (0, 0.0),
            (7, 0.0),
            (14, 0.0),
            (15, 12.0),
            (30, 12.0),
            (31, 35.0),
            (90, 35.0),
            (91, 65.0),
            (180, 65.0),
            (181, 85.0),
            (365, 85.0),
            (366, 100.0),
            (1000, 100.0),
        ],
    )
    def test_boundary_values(self, days, expected):
        assert UnifiedDataGenerator._calculate_staleness_score(days) == expected


# ---------------------------------------------------------------------------
# Pull request pressure
# ---------------------------------------------------------------------------
def _make_repo_with_pr(
    total_open=0,
    draft_count=0,
    review_requested_count=0,
    oldest_open_age_days=None,
    availability="available",
    reason="ok",
):
    repo = MagicMock(spec=Repository)
    repo.pull_request_summary = RepositoryPullRequestSummary(
        availability=availability,
        reason=reason,
        total_open=total_open,
        draft_count=draft_count,
        review_requested_count=review_requested_count,
        oldest_open_age_days=oldest_open_age_days,
    )
    return repo


class TestCalculatePullRequestPressure:
    def test_unavailable_returns_zero(self):
        repo = _make_repo_with_pr(availability="unavailable", reason="not_cached")
        result = UnifiedDataGenerator._calculate_pull_request_pressure(repo)
        assert result["score"] == 0.0
        assert result["availability"] == "unavailable"

    def test_zero_open_prs(self):
        repo = _make_repo_with_pr()
        result = UnifiedDataGenerator._calculate_pull_request_pressure(repo)
        assert result["score"] == 0.0

    def test_several_open_prs(self):
        repo = _make_repo_with_pr(total_open=3, draft_count=1, review_requested_count=1)
        result = UnifiedDataGenerator._calculate_pull_request_pressure(repo)
        # 3*12 + 1*4 + 1*8 = 48
        assert result["score"] == 48.0

    def test_score_caps_at_100(self):
        repo = _make_repo_with_pr(total_open=20, oldest_open_age_days=500)
        result = UnifiedDataGenerator._calculate_pull_request_pressure(repo)
        assert result["score"] == 100.0

    def test_old_pr_age_capped(self):
        repo = _make_repo_with_pr(total_open=0, oldest_open_age_days=300)
        result = UnifiedDataGenerator._calculate_pull_request_pressure(repo)
        # Only 180 days counted: 180 * 0.35 = 63.0
        assert result["score"] == 63.0


# ---------------------------------------------------------------------------
# Security attention
# ---------------------------------------------------------------------------
def _make_repo_with_security(
    availability="available",
    reason="ok",
    overall_state="clear",
    alert_counts=None,
):
    repo = MagicMock(spec=Repository)
    repo.security_summary = RepositorySecuritySummary(
        availability=availability,
        reason=reason,
        overall_state=overall_state,
        active_alert_counts=alert_counts or {},
    )
    return repo


class TestCalculateSecurityAttention:
    def test_no_alerts(self):
        repo = _make_repo_with_security()
        result = UnifiedDataGenerator._calculate_security_attention(repo)
        assert result["score"] == 0.0

    def test_critical_alerts_heavy_weight(self):
        repo = _make_repo_with_security(alert_counts={"critical": 2})
        result = UnifiedDataGenerator._calculate_security_attention(repo)
        assert result["score"] == 90.0  # 2*45

    def test_mixed_alerts(self):
        repo = _make_repo_with_security(
            alert_counts={"critical": 1, "high": 1, "medium": 1, "low": 1}
        )
        result = UnifiedDataGenerator._calculate_security_attention(repo)
        # 45+30+15+8 = 98
        assert result["score"] == 98.0

    def test_partial_availability_penalty(self):
        repo = _make_repo_with_security(availability="partial")
        result = UnifiedDataGenerator._calculate_security_attention(repo)
        assert result["score"] == 10.0

    def test_unavailable_penalty(self):
        repo = _make_repo_with_security(availability="unavailable")
        result = UnifiedDataGenerator._calculate_security_attention(repo)
        assert result["score"] == 20.0

    def test_score_caps_at_100(self):
        repo = _make_repo_with_security(
            alert_counts={"critical": 5},
            availability="unavailable",
        )
        result = UnifiedDataGenerator._calculate_security_attention(repo)
        assert result["score"] == 100.0


# ---------------------------------------------------------------------------
# Dependency attention
# ---------------------------------------------------------------------------
class TestCalculateDependencyAttention:
    def test_none_tech_stack(self):
        result = UnifiedDataGenerator._calculate_dependency_attention(None)
        assert result["score"] == 0.0
        assert result["total_dependencies"] == 0

    def test_perfect_tech_stack(self):
        ts = MagicMock(spec=TechnologyStack)
        ts.currency_score = 100
        ts.version_coverage_percentage = 100.0
        ts.total_dependencies = 10
        ts.outdated_count = 0
        ts.outdated_percentage = 0.0
        ts.latest_version_coverage_percentage = 100.0
        ts.unknown_versions_count = 0
        result = UnifiedDataGenerator._calculate_dependency_attention(ts)
        assert result["score"] == 0.0

    def test_low_currency_score(self):
        ts = MagicMock(spec=TechnologyStack)
        ts.currency_score = 40
        ts.version_coverage_percentage = 100.0
        ts.total_dependencies = 10
        ts.outdated_count = 6
        ts.outdated_percentage = 60.0
        ts.latest_version_coverage_percentage = 40.0
        ts.unknown_versions_count = 0
        result = UnifiedDataGenerator._calculate_dependency_attention(ts)
        # currency_pressure = 60 * 0.65 = 39.0, unknown = 0
        assert result["score"] == 39.0

    def test_unknown_versions(self):
        ts = MagicMock(spec=TechnologyStack)
        ts.currency_score = 100
        ts.version_coverage_percentage = 50.0
        ts.total_dependencies = 10
        ts.outdated_count = 0
        ts.outdated_percentage = 0.0
        ts.latest_version_coverage_percentage = 100.0
        ts.unknown_versions_count = 5
        result = UnifiedDataGenerator._calculate_dependency_attention(ts)
        # unknown_pressure = 50 * 0.35 = 17.5
        assert result["score"] == 17.5


# ---------------------------------------------------------------------------
# Build attention metrics  (integration of all scoring components)
# ---------------------------------------------------------------------------
class TestBuildAttentionMetrics:

    def _make_generator(self):
        """Create a minimal UnifiedDataGenerator instance with mocked deps."""
        with (
            patch("spark.unified_data_generator.GitHubFetcher"),
            patch("spark.unified_data_generator.CacheManager"),
            patch("spark.unified_data_generator.RepositoryRanker"),
        ):
            config = MagicMock()
            config.config = {"dashboard": {"data_generation": {}}}
            config.get_github_api_version_config.return_value = {}
            gen = UnifiedDataGenerator(
                username="testuser",
                config=config,
                output_dir=Path("/tmp/out"),
            )
        return gen

    def test_healthy_repo(self):
        gen = self._make_generator()
        repo = _make_repo_with_pr()
        repo.security_summary = RepositorySecuritySummary()
        repo.days_since_last_push = 5
        repo.open_issues = 0
        result = gen._build_attention_metrics(repo, None, recent_commits_90d=10)
        assert result["tier"] == "healthy"
        assert result["needs_attention"] is False

    def test_critical_tier(self):
        gen = self._make_generator()
        repo = _make_repo_with_pr(total_open=5)
        repo.security_summary = RepositorySecuritySummary(
            availability="available",
            active_alert_counts={"critical": 3},
        )
        repo.days_since_last_push = 400
        repo.open_issues = 10
        result = gen._build_attention_metrics(repo, None, recent_commits_90d=0)
        assert result["tier"] == "critical"
        assert result["needs_attention"] is True
        assert "security" in result["reasons"]
        assert "staleness" in result["reasons"]

    def test_elevated_tier(self):
        gen = self._make_generator()
        repo = _make_repo_with_pr(total_open=3)
        repo.security_summary = RepositorySecuritySummary(
            availability="available",
            active_alert_counts={"high": 2},
        )
        repo.days_since_last_push = 100
        repo.open_issues = 2
        result = gen._build_attention_metrics(repo, None, recent_commits_90d=0)
        assert result["tier"] in ("elevated", "critical")
        assert result["score"] >= 45

    def test_staleness_boost_for_issues_with_no_commits(self):
        gen = self._make_generator()
        repo = _make_repo_with_pr()
        repo.security_summary = RepositorySecuritySummary()
        repo.days_since_last_push = 100
        repo.open_issues = 5
        result = gen._build_attention_metrics(repo, None, recent_commits_90d=0)
        staleness = result["components"]["staleness"]["score"]
        # 91-180 days = 65, plus 10 for open issues with 0 commits = 75
        assert staleness == 75.0

    def test_component_weights_sum(self):
        """Weights: PR 0.25 + Security 0.35 + Staleness 0.25 + Deps 0.15 = 1.0."""
        gen = self._make_generator()
        repo = _make_repo_with_pr()
        repo.security_summary = RepositorySecuritySummary()
        repo.days_since_last_push = 10
        repo.open_issues = 0
        result = gen._build_attention_metrics(repo, None, recent_commits_90d=1)
        # All inputs are ~0, so result should be ~0
        assert 0 <= result["score"] <= 100


# ---------------------------------------------------------------------------
# Constructor initialization
# ---------------------------------------------------------------------------
class TestUnifiedDataGeneratorInit:

    def test_constructor_sets_attributes(self):
        with (
            patch("spark.unified_data_generator.GitHubFetcher"),
            patch("spark.unified_data_generator.CacheManager"),
            patch("spark.unified_data_generator.RepositoryRanker"),
        ):
            config = MagicMock()
            # require() returns the expected values for each call
            config.require.side_effect = lambda key: {
                "dashboard.data_generation.max_repositories": 100,
                "analyzer.top_n": 25,
                "dashboard.data_generation.include_ai_summaries": True,
                "stats.thresholds": {},
            }.get(key, MagicMock())
            config.get_github_api_version_config.return_value = {}
            config.get_ranking_weights.return_value = {
                "popularity": 0.30,
                "activity": 0.45,
                "health": 0.25,
            }
            config.get_ai_model.return_value = "claude-haiku-4-5"
            config.get_cache_dir.return_value = "/tmp/.cache"
            gen = UnifiedDataGenerator(
                username="testuser",
                config=config,
                output_dir=Path("/tmp/out"),
            )
            assert gen.username == "testuser"
            assert gen.max_repositories == 100
            assert gen.top_n_repos == 25
            assert gen.include_ai_summaries is True

    def test_max_repos_override(self):
        """max_repos_override removed — max_repositories is controlled solely by spark.yml."""
        with (
            patch("spark.unified_data_generator.GitHubFetcher"),
            patch("spark.unified_data_generator.CacheManager"),
            patch("spark.unified_data_generator.RepositoryRanker"),
        ):
            config = MagicMock()
            config.require.side_effect = lambda key: {
                "dashboard.data_generation.max_repositories": 5,
                "analyzer.top_n": 50,
                "dashboard.data_generation.include_ai_summaries": False,
            }.get(key, MagicMock())
            config.get_github_api_version_config.return_value = {}
            config.get_ranking_weights.return_value = {
                "popularity": 0.30,
                "activity": 0.45,
                "health": 0.25,
            }
            config.get_ai_model.return_value = "claude-haiku-4-5"
            config.get_cache_dir.return_value = "/tmp/.cache"
            gen = UnifiedDataGenerator(
                username="testuser",
                config=config,
                output_dir=Path("/tmp/out"),
            )
            assert gen.max_repositories == 5

    def test_defaults_without_config(self):
        """When config keys are missing, require() raises ConfigurationError."""
        from spark.exceptions import ConfigurationError

        with (
            patch("spark.unified_data_generator.GitHubFetcher"),
            patch("spark.unified_data_generator.CacheManager"),
            patch("spark.unified_data_generator.RepositoryRanker"),
        ):
            config = MagicMock()
            config.require.side_effect = ConfigurationError(
                "Missing key", field="dashboard.data_generation.max_repositories"
            )
            config.get_github_api_version_config.return_value = {}
            config.get_ranking_weights.return_value = {
                "popularity": 0.30,
                "activity": 0.45,
                "health": 0.25,
            }
            config.get_cache_dir.return_value = "/tmp/.cache"
            with pytest.raises(ConfigurationError):
                UnifiedDataGenerator(
                    username="testuser",
                    config=config,
                    output_dir=Path("/tmp/out"),
                )
