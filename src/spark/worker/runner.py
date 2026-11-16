"""Run one ``spark unified`` collection as a bounded subprocess."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Mapping, Optional

from spark.worker.status import sanitize

_ERROR_LINE = re.compile(r"\]\s+(ERROR|CRITICAL)\b")


@dataclass
class RunResult:
    exit_code: Optional[int]
    error_count: int = 0
    last_error: str = ""
    timed_out: bool = False
    stopped: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.stopped


def build_command(
    user: str,
    config_path: Path,
    extra_args: List[str],
    slug: str = "",
    repository: str = "",
) -> List[str]:
    """Command for one dashboard: a user or organization (``user`` is the
    login) or a single repository (``user`` is the owner, ``repository`` its
    name). ``slug`` names the output folder when it differs from the login."""
    command = [
        sys.executable,
        "-m",
        "spark.cli",
        "unified",
        "--user",
        user,
        "--config",
        str(config_path),
    ]
    if slug:
        command += ["--slug", slug]
    if repository:
        command += ["--repository", repository]
    return [*command, *extra_args]


def run_collection(
    command: List[str],
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: int,
    stop_event: threading.Event,
    tick: Callable[[], None] = lambda: None,
    emit: Callable[[str], None] = lambda line: print(line, flush=True),
) -> RunResult:
    """Run ``command`` in ``cwd``, streaming its log, bounded by a timeout.

    Counts ERROR/CRITICAL log lines so a run that finishes with errors can be
    reported as partial. ``stop_event`` terminates the child for shutdown.
    """
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    result = RunResult(exit_code=None)

    def read_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
            emit(line)
            if _ERROR_LINE.search(line):
                result.error_count += 1
                result.last_error = sanitize(line.split("]", 2)[-1])

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None:
        if stop_event.is_set():
            result.stopped = True
            process.terminate()
            break
        if time.monotonic() > deadline:
            result.timed_out = True
            process.terminate()
            break
        tick()
        time.sleep(1)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    reader.join(timeout=5)
    result.exit_code = process.returncode
    return result
