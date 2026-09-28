"""Unit tests for StatsCalculator."""

from datetime import datetime, timedelta
from spark.calculator import StatsCalculator


class TestSparkScore:
    """Test Spark Score calculation."""

    def test_calculate_spark_score_with_data(self):
        """Test Spark Score calculation with sample data."""
        profile = {
            "username": "testuser",
            "public_repos": 10,
            "followers": 50,
        }

        repositories = [
            {"name": "repo1", "stars": 100, "forks": 20, "watchers": 30},
            {"name": "repo2", "stars": 50, "forks": 10, "watchers": 15},
        ]

        calculator = StatsCalculator(
            profile,
            repositories,
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add some commits
        commits = [
            {
                "sha": "abc123",
                "date": datetime.now().isoformat(),
                "message": "Test commit",
            }
            for _ in range(100)
        ]
        calculator.add_commits(commits)

        spark_score = calculator.calculate_spark_score()

        assert "total_score" in spark_score
        assert "consistency_score" in spark_score
        assert "volume_score" in spark_score
        assert "collaboration_score" in spark_score
        assert "lightning_rating" in spark_score

        assert 0 <= spark_score["total_score"] <= 100
        assert 1 <= spark_score["lightning_rating"] <= 5

    def test_calculate_spark_score_no_data(self):
        """Test Spark Score calculation with no data."""
        profile = {"username": "testuser", "public_repos": 0, "followers": 0}
        repositories = []

        calculator = StatsCalculator(
            profile,
            repositories,
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )
        spark_score = calculator.calculate_spark_score()

        assert spark_score["total_score"] >= 0
        assert spark_score["lightning_rating"] >= 1


class TestLightningRating:
    """Test lightning rating mapping."""

    def test_lightning_rating_levels(self):
        """Test all lightning rating thresholds."""
        calculator = StatsCalculator(
            {},
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        assert calculator.calculate_lightning_rating(90) == 5
        assert calculator.calculate_lightning_rating(70) == 4
        assert calculator.calculate_lightning_rating(50) == 3
        assert calculator.calculate_lightning_rating(30) == 2
        assert calculator.calculate_lightning_rating(10) == 1


class TestStatisticsAggregation:
    """Test aggregate statistics across supported commit payload shapes."""

    def test_calculate_statistics_accepts_commit_stats_shape(self):
        """Ensure heatmap and time analysis work with nested commit dates."""
        calculator = StatsCalculator(
            {},
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )
        calculator.add_commits(
            [
                {
                    "sha": "a",
                    "repo": "repo-a",
                    "commit": {"author": {"date": "2025-02-03T23:00:00+00:00"}},
                    "stats": {"total": 1, "additions": 1, "deletions": 0},
                },
                {
                    "sha": "b",
                    "repo": "repo-a",
                    "commit": {"author": {"date": "2025-02-03T10:00:00+00:00"}},
                    "stats": {"total": 1, "additions": 1, "deletions": 0},
                },
                {
                    "sha": "c",
                    "repo": "repo-b",
                    "commit": {"author": {"date": "2025-02-04T23:30:00+00:00"}},
                    "stats": {"total": 1, "additions": 1, "deletions": 0},
                },
            ]
        )

        stats = calculator.calculate_statistics()

        assert stats["commits_by_day"] == {
            "2025-02-03": 2,
            "2025-02-04": 1,
        }
        assert stats["time_pattern"]["most_active_hour"] == 23
        assert stats["streaks"]["longest_streak"] == 2
        assert stats["fun_stats"]["total_commits"] == 3
        assert stats["fun_stats"]["total_repos"] == 0

    def test_calculate_statistics_populates_fun_stats(self):
        """Ensure Lightning Round stats are derived from repo and commit inputs."""
        calculator = StatsCalculator(
            {"username": "testuser", "created_at": "2024-01-01T00:00:00+00:00"},
            [
                {
                    "name": "repo-a",
                    "stars": 5,
                    "created_at": "2024-01-10T00:00:00+00:00",
                },
                {
                    "name": "repo-b",
                    "stars": 7,
                    "created_at": "2024-02-01T00:00:00+00:00",
                },
            ],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )
        calculator.add_languages({"Python": 1000, "JavaScript": 500})
        calculator.add_commits(
            [
                {"sha": "a", "date": "2025-02-03T23:00:00+00:00", "repo": "repo-a"},
                {"sha": "b", "date": "2025-02-04T23:30:00+00:00", "repo": "repo-b"},
            ]
        )

        stats = calculator.calculate_statistics()
        fun_stats = stats["fun_stats"]

        assert fun_stats["most_active_hour"] == 23
        assert fun_stats["pattern"] == "night_owl"
        assert fun_stats["total_repos"] == 2
        assert fun_stats["languages_count"] == 2
        assert fun_stats["total_stars"] == 12
        assert fun_stats["total_commits"] == 2
        assert fun_stats["account_age_days"] > 0
        assert fun_stats["avg_commits_per_day"] > 0


class TestTimePatterns:
    """Test time pattern analysis."""

    def test_night_owl_detection(self):
        """Test night owl pattern detection."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add commits during night hours (22:00-4:00)
        night_commits = []
        base_time = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)

        for i in range(50):
            commit_time = base_time - timedelta(days=i)
            night_commits.append(
                {
                    "sha": f"commit{i}",
                    "date": commit_time.isoformat(),
                    "message": "Night commit",
                }
            )

        calculator.add_commits(night_commits)
        patterns = calculator.analyze_time_patterns()

        assert patterns["category"] == "night_owl"
        assert "hour_distribution" in patterns

    def test_early_bird_detection(self):
        """Test early bird pattern detection."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add commits during morning hours (6:00-9:00)
        morning_commits = []
        base_time = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)

        for i in range(50):
            commit_time = base_time - timedelta(days=i)
            morning_commits.append(
                {
                    "sha": f"commit{i}",
                    "date": commit_time.isoformat(),
                    "message": "Morning commit",
                }
            )

        calculator.add_commits(morning_commits)
        patterns = calculator.analyze_time_patterns()

        assert patterns["category"] == "early_bird"

    def test_balanced_pattern(self):
        """Test balanced coding pattern."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add commits throughout the day
        commits = []
        base_time = datetime.now()

        for hour in range(8, 18):  # 8 AM to 6 PM
            for day in range(5):
                commit_time = base_time.replace(hour=hour, minute=0) - timedelta(
                    days=day
                )
                commits.append(
                    {
                        "sha": f"commit{hour}{day}",
                        "date": commit_time.isoformat(),
                        "message": "Day commit",
                    }
                )

        calculator.add_commits(commits)
        patterns = calculator.analyze_time_patterns()

        assert patterns["category"] == "balanced"


class TestStreaks:
    """Test coding streak calculation."""

    def test_consecutive_streak(self):
        """Test calculation of consecutive coding streak."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add commits for consecutive 10 days
        commits = []
        base_time = datetime.now()

        for i in range(10):
            commit_time = base_time - timedelta(days=i)
            commits.append(
                {
                    "sha": f"commit{i}",
                    "date": commit_time.isoformat(),
                    "message": f"Day {i} commit",
                }
            )

        calculator.add_commits(commits)
        streaks = calculator.calculate_streaks()

        assert streaks["longest_streak"] >= 10

    def test_no_streak(self):
        """Test streak calculation with no commits."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        streaks = calculator.calculate_streaks()

        assert streaks["current_streak"] == 0
        assert streaks["longest_streak"] == 0

    def test_learning_streak_tracks_new_languages(self):
        """Learning streak should reflect consecutive days introducing new languages."""
        profile = {"username": "testuser"}
        repositories = [
            {"name": "repo-py", "language": "Python"},
            {"name": "repo-js", "language": "JavaScript"},
            {"name": "repo-go", "language": "Go"},
        ]
        calculator = StatsCalculator(
            profile,
            repositories,
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        now = datetime.now()
        commits = [
            {
                "sha": "a",
                "date": (now - timedelta(days=2)).isoformat(),
                "repo": "repo-py",
            },
            {
                "sha": "b",
                "date": (now - timedelta(days=1)).isoformat(),
                "repo": "repo-js",
            },
            {"sha": "c", "date": now.isoformat(), "repo": "repo-go"},
            # Existing language on same day should not create a new introduction.
            {"sha": "d", "date": now.isoformat(), "repo": "repo-go"},
        ]
        calculator.add_commits(commits)

        streaks = calculator.calculate_streaks()

        assert streaks["longest_learning_streak"] >= 3
        assert streaks["current_learning_streak"] >= 3


class TestLanguages:
    """Test language aggregation."""

    def test_aggregate_languages(self):
        """Test language percentage calculation."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add language data
        calculator.add_languages({"Python": 1000, "JavaScript": 500, "HTML": 300})

        languages = calculator.aggregate_languages()

        assert len(languages) == 3
        assert languages[0]["name"] == "Python"
        assert languages[0]["percentage"] > languages[1]["percentage"]

        # Check percentages sum to ~100
        total_percentage = sum(lang["percentage"] for lang in languages)
        assert 99.9 <= round(total_percentage, 1) <= 100.1

    def test_aggregate_languages_grouping(self):
        """Test 'Other' grouping for many languages."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        # Add 15 languages
        languages_data = {f"Lang{i}": 100 - i * 5 for i in range(15)}
        calculator.add_languages(languages_data)

        languages = calculator.aggregate_languages()

        # Should group into top 9 + "Other"
        assert len(languages) <= 10
        if len(languages) == 10:
            assert languages[-1]["name"] == "Other"


class TestReleaseCadence:
    """Test release cadence calculations."""

    def test_release_cadence_counts_unique_repos(self):
        """Ensure weekly/monthly cadence counts unique repositories."""
        profile = {"username": "testuser"}
        calculator = StatsCalculator(
            profile,
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        base_week_start = datetime(2025, 2, 3)  # Monday anchor
        schedule = [
            (3, ["repo-z"]),
            (2, ["repo-z", "repo-y"]),
            (1, ["repo-y"]),
            (0, ["repo-x", "repo-y"]),
        ]

        commits = []
        for weeks_ago, repos in schedule:
            commit_day = base_week_start - timedelta(weeks=weeks_ago)
            for idx, repo in enumerate(repos):
                commits.append(
                    {
                        "sha": f"{repo}-{weeks_ago}-{idx}",
                        "date": commit_day.isoformat(),
                        "repo": repo,
                        "message": "test",
                    }
                )

        calculator.add_commits(commits)
        cadence = calculator.calculate_release_cadence(weeks=4, months=3)

        assert len(cadence["weekly"]) == 4
        assert cadence["weekly"][0]["repos"] == 1  # oldest week touches one repo
        assert cadence["weekly"][-1]["repos"] == 2  # current week touches two repos
        assert cadence["monthly"][-1]["repos"] == 2
        assert cadence["unique_repos"] == 3
        assert cadence["max_weekly"] >= cadence["weekly"][-1]["repos"]

    def test_release_cadence_without_repo_metadata_returns_empty_series(self):
        """Ensure cadence gracefully handles commits without repo identifiers."""
        calculator = StatsCalculator(
            {},
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )
        calculator.add_commits(
            [
                {
                    "sha": "abc",
                    "date": datetime.now().isoformat(),
                    "message": "missing repo",
                }
            ]
        )

        cadence = calculator.calculate_release_cadence(weeks=2, months=2)

        assert [point["repos"] for point in cadence["weekly"]] == [0, 0]
        assert [point["repos"] for point in cadence["monthly"]] == [0, 0]

    def test_release_cadence_accepts_commit_stats_shape(self):
        """Ensure cadence handles commits_stats cache payloads."""
        calculator = StatsCalculator(
            {},
            [],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )
        calculator.add_commits(
            [
                {
                    "sha": "abc",
                    "repo": "repo-a",
                    "commit": {
                        "author": {"date": "2025-02-03T00:00:00+00:00"},
                        "message": "test",
                    },
                    "stats": {"total": 1, "additions": 1, "deletions": 0},
                }
            ]
        )

        cadence = calculator.calculate_release_cadence(weeks=1, months=1)

        assert cadence["weekly"][0]["repos"] == 1
        assert cadence["monthly"][0]["repos"] == 1
        assert cadence["source"] == "commit_timeline"
        assert cadence["is_estimated"] is False

    def test_release_cadence_falls_back_to_repository_activity(self):
        """Ensure cadence uses repository last-activity snapshots when commits are unavailable."""
        calculator = StatsCalculator(
            {},
            [
                {
                    "name": "repo-a",
                    "commit_history": {
                        "last_commit_date": "2025-02-03T00:00:00+00:00",
                    },
                    "pushed_at": "2025-02-03T00:00:00+00:00",
                    "updated_at": "2025-02-03T00:00:00+00:00",
                },
                {
                    "name": "repo-b",
                    "last_commit_date": "2025-02-10T00:00:00+00:00",
                    "updated_at": "2025-02-10T00:00:00+00:00",
                },
            ],
            thresholds={
                "night_owl_hours": [22, 23, 0, 1, 2, 3, 4],
                "early_bird_hours": [5, 6, 7, 8, 9],
            },
        )

        cadence = calculator.calculate_release_cadence(weeks=2, months=1)

        assert [point["repos"] for point in cadence["weekly"]] == [1, 1]
        assert cadence["monthly"][0]["repos"] == 2
        assert cadence["unique_repos"] == 2
        assert cadence["source"] == "latest_repository_activity"
        assert cadence["is_estimated"] is True


class TestDashboardCommitMetrics:
    """Test repository-level commit metric helpers."""

    def test_calculate_repository_commit_metrics_tracks_distribution(self):
        commits = [
            {
                "sha": "small",
                "commit": {"author": {"date": "2026-03-01T00:00:00Z"}},
                "stats": {"total": 1, "additions": 2, "deletions": 0},
            },
            {
                "sha": "large",
                "commit": {"author": {"date": "2026-03-02T00:00:00Z"}},
                "stats": {"total": 4, "additions": 10, "deletions": 6},
            },
        ]

        metrics = StatsCalculator.calculate_repository_commit_metrics(commits)

        assert metrics["total_commits"] == 2
        assert metrics["largest_commit"]["sha"] == "large"
        assert metrics["smallest_commit"]["sha"] == "small"
        assert metrics["commit_size_distribution"]["max"] == 20
