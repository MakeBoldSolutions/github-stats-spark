"""Encryption for stored third-party secrets (for example GitHub tokens).

The key is supplied from outside the database (``SPARK_SECRET_KEY`` or
``SPARK_SECRET_KEY_FILE``), so a copied database file or backup does not
expose the secrets it holds.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from cryptography.fernet import Fernet, InvalidToken


class SecretError(RuntimeError):
    """Raised when a secret cannot be stored or read."""


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def load_key(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Return the key from the environment or a key file, or None if unset."""
    env = os.environ if env is None else env
    if env.get("SPARK_SECRET_KEY", "").strip():
        return env["SPARK_SECRET_KEY"].strip()
    path = env.get("SPARK_SECRET_KEY_FILE", "").strip()
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip() or None
        except OSError as error:
            raise SecretError(f"cannot read SPARK_SECRET_KEY_FILE: {error}") from error
    return None


class SecretBox:
    """Encrypt and decrypt short secrets with a Fernet key."""

    def __init__(self, key: Optional[str]):
        self._fernet: Optional[Fernet] = None
        if key:
            try:
                self._fernet = Fernet(key.encode("ascii"))
            except (ValueError, TypeError) as error:
                raise SecretError(
                    "SPARK_SECRET_KEY is not a valid Fernet key; generate one with "
                    "python -m spark.api generate-key"
                ) from error

    @property
    def available(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            raise SecretError(
                "no encryption key configured (set SPARK_SECRET_KEY); "
                "generate one with python -m spark.api generate-key"
            )
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not self._fernet:
            raise SecretError("no encryption key configured (set SPARK_SECRET_KEY)")
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise SecretError(
                "stored secret cannot be decrypted with the configured key"
            ) from error
