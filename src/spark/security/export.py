"""JSON export of Dependabot alerts for the dashboard's Security view.

Derived from the registry database, which stays the source of truth. Only
public repositories reached by an enabled source are exported; private and
client data waits for an explicit boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from spark.registry.store import Registry, now_iso
from spark.security.dependabot import SEVERITIES
from spark.worker.status import atomic_write_json

SCHEMA_VERSION = 1
EXPORT_PATH = Path("security") / "dependabot.json"

_ALERT_FIELDS = (
    "number",
    "state",
    "auto_dismissed",
    "severity",
    "ecosystem",
    "package",
    "manifest_path",
    "ghsa_id",
    "cve_id",
    "summary",
    "vulnerable_range",
    "fixed_version",
    "created_at",
    "updated_at",
    "dismissed_at",
    "dismissed_reason",
    "fixed_at",
    "html_url",
)


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def age_days(alert: Dict[str, Any], now: datetime) -> Optional[int]:
    """Days from creation to now (open) or to when it stopped being open."""
    created = _parse(alert.get("created_at"))
    if created is None:
        return None
    if alert["state"] == "fixed":
        end = _parse(alert.get("fixed_at"))
    elif alert["state"] == "dismissed":
        end = _parse(alert.get("dismissed_at"))
    else:
        end = now
    return max(0, ((end or now) - created).days)


def _empty_counts() -> Dict[str, Any]:
    return {
        "open": {"total": 0, **{s: 0 for s in SEVERITIES}, "unknown": 0},
        "dismissed": 0,
        "fixed": 0,
    }


def build_dependabot(
    registry: Registry, interval_seconds: int, now: Optional[datetime] = None
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    enabled = {s["id"] for s in registry.list_sources() if s["enabled"]}
    portfolio = {
        repo["full_name_lower"]: repo
        for repo in registry.list_repositories(include_excluded=False)
        if not repo["is_private"] and any(s["id"] in enabled for s in repo["sources"])
    }
    coverage = registry.list_dependabot_coverage()

    repositories: List[Dict[str, Any]] = []
    counts_by_repo: Dict[str, Dict[str, Any]] = {}
    for key, repo in portfolio.items():
        counts_by_repo[key] = _empty_counts()
        check = coverage.get(key)
        repositories.append(
            {
                "full_name": repo["full_name"],
                "html_url": repo["html_url"],
                "client": repo["client"],
                "archived": bool(repo["is_archived"]),
                "status": check["status"] if check else "not_checked",
                "reason": check["reason"] if check else "not_checked",
                "truncated": bool(check and check["truncated"]),
                "checked_at": check["checked_at"] if check else None,
                "last_success_at": check["last_success_at"] if check else None,
                "counts": counts_by_repo[key],
            }
        )

    alerts: List[Dict[str, Any]] = []
    for row in registry.list_dependabot_alerts():
        owner = portfolio.get(row["repo"])
        if owner is None:
            continue
        counts = counts_by_repo[row["repo"]]
        if row["state"] == "open":
            counts["open"]["total"] += 1
            counts["open"][row["severity"]] += 1
        elif row["state"] in ("dismissed", "fixed"):
            counts[row["state"]] += 1
        item = {key: row[key] for key in _ALERT_FIELDS}
        item["auto_dismissed"] = bool(item["auto_dismissed"])
        item["repository"] = owner["full_name"]
        item["age_days"] = age_days(row, now)
        alerts.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "refresh_interval_seconds": interval_seconds,
        "repositories": repositories,
        "alerts": alerts,
    }


def write_dependabot(
    registry: Registry, data_dir: Path, interval_seconds: int
) -> Dict[str, Any]:
    payload = build_dependabot(registry, interval_seconds)
    atomic_write_json(data_dir / EXPORT_PATH, payload)
    return payload
