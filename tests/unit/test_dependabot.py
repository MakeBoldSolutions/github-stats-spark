"""Dependabot alert collection, storage, export and scheduling."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from spark.registry import Registry
from spark.registry.db import MIGRATIONS, connect, schema_version
from spark.registry.secrets import SecretBox
from spark.security import dependabot as dep
from spark.security.dependabot import AlertCollection, collect_dependabot_alerts
from spark.security.export import age_days, build_dependabot, write_dependabot
from spark.worker.loop import CollectionWorker
from spark.worker.security import refresh_dependabot
from spark.worker.settings import WorkerSettings

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def raw_alert(number, state="open", severity="high", **extra):
    alert = {
        "number": number,
        "state": state,
        "dependency": {
            "package": {"ecosystem": "npm", "name": f"pkg{number}"},
            "manifest_path": "package-lock.json",
            "scope": "runtime",
        },
        "security_advisory": {
            "ghsa_id": f"GHSA-{number}",
            "cve_id": f"CVE-2026-{number}",
            "summary": "Bad thing",
            "severity": severity,
        },
        "security_vulnerability": {
            "severity": severity,
            "vulnerable_version_range": "< 2.0.0",
            "first_patched_version": {"identifier": "2.0.0"},
        },
        "created_at": "2025-12-01T00:00:00Z",
        "updated_at": "2025-12-02T00:00:00Z",
        "html_url": f"https://github.com/o/r/security/dependabot/{number}",
    }
    alert.update(extra)
    return alert


def response(status=200, body=None, next_url=None, headers=None):
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(body if body is not None else []).encode()
    resp.headers.update(headers or {})
    if next_url:
        resp.headers["Link"] = f'<{next_url}>; rel="next"'
    return resp


def pager(*responses):
    """A ``get`` that returns the given responses in order, recording calls."""
    calls = []
    queue = list(responses)

    def get(url, params=None):
        calls.append((url, params))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    get.calls = calls
    return get


# -- collection -----------------------------------------------------------


def test_lists_every_alert_across_pages_and_all_states():
    first = [raw_alert(n) for n in range(1, 101)]
    second = [raw_alert(101, state="fixed", fixed_at="2025-12-20T00:00:00Z")]
    third = [raw_alert(102, state="auto_dismissed")]
    get = pager(
        response(body=first, next_url="https://api.github.com/p2"),
        response(body=second, next_url="https://api.github.com/p3"),
        response(body=third),
    )
    result = collect_dependabot_alerts("o", "r", get=get)

    assert result.status == "available" and result.pages == 3
    assert len(result.alerts) == 102
    assert result.alerts[-1]["state"] == "dismissed"
    assert result.alerts[-1]["auto_dismissed"] is True
    # No state filter, so dismissed and fixed alerts come back with open ones.
    assert "state" not in (get.calls[0][1] or {})
    assert get.calls[1] == ("https://api.github.com/p2", None)


def test_zero_alerts_is_a_real_zero_not_unavailable():
    result = collect_dependabot_alerts("o", "r", get=pager(response(body=[])))
    assert (result.status, result.reason, result.alerts) == ("available", "none", [])


@pytest.mark.parametrize(
    "status, body, headers, expected",
    [
        (403, {"message": "Dependabot alerts are disabled for this repository."}, {},
         ("disabled", "dependabot_disabled")),
        (403, {"message": "Resource not accessible by personal access token"}, {},
         ("unauthorized", "permission_denied")),
        (401, {"message": "Bad credentials"}, {}, ("unauthorized", "permission_denied")),
        (404, {"message": "Not Found"}, {}, ("unauthorized", "not_found_or_no_access")),
        (403, {"message": "API rate limit exceeded"}, {}, ("unavailable", "rate_limited")),
        (403, {"message": "Forbidden"}, {"X-RateLimit-Remaining": "0"},
         ("unavailable", "rate_limited")),
        (500, {"message": "oops"}, {}, ("unavailable", "api_error")),
    ],
)
def test_failures_have_distinct_statuses(status, body, headers, expected):
    result = collect_dependabot_alerts(
        "o", "r", get=pager(response(status, body, headers=headers))
    )
    assert (result.status, result.reason) == expected
    assert result.alerts == [] and not result.read_alerts


def test_network_error_is_unavailable_not_an_exception():
    get = pager(requests.ConnectionError("down"))
    result = collect_dependabot_alerts("o", "r", get=get)
    assert (result.status, result.reason) == ("unavailable", "network_error")


def test_failure_on_a_later_page_keeps_what_was_read():
    get = pager(
        response(body=[raw_alert(1), raw_alert(2)], next_url="https://api.github.com/p2"),
        response(502, {"message": "Bad Gateway"}),
    )
    result = collect_dependabot_alerts("o", "r", get=get)
    assert (result.status, result.reason) == ("partial", "api_error")
    assert [a["number"] for a in result.alerts] == [1, 2]


def test_runaway_pagination_is_bounded_and_flagged():
    get = pager(*[response(body=[raw_alert(n)], next_url="https://x/next") for n in range(1, 4)])
    result = collect_dependabot_alerts("o", "r", get=get, max_pages=2)
    assert result.truncated and result.status == "partial"
    assert result.reason == "truncated" and len(result.alerts) == 2


def test_rate_remaining_is_reported():
    result = collect_dependabot_alerts(
        "o", "r", get=pager(response(body=[], headers={"X-RateLimit-Remaining": "42"}))
    )
    assert result.rate_remaining == 42


def test_normalize_keeps_detail_and_drops_dismisser_identity():
    raw = raw_alert(
        7,
        state="dismissed",
        dismissed_at="2025-12-10T00:00:00Z",
        dismissed_reason="tolerable_risk",
        dismissed_by={"login": "someone"},
        dismissed_comment="free text",
    )
    alert = dep.normalize_alert(raw)
    assert alert["ghsa_id"] == "GHSA-7" and alert["fixed_version"] == "2.0.0"
    assert alert["vulnerable_range"] == "< 2.0.0" and alert["ecosystem"] == "npm"
    assert alert["dismissed_reason"] == "tolerable_risk"
    assert "dismissed_by" not in alert and "dismissed_comment" not in alert


def test_normalize_handles_missing_fields_and_bad_input():
    assert dep.normalize_alert({"state": "open"}) is None
    sparse = dep.normalize_alert({"number": 1, "state": "weird"})
    assert sparse["state"] == "unknown" and sparse["severity"] == "unknown"
    assert sparse["fixed_version"] is None


# -- storage ---------------------------------------------------------------


def make_registry(*repos, private=()):
    registry = Registry.open(":memory:")
    source = registry.add_source("org", "o")
    for name in repos:
        registry.upsert_repository(
            source["id"],
            {
                "full_name": name,
                "html_url": f"https://github.com/{name}",
                "is_private": name in private,
            },
        )
    return registry


def available(*alerts):
    return AlertCollection(
        status="available", alerts=[dep.normalize_alert(a) for a in alerts], pages=1
    )


def test_migration_is_applied_to_new_and_existing_databases(tmp_path):
    assert len(MIGRATIONS) >= 3
    conn = connect(tmp_path / "r.db")
    assert schema_version(conn) == len(MIGRATIONS)
    conn.execute("SELECT * FROM dependabot_alert")
    conn.execute("SELECT * FROM dependabot_coverage")


def test_alerts_are_upserted_and_history_is_kept():
    registry = make_registry("o/r")
    registry.save_dependabot_result("o/r", available(raw_alert(1), raw_alert(2)))
    registry.save_dependabot_result(
        "o/r",
        available(raw_alert(1, state="fixed", fixed_at="2025-12-25T00:00:00Z")),
    )
    rows = {a["number"]: a for a in registry.list_dependabot_alerts()}
    assert rows[1]["state"] == "fixed"
    assert rows[2]["state"] == "open"  # absent from the later response, not deleted
    assert rows[1]["first_seen_at"] <= rows[1]["last_seen_at"]


def test_each_read_adds_a_counts_observation():
    registry = make_registry("o/r")
    registry.save_dependabot_result("o/r", available(raw_alert(1), raw_alert(2, severity="low")))
    registry.save_dependabot_result("o/r", available(raw_alert(1), raw_alert(2, severity="low")))
    rows = registry.conn.execute(
        "SELECT value FROM observation WHERE kind = 'dependabot.counts'"
    ).fetchall()
    assert len(rows) == 2
    counts = json.loads(rows[0]["value"])
    assert counts["open"] == 2 and counts["open_by_severity"] == {"high": 1, "low": 1}


def test_a_failed_check_keeps_alerts_and_last_success():
    registry = make_registry("o/r")
    registry.save_dependabot_result("o/r", available(raw_alert(1)))
    first = registry.list_dependabot_coverage()["o/r"]
    registry.save_dependabot_result(
        "o/r", AlertCollection(status="unauthorized", reason="permission_denied")
    )
    after = registry.list_dependabot_coverage()["o/r"]
    assert after["status"] == "unauthorized" and after["reason"] == "permission_denied"
    assert after["last_success_at"] == first["last_success_at"]
    assert len(registry.list_dependabot_alerts()) == 1
    # A failure is not an observation of zero alerts.
    assert registry.conn.execute(
        "SELECT COUNT(*) FROM observation WHERE kind = 'dependabot.counts'"
    ).fetchone()[0] == 1


def test_alerts_survive_pruning_the_repository():
    registry = make_registry("o/r")
    registry.save_dependabot_result("o/r", available(raw_alert(1)))
    registry.conn.execute("DELETE FROM repository_source")
    registry.prune_orphans()
    assert len(registry.list_dependabot_alerts()) == 1


# -- export ----------------------------------------------------------------


def test_age_uses_the_end_of_the_open_period():
    created = "2025-12-01T00:00:00Z"
    assert age_days({"state": "open", "created_at": created}, NOW) == 31
    fixed = {"state": "fixed", "created_at": created, "fixed_at": "2025-12-11T00:00:00Z"}
    assert age_days(fixed, NOW) == 10
    assert age_days({"state": "open", "created_at": None}, NOW) is None


def test_export_counts_states_and_distinguishes_coverage():
    registry = make_registry("o/ok", "o/off", "o/new", "o/secret", private=("o/secret",))
    registry.save_dependabot_result(
        "o/ok",
        available(
            raw_alert(1, severity="critical"),
            raw_alert(2, state="fixed", fixed_at="2025-12-20T00:00:00Z"),
            raw_alert(3, state="dismissed", dismissed_at="2025-12-20T00:00:00Z"),
        ),
    )
    registry.save_dependabot_result(
        "o/off", AlertCollection(status="disabled", reason="dependabot_disabled")
    )
    registry.save_dependabot_result("o/secret", available(raw_alert(9)))

    payload = build_dependabot(registry, 21600, NOW)
    repos = {r["full_name"]: r for r in payload["repositories"]}

    assert "o/secret" not in repos  # private data stays out
    assert all(a["repository"] != "o/secret" for a in payload["alerts"])
    assert repos["o/ok"]["counts"]["open"]["critical"] == 1
    assert repos["o/ok"]["counts"]["fixed"] == 1 and repos["o/ok"]["counts"]["dismissed"] == 1
    assert repos["o/off"]["status"] == "disabled" and repos["o/off"]["counts"]["open"]["total"] == 0
    assert repos["o/new"]["status"] == "not_checked"
    assert len(payload["alerts"]) == 3
    assert {"html_url", "ghsa_id", "fixed_version", "age_days"} <= set(payload["alerts"][0])


def test_export_leaves_out_repositories_only_disabled_sources_reach(tmp_path):
    registry = make_registry("o/r")
    registry.save_dependabot_result("o/r", available(raw_alert(1)))
    registry.set_source_enabled(registry.list_sources()[0]["id"], False)
    assert build_dependabot(registry, 60, NOW)["repositories"] == []
    # The retained history is still in the database.
    assert len(registry.list_dependabot_alerts()) == 1
    write_dependabot(registry, tmp_path, 60)
    assert (tmp_path / "security" / "dependabot.json").exists()


# -- worker refresh and schedule ------------------------------------------------


@pytest.fixture
def settings(tmp_path):
    return WorkerSettings(
        users=["o"],
        interval_seconds=3600,
        retry_seconds=600,
        min_rate_remaining=100,
        security_interval_seconds=7200,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        config_path=tmp_path / "spark.yml",
        cache_dir=tmp_path / "cache",
        stage_dir=tmp_path / "stage",
    )


def seed(settings, *repos, private=()):
    registry = make_registry(*repos, private=private)
    # make_registry is in-memory; copy to the worker's database file.
    disk = Registry.open(settings.db_path)
    source = disk.add_source("org", "o")
    for name in repos:
        disk.upsert_repository(
            source["id"],
            {"full_name": name, "html_url": "u", "is_private": name in private},
        )
    registry.close()
    disk.close()


def test_refresh_reads_public_repositories_and_writes_the_export(settings):
    seed(settings, "o/a", "o/b", "o/p", private=("o/p",))
    seen = []

    def collect(owner, repo, token):
        seen.append((owner, repo))
        return available(raw_alert(1))

    result = refresh_dependabot(settings, SecretBox(None), "tok", collect=collect, log=lambda m: None)
    assert sorted(seen) == [("o", "a"), ("o", "b")]  # the private repository is skipped
    assert (result.checked, result.read, result.outcome) == (2, 2, "success")
    exported = json.loads((settings.data_dir / "security" / "dependabot.json").read_text())
    assert len(exported["alerts"]) == 2


def test_one_unreadable_repository_makes_the_run_partial(settings):
    seed(settings, "o/a", "o/b")

    def collect(owner, repo, token):
        if repo == "b":
            return AlertCollection(status="disabled", reason="dependabot_disabled")
        return available(raw_alert(1))

    result = refresh_dependabot(settings, SecretBox(None), "t", collect=collect, log=lambda m: None)
    assert result.outcome == "partial" and (result.read, result.checked) == (1, 2)


def test_low_rate_limit_stops_and_leaves_the_rest_for_next_time(settings):
    seed(settings, "o/a", "o/b", "o/c")

    def collect(owner, repo, token):
        out = available()
        out.rate_remaining = 10
        return out

    result = refresh_dependabot(settings, SecretBox(None), "t", collect=collect, log=lambda m: None)
    assert result.checked == 1 and result.skipped == 2
    assert "rate limit" in result.stopped_reason and result.outcome == "partial"


def make_worker(settings, now=NOW, rate=None):
    return CollectionWorker(
        settings,
        runner=lambda *a, **k: None,
        rate_limit_fn=lambda token: rate,
        now_fn=lambda: now,
        log=lambda m: None,
    )


def test_security_is_due_on_first_start_then_only_after_the_interval(settings):
    seed(settings, "o/a")
    worker = make_worker(settings)
    assert worker.security_due(NOW)
    worker.status.record_security(at=NOW, outcome="success", interval_seconds=7200)
    assert not worker.security_due(NOW + timedelta(seconds=7199))
    assert worker.security_due(NOW + timedelta(seconds=7200))


def test_a_failed_refresh_retries_sooner(settings):
    seed(settings, "o/a")
    worker = make_worker(settings)
    worker.status.record_security(at=NOW, outcome="failed", interval_seconds=7200)
    assert not worker.security_due(NOW + timedelta(seconds=599))
    assert worker.security_due(NOW + timedelta(seconds=600))


def test_security_can_be_switched_off(settings):
    seed(settings, "o/a")
    settings.security_interval_seconds = 0
    worker = make_worker(settings)
    assert not worker.security_due(NOW)
    assert worker.security_if_due(force=True) is None


def test_security_status_is_published_and_survives_a_restart(settings, monkeypatch):
    seed(settings, "o/a")
    monkeypatch.setattr(
        "spark.worker.security.collect_dependabot_alerts",
        lambda owner, repo, token: available(raw_alert(1)),
    )
    # refresh_dependabot binds its default collector at import; patch the call.
    from spark.worker import security as sec

    monkeypatch.setattr(
        sec, "refresh_dependabot",
        lambda *a, **k: SimpleNamespace(
            outcome="success", checked=1, read=1, open_alerts=1, stopped_reason="", skipped=0
        ),
    )
    worker = make_worker(settings)
    assert worker.security_if_due() == "success"
    status = json.loads(settings.status_path.read_text())["security"]
    assert status["open_alerts"] == 1 and status["repositories_read"] == 1

    restarted = make_worker(settings)
    assert restarted.status.state["security"]["last_attempt_at"] == status["last_attempt_at"]
    assert restarted.security_if_due() is None  # not due again straight away


def test_a_crash_in_the_refresh_is_recorded_not_raised(settings, monkeypatch):
    seed(settings, "o/a")
    from spark.worker import security as sec

    def boom(*a, **k):
        raise RuntimeError("db locked")

    monkeypatch.setattr(sec, "refresh_dependabot", boom)
    worker = make_worker(settings)
    assert worker.security_if_due() == "failed"
    assert "db locked" in worker.status.state["security"]["reason"]


def test_low_rate_limit_skips_the_refresh(settings):
    seed(settings, "o/a")
    rate = {"limit": 5000, "remaining": 5, "reset_at": NOW.isoformat()}
    worker = make_worker(settings, rate=rate)
    import os

    os.environ["GITHUB_TOKEN"] = "t"
    try:
        assert worker.security_if_due() == "skipped"
    finally:
        del os.environ["GITHUB_TOKEN"]
    assert worker.status.state["security"]["outcome"] == "skipped"


def test_security_interval_setting_parses_and_clamps():
    base = {"SPARK_USER": "o"}
    assert WorkerSettings.from_env(base).security_interval_seconds == 6 * 3600
    assert WorkerSettings.from_env({**base, "SPARK_SECURITY_INTERVAL": "2h"}).security_interval_seconds == 7200
    assert WorkerSettings.from_env({**base, "SPARK_SECURITY_INTERVAL": "off"}).security_interval_seconds == 0
    assert WorkerSettings.from_env({**base, "SPARK_SECURITY_INTERVAL": "1m"}).security_interval_seconds == 900
