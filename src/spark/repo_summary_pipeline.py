"""Generate LLM summaries from per-repo detail JSON files.

Feeds the rich cached data directly to Claude for summarization,
then assembles the final repositories.json for the frontend.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


from spark.ai_response import extract_response_text
from spark.cache import APICache
from spark.logger import get_logger
from spark.time_utils import sanitize_timestamp_for_filename

logger = get_logger()

SUMMARY_PROMPT = """Analyze this GitHub repository data and provide a concise technical summary.

Repository: {repo_name}
Owner: {owner}
Description: {description}
Primary Language: {primary_language}
Created: {created_at}
Last Push: {pushed_at}
Size: {size_kb} KB

LANGUAGES:
{languages_section}

QUALITY SIGNALS:
- License: {has_license}
- CI/CD: {has_ci_cd}
- Tests: {has_tests}
- Documentation: {has_docs}
- Total Commits: {total_commits}
- Stars: {stars} | Forks: {forks} | Watchers: {watchers}
- Open Issues: {open_issues} | Open PRs: {open_prs}
- Issue Close Ratio: {issue_close_ratio}

COMMUNITY:
- Topics: {topics}
- Has Releases: {has_releases} (latest: {latest_release})
- Has Contributing Guide: {has_contributing}
- Has Code of Conduct: {has_code_of_conduct}
- Homepage: {homepage_url} (status: {homepage_status})
- README Quality Score: {readme_quality_score}/100

DEPENDENCIES:
{dependencies_section}

README (excerpt):
{readme_excerpt}

Provide a JSON response with exactly these fields:
{{
  "summary": "A 2-3 sentence technical summary of what this project does and its main value.",
  "purpose": "One sentence: the primary purpose or problem it solves.",
  "tech_highlights": ["up to 5 key technologies, frameworks, or tools used"],
  "project_maturity": "one of: prototype, active-development, stable, maintenance, archived",
  "target_audience": "Who would use this project (one sentence)"
}}

Respond ONLY with valid JSON, no markdown fencing."""


def _build_prompt(detail: Dict[str, Any]) -> str:
    """Build the LLM prompt from a repo detail dict."""
    base = detail.get("base", {})
    langs = detail.get("languages") or {}
    qi = detail.get("quality_indicators") or {}
    ch = detail.get("community_health") or {}
    ws = detail.get("web_signals") or {}
    deps = detail.get("dependency_files") or {}
    readme = detail.get("readme") or ""

    # Languages section
    if langs:
        total = sum(langs.values())
        top = sorted(langs.items(), key=lambda x: -x[1])[:8]
        languages_section = "\n".join(
            f"  {lang}: {bytes_val:,} bytes ({bytes_val/total*100:.1f}%)"
            for lang, bytes_val in top
        )
    else:
        languages_section = "  (none detected)"

    # Dependencies section (first 500 chars of each file)
    dep_parts = []
    for filename, content in deps.items():
        dep_parts.append(f"  [{filename}]: {content[:500]}")
    dependencies_section = "\n".join(dep_parts) if dep_parts else "  (none found)"

    # README excerpt (first 2000 chars)
    readme_excerpt = readme[:2000] if readme else "(no README)"

    return SUMMARY_PROMPT.format(
        repo_name=base.get("name", "?"),
        owner=detail.get("metadata", {}).get("owner", "?"),
        description=base.get("description") or ch.get("description") or "(none)",
        primary_language=base.get("primary_language") or "Unknown",
        created_at=base.get("created_at", "?"),
        pushed_at=base.get("pushed_at", "?"),
        size_kb=base.get("size_kb", 0),
        languages_section=languages_section,
        has_license=qi.get("has_license", False),
        has_ci_cd=qi.get("has_ci_cd", False),
        has_tests=qi.get("has_tests", False),
        has_docs=qi.get("has_docs", False),
        total_commits=ws.get("total_commits", "?"),
        stars=ws.get("stars", base.get("stars", 0)),
        forks=ws.get("forks", base.get("forks", 0)),
        watchers=ws.get("watchers", base.get("watchers", 0)),
        open_issues=ws.get("open_issues", 0),
        open_prs=ws.get("open_prs", 0),
        issue_close_ratio=ch.get("issue_close_ratio", "N/A"),
        topics=", ".join(ch.get("topics", [])) or "(none)",
        has_releases=ch.get("release_count", 0) > 0,
        latest_release=ch.get("latest_release_tag") or "none",
        has_contributing=ch.get("has_contributing", False),
        has_code_of_conduct=ch.get("has_code_of_conduct", False),
        homepage_url=ch.get("homepage_url") or base.get("homepage") or "(none)",
        homepage_status=ch.get("homepage_status") or "N/A",
        readme_quality_score=(
            ch.get("readme_quality_score", {}).get("score", "?")
            if isinstance(ch.get("readme_quality_score"), dict)
            else "?"
        ),
        dependencies_section=dependencies_section,
        readme_excerpt=readme_excerpt,
    )


def generate_summaries(
    detail_dir: str,
    cache: APICache,
    username: str,
    api_key: Optional[str] = None,
    model: str = "claude-haiku-4-5",
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Generate LLM summaries for all repo detail files.

    Args:
        detail_dir: Path to directory containing per-repo detail JSON files
        cache: APICache for caching summaries
        username: GitHub username (for cache keys)
        api_key: Anthropic API key
        model: Model to use

    Returns:
        Dict mapping repo_name -> summary dict
    """
    import anthropic

    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping LLM summaries")
        return {}

    client = anthropic.Anthropic(api_key=api_key)
    detail_path = Path(detail_dir)
    summaries: Dict[str, Optional[Dict[str, Any]]] = {}
    total_tokens = 0
    cache_hits = 0

    files = sorted(detail_path.glob("*.json"))
    logger.info(f"Generating LLM summaries for {len(files)} repos (model={model})")

    for i, file_path in enumerate(files, 1):
        repo_name = file_path.stem
        detail = json.loads(file_path.read_text(encoding="utf-8"))

        # Cache key based on pushed_at
        pushed_at_str = detail.get("base", {}).get("pushed_at")
        if pushed_at_str:
            pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
            cache_key = sanitize_timestamp_for_filename(pushed_at)
        else:
            cache_key = "unknown"

        # Check cache
        cached = cache.get("llm_summary", username, repo=repo_name, week=cache_key)
        if cached:
            summaries[repo_name] = cached
            cache_hits += 1
            logger.info(f"  [{i:2d}/{len(files)}] {repo_name:35s} CACHED")
            continue

        # Build prompt and call LLM
        prompt = _build_prompt(detail)
        t0 = time.time()

        try:
            response = client.messages.create(
                model=model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = time.time() - t0
            tokens = response.usage.input_tokens + response.usage.output_tokens
            total_tokens += tokens

            # Parse JSON response
            raw_text = extract_response_text(response.content).strip()
            # Strip markdown fencing if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            summary_data = json.loads(raw_text)
            summary_data["tokens_used"] = tokens
            summary_data["model"] = model
            summary_data["generated_at"] = datetime.now(timezone.utc).isoformat()

            summaries[repo_name] = summary_data

            # Cache it
            cache.set(
                "llm_summary", username, summary_data, repo=repo_name, week=cache_key
            )

            logger.info(
                f"  [{i:2d}/{len(files)}] {repo_name:35s} {elapsed:.1f}s  {tokens} tokens"
            )

        except json.JSONDecodeError as e:
            logger.warning(
                f"  [{i:2d}/{len(files)}] {repo_name:35s} JSON parse error: {e}"
            )
            # Store raw text as fallback
            summaries[repo_name] = {
                "summary": raw_text[:300],
                "purpose": "",
                "tech_highlights": [],
                "project_maturity": "unknown",
                "target_audience": "",
                "model": model,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "parse_error": True,
            }
        except Exception as e:
            logger.warning(f"  [{i:2d}/{len(files)}] {repo_name:35s} ERROR: {e}")
            summaries[repo_name] = None

    logger.info(
        f"  Done: {len(summaries)} summaries, {cache_hits} cached, {total_tokens} tokens used"
    )
    return summaries


def build_repositories_json(
    repos: List[Dict[str, Any]],
    detail_dir: str,
    summaries: Dict[str, Dict[str, Any]],
    username: str,
    output_path: str = "data/users/{username}/repositories.json",
) -> str:
    """Assemble the final repositories.json for the frontend.

    Args:
        repos: List of repo dicts from fetcher
        detail_dir: Path to per-repo detail JSON files
        summaries: Dict of repo_name -> LLM summary
        username: GitHub username
        output_path: Output file path template

    Returns:
        Path to written file
    """
    detail_path = Path(detail_dir)
    repositories = []

    for repo in repos:
        repo_name = repo["name"]
        detail_file = detail_path / f"{repo_name}.json"

        if detail_file.exists():
            detail = json.loads(detail_file.read_text(encoding="utf-8"))
        else:
            detail = {}

        base = detail.get("base", {})
        langs = detail.get("languages") or {}
        qi = detail.get("quality_indicators") or {}
        ch = detail.get("community_health") or {}
        ws = detail.get("web_signals") or {}
        ps = detail.get("pull_request_summary") or {}
        ss = detail.get("security_summary") or {}
        detail.get("dependency_files") or {}

        # Language stats as percentages
        total_bytes = sum(langs.values()) if langs else 0
        language_stats = {}
        if total_bytes > 0:
            for lang, b in sorted(langs.items(), key=lambda x: -x[1]):
                language_stats[lang] = round(b / total_bytes * 100, 1)

        # Build the frontend-expected structure
        entry: Dict[str, Any] = {
            "name": repo_name,
            "description": base.get("description") or ch.get("description") or "",
            "url": f"https://github.com/{username}/{repo_name}",
            "homepage": base.get("homepage") or ch.get("homepage_url") or "",
            "has_pages": base.get("has_pages", False),
            "pages_url": (
                f"https://{username}.github.io/{repo_name}/"
                if base.get("has_pages")
                else None
            ),
            "stars": ws.get("stars", base.get("stars", 0)),
            "forks": ws.get("forks", base.get("forks", 0)),
            "watchers": ws.get("watchers", base.get("watchers", 0)),
            "language": base.get("primary_language"),
            "languages": list(langs.keys()),
            "language_stats": language_stats,
            "language_count": len(langs),
            "size_kb": base.get("size_kb", 0),
            "created_at": base.get("created_at"),
            "updated_at": base.get("updated_at"),
            "pushed_at": base.get("pushed_at"),
            "is_fork": base.get("is_fork", False),
            "is_private": base.get("is_private", False),
            "is_archived": base.get("is_archived", False),
            # Commit signals from web scraping
            "total_commits": ws.get("total_commits"),
            "open_issues": ws.get("open_issues", 0),
            "open_prs": ws.get("open_prs", 0),
            # Quality indicators
            "has_readme": bool(detail.get("readme")),
            "has_license": qi.get("has_license", False),
            "has_ci_cd": qi.get("has_ci_cd", False),
            "has_tests": qi.get("has_tests", False),
            "has_docs": qi.get("has_docs", False),
            # Community health
            "topics": ch.get("topics", []),
            "issue_close_ratio": ch.get("issue_close_ratio"),
            "has_discussions": ch.get("has_discussions", False),
            "release_count": ch.get("release_count", 0),
            "latest_release_tag": ch.get("latest_release_tag"),
            "latest_release_date": ch.get("latest_release_date"),
            "has_contributing": ch.get("has_contributing", False),
            "has_code_of_conduct": ch.get("has_code_of_conduct", False),
            "has_security_policy": ch.get("has_security_policy", False),
            "readme_quality_score": (
                ch.get("readme_quality_score", {}).get("score")
                if isinstance(ch.get("readme_quality_score"), dict)
                else None
            ),
            "homepage_status": ch.get("homepage_status"),
            "homepage_response_ms": ch.get("homepage_response_ms"),
            # Pull request summary
            "pull_request_summary": (
                ps if ps.get("availability") == "available" else None
            ),
            # Security summary
            "security_summary": ss if ss.get("availability") != "unavailable" else None,
            # AI summary
            "ai_summary": summaries.get(repo_name),
        }

        # Compute age and recency
        if base.get("created_at"):
            try:
                created = datetime.fromisoformat(
                    base["created_at"].replace("Z", "+00:00")
                )
                entry["age_days"] = (datetime.now(timezone.utc) - created).days
            except (ValueError, TypeError):
                entry["age_days"] = None
        else:
            entry["age_days"] = None

        if base.get("pushed_at"):
            try:
                pushed = datetime.fromisoformat(
                    base["pushed_at"].replace("Z", "+00:00")
                )
                entry["days_since_last_push"] = (
                    datetime.now(timezone.utc) - pushed
                ).days
            except (ValueError, TypeError):
                entry["days_since_last_push"] = None
        else:
            entry["days_since_last_push"] = None

        repositories.append(entry)

    # Build profile summary
    profile = {
        "username": username,
        "total_repositories": len(repositories),
        "total_stars": sum(r.get("stars", 0) for r in repositories),
        "total_forks": sum(r.get("forks", 0) for r in repositories),
        "total_commits": sum(r.get("total_commits", 0) or 0 for r in repositories),
    }

    # Final output
    output = {
        "profile": profile,
        "repositories": repositories,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "3.0.0",
            "generator": "repo_detail_pipeline",
            "schema_features": [
                "llm_summaries",
                "web_signals",
                "community_health",
                "readme_quality_score",
            ],
        },
    }

    out_file = Path(output_path.format(username=username))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str, ensure_ascii=False)

    logger.info(
        f"Wrote {out_file} ({os.path.getsize(out_file) // 1024}KB, {len(repositories)} repos)"
    )
    return str(out_file)
