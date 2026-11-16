"""Entry point: ``python -m spark.worker [--once | --healthcheck]``."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from spark.worker.loop import CollectionWorker
from spark.worker.settings import SettingsError, WorkerSettings

HEALTHY_HEARTBEAT_SECONDS = 120


def _age_seconds(value, now: datetime):
    try:
        return (now - datetime.fromisoformat(value)).total_seconds()
    except (TypeError, ValueError):
        return None


def health_problem(settings: WorkerSettings, now: Optional[datetime] = None) -> str:
    """Why the worker is unhealthy, or "" when it is healthy.

    Unhealthy means the loop has stalled, collection has not succeeded for two
    intervals (or keeps failing with no success yet), or backups have been
    failing for two backup intervals.
    """
    now = now or datetime.now(timezone.utc)
    try:
        beat = float(settings.heartbeat_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "no worker heartbeat"
    if time.time() - beat >= HEALTHY_HEARTBEAT_SECONDS:
        return "worker loop has stalled"
    try:
        status = json.loads(settings.status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""  # first start: nothing recorded yet
    interval = status.get("interval_seconds") or settings.interval_seconds
    age = _age_seconds(status.get("last_success_at"), now)
    if age is not None and age > 2 * interval + settings.retry_seconds:
        return "no successful collection for over two refresh intervals"
    if age is None and (status.get("consecutive_failures") or 0) >= 3:
        return "collection has failed repeatedly with no success"
    backup = status.get("backup")
    if backup and settings.backup_interval_seconds > 0 and not backup.get("ok"):
        since = _age_seconds(backup.get("last_success_at"), now)
        if since is None or since > 2 * settings.backup_interval_seconds:
            return "database backups are failing"
    return ""


def healthcheck(settings: WorkerSettings) -> int:
    problem = health_problem(settings)
    if problem:
        print(f"unhealthy: {problem}", file=sys.stderr)
    return 1 if problem else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="spark.worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one cycle and exit")
    mode.add_argument(
        "--healthcheck", action="store_true", help="exit 0 if the worker is alive"
    )
    args = parser.parse_args(argv)

    try:
        settings = WorkerSettings.from_env()
    except SettingsError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if args.healthcheck:
        return healthcheck(settings)

    worker = CollectionWorker(settings)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.stop_event.set())

    if args.once:
        return 1 if worker.run_once() == "failed" else 0

    print(
        f"Worker started: users={','.join(settings.users)} "
        f"interval={settings.interval_seconds}s run_on_start={settings.run_on_start}",
        flush=True,
    )
    worker.run_forever()
    print("Worker stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
