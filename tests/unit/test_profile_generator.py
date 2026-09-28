"""Unit tests for user profile generation."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from spark.summarizer import UserProfileGenerator, RepositorySummarizer
from spark.models.repository import Repository
from spark.models.commit import CommitHistory
from spark.models.tech_stack import TechnologyStack


class TestUserProfileGenerator:
    """Test cases for UserProfileGenerator."""

    @pytest.fixture
    def mock_summarizer(self):
        """Create mock summarizer."""
        summarizer = Mock(spec=RepositorySummarizer)
        summarizer.anthropic = None  # Default to no AI
        return summarizer

    @pytest.fixture
    def generator(self, mock_summarizer):
        """Create profile generator instance."""
        return UserProfileGenerator(mock_summarizer)

    @pytest.fixture
    def sample_repositories(self):
        """Create sample repositories."""
        return [
            Repository(
                name="repo1",
                description="Python project",
                url="https://github.com/user/repo1",
                created_at=datetime(2023, 1, 1),
                updated_at=datetime(2024, 12, 1),
                pushed_at=datetime(2024, 12, 1),
                primary_language="Python",
                language_stats={"Python": 100000, "JavaScript": 5000},
                stars=50,
                forks=10,
                is_archived=False,
                is_fork=False,
            ),
            Repository(
                name="repo2",
                description="JavaScript project",
                url="https://github.com/user/repo2",
                created_at=datetime(2023, 6, 1),
                updated_at=datetime(2024, 11, 1),
                pushed_at=datetime(2024, 11, 1),
                primary_language="JavaScript",
                language_stats={"JavaScript": 80000, "CSS": 2000},
                stars=30,
                forks=5,
                is_archived=False,
                is_fork=False,
            ),
            Repository(
                name="repo3",
                description="Python project",
                url="https://github.com/user/repo3",
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 12, 15),
                pushed_at=datetime(2024, 12, 15),
                primary_language="Python",
                language_stats={"Python": 150000, "Shell": 1000},
                stars=100,
                forks=20,
                is_archived=False,
                is_fork=False,
            ),
        ]

    @pytest.fixture
    def sample_commit_histories(self):
        """Create sample commit histories."""
        return {
            "repo1": CommitHistory(
                repository_name="repo1",
                total_commits=100,
                recent_90d=20,
                recent_180d=40,
                recent_365d=80,
                last_commit_date=datetime(2024, 12, 1),
                patterns=["consistent"],
                commit_frequency=15.5,
            ),
            "repo2": CommitHistory(
                repository_name="repo2",
                total_commits=50,
                recent_90d=5,
                recent_180d=10,
                recent_365d=30,
                last_commit_date=datetime(2024, 11, 1),
                patterns=["consistent"],
                commit_frequency=8.2,
            ),
            "repo3": CommitHistory(
                repository_name="repo3",
                total_commits=200,
                recent_90d=60,
                recent_180d=120,
                recent_365d=200,
                last_commit_date=datetime(2024, 12, 15),
                patterns=["consistent", "frequent"],
                commit_frequency=25.3,
            ),
        }

    @pytest.fixture
    def sample_tech_stacks(self):
        """Create sample tech stacks."""
        return {
            "repo1": TechnologyStack(
                repository_name="repo1",
                languages={"Python": 100000, "JavaScript": 5000},
                frameworks=["Django", "React"],
            ),
            "repo2": TechnologyStack(
                repository_name="repo2",
                languages={"JavaScript": 80000, "CSS": 2000},
                frameworks=["React", "Node.js"],
            ),
            "repo3": TechnologyStack(
                repository_name="repo3",
                languages={"Python": 150000, "Shell": 1000},
                frameworks=["Flask"],
            ),
        }

    def test_generate_profile_basic(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test basic profile generation."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        assert profile.username == "testuser"
        assert profile.total_repos == 3
        assert profile.active_repos == 3  # All have recent_90d > 0
        assert len(profile.primary_languages) >= 2
        assert profile.tech_diversity > 0

    def test_technology_diversity_calculation(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test technology diversity calculation."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should aggregate languages across all repos
        assert "Python" in profile.primary_languages
        assert "JavaScript" in profile.primary_languages
        assert profile.primary_languages["Python"] == 250000  # 100k + 150k
        assert profile.primary_languages["JavaScript"] == 85000  # 5k + 80k

    def test_framework_aggregation(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test framework usage aggregation."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        assert "React" in profile.framework_usage
        assert profile.framework_usage["React"] == 2  # Used in 2 repos
        assert profile.framework_usage["Django"] == 1
        assert profile.framework_usage["Flask"] == 1

    def test_activity_pattern_detection_technology_focus(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test technology focus pattern detection."""
        # Modify repos to have strong Python focus
        for repo in sample_repositories:
            repo.language_stats = {"Python": 100000}

        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should detect Python focus
        focus_patterns = [
            p for p in profile.activity_patterns if p.pattern_type == "technology_focus"
        ]
        assert len(focus_patterns) > 0
        assert "Python" in focus_patterns[0].description

    def test_activity_pattern_detection_consistency(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test commit consistency pattern detection."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should detect consistent patterns (all 3 repos have "consistent")
        consistency_patterns = [
            p
            for p in profile.activity_patterns
            if p.pattern_type == "commit_consistency"
        ]
        assert len(consistency_patterns) > 0
        assert "3 repositories" in consistency_patterns[0].description

    def test_template_impression_generation(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test template-based impression generation."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should have template impression (no AI)
        assert profile.overall_impression is not None
        assert len(profile.overall_impression) > 0
        assert "testuser" in profile.overall_impression

    def test_contribution_classification(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test contribution classification."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should classify based on activity
        assert profile.contribution_classification in [
            "active_maintainer",
            "specialist",
            "polyglot",
            "hobbyist",
            "experimenter",
            "developer",
        ]

    def test_no_active_repositories(
        self, generator, sample_repositories, sample_tech_stacks
    ):
        """Test profile with no active repositories."""
        # Create commit histories with no recent activity
        inactive_histories = {
            repo.name: CommitHistory(
                repository_name=repo.name,
                total_commits=100,
                recent_90d=0,
                recent_180d=0,
                recent_365d=10,
                last_commit_date=datetime(2023, 1, 1),
                patterns=[],
                commit_frequency=0.0,
            )
            for repo in sample_repositories
        }

        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=inactive_histories,
            tech_stacks=sample_tech_stacks,
        )

        assert profile.active_repos == 0
        assert profile.commit_frequency >= 0

    @patch("spark.summarizer.RepositorySummarizer")
    def test_ai_impression_generation(
        self,
        mock_summarizer_class,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test AI-powered impression generation."""
        # Create mock with AI enabled
        mock_summarizer = MagicMock()
        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This developer is highly skilled.")]
        mock_anthropic.messages.create.return_value = mock_response

        mock_summarizer.anthropic = mock_anthropic
        mock_summarizer.model = "claude-haiku-4-5"

        generator = UserProfileGenerator(mock_summarizer)
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should use AI impression
        assert profile.overall_impression == "This developer is highly skilled."
        assert mock_anthropic.messages.create.called

    def test_top_languages_property(
        self,
        generator,
        sample_repositories,
        sample_commit_histories,
        sample_tech_stacks,
    ):
        """Test top languages property."""
        profile = generator.generate_profile(
            username="testuser",
            repositories=sample_repositories,
            commit_histories=sample_commit_histories,
            tech_stacks=sample_tech_stacks,
        )

        # Should have Python as top language
        assert len(profile.top_languages) > 0
        assert profile.top_languages[0] == "Python"
