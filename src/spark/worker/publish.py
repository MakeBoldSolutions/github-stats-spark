"""Atomic publication of generated trees into a served volume.

Each run's output is copied into ``<volume>/.releases/<release_id>/`` and the
served top-level entries (for example ``users``) are symlinks that are swapped
with ``os.replace`` - an atomic rename - so readers see either the previous
complete dataset or the new one, never a half-written tree. A failed run
never calls this, so the last good data stays served.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

RELEASES_DIR = ".releases"
KEEP_RELEASES = 2


def _served_entries(root: Path) -> List[Path]:
    return sorted(p for p in root.iterdir() if not p.name.startswith("."))


def seed_stage(published: Path, stage: Path, skip: tuple = ("status.json",)) -> None:
    """Copy the currently published tree into ``stage``.

    Keeps data for users/entries this run does not regenerate.
    """
    stage.mkdir(parents=True, exist_ok=True)
    if not published.exists():
        return
    for entry in _served_entries(published):
        if entry.name in skip:
            continue
        target = stage / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def publish_tree(stage: Path, volume: Path, release_id: str) -> List[str]:
    """Publish every top-level entry of ``stage`` into ``volume``.

    Returns the names published.
    """
    release_root = volume / RELEASES_DIR / release_id
    published: List[str] = []
    for entry in _served_entries(stage):
        release_root.mkdir(parents=True, exist_ok=True)
        target = release_root / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target)
        else:
            shutil.copy2(entry, target)

        link = volume / entry.name
        if link.exists() and not link.is_symlink():
            # One-time migration of a pre-release layout (a real directory):
            # keep its content as a release so it can still be rolled back to.
            legacy = volume / RELEASES_DIR / f"legacy-{release_id}"
            legacy.mkdir(parents=True, exist_ok=True)
            os.replace(link, legacy / entry.name)
        tmp_link = volume / f".{entry.name}.tmp-{release_id}"
        if tmp_link.is_symlink() or tmp_link.exists():
            tmp_link.unlink()
        os.symlink(Path(RELEASES_DIR) / release_id / entry.name, tmp_link)
        _swap_link(tmp_link, link)
        published.append(entry.name)

    prune_releases(volume)
    return published


def _swap_link(tmp_link: Path, link: Path) -> None:
    """Atomically point ``link`` at ``tmp_link``'s target (POSIX rename)."""
    try:
        os.replace(tmp_link, link)
    except PermissionError:
        # Windows cannot rename over a directory symlink. Production runs on
        # Linux, where the branch above is atomic; this keeps dev/tests working.
        if os.name != "nt":
            raise
        os.rmdir(link)
        os.rename(tmp_link, link)


def prune_releases(volume: Path, keep: int = KEEP_RELEASES) -> None:
    """Delete old releases, always keeping any a served link points to."""
    releases = volume / RELEASES_DIR
    if not releases.is_dir():
        return
    in_use = set()
    for entry in volume.iterdir():
        if entry.is_symlink():
            parts = Path(os.readlink(entry)).parts
            if len(parts) >= 2 and parts[0] == RELEASES_DIR:
                in_use.add(parts[1])
    ordered = sorted(p.name for p in releases.iterdir() if p.is_dir())
    for name in ordered[: max(0, len(ordered) - keep)]:
        if name not in in_use:
            shutil.rmtree(releases / name, ignore_errors=True)
