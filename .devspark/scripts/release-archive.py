#!/usr/bin/env python3
# DevSpark - (c) 2026 Make Bold Solutions. Source: https://dev.makeboldspark.com
"""Archive completed .devspark.work artifacts into .archive/{YYYY-MM-DD}/ for a formal release.

Commands:
  plan      Read-only inventory of what a release would archive, keep, or need a decision on.
  apply     Journal the moves in a manifest, move the files, stage the result, then validate.
  validate  Check the manifest against the archive and the workspace.

Eligibility is decided by release-context.py's classifier (one definition, not a second one). This
script only performs the move the release contract describes: deterministic, never overwriting
archived evidence, and resumable after an interruption.

The archive is this repository's `.archive/` unless `archive.root` in .devspark.work/devspark.json (or
--archive-root) names an existing folder outside the repository, for teams that keep history elsewhere.
Files bound for an external archive are copied and hash-checked before the original is removed.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WORK = ".devspark.work"
ARCHIVE = ".archive"
DEFAULT_SWEPT_CATEGORIES = ("audit", "metrics", "pr-review", "telemetry")
# Directories under .devspark.work/ that hold live framework configuration or pre-spec backlog.
LIVE_DIRECTORIES = {"commands", "scripts", "extensions", "intake", "drafts", "releases", "roadmap"}
ROADMAP = "roadmap"
MAX_FILE_BYTES = 1_000_000
REPORT_LIMIT = 200


class ArchiveError(Exception):
    """A precondition failed; nothing was changed."""


def load_release_context():
    path = Path(__file__).with_name("release-context.py")
    spec = importlib.util.spec_from_file_location("devspark_release_context", path)
    if spec is None or spec.loader is None:
        raise ArchiveError(f"cannot load the release classifier at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RC = load_release_context()


def roadmap_in_use(repo: Path) -> bool:
    """A default roadmap folder or a `roadmap` section in devspark.json; otherwise release runs exactly as before."""
    if (repo / WORK / ROADMAP).is_dir():
        return True
    try:
        data = json.loads((repo / WORK / "devspark.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and "roadmap" in data


def load_roadmap_checker():
    """Loaded only when a roadmap is in use, so a repository without one runs exactly as before."""
    path = Path(__file__).with_name("roadmap-check.py")
    spec = importlib.util.spec_from_file_location("devspark_roadmap_check", path)
    if spec is None or spec.loader is None:
        raise ArchiveError(f"cannot load the roadmap checker at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=False, capture_output=True, text=True, encoding="utf-8", timeout=120
    )


def git_lines(repo: Path, *args: str) -> list[str]:
    result = run_git(repo, *args)
    return [line for line in result.stdout.splitlines() if line] if result.returncode == 0 else []


def tracked_paths(repo: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo, check=False, capture_output=True, timeout=120
    )
    if result.returncode != 0:
        return set()
    return {part.decode("utf-8", "surrogateescape") for part in result.stdout.split(b"\0") if part}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_under(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix())


def rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def core_version(text: str) -> tuple[int, int, int]:
    match = SEMVER.match(text.lstrip("v"))
    if not match:
        raise ArchiveError(f"'{text}' is not a semantic version (expected MAJOR.MINOR.PATCH)")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def validate_version(repo: Path, version: str, resuming: bool) -> None:
    core = core_version(version)
    if run_git(repo, "rev-parse", "-q", "--verify", f"refs/tags/v{version}").returncode == 0:
        raise ArchiveError(f"tag v{version} already exists: that release is already cut, so nothing may be archived into it")
    last_tag = RC.git(repo, "describe", "--tags", "--abbrev=0")
    if last_tag and not resuming and core <= core_version(last_tag):
        raise ArchiveError(f"version {version} is not newer than the previous release {last_tag}")


@dataclass(frozen=True)
class ArchiveLocation:
    """Where release writes: this repository's `.archive/`, or an existing folder outside it.

    The journal records paths relative to the repository for `.archive/`, so its manifest keeps its
    shape, and relative to the archive folder for an external one, so the journal survives a re-clone.
    """

    root: Path
    repo: Path
    external: bool
    source: str

    def locate(self, recorded: str) -> Path:
        return (self.root if self.external else self.repo) / recorded

    def record(self, path: Path) -> str:
        return rel(self.root if self.external else self.repo, path)

    def show(self, path: Path) -> str:
        return path.as_posix() if self.external else rel(self.repo, path)


def configured_archive_root(repo: Path) -> str:
    config = repo / WORK / "devspark.json"
    if not config.is_file():
        return ""
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"release-archive: warning: {config.as_posix()} is not valid JSON ({error}); using the default archive", file=sys.stderr)
        return ""
    section = data.get("archive") if isinstance(data, dict) else None
    if section is None:
        return ""
    if not isinstance(section, dict):
        raise ArchiveError("devspark.json 'archive' must be an object")
    if "root" not in section:
        return ""
    root = section["root"]
    if not isinstance(root, str) or not root.strip():
        raise ArchiveError("devspark.json 'archive.root' must be a non-empty string")
    return root.strip()


def resolve_archive_root(repo: Path, explicit: str) -> ArchiveLocation:
    """The archive folder: --archive-root, else `archive.root`, else `.archive/`.

    It is `.archive/` (or a folder inside it) or an existing folder outside the repository. Any other
    folder inside the repository would put history where scans and Knowledge tooling read it as live content.
    """
    if explicit:
        value, source = explicit, "argument"
    else:
        value = configured_archive_root(repo)
        source = "config" if value else "default"
        value = value or ARCHIVE
    base = repo.resolve()
    path = Path(os.path.expanduser(value))
    resolved = (path if path.is_absolute() else repo / path).resolve()
    if resolved == base or base.is_relative_to(resolved):
        raise ArchiveError(f"archive root {value!r} must be a dedicated archive folder, not the repository root or above it")
    if resolved.is_relative_to(base):
        if resolved != base / ARCHIVE and not resolved.is_relative_to(base / ARCHIVE):
            raise ArchiveError(
                f"archive root {value!r} is inside this repository but outside {ARCHIVE}/, where scans and Knowledge "
                f"tooling would read archived history as live content; use {ARCHIVE}/ or a folder outside the repository"
            )
        return ArchiveLocation(repo / resolved.relative_to(base), repo, False, source)
    if not resolved.is_dir():
        raise ArchiveError(f"archive root {value!r} is not an existing folder; create it, or clone the repository that holds it, then rerun")
    return ArchiveLocation(resolved, repo, True, source)


def archive_date_for(location: ArchiveLocation, version: str, explicit: str) -> str:
    if explicit and not DATE.match(explicit):
        raise ArchiveError(f"--date '{explicit}' must be YYYY-MM-DD")
    existing = sorted(
        path.parent.parent.name for path in location.root.glob(f"*/release/archive-manifest-{version}.json")
    )
    if len(existing) > 1:
        raise ArchiveError(f"release {version} has manifests in more than one archive folder: {', '.join(existing)}")
    if explicit and existing and explicit != existing[0]:
        raise ArchiveError(f"release {version} is already journaled under {existing[0]}, not {explicit}")
    return explicit or (existing[0] if existing else datetime.date.today().isoformat())


def swept_categories(repo: Path) -> list[str]:
    registry = repo / ".knowledge" / "taxonomy-registry.json"
    try:
        mappings = json.loads(registry.read_text(encoding="utf-8")).get("mappings", [])
    except (OSError, ValueError):
        return list(DEFAULT_SWEPT_CATEGORIES)
    prefix = f"{WORK}/"
    return sorted(
        {
            item["pathPattern"][len(prefix) : -3]
            for item in mappings
            if isinstance(item, dict)
            and item.get("lifecycle") == "archive-on-release"
            and str(item.get("pathPattern", "")).startswith(prefix)
            and str(item.get("pathPattern", "")).endswith("/**")
        }
    )


def is_operational_file(name: str) -> bool:
    return name.startswith(".") or name.lower() == "readme.md"


def manifest_path(location: ArchiveLocation, date: str, version: str) -> Path:
    return location.root / date / "release" / f"archive-manifest-{version}.json"


def read_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ArchiveError(f"manifest {path.as_posix()} is unreadable: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ArchiveError(f"manifest {path.as_posix()} does not have an items list")
    return data


def write_manifest(path: Path, data: dict[str, object]) -> bool:
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)
    return True


def uncommitted_paths(repo: Path) -> set[str]:
    """Tracked workspace files that differ from HEAD, staged or not."""
    result = run_git(repo, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=no", "--", WORK)
    if result.returncode != 0:
        return set()
    return {entry[3:] for entry in result.stdout.split("\0") if len(entry) > 3}


class Inventory:
    """Everything the release needs to know about the workspace, computed once."""

    def __init__(
        self, repo: Path, version: str, date: str, location: ArchiveLocation, include_roadmap: bool = False
    ) -> None:
        self.repo = repo
        self.version = version
        self.date = date
        self.location = location
        self.include_roadmap = include_roadmap
        self.archive_root = location.record(location.root / date)
        self.manifest_file = manifest_path(location, date, version or "unversioned")
        self.journal = read_manifest(self.manifest_file) if version else {"items": []}
        self.tracked = tracked_paths(repo)
        # Content that leaves the repository must match what Git already holds.
        self.uncommitted = uncommitted_paths(repo) if location.external else set()
        self.last_tag = RC.git(repo, "describe", "--tags", "--abbrev=0")
        self.window = set(git_lines(repo, "rev-list", f"{self.last_tag}..HEAD")) if self.last_tag else set()
        self.to_archive: list[dict[str, object]] = []
        self.resuming: list[dict[str, object]] = []
        self.in_flight: list[dict[str, object]] = []
        self.needs_decision: list[dict[str, str]] = []
        self.retained: list[str] = []
        self.collisions: list[dict[str, str]] = []
        self.already_archived: list[str] = []
        self.roadmap_completed: list[str] = []
        self.roadmap_checker = None
        self.roadmap_root: Path | None = None
        self.roadmap_external = False
        self.roadmap_error = ""
        self.roadmap_notice = ""
        self.roadmap_area = ""
        self.roadmap_relink: list[str] = []
        self.roadmap_relinked: list[str] = []
        self.build()

    def destination(self, original: str) -> str:
        return f"{self.archive_root}/{original[len(WORK) + 1:]}"

    def origin_evidence(self, original: str) -> dict[str, object]:
        commit = (git_lines(self.repo, "log", "-1", "--format=%H", "--", original) or [""])[0]
        in_window: bool | None = (commit in self.window) if (commit and self.last_tag) else None
        return {"last_commit": commit, "in_release_window": in_window}

    def unit(
        self, kind: str, original: str, files: list[Path], hashes: dict[str, str] | None = None, archived: str = ""
    ) -> dict[str, object]:
        root = self.repo / original
        entries = []
        for path in files:
            relative = path.name if root.is_file() else rel(root, path)
            entries.append({"path": relative, "sha256": (hashes or {}).get(relative) or sha256_of(path)})
        return {
            "kind": kind,
            "original": original,
            "archived": archived or self.destination(original),
            "is_file": root.is_file(),
            "files": entries,
            **self.origin_evidence(original),
        }

    def file_destination(self, unit: dict[str, object], relative: str) -> Path:
        base = self.location.locate(str(unit["archived"]))
        return base if unit["is_file"] else base / relative

    def check_collisions(self, unit: dict[str, object]) -> bool:
        """True when every file can move: its destination is absent or already holds identical bytes."""
        clean = True
        for entry in unit["files"]:  # type: ignore[union-attr]
            destination = self.file_destination(unit, entry["path"])
            if destination.exists() and (not destination.is_file() or sha256_of(destination) != entry["sha256"]):
                self.collisions.append(
                    {
                        "path": str(unit["original"]) if unit["is_file"] else f"{unit['original']}/{entry['path']}",
                        "archived": self.location.show(destination),
                        "reason": "a different file already exists at the archive destination; nothing was overwritten",
                    }
                )
                clean = False
        return clean

    def build(self) -> None:
        work = self.repo / WORK
        if not work.is_dir():
            return
        journaled = {str(item["original"]): item for item in self.journal["items"]}  # type: ignore[index]
        self.collect_resumable(journaled)
        for unit_candidate in self.candidates(set(journaled)):
            self.classify(unit_candidate)
        try:
            self.collect_roadmap(set(journaled))
        except Exception as error:  # noqa: BLE001 - an unusable roadmap must never block the release
            self.roadmap_error = f"roadmap skipped, nothing in it was changed: {error}"
        self.collect_retained()
        self.to_archive.sort(key=lambda item: str(item["original"]))
        self.resuming.sort(key=lambda item: str(item["original"]))

    def collect_resumable(self, journaled: dict[str, dict[str, object]]) -> None:
        """A journaled bundle that still has files was interrupted mid-move: finish it from the
        journal's recorded hashes rather than re-classifying a half-moved bundle."""
        for original, item in sorted(journaled.items()):
            root = self.repo / original
            leftovers = files_under(root)
            if not leftovers:
                self.already_archived.append(original)
                continue
            recorded = {entry["path"]: entry["sha256"] for entry in item["files"]}  # type: ignore[index]
            leftover_rel = {(path.name if root.is_file() else rel(root, path)): path for path in leftovers}
            unknown = sorted(set(leftover_rel) - set(recorded))
            if unknown:
                self.needs_decision.append(
                    {
                        "path": original,
                        "reason": f"files appeared after this bundle was journaled: {', '.join(unknown[:5])}",
                        "action": "review the new files, then archive them by hand or move them out of the archived bundle",
                    }
                )
                continue
            changed = sorted(name for name, path in leftover_rel.items() if sha256_of(path) != recorded[name])
            if changed:
                self.collisions.append(
                    {
                        "path": original,
                        "archived": str(item["archived"]),
                        "reason": f"files changed after being journaled: {', '.join(changed[:5])}",
                    }
                )
                continue
            resumed = {key: item[key] for key in ("kind", "original", "archived", "is_file", "last_commit", "in_release_window")}
            resumed["files"] = [{"path": name, "sha256": recorded[name]} for name in sorted(leftover_rel)]
            if self.check_collisions(resumed):
                self.resuming.append(resumed)

    def candidates(self, skip: set[str]) -> list[tuple[str, str, Path]]:
        work = self.repo / WORK
        found: list[tuple[str, str, Path]] = []
        for category, kind in (("specs", "spec"), ("quickfixes", "quickfix")):
            root = work / category
            if root.is_dir():
                found += [
                    (kind, rel(self.repo, child), child)
                    for child in sorted(root.iterdir(), key=lambda p: p.as_posix())
                    if rel(self.repo, child) not in skip and not (child.is_file() and is_operational_file(child.name))
                ]
        for category in swept_categories(self.repo):
            for path in files_under(work / category):
                if is_operational_file(path.name) or rel(self.repo, path) in skip:
                    continue
                found.append(("work-product", rel(self.repo, path), path))
        return found

    def classify(self, candidate: tuple[str, str, Path], archived: str = "", roadmap_status: str = "") -> None:
        kind, original, path = candidate
        files = files_under(path)
        if not files:
            return
        if kind in ("spec", "quickfix"):
            verdict = RC.classify_bundle(self.repo, path)
            if not verdict["archive_eligible"]:
                self.in_flight.append({"path": original, "blockers": verdict["blockers"]})
                if verdict["orphan_candidate"]:
                    self.needs_decision.append(
                        {
                            "path": original,
                            "reason": "not Complete and its branch no longer exists (orphaned, abandoned or unrecorded completion)",
                            "action": "owner decides: record real completion evidence and linkage, keep it in flight, or retire it by explicit decision",
                        }
                    )
                return
        untracked = sorted(rel(self.repo, p) for p in files if rel(self.repo, p) not in self.tracked)
        if untracked:
            self.needs_decision.append(
                {
                    "path": original,
                    "reason": f"{len(untracked)} file(s) are not tracked by Git, so ownership and history cannot be confirmed (e.g. {untracked[0]})",
                    "action": "commit the files (or remove them deliberately), then rerun",
                }
            )
            return
        changed = sorted(item for item in self.uncommitted if item == original or item.startswith(f"{original}/"))
        if changed:
            self.needs_decision.append(
                {
                    "path": original,
                    "reason": f"{len(changed)} file(s) have uncommitted changes, and the archive is outside this repository, so Git would not keep what leaves it (e.g. {changed[0]})",
                    "action": "commit the changes, then rerun",
                }
            )
            return
        unit = self.unit(kind, original, files, archived=archived)
        if kind == "prospective-spec":
            unit["roadmap_status"] = roadmap_status
        if self.check_collisions(unit):
            self.to_archive.append(unit)

    def collect_roadmap(self, skip: set[str]) -> None:
        """Resolved Prospective Specs staged in the roadmap's specs/complete/. They are reported on every
        run and archived only when the release was asked to include them. Any roadmap problem is reported
        and skipped: planning never blocks a release."""
        if not roadmap_in_use(self.repo):
            return
        checker = load_roadmap_checker()
        root, source = checker.resolve_root(self.repo, "")
        self.roadmap_checker, self.roadmap_root = checker, root
        if not checker.inside(root, self.repo):
            self.roadmap_external = True
            self.roadmap_notice = (
                f"the roadmap at {root.as_posix()} is outside this repository; release never reads, moves or "
                "rewrites it. Archive its completed Prospective Specs from the planning repository when its owner authorizes it."
            )
            return
        if self.repo / WORK in root.parents:
            self.roadmap_area = root.relative_to(self.repo / WORK).parts[0]
        complete = root / "specs" / "complete"
        if not complete.is_dir():
            return
        roadmap = checker.Roadmap(self.repo, root, source)
        if roadmap.preserve_paths:
            self.roadmap_notice = "the roadmap layout preserves published paths; its Prospective Specs remain in place"
            return
        items = {item["_path"]: item for item in roadmap.items}
        errors = {finding["path"] for finding in roadmap.findings if finding["severity"] == "error"}
        ready: list[tuple[str, Path, str]] = []
        for path in sorted(complete.glob("*.md"), key=lambda p: p.as_posix()):
            original = rel(self.repo, path)
            if path.name.lower() == "readme.md" or original in skip or path in roadmap.supporting:
                continue
            item = items.get(path)
            if not roadmap.safe(path):
                reason = "a symbolic link or a file outside the roadmap root; release never follows or moves it"
            elif item is None or item["path"] in errors or item["status"] not in checker.RESOLVED:
                reason = "a staged Prospective Spec is not a cleanly resolved roadmap item"
            else:
                self.roadmap_completed.append(original)
                ready.append((original, path, f"{self.archive_root}/{ROADMAP}/{rel(root, path)}"))
                continue
            self.needs_decision.append(
                {"path": original, "reason": reason, "action": "run roadmap-check, correct the item, then rerun"}
            )
        if not (self.include_roadmap and ready):
            return
        if self.location.external:
            self.roadmap_notice = (
                "roadmap archival needs the archive inside this repository, and the archive root is outside it, so the "
                "resolved Prospective Specs stay in specs/complete/ and nothing in the roadmap was changed; "
                f"rerun with --archive-root {ARCHIVE} to archive them"
            )
            return
        statuses = {path: str(items[path]["status"]) for _, path, _ in ready}
        relinks = checker.archive_relinks(
            roadmap, {path: self.repo / archived for _, path, archived in ready}, self.version, statuses=statuses
        )
        documents = sorted(rel(self.repo, path) for path in relinks)
        dirty = git_lines(self.repo, "status", "--porcelain", "--", *documents, *(original for original, _, _ in ready))
        if dirty:
            for original, _, _ in ready:
                self.needs_decision.append(
                    {
                        "path": original,
                        "reason": "roadmap files this archival would move or relink have uncommitted changes",
                        "action": "commit or discard the roadmap changes, then rerun; the rest of the release is unaffected",
                    }
                )
            return
        self.roadmap_relink = documents
        for original, path, archived in ready:
            self.classify(("prospective-spec", original, path), archived=archived, roadmap_status=statuses[path])

    def collect_retained(self) -> None:
        work = self.repo / WORK
        swept = set(swept_categories(self.repo)) | {"specs", "quickfixes"}
        for child in sorted(work.iterdir(), key=lambda p: p.as_posix()):
            name = child.name
            if name in swept:
                self.retained += [
                    rel(self.repo, p) for p in files_under(child) if is_operational_file(p.name)
                ]
            elif child.is_file() or name in LIVE_DIRECTORIES or name == self.roadmap_area or (child / "commands").is_dir():
                self.retained.append(rel(self.repo, child))
            else:
                self.needs_decision.append(
                    {
                        "path": rel(self.repo, child),
                        "reason": "uncategorized work area: no taxonomy lifecycle says whether it belongs to a release",
                        "action": "add a lifecycle in .knowledge/taxonomy-registry.json, or decide per file",
                    }
                )

    def stale_references(self, originals: list[str], exclude_prefixes: tuple[str, ...]) -> tuple[list[dict[str, object]], bool]:
        return find_stale_references(self.repo, self.tracked, originals, exclude_prefixes)


def find_stale_references(
    repo: Path, tracked: set[str], originals: list[str], exclude_prefixes: tuple[str, ...]
) -> tuple[list[dict[str, object]], bool]:
    """Tracked text outside the archive that still names a path this release moved."""
    if not originals:
        return [], False
    pattern = re.compile("|".join(re.escape(item) for item in sorted(originals)) + r"(?![\w-])")
    found: list[dict[str, object]] = []
    for path in sorted(tracked):
        if path.startswith((f"{ARCHIVE}/", ".git/", *exclude_prefixes)) or Path(path).suffix.lower() not in RC.TEXT_EXTENSIONS:
            continue
        absolute = repo / path
        try:
            if not absolute.is_file() or absolute.stat().st_size > MAX_FILE_BYTES:
                continue
            lines = absolute.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, start=1):
            match = pattern.search(line)
            if match:
                found.append({"file": path, "line": number, "target": match.group(0)})
                if len(found) >= REPORT_LIMIT:
                    return found, True
    return found, False


def result_payload(inventory: Inventory, command: str) -> dict[str, object]:
    originals = [str(unit["original"]) for unit in [*inventory.to_archive, *inventory.resuming]]
    stale, truncated = inventory.stale_references(originals, tuple(f"{original}/" for original in originals))
    def summary(unit: dict[str, object]) -> dict[str, object]:
        return {
            "kind": unit["kind"],
            "original": unit["original"],
            "archived": inventory.location.show(inventory.location.locate(str(unit["archived"]))),
            "files": len(unit["files"]),  # type: ignore[arg-type]
            "last_commit": unit["last_commit"],
            "in_release_window": unit["in_release_window"],
        }

    location = inventory.location
    return {
        "COMMAND": command,
        "RELEASE_VERSION": inventory.version,
        "RELEASE_FROM": inventory.last_tag,
        "ARCHIVE_DATE": inventory.date,
        "ARCHIVE_ROOT": location.show(location.root / inventory.date),
        "ARCHIVE_EXTERNAL": location.external,
        "ARCHIVE_SOURCE": location.source,
        "ARCHIVE_NOTICE": archive_notice(inventory),
        "MANIFEST": location.show(inventory.manifest_file) if inventory.version else "",
        "TO_ARCHIVE": [summary(unit) for unit in inventory.to_archive],
        "RESUMING": [summary(unit) for unit in inventory.resuming],
        "ALREADY_ARCHIVED": sorted(inventory.already_archived),
        "IN_FLIGHT": inventory.in_flight,
        "NEEDS_DECISION": sorted(inventory.needs_decision, key=lambda item: item["path"]),
        "RETAINED": sorted(inventory.retained),
        "COLLISIONS": inventory.collisions,
        "ROADMAP_COMPLETED": inventory.roadmap_completed,
        "ROADMAP_INCLUDED": inventory.include_roadmap,
        "ROADMAP_ROOT": roadmap_display(inventory),
        "ROADMAP_EXTERNAL": inventory.roadmap_external,
        "ROADMAP_RELINK": inventory.roadmap_relink,
        "ROADMAP_NOTICE": inventory.roadmap_notice,
        "ROADMAP_ERROR": inventory.roadmap_error,
        "STALE_REFERENCES": stale,
        "STALE_REFERENCES_TRUNCATED": truncated,
        "READY": not inventory.collisions,
    }


def archive_notice(inventory: Inventory) -> str:
    location = inventory.location
    if not location.external:
        return ""
    return (
        f"archived files are written to {location.show(location.root / inventory.date)}, outside this repository; "
        "commit them in the repository that owns that folder. This repository's commit records only their removal."
    )


def roadmap_display(inventory: Inventory) -> str:
    root = inventory.roadmap_root
    if root is None:
        return ""
    return root.as_posix() if inventory.roadmap_external else rel(inventory.repo, root)


def relink_roadmap(inventory: Inventory, journal: dict[str, object]) -> list[str]:
    """Point live roadmap links at the archived copies of the Prospective Specs this release journaled.

    Computed from the journal, including each resolved status captured before the moves, so an
    interrupted apply finishes the same links and live Delivered records without reading archived items.
    """
    checker, root = inventory.roadmap_checker, inventory.roadmap_root
    if checker is None or root is None or inventory.roadmap_external or inventory.roadmap_error or inventory.location.external:
        return []
    repo = inventory.repo
    archived = {
        repo / str(item["original"]): inventory.location.locate(str(item["archived"]))
        for item in journal["items"]  # type: ignore[union-attr]
        if item.get("kind") == "prospective-spec"
    }
    if not archived:
        return []
    statuses = {
        repo / str(item["original"]): str(item.get("roadmap_status", "unknown"))
        for item in journal["items"]  # type: ignore[union-attr]
        if item.get("kind") == "prospective-spec"
    }
    try:
        roadmap = checker.Roadmap(repo, root, "release")
        rewrites = checker.archive_relinks(roadmap, archived, inventory.version, statuses=statuses)
        for path, text in rewrites.items():
            checker.write_text(root, path, text)
    except Exception as error:  # noqa: BLE001 - the archive is complete; links are reported, never a release blocker
        inventory.roadmap_error = f"archived Prospective Specs, but roadmap links were not rewritten: {error}"
        return []
    return sorted(rel(repo, path) for path in rewrites)


def stage(repo: Path, paths: list[str]) -> None:
    for start in range(0, len(paths), 100):
        run_git(repo, "add", "-A", "--", *paths[start : start + 100])


def relocate(source: Path, destination: Path, expected: str, external: bool) -> None:
    """Move one file into the archive.

    An external archive can sit on another volume or share, so its bytes are copied, hash-checked and
    published under their final name before the original is removed. An interruption leaves the original
    in place, and the journal resumes the move.
    """
    if not external:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            source.unlink()
        else:
            os.replace(source, destination)
        return
    partial = destination.with_name(destination.name + ".partial")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, partial)
            if sha256_of(partial) != expected:
                raise ArchiveError(f"{source.name} no longer matches the plan (it changed or was damaged while copying); the original was kept")
            os.replace(partial, destination)
        source.unlink()
    except OSError as error:
        reason = error.strerror or type(error).__name__
        raise ArchiveError(
            f"could not move {source.name} into the archive ({reason}); the original was kept. Fix the cause and rerun apply to resume"
        ) from error
    finally:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)


def apply_plan(inventory: Inventory) -> list[str]:
    repo = inventory.repo
    location = inventory.location
    units = [*inventory.resuming, *inventory.to_archive]
    known = {str(item["original"]): item for item in inventory.journal["items"]}  # type: ignore[index]
    for unit in units:
        known.setdefault(str(unit["original"]), unit)
    journal = {
        "schema": 1,
        "release": inventory.version,
        "archive_root": inventory.archive_root,
        "release_from": inventory.last_tag,
        "items": [known[key] for key in sorted(known)],
    }
    if location.external:
        journal["location"] = "external"
    try:
        write_manifest(inventory.manifest_file, journal)
    except OSError as error:
        reason = error.strerror or type(error).__name__
        raise ArchiveError(f"cannot write the release journal to the archive ({reason}); nothing was moved") from error

    touched: list[str] = []
    for unit in units:
        original = repo / str(unit["original"])
        for entry in unit["files"]:  # type: ignore[union-attr]
            source = original if unit["is_file"] else original / entry["path"]
            relocate(source, inventory.file_destination(unit, entry["path"]), str(entry["sha256"]), location.external)
        if original.is_dir():
            for directory in sorted((p for p in original.rglob("*") if p.is_dir()), key=lambda p: p.as_posix(), reverse=True):
                if not any(directory.iterdir()):
                    directory.rmdir()
            if not any(original.iterdir()):
                original.rmdir()
        touched.append(str(unit["original"]))
        if not location.external:
            touched.append(str(unit["archived"]))
    if not location.external:
        touched.append(rel(repo, inventory.manifest_file))
    inventory.roadmap_relinked = relink_roadmap(inventory, journal)
    touched += inventory.roadmap_relinked
    stage(repo, touched)
    return [str(unit["original"]) for unit in units]


def validate_archive(location: ArchiveLocation, version: str, date: str) -> dict[str, object]:
    repo = location.repo
    path = manifest_path(location, date, version)
    problems: list[str] = []
    if not path.is_file():
        return {"COMMAND": "validate", "RELEASE_VERSION": version, "OK": False, "PROBLEMS": [f"no manifest at {location.show(path)}"], "ARCHIVED": 0, "STALE_REFERENCES": []}
    manifest = read_manifest(path)
    if manifest.get("release") != version:
        problems.append(f"manifest records release {manifest.get('release')!r}, expected {version!r}")
    originals: list[str] = []
    count = 0
    for item in manifest["items"]:  # type: ignore[union-attr]
        original, archived = str(item["original"]), str(item["archived"])
        originals.append(original)
        for entry in item["files"]:
            count += 1
            was_file = bool(item["is_file"])
            target = location.locate(archived) if was_file else location.locate(archived) / entry["path"]
            source = repo / original if was_file else repo / original / entry["path"]
            if not target.is_file():
                problems.append(f"missing from archive: {location.show(target)}")
            elif sha256_of(target) != entry["sha256"]:
                problems.append(f"archived content differs from the journal: {location.show(target)}")
            if source.exists():
                problems.append(f"still present in the workspace: {rel(repo, source)}")
    stale, truncated = find_stale_references(repo, tracked_paths(repo), originals, ())
    return {
        "COMMAND": "validate",
        "RELEASE_VERSION": version,
        "ARCHIVE_ROOT": location.show(location.root / date),
        "ARCHIVE_EXTERNAL": location.external,
        "MANIFEST": location.show(path),
        "ARCHIVED": count,
        "PROBLEMS": problems,
        "STALE_REFERENCES": stale,
        "STALE_REFERENCES_TRUNCATED": truncated,
        "OK": not problems,
    }


def print_report(payload: dict[str, object]) -> None:
    command = payload["COMMAND"]
    print(f"release-archive {command}: release {payload.get('RELEASE_VERSION') or '(not given)'} -> {payload.get('ARCHIVE_ROOT', '')}")
    for key in ("TO_ARCHIVE", "RESUMING", "MOVED"):
        for item in payload.get(key, []):  # type: ignore[union-attr]
            line = item["original"] if isinstance(item, dict) else item
            print(f"  {key.lower()}: {line}")
    for item in payload.get("ALREADY_ARCHIVED", []):  # type: ignore[union-attr]
        print(f"  already archived: {item}")
    for item in payload.get("IN_FLIGHT", []):  # type: ignore[union-attr]
        print(f"  in flight: {item['path']} ({'; '.join(item['blockers'])})")
    for item in payload.get("NEEDS_DECISION", []):  # type: ignore[union-attr]
        print(f"  NEEDS DECISION: {item['path']} - {item['reason']} -> {item['action']}")
    for item in payload.get("COLLISIONS", []):  # type: ignore[union-attr]
        print(f"  COLLISION: {item['path']} -> {item['archived']} ({item['reason']})")
    for item in payload.get("PROBLEMS", []):  # type: ignore[union-attr]
        print(f"  PROBLEM: {item}")
    for key in ("ROADMAP_NOTICE", "ROADMAP_ERROR"):
        if payload.get(key):
            print(f"  roadmap: {payload[key]}")
    if payload.get("ARCHIVE_NOTICE"):
        print(f"  archive: {payload['ARCHIVE_NOTICE']}")
    for item in payload.get("ROADMAP_RELINKED", []):  # type: ignore[union-attr]
        print(f"  roadmap relinked: {item}")
    stale = payload.get("STALE_REFERENCES", [])
    if stale:
        print(f"  stale references to moved paths: {len(stale)}")  # type: ignore[arg-type]
    print(f"  result: {'OK' if payload.get('OK', payload.get('READY')) else 'NOT OK'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("plan", "apply", "validate"))
    parser.add_argument("--version", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--archive-root", default="", help="archive folder: .archive/ or a folder inside it, or an existing folder outside the repository (overrides archive.root in devspark.json)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-roadmap", action="store_true", help="also archive resolved Prospective Specs from the repository's roadmap specs/complete/ (never an external roadmap)")
    args, _ = parser.parse_known_args()

    repo = Path(args.repo_root).resolve() if args.repo_root else RC.repository_root()
    version = args.version.lstrip("v")
    try:
        if args.command != "plan" and not version:
            raise ArchiveError(f"'{args.command}' needs --version (the release being prepared)")
        location = resolve_archive_root(repo, args.archive_root)
        date = archive_date_for(location, version, args.date) if version else (args.date or datetime.date.today().isoformat())
        if version:
            validate_version(repo, version, resuming=manifest_path(location, date, version).is_file())
        if args.command == "validate":
            payload = validate_archive(location, version, date)
            code = 0 if payload["OK"] else 1
        else:
            inventory = Inventory(repo, version, date, location, include_roadmap=args.include_roadmap)
            payload = result_payload(inventory, args.command)
            code = 0
            if args.command == "apply":
                if inventory.collisions:
                    code = 2
                elif not args.dry_run:
                    payload["MOVED"] = apply_plan(inventory)
                    payload["ROADMAP_RELINKED"] = inventory.roadmap_relinked
                    payload["ROADMAP_ERROR"] = inventory.roadmap_error
                    verified = validate_archive(location, version, date)
                    payload["VALIDATION"] = verified
                    payload["OK"] = verified["OK"]
                    code = 0 if verified["OK"] else 1
        if args.command == "apply" and payload.get("COLLISIONS"):
            payload["OK"] = False
    except ArchiveError as error:
        payload, code = {"COMMAND": args.command, "OK": False, "ERROR": str(error)}, 2
        if not args.json:
            print(f"release-archive: {error}", file=sys.stderr)

    if args.json:
        print(json.dumps(payload, separators=(",", ":")))
    elif "ERROR" not in payload:
        print_report(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
