"""Backup and restore of the registry database (``python -m spark.backup``).

The registry database holds the sources, portfolio and the accumulating
history, so it is the one thing that cannot be rebuilt from GitHub. Backups
use SQLite's online backup API (safe while the API and worker are running),
are verified before they are kept, and are rotated.

Backups never contain the encryption key. Saved tokens in a backup can only be
read with the same ``SPARK_SECRET_KEY`` that encrypted them, so store that key
separately from the backups.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union

from spark.registry.db import MIGRATIONS, copy_database

_NAME = re.compile(r"^registry-(\d{8}T\d{6}Z)\.db$")
_STAMP = "%Y%m%dT%H%M%SZ"
REQUIRED_TABLES = {"source", "repository", "connection", "admin_user"}


class BackupError(RuntimeError):
    """Raised when a backup or restore cannot be completed safely."""


@dataclass
class BackupInfo:
    path: Path
    created_at: datetime
    schema_version: int
    sources: int
    repositories: int
    size_bytes: int


def verify_backup(path: Union[str, Path]) -> BackupInfo:
    """Open a backup read-only and check it is a usable registry database."""
    path = Path(path)
    if not path.is_file():
        raise BackupError(f"backup not found: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    except sqlite3.Error as error:
        raise BackupError(f"cannot open {path.name}: {error}") from error
    try:
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if check != "ok":
                raise BackupError(f"{path.name} failed its integrity check: {check}")
            missing = REQUIRED_TABLES - tables
            if version < 2 or missing:
                raise BackupError(
                    f"{path.name} is not a usable registry database "
                    f"(schema v{version}, missing {sorted(missing) or 'none'})"
                )
            sources = conn.execute("SELECT COUNT(*) FROM source").fetchone()[0]
            repositories = conn.execute("SELECT COUNT(*) FROM repository").fetchone()[0]
        except sqlite3.DatabaseError as error:
            raise BackupError(
                f"{path.name} is not a valid database: {error}"
            ) from error
    finally:
        conn.close()
    match = _NAME.match(path.name)
    created = (
        datetime.strptime(match.group(1), _STAMP).replace(tzinfo=timezone.utc)
        if match
        else datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    )
    return BackupInfo(
        path, created, version, sources, repositories, path.stat().st_size
    )


def list_backups(backup_dir: Union[str, Path]) -> List[Tuple[Path, datetime]]:
    """Backups in ``backup_dir``, newest first."""
    directory = Path(backup_dir)
    found = []
    if directory.is_dir():
        for entry in directory.iterdir():
            match = _NAME.match(entry.name)
            if match:
                found.append(
                    (
                        entry,
                        datetime.strptime(match.group(1), _STAMP).replace(
                            tzinfo=timezone.utc
                        ),
                    )
                )
    return sorted(found, key=lambda item: item[1], reverse=True)


def latest_backup(backup_dir: Union[str, Path]) -> Optional[Tuple[Path, datetime]]:
    backups = list_backups(backup_dir)
    return backups[0] if backups else None


def backup_due(
    backup_dir: Union[str, Path],
    interval_seconds: int,
    now: Optional[datetime] = None,
) -> bool:
    """True when there is no backup yet or the newest is older than the interval."""
    newest = latest_backup(backup_dir)
    if newest is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - newest[1]).total_seconds() >= interval_seconds


def create_backup(
    db_path: Union[str, Path],
    backup_dir: Union[str, Path],
    *,
    keep: int = 14,
    config_path: Optional[Union[str, Path]] = None,
    now: Optional[datetime] = None,
) -> BackupInfo:
    """Take a verified, rotated backup. A backup that fails verification is
    deleted rather than kept, so a bad file never counts as protection."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.is_file():
        raise BackupError(f"database not found: {db_path}")
    if keep < 1:
        raise BackupError("keep must be at least 1")
    stamp = (now or datetime.now(timezone.utc)).strftime(_STAMP)
    target = backup_dir / f"registry-{stamp}.db"
    try:
        copy_database(db_path, target)
        info = verify_backup(target)
    except (sqlite3.Error, OSError, BackupError) as error:
        target.unlink(missing_ok=True)
        raise BackupError(f"backup failed: {error}") from error
    if config_path and Path(config_path).is_file():
        shutil.copy2(config_path, backup_dir / f"spark-{stamp}.yml")
    _rotate(backup_dir, keep)
    return info


def _rotate(backup_dir: Path, keep: int) -> None:
    for path, _ in list_backups(backup_dir)[keep:]:
        path.unlink(missing_ok=True)
        stamp = _NAME.match(path.name).group(1)
        (backup_dir / f"spark-{stamp}.yml").unlink(missing_ok=True)


def restore_backup(
    backup: Union[str, Path],
    db_path: Union[str, Path],
    *,
    now: Optional[datetime] = None,
) -> Optional[Path]:
    """Replace the database with a verified backup.

    The current database (if any) is first saved beside it as
    ``<name>.before-restore-<time>``. Returns that safety copy's path.
    Stop the api and worker first; restore refuses if the database is in use.
    """
    db_path = Path(db_path)
    info = verify_backup(backup)
    if info.schema_version > len(MIGRATIONS):
        raise BackupError(
            f"backup is schema v{info.schema_version}, newer than this release "
            f"supports (v{len(MIGRATIONS)}); deploy the newer release first"
        )
    safety: Optional[Path] = None
    if db_path.exists():
        guard = sqlite3.connect(str(db_path), timeout=1)
        try:
            guard.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as error:
            raise BackupError(
                "the database is in use; stop the api and worker, then restore"
            ) from error
        finally:
            guard.close()
        stamp = (now or datetime.now(timezone.utc)).strftime(_STAMP)
        safety = db_path.with_name(f"{db_path.name}.before-restore-{stamp}")
        copy_database(db_path, safety)
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    copy_database(info.path, db_path)
    return safety


def _paths(args) -> Tuple[Path, Path, Optional[Path]]:
    env = os.environ
    config = Path(env.get("SPARK_CONFIG_PATH", "/app/config/spark.yml"))
    db = Path(args.db or env.get("SPARK_DB_PATH") or config.parent / "registry.db")
    directory = Path(args.dir or env.get("SPARK_BACKUP_DIR", "/app/backups"))
    return db, directory, config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="spark.backup")
    parser.add_argument("--db", help="registry database (default: SPARK_DB_PATH)")
    parser.add_argument("--dir", help="backup directory (default: SPARK_BACKUP_DIR)")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="take a verified backup now")
    create.add_argument(
        "--keep", type=int, default=int(os.environ.get("SPARK_BACKUP_KEEP", "14"))
    )
    sub.add_parser("list", help="show backups, newest first")
    verify = sub.add_parser("verify", help="check a backup file")
    verify.add_argument("file", type=Path)
    restore = sub.add_parser("restore", help="replace the database from a backup")
    restore.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    db, directory, config = _paths(args)

    try:
        if args.command == "create":
            info = create_backup(db, directory, keep=args.keep, config_path=config)
            print(
                f"created {info.path} ({info.sources} sources, "
                f"{info.repositories} repositories, {info.size_bytes} bytes)"
            )
        elif args.command == "list":
            for path, created in list_backups(directory):
                print(f"{created.isoformat()}  {path}")
        elif args.command == "verify":
            info = verify_backup(args.file)
            print(
                f"ok: schema v{info.schema_version}, {info.sources} sources, "
                f"{info.repositories} repositories"
            )
        else:
            safety = restore_backup(args.file, db)
            print(f"restored {db} from {args.file}")
            if safety:
                print(f"previous database kept at {safety}")
    except BackupError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
