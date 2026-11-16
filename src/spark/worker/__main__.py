"""Entry point: ``python -m spark.worker [--once | --healthcheck]``."""

from __future__ import annotations

import argparse
import signal
import sys
import time

from spark.worker.loop import CollectionWorker
from spark.worker.settings import SettingsError, WorkerSettings

HEALTHY_HEARTBEAT_SECONDS = 120


def healthcheck(settings: WorkerSettings) -> int:
    """Healthy when the worker loop has beaten recently."""
    try:
        beat = float(settings.heartbeat_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    return 0 if time.time() - beat < HEALTHY_HEARTBEAT_SECONDS else 1


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
