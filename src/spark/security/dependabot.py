"""Collect every Dependabot alert for one repository.

Unlike the summary counts in the repository fetcher, this keeps the alert
detail, in every state, across all pages. The outcome always says *why* a
repository has no alerts: ``available`` with zero alerts is a real zero;
``disabled``, ``unauthorized`` and ``unavailable`` are not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

API_ROOT = "https://api.github.com"
PER_PAGE = 100
# 100 pages * 100 alerts. Far beyond any real repository; it only bounds a
# runaway pagination loop, and a hit is reported as ``truncated``.
MAX_PAGES = 100
SEVERITIES = ("critical", "high", "medium", "low")

# status
AVAILABLE = "available"  # alerts were read (zero is a genuine zero)
DISABLED = "disabled"  # Dependabot alerts are switched off for the repository
UNAUTHORIZED = "unauthorized"  # the token cannot read them
UNAVAILABLE = "unavailable"  # GitHub or the network failed
PARTIAL = "partial"  # some pages were read before a failure

GetPage = Callable[[str, Optional[Dict[str, Any]]], requests.Response]


@dataclass
class AlertCollection:
    status: str
    reason: str = "none"
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    pages: int = 0
    rate_remaining: Optional[int] = None

    @property
    def read_alerts(self) -> bool:
        """True when ``alerts`` is a trustworthy (possibly empty) list."""
        return self.status == AVAILABLE or (
            self.status == PARTIAL and bool(self.alerts)
        )


def _github_get(token: str) -> GetPage:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-stats-spark",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        return requests.get(url, headers=headers, params=params, timeout=30)

    return get


def _message(response: requests.Response) -> str:
    try:
        return str((response.json() or {}).get("message", "")).lower()
    except (ValueError, AttributeError):
        return ""


def classify_failure(response: requests.Response) -> tuple:
    """Map an error response to ``(status, reason)``.

    GitHub answers 403 both when the feature is off ("Dependabot alerts are
    disabled") and when the token lacks permission, and 404 when the token
    cannot see the repository at all, so the message is read to tell them apart.
    """
    code = response.status_code
    message = _message(response)
    remaining = response.headers.get("X-RateLimit-Remaining")
    if code in (403, 429) and (
        "rate limit" in message or "abuse" in message or remaining == "0"
    ):
        return UNAVAILABLE, "rate_limited"
    if code == 403 and "disabled" in message:
        return DISABLED, "dependabot_disabled"
    if code in (401, 403):
        return UNAUTHORIZED, "permission_denied"
    if code == 404:
        return UNAUTHORIZED, "not_found_or_no_access"
    return UNAVAILABLE, "api_error"


def _text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def normalize_alert(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reduce one API alert to the fields the dashboard keeps.

    The dismisser's identity and free-text comment are deliberately dropped.
    """
    number = raw.get("number")
    if not isinstance(number, int):
        return None
    advisory = raw.get("security_advisory") or {}
    vulnerability = raw.get("security_vulnerability") or {}
    dependency = raw.get("dependency") or {}
    package = vulnerability.get("package") or dependency.get("package") or {}
    severity = str(
        vulnerability.get("severity") or advisory.get("severity") or ""
    ).lower()
    state = str(raw.get("state") or "").lower()
    auto_dismissed = state == "auto_dismissed"
    if auto_dismissed:
        state = "dismissed"
    if state not in ("open", "dismissed", "fixed"):
        state = "unknown"
    patched = vulnerability.get("first_patched_version") or {}
    return {
        "number": number,
        "state": state,
        "auto_dismissed": auto_dismissed,
        "severity": severity if severity in SEVERITIES else "unknown",
        "ecosystem": _text(package.get("ecosystem")),
        "package": _text(package.get("name")),
        "manifest_path": _text(dependency.get("manifest_path")),
        "scope": _text(dependency.get("scope")),
        "ghsa_id": _text(advisory.get("ghsa_id")),
        "cve_id": _text(advisory.get("cve_id")),
        "summary": _text(advisory.get("summary")),
        "vulnerable_range": _text(vulnerability.get("vulnerable_version_range")),
        "fixed_version": _text(patched.get("identifier")),
        "created_at": _text(raw.get("created_at")),
        "updated_at": _text(raw.get("updated_at")),
        "dismissed_at": _text(raw.get("dismissed_at") or raw.get("auto_dismissed_at")),
        "dismissed_reason": _text(raw.get("dismissed_reason")),
        "fixed_at": _text(raw.get("fixed_at")),
        "html_url": _text(raw.get("html_url")),
    }


def _remaining(response: requests.Response) -> Optional[int]:
    try:
        return int(response.headers.get("X-RateLimit-Remaining"))
    except (TypeError, ValueError):
        return None


def collect_dependabot_alerts(
    owner: str,
    repo: str,
    token: str = "",
    *,
    get: Optional[GetPage] = None,
    max_pages: int = MAX_PAGES,
) -> AlertCollection:
    """Read all alerts (open, dismissed and fixed) for ``owner/repo``.

    Follows the ``Link: rel="next"`` header, which works for both page- and
    cursor-based pagination. Never raises: failures are returned as a status.
    """
    fetch = get or _github_get(token)
    url: Optional[str] = f"{API_ROOT}/repos/{owner}/{repo}/dependabot/alerts"
    params: Optional[Dict[str, Any]] = {"per_page": PER_PAGE}
    result = AlertCollection(status=AVAILABLE)

    while url:
        if result.pages >= max_pages:
            result.truncated = True
            result.status, result.reason = PARTIAL, "truncated"
            break
        try:
            response = fetch(url, params)
        except requests.RequestException:
            return _failed(result, UNAVAILABLE, "network_error")
        result.rate_remaining = _remaining(response)
        if response.status_code >= 400:
            status, reason = classify_failure(response)
            return _failed(result, status, reason)
        try:
            payload = response.json()
        except ValueError:
            return _failed(result, UNAVAILABLE, "api_error")
        if not isinstance(payload, list):
            return _failed(result, UNAVAILABLE, "api_error")
        result.pages += 1
        for raw in payload:
            alert = normalize_alert(raw) if isinstance(raw, dict) else None
            if alert:
                result.alerts.append(alert)
        url = (response.links.get("next") or {}).get("url")
        params = None  # the next URL carries its own query string
    return result


def _failed(result: AlertCollection, status: str, reason: str) -> AlertCollection:
    """A failure on the first page is a plain failure; after earlier pages it
    keeps what was read and says so."""
    if result.alerts:
        result.status, result.reason = PARTIAL, reason
    else:
        result.status, result.reason = status, reason
    return result
