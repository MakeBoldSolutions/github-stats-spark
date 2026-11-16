"""Repository discovery for registered sources, with actionable errors.

Discovery is independent of the collection pipeline and takes a PyGithub-style
client, so it can be tested without network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from github import GithubException

from spark.registry.secrets import SecretError
from spark.registry.store import Registry

ERROR_HINTS = {
    "not_found": "GitHub could not find it. Check the spelling, and that the "
    "token can see it (private organizations and repositories return 404 "
    "without access).",
    "no_access": "The token is not permitted to read it. Check the token's "
    "scopes or repository access.",
    "sso_required": "The organization enforces SAML SSO. Authorize the token "
    "for SSO in GitHub (Settings > Tokens > Configure SSO).",
    "rate_limited": "The GitHub API rate limit is exhausted. Discovery resumes "
    "on the next cycle after the limit resets.",
    "bad_credentials": "GitHub rejected the token as invalid or expired.",
    "connection_unusable": "The source's saved connection cannot be used "
    "(expired, removed, or its secret cannot be read). Replace the token on the "
    "Connections tab.",
    "network": "GitHub could not be reached.",
    "error": "Unexpected error talking to GitHub.",
}


@dataclass
class DiscoveryError(Exception):
    code: str
    detail: str = ""

    @property
    def message(self) -> str:
        hint = ERROR_HINTS.get(self.code, ERROR_HINTS["error"])
        return f"{hint} ({self.detail})" if self.detail else hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.message}"


def classify_error(error: Exception) -> DiscoveryError:
    """Map a GitHub/network exception to a stable, actionable error code."""
    if isinstance(error, DiscoveryError):
        return error
    if isinstance(error, GithubException):
        status = getattr(error, "status", 0)
        data = getattr(error, "data", None)
        message = str(data.get("message", "")) if isinstance(data, dict) else ""
        headers = {
            str(k).lower(): str(v)
            for k, v in (getattr(error, "headers", None) or {}).items()
        }
        lowered = message.lower()
        if "x-github-sso" in headers or "saml" in lowered:
            return DiscoveryError("sso_required", message)
        if (
            status == 429
            or "rate limit" in lowered
            or headers.get("x-ratelimit-remaining") == "0"
        ):
            return DiscoveryError("rate_limited", message)
        if status == 401:
            return DiscoveryError("bad_credentials", message)
        if status == 403:
            return DiscoveryError("no_access", message)
        if status == 404:
            return DiscoveryError("not_found", message)
        return DiscoveryError("error", f"HTTP {status} {message}".strip())
    if isinstance(error, (OSError, TimeoutError)):
        return DiscoveryError("network", f"{type(error).__name__}: {error}")
    return DiscoveryError("error", f"{type(error).__name__}: {error}")


def _serialize(repo: Any) -> Dict[str, Any]:
    return {
        "full_name": repo.full_name,
        "description": repo.description,
        "language": repo.language,
        "html_url": repo.html_url,
        "default_branch": repo.default_branch,
        "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
        "is_fork": repo.fork,
        "is_private": repo.private,
        "is_archived": repo.archived,
    }


def _list_repositories(github: Any, source_type: str, identifier: str) -> Iterable:
    """Return an iterable of GitHub repositories. Iterating a PyGithub
    paginated list walks every page."""
    if source_type == "org":
        return github.get_organization(identifier).get_repos(type="all")
    if source_type == "user":
        return github.get_user(identifier).get_repos()
    return [github.get_repo(identifier)]


def validate_access(
    github: Any, source_type: str, identifier: str
) -> Tuple[bool, Optional[DiscoveryError]]:
    """Check that a source exists and is readable, without listing everything."""
    try:
        if source_type == "org":
            github.get_organization(identifier).login  # noqa: B018 - triggers fetch
        elif source_type == "user":
            github.get_user(identifier).login  # noqa: B018
        else:
            github.get_repo(identifier).full_name  # noqa: B018
        return True, None
    except Exception as error:  # noqa: BLE001 - classified below
        return False, classify_error(error)


def discover_source(registry: Registry, github: Any, source: Dict[str, Any]) -> dict:
    """Discover one source and record its status. Never raises: a failure is
    recorded on the source and leaves its previous links and repositories
    untouched."""
    sid = source["id"]
    try:
        seen: List[int] = []
        for repo in _list_repositories(github, source["type"], source["identifier"]):
            seen.append(registry.upsert_repository(sid, _serialize(repo)))
        registry.sync_source_links(sid, seen)
    except Exception as error:  # noqa: BLE001
        problem = classify_error(error)
        registry.record_source_status(
            sid, "error", error_code=problem.code, error_message=problem.message
        )
        return {"source_id": sid, "state": "error", "code": problem.code, "count": 0}

    registry.record_source_status(
        sid, "ok", repository_count=len(seen), discovered=True
    )
    registry.record_observation(
        f"source:{source['type']}:{source['identifier'].lower()}",
        "repository_count",
        len(seen),
        "discovery",
        source.get("client_id"),
    )
    return {"source_id": sid, "state": "ok", "code": None, "count": len(seen)}


def run_discovery(
    registry: Registry,
    github: Any = None,
    *,
    github_for: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> List[dict]:
    """Discover every enabled source. Disabled sources are left as they were.

    ``github_for(source)`` supplies a per-source client (so each source can use
    its own connection); if it raises, that source is marked
    ``connection_unusable`` and the others still run.
    """
    results = []
    for source in registry.list_sources(enabled_only=True):
        try:
            client = github_for(source) if github_for else github
        except SecretError as error:
            registry.record_source_status(
                source["id"],
                "error",
                error_code="connection_unusable",
                error_message=f"{ERROR_HINTS['connection_unusable']} ({error})",
            )
            results.append(
                {
                    "source_id": source["id"],
                    "state": "error",
                    "code": "connection_unusable",
                    "count": 0,
                }
            )
            continue
        results.append(discover_source(registry, client, source))
    return results
