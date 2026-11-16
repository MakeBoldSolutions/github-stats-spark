"""Environment-driven settings for the collection worker."""

from __future__ import annotations

import os
import re
import shlex
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Mapping, Optional

_DURATION = re.compile(r"^\s*(\d+)\s*([smhd]?)\s*$", re.IGNORECASE)
_UNITS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}
MIN_INTERVAL_SECONDS = 60


class SettingsError(ValueError):
    """Raised when worker configuration is invalid."""


def parse_duration(value: str, name: str = "duration") -> int:
    """Parse ``90``, ``30m``, ``6h`` or ``1d`` into seconds."""
    match = _DURATION.match(value or "")
    if not match:
        raise SettingsError(f"{name} must look like 30m, 6h or 1d (got {value!r})")
    return int(match.group(1)) * _UNITS[match.group(2).lower()]


def _backup_interval(value: Optional[str]) -> int:
    """Seconds between backups; ``off`` (or 0) disables scheduled backups."""
    if value is None or value.strip() == "":
        return 24 * 3600
    if value.strip().lower() in {"off", "false", "no", "0"}:
        return 0
    return max(3600, parse_duration(value, "SPARK_BACKUP_INTERVAL"))


def _flag(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class WorkerSettings:
    users: List[str]
    interval_seconds: int = 6 * 3600
    run_on_start: bool = True
    run_timeout_seconds: int = 2 * 3600
    retry_seconds: int = 30 * 60
    min_rate_remaining: int = 300
    data_dir: Path = Path("/app/data")
    output_dir: Path = Path("/app/output")
    config_path: Path = Path("/app/config/spark.yml")
    cache_dir: Path = Path("/app/.cache")
    stage_dir: Path = field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "spark-stage"
    )
    extra_args: List[str] = field(default_factory=list)
    db_path: Optional[Path] = None
    backup_dir: Path = Path("/app/backups")
    backup_interval_seconds: int = 24 * 3600  # 0 disables scheduled backups
    backup_keep: int = 14

    def __post_init__(self) -> None:
        if self.db_path is None:
            self.db_path = self.config_path.parent / "registry.db"

    @property
    def heartbeat_path(self) -> Path:
        return self.cache_dir / ".worker-heartbeat"

    @property
    def status_path(self) -> Path:
        return self.data_dir / "status.json"

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "WorkerSettings":
        env = os.environ if env is None else env
        users = [u.strip() for u in env.get("SPARK_USER", "").split(",") if u.strip()]
        if not users:
            raise SettingsError("SPARK_USER must name at least one GitHub user")

        interval = parse_duration(
            env.get("SPARK_REFRESH_INTERVAL", "6h"), "SPARK_REFRESH_INTERVAL"
        )
        if interval < MIN_INTERVAL_SECONDS:
            raise SettingsError(
                f"SPARK_REFRESH_INTERVAL must be at least {MIN_INTERVAL_SECONDS}s"
            )
        retry = parse_duration(env.get("SPARK_RETRY_DELAY", "30m"), "SPARK_RETRY_DELAY")
        settings = cls(
            users=users,
            interval_seconds=interval,
            run_on_start=_flag(env.get("SPARK_RUN_ON_START"), True),
            run_timeout_seconds=parse_duration(
                env.get("SPARK_RUN_TIMEOUT", "2h"), "SPARK_RUN_TIMEOUT"
            ),
            retry_seconds=min(interval, retry),
            min_rate_remaining=int(env.get("SPARK_MIN_RATE_REMAINING", "300")),
            data_dir=Path(env.get("SPARK_DATA_DIR", "/app/data")),
            output_dir=Path(env.get("SPARK_OUTPUT_DIR", "/app/output")),
            config_path=Path(env.get("SPARK_CONFIG_PATH", "/app/config/spark.yml")),
            cache_dir=Path(env.get("SPARK_CACHE_DIR", "/app/.cache")),
            extra_args=shlex.split(env.get("SPARK_EXTRA_ARGS", "")),
            db_path=Path(env["SPARK_DB_PATH"]) if env.get("SPARK_DB_PATH") else None,
            backup_dir=Path(env.get("SPARK_BACKUP_DIR", "/app/backups")),
            backup_interval_seconds=_backup_interval(env.get("SPARK_BACKUP_INTERVAL")),
            backup_keep=max(1, int(env.get("SPARK_BACKUP_KEEP", "14"))),
        )
        if env.get("SPARK_STAGE_DIR"):
            settings.stage_dir = Path(env["SPARK_STAGE_DIR"])
        return settings
