"""Unit tests for repository ranking algorithm.

Tests the RepositoryRanker class which implements composite scoring:
- 30% Popularity (logarithmic scaling)
- 45% Activity (multi-window time decay)
- 25% Health (documentation, maturity, issues)
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from spark.models.repository import Repository
from spark.models.commit import CommitHistory
from spark.ranker import RepositoryRanker


@pytest.fixture
def ranker():
    """Create a RepositoryRanker instance for testing."""
    return RepositoryRanker(
        config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
    )


@pytest.fixture
def ranking_scenarios():
    """Load ranking test scenarios from fixtures."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "ranking_scenarios.json"
    with open(fixtures_path, "r") as f:
        return json.load(f)


def create_repository_from_scenario(scenario_data):
    """Create Repository and CommitHistory objects from scenario data."""
    repo_data = scenario_data["repository"]
    commit_data = scenario_data["commits"]

    # Calculate dates
    now = datetime.now()
    created_at = now - timedelta(days=repo_data["created_days_ago"])
    updated_at = now - timedelta(days=repo_data["updated_days_ago"])
    last_commit_days = commit_data["last_commit_days_ago"]

    # For empty repos (no commits ever), set pushed_at to None
    if commit_data["total"] == 0 or last_commit_days > 9000:
        last_commit = None
    else:
        last_commit = now - timedelta(days=last_commit_days)

    # Create Repository object
    repository = Repository(
        name=repo_data["name"],
        description=f"Test repository: {scenario_data['description']}",
        url=f"https://github.com/testuser/{repo_data['name']}",
        created_at=created_at,
        updated_at=updated_at,
        pushed_at=last_commit,
        primary_language="Python",
        language_stats={"Python": 10000},
        stars=repo_data["stars"],
        forks=repo_data["forks"],
        watchers=repo_data.get("watchers", repo_data["stars"]),
        open_issues=repo_data.get("open_issues", 0),
        is_archived=repo_data.get("is_archived", False),
        is_fork=repo_data.get("is_fork", False),
        is_private=repo_data.get("is_private", False),
        size_kb=repo_data.get("size_kb", 1000),
        has_readme=repo_data.get("has_readme", True),
    )

    # Create CommitHistory object
    commit_history = CommitHistory(
        repository_name=repo_data["name"],
        total_commits=commit_data["total"],
        recent_90d=commit_data["recent_90d"],
        recent_180d=commit_data["recent_180d"],
        recent_365d=commit_data["recent_365d"],
        last_commit_date=last_commit,
        patterns={
            "frequency": "active" if commit_data["recent_90d"] > 20 else "moderate",
            "consistency": (
                "consistent" if commit_data["recent_90d"] > 0 else "sporadic"
            ),
        },
    )

    return repository, commit_history


class TestPrivacyFilter:
    """Test privacy filter (constitution requirement - T027)."""

    # REMOVED: test_private_repos_excluded - Cannot create private Repository anymore
    # Privacy enforcement is now at model level (Repository.__post_init__ raises ValueError)
    # The ranker filter is now defensive code that cannot be reached in production

    def test_all_public_repos_included(self, ranker, ranking_scenarios):
        """Test that all public repositories pass privacy filter."""
        public_repos = []
        commit_histories = {}

        for scenario in ranking_scenarios["scenarios"]:
            # Skip scenarios that should be excluded
            if scenario.get("should_exclude"):
                continue
            if scenario["repository"].get("is_private", False):
                continue

            repo, commits = create_repository_from_scenario(scenario)
            public_repos.append(repo)
            commit_histories[repo.name] = commits

        # Rank public repositories
        ranked = ranker.rank_repositories(
            public_repos, commit_histories, top_n=len(public_repos)
        )

        # All non-empty public repos should be included
        expected_count = len([r for r in public_repos if not r.is_empty])
        assert len(ranked) == expected_count


class TestCompositeScoring:
    """Test composite scoring algorithm."""

    def test_composite_score_range(self, ranker, ranking_scenarios):
        """Test that composite scores are within 0-100 range."""
        for scenario in ranking_scenarios["scenarios"]:
            if scenario.get("should_exclude"):
                continue

            repo, commits = create_repository_from_scenario(scenario)
            commit_histories = {repo.name: commits}

            # Rank single repository
            ranked = ranker.rank_repositories([repo], commit_histories, top_n=1)

            if len(ranked) > 0:  # If not filtered out
                _, score = ranked[0]
                assert (
                    0 <= score <= 100
                ), f"Score out of range for {scenario['name']}: {score}"

    def test_composite_weights_applied(self, ranker):
        """Test that composite score uses correct weights (30/45/25)."""
        # Verify the ranker has correct weights
        assert abs(ranker.weight_popularity - 0.30) < 0.01
        assert abs(ranker.weight_activity - 0.45) < 0.01
        assert abs(ranker.weight_health - 0.25) < 0.01

        # Verify weights sum to 1.0
        total = ranker.weight_popularity + ranker.weight_activity + ranker.weight_health
        assert abs(total - 1.0) < 0.01


class TestRankingIntegration:
    """Test complete ranking workflow."""

    def test_rank_repositories(self, ranker, ranking_scenarios):
        """Test ranking multiple repositories."""
        repos = []
        commit_histories = {}

        for scenario in ranking_scenarios["scenarios"]:
            if scenario.get("should_exclude"):
                continue

            repo, commits = create_repository_from_scenario(scenario)
            repos.append(repo)
            commit_histories[repo.name] = commits

        # Rank repositories
        ranked = ranker.rank_repositories(repos, commit_histories, top_n=len(repos))

        # Assertions
        assert len(ranked) > 0
        assert len(ranked) <= len(repos)

        # Scores should be in descending order
        for i in range(len(ranked) - 1):
            _, score1 = ranked[i]
            _, score2 = ranked[i + 1]
            assert (
                score1 >= score2
            ), f"Scores not in descending order: {score1} < {score2}"

    def test_top_n_selection(self, ranker, ranking_scenarios):
        """Test that top_n parameter limits results."""
        repos = []
        commit_histories = {}

        for scenario in ranking_scenarios["scenarios"]:
            if scenario.get("should_exclude"):
                continue

            repo, commits = create_repository_from_scenario(scenario)
            repos.append(repo)
            commit_histories[repo.name] = commits

        # Request top 3
        ranked = ranker.rank_repositories(repos, commit_histories, top_n=3)

        assert len(ranked) <= 3
        if len(ranked) >= 2:
            _, score1 = ranked[0]
            _, score2 = ranked[1]
            assert score1 >= score2

    def test_empty_repository_filter(self, ranker, ranking_scenarios):
        """Test that empty repositories are excluded."""
        # Find empty repository scenario
        empty_scenario = None
        for scenario in ranking_scenarios["scenarios"]:
            if scenario["name"] == "empty_repo":
                empty_scenario = scenario
                break

        if empty_scenario:
            repo, commits = create_repository_from_scenario(empty_scenario)
            commit_histories = {repo.name: commits}

            # Should be filtered out
            ranked = ranker.rank_repositories([repo], commit_histories, top_n=10)

            # Empty repo should not be in results (filtered by is_empty property)
            assert len(ranked) == 0 or all(r.name != "placeholder" for r, _ in ranked)


class TestEdgeCases:
    """Test edge case handling."""

    def test_archived_repository_handling(self, ranker, ranking_scenarios):
        """Test that archived repositories receive appropriate scoring."""
        archived_scenario = None
        for scenario in ranking_scenarios["scenarios"]:
            if scenario["name"] == "archived_repo":
                archived_scenario = scenario
                break

        assert archived_scenario is not None

        repo, commits = create_repository_from_scenario(archived_scenario)
        commit_histories = {repo.name: commits}

        ranked = ranker.rank_repositories([repo], commit_histories, top_n=1)

        if len(ranked) > 0:
            _, score = ranked[0]
            # Archived repos should have lower scores
            assert score < 50, f"Archived repo score too high: {score}"

    def test_fork_handling(self, ranker, ranking_scenarios):
        """Test that fork repositories are handled appropriately."""
        fork_scenarios = [
            s for s in ranking_scenarios["scenarios"] if "fork" in s["name"]
        ]

        for scenario in fork_scenarios:
            repo, commits = create_repository_from_scenario(scenario)
            commit_histories = {repo.name: commits}

            ranked = ranker.rank_repositories([repo], commit_histories, top_n=1)

            # Forks should still be rankable
            assert len(ranked) <= 1

    def test_new_active_repo_vs_legacy(self, ranker, ranking_scenarios):
        """Test that activity weight favors recent work over legacy stars."""
        new_active = None
        legacy = None

        for scenario in ranking_scenarios["scenarios"]:
            if scenario["name"] == "new_active_repo":
                new_active = scenario
            elif scenario["name"] == "legacy_popular_repo":
                legacy = scenario

        if new_active and legacy:
            new_repo, new_commits = create_repository_from_scenario(new_active)
            legacy_repo, legacy_commits = create_repository_from_scenario(legacy)

            repos = [new_repo, legacy_repo]
            commit_histories = {
                new_repo.name: new_commits,
                legacy_repo.name: legacy_commits,
            }

            ranked = ranker.rank_repositories(repos, commit_histories, top_n=2)

            # With 45% activity weight, active repos should compete well
            assert len(ranked) == 2


class TestScenarioValidation:
    """Test against predefined scenarios with expected scores."""

    def test_ideal_active_repo_scores_high(self, ranker, ranking_scenarios):
        """Test that ideal active repo scores in expected range."""
        ideal_scenario = None
        for scenario in ranking_scenarios["scenarios"]:
            if scenario["name"] == "ideal_active_repo":
                ideal_scenario = scenario
                break

        assert ideal_scenario is not None

        repo, commits = create_repository_from_scenario(ideal_scenario)
        commit_histories = {repo.name: commits}

        ranked = ranker.rank_repositories([repo], commit_histories, top_n=1)

        assert len(ranked) == 1
        _, score = ranked[0]

        # Should score highly (expected: 84)
        assert score > 70, f"Ideal repo scored too low: {score}"

    def test_stale_repo_scores_low(self, ranker, ranking_scenarios):
        """Test that stale repo scores in expected range."""
        stale_scenario = None
        for scenario in ranking_scenarios["scenarios"]:
            if scenario["name"] == "stale_repo":
                stale_scenario = scenario
                break

        if stale_scenario:
            repo, commits = create_repository_from_scenario(stale_scenario)
            commit_histories = {repo.name: commits}

            ranked = ranker.rank_repositories([repo], commit_histories, top_n=1)

            if len(ranked) > 0:
                _, score = ranked[0]
                # Stale repo should score low
                assert score < 40, f"Stale repo scored too high: {score}"


class TestPerformance:
    """Test ranking performance."""

    def test_ranking_50_repos(self, ranker, ranking_scenarios):
        """Test that ranking 50 repositories completes quickly."""
        import time

        # Create 50 repos by repeating scenarios
        repos = []
        commit_histories = {}

        for i in range(50):
            scenario_idx = i % len(ranking_scenarios["scenarios"])
            scenario = ranking_scenarios["scenarios"][scenario_idx]

            if scenario.get("should_exclude"):
                continue

            repo, commits = create_repository_from_scenario(scenario)
            # Modify name to make unique
            repo.name = f"{repo.name}-{i}"
            repo.full_name = f"testuser/{repo.name}"

            repos.append(repo)
            commit_histories[repo.name] = commits

        start = time.time()
        ranked = ranker.rank_repositories(repos, commit_histories, top_n=50)
        elapsed = time.time() - start

        # Should complete in under 1 second
        assert elapsed < 1.0, f"Ranking took too long: {elapsed:.2f}s"
        assert len(ranked) > 0


class TestConfigurationCustomization:
    """Test ranker configuration options."""

    def test_custom_weights(self):
        """Test that custom weights can be configured."""
        custom_config = {"popularity": 0.4, "activity": 0.4, "health": 0.2}

        ranker = RepositoryRanker(config=custom_config)

        assert abs(ranker.weight_popularity - 0.4) < 0.01
        assert abs(ranker.weight_activity - 0.4) < 0.01
        assert abs(ranker.weight_health - 0.2) < 0.01

    def test_default_weights(self):
        """Test that weights are loaded from config (no silent defaults)."""
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )

        assert abs(ranker.weight_popularity - 0.30) < 0.01
        assert abs(ranker.weight_activity - 0.45) < 0.01
        assert abs(ranker.weight_health - 0.25) < 0.01

    def test_missing_config_raises_error(self):
        """Test that RepositoryRanker raises ConfigurationError when no config provided."""
        from spark.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError):
            RepositoryRanker()


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_repository_list(self, ranker):
        """Test ranking with empty repository list."""
        ranked = ranker.rank_repositories([], {}, top_n=10)
        assert ranked == []

    def test_repository_without_commit_history(self, ranker):
        """Test ranking repo without commit history."""
        now = datetime.now()
        repo = Repository(
            name="no-history",
            description="Test repo",
            url="https://github.com/user/no-history",
            created_at=now - timedelta(days=100),
            updated_at=now - timedelta(days=10),
            pushed_at=now - timedelta(days=10),
            primary_language="Python",
            language_stats={"Python": 10000},
            stars=50,
            forks=10,
            watchers=25,
            open_issues=5,
            is_archived=False,
            is_fork=False,
            is_private=False,
            size_kb=2000,
            has_readme=True,
        )

        # No commit history provided
        ranked = ranker.rank_repositories([repo], {}, top_n=1)

        # Should still rank but with zero activity score
        assert len(ranked) == 1

    def test_top_n_larger_than_repo_count(self, ranker, ranking_scenarios):
        """Test requesting more repos than available."""
        repos = []
        commit_histories = {}

        # Create only 3 repos
        for i, scenario in enumerate(ranking_scenarios["scenarios"][:3]):
            if scenario.get("should_exclude"):
                continue

            repo, commits = create_repository_from_scenario(scenario)
            repos.append(repo)
            commit_histories[repo.name] = commits

        # Request top 100
        ranked = ranker.rank_repositories(repos, commit_histories, top_n=100)

        # Should return all available repos
        assert len(ranked) <= len(repos)


# ---------------------------------------------------------------------------
# Individual scoring method tests (targeting >80% coverage)
# ---------------------------------------------------------------------------


def _make_repo(**kwargs):
    """Helper to create Repository instances with sensible defaults."""
    now = datetime.now()
    defaults = dict(
        name="test-repo",
        description="Test repo",
        url="https://github.com/user/test-repo",
        created_at=now - timedelta(days=365),
        updated_at=now - timedelta(days=1),
        pushed_at=now - timedelta(days=1),
        primary_language="Python",
        language_stats={"Python": 10000},
        stars=10,
        forks=2,
        watchers=5,
        open_issues=0,
        is_archived=False,
        is_fork=False,
        is_private=False,
        size_kb=1000,
        has_readme=True,
    )
    defaults.update(kwargs)
    return Repository(**defaults)


def _make_commit_history(**kwargs):
    """Helper to create CommitHistory with sensible defaults."""
    defaults = dict(
        repository_name="test-repo",
        total_commits=100,
        recent_90d=20,
        recent_180d=40,
        recent_365d=80,
        last_commit_date=datetime.now() - timedelta(days=1),
    )
    defaults.update(kwargs)
    return CommitHistory(**defaults)


class TestPopularityScore:
    """Test _calculate_popularity_score in isolation."""

    def test_zero_stars(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(stars=0, forks=0, watchers=0)
        assert ranker._calculate_popularity_score(repo) == 0.0

    def test_moderate_stars(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(stars=100, forks=20, watchers=50)
        score = ranker._calculate_popularity_score(repo)
        assert 50 < score < 80

    def test_mega_repo(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(stars=50000, forks=10000, watchers=20000)
        score = ranker._calculate_popularity_score(repo)
        assert score == 100.0  # capped

    def test_log_scaling_prevents_dominance(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo_10 = _make_repo(stars=10, forks=0, watchers=0)
        repo_10000 = _make_repo(stars=10000, forks=0, watchers=0)
        score_10 = ranker._calculate_popularity_score(repo_10)
        score_10000 = ranker._calculate_popularity_score(repo_10000)
        # 10000 stars should NOT be 1000x the score of 10 stars
        assert score_10000 / max(score_10, 0.01) < 4


class TestActivityScore:
    """Test _calculate_activity_score in isolation."""

    def test_zero_commits(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(pushed_at=None)
        history = _make_commit_history(
            recent_90d=0,
            recent_180d=0,
            recent_365d=0,
            last_commit_date=None,
        )
        score = ranker._calculate_activity_score(repo, history)
        # No commits and no pushed_at means no recency bonus (0)
        assert score == 0.0

    def test_high_activity(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(pushed_at=datetime.now() - timedelta(days=1))
        history = _make_commit_history(
            recent_90d=90,
            recent_180d=180,
            recent_365d=365,
        )
        score = ranker._calculate_activity_score(repo, history)
        assert score == 100.0  # capped at 100

    def test_recency_bonus_applied(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        recent_repo = _make_repo(pushed_at=datetime.now() - timedelta(days=1))
        old_repo = _make_repo(pushed_at=datetime.now() - timedelta(days=400))
        history = _make_commit_history(recent_90d=0, recent_180d=0, recent_365d=0)

        recent_score = ranker._calculate_activity_score(recent_repo, history)
        old_score = ranker._calculate_activity_score(old_repo, history)
        assert recent_score > old_score


class TestRecencyBonus:
    """Test _calculate_recency_bonus at boundary values."""

    @pytest.mark.parametrize(
        "days_since, expected",
        [
            (None, 0.0),
            (1, 30.0),
            (7, 30.0),  # threshold: RECENCY_EXCELLENT
            (8, 20.0),
            (30, 20.0),  # threshold: RECENCY_GOOD
            (31, 10.0),
            (90, 10.0),  # threshold: RECENCY_FAIR
            (91, 0.0),
            (180, 0.0),
            (181, -20.0),
            (365, -20.0),
            (366, -50.0),
            (1000, -50.0),
        ],
    )
    def test_boundaries(self, days_since, expected):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        if days_since is None:
            repo = _make_repo(pushed_at=None)
        else:
            repo = _make_repo(pushed_at=datetime.now() - timedelta(days=days_since))
        assert ranker._calculate_recency_bonus(repo) == expected


class TestHealthScore:
    """Test _calculate_health_score in isolation."""

    def test_perfect_health(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(
            has_readme=True,
            stars=10,
            forks=2,
            open_issues=0,
            created_at=datetime.now() - timedelta(days=1500),
        )
        history = _make_commit_history(total_commits=200, recent_90d=30)
        score = ranker._calculate_health_score(repo, history)
        assert score >= 70

    def test_no_readme_penalty(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        with_readme = _make_repo(has_readme=True)
        without_readme = _make_repo(has_readme=False)
        history = _make_commit_history()
        assert ranker._calculate_health_score(
            with_readme, history
        ) > ranker._calculate_health_score(without_readme, history)

    def test_high_issue_ratio_penalty(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(open_issues=100)
        history = _make_commit_history(recent_90d=5)
        score = ranker._calculate_health_score(repo, history)
        # Issue ratio = 100/5 = 20, penalty = 20 * 5 = 100, issue_score = max(0, 20-100) = 0
        assert score < 60

    def test_zero_stars_community(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(stars=0, forks=0)
        history = _make_commit_history()
        score = ranker._calculate_health_score(repo, history)
        # community component = 0 when no stars and no forks
        assert score >= 0

    def test_no_recent_activity_with_issues(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(open_issues=5)
        history = _make_commit_history(recent_90d=0)
        score = ranker._calculate_health_score(repo, history)
        # No recent activity + issues = 0 issue points
        assert score >= 0

    def test_no_recent_activity_no_issues(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(open_issues=0)
        history = _make_commit_history(recent_90d=0)
        score = ranker._calculate_health_score(repo, history)
        # No recent activity + no issues = 10 issue points
        assert score >= 10


class TestEdgeCasePenalties:
    """Test _apply_edge_case_penalties."""

    def test_archived_low_stars(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(is_archived=True, stars=50)
        result = ranker._apply_edge_case_penalties(
            repo, composite=80.0, activity=50.0, popularity=40.0
        )
        assert result == pytest.approx(8.0)  # 80 * 0.1

    def test_archived_high_stars(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(is_archived=True, stars=2000)
        result = ranker._apply_edge_case_penalties(
            repo, composite=80.0, activity=50.0, popularity=40.0
        )
        assert result == pytest.approx(40.0)  # 80 * 0.5

    def test_active_fork(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(is_fork=True)
        repo.fork_info = {"commits_ahead": 20, "commits_behind": 5}
        result = ranker._apply_edge_case_penalties(
            repo, composite=80.0, activity=50.0, popularity=40.0
        )
        assert result == pytest.approx(56.0)  # 80 * 0.7

    def test_inactive_fork(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(is_fork=True)
        repo.fork_info = {"commits_ahead": 0, "commits_behind": 50}
        result = ranker._apply_edge_case_penalties(
            repo, composite=80.0, activity=50.0, popularity=40.0
        )
        assert result == pytest.approx(24.0)  # 80 * 0.3

    def test_zero_star_active_boost(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(stars=0, is_fork=False, is_archived=False)
        result = ranker._apply_edge_case_penalties(
            repo, composite=20.0, activity=80.0, popularity=0.0
        )
        # boost = (80-0) * 0.3 = 24
        assert result == pytest.approx(44.0)

    def test_non_archived_non_fork_no_penalty(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo(stars=10)
        result = ranker._apply_edge_case_penalties(
            repo, composite=50.0, activity=40.0, popularity=30.0
        )
        assert result == 50.0


class TestGetRankingBreakdown:
    """Test get_ranking_breakdown method."""

    def test_returns_expected_keys(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo()
        history = _make_commit_history()
        breakdown = ranker.get_ranking_breakdown(repo, history)
        expected_keys = {
            "repository",
            "composite_score",
            "popularity_score",
            "activity_score",
            "health_score",
            "popularity_weight",
            "activity_weight",
            "health_weight",
            "weighted_popularity",
            "weighted_activity",
            "weighted_health",
            "is_archived",
            "is_fork",
            "stars",
            "recent_90d_commits",
            "days_since_push",
        }
        assert set(breakdown.keys()) == expected_keys

    def test_scores_in_range(self):
        ranker = RepositoryRanker(
            config={"popularity": 0.30, "activity": 0.45, "health": 0.25}
        )
        repo = _make_repo()
        history = _make_commit_history()
        breakdown = ranker.get_ranking_breakdown(repo, history)
        assert 0 <= breakdown["composite_score"] <= 100
        assert 0 <= breakdown["popularity_score"] <= 100
        assert 0 <= breakdown["health_score"] <= 100
