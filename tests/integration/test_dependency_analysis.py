"""Integration tests for dependency parsing workflow."""

import pytest
from spark.dependencies.analyzer import RepositoryDependencyAnalyzer


class TestDependencyAnalysisIntegration:
    """Integration tests for dependency parsing."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return RepositoryDependencyAnalyzer()

    def test_analyze_npm_dependencies(self, analyzer):
        """Test parsing NPM dependencies."""
        dependency_files = {"package.json": """
            {
                "dependencies": {
                    "react": "^18.0.0",
                    "lodash": "^4.17.0"
                }
            }
            """}

        report = analyzer.analyze_repository(dependency_files)

        assert report.total_dependencies == 2
        assert "npm" in report.ecosystems

    def test_analyze_python_dependencies(self, analyzer):
        """Test parsing Python dependencies."""
        dependency_files = {"requirements.txt": """
            requests>=2.31.0
            flask==3.0.0
            """}

        report = analyzer.analyze_repository(dependency_files)

        assert report.total_dependencies == 2
        assert "pypi" in report.ecosystems

    def test_analyze_mixed_ecosystems(self, analyzer):
        """Test parsing multiple ecosystems."""
        dependency_files = {
            "package.json": '{"dependencies": {"react": "^18.0.0"}}',
            "requirements.txt": "requests>=2.31.0",
        }

        report = analyzer.analyze_repository(dependency_files)

        assert report.total_dependencies == 2
        assert "npm" in report.ecosystems
        assert "pypi" in report.ecosystems

    def test_analyze_no_dependencies(self, analyzer):
        """Test parsing repository with no dependencies."""
        report = analyzer.analyze_repository({})

        assert report.total_dependencies == 0
        assert len(report.ecosystems) == 0

    def test_analyze_malformed_file(self, analyzer):
        """Test parsing malformed dependency file."""
        dependency_files = {"package.json": "{ invalid json"}

        report = analyzer.analyze_repository(dependency_files)

        assert report.total_dependencies == 0

    def test_dependency_summary(self, analyzer):
        """Test generating dependency summary."""
        dependency_files = {"requirements.txt": "requests==2.0.0\nflask==3.0.0"}

        report = analyzer.analyze_repository(dependency_files)
        summary = analyzer.get_dependency_summary(report)

        assert "Total Dependencies" in summary
        assert "pypi" in summary.lower()

    def test_analyze_dependency_versions_with_registry_lookup(
        self, analyzer, monkeypatch
    ):
        """Test enriching dependencies with latest version data."""
        dependency_files = {"package.json": '{"dependencies": {"react": "^18.2.0"}}'}

        monkeypatch.setattr(
            analyzer,
            "_fetch_latest_version",
            lambda ecosystem, dependency_name, timeout_seconds: (
                "19.0.0",
                "resolved",
                "npm",
            ),
        )

        report = analyzer.analyze_repository(dependency_files)

        assert report.total_dependencies == 1
        detail = report.details[0]
        assert detail.current_version == "18.2.0"
        assert detail.latest_version == "19.0.0"
        assert detail.current_version_known is True
        assert detail.latest_version_status == "resolved"
        assert detail.status == "major_outdated"
        assert detail.is_outdated is True
        assert detail.source_file == "package.json"

    def test_analyze_unbounded_dependency_marks_unknown_current_version(
        self, analyzer, monkeypatch
    ):
        """Test unbounded dependency requirements expose unknown current version."""
        dependency_files = {"requirements.txt": "requests\n"}

        monkeypatch.setattr(
            analyzer,
            "_fetch_latest_version",
            lambda ecosystem, dependency_name, timeout_seconds: (
                "2.32.0",
                "resolved",
                "pypi",
            ),
        )

        report = analyzer.analyze_repository(dependency_files)

        detail = report.details[0]
        assert detail.current_version == "latest"
        assert detail.current_version_known is False
        assert detail.version_requirement == "latest"
        assert detail.status == "unknown"
        assert detail.latest_version == "2.32.0"

    # REMOVED: test_real_npm_package - Version checking removed (out of scope)
    # REMOVED: test_real_pypi_package - Version checking removed (out of scope)
