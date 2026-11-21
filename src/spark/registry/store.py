"""Registry operations: sources, repositories and portfolio associations.

SIZE JUSTIFICATION (Constitution I): this is the single data-access class the
API, worker and CLI share. Managed lists live in ``catalog``, classification in
``domains``, and tokens in ``connections``; what remains is core record access
plus the Dependabot upserts, which share its transactions.
"""

from __future__ import annotations

import json
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


class NotFoundError(RegistryError):
    """The record named by an id or repository name does not exist."""


class UnknownNameError(RegistryError):
    """A client, project or application name that is not in its managed list
    (or is retired). Names are never created as a side effect of assignment."""


def inserted_id(cursor: sqlite3.Cursor) -> int:
    """The row id from an INSERT; sqlite3 types it Optional, but an INSERT sets it."""
    if cursor.lastrowid is None:  # pragma: no cover - only after a non-INSERT
        raise RegistryError("INSERT did not produce a row id")
    return cursor.lastrowid


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
        client_id = self.client_id_for(client)
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO source (type, identifier, enabled, client_id, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (source_type, identifier, int(enabled), client_id, now_iso()),
            )
        return self.get_source(inserted_id(cursor))

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
            raise NotFoundError(f"no source with id {source_id}")
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
            raise NotFoundError(f"unknown repository {full_name!r}")

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
    def client_id_for(
        self, name: Optional[str], *, current: Optional[int] = None
    ) -> Optional[int]:
        """Id of an active client by name; ``current`` may stay even if retired."""
        return self._resolve("client", name, None, None, current)

    def _resolve(
        self,
        table: str,
        name: Optional[str],
        parent_column: Optional[str],
        parent_id: Optional[int],
        current: Optional[int],
    ) -> Optional[int]:
        """Look a managed name up; never create it. A retired entry is only
        accepted when it is what the record already uses."""
        if not name:
            return None
        sql = f"SELECT id, retired_at FROM {table} WHERE name = ?"
        params: List[Any] = [name]
        if parent_column:
            sql += f" AND {parent_column} IS ?"
            params.append(parent_id)
        row = self.conn.execute(sql, params).fetchone()
        if not row:
            raise UnknownNameError(
                f"unknown {table} {name!r}; add it under Admin > Lists first"
            )
        if row["retired_at"] and row["id"] != current:
            raise UnknownNameError(
                f"{table} {name!r} is retired; restore it under Admin > Lists"
                " or choose another"
            )
        return row["id"]

    def associate_repository(
        self,
        full_name: str,
        *,
        client: Optional[str] = None,
        project: Optional[str] = None,
        application: Optional[str] = None,
    ) -> None:
        """Link a repository to an existing client/project/application (all
        optional; unassigned is valid). A project without a client is an
        internal project. Unknown or retired names are rejected."""
        row = self.conn.execute(
            "SELECT id, client_id, project_id, application_id FROM repository"
            " WHERE full_name_lower = ?",
            (full_name.lower(),),
        ).fetchone()
        if not row:
            raise NotFoundError(f"unknown repository {full_name!r}")
        if application and not project:
            raise RegistryError("an application belongs to a project; choose one")
        client_id = self.client_id_for(client, current=row["client_id"])
        project_id = self._resolve(
            "project", project, "client_id", client_id, row["project_id"]
        )
        application_id = self._resolve(
            "application", application, "project_id", project_id, row["application_id"]
        )
        with self.conn:
            self.conn.execute(
                "UPDATE repository SET client_id = ?, project_id = ?,"
                " application_id = ? WHERE id = ?",
                (client_id, project_id, application_id, row["id"]),
            )

    def _require(self, table: str, row_id: int) -> sqlite3.Row:
        if table not in ("client", "project", "application", "connection"):
            raise ValueError(table)
        row = self.conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)
        ).fetchone()
        if not row:
            raise NotFoundError(f"no {table} with id {row_id}")
        return row

    # -- source editing ---------------------------------------------------
    def update_source(
        self,
        source_id: int,
        *,
        client: Optional[str] = None,
        connection_id: Optional[int] = None,
        clear_connection: bool = False,
    ) -> Dict[str, Any]:
        """``client=""`` clears the client; ``None`` leaves it unchanged."""
        source = self.get_source(source_id)
        with self.conn:
            if client is not None:
                self.conn.execute(
                    "UPDATE source SET client_id = ? WHERE id = ?",
                    (
                        self.client_id_for(client, current=source["client_id"]),
                        source_id,
                    ),
                )
            if clear_connection:
                self.conn.execute(
                    "UPDATE source SET connection_id = NULL WHERE id = ?", (source_id,)
                )
            elif connection_id is not None:
                self._require("connection", connection_id)
                self.conn.execute(
                    "UPDATE source SET connection_id = ? WHERE id = ?",
                    (connection_id, source_id),
                )
        return self.get_source(source_id)

    # -- refresh requests (the API asks, the worker acts) -------------------
    def request_refresh(self) -> int:
        with self.conn:
            return inserted_id(
                self.conn.execute(
                    "INSERT INTO refresh_request (requested_at) VALUES (?)",
                    (now_iso(),),
                )
            )

    def pending_refresh(self) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM refresh_request WHERE handled_at IS NULL LIMIT 1"
            ).fetchone()
            is not None
        )

    def consume_refresh_requests(self) -> int:
        with self.conn:
            return self.conn.execute(
                "UPDATE refresh_request SET handled_at = ? WHERE handled_at IS NULL",
                (now_iso(),),
            ).rowcount

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

    # -- Dependabot alerts ----------------------------------------------
    def save_dependabot_result(
        self,
        full_name: str,
        collection: Any,
        client_id: Optional[int] = None,
    ) -> None:
        """Store one repository's check: the alerts read, the coverage outcome,
        and an observation of the counts so history accumulates.

        Alerts are upserted by (repository, number) and never deleted: GitHub
        keeps dismissed and fixed alerts, and a failed check must not erase
        what an earlier one found.
        """
        repo = full_name.lower()
        now = now_iso()
        with self.conn:
            if collection.alerts:
                for alert in collection.alerts:
                    self.conn.execute(
                        _UPSERT_ALERT, {**alert, "repo": repo, "now": now}
                    )
            read = collection.read_alerts
            self.conn.execute(
                _UPSERT_COVERAGE,
                {
                    "repo": repo,
                    "status": collection.status,
                    "reason": collection.reason,
                    "count": len(collection.alerts),
                    "truncated": int(collection.truncated),
                    "now": now,
                    "success": now if read else None,
                },
            )
            if read:
                counts = self._dependabot_counts(repo)
                self.conn.execute(
                    "INSERT INTO observation (subject, kind, value, source,"
                    " client_id, observed_at) VALUES (?, 'dependabot.counts', ?,"
                    " 'rest.dependabot.alerts', ?, ?)",
                    (full_name, json.dumps(counts, sort_keys=True), client_id, now),
                )

    def _dependabot_counts(self, repo: str) -> Dict[str, Any]:
        counts: Dict[str, Any] = {"open": 0, "dismissed": 0, "fixed": 0}
        by_severity: Dict[str, int] = {}
        for row in self.conn.execute(
            "SELECT state, severity, COUNT(*) AS n FROM dependabot_alert"
            " WHERE repo = ? GROUP BY state, severity",
            (repo,),
        ):
            if row["state"] in counts:
                counts[row["state"]] += row["n"]
            if row["state"] == "open":
                by_severity[row["severity"]] = row["n"]
        counts["open_by_severity"] = by_severity
        return counts

    def list_dependabot_alerts(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM dependabot_alert ORDER BY repo, number DESC"
        )
        return [dict(r) for r in rows]

    def list_dependabot_coverage(self) -> Dict[str, Dict[str, Any]]:
        return {
            r["repo"]: dict(r)
            for r in self.conn.execute("SELECT * FROM dependabot_coverage")
        }


_UPSERT_ALERT = """
INSERT INTO dependabot_alert (repo, number, state, auto_dismissed, severity,
    ecosystem, package, manifest_path, scope, ghsa_id, cve_id, summary,
    vulnerable_range, fixed_version, created_at, updated_at, dismissed_at,
    dismissed_reason, fixed_at, html_url, first_seen_at, last_seen_at)
VALUES (:repo, :number, :state, :auto_dismissed, :severity, :ecosystem,
    :package, :manifest_path, :scope, :ghsa_id, :cve_id, :summary,
    :vulnerable_range, :fixed_version, :created_at, :updated_at, :dismissed_at,
    :dismissed_reason, :fixed_at, :html_url, :now, :now)
ON CONFLICT (repo, number) DO UPDATE SET
    state = excluded.state, auto_dismissed = excluded.auto_dismissed,
    severity = excluded.severity, ecosystem = excluded.ecosystem,
    package = excluded.package, manifest_path = excluded.manifest_path,
    scope = excluded.scope, ghsa_id = excluded.ghsa_id, cve_id = excluded.cve_id,
    summary = excluded.summary, vulnerable_range = excluded.vulnerable_range,
    fixed_version = excluded.fixed_version, created_at = excluded.created_at,
    updated_at = excluded.updated_at, dismissed_at = excluded.dismissed_at,
    dismissed_reason = excluded.dismissed_reason, fixed_at = excluded.fixed_at,
    html_url = excluded.html_url, last_seen_at = excluded.last_seen_at
"""

_UPSERT_COVERAGE = """
INSERT INTO dependabot_coverage (repo, status, reason, alert_count, truncated,
    checked_at, last_success_at)
VALUES (:repo, :status, :reason, :count, :truncated, :now, :success)
ON CONFLICT (repo) DO UPDATE SET
    status = excluded.status, reason = excluded.reason,
    alert_count = excluded.alert_count, truncated = excluded.truncated,
    checked_at = excluded.checked_at,
    last_success_at = COALESCE(excluded.last_success_at,
                               dependabot_coverage.last_success_at)
"""
