"""Security-alert collection, kept apart from the repository fetcher."""

from spark.security.dependabot import (
    AlertCollection,
    collect_dependabot_alerts,
    normalize_alert,
)

__all__ = ["AlertCollection", "collect_dependabot_alerts", "normalize_alert"]
