"""Helpers for CLI output path layout."""

from pathlib import Path
from typing import TypedDict


class OutputLayout(TypedDict):
    """Resolved output directories for a CLI run."""

    data_dir: Path
    artifact_root: Path
    report_dir: Path
    screenshot_dir: Path


def slugify_username(username: str) -> str:
    """Create a filesystem-safe username segment for scoped outputs."""
    safe_chars = []
    for char in username.strip().lower():
        if char.isalnum() or char in {"-", "_", "."}:
            safe_chars.append(char)
        else:
            safe_chars.append("-")

    slug = "".join(safe_chars).strip("-")
    return slug or "user"


def to_posix_path(path: Path) -> str:
    """Return a repository-relative path string suitable for JSON payloads."""
    return path.as_posix()


def build_output_layout(username: str, data_output_dir: str) -> OutputLayout:
    """Resolve output directories for unified generation.

    Outputs are always scoped to the username so that multiple users can
    coexist on the same filesystem and the same GitHub Pages deployment.
    """
    user_slug = slugify_username(username)
    data_dir = Path(data_output_dir) / "users" / user_slug
    output_root = Path("output") / "users" / user_slug

    return {
        "data_dir": data_dir,
        "artifact_root": output_root,
        "report_dir": output_root / "reports",
        "screenshot_dir": output_root / "screenshots",
    }
