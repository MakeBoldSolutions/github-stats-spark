"""Screenshot audit helpers for website health and capture quality."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from PIL import Image, ImageStat

STRONG_404_MARKERS = (
    "there isn't a github pages site here",
    "site not found",
    "page not found",
    "this site can't be reached",
    "404 page not found",
)


def _analyze_http_response(website_url: str, timeout: int = 20) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status_code": None,
        "final_url": website_url,
        "page_title": None,
        "flags": [],
    }

    response = requests.get(
        website_url,
        timeout=timeout,
        allow_redirects=True,
        headers={"User-Agent": "StatsSparkScreenshotAudit/1.0"},
    )
    audit["status_code"] = response.status_code
    audit["final_url"] = response.url

    soup = BeautifulSoup(response.text[:20000], "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    body_text = soup.get_text(" ", strip=True).lower()
    audit["page_title"] = title

    if response.status_code >= 400:
        audit["flags"].append("likely_404")
        return audit

    title_text = (title or "").lower()
    if any(marker in title_text for marker in ("404", "not found", "site not found")):
        audit["flags"].append("likely_404")
        return audit

    if any(marker in body_text for marker in STRONG_404_MARKERS):
        audit["flags"].append("likely_404")

    return audit


def _analyze_image(image_path: Path) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "image_analysis_available": bool(Image and ImageStat),
        "brightness": None,
        "variance": None,
        "flags": [],
    }
    if not image_path.exists():
        audit["flags"].append("missing_screenshot")
        return audit

    if not Image or not ImageStat:
        return audit

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        stat = ImageStat.Stat(rgb)
        brightness = sum(stat.mean) / 3.0
        variance = sum(stat.stddev) / 3.0
        audit["brightness"] = round(brightness, 2)
        audit["variance"] = round(variance, 2)

        if brightness < 28 and variance < 18:
            audit["flags"].append("likely_black_or_blank")

    return audit


def audit_screenshot_outputs(
    repositories: List[Dict[str, Any]], workspace_root: Path
) -> Dict[str, Any]:
    """Audit screenshot outputs and linked websites for broken captures.

    Returns a payload suitable for embedding in repositories.json metadata and
    repository-level entries.
    """
    per_repo: Dict[str, Dict[str, Any]] = {}
    likely_404_pages: List[Dict[str, Any]] = []
    likely_black_or_blank: List[Dict[str, Any]] = []
    missing_screenshots: List[Dict[str, Any]] = []

    repos_with_website = 0
    repos_with_screenshot = 0
    image_analysis_available = bool(Image and ImageStat)

    for repo in repositories:
        repo_name = repo.get("name", "")
        website_url = repo.get("website_url")
        screenshot = repo.get("screenshot") or {}
        screenshot_path = screenshot.get("path")

        audit_entry: Dict[str, Any] = {
            "status": "ok",
            "website_url": website_url,
            "screenshot_path": screenshot_path,
            "flags": [],
            "http": None,
            "image": None,
        }

        if website_url:
            repos_with_website += 1
            try:
                http_audit = _analyze_http_response(website_url)
                audit_entry["http"] = http_audit
                if "likely_404" in http_audit["flags"]:
                    audit_entry["flags"].append("likely_404")
                    likely_404_pages.append(
                        {
                            "repo": repo_name,
                            "website_url": website_url,
                            "status_code": http_audit.get("status_code"),
                            "final_url": http_audit.get("final_url"),
                            "page_title": http_audit.get("page_title"),
                        }
                    )
            except requests.RequestException as error:
                audit_entry["flags"].append("website_unreachable")
                audit_entry["http"] = {
                    "status_code": None,
                    "final_url": None,
                    "page_title": None,
                    "flags": ["website_unreachable"],
                    "error": type(error).__name__,
                }

        if screenshot_path:
            repos_with_screenshot += 1
            image_path = (workspace_root / screenshot_path).resolve()
            image_audit = _analyze_image(image_path)
            audit_entry["image"] = image_audit
            if "likely_black_or_blank" in image_audit["flags"]:
                audit_entry["flags"].append("likely_black_or_blank")
                likely_black_or_blank.append(
                    {
                        "repo": repo_name,
                        "path": screenshot_path,
                        "brightness": image_audit.get("brightness"),
                        "variance": image_audit.get("variance"),
                    }
                )
            image_analysis_available = image_analysis_available or image_audit.get(
                "image_analysis_available", False
            )
        elif website_url:
            audit_entry["flags"].append("missing_screenshot")
            missing_screenshots.append({"repo": repo_name, "website_url": website_url})

        if audit_entry["flags"]:
            if any(
                flag in {"likely_404", "website_unreachable", "missing_screenshot"}
                for flag in audit_entry["flags"]
            ):
                audit_entry["status"] = "error"
            else:
                audit_entry["status"] = "warning"

        per_repo[repo_name] = audit_entry

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos_with_website": repos_with_website,
        "repos_with_screenshot": repos_with_screenshot,
        "image_analysis_available": image_analysis_available,
        "likely_404_pages": likely_404_pages,
        "likely_black_or_blank": likely_black_or_blank,
        "missing_screenshots": missing_screenshots,
        "flagged_repository_count": sum(
            1 for value in per_repo.values() if value["flags"]
        ),
        "repositories": per_repo,
    }


def build_screenshot_audit_markdown(audit_payload: Optional[Dict[str, Any]]) -> str:
    """Render a compact markdown section for the screenshot audit."""
    if not audit_payload:
        return ""

    lines = ["## Screenshot Audit", ""]
    lines.append(
        f"- Repositories with websites: {audit_payload.get('repos_with_website', 0)}"
    )
    lines.append(
        f"- Screenshots present: {audit_payload.get('repos_with_screenshot', 0)}"
    )
    lines.append(
        f"- Flagged repositories: {audit_payload.get('flagged_repository_count', 0)}"
    )
    lines.append("")

    likely_404_pages = audit_payload.get("likely_404_pages", [])
    likely_black_or_blank = audit_payload.get("likely_black_or_blank", [])
    missing_screenshots = audit_payload.get("missing_screenshots", [])

    if likely_404_pages:
        lines.append("### Likely 404 Pages")
        lines.append("")
        for item in likely_404_pages:
            lines.append(
                f"- {item['repo']}: {item.get('website_url')} "
                f"(status: {item.get('status_code')}, title: {item.get('page_title') or 'n/a'})"
            )
        lines.append("")

    if likely_black_or_blank:
        lines.append("### Likely Black Or Blank Screenshots")
        lines.append("")
        for item in likely_black_or_blank:
            lines.append(
                f"- {item['repo']}: {item.get('path')} "
                f"(brightness: {item.get('brightness')}, variance: {item.get('variance')})"
            )
        lines.append("")

    if missing_screenshots:
        lines.append("### Missing Screenshots")
        lines.append("")
        for item in missing_screenshots:
            lines.append(f"- {item['repo']}: {item.get('website_url')}")
        lines.append("")

    if not any([likely_404_pages, likely_black_or_blank, missing_screenshots]):
        lines.append("No broken site captures were detected in this run.")
        lines.append("")

    return "\n".join(lines).rstrip()
