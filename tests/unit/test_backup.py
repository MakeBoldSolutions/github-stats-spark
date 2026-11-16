"""Tests for backup, restore, migration safety and health (ps-009)."""

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

from spark.backup import (
    BackupError,
    backup_due,
    create_backup,
    list_backups,
    restore_backup,
    verify_backup,
)
from spark.registry import Registry, connections
from spark.registry.db import MIGRATIONS, connect, schema_version
from spark.registry.secrets import SecretBox, generate_key
from spark.worker.__main__ import health_problem
from spark.worker.loop import CollectionWorker
from spark.worker.settings import WorkerSettings, _backup_interval
from tests.unit.registry_fakes import FakeGithub, make_repo

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
TOKEN = "github_pat_" + "z" * 40


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "config" / "registry.db"
    registry = Registry.open(path)
    registry.add_source("org", "Acme")
    registry.upsert_repository(1, {"full_name": "Acme/a"})
    registry.record_observation("source:org:acme", "repository_count", 1, "test")
    registry.close()
    return path


# -- create, verify, rotate ------------------------------------------------
def test_backup_is_verified_and_describes_its_contents(db, tmp_path):
    info = create_backup(db, tmp_path / "b", now=NOW)
    assert info.path.name == "registry-20260301T120000Z.db"
    assert (info.sources, info.repositories) == (1, 1)
    assert info.schema_version == len(MIGRATIONS)
    assert verify_backup(info.path).sources == 1


def test_a_backup_is_one_self_contained_file(db, tmp_path):
    info = create_backup(db, tmp_path / "b", now=NOW)
    verify_backup(info.path)  # verifying must not create companions either
    assert sorted(p.name for p in (tmp_path / "b").iterdir()) == [info.path.name]
    header = info.path.read_bytes()[:20]
    assert header[18] == header[19] == 1  # rollback-journal format, not WAL


def test_backup_includes_a_copy_of_the_config_file(db, tmp_path):
    config = tmp_path / "spark.yml"
    config.write_text("users: [a]\n")
    create_backup(db, tmp_path / "b", config_path=config, now=NOW)
    assert (tmp_path / "b" / "spark-20260301T120000Z.yml").read_text() == "users: [a]\n"


def test_rotation_keeps_the_newest_and_removes_their_config_copies(db, tmp_path):
    config = tmp_path / "spark.yml"
    config.write_text("x")
    for day in range(5):
        create_backup(
            db,
            tmp_path / "b",
            keep=3,
            config_path=config,
            now=NOW + timedelta(days=day),
        )
    kept = [p.name for p, _ in list_backups(tmp_path / "b")]
    assert kept == [f"registry-2026030{d}T120000Z.db" for d in (5, 4, 3)]
    assert sorted(p.name for p in (tmp_path / "b").glob("spark-*.yml")) == [
        f"spark-2026030{d}T120000Z.yml" for d in (3, 4, 5)
    ]


def test_backup_is_consistent_while_another_connection_is_writing(db, tmp_path):
    writer = sqlite3.connect(db, timeout=30)
    writer.execute("BEGIN")
    writer.execute(
        "INSERT INTO source (type, identifier, created_at) VALUES ('org','Inflight','x')"
    )
    info = create_backup(db, tmp_path / "b", now=NOW)  # while a write is open
    writer.rollback()
    writer.close()
    assert info.sources == 1  # the uncommitted row is not in the backup


def test_failed_verification_leaves_no_backup_behind(tmp_path):
    bad = tmp_path / "not-a-db.db"
    bad.write_bytes(b"this is not sqlite" * 100)
    with pytest.raises(BackupError):
        create_backup(bad, tmp_path / "b", now=NOW)
    assert list_backups(tmp_path / "b") == []


def test_missing_database_and_bad_arguments_are_clear_errors(tmp_path, db):
    with pytest.raises(BackupError, match="not found"):
        create_backup(tmp_path / "nope.db", tmp_path / "b")
    with pytest.raises(BackupError, match="keep"):
        create_backup(db, tmp_path / "b", keep=0)


def test_verify_rejects_corrupt_foreign_and_missing_files(tmp_path):
    corrupt = tmp_path / "registry-20260101T000000Z.db"
    corrupt.write_bytes(b"\x00" * 4096)
    foreign = tmp_path / "other.db"
    conn = sqlite3.connect(foreign)
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    for path in (corrupt, foreign, tmp_path / "missing.db"):
        with pytest.raises(BackupError):
            verify_backup(path)


def test_backup_due_follows_the_newest_backup(db, tmp_path):
    directory = tmp_path / "b"
    assert backup_due(directory, 3600, NOW) is True
    create_backup(db, directory, now=NOW)
    assert backup_due(directory, 3600, NOW + timedelta(minutes=30)) is False
    assert backup_due(directory, 3600, NOW + timedelta(hours=2)) is True


# -- restore ---------------------------------------------------------------
def test_restore_on_a_clean_host_reproduces_sources_history_and_secrets(tmp_path):
    key = generate_key()
    original = tmp_path / "old-host" / "registry.db"
    registry = Registry.open(original)
    registry.add_source("org", "Acme")
    conn = connections.create_connection(
        registry, SecretBox(key), name="acme", token=TOKEN
    )
    registry.update_source(1, connection_id=conn["id"])
    registry.record_observation("source:org:acme", "repository_count", 7, "discovery")
    registry.close()
    backup = create_backup(original, tmp_path / "backups", now=NOW).path

    clean = tmp_path / "new-host" / "registry.db"  # nothing exists here yet
    assert restore_backup(backup, clean) is None

    restored = Registry.open(clean)
    assert [s["identifier"] for s in restored.list_sources()] == ["Acme"]
    assert restored.conn.execute("SELECT value FROM observation").fetchone()[0] == "7"
    source = restored.list_sources()[0]
    # The restored token is readable with the same key, and only that key.
    assert connections.resolve_token(restored, SecretBox(key), source) == TOKEN
    restored.close()
    assert TOKEN not in clean.read_bytes().decode("latin-1")


def test_restore_keeps_a_safety_copy_of_the_current_database(db, tmp_path):
    backup = create_backup(db, tmp_path / "b", now=NOW).path
    registry = Registry.open(db)
    registry.add_source("org", "Later")
    registry.close()

    safety = restore_backup(backup, db, now=NOW + timedelta(hours=1))

    after = Registry.open(db)
    assert [s["identifier"] for s in after.list_sources()] == ["Acme"]
    after.close()
    kept = sqlite3.connect(safety)
    assert kept.execute("SELECT COUNT(*) FROM source").fetchone()[0] == 2
    kept.close()


def test_restore_refuses_a_database_in_use(db, tmp_path):
    backup = create_backup(db, tmp_path / "b", now=NOW).path
    holder = sqlite3.connect(db, timeout=30)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(BackupError, match="in use"):
            restore_backup(backup, db)
    finally:
        holder.rollback()
        holder.close()


def test_restore_refuses_a_backup_from_a_newer_release(db, tmp_path):
    backup = create_backup(db, tmp_path / "b", now=NOW).path
    conn = sqlite3.connect(backup)
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    conn.commit()
    conn.close()
    with pytest.raises(BackupError, match="newer"):
        restore_backup(backup, tmp_path / "restored.db")


# -- upgrade and rollback ---------------------------------------------------
def _make_v1_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(MIGRATIONS[0])
    conn.execute(
        "INSERT INTO source (type, identifier, created_at) VALUES ('org','Legacy','x')"
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()


def test_upgrade_keeps_a_copy_of_the_previous_schema_for_rollback(tmp_path):
    path = tmp_path / "registry.db"
    _make_v1_database(path)

    conn = connect(path)  # the new release starts and migrates
    assert schema_version(conn) == len(MIGRATIONS)
    assert conn.execute("SELECT identifier FROM source").fetchone()[0] == "Legacy"
    conn.close()

    saved = tmp_path / "registry.db.pre-v1.bak"
    old = sqlite3.connect(saved)
    assert old.execute("PRAGMA user_version").fetchone()[0] == 1
    assert old.execute("SELECT identifier FROM source").fetchone()[0] == "Legacy"
    old.close()

    connect(path).close()  # a later start does not overwrite it
    assert sorted(p.name for p in tmp_path.glob("registry.db.pre-*")) == [
        "registry.db.pre-v1.bak"
    ]


def test_fresh_databases_do_not_create_pre_migration_copies(tmp_path):
    connect(tmp_path / "registry.db").close()
    assert list(tmp_path.glob("*.bak")) == []


def test_old_release_refuses_a_newer_database_so_rollback_needs_the_saved_copy(
    tmp_path, monkeypatch
):
    path = tmp_path / "registry.db"
    connect(path).close()
    monkeypatch.setattr("spark.registry.db.MIGRATIONS", MIGRATIONS[:1])
    with pytest.raises(RuntimeError, match="newer"):
        connect(path)


# -- worker: scheduled backups and health -------------------------------------
@pytest.fixture
def settings(tmp_path, db):
    return WorkerSettings(
        users=["Octo"],
        interval_seconds=3600,
        retry_seconds=600,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        config_path=db.parent / "spark.yml",
        cache_dir=tmp_path / "cache",
        stage_dir=tmp_path / "stage",
        backup_dir=tmp_path / "backups",
        backup_interval_seconds=7200,
        backup_keep=2,
    )


def make_worker(settings, now=NOW):
    return CollectionWorker(
        settings,
        runner=lambda *a, **k: None,
        rate_limit_fn=lambda token: None,
        now_fn=lambda: now,
        github_factory=lambda token: FakeGithub(users={"Octo": [make_repo("Octo/x")]}),
        log=lambda msg: None,
    )


def test_worker_backs_up_when_due_and_publishes_the_result(settings):
    worker = make_worker(settings)
    assert worker.backup_if_due() is True
    assert worker.backup_if_due() is None  # not due again yet
    state = json.loads(settings.status_path.read_text())["backup"]
    assert state["ok"] is True and state["sources"] == 1
    assert str(settings.backup_dir) not in json.dumps(
        state
    )  # no paths in the public file


def test_a_restart_republishes_the_newest_existing_backup(settings):
    first = make_worker(settings)
    assert first.backup_if_due() is True
    # An older release rewrote status.json without the backup field.
    settings.status_path.write_text(json.dumps({"schema_version": 1}))

    restarted = make_worker(settings, now=NOW + timedelta(minutes=5))
    assert restarted.backup_if_due() is None  # nothing due, but status is restored
    state = json.loads(settings.status_path.read_text())["backup"]
    assert state["ok"] is True and state["sources"] == 1


def test_a_restart_does_not_vouch_for_a_corrupt_backup(settings):
    make_worker(settings).backup_if_due()
    newest = next(settings.backup_dir.glob("registry-*.db"))
    newest.write_bytes(b"corrupt" * 100)
    settings.status_path.write_text(json.dumps({"schema_version": 1}))
    restarted = make_worker(settings, now=NOW + timedelta(minutes=5))
    restarted.backup_if_due()
    assert "backup" not in json.loads(settings.status_path.read_text())


def test_worker_reports_a_failed_backup_and_backs_off(settings):
    settings.backup_dir = settings.db_path  # a file where a directory is needed
    worker = make_worker(settings)
    assert worker.backup_if_due() is False
    state = worker.status.state["backup"]
    assert state["ok"] is False and "backup failed" in state["reason"]
    assert worker.backup_if_due() is None  # waits before retrying


def test_scheduled_backups_can_be_switched_off(settings):
    settings.backup_interval_seconds = 0
    assert make_worker(settings).backup_if_due() is None
    assert not settings.backup_dir.exists()


def test_backup_interval_setting():
    assert _backup_interval(None) == 86400
    assert _backup_interval("12h") == 43200
    assert _backup_interval("off") == 0
    assert _backup_interval("5m") == 3600  # floor


def write_state(settings, **overrides):
    state = {
        "interval_seconds": 3600,
        "last_success_at": NOW.isoformat(),
        "consecutive_failures": 0,
    }
    state.update(overrides)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.status_path.write_text(json.dumps(state))


def beat(settings, age=0):
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.heartbeat_path.write_text(str(time.time() - age))


def test_health_is_ok_when_beating_and_recent(settings):
    beat(settings)
    write_state(settings)
    assert health_problem(settings, NOW + timedelta(minutes=5)) == ""


def test_health_goes_red_when_the_loop_stalls(settings):
    assert "heartbeat" in health_problem(settings, NOW)
    beat(settings, age=600)
    assert "stalled" in health_problem(settings, NOW)


def test_health_goes_red_when_collection_is_stale_or_never_succeeds(settings):
    beat(settings)
    write_state(settings)
    assert "two refresh intervals" in health_problem(settings, NOW + timedelta(hours=3))
    write_state(settings, last_success_at=None, consecutive_failures=3)
    assert "repeatedly" in health_problem(settings, NOW)
    write_state(settings, last_success_at=None, consecutive_failures=1)
    assert health_problem(settings, NOW) == ""


def test_health_goes_red_only_after_backups_fail_for_two_intervals(settings):
    beat(settings)
    fresh = (NOW - timedelta(hours=1)).isoformat()
    stale = (NOW - timedelta(hours=5)).isoformat()
    write_state(
        settings,
        last_success_at=NOW.isoformat(),
        backup={"ok": False, "last_success_at": fresh},
    )
    assert health_problem(settings, NOW) == ""
    write_state(
        settings,
        last_success_at=NOW.isoformat(),
        backup={"ok": False, "last_success_at": stale},
    )
    assert "backups are failing" in health_problem(settings, NOW)
