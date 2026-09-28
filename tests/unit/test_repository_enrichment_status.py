"""Unit tests for repository enrichment status model behavior."""

from datetime import datetime, timezone

from spark.models.repository import (
    Repository,
    RepositoryDiagnosticsSummary,
    RepositoryPullRequestSummary,
    RepositorySecuritySummary,
)


def test_repository_pull_request_summary_defaults_round_trip():
    summary = RepositoryPullRequestSummary()
    payload = summary.to_dict()
    restored = RepositoryPullRequestSummary.from_dict(payload)

    assert restored.availability == "unavailable"
    assert restored.reason == "not_requested"
    assert restored.total_open == 0


def test_repository_security_summary_defaults_round_trip():
    summary = RepositorySecuritySummary()
    payload = summary.to_dict()
    restored = RepositorySecuritySummary.from_dict(payload)

    assert restored.availability == "unavailable"
    assert restored.overall_state == "unavailable"
    assert restored.active_alert_counts["total_open"] == 0


def test_repository_diagnostics_summary_defaults_round_trip():
    summary = RepositoryDiagnosticsSummary()
    payload = summary.to_dict()
    restored = RepositoryDiagnosticsSummary.from_dict(payload)

    assert restored.availability == "unavailable"
    assert restored.reason == "not_requested"
    assert restored.pull_requests == {}


def test_repository_from_dict_preserves_enrichment_objects():
    repo = Repository.from_dict(
        {
            "name": "sample",
            "url": "https://github.com/markhazleton/sample",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "is_private": False,
            "pull_request_summary": {
                "availability": "available",
                "reason": "none",
                "has_open_pull_requests": True,
                "total_open": 1,
                "draft_count": 0,
                "review_requested_count": 1,
                "oldest_open_age_days": 5,
                "source": "rest.pulls.list",
            },
            "security_summary": {
                "availability": "partial",
                "reason": "permission_denied",
                "overall_state": "warning_present",
                "feature_status": {
                    "advanced_security": "unavailable",
                    "secret_scanning": "unavailable",
                    "secret_scanning_push_protection": "unavailable",
                    "dependency_alerts": "enabled",
                    "automated_security_fixes": "enabled",
                },
                "active_alert_counts": {
                    "total_open": 2,
                    "critical": 1,
                    "high": 1,
                    "medium": 0,
                    "low": 0,
                },
                "sources": ["rest.dependabot.alerts"],
            },
            "diagnostics_summary": {
                "availability": "available",
                "reason": "none",
                "pull_requests": {
                    "availability": "available",
                    "reason": "none",
                    "total_open": 3,
                },
                "issues": {
                    "availability": "available",
                    "reason": "none",
                    "total_open": 5,
                    "stale_over_90d": 1,
                },
                "security": {
                    "availability": "partial",
                    "reason": "not_supported",
                    "dependabot": {
                        "total_open": 2,
                        "critical": 1,
                        "high": 1,
                        "medium": 0,
                        "low": 0,
                    },
                    "code_scanning": {
                        "total_open": 0,
                        "error": 0,
                        "warning": 0,
                        "note": 0,
                    },
                },
                "actions": {
                    "availability": "available",
                    "reason": "none",
                    "recent_runs": 2,
                    "failure_count": 1,
                },
                "sources": ["rest.pulls.list", "rest.issues.list"],
            },
        }
    )

    assert repo.pull_request_summary.total_open == 1
    assert repo.security_summary.availability == "partial"
    assert repo.diagnostics_summary.pull_requests["total_open"] == 3
    assert repo.to_dict()["security_summary"]["active_alert_counts"]["critical"] == 1
    assert repo.to_dict()["diagnostics_summary"]["issues"]["total_open"] == 5


def test_repository_website_url_prefers_homepage_then_pages():
    now = datetime.now(timezone.utc)
    repo = Repository(
        name="sample",
        description="repo",
        url="https://github.com/markhazleton/sample",
        created_at=now,
        updated_at=now,
        pushed_at=now,
        primary_language="Python",
        homepage="https://example.com",
        has_pages=True,
        is_private=False,
    )

    assert repo.website_url == "https://example.com"
    assert repo.pages_url == "https://markhazleton.github.io/sample/"


def test_repository_from_dict_defaults_and_dashboard_dict():
    repo = Repository.from_dict({"name": "fallback"})

    dashboard = repo.to_dashboard_dict()

    assert repo.name == "fallback"
    assert dashboard["name"] == "fallback"
    assert dashboard["pull_request_summary"]["availability"] == "unavailable"


def test_repository_from_github_repo_extracts_quality_and_activity_indicators():
    now = datetime.now(timezone.utc)

    class FakeContent:
        def __init__(self, name, item_type):
            self.name = name
            self.type = item_type

    class FakeGitHubRepo:
        name = "sample"
        description = "repo"
        html_url = "https://github.com/markhazleton/sample"
        created_at = now
        updated_at = now
        pushed_at = now
        language = "Python"
        stargazers_count = 1
        forks_count = 2
        watchers_count = 3
        open_issues_count = 4
        archived = False
        fork = True
        parent = object()
        size = 5
        private = False
        homepage = None
        has_pages = True

        @staticmethod
        def get_readme():
            return object()

        @staticmethod
        def get_contributors():
            return type("Contribs", (), {"totalCount": 7})()

        @staticmethod
        def get_workflows():
            return type("Workflows", (), {"totalCount": 1})()

        @staticmethod
        def get_contents(path):
            return [
                FakeContent("tests", "dir"),
                FakeContent("docs", "dir"),
                FakeContent("CHANGELOG.md", "file"),
            ]

        @staticmethod
        def get_license():
            return object()

        @staticmethod
        def get_releases():
            return type(
                "Releases",
                (),
                {
                    "totalCount": 1,
                    "__getitem__": lambda self, idx: type(
                        "Release", (), {"created_at": now}
                    )(),
                },
            )()

    repo = Repository.from_github_repo(FakeGitHubRepo())

    assert repo.has_readme is True
    assert repo.has_tests is True
    assert repo.has_docs is True
    assert repo.has_license is True
    assert repo.release_count == 1
    assert repo.pull_request_summary.availability == "unavailable"
