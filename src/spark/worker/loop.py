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

from spark.cli_output_layout import source_slug
from spark.backup import (
    BackupError,
    backup_due,
    create_backup,
    latest_backup,
    verify_backup,
)
from spark.registry import Registry, seed_users
from spark.registry.connections import resolve_token
from spark.registry.secrets import SecretBox, SecretError, load_key
from spark.registry.discovery import run_discovery
from spark.registry.export import write_portfolio
from spark.worker import publish
from spark.worker import security as security_refresh
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
            jobs, problems, portfolio_count = self._refresh_registry(token, stage)
            users = [job["label"] for job in jobs]
            ok_users, failed_users = [], []
            for job in jobs:
                label = job["label"]
                self.log(f"Collecting {label}")
                job_env = dict(env)
                if job["token"]:
                    job_env["GITHUB_TOKEN"] = job["token"]
                result = self.runner(
                    build_command(
                        job["owner"],
                        s.config_path,
                        s.extra_args,
                        slug=job["slug"],
                        repository=job["repository"],
                    ),
                    cwd=stage,
                    env=job_env,
                    timeout_seconds=s.run_timeout_seconds,
                    stop_event=self.stop_event,
                    tick=self.heartbeat,
                )
                errors += result.error_count
                exit_code = result.exit_code
                if result.ok and self._has_valid_data(stage, job["slug"]):
                    ok_users.append(label)
                else:
                    failed_users.append(label)
                    reason = self._failure_reason(result, label) or reason

            if ok_users or (not users and portfolio_count):
                release_id = started.strftime("%Y%m%dT%H%M%SZ")
                publish.publish_tree(stage / "data", s.data_dir, release_id)
                publish.publish_tree(stage / "output", s.output_dir, release_id)
                outcome = (
                    "partial" if (failed_users or errors or problems) else "success"
                )
                if failed_users:
                    reason = f"{len(failed_users)} source(s) failed: " + reason
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

        Returns (dashboards to collect, source problems, portfolio repository count).
        A failing source is recorded on that source and reported; it never
        blocks the others.
        """
        registry = Registry.open(self.settings.registry_path)
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
            jobs = []
            for source in registry.list_sources(enabled_only=True):
                job = self._dashboard_job(registry, source)
                if job:
                    jobs.append(job)
            self.status.state["users"] = [job["label"] for job in jobs]
            return jobs, problems, payload["repository_count"]
        finally:
            registry.close()

    def _dashboard_job(self, registry, source) -> Optional[dict]:
        """One collection run for an enabled source, or None to skip it.

        Users and organizations collect every public repository they own; a
        repository source collects just that repository. Dashboards live under
        ``data/users/<slug>/`` with the slug from ``source_slug``."""
        kind, identifier = source["type"], source["identifier"]
        if kind not in ("user", "org", "repo"):
            return None
        try:
            token = resolve_token(registry, self.secret_box, source)
        except SecretError:
            return None  # reported by discovery; do not run it unauthenticated
        owner, repository = identifier, ""
        if kind == "repo":
            owner, _, repository = identifier.partition("/")
        return {
            "label": identifier,
            "owner": owner,
            "repository": repository,
            "slug": source_slug(kind, identifier),
            "token": token,
        }

    @staticmethod
    def _has_valid_data(stage, slug: str) -> bool:
        path = stage / "data" / "users" / slug / "repositories.json"
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
        if s.backup_interval_seconds <= 0 or not s.registry_path.exists():
            return None
        now = self.now()
        if not self._backup_retry_ready(now) or not backup_due(
            s.backup_dir, s.backup_interval_seconds, now
        ):
            self._publish_existing_backup()
            return None
        try:
            info = create_backup(
                s.registry_path,
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

    def _publish_existing_backup(self) -> None:
        """If status.json has no backup state (a fresh start, or it was written
        by an older release), report the newest existing backup instead of
        staying silent until the next one is due."""
        if self.status.state.get("backup"):
            return
        newest = latest_backup(self.settings.backup_dir)
        if newest is None:
            return
        try:
            info = verify_backup(newest[0])
        except BackupError:
            return  # an unusable file is not evidence of protection
        self.status.record_backup(
            ok=True,
            at=newest[1],
            interval_seconds=self.settings.backup_interval_seconds,
            sources=info.sources,
            repositories=info.repositories,
        )

    def _backup_retry_ready(self, now: datetime) -> bool:
        failed = self._backup_failed_at
        return failed is None or (now - failed).total_seconds() >= BACKUP_RETRY_SECONDS

    # -- Dependabot refresh ----------------------------------------------
    def security_due(self, now: datetime) -> bool:
        """True when no refresh has run yet, or the interval (or, after a
        total failure, the retry delay) has passed since the last attempt."""
        s = self.settings
        if s.security_interval_seconds <= 0 or not s.registry_path.exists():
            return False
        last = self.status.state.get("security") or {}
        attempted = last.get("last_attempt_at")
        if not attempted:
            return True
        try:
            elapsed = (now - datetime.fromisoformat(attempted)).total_seconds()
        except ValueError:
            return True
        wait = (
            min(s.retry_seconds, s.security_interval_seconds)
            if last.get("outcome") in ("failed", "skipped")
            else s.security_interval_seconds
        )
        return elapsed >= wait

    def security_if_due(self, force: bool = False) -> Optional[str]:
        """Refresh Dependabot alerts when due. Returns the outcome, or None if
        nothing was due. Never raises: collection must not depend on it."""
        s = self.settings
        started = self.now()
        if not (force and s.security_interval_seconds > 0) and not self.security_due(
            started
        ):
            return None
        token = os.environ.get("GITHUB_TOKEN", "")
        rate = self.rate_limit_fn(token) if token else None
        if rate and rate["remaining"] < s.min_rate_remaining:
            self.status.record_security(
                at=started,
                outcome="skipped",
                interval_seconds=s.security_interval_seconds,
                reason=f"GitHub rate limit low ({rate['remaining']} remaining)",
            )
            self.log("Dependabot refresh skipped: rate limit low")
            return "skipped"
        try:
            result = security_refresh.refresh_dependabot(
                s,
                self.secret_box,
                token,
                stop_event=self.stop_event,
                log=self.log,
                on_progress=self.heartbeat,
            )
        except Exception as error:  # noqa: BLE001 - the loop must survive anything
            self.status.record_security(
                at=started,
                outcome="failed",
                interval_seconds=s.security_interval_seconds,
                reason=f"{type(error).__name__}: {error}",
            )
            self.log(f"Dependabot refresh failed: {error}")
            return "failed"
        self.status.record_security(
            at=started,
            outcome=result.outcome,
            interval_seconds=s.security_interval_seconds,
            checked=result.checked,
            read=result.read,
            open_alerts=result.open_alerts,
            reason=result.stopped_reason
            or (
                f"{result.checked - result.read} repositories could not be read"
                if result.read < result.checked
                else ""
            ),
        )
        return result.outcome

    # -- scheduling ----------------------------------------------------
    def _refresh_requested(self) -> bool:
        """True once if the admin asked for a refresh (via the database)."""
        path = self.settings.registry_path
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
            requested = self._refresh_requested()
            if self.now() >= next_due or requested:
                self.run_once()
                self.security_if_due(force=requested)
                next_run = self.status.state.get("next_run_at")
                next_due = (
                    datetime.fromisoformat(next_run)
                    if next_run
                    else self.now() + timedelta(seconds=s.interval_seconds)
                )
            else:
                self.security_if_due()
            self.stop_event.wait(timeout=5)
