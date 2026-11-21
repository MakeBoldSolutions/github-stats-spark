"""SQLite connection and versioned migrations for the source registry.

Configuration tables (client, project, application, source, repository,
associations, connection) live beside collected-data tables (observation) in
one database, but are kept apart by purpose. Every record that can belong to a
client carries a nullable ``client_id`` (NULL means an internal asset).
"""

from __future__ import annotations

import os
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
    # 2: administrator, sessions, stored connections, refresh requests
    """
    CREATE TABLE admin_user (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    -- Only a hash of the session token is stored, so a copied database cannot
    -- be used to impersonate a signed-in administrator.
    CREATE TABLE admin_session (
        id INTEGER PRIMARY KEY,
        token_hash TEXT NOT NULL UNIQUE,
        csrf_token TEXT NOT NULL,
        user_id INTEGER NOT NULL REFERENCES admin_user(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    -- secret_encrypted is a Fernet token; the key lives outside the database.
    ALTER TABLE connection ADD COLUMN secret_encrypted TEXT;
    ALTER TABLE connection ADD COLUMN owner TEXT;
    ALTER TABLE connection ADD COLUMN expires_at TEXT;
    ALTER TABLE connection ADD COLUMN last_validated_at TEXT;
    -- The API asks; the worker (a separate process) acts. No RPC.
    CREATE TABLE refresh_request (
        id INTEGER PRIMARY KEY,
        requested_at TEXT NOT NULL,
        handled_at TEXT
    );
    """,
    # 3: Dependabot alert detail and per-repository coverage. Keyed by the
    # lower-cased repository name rather than a foreign key, so history
    # survives pruning a repository nothing reaches any more.
    """
    CREATE TABLE dependabot_alert (
        repo TEXT NOT NULL,
        number INTEGER NOT NULL,
        state TEXT NOT NULL,
        auto_dismissed INTEGER NOT NULL DEFAULT 0,
        severity TEXT NOT NULL,
        ecosystem TEXT,
        package TEXT,
        manifest_path TEXT,
        scope TEXT,
        ghsa_id TEXT,
        cve_id TEXT,
        summary TEXT,
        vulnerable_range TEXT,
        fixed_version TEXT,
        created_at TEXT,
        updated_at TEXT,
        dismissed_at TEXT,
        dismissed_reason TEXT,
        fixed_at TEXT,
        html_url TEXT,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        PRIMARY KEY (repo, number)
    );
    CREATE INDEX dependabot_alert_state ON dependabot_alert (state, severity);
    -- What the last check of each repository found out, including why it
    -- could not read alerts. last_success_at only moves when alerts were read.
    CREATE TABLE dependabot_coverage (
        repo TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        reason TEXT NOT NULL,
        alert_count INTEGER NOT NULL DEFAULT 0,
        truncated INTEGER NOT NULL DEFAULT 0,
        checked_at TEXT NOT NULL,
        last_success_at TEXT
    );
    """,
    # 4: managed lists and classification domains. Clients, projects and
    # applications can be retired (hidden from pickers, kept on what already
    # uses them). A domain is a named list of allowed values; a repository is
    # classified by linking it to values. Keys are stable; labels may change.
    """
    ALTER TABLE client ADD COLUMN retired_at TEXT;
    ALTER TABLE project ADD COLUMN retired_at TEXT;
    ALTER TABLE application ADD COLUMN retired_at TEXT;
    CREATE TABLE domain (
        id INTEGER PRIMARY KEY,
        key TEXT NOT NULL UNIQUE COLLATE NOCASE,
        label TEXT NOT NULL,
        description TEXT,
        multi INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        retired_at TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE domain_value (
        id INTEGER PRIMARY KEY,
        domain_id INTEGER NOT NULL REFERENCES domain(id) ON DELETE CASCADE,
        key TEXT NOT NULL COLLATE NOCASE,
        label TEXT NOT NULL,
        description TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        retired_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (domain_id, key)
    );
    CREATE TABLE repository_classification (
        repository_id INTEGER NOT NULL REFERENCES repository(id) ON DELETE CASCADE,
        value_id INTEGER NOT NULL REFERENCES domain_value(id),
        assigned_at TEXT NOT NULL,
        PRIMARY KEY (repository_id, value_id)
    );
    CREATE INDEX repository_classification_value
        ON repository_classification (value_id);
    INSERT INTO domain (key, label, description, multi, sort_order, created_at)
    VALUES
        ('tier', 'Tier', 'How much the repository matters to the portfolio now.',
         0, 10, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        ('type', 'Type', 'What the repository is.',
         0, 20, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        ('lifecycle', 'Lifecycle', 'Where the repository is in its life.',
         0, 30, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        ('stack', 'Stack', 'Main technologies; choose all that apply.',
         1, 40, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
    INSERT INTO domain_value (domain_id, key, label, sort_order, created_at)
    SELECT d.id, v.key, v.label, v.sort_order, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM domain d JOIN (
        SELECT 'tier' AS domain, 'core' AS key, 'Core' AS label, 10 AS sort_order
        UNION ALL SELECT 'tier', 'supporting', 'Supporting', 20
        UNION ALL SELECT 'tier', 'archive', 'Archive', 30
        UNION ALL SELECT 'type', 'website', 'Website', 10
        UNION ALL SELECT 'type', 'web-app', 'Web app', 20
        UNION ALL SELECT 'type', 'api', 'API', 30
        UNION ALL SELECT 'type', 'library', 'Library', 40
        UNION ALL SELECT 'type', 'tool', 'Tool', 50
        UNION ALL SELECT 'type', 'docs', 'Docs', 60
        UNION ALL SELECT 'type', 'template', 'Template', 70
        UNION ALL SELECT 'lifecycle', 'active', 'Active', 10
        UNION ALL SELECT 'lifecycle', 'maintenance', 'Maintenance', 20
        UNION ALL SELECT 'lifecycle', 'deprecated', 'Deprecated', 30
        UNION ALL SELECT 'lifecycle', 'experiment', 'Experiment', 40
        UNION ALL SELECT 'stack', 'dotnet', '.NET', 10
        UNION ALL SELECT 'stack', 'python', 'Python', 20
        UNION ALL SELECT 'stack', 'node-react', 'Node/React', 30
        UNION ALL SELECT 'stack', 'static-site', 'Static site', 40
    ) v ON v.domain = d.key;
    """,
]


def copy_database(source: Union[str, Path], target: Union[str, Path]) -> None:
    """Consistent copy using SQLite's online backup API, so it is safe while
    other processes are writing. The target appears only once complete."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    partial.unlink(missing_ok=True)
    src = sqlite3.connect(str(source), timeout=30)
    dst = sqlite3.connect(str(partial))
    try:
        src.backup(dst)
        # A copy is a single self-contained file: no -wal/-shm companions to
        # lose, rotate, or leave behind. connect() restores WAL on the live DB.
        dst.execute("PRAGMA journal_mode = DELETE")
    finally:
        dst.close()
        src.close()
    os.replace(partial, target)


def _save_pre_migration_copy(path: Path, conn: sqlite3.Connection) -> None:
    """Before upgrading an existing database, keep a copy of it as it was, so a
    rollback to the previous release has something it can open."""
    current = schema_version(conn)
    if 0 < current < len(MIGRATIONS):
        keep = path.with_name(f"{path.name}.pre-v{current}.bak")
        if not keep.exists():
            copy_database(path, keep)


def connect(path: Union[str, Path]) -> sqlite3.Connection:
    """Open the registry database, creating and migrating it as needed."""
    on_disk = str(path) != ":memory:"
    if on_disk:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if on_disk:
        conn.execute("PRAGMA journal_mode = WAL")
        _save_pre_migration_copy(Path(path), conn)
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
