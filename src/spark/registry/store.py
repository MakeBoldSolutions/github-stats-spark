"""Registry operations: sources, repositories and portfolio associations."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from spark.registry.db import connect

SOURCE_TYPES = ("org", "user", "repo")
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class RegistryError(ValueError):
    """Raised for invalid registry input or a missing record."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_identifier(source_type: str, identifier: str) -> str:
    """Validate and normalize a source identifier (``owner`` or ``owner/repo``)."""
    if source_type not in SOURCE_TYPES:
        raise RegistryError(f"source type must be one of {', '.join(SOURCE_TYPES)}")
    value = (identifier or "").strip().strip("/")
    if source_type == "repo":
        owner, _, name = value.partition("/")
        if not (_OWNER.match(owner) and _REPO.match(name) and "/" not in name):
            raise RegistryError(f"repository must look like owner/name (got {value!r})")
    elif not _OWNER.match(value):
        raise RegistryError(f"{source_type} must be a GitHub login (got {value!r})")
    return value


class Registry:
    """Thin, explicit data-access layer over the registry database."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def open(cls, path: Union[str, Path]) -> "Registry":
        return cls(connect(path))

    def close(self) -> None:
        self.conn.close()

    # -- sources --------------------------------------------------------
    def add_source(
        self,
        source_type: str,
        identifier: str,
        *,
        client: Optional[str] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Register a source; adding an existing one returns it unchanged."""
        identifier = normalize_identifier(source_type, identifier)
        existing = self.find_source(source_type, identifier)
        if existing:
            return existing
        client_id = self._client_id(client, create=True) if client else None
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO source (type, identifier, enabled, client_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (source_type, identifier, int(enabled), client_id, now_iso()),
            )
        return self.get_source(cursor.lastrowid)

    def find_source(self, source_type: str, identifier: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM source WHERE type = ? AND identifier = ? COLLATE NOCASE",
            (source_type, identifier),
        ).fetchone()
        return dict(row) if row else None

    def get_source(self, source_id: int) -> Dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM source WHERE id = ?", (source_id,)
        ).fetchone()
        if not row:
            raise RegistryError(f"no source with id {source_id}")
        return dict(row)

    def list_sources(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM source"
        if enabled_only:
            sql += " WHERE enabled = 1"
        return [dict(r) for r in self.conn.execute(sql + " ORDER BY type, identifier")]

    def set_source_enabled(self, source_id: int, enabled: bool) -> None:
        self.get_source(source_id)
        with self.conn:
            self.conn.execute(
                "UPDATE source SET enabled = ? WHERE id = ?", (int(enabled), source_id)
            )

    def remove_source(self, source_id: int) -> None:
        """Remove a source and its links. Repositories are kept (see prune)."""
        self.get_source(source_id)
        with self.conn:
            self.conn.execute("DELETE FROM source WHERE id = ?", (source_id,))

    def record_source_status(
        self,
        source_id: int,
        state: str,
        *,
        repository_count: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        discovered: bool = False,
    ) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE source SET state = ?, error_code = ?, error_message = ?,"
                " repository_count = COALESCE(?, repository_count),"
                " last_discovery_at = CASE WHEN ? THEN ? ELSE last_discovery_at END"
                " WHERE id = ?",
                (
                    state,
                    error_code,
                    error_message,
                    repository_count,
                    int(discovered),
                    now_iso(),
                    source_id,
                ),
            )

    # -- repositories ---------------------------------------------------
    def upsert_repository(self, source_id: int, repo: Dict[str, Any]) -> int:
        """Insert or refresh a repository (deduped by case-insensitive name)
        and record that ``source_id`` reaches it."""
        full_name = repo["full_name"]
        owner, _, name = full_name.partition("/")
        stamp = now_iso()
        values = (
            owner,
            name,
            repo.get("description"),
            repo.get("language"),
            repo.get("html_url"),
            repo.get("default_branch"),
            repo.get("pushed_at"),
            int(bool(repo.get("is_fork"))),
            int(bool(repo.get("is_private"))),
            int(bool(repo.get("is_archived"))),
        )
        with self.conn:
            self.conn.execute(
                "INSERT INTO repository (full_name, full_name_lower, owner, name,"
                " description, language, html_url, default_branch, pushed_at,"
                " is_fork, is_private, is_archived, first_seen_at, last_seen_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(full_name_lower) DO UPDATE SET"
                " full_name = excluded.full_name, owner = excluded.owner,"
                " name = excluded.name, description = excluded.description,"
                " language = excluded.language, html_url = excluded.html_url,"
                " default_branch = excluded.default_branch,"
                " pushed_at = excluded.pushed_at, is_fork = excluded.is_fork,"
                " is_private = excluded.is_private,"
                " is_archived = excluded.is_archived,"
                " last_seen_at = excluded.last_seen_at",
                (full_name, full_name.lower(), *values, stamp, stamp),
            )
            repo_id = self.conn.execute(
                "SELECT id FROM repository WHERE full_name_lower = ?",
                (full_name.lower(),),
            ).fetchone()[0]
            self.conn.execute(
                "INSERT OR IGNORE INTO repository_source VALUES (?, ?)",
                (repo_id, source_id),
            )
        return repo_id

    def sync_source_links(self, source_id: int, seen_ids: Iterable[int]) -> int:
        """After a *complete* listing, drop links to repositories the source no
        longer returns. Repositories themselves are never deleted here."""
        seen = set(seen_ids)
        rows = self.conn.execute(
            "SELECT repository_id FROM repository_source WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        stale = [r[0] for r in rows if r[0] not in seen]
        with self.conn:
            self.conn.executemany(
                "DELETE FROM repository_source WHERE source_id = ? AND repository_id = ?",
                [(source_id, rid) for rid in stale],
            )
        return len(stale)

    def set_repository_excluded(self, full_name: str, excluded: bool) -> None:
        cursor = self.conn.execute(
            "UPDATE repository SET excluded = ? WHERE full_name_lower = ?",
            (int(excluded), full_name.lower()),
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            raise RegistryError(f"unknown repository {full_name!r}")

    def list_repositories(self, include_excluded: bool = True) -> List[Dict[str, Any]]:
        sql = (
            "SELECT r.*, c.name AS client, p.name AS project, a.name AS application"
            " FROM repository r"
            " LEFT JOIN client c ON c.id = r.client_id"
            " LEFT JOIN project p ON p.id = r.project_id"
            " LEFT JOIN application a ON a.id = r.application_id"
        )
        if not include_excluded:
            sql += " WHERE r.excluded = 0"
        out = []
        for row in self.conn.execute(sql + " ORDER BY r.full_name_lower"):
            item = dict(row)
            item["sources"] = [
                dict(s)
                for s in self.conn.execute(
                    "SELECT s.id, s.type, s.identifier FROM repository_source rs"
                    " JOIN source s ON s.id = rs.source_id"
                    " WHERE rs.repository_id = ? ORDER BY s.type, s.identifier",
                    (row["id"],),
                )
            ]
            out.append(item)
        return out

    def prune_orphans(self) -> int:
        """Explicit admin action: delete repositories no source reaches."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM repository WHERE id NOT IN"
                " (SELECT repository_id FROM repository_source)"
            )
        return cursor.rowcount

    # -- portfolio ------------------------------------------------------
    def _client_id(self, name: Optional[str], create: bool = False) -> Optional[int]:
        if not name:
            return None
        row = self.conn.execute(
            "SELECT id FROM client WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row[0]
        if not create:
            raise RegistryError(f"unknown client {name!r}")
        with self.conn:
            return self.conn.execute(
                "INSERT INTO client (name, created_at) VALUES (?, ?)", (name, now_iso())
            ).lastrowid

    def associate_repository(
        self,
        full_name: str,
        *,
        client: Optional[str] = None,
        project: Optional[str] = None,
        application: Optional[str] = None,
    ) -> None:
        """Link a repository to a client/project/application (all optional;
        names are created on first use). Unassigned repositories are valid."""
        row = self.conn.execute(
            "SELECT id FROM repository WHERE full_name_lower = ?", (full_name.lower(),)
        ).fetchone()
        if not row:
            raise RegistryError(f"unknown repository {full_name!r}")
        client_id = self._client_id(client, create=True)
        project_id = application_id = None
        with self.conn:
            if project:
                found = self.conn.execute(
                    "SELECT id FROM project WHERE name = ? AND client_id IS ?",
                    (project, client_id),
                ).fetchone()
                project_id = (
                    found[0]
                    if found
                    else self.conn.execute(
                        "INSERT INTO project (client_id, name, created_at)"
                        " VALUES (?, ?, ?)",
                        (client_id, project, now_iso()),
                    ).lastrowid
                )
            if application:
                found = self.conn.execute(
                    "SELECT id FROM application WHERE name = ? AND project_id IS ?",
                    (application, project_id),
                ).fetchone()
                application_id = (
                    found[0]
                    if found
                    else self.conn.execute(
                        "INSERT INTO application"
                        " (client_id, project_id, name, created_at)"
                        " VALUES (?, ?, ?, ?)",
                        (client_id, project_id, application, now_iso()),
                    ).lastrowid
                )
            self.conn.execute(
                "UPDATE repository SET client_id = ?, project_id = ?,"
                " application_id = ? WHERE id = ?",
                (client_id, project_id, application_id, row[0]),
            )

    # -- collected data -------------------------------------------------
    def record_observation(
        self,
        subject: str,
        kind: str,
        value: Any,
        source: str,
        client_id: Optional[int] = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO observation (subject, kind, value, source, client_id,"
                " observed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (subject, kind, str(value), source, client_id, now_iso()),
            )
