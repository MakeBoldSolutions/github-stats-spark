"""Unit tests for markdown report generation."""

import pytest
from datetime import datetime
from spark.report_generator import ReportGenerator
from spark.models.report import Report, RepositoryAnalysis
from spark.models.repository import Repository
from spark.models.commit import CommitHistory
from spark.models.summary import RepositorySummary
from spark.models.profile import UserProfile, ActivityPattern
from spark.models.tech_stack import TechnologyStack, DependencyInfo


class TestReportGenerator:
    """Test cases for ReportGenerator."""

    @pytest.fixture
    def generator(self):
        """Create report generator instance."""
        return ReportGenerator()

    @pytest.fixture
    def sample_repository(self):
        """Create sample repository."""
        return Repository(
            name="test-repo",
            description="A test repository",
            url="https://github.com/user/test-repo",
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2024, 12, 1),
            pushed_at=datetime(2024, 12, 1),
            primary_language="Python",
            language_stats={"Python": 100000, "JavaScript": 5000},
            stars=100,
            forks=20,
            watchers=50,
            open_issues=5,
            is_archived=False,
            is_fork=False,
        )

    @pytest.fixture
    def sample_commit_history(self):
        """Create sample commit history."""
        return CommitHistory(
            repository_name="test-repo",
            total_commits=150,
            recent_90d=30,
            recent_180d=60,
            recent_365d=120,
            last_commit_date=datetime(2024, 12, 1),
            patterns=["consistent", "active"],
            commit_frequency=15.0,
        )

    @pytest.fixture
    def sample_summary(self):
        """Create sample summary."""
        return RepositorySummary(
            repo_id="test-repo",
            ai_summary="A comprehensive test repository with excellent documentation.",
            generation_method="ai",
            model_used="claude-haiku-4-5",
            tokens_used=150,
        )

    @pytest.fixture
    def sample_tech_stack(self):
        """Create sample technology stack."""
        deps = [
            DependencyInfo(
                name="requests",
                current_version="2.28.0",
                latest_version="2.31.0",
                ecosystem="pypi",
                versions_behind=0,
                is_outdated=False,
                status="current",
            ),
            DependencyInfo(
                name="flask",
                current_version="2.0.0",
                latest_version="3.0.0",
                ecosystem="pypi",
                versions_behind=1,
                is_outdated=True,
                status="outdated",
            ),
        ]

        tech_stack = TechnologyStack(
            repository_name="test-repo",
            languages={"Python": 100000, "JavaScript": 5000},
            frameworks=["Flask", "React"],
            dependencies=deps,
        )
        return tech_stack

    @pytest.fixture
    def sample_user_profile(self):
        """Create sample user profile."""
        profile = UserProfile(
            username="testuser",
            total_repos=10,
            active_repos=7,
            primary_languages={"Python": 500000, "JavaScript": 200000},
            framework_usage={"Flask": 3, "React": 2},
            commit_frequency=20.5,
        )

        profile.add_pattern(
            ActivityPattern(
                pattern_type="technology_focus",
                description="Strong focus on Python (71% of codebase)",
                evidence={"language": "Python", "percentage": 71.4},
                confidence=90,
            )
        )

        profile.overall_impression = (
            "testuser is an active maintainer with primary focus on Python."
        )
        return profile

    @pytest.fixture
    def sample_report(
        self,
        sample_repository,
        sample_commit_history,
        sample_summary,
        sample_tech_stack,
        sample_user_profile,
    ):
        """Create sample report."""
        analysis = RepositoryAnalysis(
            repository=sample_repository,
            rank=1,
            composite_score=85.5,
            commit_history=sample_commit_history,
            summary=sample_summary,
            tech_stack=sample_tech_stack,
        )

        return Report(
            username="testuser",
            generation_timestamp=datetime(2024, 12, 29, 10, 0, 0),
            repositories=[analysis],
            user_profile=sample_user_profile,
            generation_time_seconds=120.5,
            total_api_calls=25,
            total_ai_tokens=1500,
            errors=[],
        )

    def test_generate_header(self, generator, sample_report):
        """Test markdown header generation."""
        header = generator._generate_header(sample_report)

        assert "# GitHub Repository Analysis: testuser" in header
        assert "2024-12-29 10:00:00 UTC" in header
        assert "Repositories Analyzed**: 1" in header  # We have 1 repo in the sample
        assert "AI Summary Rate" in header

    def test_generate_profile_section(self, generator, sample_report):
        """Test user profile section generation."""
        section = generator._generate_profile_section(sample_report)

        assert "## Developer Profile" in section
        assert "testuser" in section
        assert "Total Public Repositories**: 10" in section
        assert "Active Repositories (90d)**: 7" in section
        assert "Primary Technologies" in section
        assert "Python" in section
        assert "Observable Patterns" in section
        assert "Overall Impression" in section

    def test_generate_repositories_section(self, generator, sample_report):
        """Test repositories listing section."""
        section = generator._generate_repositories_section(sample_report)

        assert "## Top 1 Repositories" in section
        assert "test-repo" in section

    def test_format_repository_entry(self, generator, sample_report):
        """Test single repository entry formatting."""
        analysis = sample_report.repositories[0]
        entry = generator._format_repository_entry(analysis)

        # Check title with rank
        assert "### #1. [test-repo]" in entry
        assert "https://github.com/user/test-repo" in entry

        # Check stats
        assert "Stars: 100" in entry
        assert "Forks: 20" in entry
        assert "Python" in entry
        assert "30 commits (90d)" in entry

        # Check summary
        assert "A comprehensive test repository" in entry

        # Check creation date
        assert "2023-01-01" in entry

    def test_format_tech_stack_with_outdated_deps(self, generator, sample_tech_stack):
        """Test technology stack formatting with outdated dependencies."""
        formatted = generator._format_tech_stack(sample_tech_stack)

        assert "Technology Stack Currency" in formatted
        assert "Dependencies" in formatted
        assert "2 total" in formatted
        assert "1 outdated" in formatted
        assert "Most Outdated" in formatted
        assert "flask" in formatted

    def test_get_currency_emoji(self, generator):
        """Test currency emoji selection."""
        assert generator._get_currency_emoji(95) == "✅"
        assert generator._get_currency_emoji(85) == "🟢"
        assert generator._get_currency_emoji(60) == "🟡"
        assert generator._get_currency_emoji(40) == "🔴"

    def test_generate_metadata_section(self, generator, sample_report):
        """Test metadata section generation."""
        section = generator._generate_metadata_section(sample_report)

        assert "## Report Metadata" in section
        assert "120.5 seconds" in section
        assert "Total API Calls**: 25" in section
        assert "Total AI Tokens**: 1500" in section
        assert "Success Rate**: 100.0%" in section
        assert "Stats Spark" in section

    def test_generate_errors_section(self, generator):
        """Test errors section generation."""
        report = Report(
            username="testuser",
            generation_timestamp=datetime.now(),
            repositories=[],
            user_profile=None,
            generation_time_seconds=60.0,
            total_api_calls=10,
            total_ai_tokens=500,
            errors=["API rate limit reached", "Failed to fetch repo: test"],
        )

        section = generator._generate_errors_section(report)

        assert "## ⚠️ Errors Encountered" in section
        assert "API rate limit reached" in section
        assert "Failed to fetch repo: test" in section

    def test_build_markdown_complete(self, generator, sample_report):
        """Test complete markdown document building."""
        markdown = generator._build_markdown(sample_report)

        # Verify all sections present
        assert "# GitHub Repository Analysis" in markdown
        assert "## Developer Profile" in markdown
        assert "## Top 1 Repositories" in markdown
        assert "## Report Metadata" in markdown

        # Verify proper spacing
        assert "\n\n" in markdown

    def test_build_markdown_without_profile(self, generator, sample_report):
        """Test markdown generation without user profile."""
        sample_report.user_profile = None
        markdown = generator._build_markdown(sample_report)

        # Should not have profile section
        assert "## Developer Profile" not in markdown

        # But should have other sections
        assert "# GitHub Repository Analysis" in markdown
        assert "## Top 1 Repositories" in markdown

    def test_build_markdown_with_errors(self, generator, sample_report):
        """Test markdown generation with errors."""
        sample_report.errors = ["Test error message"]
        markdown = generator._build_markdown(sample_report)

        # Should include errors section
        assert "## ⚠️ Errors Encountered" in markdown
        assert "Test error message" in markdown

    def test_generate_report_writes_file(self, generator, sample_report, tmp_path):
        """Test report file writing."""
        output_path = tmp_path / "test_report.md"

        generator.generate_report(sample_report, str(output_path))

        # Verify file was created
        assert output_path.exists()

        # Verify content
        content = output_path.read_text(encoding="utf-8")
        assert "# GitHub Repository Analysis: testuser" in content
        assert "## Developer Profile" in content

    def test_archived_repository_indicator(self, generator, sample_repository):
        """Test archived repository indicator."""
        sample_repository.is_archived = True

        analysis = RepositoryAnalysis(
            repository=sample_repository,
            rank=1,
            composite_score=50.0,
            commit_history=None,
            summary=None,
            tech_stack=None,
        )

        entry = generator._format_repository_entry(analysis)
        assert "⚠️ **Archived**" in entry

    def test_fork_repository_indicator(self, generator, sample_repository):
        """Test fork repository indicator."""
        sample_repository.is_fork = True

        analysis = RepositoryAnalysis(
            repository=sample_repository,
            rank=1,
            composite_score=70.0,
            commit_history=None,
            summary=None,
            tech_stack=None,
        )

        entry = generator._format_repository_entry(analysis)
        assert "🔀 **Fork**" in entry

    def test_github_flavored_markdown_compliance(self, generator, sample_report):
        """Test GitHub-flavored markdown compliance."""
        markdown = generator._build_markdown(sample_report)

        # Check for proper heading structure
        assert markdown.startswith("# GitHub Repository Analysis")  # H1 at start
        assert "## " in markdown  # Multiple H2s
        assert "### " in markdown  # Multiple H3s

        # Check for proper list formatting
        assert "- " in markdown

        # Check for proper bold formatting
        assert "**" in markdown

        # Check for proper link formatting
        assert "[" in markdown and "](" in markdown
