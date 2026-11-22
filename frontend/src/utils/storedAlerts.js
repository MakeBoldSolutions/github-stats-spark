import { fullNameOf, repoKey } from "./scope";

/**
 * One source per number: in the self-hosted deployment the worker keeps
 * every Dependabot alert (data/security/dependabot.json), while collected
 * repository records carry a summary read from the first page of alerts.
 * These helpers make the stored alerts the count every view shows.
 */

/** Availability as the dashboard records spell it, from a coverage status. */
const AVAILABILITY = {
  available: "available",
  partial: "available",
  disabled: "unsupported",
  unauthorized: "unauthorized",
  unavailable: "unavailable",
  not_checked: "unavailable",
};

const countsFrom = (open) => ({
  total_open: open.total ?? 0,
  critical: open.critical ?? 0,
  high: open.high ?? 0,
  medium: open.medium ?? 0,
  low: open.low ?? 0,
});

/** Stored coverage and counts by repository key. */
export function storedCoverage(file) {
  return new Map(
    (file?.repositories || []).map((entry) => [
      repoKey(entry.full_name),
      entry,
    ]),
  );
}

/**
 * Copy of `repo` whose alert counts come from the stored alerts. Records
 * the store does not cover are returned unchanged.
 */
export function withStoredAlerts(repo, coverage) {
  const entry = coverage.get(repoKey(fullNameOf(repo)));
  if (!entry) return repo;
  const counts = countsFrom(entry.counts?.open || {});
  const availability = AVAILABILITY[entry.status] || "unavailable";
  const security = repo.security_summary || {};
  const diagnostics = repo.diagnostics_summary;
  const attention = repo.attention_metrics;
  return {
    ...repo,
    security_summary: {
      ...security,
      availability,
      reason: entry.reason,
      active_alert_counts: counts,
      alert_source: "stored",
    },
    ...(diagnostics && {
      diagnostics_summary: {
        ...diagnostics,
        security: {
          ...(diagnostics.security || {}),
          dependabot: counts,
        },
      },
    }),
    ...(attention?.components?.security && {
      attention_metrics: {
        ...attention,
        components: {
          ...attention.components,
          security: {
            ...attention.components.security,
            availability,
            active_alert_counts: counts,
          },
        },
      },
    }),
  };
}

/** The alert file restricted to repositories whose key is in `keys`. */
export function scopeAlertFile(file, keys) {
  if (!file || !keys) return file;
  return {
    ...file,
    repositories: file.repositories.filter((r) =>
      keys.has(repoKey(r.full_name)),
    ),
    alerts: file.alerts.filter((a) => keys.has(repoKey(a.repository))),
  };
}

/** Alerts and coverage for one repository, for the drawer. */
export function alertsForRepository(file, fullName) {
  if (!file) return null;
  const key = repoKey(fullName);
  const coverage = file.repositories.find((r) => repoKey(r.full_name) === key);
  if (!coverage) return null;
  return {
    coverage,
    alerts: file.alerts.filter((a) => repoKey(a.repository) === key),
  };
}
