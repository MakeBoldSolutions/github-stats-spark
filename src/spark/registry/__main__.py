"""Admin CLI: ``python -m spark.registry <command>``.

Manages sources until the management UI exists. The database path comes from
``--db`` or ``SPARK_DB_PATH``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from github import Auth, Github

from spark.registry.discovery import run_discovery, validate_access
from spark.registry.export import write_portfolio
from spark.registry.store import Registry, RegistryError


def _github():
    token = os.environ.get("GITHUB_TOKEN", "")
    return Github(auth=Auth.Token(token)) if token else Github()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spark.registry")
    parser.add_argument("--db", default=os.environ.get("SPARK_DB_PATH", "registry.db"))
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="register a source")
    add.add_argument("type", choices=["org", "user", "repo"])
    add.add_argument("identifier", help="login, or owner/name for a repo")
    add.add_argument("--client", help="client the source belongs to")
    add.add_argument("--no-validate", action="store_true")

    sub.add_parser("list", help="show sources and their status")
    for name in ("enable", "disable", "remove"):
        cmd = sub.add_parser(name, help=f"{name} a source by id")
        cmd.add_argument("id", type=int)
    sub.add_parser("discover", help="discover repositories for enabled sources")

    for name in ("exclude", "include"):
        cmd = sub.add_parser(name, help=f"{name} a repository in the portfolio")
        cmd.add_argument("repository", help="owner/name")
    assign = sub.add_parser("assign", help="associate a repository")
    assign.add_argument("repository")
    assign.add_argument("--client")
    assign.add_argument("--project")
    assign.add_argument("--application")

    export = sub.add_parser("export", help="write portfolio.json")
    export.add_argument("path", type=Path)
    sub.add_parser("prune", help="delete repositories no source reaches")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    registry = Registry.open(args.db)
    try:
        return _run(args, registry)
    except RegistryError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    finally:
        registry.close()


def _run(args, registry: Registry) -> int:
    cmd = args.command
    if cmd == "add":
        if not args.no_validate:
            _, problem = validate_access(_github(), args.type, args.identifier)
            if problem is not None:
                print(
                    f"ERROR: cannot use {args.identifier}: {problem.message}",
                    file=sys.stderr,
                )
                return 1
        source = registry.add_source(args.type, args.identifier, client=args.client)
        print(f"source {source['id']}: {source['type']} {source['identifier']}")
    elif cmd == "list":
        for s in registry.list_sources():
            flag = "on " if s["enabled"] else "off"
            detail = s["error_code"] or f"{s['repository_count']} repos"
            print(
                f"{s['id']:>3} {flag} {s['type']:<4} {s['identifier']:<40} {s['state']:<8} {detail}"
            )
    elif cmd in ("enable", "disable"):
        registry.set_source_enabled(args.id, cmd == "enable")
    elif cmd == "remove":
        registry.remove_source(args.id)
    elif cmd == "discover":
        for r in run_discovery(registry, _github()):
            print(
                f"source {r['source_id']}: {r['state']} {r['code'] or ''} ({r['count']} repos)"
            )
    elif cmd in ("exclude", "include"):
        registry.set_repository_excluded(args.repository, cmd == "exclude")
    elif cmd == "assign":
        registry.associate_repository(
            args.repository,
            client=args.client,
            project=args.project,
            application=args.application,
        )
    elif cmd == "export":
        payload = write_portfolio(registry, args.path)
        print(f"wrote {args.path} ({payload['repository_count']} repositories)")
    elif cmd == "prune":
        print(f"deleted {registry.prune_orphans()} orphaned repositories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
