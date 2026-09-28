"""API response caching with hierarchical storage and smart invalidation.

# SIZE JUSTIFICATION (Constitution I — ~528 LOC as of 2026-04-02):
# Content-addressed cache storage, directory hierarchy management, read/write
# helpers, and the pushed_at-based invalidation logic share internal path
# constants and serialization helpers that would require duplication or a
# shared internal package if split.  The module is a proven-stable utility
# with no recent growth trend; splitting is deferred until a clear boundary
# emerges.
"""

from __future__ import annotations

import json
import os
import shutil
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Dict, List

from spark.config import SparkConfig


class _CacheFileLock:
    """Cross-platform file lock to coordinate cache access."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._handle = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Binary append avoids truncation
        self._handle = open(self.lock_path, "a+b")
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb):
        if not self._handle:
            return False
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            try:
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl

            try:
                fcntl.flock(self._handle, fcntl.LOCK_UN)
            except OSError:
                pass
        self._handle.close()
        self._handle = None
        return False


class CacheManifest:
    """Manages the cache index file for quick lookups."""

    def __init__(self, cache_dir: Path):
        self.manifest_path = cache_dir / "index.json"
        self.data: Dict[str, Any] = {"entries": {}}
        self._dirty = False
        self._last_mtime = 0

    def load(self):
        """Load manifest from disk."""
        if self.manifest_path.exists():
            try:
                mtime = self.manifest_path.stat().st_mtime
                if mtime > self._last_mtime:
                    with open(self.manifest_path, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    self._last_mtime = mtime
            except (json.JSONDecodeError, OSError):
                # If corrupt, start fresh
                self.data = {"entries": {}}

    def save(self):
        """Save manifest to disk if modified."""
        if self._dirty:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            self._dirty = False
            try:
                self._last_mtime = self.manifest_path.stat().st_mtime
            except OSError:
                pass

    def update_entry(self, key: str, week: str):
        """Update an entry in the manifest."""
        if key not in self.data["entries"]:
            self.data["entries"][key] = {
                "latest_week": week,
                "weeks": [week],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._dirty = True
        else:
            entry = self.data["entries"][key]
            if week not in entry["weeks"]:
                entry["weeks"].append(week)
                entry["weeks"].sort(reverse=True)  # Keep newest first
                self._dirty = True

            if entry.get("latest_week") != week:
                # Only update latest_week if the new one is "newer" or we just treat the last written as latest?
                # For now, let's assume the caller knows what they are doing.
                # But usually we want the lexically largest week (e.g. 2026W02 > 2026W01)
                if week > entry.get("latest_week", ""):
                    entry["latest_week"] = week
                    self._dirty = True

            entry["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_entry(self, key: str) -> Optional[Dict[str, Any]]:
        return self.data["entries"].get(key)

    def remove_week(self, key: str, week: str):
        """Remove a week from an entry."""
        if key in self.data["entries"]:
            entry = self.data["entries"][key]
            if week in entry["weeks"]:
                entry["weeks"].remove(week)
                self._dirty = True
                # If we removed the latest week, update it
                if entry["latest_week"] == week:
                    entry["latest_week"] = entry["weeks"][0] if entry["weeks"] else None

            if not entry["weeks"]:
                del self.data["entries"][key]
                self._dirty = True


class APICache:
    """Manages cached API responses with repository-aware invalidation."""

    def __init__(self, cache_dir: str = ".cache", config: Optional[SparkConfig] = None):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files
            config: SparkConfig instance for configuration
        """
        env_cache_dir = os.getenv("SPARK_CACHE_DIR")
        self.cache_dir = Path(env_cache_dir or cache_dir)
        self.config = config or SparkConfig()
        # Ensure config is loaded if passed empty
        if not self.config.config and Path("config/spark.yml").exists():
            self.config.load()

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.cache_dir / ".cache.lock"
        self.logger = logging.getLogger(__name__)

        self.manifest = CacheManifest(self.cache_dir)
        with self._acquire_lock():
            self.manifest.load()

    def _acquire_lock(self):
        return _CacheFileLock(self._lock_path)

    def _get_key_path(self, category: str, owner: str, repo: Optional[str]) -> str:
        """Generate the logical key for manifest lookup."""
        if repo:
            return f"{owner}/{repo}/{category}"
        return f"{owner}/_global_/{category}"

    def _get_fs_path(
        self, category: str, owner: str, repo: Optional[str], week: str
    ) -> Path:
        """Generate the filesystem path."""
        if repo:
            return self.cache_dir / owner / repo / category / f"{week}.json"
        return self.cache_dir / owner / "_global_" / category / f"{week}.json"

    def _calculate_hash(self, data: Any) -> str:
        """Calculate SHA256 hash of the data."""
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(
        self,
        category: str,
        owner: str,
        repo: Optional[str] = None,
        week: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieve a cached value.

        Args:
            category: Cache category
            owner: Repository owner
            repo: Repository name (optional)
            week: Specific week to retrieve (optional, defaults to latest)

        Returns:
            Cached value or None
        """
        key = self._get_key_path(category, owner, repo)

        with self._acquire_lock():
            self.manifest.load()
            # If week not specified, look up latest in manifest
            if not week:
                entry = self.manifest.get_entry(key)
                if not entry or not entry.get("latest_week"):
                    return None
                week = entry["latest_week"]

            cache_path = self._get_fs_path(category, owner, repo, week)

            if not cache_path.exists():
                return None

            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                self.logger.warning(f"Corrupt cache file {cache_path}: {exc}")
                try:
                    cache_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None

            # Integrity check
            stored_hash = data.get("hash")
            value = data.get("value")
            if stored_hash:
                current_hash = self._calculate_hash(value)
                if current_hash != stored_hash:
                    self.logger.error(f"Cache integrity failure for {cache_path}")
                    try:
                        cache_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return None

            # No TTL check - cache is valid until data changes on GitHub
            # Higher-level logic (cache_status.py) compares pushed_at timestamps
            # to determine if refresh is needed

            return value

    def has_entry(
        self,
        category: str,
        owner: str,
        repo: Optional[str] = None,
        week: Optional[str] = None,
    ) -> bool:
        """Check if a cache entry exists."""
        key = self._get_key_path(category, owner, repo)
        with self._acquire_lock():
            self.manifest.load()
            entry = self.manifest.get_entry(key)
            if not entry:
                return False
            if week:
                return week in entry.get("weeks", [])
            return bool(entry.get("latest_week"))

    def get_entry_info(
        self, category: str, owner: str, repo: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get info about a cache entry from manifest."""
        key = self._get_key_path(category, owner, repo)
        with self._acquire_lock():
            self.manifest.load()
            return self.manifest.get_entry(key)

    def set(
        self,
        category: str,
        owner: str,
        value: Any,
        repo: Optional[str] = None,
        week: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a value in the cache."""
        if week is None:
            # For user-level data (repositories list, user profile), use a simple default
            # For repo-specific data, week should ALWAYS be provided based on repo_pushed_at
            if repo and not repo.startswith("list_"):
                # This is repo-specific data - week parameter is required
                raise ValueError(
                    f"week parameter is required for repo-specific data (category: {category}, repo: {repo}). Cache keys must be based on repo_pushed_at, not time-based."
                )

            # User-level data: use a simple cache key (refreshed when list changes)
            week = "current"

        key = self._get_key_path(category, owner, repo)
        cache_path = self._get_fs_path(category, owner, repo, week)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": value,
            "hash": self._calculate_hash(value),
            "metadata": metadata or {},
            "category": category,
            "owner": owner,
            "repo": repo,
            "week": week,
        }

        with self._acquire_lock():
            self.manifest.load()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Atomic write
                import tempfile

                with tempfile.NamedTemporaryFile(
                    "w", delete=False, dir=self.cache_dir, encoding="utf-8"
                ) as tmp:
                    json.dump(payload, tmp, indent=2)
                    temp_name = tmp.name

                # Move to final location
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                shutil.move(temp_name, cache_path)

                # Update manifest
                self.manifest.update_entry(key, week)
                self.manifest.save()

            except Exception as exc:
                self.logger.error(f"Failed to write cache file {cache_path}: {exc}")
                if "temp_name" in locals() and os.path.exists(temp_name):
                    os.remove(temp_name)
                raise

    def prune(self, keep_weeks: int = 2):
        """Prune old cache entries."""
        self.logger.info("Running cache janitor...")

        with self._acquire_lock():
            # Reload manifest to be safe
            self.manifest.load()

            for key, entry in self.manifest.data["entries"].items():
                weeks = entry.get("weeks", [])
                if len(weeks) > keep_weeks:
                    # Sort weeks descending
                    weeks.sort(reverse=True)
                    weeks[:keep_weeks]
                    weeks_to_remove = weeks[keep_weeks:]

                    parts = key.split("/")
                    if len(parts) == 3:
                        owner, repo, category = parts
                        if repo == "_global_":
                            repo = None
                    else:
                        continue

                    for week in weeks_to_remove:
                        path = self._get_fs_path(category, owner, repo, week)
                        try:
                            if path.exists():
                                path.unlink()
                            self.manifest.remove_week(key, week)
                        except OSError as e:
                            self.logger.warning(f"Failed to delete {path}: {e}")

            self.manifest.save()

    def clear(self) -> None:
        """Clear all cached values."""
        with self._acquire_lock():
            # Remove all files in cache dir except lock and index?
            # Or just recreate the dir
            for item in self.cache_dir.iterdir():
                if item.name == ".cache.lock":
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except OSError as e:
                    self.logger.warning(f"Failed to delete {item}: {e}")

            # Reset manifest
            self.manifest.data = {"entries": {}}
            self.manifest.save()

    def clear_repository_cache(self, username: str, repo_name: str) -> int:
        """Clear all cache entries related to a specific repository."""
        count = 0
        repo_dir = self.cache_dir / username / repo_name

        with self._acquire_lock():
            self.manifest.load()
            if repo_dir.exists():
                # Count files
                for _ in repo_dir.rglob("*.json"):
                    count += 1
                shutil.rmtree(repo_dir)

                # Update manifest
                keys_to_remove = []
                prefix = f"{username}/{repo_name}/"
                for key in self.manifest.data["entries"]:
                    if key.startswith(prefix):
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    del self.manifest.data["entries"][key]

                if keys_to_remove:
                    self.manifest._dirty = True
                    self.manifest.save()

        return count

    def collect_garbage(
        self, owner: str, active_repo_names: List[str]
    ) -> Dict[str, Any]:
        """Remove cache entries for repositories that no longer exist.

        Compares cached repository directories against the current list of
        active repositories from the GitHub API. Removes orphaned cache
        directories (e.g., from renamed or deleted repos) and their manifest
        entries.

        Args:
            owner: Repository owner/username
            active_repo_names: List of current repository names from GitHub API

        Returns:
            Dict with 'removed_repos' list and 'removed_files' count
        """
        active_set = set(active_repo_names)
        owner_dir = self.cache_dir / owner
        result: Dict[str, Any] = {"removed_repos": [], "removed_files": 0}

        if not owner_dir.exists():
            return result

        with self._acquire_lock():
            self.manifest.load()

            for repo_dir in sorted(owner_dir.iterdir()):
                if not repo_dir.is_dir():
                    continue
                repo_name = repo_dir.name
                # Skip the _global_ pseudo-directory (user-level caches)
                if repo_name == "_global_":
                    continue
                if repo_name not in active_set:
                    # Count files before removal
                    file_count = sum(1 for _ in repo_dir.rglob("*.json"))
                    try:
                        shutil.rmtree(repo_dir)
                        self.logger.info(
                            f"Cache GC: removed orphaned cache for '{repo_name}' "
                            f"({file_count} files)"
                        )
                        result["removed_repos"].append(repo_name)
                        result["removed_files"] += file_count
                    except OSError as e:
                        self.logger.warning(
                            f"Cache GC: failed to remove '{repo_name}': {e}"
                        )
                        continue

                    # Clean manifest entries for this repo
                    prefix = f"{owner}/{repo_name}/"
                    keys_to_remove = [
                        k for k in self.manifest.data["entries"] if k.startswith(prefix)
                    ]
                    for key in keys_to_remove:
                        del self.manifest.data["entries"][key]
                    if keys_to_remove:
                        self.manifest._dirty = True

            if self.manifest._dirty:
                self.manifest.save()

        if result["removed_repos"]:
            self.logger.info(
                f"Cache GC complete: removed {len(result['removed_repos'])} orphaned repos, "
                f"{result['removed_files']} files"
            )
        else:
            self.logger.info("Cache GC: no orphaned repositories found")

        return result

    def migrate_ai_summary_cache_keys(self) -> Dict[str, int]:
        """Migrate ai_summary cache keys from timestamp_hash to timestamp-only."""
        results = {
            "moved": 0,
            "skipped_exists": 0,
            "missing": 0,
            "errors": 0,
        }

        with self._acquire_lock():
            self.manifest.load()

            for key, entry in list(self.manifest.data["entries"].items()):
                if not key.endswith("/ai_summary"):
                    continue

                parts = key.split("/")
                if len(parts) != 3:
                    continue

                owner, repo, category = parts
                repo_name = None if repo == "_global_" else repo
                weeks = list(entry.get("weeks", []))

                for week in weeks:
                    if "_" not in week:
                        continue
                    new_week = week.rsplit("_", 1)[0]
                    if new_week == week:
                        continue

                    old_path = self._get_fs_path(category, owner, repo_name, week)
                    new_path = self._get_fs_path(category, owner, repo_name, new_week)

                    try:
                        if not old_path.exists():
                            results["missing"] += 1
                            self.manifest.remove_week(key, week)
                            continue

                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        if new_path.exists():
                            results["skipped_exists"] += 1
                            old_path.unlink(missing_ok=True)
                            self.manifest.remove_week(key, week)
                            continue

                        os.replace(old_path, new_path)
                        results["moved"] += 1
                        self.manifest.update_entry(key, new_week)
                        self.manifest.remove_week(key, week)
                    except OSError:
                        results["errors"] += 1

            self.manifest.save()

        return results
