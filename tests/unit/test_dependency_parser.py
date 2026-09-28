"""Unit tests for dependency parser."""

import pytest
from spark.dependencies.parser import DependencyParser


class TestDependencyParser:
    """Test cases for DependencyParser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return DependencyParser()

    def test_parse_package_json(self, parser):
        """Test parsing package.json (NPM)."""
        content = """
        {
            "dependencies": {
                "react": "^18.2.0",
                "lodash": "~4.17.21"
            },
            "devDependencies": {
                "typescript": ">=5.0.0"
            }
        }
        """
        deps = parser.parse_file("package.json", content)

        assert len(deps) == 3
        assert any(d.name == "react" and d.version_constraint == "18.2.0" for d in deps)
        assert any(
            d.name == "lodash" and d.version_constraint == "4.17.21" for d in deps
        )
        assert any(
            d.name == "typescript" and d.version_constraint == "5.0.0" for d in deps
        )

    def test_parse_requirements_txt(self, parser):
        """Test parsing requirements.txt (PyPI)."""
        content = """
        # Comments should be ignored
        requests>=2.31.0
        flask==3.0.0
        numpy
        -e git+https://github.com/user/repo.git#egg=package
        """
        deps = parser.parse_file("requirements.txt", content)

        assert len(deps) == 3
        assert any(
            d.name == "requests" and d.version_constraint == "2.31.0" for d in deps
        )
        assert any(d.name == "flask" and d.version_constraint == "3.0.0" for d in deps)
        assert any(d.name == "numpy" and d.version_constraint == "latest" for d in deps)

    def test_parse_pyproject_toml(self, parser):
        """Test parsing pyproject.toml (PyPI)."""
        content = """
        [tool.poetry.dependencies]
        python = "^3.9"
        requests = "^2.31.0"
        flask = {version = "^3.0.0"}
        """
        deps = parser.parse_file("pyproject.toml", content)

        assert len(deps) >= 2  # Excludes python
        assert any(d.name == "requests" for d in deps)
        assert any(d.name == "flask" for d in deps)

    def test_parse_gemfile(self, parser):
        """Test parsing Gemfile (RubyGems)."""
        content = """
        gem 'rails', '7.0.0'
        gem 'puma'
        gem "nokogiri", "~> 1.14"
        """
        deps = parser.parse_file("Gemfile", content)

        assert len(deps) == 3
        assert any(d.name == "rails" and d.version_constraint == "7.0.0" for d in deps)
        assert any(d.name == "puma" and d.version_constraint == "latest" for d in deps)
        assert any(
            d.name == "nokogiri" and d.version_constraint == "1.14" for d in deps
        )

    def test_parse_go_mod(self, parser):
        """Test parsing go.mod (Go Modules)."""
        content = """
        module github.com/user/project

        go 1.21

        require (
            github.com/gin-gonic/gin v1.9.1
            github.com/stretchr/testify v1.8.4
        )

        require github.com/spf13/cobra v1.7.0
        """
        deps = parser.parse_file("go.mod", content)

        assert len(deps) == 3
        assert any(
            d.name == "github.com/gin-gonic/gin" and d.version_constraint == "1.9.1"
            for d in deps
        )
        assert any(
            d.name == "github.com/stretchr/testify" and d.version_constraint == "1.8.4"
            for d in deps
        )
        assert any(
            d.name == "github.com/spf13/cobra" and d.version_constraint == "1.7.0"
            for d in deps
        )

    def test_unsupported_file(self, parser):
        """Test parsing unsupported file type."""
        deps = parser.parse_file("unknown.txt", "content")
        assert len(deps) == 0

    def test_malformed_json(self, parser):
        """Test parsing malformed JSON."""
        content = "{ invalid json"
        deps = parser.parse_file("package.json", content)
        assert len(deps) == 0

    def test_clean_npm_version(self, parser):
        """Test NPM version cleaning."""
        assert parser._clean_npm_version("^1.2.3") == "1.2.3"
        assert parser._clean_npm_version("~4.5.6") == "4.5.6"
        assert parser._clean_npm_version(">=7.8.9") == "7.8.9"
        assert parser._clean_npm_version("1.0.0 - 2.0.0") == "1.0.0"
        assert parser._clean_npm_version("1.0.0 || 2.0.0") == "1.0.0"
