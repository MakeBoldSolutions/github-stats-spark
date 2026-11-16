"""Tests for the scheduled collection worker (ps-002)."""

import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from spark.worker import publish
from tests.unit.registry_fakes import FakeGithub
from spark.worker.loop import CollectionWorker
from spark.worker.runner import RunResult, run_collection
from spark.worker.settings import SettingsError, WorkerSettings, parse_duration
from spark.worker.status import StatusStore, sanitize


def _symlinks_supported(tmp_path: Path) -> bool:
    try:
        (tmp_path / "t").mkdir()
        os.symlink("t", tmp_path / "l")
        return True
    except (OSError, NotImplementedError):
        return False


@pytest.fixture
def needs_symlinks(tmp_path_factory):
    if not _symlinks_supported(tmp_path_factory.mktemp("symcheck")):
        pytest.skip("symlinks unavailable on this platform")


@pytest.fixture
def settings(tmp_path):
    return WorkerSettings(
        users=["Octo"],
        interval_seconds=3600,
        retry_seconds=600,
        min_rate_remaining=100,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        config_path=tmp_path / "spark.yml",
        cache_dir=tmp_path / "cache",
        stage_dir=tmp_path / "stage",
    )


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _write_repos(cwd: Path, user: str, repos):
    target = cwd / "data" / "users" / user.lower()
    target.mkdir(parents=True, exist_ok=True)
    (target / "repositories.json").write_text(json.dumps({"repositories": repos}))
    svg = cwd / "output" / "users" / user.lower()
    svg.mkdir(parents=True, exist_ok=True)
    (svg / "overview.svg").write_text("<svg/>")


def _good_runner(repos=("a",)):
    def runner(command, cwd, env, timeout_seconds, stop_event, tick):
        folder = command[command.index("--slug") + 1] if "--slug" in command else None
        _write_repos(cwd, folder or command[command.index("--user") + 1], list(repos))
        return RunResult(exit_code=0)

    return runner


def _make(settings, runner, rate=None, clock=None):
    return CollectionWorker(
        settings,
        runner=runner,
        rate_limit_fn=lambda token: rate,
        now_fn=clock or (lambda: NOW),
        github_factory=lambda token: FakeGithub(users={"Octo": []}),
        log=lambda msg: None,
    )


def _published(settings):
    return json.loads(
        (settings.data_dir / "users" / "octo" / "repositories.json").read_text()
    )


# -- settings ----------------------------------------------------------
def test_parse_duration_units():
    assert parse_duration("90") == 90
    assert parse_duration("30m") == 1800
    assert parse_duration("6h") == 21600
    assert parse_duration("1d") == 86400
    with pytest.raises(SettingsError):
        parse_duration("soon")


def test_settings_require_user_and_sane_interval():
    with pytest.raises(SettingsError):
        WorkerSettings.from_env({})
    with pytest.raises(SettingsError):
        WorkerSettings.from_env({"SPARK_USER": "a", "SPARK_REFRESH_INTERVAL": "10s"})
    parsed = WorkerSettings.from_env(
        {
            "SPARK_USER": "a, b",
            "SPARK_REFRESH_INTERVAL": "2h",
            "SPARK_RUN_ON_START": "no",
        }
    )
    assert parsed.users == ["a", "b"]
    assert parsed.interval_seconds == 7200
    assert parsed.run_on_start is False
    assert parsed.retry_seconds <= parsed.interval_seconds


# -- status ------------------------------------------------------------
def test_sanitize_redacts_tokens_and_bounds_length():
    secret = "ghp_" + "a" * 36
    cleaned = sanitize(f"auth failed for {secret} " + "x" * 500)
    assert secret not in cleaned
    assert "[redacted]" in cleaned
    assert len(cleaned) <= 200


def test_status_tracks_success_failures_and_survives_restart(tmp_path):
    path = tmp_path / "status.json"
    store = StatusStore(path, 3600, ["Octo"])
    t0 = NOW
    store.record_attempt(started=t0, finished=t0, outcome="failed", reason="boom")
    store.record_attempt(started=t0, finished=t0, outcome="failed", reason="boom")
    assert store.state["consecutive_failures"] == 2
    assert store.state["last_success_at"] is None
    store.record_attempt(
        started=t0, finished=t0 + timedelta(seconds=5), outcome="success"
    )
    assert store.state["consecutive_failures"] == 0
    restarted = StatusStore(path, 3600, ["Octo"])
    assert restarted.state["last_success_at"] == store.state["last_success_at"]
    assert json.loads(path.read_text())["schema_version"] == 1


# -- publish -----------------------------------------------------------
def test_publish_swaps_atomically_and_prunes(tmp_path, needs_symlinks):
    volume = tmp_path / "vol"
    for i, ident in enumerate(
        ["20260101T000000Z", "20260102T000000Z", "20260103T000000Z"]
    ):
        stage = tmp_path / f"stage{i}"
        (stage / "users").mkdir(parents=True)
        (stage / "users" / "v.txt").write_text(ident)
        publish.publish_tree(stage, volume, ident)
    assert (volume / "users" / "v.txt").read_text() == "20260103T000000Z"
    releases = sorted(p.name for p in (volume / ".releases").iterdir())
    assert releases == ["20260102T000000Z", "20260103T000000Z"]


def test_publish_migrates_existing_real_directory(tmp_path, needs_symlinks):
    volume = tmp_path / "vol"
    (volume / "users").mkdir(parents=True)
    (volume / "users" / "old.txt").write_text("old")
    stage = tmp_path / "stage"
    (stage / "users").mkdir(parents=True)
    (stage / "users" / "new.txt").write_text("new")
    publish.publish_tree(stage, volume, "20260101T000000Z")
    assert (volume / "users" / "new.txt").exists()
    assert (
        volume / ".releases" / "legacy-20260101T000000Z" / "users" / "old.txt"
    ).exists()


def test_seed_stage_copies_published_content(tmp_path, needs_symlinks):
    volume = tmp_path / "vol"
    stage = tmp_path / "s"
    (stage / "users" / "other").mkdir(parents=True)
    (stage / "users" / "other" / "repositories.json").write_text("{}")
    publish.publish_tree(stage, volume, "20260101T000000Z")
    (volume / "status.json").write_text("{}")
    fresh = tmp_path / "fresh"
    publish.seed_stage(volume, fresh)
    assert (fresh / "users" / "other" / "repositories.json").exists()
    assert not (fresh / "status.json").exists()


# -- worker cycle -------------------------------------------------------
def test_successful_run_publishes_and_records_status(settings, needs_symlinks):
    worker = _make(settings, _good_runner(["a", "b"]))
    assert worker.run_once() == "success"
    assert len(_published(settings)["repositories"]) == 2
    assert (settings.output_dir / "users" / "octo" / "overview.svg").exists()
    state = json.loads(settings.status_path.read_text())
    assert state["last_attempt"]["outcome"] == "success"
    assert state["last_success_at"] is not None
    assert state["state"] == "idle"
    assert not settings.stage_dir.exists()


def test_failed_run_keeps_previous_data_and_reports_failure(settings, needs_symlinks):
    _make(settings, _good_runner(["good"])).run_once()

    def failing(command, cwd, env, timeout_seconds, stop_event, tick):
        _write_repos(cwd, "octo", ["half-written"])
        return RunResult(exit_code=1, error_count=3, last_error="token rejected")

    worker = _make(settings, failing)
    assert worker.run_once() == "failed"
    assert _published(settings)["repositories"] == ["good"]
    state = json.loads(settings.status_path.read_text())
    assert state["last_attempt"]["outcome"] == "failed"
    assert "code 1" in state["last_attempt"]["reason"]
    assert state["consecutive_failures"] == 1
    assert state["last_success_at"] is not None  # earlier success remembered
    expected_retry = datetime.fromisoformat(
        state["last_attempt"]["finished_at"]
    ) + timedelta(seconds=settings.retry_seconds)
    assert datetime.fromisoformat(state["next_run_at"]) == expected_retry


def test_empty_repository_list_is_not_published(settings, needs_symlinks):
    _make(settings, _good_runner(["keep"])).run_once()
    assert _make(settings, _good_runner([])).run_once() == "failed"
    assert _published(settings)["repositories"] == ["keep"]


def test_logged_errors_make_the_run_partial(settings, needs_symlinks):
    def noisy(command, cwd, env, timeout_seconds, stop_event, tick):
        _write_repos(cwd, "octo", ["a"])
        return RunResult(exit_code=0, error_count=2)

    worker = _make(settings, noisy)
    assert worker.run_once() == "partial"
    state = json.loads(settings.status_path.read_text())
    assert state["last_attempt"]["error_count"] == 2
    assert state["last_success_at"] is not None


def test_one_failed_user_does_not_block_the_other(settings, needs_symlinks):
    settings.users = ["Octo", "Broken"]

    def mixed(command, cwd, env, timeout_seconds, stop_event, tick):
        user = command[command.index("--user") + 1]
        if user == "Broken":
            return RunResult(exit_code=1)
        _write_repos(cwd, user, ["a"])
        return RunResult(exit_code=0)

    assert _make(settings, mixed).run_once() == "partial"
    assert _published(settings)["repositories"] == ["a"]


def test_low_rate_limit_skips_run_and_resumes_after_reset(settings):
    called = []
    os.environ["GITHUB_TOKEN"] = "test-token-value"
    try:
        reset = NOW + timedelta(minutes=20)
        worker = _make(
            settings,
            lambda *a, **k: called.append(1),
            rate={"limit": 5000, "remaining": 5, "reset_at": reset.isoformat()},
        )
        assert worker.run_once() == "skipped"
    finally:
        os.environ.pop("GITHUB_TOKEN", None)
    assert not called
    state = json.loads(settings.status_path.read_text())
    assert state["last_attempt"]["outcome"] == "skipped"
    assert state["consecutive_failures"] == 0
    assert datetime.fromisoformat(state["next_run_at"]) >= reset
    assert state["rate_limit"]["remaining"] == 5


def test_runner_exception_is_contained_as_a_failure(settings):
    def explode(*args, **kwargs):
        raise RuntimeError("disk on fire")

    assert _make(settings, explode).run_once() == "failed"
    state = json.loads(settings.status_path.read_text())
    assert "disk on fire" in state["last_attempt"]["reason"]


# -- runner (real subprocesses) ---------------------------------------------
def test_run_collection_counts_logged_errors(tmp_path):
    code = (
        "print('[2026-01-01 00:00:00] [spark.x] ERROR: bad thing')\n"
        "print('[2026-01-01 00:00:00] [spark.x] INFO: fine')\n"
    )
    result = run_collection(
        [sys.executable, "-c", code],
        tmp_path,
        os.environ,
        30,
        threading.Event(),
        emit=lambda line: None,
    )
    assert result.ok
    assert result.error_count == 1
    assert "bad thing" in result.last_error


def test_run_collection_times_out(tmp_path):
    result = run_collection(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        tmp_path,
        os.environ,
        1,
        threading.Event(),
        emit=lambda line: None,
    )
    assert result.timed_out
    assert not result.ok


# -- healthcheck ---------------------------------------------------------------
def test_healthcheck_depends_on_heartbeat_age(settings):
    from spark.worker.__main__ import healthcheck

    assert healthcheck(settings) == 1
    worker = _make(settings, _good_runner())
    worker.heartbeat(force=True)
    assert healthcheck(settings) == 0
    settings.heartbeat_path.write_text("1")
    assert healthcheck(settings) == 1


# -- source registry integration (ps-003) ---------------------------------
def _make_with_github(settings, runner, github):
    return CollectionWorker(
        settings,
        runner=runner,
        rate_limit_fn=lambda token: None,
        now_fn=lambda: NOW,
        github_factory=lambda token: github,
        log=lambda msg: None,
    )


def test_run_publishes_a_deduplicated_portfolio(settings):
    from tests.unit.registry_fakes import make_repo
    from spark.registry import Registry

    registry = Registry.open(settings.db_path)
    registry.add_source("user", "Octo")
    registry.add_source("org", "Acme")
    registry.add_source("repo", "acme/A")
    registry.close()
    github = FakeGithub(
        users={"Octo": [make_repo("Octo/x")]},
        orgs={"Acme": [make_repo("Acme/a"), make_repo("Acme/b")]},
        repos={"acme/A": make_repo("Acme/a")},
    )
    outcome = _make_with_github(settings, _good_runner(), github).run_once()

    assert outcome == "success"
    portfolio = json.loads((settings.data_dir / "portfolio.json").read_text())
    assert [r["full_name"] for r in portfolio["repositories"]] == [
        "Acme/a",
        "Acme/b",
        "Octo/x",
    ]


def test_bad_source_makes_the_run_partial_with_the_reason(settings):
    from spark.registry import Registry

    registry = Registry.open(settings.db_path)
    registry.add_source("user", "Octo")
    registry.add_source("org", "Typo")
    registry.close()
    worker = _make_with_github(settings, _good_runner(), FakeGithub(users={"Octo": []}))

    assert worker.run_once() == "partial"
    assert "org Typo: not_found" in worker.status.state["last_attempt"]["reason"]
    assert _published(settings)["repositories"] == ["a"]  # others still published


def test_org_and_repo_sources_each_get_their_own_dashboard(settings):
    from tests.unit.registry_fakes import make_repo
    from spark.registry import Registry

    registry = Registry.open(settings.db_path)
    registry.add_source("org", "Acme")
    registry.add_source("repo", "Acme/Widget")
    registry.set_source_enabled(registry.find_source("org", "Acme")["id"], True)
    registry.close()
    commands = []

    def runner(command, cwd, env, timeout_seconds, stop_event, tick):
        commands.append(command)
        return _good_runner()(command, cwd, env, timeout_seconds, stop_event, tick)

    github = FakeGithub(
        orgs={"Acme": [make_repo("Acme/a")]},
        repos={"Acme/Widget": make_repo("Acme/Widget")},
    )
    outcome = _make_with_github(settings, runner, github).run_once()

    assert outcome == "success"
    org_command = next(c for c in commands if "--repository" not in c)
    assert org_command[org_command.index("--user") + 1] == "Acme"
    repo_command = next(c for c in commands if "--repository" in c)
    assert repo_command[repo_command.index("--repository") + 1] == "Widget"
    assert repo_command[repo_command.index("--slug") + 1] == "acme--widget"
    assert (settings.data_dir / "users" / "acme" / "repositories.json").exists()
    assert (settings.data_dir / "users" / "acme--widget" / "repositories.json").exists()
    portfolio = json.loads((settings.data_dir / "portfolio.json").read_text())
    slugs = {s["identifier"]: s["slug"] for s in portfolio["sources"]}
    assert slugs == {"Acme": "acme", "Acme/Widget": "acme--widget"}


def test_a_disabled_source_is_not_collected(settings):
    from tests.unit.registry_fakes import make_repo
    from spark.registry import Registry

    registry = Registry.open(settings.db_path)
    registry.add_source("org", "Acme")
    source = registry.find_source("org", "Acme")
    registry.set_source_enabled(source["id"], False)
    registry.close()
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)
        return RunResult(exit_code=0)

    github = FakeGithub(orgs={"Acme": [make_repo("Acme/a")]})
    _make_with_github(settings, runner, github).run_once()
    assert calls == []


def test_registry_is_seeded_from_spark_user_once(settings):
    from spark.registry import Registry

    _make(settings, _good_runner()).run_once()
    registry = Registry.open(settings.db_path)
    assert [s["identifier"] for s in registry.list_sources()] == ["Octo"]
    registry.close()


# -- admin integration (ps-004) ---------------------------------------------
def test_refresh_request_from_the_api_is_consumed_once(settings):
    from spark.registry import Registry

    registry = Registry.open(settings.db_path)
    registry.request_refresh()
    registry.close()
    worker = _make(settings, _good_runner())
    assert worker._refresh_requested() is True
    assert worker._refresh_requested() is False


def test_each_user_source_collects_with_its_own_connection_token(settings, monkeypatch):
    from spark.registry import Registry, connections
    from spark.registry.secrets import SecretBox, generate_key

    key = generate_key()
    monkeypatch.setenv("SPARK_SECRET_KEY", key)
    registry = Registry.open(settings.db_path)
    conn = connections.create_connection(
        registry, SecretBox(key), name="octo", token="github_pat_" + "o" * 40
    )
    source = registry.add_source("user", "Octo")
    registry.update_source(source["id"], connection_id=conn["id"])
    registry.close()
    seen = {}

    def runner(command, cwd, env, timeout_seconds, stop_event, tick):
        seen["token"] = env.get("GITHUB_TOKEN")
        _write_repos(cwd, "Octo", ["a"])
        return RunResult(exit_code=0)

    monkeypatch.setenv("GITHUB_TOKEN", "default-token")
    assert _make(settings, runner).run_once() == "success"
    assert seen["token"] == "github_pat_" + "o" * 40


def test_user_with_an_expired_connection_is_skipped_not_run_unauthenticated(
    settings, monkeypatch
):
    from spark.registry import Registry, connections
    from spark.registry.secrets import SecretBox, generate_key

    key = generate_key()
    monkeypatch.setenv("SPARK_SECRET_KEY", key)
    registry = Registry.open(settings.db_path)
    conn = connections.create_connection(
        registry,
        SecretBox(key),
        name="old",
        token="github_pat_" + "o" * 40,
        expires_at="2020-01-01",
    )
    source = registry.add_source("user", "Octo")
    registry.update_source(source["id"], connection_id=conn["id"])
    registry.close()
    calls = []

    def runner(*args, **kwargs):
        calls.append(1)
        return RunResult(exit_code=0)

    worker = _make(settings, runner)
    assert worker.run_once() == "failed"
    assert calls == []
    registry = Registry.open(settings.db_path)
    assert registry.list_sources()[0]["error_code"] == "connection_unusable"
    registry.close()


def test_source_slug_never_collides_with_a_login():
    from spark.cli_output_layout import source_slug

    assert source_slug("user", "MarkHazleton") == "markhazleton"
    assert source_slug("org", "West-Wichita-Rotary-Club") == "west-wichita-rotary-club"
    assert source_slug("repo", "Acme/My.Repo") == "acme--my.repo"
    # GitHub logins cannot contain "--", so a repo slug is never a login.
    assert "--" in source_slug("repo", "a/b")


def test_build_command_scopes_a_repository_run():
    from spark.worker.runner import build_command

    command = build_command(
        "acme", Path("c.yml"), [], slug="acme--widget", repository="Widget"
    )
    assert command[-4:] == ["--slug", "acme--widget", "--repository", "Widget"]
    assert "--slug" not in build_command("acme", Path("c.yml"), [])
