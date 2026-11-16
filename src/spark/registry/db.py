"""SQLite connection and versioned migrations for the source registry.

Configuration tables (client, project, application, source, repository,
associations, connection) live beside collected-data tables (observation) in
one database, but are kept apart by purpose. Every record that can belong to a
client carries a nullable ``client_id`` (NULL means an internal asset).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Union

MIGRATIONS: List[str] = [
    # 1: initial registry
    """
    CREATE TABLE client (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        created_at TEXT NOT NULL
    );
    CREATE TABLE project (
        id INTEGER PRIMARY KEY,
        client_id INTEGER REFERENCES client(id),
        name TEXT NOT NULL COLLATE NOCASE,
        created_at TEXT NOT NULL,
        UNIQUE (client_id, name)
    );
    CREATE TABLE application (
        id INTEGER PRIMARY KEY,
        client_id INTEGER REFERENCES client(id),
        project_id INTEGER REFERENCES project(id),
        name TEXT NOT NULL COLLATE NOCASE,
        created_at TEXT NOT NULL,
        UNIQUE (project_id, name)
    );
    -- A reference to where a credential lives (for example an environment
    -- variable name). Secret values are never stored here.
    CREATE TABLE connection (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        kind TEXT NOT NULL,
        secret_ref TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE source (
        id INTEGER PRIMARY KEY,
        type TEXT NOT NULL CHECK (type IN ('org', 'user', 'repo')),
        identifier TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        client_id INTEGER REFERENCES client(id),
        connection_id INTEGER REFERENCES connection(id),
        state TEXT NOT NULL DEFAULT 'pending',
        error_code TEXT,
        error_message TEXT,
        repository_count INTEGER NOT NULL DEFAULT 0,
        last_discovery_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (type, identifier COLLATE NOCASE)
    );
    CREATE TABLE repository (
        id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        full_name_lower TEXT NOT NULL UNIQUE,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        language TEXT,
        html_url TEXT,
        default_branch TEXT,
        pushed_at TEXT,
        is_fork INTEGER NOT NULL DEFAULT 0,
        is_private INTEGER NOT NULL DEFAULT 0,
        is_archived INTEGER NOT NULL DEFAULT 0,
        excluded INTEGER NOT NULL DEFAULT 0,
        client_id INTEGER REFERENCES client(id),
        project_id INTEGER REFERENCES project(id),
        application_id INTEGER REFERENCES application(id),
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
    );
    CREATE TABLE repository_source (
        repository_id INTEGER NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
        source_id INTEGER NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        PRIMARY KEY (repository_id, source_id)
    );
    -- Generic collected-data shape so later collectors need no schema change.
    CREATE TABLE observation (
        id INTEGER PRIMARY KEY,
        subject TEXT NOT NULL,
        kind TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT NOT NULL,
        client_id INTEGER REFERENCES client(id),
        observed_at TEXT NOT NULL
    );
    CREATE INDEX observation_lookup ON observation (subject, kind, observed_at);
    """,
]


def connect(path: Union[str, Path]) -> sqlite3.Connection:
    """Open the registry database, creating and migrating it as needed."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    migrate(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations, each in its own transaction."""
    current = schema_version(conn)
    if current > len(MIGRATIONS):
        raise RuntimeError(
            f"registry database is schema v{current}, newer than this "
            f"application supports (v{len(MIGRATIONS)}); refusing to open it"
        )
    for number in range(current, len(MIGRATIONS)):
        script = MIGRATIONS[number]
        try:
            conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number + 1};")
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
    return schema_version(conn)
