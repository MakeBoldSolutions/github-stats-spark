"""Named GitHub connections: where a source's credential comes from.

A connection holds an encrypted token (kind ``pat`` first; the schema leaves
room for ``app``), the owner it covers, and when it expires. Secret values
are never returned by any function here except ``resolve_token``, which the
worker alone uses to talk to GitHub.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from spark.registry.secrets import SecretBox, SecretError
from spark.registry.store import Registry, RegistryError, inserted_id, now_iso

KINDS = ("pat",)
PUBLIC_FIELDS = (
    "id",
    "name",
    "kind",
    "owner",
    "expires_at",
    "last_validated_at",
    "created_at",
)


def is_expired(expires_at: Optional[str], now: Optional[datetime] = None) -> bool:
    if not expires_at:
        return False
    try:
        moment = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment <= (now or datetime.now(timezone.utc))


def _public(row) -> Dict[str, Any]:
    item = {key: row[key] for key in PUBLIC_FIELDS}
    item["has_secret"] = bool(row["secret_encrypted"])
    item["expired"] = is_expired(row["expires_at"])
    return item


def create_connection(
    registry: Registry,
    box: SecretBox,
    *,
    name: str,
    token: str,
    owner: Optional[str] = None,
    expires_at: Optional[str] = None,
    kind: str = "pat",
) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name or len(name) > 80:
        raise RegistryError("connection name must be 1-80 characters")
    if kind not in KINDS:
        raise RegistryError(f"connection kind must be one of {', '.join(KINDS)}")
    if not token or len(token) < 20:
        raise RegistryError("token looks too short to be a GitHub token")
    if expires_at:
        try:
            datetime.fromisoformat(expires_at)
        except ValueError as error:
            raise RegistryError("expires_at must be an ISO date") from error
    try:
        encrypted = box.encrypt(token)
    except SecretError as error:
        raise RegistryError(str(error)) from error
    try:
        with registry.conn:
            new_id = inserted_id(
                registry.conn.execute(
                    "INSERT INTO connection (name, kind, secret_ref, secret_encrypted,"
                    " owner, expires_at, created_at)"
                    " VALUES (?, ?, 'stored', ?, ?, ?, ?)",
                    (name, kind, encrypted, owner, expires_at or None, now_iso()),
                )
            )
    except sqlite3.IntegrityError as error:
        raise RegistryError(f"a connection named {name!r} already exists") from error
    return get_connection(registry, new_id)


def get_connection(registry: Registry, connection_id: int) -> Dict[str, Any]:
    row = registry.conn.execute(
        "SELECT * FROM connection WHERE id = ?", (connection_id,)
    ).fetchone()
    if not row:
        raise RegistryError(f"no connection with id {connection_id}")
    return _public(row)


def list_connections(registry: Registry) -> List[Dict[str, Any]]:
    rows = registry.conn.execute("SELECT * FROM connection ORDER BY name").fetchall()
    return [_public(r) for r in rows]


def delete_connection(registry: Registry, connection_id: int) -> int:
    """Delete a connection; sources using it fall back to the default token.
    Returns how many sources were detached."""
    get_connection(registry, connection_id)
    with registry.conn:
        detached = registry.conn.execute(
            "UPDATE source SET connection_id = NULL WHERE connection_id = ?",
            (connection_id,),
        ).rowcount
        registry.conn.execute("DELETE FROM connection WHERE id = ?", (connection_id,))
    return detached


def mark_validated(registry: Registry, connection_id: int) -> None:
    with registry.conn:
        registry.conn.execute(
            "UPDATE connection SET last_validated_at = ? WHERE id = ?",
            (now_iso(), connection_id),
        )


def resolve_token(
    registry: Registry,
    box: SecretBox,
    source: Dict[str, Any],
    default: str = "",
) -> str:
    """The token to use for ``source``: its own connection, else ``default``.

    Raises ``SecretError`` for an expired connection or an unreadable secret,
    so the caller can report an actionable source error instead of silently
    falling back to a different identity.
    """
    connection_id = source.get("connection_id")
    if not connection_id:
        return default
    row = registry.conn.execute(
        "SELECT * FROM connection WHERE id = ?", (connection_id,)
    ).fetchone()
    if not row or not row["secret_encrypted"]:
        raise SecretError("the source's connection no longer has a stored token")
    if is_expired(row["expires_at"]):
        raise SecretError(f"connection {row['name']!r} expired on {row['expires_at']}")
    return box.decrypt(row["secret_encrypted"])
