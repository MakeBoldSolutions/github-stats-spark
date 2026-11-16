"""``python -m spark.api <command>``: serve the admin API and manage the admin.

serve            run the API (uvicorn); bootstraps an admin from the
                 environment if none exists yet
create-admin     create the administrator interactively
reset-password   set a new password (signs every session out)
generate-key     print a new SPARK_SECRET_KEY
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Mapping, Optional

from spark.api import security
from spark.registry import Registry
from spark.registry.secrets import SecretBox, SecretError, generate_key, load_key
from spark.registry.store import RegistryError


def db_path(env: Mapping[str, str]) -> Path:
    if env.get("SPARK_DB_PATH"):
        return Path(env["SPARK_DB_PATH"])
    return (
        Path(env.get("SPARK_CONFIG_PATH", "/app/config/spark.yml")).parent
        / "registry.db"
    )


def read_secret(env: Mapping[str, str], name: str) -> Optional[str]:
    """Read ``NAME`` or the file named by ``NAME_FILE``."""
    if env.get(name):
        return env[name]
    path = env.get(f"{name}_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise SystemExit(f"cannot read {name}_FILE: {error}") from error
    return None


def bootstrap_admin(registry: Registry, env: Mapping[str, str]) -> Optional[str]:
    """Create the first administrator from the environment, once.

    Does nothing when an administrator already exists, so the password can be
    removed from the environment after first start.
    """
    if security.admin_exists(registry):
        return None
    username = env.get("SPARK_ADMIN_USER", "").strip()
    password = read_secret(env, "SPARK_ADMIN_PASSWORD")
    if not (username and password):
        return None
    security.create_admin(registry, username, password)
    return username


def build_app(env: Optional[Mapping[str, str]] = None):
    from spark.api.app import create_app

    env = os.environ if env is None else env
    path = db_path(env)
    registry = Registry.open(path)
    try:
        created = bootstrap_admin(registry, env)
        has_admin = security.admin_exists(registry)
    finally:
        registry.close()
    if created:
        print(f"Created administrator {created!r}", flush=True)
    if not has_admin:
        print(
            "WARNING: no administrator exists; run 'python -m spark.api create-admin' "
            "or set SPARK_ADMIN_USER and SPARK_ADMIN_PASSWORD",
            flush=True,
        )
    try:
        box = SecretBox(load_key(env))
    except SecretError as error:
        raise SystemExit(f"ERROR: {error}") from error
    if not box.available:
        print(
            "NOTE: SPARK_SECRET_KEY is not set; saving tokens is disabled", flush=True
        )
    return create_app(
        path,
        secret_box=box,
        default_token=read_secret(env, "GITHUB_TOKEN") or "",
        cookie_secure=env.get("SPARK_COOKIE_SECURE", "").lower()
        in ("1", "true", "yes"),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="spark.api")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument(
        "--host", default="0.0.0.0"
    )  # noqa: S104 - container network only
    serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("create-admin")
    sub.add_parser("reset-password")
    sub.add_parser("generate-key")
    args = parser.parse_args(argv)

    if args.command == "generate-key":
        print(generate_key())
        return 0
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            build_app(),
            host=args.host,
            port=args.port,
            proxy_headers=False,
            server_header=False,
            access_log=False,
        )
        return 0

    registry = Registry.open(db_path(os.environ))
    try:
        username = input("Username: ").strip()
        password = getpass.getpass("Password (min 12 chars): ")
        if password != getpass.getpass("Repeat password: "):
            print("ERROR: passwords do not match", file=sys.stderr)
            return 2
        if args.command == "create-admin":
            security.create_admin(registry, username, password)
        else:
            security.set_admin_password(registry, username, password)
        print("done")
        return 0
    except RegistryError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    finally:
        registry.close()


if __name__ == "__main__":
    sys.exit(main())
