#!/usr/bin/env python3
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
"""Structural consistency for an optional DevSpark roadmap.

Commands:
  check          Read-only. Resolve the roadmap root, list Prospective Specs, report findings.
  repair         Plan deterministic mechanical repairs (item placement, broken local links).
                 Writes nothing unless --apply is given, and never writes outside the roadmap root.
  locate <id>    Read-only. Report one Prospective Spec and the status of its dependencies.

The roadmap root is --root, else `roadmap.root` in .devspark.work/devspark.json, else
.devspark.work/roadmap/. A missing roadmap is a normal state, never an error. Nothing here reads
the network, changes Git state, advances a status, or touches application files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

DEFAULT_ROOT = ".devspark.work/roadmap"
STATUSES = ("proposed", "ready", "active", "complete", "dropped")
RESOLVED = {"complete", "dropped"}
FIELDS = {"id", "title", "status", "order", "depends_on", "blockers", "delivery"}
REQUIRED = ("id", "title", "status")
ID = re.compile(r"^ps-(\d{3,})$")
FILENAME = re.compile(r"^(ps-\d{3,})(?:-[a-z0-9][a-z0-9-]*)?\.md$")
LEGACY_ID = re.compile(r"^ps-(\d{2,})$", re.I)
LEGACY_FILENAME = re.compile(r"^(ps-\d{2,})(?:-[a-z0-9][a-z0-9-]*)?\.md$", re.I)
FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)\)")
DELIVERED = re.compile(r"^- \[[^\]\n]*\]\(([^)\s]+)\) — (complete|dropped|unknown); archived(?: with release [^\r\n]+)?[ \t]*\r?$", re.M)
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
TIMEOUT = 30
# Repository areas a roadmap root may never sit in: durable truth, history, framework-managed files,
# delivery records, and work areas that every release sweeps.
PROTECTED = (
    ".git",
    ".archive",
    ".knowledge",
    ".devspark",
    *(f".devspark.work/{area}" for area in ("specs", "quickfixes", "audit", "metrics", "pr-review", "telemetry")),
)


class UsageError(Exception):
    """The request cannot be evaluated; nothing was changed."""


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=False, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT
    )


def repository_root(explicit: str) -> Path:
    if explicit:
        return Path(explicit).resolve()
    try:
        result = git(Path.cwd(), "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError):
        return Path.cwd().resolve()
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 and result.stdout.strip() else Path.cwd().resolve()


def configured_root(repo: Path) -> str:
    config = repo / ".devspark.work" / "devspark.json"
    if not config.is_file():
        return ""
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"roadmap-check: warning: {config.as_posix()} is not valid JSON ({error}); using the default roadmap root", file=sys.stderr)
        return ""
    section = data.get("roadmap") if isinstance(data, dict) else None
    if section is None:
        return ""
    root = section.get("root") if isinstance(section, dict) else None
    if not isinstance(root, str) or not root.strip():
        raise UsageError("devspark.json 'roadmap.root' must be a non-empty string")
    return root.strip()


def resolve_root(repo: Path, explicit: str) -> tuple[Path, str]:
    if explicit:
        value, source = explicit, "argument"
    else:
        value = configured_root(repo)
        source = "config" if value else "default"
        value = value or DEFAULT_ROOT
    path = Path(os.path.expanduser(value))
    resolved = (path if path.is_absolute() else repo / path).resolve()
    if resolved == repo or inside(repo, resolved):
        raise UsageError(f"roadmap root {value!r} must be a dedicated planning directory, not the repository root or above it")
    for protected in PROTECTED:
        if inside(resolved, repo / protected):
            raise UsageError(f"roadmap root {value!r} is inside {protected}/, which a roadmap must never write")
    return resolved, source


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def display(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if inside(path, root) else path.as_posix()


def read_text(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


def as_list(value: object) -> list[str] | None:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list) and all(isinstance(item, (str, int)) for item in value):
        return [str(item) for item in value]
    return None


def canonical_id(value: str, legacy: bool) -> str:
    match = LEGACY_ID.fullmatch(value) if legacy else None
    return f"ps-{int(match.group(1)):03d}" if match else value


def roadmap_layout(root: Path) -> tuple[Path, bool, bool, dict[Path, str]]:
    config = root / ".devspark-roadmap.json"
    if config.is_symlink():
        raise UsageError("roadmap layout configuration must not be a symbolic link")
    if not config.exists():
        return root / "roadmap.md", False, False, {}
    if not config.is_file():
        raise UsageError("roadmap layout configuration must be a regular file")
    try:
        layout = json.loads(read_text(config))
    except (OSError, ValueError) as error:
        raise UsageError(f"invalid roadmap layout configuration: {error}") from error
    allowed = {"overview", "legacy_ids", "preserve_paths", "supporting_files"}
    if not isinstance(layout, dict) or set(layout) - allowed:
        raise UsageError("roadmap layout has unsupported fields or is not an object")
    overview = layout.get("overview", "roadmap.md")
    if (
        not isinstance(overview, str)
        or not overview.endswith(".md")
        or Path(overview).name != overview
        or "\\" in overview
    ):
        raise UsageError("roadmap overview must be a Markdown filename directly inside the roadmap root")
    legacy = layout.get("legacy_ids", False)
    if not isinstance(legacy, bool):
        raise UsageError("roadmap layout legacy_ids must be a boolean")
    preserve_paths = layout.get("preserve_paths", False)
    if not isinstance(preserve_paths, bool):
        raise UsageError("roadmap layout preserve_paths must be a boolean")

    def item_path(value: object) -> Path:
        if not isinstance(value, str) or "\\" in value:
            raise UsageError("roadmap layout item paths must be relative Markdown paths")
        parts = value.split("/")
        if (
            len(parts) not in (2, 3)
            or parts[0] != "specs"
            or (len(parts) == 3 and parts[1] != "complete")
            or not parts[-1].endswith(".md")
            or parts[-1] in (".", "..", "README.md")
        ):
            raise UsageError(f"roadmap layout item path {value!r} must be a file in specs/ or specs/complete/")
        path = root.joinpath(*parts)
        if path.is_symlink() or not inside(path, root) or not path.is_file():
            raise UsageError(f"roadmap layout item {value!r} must be an existing regular file inside the roadmap root")
        return path

    declared = layout.get("supporting_files", {})
    if not isinstance(declared, dict) or any(not isinstance(value, str) for value in declared.values()):
        raise UsageError("roadmap layout supporting_files must map paths to Prospective Spec ids")
    supporting: dict[Path, str] = {}
    for name, identity in declared.items():
        path = item_path(name)
        identity = canonical_id(identity, legacy)
        if not ID.fullmatch(identity):
            raise UsageError(f"supporting file {name!r} must name a valid Prospective Spec id")
        supporting[path] = identity
    return root / overview, legacy, preserve_paths, supporting


def planning_repository(repo: Path, root: Path) -> Path:
    if inside(root, repo) or not root.is_dir():
        return repo
    try:
        result = git(root, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError):
        return repo
    candidate = Path(result.stdout.strip()).resolve() if result.returncode == 0 and result.stdout.strip() else repo
    return candidate if inside(root, candidate) else repo


class Roadmap:
    """One read of the roadmap root; every command works from this snapshot."""

    def __init__(self, repo: Path, root: Path, source: str) -> None:
        self.repo = repo
        self.root = root
        self.source = source
        self.specs = root / "specs"
        self.complete = self.specs / "complete"
        self.overview, self.legacy_ids, self.preserve_paths, self.supporting = roadmap_layout(root)
        self.archive = planning_repository(repo, root) / ".archive"
        self.items: list[dict[str, object]] = []
        self.findings: list[dict[str, object]] = []
        self.archived: dict[str, str] = {}
        self.present = self.overview.is_file() or self.specs.is_dir()
        if self.present:
            self.load()
            self.check()

    def finding(self, code: str, severity: str, path: Path, message: str, repairable: bool = False) -> None:
        self.findings.append(
            {"code": code, "severity": severity, "path": display(path, self.root), "message": message, "repairable": repairable}
        )

    def safe(self, path: Path) -> bool:
        """A roadmap file the tools may read and write: a regular file that resolves inside the root."""
        return not path.is_symlink() and inside(path, self.root)

    def documents(self) -> list[Path]:
        found = [self.overview] if self.overview.is_file() and self.safe(self.overview) else []
        return found + [item["_path"] for item in self.items] + list(self.supporting)  # type: ignore[misc]

    def filename_id(self, filename: str) -> str:
        match = (LEGACY_FILENAME if self.legacy_ids else FILENAME).fullmatch(filename)
        return canonical_id(match.group(1), self.legacy_ids) if match else ""

    def candidates(self) -> list[Path]:
        paths: list[Path] = []
        for folder in (self.specs, self.complete):
            if folder.is_dir():
                paths += [p for p in folder.glob("*.md") if p.is_file() and p.name.lower() != "readme.md" and p not in self.supporting]
        return sorted(paths, key=lambda p: p.as_posix())

    def load(self) -> None:
        if self.overview.is_file() and not self.safe(self.overview):
            self.finding("unsafe-path", "error", self.overview, "is a symbolic link or resolves outside the roadmap root; it is never read or written")
        for path in self.candidates():
            if not self.safe(path):
                self.finding("unsafe-path", "error", path, "is a symbolic link or resolves outside the roadmap root; it is never read or written")
                continue
            item = self.parse(path)
            if item is not None:
                self.items.append(item)
        self.items.sort(key=lambda item: (item["order"] if isinstance(item["order"], int) else 10**9, str(item["id"])))

    def parse(self, path: Path) -> dict[str, object] | None:
        match = FRONTMATTER.match(read_text(path))
        if not match:
            self.finding("malformed-metadata", "error", path, "no YAML frontmatter block")
            return None
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError as error:
            self.finding("malformed-metadata", "error", path, f"frontmatter is not valid YAML: {str(error).splitlines()[0]}")
            return None
        if not isinstance(meta, dict):
            self.finding("malformed-metadata", "error", path, "frontmatter must be a mapping")
            return None
        for key in sorted(set(map(str, meta)) - FIELDS):
            self.finding("unsupported-field", "warning", path, f"unsupported metadata field '{key}'")
        missing = [key for key in REQUIRED if not str(meta.get(key) or "").strip()]
        if missing:
            self.finding("missing-field", "error", path, f"missing required metadata: {', '.join(missing)}")
        identity = canonical_id(str(meta.get("id") or "").strip(), self.legacy_ids)
        if identity and not ID.match(identity):
            self.finding("invalid-id", "error", path, f"id '{identity}' must look like ps-NNN")
        if identity and self.filename_id(path.name) != identity:
            self.finding("id-filename-mismatch", "error", path, f"file name must start with its id '{identity}'")
        status = str(meta.get("status") or "").strip().lower()
        if status and status not in STATUSES:
            self.finding("invalid-status", "error", path, f"status '{status}' is not one of {', '.join(STATUSES)}")
        order = meta.get("order")
        if order is not None and (isinstance(order, bool) or not isinstance(order, int)):
            self.finding("malformed-metadata", "error", path, "order must be an integer")
            order = None
        depends = as_list(meta.get("depends_on"))
        delivery = as_list(meta.get("delivery"))
        blockers = meta.get("blockers", [])
        if depends is None:
            self.finding("malformed-metadata", "error", path, "depends_on must be a list of ids")
        if delivery is None:
            self.finding("malformed-metadata", "error", path, "delivery must be a list of references")
        if not isinstance(blockers, list) or not all(isinstance(value, str) and value.strip() for value in blockers):
            self.finding("malformed-metadata", "error", path, "blockers must be a list of non-empty descriptions")
            blockers = []
        return {
            "id": identity,
            "title": str(meta.get("title") or "").strip(),
            "status": status,
            "order": order,
            "depends_on": [canonical_id(value, self.legacy_ids) for value in (depends or [])],
            "blockers": blockers,
            "delivery": delivery or [],
            "path": display(path, self.root),
            "_path": path,
        }

    def check(self) -> None:
        self.archived = self.archived_ids()
        by_id: dict[str, list[dict[str, object]]] = {}
        for item in self.items:
            if item["id"]:
                by_id.setdefault(str(item["id"]), []).append(item)
        for identity, group in sorted(by_id.items()):
            if len(group) > 1:
                paths = ", ".join(str(item["path"]) for item in group)
                for item in group:
                    self.finding("duplicate-id", "error", item["_path"], f"id {identity} is used by more than one file: {paths}")  # type: ignore[arg-type]
        for path, identity in self.supporting.items():
            if identity not in by_id and identity not in self.archived:
                self.finding("orphaned-supporting-file", "error", path, f"supporting file refers to missing item {identity}")
        for item in self.items:
            path: Path = item["_path"]  # type: ignore[assignment]
            for dependency in item["depends_on"]:  # type: ignore[union-attr]
                if dependency == item["id"]:
                    self.finding("dependency-cycle", "error", path, f"{item['id']} depends on itself")
                elif dependency not in by_id and dependency in self.archived:
                    if self.archived[dependency] == "dropped" and item["status"] not in RESOLVED:
                        self.finding("depends-on-dropped", "warning", path, f"depends on {dependency}, which was dropped")
                    elif self.archived[dependency] == "unknown" and item["status"] not in RESOLVED:
                        self.finding("unknown-dependency-status", "warning", path, f"depends on {dependency}, whose resolved status is not recorded in roadmap.md; confirm it from delivery evidence")
                elif dependency not in by_id:
                    self.finding("missing-dependency", "error", path, f"depends on {dependency}, which does not exist")
                elif all(other["status"] == "dropped" for other in by_id[dependency]) and item["status"] not in RESOLVED:
                    self.finding("depends-on-dropped", "warning", path, f"depends on {dependency}, which was dropped")
            wanted = self.complete if item["status"] in RESOLVED else self.specs
            if item["status"] in STATUSES and path.parent != wanted and not self.preserve_paths:
                where = "specs/complete/" if wanted == self.complete else "specs/"
                self.finding("misplaced-item", "error", path, f"a {item['status']} item belongs in {where}", repairable=True)
            self.check_tracking(item, path)
        self.check_cycles(by_id)
        self.check_links()

    def check_tracking(self, item: dict[str, object], path: Path) -> None:
        delivery: list[str] = item["delivery"]  # type: ignore[assignment]
        if item["status"] == "complete" and not delivery:
            self.finding("complete-without-delivery", "warning", path, "marked complete but records no delivery reference")
        if item["status"] in ("proposed", "ready") and delivery:
            self.finding("status-behind-delivery", "warning", path, f"status is {item['status']} but delivery references exist; confirm the status")
        for reference in delivery:
            if COMMIT.match(reference) and not self.commit_exists(reference):
                self.finding("unresolved-delivery-ref", "warning", path, f"delivery commit {reference} is not in this repository")

    def commit_exists(self, reference: str) -> bool:
        """True when Git confirms the commit, and also when Git cannot answer, so absence of Git is never a finding."""
        try:
            result = git(self.repo, "cat-file", "-e", f"{reference}^{{commit}}")
        except (OSError, subprocess.SubprocessError):
            return True
        if result.returncode == 0:
            return True
        return git(self.repo, "rev-parse", "--git-dir").returncode != 0

    def check_cycles(self, by_id: dict[str, list[dict[str, object]]]) -> None:
        graph = {identity: [d for d in group[0]["depends_on"] if d in by_id and d != identity] for identity, group in by_id.items()}  # type: ignore[union-attr]
        state: dict[str, int] = {}
        reported: set[tuple[str, ...]] = set()

        def visit(node: str, trail: list[str]) -> None:
            state[node] = 1
            trail.append(node)
            for nxt in graph[node]:
                if state.get(nxt) == 1:
                    cycle = trail[trail.index(nxt):]
                    start = cycle.index(min(cycle))
                    key = tuple(cycle[start:] + cycle[:start])
                    if key not in reported:
                        reported.add(key)
                        self.finding("dependency-cycle", "error", by_id[key[0]][0]["_path"], "dependency cycle: " + " -> ".join([*key, key[0]]))  # type: ignore[arg-type]
                elif state.get(nxt) is None:
                    visit(nxt, trail)
            trail.pop()
            state[node] = 2

        for node in sorted(graph):
            if node not in state:
                visit(node, [])

    def archived_ids(self) -> dict[str, str]:
        """Reserve linked historical ids; only explicit live Delivered records establish their status.

        Archived files are never opened. A bare history link has unknown status, even when its target
        exists. The overview retains each resolved id after any referring Prospective Spec is archived.
        """
        found: dict[str, str] = {}
        for document in self.documents():
            for target, _ in local_links(read_text(document)):
                identity = self.filename_id(Path(target).name)
                if identity and inside(document.parent / target, self.archive):
                    found.setdefault(identity, "unknown")
        overview = self.overview
        if overview in self.documents():
            records: dict[str, set[str]] = {}
            for match in DELIVERED.finditer(delivered_section(read_text(overview))):
                target, status = match.groups()
                identity = self.filename_id(Path(target).name)
                if identity and inside(overview.parent / target, self.archive):
                    records.setdefault(identity, set()).add(status)
            for identity, statuses in records.items():
                found[identity] = next(iter(statuses)) if len(statuses) == 1 else "unknown"
                if len(statuses) > 1:
                    self.finding("conflicting-archived-status", "error", overview, f"{identity} has conflicting resolved statuses in Delivered")
        return found

    def check_links(self) -> None:
        for document in self.documents():
            for target, _ in local_links(read_text(document)):
                resolved = (document.parent / target).resolve()
                if inside(resolved, self.archive):
                    continue  # traceability into release history, which no command reads
                if not resolved.exists():
                    fixable = resolved.name in self.locations()
                    self.finding("broken-link", "error", document, f"link target {target} does not exist", repairable=fixable)

    def locations(self) -> dict[str, Path]:
        names: dict[str, list[Path]] = {}
        for item in self.items:
            names.setdefault(item["_path"].name, []).append(item["_path"])  # type: ignore[union-attr]
        return {name: paths[0] for name, paths in names.items() if len(paths) == 1}

    def unblocked(self) -> list[str]:
        status = {str(item["id"]): item["status"] for item in self.items}
        broken = {f["path"] for f in self.findings if f["severity"] == "error"}
        return [
            str(item["id"])
            for item in self.items
            if item["status"] in ("proposed", "ready")
            and item["path"] not in broken
            and not item["blockers"]
            and all(status.get(d) == "complete" or (d not in status and self.archived.get(d) == "complete") for d in item["depends_on"])  # type: ignore[union-attr]
        ]

    def next_id(self) -> str:
        """One past the highest id in use or recorded in roadmap history, so an archived id is never reused."""
        found = [m.group(1) for item in self.items if (m := ID.match(str(item["id"])))]
        found += [identity[3:] for identity in self.archived]
        overview = self.overview
        if overview.is_file() and self.safe(overview):
            pattern = r"\bps-(\d{2,})\b" if self.legacy_ids else r"\bps-(\d{3,})\b"
            found += re.findall(pattern, read_text(overview), re.I if self.legacy_ids else 0)
        width = max([3, *(len(number) for number in found)])
        return f"ps-{(max(int(number) for number in found) + 1 if found else 1):0{width}d}"

    def payload(self, command: str) -> dict[str, object]:
        errors = [f for f in self.findings if f["severity"] == "error"]
        return {
            "COMMAND": command,
            "REPO_ROOT": self.repo.as_posix(),
            "ROADMAP_ROOT": self.root.as_posix(),
            "ROADMAP_FILE": display(self.overview, self.root),
            "PRESERVE_PATHS": self.preserve_paths,
            "ROOT_SOURCE": self.source,
            "EXTERNAL": not inside(self.root, self.repo),
            "PRESENT": self.present,
            "ITEMS": [{k: v for k, v in item.items() if not k.startswith("_")} for item in self.items],
            "FINDINGS": sorted(self.findings, key=lambda f: (str(f["path"]), str(f["code"]), str(f["message"]))),
            "UNBLOCKED": self.unblocked() if self.present else [],
            "ARCHIVED": dict(sorted(self.archived.items())),
            "SUPPORTING": [{"path": display(path, self.root), "id": identity} for path, identity in sorted(self.supporting.items())],
            "NEXT_ID": self.next_id(),
            "OK": not errors,
        }


def local_links(text: str) -> list[tuple[str, str]]:
    """(path, anchor) for each relative Markdown link; URLs, anchors-only and absolute paths are skipped."""
    found = []
    for match in LINK.finditer(text):
        raw = match.group(1)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw) or raw.startswith(("#", "/")):
            continue
        path, _, anchor = raw.partition("#")
        if path:
            found.append((path, anchor))
    return found


def plan_repairs(roadmap: Roadmap) -> tuple[list[dict[str, str]], dict[Path, Path], dict[Path, str], list[str]]:
    """Moves for misplaced items and rewritten text for files whose local links need a mechanical fix."""
    root = roadmap.root
    moves: dict[Path, Path] = {}
    refused: list[str] = []
    for finding in roadmap.findings:
        if finding["code"] != "misplaced-item":
            continue
        source = root / str(finding["path"])
        item = next(i for i in roadmap.items if i["_path"] == source)
        folder = roadmap.complete if item["status"] in RESOLVED else roadmap.specs
        destination = folder / source.name
        if destination.exists():
            refused.append(f"{display(source, root)}: {display(destination, root)} already exists")
            continue
        moves[source] = destination
    destinations = set(moves.values())
    by_name = {name: moves.get(path, path) for name, path in roadmap.locations().items()}

    def exists_after(path: Path) -> bool:
        return path in destinations or (path.exists() and path not in moves)

    rewrites: dict[Path, str] = {}
    for document in roadmap.documents():
        final_dir = moves.get(document, document).parent
        text = read_text(document)

        def fix(match: re.Match[str]) -> str:
            raw = match.group(1)
            links = local_links(f"[x]({raw})")
            if not links:
                return match.group(0)
            target, anchor = links[0]
            intended = (document.parent / target).resolve()
            final = moves.get(intended, intended)
            if not exists_after(final):
                if intended.name not in by_name:
                    return match.group(0)
                final = by_name[intended.name]
            new = Path(os.path.relpath(final, final_dir)).as_posix() + (f"#{anchor}" if anchor else "")
            return match.group(0) if new == raw else match.group(0).replace(f"({raw})", f"({new})")

        updated = LINK.sub(fix, text)
        if updated != text:
            rewrites[document] = updated
    final_rewrites = {moves.get(path, path): text for path, text in rewrites.items()}
    planned = [{"action": "move", "from": display(s, root), "to": display(d, root)} for s, d in sorted(moves.items())]
    planned += [{"action": "relink", "file": display(p, root)} for p in sorted(final_rewrites)]
    return planned, moves, final_rewrites, refused


def apply_repairs(root: Path, moves: dict[Path, Path], rewrites: dict[Path, str]) -> None:
    for path in [*moves, *moves.values(), *rewrites]:
        guard(root, path)
    for source, destination in moves.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
    for path, text in rewrites.items():
        write_text(root, path, text)


def guard(root: Path, path: Path) -> None:
    if path.is_symlink() or not inside(path, root):
        raise UsageError(f"refusing to write {path.as_posix()}: outside the roadmap root {root.as_posix()}")


def archive_relinks(
    roadmap: Roadmap, archived: dict[Path, Path], release: str = "", *, statuses: dict[Path, str]
) -> dict[Path, str]:
    """New text for each live roadmap document whose links name a file release archival moves.

    `archived` maps each original file to its archived copy; `statuses` comes from live items or the
    release journal, never archived content. Existing prose is preserved except for moved link targets.
    Every archived item also gets a permanent, explicit-status Delivered record in roadmap.md, even
    when another live document links to it. Repeating the call changes nothing.
    """
    moving = {path.resolve() for path in archived}
    targets = {path.resolve(): destination for path, destination in archived.items()}
    rewrites: dict[Path, str] = {}
    for document in roadmap.documents():
        if document.resolve() in moving:
            continue
        text = read_text(document)

        def relink(match: re.Match[str], document: Path = document) -> str:
            links = local_links(f"[x]({match.group(1)})")
            if not links:
                return match.group(0)
            target, anchor = links[0]
            resolved = (document.parent / target).resolve()
            destination = targets.get(resolved)
            if destination is None:
                return match.group(0)
            new = Path(os.path.relpath(destination, document.parent)).as_posix() + (f"#{anchor}" if anchor else "")
            return match.group(0).replace(f"({match.group(1)})", f"({new})")

        updated = LINK.sub(relink, text)
        if updated != text:
            rewrites[document] = updated
    overview = roadmap.overview
    if archived:
        guard(roadmap.root, overview)
        text = rewrites.get(overview, read_text(overview) if overview.is_file() else "# Roadmap\n")
        newline = "\r\n" if "\r\n" in text else "\n"
        suffix = f"archived with release {release}" if release else "archived"
        recorded = {(overview.parent / match.group(1)).resolve() for match in DELIVERED.finditer(delivered_section(text))}
        lines = []
        for original, destination in sorted(archived.items()):
            if destination.resolve() in recorded:
                continue
            status = statuses.get(original, "unknown")
            status = status if status in RESOLVED else "unknown"
            lines.append(f"- [{destination.stem}]({Path(os.path.relpath(destination, roadmap.root)).as_posix()}) — {status}; {suffix}")
        if lines:
            rewrites[overview] = record_delivered(text, lines, newline)
    return rewrites


def delivered_section(text: str) -> str:
    """The live overview's Delivered section; similar-looking prose elsewhere is not status evidence."""
    heading = re.search(r"^##[ \t]+Delivered[ \t]*\r?$", text, re.M)
    if heading is None:
        return ""
    following = re.search(r"^#{1,2}[ \t]", text[heading.end():], re.M)
    end = heading.end() + following.start() if following else len(text)
    return text[heading.end():end]


def record_delivered(text: str, lines: list[str], newline: str) -> str:
    """Append history lines to the end of the `## Delivered` section, creating it at the end when absent."""
    heading = re.search(r"^##[ \t]+Delivered[ \t]*\r?$", text, re.M)
    block = newline.join(lines) + newline
    if heading is None:
        return text.rstrip("\r\n") + newline + newline + "## Delivered" + newline + newline + block
    following = re.search(r"^#{1,2}[ \t]", text[heading.end():], re.M)
    end = heading.end() + following.start() if following else len(text)
    section = text[heading.end():end].rstrip("\r\n")
    separator = "" if section.strip() else newline
    rest = text[end:]
    return text[: heading.end()] + section + newline + separator + block + (newline + rest if rest else "")


def write_text(root: Path, path: Path, text: str) -> None:
    guard(root, path)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "repair", "locate"))
    parser.add_argument("id", nargs="?", default="")
    parser.add_argument("--root", default="", help="roadmap root (default: devspark.json roadmap.root, else .devspark.work/roadmap)")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--apply", action="store_true", help="repair: perform the planned mechanical repairs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        repo = repository_root(args.repo_root)
        root, source = resolve_root(repo, args.root)
        roadmap = Roadmap(repo, root, source)
        payload = roadmap.payload(args.command)
        code = 0 if payload["OK"] else 1
        if args.command == "locate":
            identity = args.id.strip().lower()
            requested_supporting = ""
            if identity.endswith(".md"):
                name = Path(identity).name
                supporting = [path for path in roadmap.supporting if path.name.lower() == name]
                if len(supporting) == 1:
                    requested_supporting = display(supporting[0], root)
                    identity = roadmap.supporting[supporting[0]]
                else:
                    identity = roadmap.filename_id(name) or identity
            identity = canonical_id(identity, roadmap.legacy_ids)
            if not identity:
                raise UsageError("locate needs a Prospective Spec id, for example ps-001")
            matches = [i for i in payload["ITEMS"] if i["id"] == identity]  # type: ignore[union-attr]
            status = {i["id"]: i["status"] for i in payload["ITEMS"]}  # type: ignore[union-attr]
            item = matches[0] if len(matches) == 1 else None
            payload["ITEM"] = item
            payload["SUPPORTING"] = [
                entry for entry in payload["SUPPORTING"] if entry["id"] == identity  # type: ignore[union-attr]
            ]
            payload["REQUESTED_SUPPORTING"] = requested_supporting
            payload["DEPENDENCIES"] = {
                d: status.get(d, roadmap.archived.get(d, "missing")) for d in (item or {}).get("depends_on", [])
            }
            payload["FINDINGS"] = [f for f in payload["FINDINGS"] if item and f["path"] == item["path"]]  # type: ignore[union-attr]
            payload["OK"] = item is not None and not any(f["severity"] == "error" for f in payload["FINDINGS"])  # type: ignore[union-attr]
            code = 0 if payload["OK"] else 1
            if len(matches) > 1:
                payload["ERROR"] = f"{identity} is not unique in this roadmap"
            elif not item:
                payload["ERROR"] = f"{identity} was not found under {root.as_posix()}"
        elif args.command == "repair":
            planned, moves, rewrites, refused = plan_repairs(roadmap) if roadmap.present else ([], {}, {}, [])
            payload["REPAIRS"] = planned
            payload["REFUSED"] = refused
            payload["APPLIED"] = False
            if args.apply and planned:
                apply_repairs(root, moves, rewrites)
                after = Roadmap(repo, root, source).payload("repair")
                payload.update({k: after[k] for k in ("ITEMS", "FINDINGS", "UNBLOCKED", "NEXT_ID", "OK")})
                payload["APPLIED"] = True
            code = 0 if payload["OK"] else 1
    except UsageError as error:
        payload, code = {"COMMAND": args.command, "OK": False, "ERROR": str(error)}, 2

    if args.json:
        print(json.dumps(payload, separators=(",", ":")))
    else:
        print_report(payload)
    return code


def print_report(payload: dict[str, object]) -> None:
    if "ROADMAP_ROOT" not in payload:
        print(f"roadmap-check: {payload.get('ERROR')}", file=sys.stderr)
        return
    print(f"roadmap {payload['COMMAND']}: {payload['ROADMAP_ROOT']} ({payload['ROOT_SOURCE']}{', external' if payload['EXTERNAL'] else ''})")
    if not payload["PRESENT"]:
        print("  no roadmap at this location (optional; nothing to check)")
        return
    for item in payload["ITEMS"]:  # type: ignore[union-attr]
        print(f"  {item['id'] or '?'} [{item['status'] or '?'}] {item['title']}")
    for finding in payload["FINDINGS"]:  # type: ignore[union-attr]
        print(f"  {finding['severity'].upper()} {finding['code']}: {finding['path']} - {finding['message']}")
    for repair in payload.get("REPAIRS", []):  # type: ignore[union-attr]
        detail = f"{repair['from']} -> {repair['to']}" if repair["action"] == "move" else repair["file"]
        print(f"  {'repaired' if payload.get('APPLIED') else 'would repair'} ({repair['action']}): {detail}")
    for refusal in payload.get("REFUSED", []):  # type: ignore[union-attr]
        print(f"  NOT REPAIRED: {refusal}")
    if payload.get("ERROR"):
        print(f"  {payload['ERROR']}")
    print(f"  unblocked: {', '.join(payload['UNBLOCKED']) or 'none'}; next id: {payload['NEXT_ID']}")  # type: ignore[arg-type]
    print(f"  result: {'OK' if payload['OK'] else 'NOT OK'}")


if __name__ == "__main__":
    raise SystemExit(main())
