"""Regression tests for defects uncovered by full application validation."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from spark.ai_response import extract_response_text
from spark.cache import APICache
from spark.cli_output_layout import build_output_layout
from spark.models.summary import RepositorySummary
from spark.models.tech_stack import DependencyInfo, TechnologyStack
from spark.time_utils import sanitize_timestamp_for_filename
from spark.unified_report_workflow import UnifiedReportWorkflow


def test_output_layout_normalizes_mixed_case_owner():
    layout = build_output_layout("MakeBoldSolutions", "data")
    assert layout["data_dir"].as_posix() == "data/users/makeboldsolutions"
    assert layout["artifact_root"].as_posix() == "output/users/makeboldsolutions"


def test_ai_response_skips_non_text_blocks():
    blocks = [
        SimpleNamespace(thinking="private"),
        SimpleNamespace(text="first"),
        SimpleNamespace(text="second"),
    ]
    assert extract_response_text(blocks) == "first\nsecond"
    with pytest.raises(ValueError, match="no text"):
        extract_response_text([SimpleNamespace(type="tool_use")])


def test_summary_serialization_roundtrip():
    summary = RepositorySummary(
        repo_id="example",
        ai_summary="A summary",
        generation_timestamp=datetime.now(timezone.utc),
    )
    assert RepositorySummary.from_dict(summary.to_dict()) == summary


def test_technology_stack_serialization_roundtrip():
    stack = TechnologyStack(
        repository_name="example",
        languages={"Python": 100},
        dependencies=[
            DependencyInfo(name="pytest", current_version="9.1.1", ecosystem="pypi")
        ],
    )
    restored = TechnologyStack.from_dict(stack.to_dict())
    assert restored == stack
    assert isinstance(restored.dependencies[0], DependencyInfo)


@pytest.mark.parametrize("single_repository_mode", [False, True])
def test_unified_report_uses_current_constructor_and_validates(
    spark_config_factory, tmp_path, single_repository_mode
):
    workflow = UnifiedReportWorkflow(
        spark_config_factory(), cache=APICache(cache_dir=str(tmp_path))
    )
    report = workflow._generate_unified_report(
        "MakeBoldSolutions",
        SimpleNamespace(api_call_count=3),
        ["invalid-svg"],
        [],
        single_repository_mode=single_repository_mode,
    )
    assert report.username == "MakeBoldSolutions"
    assert report.total_api_calls == 3
    assert report.timestamp.tzinfo is not None
    assert any("Invalid SVG" in warning for warning in report.warnings)


def test_invalid_timestamp_still_produces_safe_cache_key():
    assert sanitize_timestamp_for_filename("invalid:timestamp") == "invalid-timestamp"
