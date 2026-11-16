"""Administrator credentials and sessions.

Passwords are stored only as salted, slow Argon2id hashes. Session tokens are
random and only their SHA-256 hash is stored, so a copied database cannot be
used to sign in or to impersonate a session.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from spark.registry.store import Registry, RegistryError, now_iso

MIN_PASSWORD_LENGTH = 12
_hasher = PasswordHasher()
# Verified against when the user does not exist, so timing does not reveal
# which usernames are valid.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise RegistryError(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    return _hasher.hash(password)


def verify_password(stored_hash: Optional[str], password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and bool(
            stored_hash
        )
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# -- administrator ------------------------------------------------------
def admin_exists(registry: Registry) -> bool:
    return (
        registry.conn.execute("SELECT 1 FROM admin_user LIMIT 1").fetchone() is not None
    )


def create_admin(registry: Registry, username: str, password: str) -> int:
    username = (username or "").strip()
    if not username or len(username) > 64:
        raise RegistryError("username must be 1-64 characters")
    hashed = hash_password(password)
    with registry.conn:
        return registry.conn.execute(
            "INSERT INTO admin_user (username, password_hash, created_at)"
            " VALUES (?, ?, ?)",
            (username, hashed, now_iso()),
        ).lastrowid


def set_admin_password(registry: Registry, username: str, password: str) -> None:
    hashed = hash_password(password)
    with registry.conn:
        changed = registry.conn.execute(
            "UPDATE admin_user SET password_hash = ? WHERE username = ?",
            (hashed, username),
        ).rowcount
        if not changed:
            raise RegistryError(f"no administrator named {username!r}")
        # A password change signs every session out.
        registry.conn.execute("DELETE FROM admin_session")


def authenticate(registry: Registry, username: str, password: str) -> Optional[int]:
    row = registry.conn.execute(
        "SELECT id, password_hash FROM admin_user WHERE username = ?", (username,)
    ).fetchone()
    ok = verify_password(row["password_hash"] if row else None, password)
    return row["id"] if (row and ok) else None


# -- sessions -----------------------------------------------------------
def create_session(
    registry: Registry,
    user_id: int,
    hours: float = 12,
    now: Optional[datetime] = None,
) -> Tuple[str, str]:
    """Returns (session token for the cookie, csrf token for the page)."""
    now = now or datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    with registry.conn:
        registry.conn.execute(
            "DELETE FROM admin_session WHERE expires_at <= ?", (now.isoformat(),)
        )
        registry.conn.execute(
            "INSERT INTO admin_session (token_hash, csrf_token, user_id, created_at,"
            " expires_at) VALUES (?, ?, ?, ?, ?)",
            (
                token_hash(token),
                csrf,
                user_id,
                now.isoformat(),
                (now + timedelta(hours=hours)).isoformat(),
            ),
        )
    return token, csrf


def lookup_session(
    registry: Registry, token: Optional[str], now: Optional[datetime] = None
) -> Optional[Dict[str, str]]:
    if not token:
        return None
    now = now or datetime.now(timezone.utc)
    row = registry.conn.execute(
        "SELECT s.csrf_token, s.expires_at, u.username FROM admin_session s"
        " JOIN admin_user u ON u.id = s.user_id WHERE s.token_hash = ?",
        (token_hash(token),),
    ).fetchone()
    if not row or datetime.fromisoformat(row["expires_at"]) <= now:
        return None
    return {"username": row["username"], "csrf_token": row["csrf_token"]}


def end_session(registry: Registry, token: Optional[str]) -> None:
    if token:
        with registry.conn:
            registry.conn.execute(
                "DELETE FROM admin_session WHERE token_hash = ?", (token_hash(token),)
            )


def csrf_matches(expected: str, provided: Optional[str]) -> bool:
    return bool(provided) and hmac.compare_digest(expected, provided)


class LoginThrottle:
    """Lock a username out briefly after repeated failures (in memory; the
    API runs as a single process)."""

    def __init__(
        self, max_failures: int = 5, window_seconds: int = 900, clock=time.monotonic
    ):
        self.max_failures = max_failures
        self.window = window_seconds
        self.clock = clock
        self._failures: Dict[str, list] = {}

    def _recent(self, key: str) -> list:
        cutoff = self.clock() - self.window
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        self._failures[key] = recent
        return recent

    def blocked(self, key: str) -> bool:
        return len(self._recent(key.lower())) >= self.max_failures

    def fail(self, key: str) -> None:
        self._recent(key.lower()).append(self.clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key.lower(), None)
