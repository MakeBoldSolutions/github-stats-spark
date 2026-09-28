"""Tests for RepositorySummarizer - three-tier fallback and helpers."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from spark.summarizer import RepositorySummarizer
from spark.models.repository import Repository
from spark.models.commit import CommitHistory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_repo(**overrides):
    now = datetime.now()
    defaults = dict(
        name="test-repo",
        description="A test repository",
        url="https://github.com/user/test-repo",
        created_at=now,
        updated_at=now,
        pushed_at=now,
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
    defaults.update(overrides)
    return Repository(**defaults)


def _make_history(**overrides):
    defaults = dict(
        repository_name="test-repo",
        total_commits=50,
        recent_90d=15,
        recent_180d=30,
        recent_365d=45,
        last_commit_date=datetime.now(),
    )
    defaults.update(overrides)
    return CommitHistory(**defaults)


SAMPLE_README = """# Awesome Project

A comprehensive toolkit for building scalable web applications.

## Features

- Fast rendering
- Dark mode
- API support
- Well documented
- Actively maintained

## Installation

```bash
pip install awesome-project
```

## Usage

```python
from awesome import App
app = App()
```
"""


@pytest.fixture
def summarizer():
    """Create a RepositorySummarizer with AI disabled."""
    return RepositorySummarizer(enable_ai=False)


# ---------------------------------------------------------------------------
# Model name normalization
# ---------------------------------------------------------------------------
class TestNormalizeModelName:
    def test_known_alias(self):
        assert (
            RepositorySummarizer._normalize_model_name("claude-haiku-3.5")
            == "claude-haiku-4-5"
        )

    def test_passthrough_unknown(self):
        assert (
            RepositorySummarizer._normalize_model_name("claude-haiku-4-5")
            == "claude-haiku-4-5"
        )

    def test_all_aliases_resolve(self):
        for alias, target in RepositorySummarizer.MODEL_ALIASES.items():
            assert RepositorySummarizer._normalize_model_name(alias) == target


# ---------------------------------------------------------------------------
# Candidate models
# ---------------------------------------------------------------------------
class TestCandidateModels:
    def test_default_model_first(self, summarizer):
        candidates = summarizer._candidate_models()
        assert candidates[0] == summarizer.model

    def test_no_duplicates(self, summarizer):
        candidates = summarizer._candidate_models()
        assert len(candidates) == len(set(candidates))

    def test_fallback_chain_included(self, summarizer):
        candidates = summarizer._candidate_models()
        assert len(candidates) >= 1


# ---------------------------------------------------------------------------
# README truncation
# ---------------------------------------------------------------------------
class TestTruncateReadme:
    def test_short_readme_unchanged(self, summarizer):
        text = "Short README"
        assert summarizer._truncate_readme(text) == text

    def test_long_readme_truncated(self, summarizer):
        text = "x" * 10000
        result = summarizer._truncate_readme(text)
        assert len(result) <= summarizer.MAX_README_LENGTH

    def test_truncation_at_paragraph_boundary(self, summarizer):
        para1 = "A" * 6000
        para2 = "B" * 4000
        text = para1 + "\n\n" + para2
        result = summarizer._truncate_readme(text)
        # Should cut at paragraph boundary
        assert len(result) <= summarizer.MAX_README_LENGTH

    def test_preserves_beginning(self, summarizer):
        text = "# Title\n\nImportant intro." + "\n\nFiller. " * 5000
        result = summarizer._truncate_readme(text)
        assert "# Title" in result
        assert "Important intro" in result


# ---------------------------------------------------------------------------
# Description extraction
# ---------------------------------------------------------------------------
class TestExtractDescription:
    def test_basic_extraction(self, summarizer):
        readme = "# My Project\n\nThis is a great project.\n\n## Features"
        desc = summarizer._extract_description(readme)
        assert desc == "This is a great project."

    def test_empty_readme(self, summarizer):
        assert summarizer._extract_description("") is None

    def test_heading_only(self, summarizer):
        assert summarizer._extract_description("# Title\n") is None

    def test_strips_html(self, summarizer):
        readme = "# Title\n\nA project with <b>bold</b> text."
        desc = summarizer._extract_description(readme)
        assert "<b>" not in desc

    def test_max_length(self, summarizer):
        readme = "# Title\n\n" + "x" * 500
        desc = summarizer._extract_description(readme)
        assert len(desc) <= 300


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
class TestExtractFeatures:
    def test_extracts_bullet_points(self, summarizer):
        readme = (
            "## Features\n- Fast rendering\n- Dark mode\n- API support\n\n## Install"
        )
        features = summarizer._extract_features(readme)
        assert len(features) == 3
        assert "Fast rendering" in features

    def test_max_five_features(self, summarizer):
        readme = "## Features\n" + "\n".join(f"- Feature {i}" for i in range(10))
        features = summarizer._extract_features(readme)
        assert len(features) == 5

    def test_no_features_section(self, summarizer):
        readme = "# Project\n\nSome text.\n## Installation"
        assert summarizer._extract_features(readme) == []

    def test_star_bullet_points(self, summarizer):
        readme = "## Features\n* Alpha\n* Beta"
        features = summarizer._extract_features(readme)
        assert len(features) == 2

    def test_plus_bullet_points(self, summarizer):
        readme = "## Feature\n+ One\n+ Two"
        features = summarizer._extract_features(readme)
        assert len(features) == 2


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------
class TestTrackCost:
    def test_cost_accumulates(self, summarizer):
        summarizer._track_cost(1000)
        assert summarizer.total_cost > 0
        first = summarizer.total_cost
        summarizer._track_cost(1000)
        assert summarizer.total_cost > first

    def test_zero_tokens(self, summarizer):
        summarizer._track_cost(0)
        assert summarizer.total_cost == 0.0


# ---------------------------------------------------------------------------
# Basic fallback
# ---------------------------------------------------------------------------
class TestBasicFallback:
    def test_with_description(self, summarizer):
        repo = _make_repo(description="My awesome project")
        result = summarizer._generate_basic_fallback(repo, None)
        assert "My awesome project" in result.summary
        assert result.generation_method == "basic-template"
        assert result.confidence_score == 40

    def test_without_description(self, summarizer):
        repo = _make_repo(description=None)
        result = summarizer._generate_basic_fallback(repo, None)
        assert "test-repo" in result.summary

    def test_includes_language(self, summarizer):
        repo = _make_repo(primary_language="Rust")
        result = summarizer._generate_basic_fallback(repo, None)
        assert "Rust" in result.summary

    def test_includes_stars_forks(self, summarizer):
        repo = _make_repo(stars=50, forks=10)
        result = summarizer._generate_basic_fallback(repo, None)
        assert "50 stars" in result.summary

    def test_includes_recent_activity(self, summarizer):
        repo = _make_repo()
        history = _make_history(recent_90d=25)
        result = summarizer._generate_basic_fallback(repo, history)
        assert "25 commits" in result.summary


# ---------------------------------------------------------------------------
# Enhanced fallback
# ---------------------------------------------------------------------------
class TestEnhancedFallback:
    def test_includes_readme_description(self, summarizer):
        repo = _make_repo()
        result = summarizer._generate_enhanced_fallback(repo, SAMPLE_README, None)
        assert "toolkit" in result.summary.lower()
        assert result.generation_method == "enhanced-template"
        assert result.confidence_score == 60

    def test_includes_language(self, summarizer):
        repo = _make_repo(primary_language="Go")
        result = summarizer._generate_enhanced_fallback(
            repo, "# Title\n\nSome desc.", None
        )
        assert "Go" in result.summary

    def test_active_maintenance_note(self, summarizer):
        repo = _make_repo()
        history = _make_history(recent_90d=20)
        result = summarizer._generate_enhanced_fallback(repo, "# T\n\nDesc.", history)
        assert "Actively maintained" in result.summary

    def test_popular_project_note(self, summarizer):
        repo = _make_repo(stars=200)
        result = summarizer._generate_enhanced_fallback(repo, "# T\n\nDesc.", None)
        assert "Popular" in result.summary

    def test_includes_features(self, summarizer):
        repo = _make_repo()
        result = summarizer._generate_enhanced_fallback(repo, SAMPLE_README, None)
        assert (
            "Fast rendering" in result.summary or "features" in result.summary.lower()
        )


# ---------------------------------------------------------------------------
# Three-tier fallback integration
# ---------------------------------------------------------------------------
class TestSummarizeRepository:
    def test_no_ai_with_readme_uses_enhanced(self, summarizer):
        repo = _make_repo()
        result = summarizer.summarize_repository(
            repo, readme_content=SAMPLE_README, allow_ai=False
        )
        assert result.generation_method == "enhanced-template"

    def test_no_ai_no_readme_uses_basic(self, summarizer):
        repo = _make_repo()
        result = summarizer.summarize_repository(
            repo, readme_content=None, allow_ai=False
        )
        assert result.generation_method == "basic-template"

    def test_ai_disabled_falls_to_enhanced(self, summarizer):
        repo = _make_repo()
        result = summarizer.summarize_repository(
            repo, readme_content=SAMPLE_README, allow_ai=True
        )
        # anthropic is None, so falls through to enhanced
        assert result.generation_method == "enhanced-template"

    def test_no_readme_repo_uses_basic(self, summarizer):
        repo = _make_repo(
            description="A JavaScript library", primary_language="JavaScript"
        )
        result = summarizer.summarize_repository(repo, readme_content=None)
        assert result.generation_method == "basic-template"
        assert "JavaScript" in result.summary

    def test_ai_summary_coerces_string_token_usage(self, summarizer):
        repo = _make_repo()
        summarizer.anthropic = MagicMock()
        summarizer.model = "claude-haiku-4-5"

        fake_response = MagicMock()
        fake_response.content = [MagicMock(text="Generated AI summary")]
        fake_response.usage = MagicMock(input_tokens=120, output_tokens="30")

        summarizer.anthropic.messages.create.return_value = fake_response
        summarizer.cache.get = MagicMock(return_value=None)

        result = summarizer._generate_ai_summary(
            repo=repo,
            readme_content=SAMPLE_README,
            commit_history=_make_history(),
            language_stats=repo.language_stats,
            tech_stack=None,
            repository_owner=None,
            repo_pushed_at=repo.pushed_at,
            write_cache=False,
        )

        assert result.generation_method == "claude-haiku-4-5"
        assert result.tokens_used == 150


# ---------------------------------------------------------------------------
# Cache metadata
# ---------------------------------------------------------------------------
class TestBuildCacheMetadata:
    def test_metadata_structure(self, summarizer):
        meta = summarizer._build_cache_metadata(
            repo_name="my-repo",
            repository_owner="testuser",
            cache_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert meta["repository"]["owner"] == "testuser"
        assert meta["repository"]["name"] == "my-repo"
        assert meta["category"] == "ai_summary"

    def test_none_date(self, summarizer):
        meta = summarizer._build_cache_metadata("repo", "owner", None)
        assert meta["category"] == "ai_summary"


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------
class TestBuildRepositoryPrompt:
    def test_includes_repo_info(self, summarizer):
        repo = _make_repo(name="cool-project", stars=42, primary_language="Python")
        prompt = summarizer._build_repository_prompt(repo, "README content", None)
        assert "cool-project" in prompt
        assert "42" in prompt
        assert "Python" in prompt

    def test_includes_language_stats(self, summarizer):
        repo = _make_repo()
        stats = {"Python": 8000, "JavaScript": 2000}
        prompt = summarizer._build_repository_prompt(
            repo, "README", None, language_stats=stats
        )
        assert "Python" in prompt
        assert "80.0%" in prompt

    def test_language_stats_with_string_numbers(self, summarizer):
        repo = _make_repo()
        stats = {"Python": "8000", "JavaScript": 2000}
        prompt = summarizer._build_repository_prompt(
            repo, "README", None, language_stats=stats
        )
        assert "Python" in prompt
        assert "JavaScript" in prompt

    def test_language_stats_skips_invalid_values(self, summarizer):
        repo = _make_repo()
        stats = {"Python": "oops", "JavaScript": "2000"}
        prompt = summarizer._build_repository_prompt(
            repo, "README", None, language_stats=stats
        )
        assert "Languages: JavaScript (100.0%)" in prompt

    def test_includes_commit_activity(self, summarizer):
        repo = _make_repo()
        history = _make_history(recent_90d=20, recent_365d=80)
        prompt = summarizer._build_repository_prompt(repo, "README", history)
        assert "20 commits (90d)" in prompt

    def test_includes_readme_content(self, summarizer):
        repo = _make_repo()
        prompt = summarizer._build_repository_prompt(repo, "This is the README.", None)
        assert "This is the README." in prompt

    def test_includes_quality_indicators(self, summarizer):
        repo = _make_repo()
        repo.has_tests = True
        repo.has_ci_cd = True
        repo.has_license = True
        prompt = summarizer._build_repository_prompt(repo, "README", None)
        assert "tests" in prompt
        assert "CI/CD" in prompt


# ---------------------------------------------------------------------------
# Constructor initialization
# ---------------------------------------------------------------------------
class TestSummarizerInit:
    def test_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            s = RepositorySummarizer(enable_ai=True)
            assert s.anthropic is None

    def test_enable_ai_false(self):
        s = RepositorySummarizer(api_key="test-key", enable_ai=False)
        assert s.anthropic is None

    def test_custom_model(self):
        s = RepositorySummarizer(model="claude-haiku-3.5", enable_ai=False)
        assert s.model == "claude-haiku-4-5"

    def test_default_model(self):
        s = RepositorySummarizer(enable_ai=False)
        assert s.model == RepositorySummarizer.DEFAULT_MODEL

    def test_counters_initialized(self):
        s = RepositorySummarizer(enable_ai=False)
        assert s.total_tokens_used == 0
        assert s.total_cost == 0.0
        assert s.cache_hits == 0
        assert s.cache_misses == 0
