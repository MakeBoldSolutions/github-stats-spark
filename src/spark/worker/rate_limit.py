"""GitHub rate-limit lookup. The /rate_limit endpoint does not consume quota."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

API_URL = "https://api.github.com/rate_limit"


def fetch_rate_limit(token: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """Return ``{limit, remaining, reset_at}`` for the core quota, or None."""
    try:
        response = requests.get(
            API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return None
        core = response.json()["resources"]["core"]
        return {
            "limit": core["limit"],
            "remaining": core["remaining"],
            "reset_at": datetime.fromtimestamp(
                core["reset"], tz=timezone.utc
            ).isoformat(),
        }
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None
