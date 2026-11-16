"""The scheduler loop: run collection, publish atomically, record status."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from github import Auth, Github

from spark.cli_output_layout import slugify_username
from spark.backup import BackupError, backup_due, create_backup
from spark.registry import Registry, seed_users
from spark.registry.connections import resolve_token
from spark.registry.secrets import SecretBox, SecretError, load_key
from spark.registry.discovery import run_discovery
from spark.registry.export import write_portfolio
from spark.worker import publish
from spark.worker.rate_limit import fetch_rate_limit
from spark.worker.runner import RunResult, build_command, run_collection
from spark.worker.settings import WorkerSettings
from spark.worker.status import StatusStore, utcnow

HEARTBEAT_EVERY_SECONDS = 15
RATE_LIMIT_RESUME_PAD_SECONDS = 60
BACKUP_RETRY_SECONDS = 15 * 60


class CollectionWorker:
    def __init__(
        self,
        settings: WorkerSettings,
        *,
        runner: Callable[..., RunResult] = run_collection,
        rate_limit_fn: Callable[[str], Optional[dict]] = fetch_rate_limit,
        now_fn: Callable[[], datetime] = utcnow,
        github_factory: Callable[[str], object] = lambda token: (
            Github(auth=Auth.Token(token), timeout=30) if token else Github(timeout=30)
        ),
        log: Callable[[str], None] = lambda msg: print(msg, flush=True),
    ):
        self.settings = settings
        self.runner = runner
        self.rate_limit_fn = rate_limit_fn
        self.now = now_fn
        self.github_factory = github_factory
        self.secret_box = SecretBox(load_key())
        self._backup_failed_at: Optional[datetime] = None
        self._user_tokens: dict = {}
        self.log = log
        self.stop_event = threading.Event()
        self.status = StatusStore(
            settings.status_path, settings.interval_seconds, settings.users
        )
        self._last_beat = 0.0

    # -- liveness -----------------------------------------------------
    def heartbeat(self, force: bool = False) -> None:
        if not force and time.monotonic() - self._last_beat < HEARTBEAT_EVERY_SECONDS:
            return
        self._last_beat = time.monotonic()
        path = self.settings.heartbeat_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass  # liveness is best-effort; collection must not depend on it

    # -- one collection cycle ------------------------------------------
    def run_once(self) -> str:
        """Run one cycle and return its outcome (success/partial/failed/skipped)."""
        s = self.settings
        token = os.environ.get("GITHUB_TOKEN", "")
        started = self.now()

        rate = self.rate_limit_fn(token) if token else None
        if rate and rate["remaining"] < s.min_rate_remaining:
            reset_at = datetime.fromisoformat(rate["reset_at"])
            resume = max(
                reset_at + timedelta(seconds=RATE_LIMIT_RESUME_PAD_SECONDS),
                started + timedelta(seconds=RATE_LIMIT_RESUME_PAD_SECONDS),
            )
            self.status.record_attempt(
                started=started,
                finished=self.now(),
                outcome="skipped",
                reason=(
                    f"GitHub rate limit low ({rate['remaining']} remaining); "
                    "resuming after reset"
                ),
                next_run=resume,
                rate_limit=rate,
            )
            self.log(f"Skipped: rate limit low ({rate['remaining']} remaining)")
            return "skipped"

        self.status.mark_running(started)
        self.heartbeat(force=True)
        stage = s.stage_dir
        outcome, reason, errors, exit_code = "failed", "", 0, None
        try:
            if stage.exists():
                shutil.rmtree(stage)
            (stage / "data").mkdir(parents=True)
            (stage / "output").mkdir(parents=True)
            publish.seed_stage(s.data_dir, stage / "data")
            publish.seed_stage(s.output_dir, stage / "output")

            env = dict(os.environ)
            env["SPARK_CACHE_DIR"] = str(s.cache_dir)
            users, problems, portfolio_count = self._refresh_registry(token, stage)
            ok_users, failed_users = [], []
            for user in users:
                self.log(f"Collecting {user}")
                user_env = dict(env)
                if self._user_tokens.get(user):
                    user_env["GITHUB_TOKEN"] = self._user_tokens[user]
                result = self.runner(
                    build_command(user, s.config_path, s.extra_args),
                    cwd=stage,
                    env=user_env,
                    timeout_seconds=s.run_timeout_seconds,
                    stop_event=self.stop_event,
                    tick=self.heartbeat,
                )
                errors += result.error_count
                exit_code = result.exit_code
                if result.ok and self._has_valid_data(stage, user):
                    ok_users.append(user)
                else:
                    failed_users.append(user)
                    reason = self._failure_reason(result, user) or reason

            if ok_users or (not users and portfolio_count):
                release_id = started.strftime("%Y%m%dT%H%M%SZ")
                publish.publish_tree(stage / "data", s.data_dir, release_id)
                publish.publish_tree(stage / "output", s.output_dir, release_id)
                outcome = (
                    "partial" if (failed_users or errors or problems) else "success"
                )
                if failed_users:
                    reason = f"{len(failed_users)} user(s) failed: " + reason
                elif errors:
                    reason = f"completed with {errors} logged error(s)"
                elif problems:
                    reason = "; ".join(problems)
            else:
                reason = reason or "no data was collected"
        except Exception as error:  # noqa: BLE001 - the loop must survive anything
            outcome, reason = "failed", f"{type(error).__name__}: {error}"
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        finished = self.now()
        delay = (
            s.interval_seconds if outcome in ("success", "partial") else s.retry_seconds
        )
        self.status.record_attempt(
            started=started,
            finished=finished,
            outcome=outcome,
            reason=reason,
            error_count=errors,
            exit_code=exit_code,
            next_run=finished + timedelta(seconds=delay),
            rate_limit=self.rate_limit_fn(token) if token else None,
        )
        self.log(f"Collection {outcome}: {reason or 'ok'}")
        return outcome

    def _refresh_registry(self, token: str, stage):
        """Discover sources and write portfolio.json into the stage.

        Returns (users to collect, source problems, portfolio repository count).
        A failing source is recorded on that source and reported; it never
        blocks the others.
        """
        registry = Registry.open(self.settings.db_path)
        try:
            seed_users(registry, self.settings.users)
            clients: dict = {}

            def github_for(source):
                # Each source uses its own connection, else the default token.
                # A client is reused for sources that share a token.
                source_token = resolve_token(
                    registry, self.secret_box, source, default=token
                )
                if source_token not in clients:
                    clients[source_token] = self.github_factory(source_token)
                return clients[source_token]

            results = run_discovery(registry, github_for=github_for)
            payload = write_portfolio(registry, stage / "data" / "portfolio.json")
            sources = {src["id"]: src for src in registry.list_sources()}
            problems = [
                f"{sources[r['source_id']]['type']} "
                f"{sources[r['source_id']]['identifier']}: {r['code']}"
                for r in results
                if r["state"] == "error"
            ]
            users, self._user_tokens = [], {}
            for source in registry.list_sources(enabled_only=True):
                if source["type"] != "user":
                    continue
                try:
                    self._user_tokens[source["identifier"]] = resolve_token(
                        registry, self.secret_box, source
                    )
                except SecretError:
                    continue  # reported by discovery; do not run it unauthenticated
                users.append(source["identifier"])
            self.status.state["users"] = users
            return users, problems, payload["repository_count"]
        finally:
            registry.close()

    @staticmethod
    def _has_valid_data(stage, user: str) -> bool:
        path = stage / "data" / "users" / slugify_username(user) / "repositories.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return bool(payload.get("repositories"))

    @staticmethod
    def _failure_reason(result: RunResult, user: str) -> str:
        if result.stopped:
            return "stopped during shutdown"
        if result.timed_out:
            return f"{user}: run exceeded the time limit"
        if result.exit_code not in (0, None):
            return f"{user}: collection exited with code {result.exit_code}" + (
                f" ({result.last_error})" if result.last_error else ""
            )
        return f"{user}: no repositories were collected"

    # -- database backup -------------------------------------------------
    def backup_if_due(self) -> Optional[bool]:
        """Take a verified backup when one is due. Returns None if nothing was
        due (or backups are off), else whether it succeeded. A failure is
        published in status.json and retried on the next tick interval, never
        raised: collection must not depend on backups."""
        s = self.settings
        if s.backup_interval_seconds <= 0 or not s.db_path.exists():
            return None
        now = self.now()
        if not self._backup_retry_ready(now) or not backup_due(
            s.backup_dir, s.backup_interval_seconds, now
        ):
            return None
        try:
            info = create_backup(
                s.db_path,
                s.backup_dir,
                keep=s.backup_keep,
                config_path=s.config_path,
                now=now,
            )
        except (BackupError, OSError) as error:
            self._backup_failed_at = now
            self.status.record_backup(
                ok=False,
                at=now,
                interval_seconds=s.backup_interval_seconds,
                reason=f"backup failed: {error}",
            )
            self.log(f"Backup failed: {error}")
            return False
        self._backup_failed_at = None
        self.status.record_backup(
            ok=True,
            at=now,
            interval_seconds=s.backup_interval_seconds,
            sources=info.sources,
            repositories=info.repositories,
        )
        self.log(
            f"Backup ok ({info.sources} sources, {info.repositories} repositories)"
        )
        return True

    def _backup_retry_ready(self, now: datetime) -> bool:
        failed = self._backup_failed_at
        return failed is None or (now - failed).total_seconds() >= BACKUP_RETRY_SECONDS

    # -- scheduling ----------------------------------------------------
    def _refresh_requested(self) -> bool:
        """True once if the admin asked for a refresh (via the database)."""
        path = self.settings.db_path
        if not path.exists():
            return False
        try:
            registry = Registry.open(path)
            try:
                return registry.consume_refresh_requests() > 0
            finally:
                registry.close()
        except Exception:  # noqa: BLE001 - a busy DB must not stop the loop
            return False

    def run_forever(self) -> None:
        s = self.settings
        next_due = (
            self.now()
            if s.run_on_start
            else self.now() + timedelta(seconds=s.interval_seconds)
        )
        self.status.schedule(next_due)
        while not self.stop_event.is_set():
            self.heartbeat()
            self.backup_if_due()
            if self.now() >= next_due or self._refresh_requested():
                self.run_once()
                next_run = self.status.state.get("next_run_at")
                next_due = (
                    datetime.fromisoformat(next_run)
                    if next_run
                    else self.now() + timedelta(seconds=s.interval_seconds)
                )
            self.stop_event.wait(timeout=5)
