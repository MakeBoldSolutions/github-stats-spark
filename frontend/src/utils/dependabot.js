export const SEVERITY_ORDER = ["critical", "high", "medium", "low", "unknown"];

export const STATE_FILTERS = [
  { value: "open", label: "Open" },
  { value: "dismissed", label: "Dismissed" },
  { value: "fixed", label: "Fixed" },
  { value: "all", label: "All states" },
];

/** Plain-language reason a repository has no readable alerts. */
export const COVERAGE_LABELS = {
  available: "Read",
  disabled: "Dependabot alerts are turned off",
  unauthorized: "Token cannot read alerts",
  unavailable: "GitHub could not be reached",
  partial: "Only partly read",
  not_checked: "Not checked yet",
};

export const REASON_LABELS = {
  dependabot_disabled: "Dependabot alerts are disabled for this repository.",
  permission_denied:
    "The token lacks Dependabot alerts read permission for this repository.",
  not_found_or_no_access:
    "GitHub returned not found: the token cannot see this repository.",
  connection_unusable:
    "The connection for this repository is expired or unreadable.",
  rate_limited: "GitHub rate limit reached; will retry on the next refresh.",
  network_error: "The request to GitHub failed.",
  api_error: "GitHub returned an error.",
  truncated: "Too many alerts to read in one run; the list is incomplete.",
  not_checked: "No check has completed yet.",
  none: "",
};

const severityRank = (severity) => {
  const index = SEVERITY_ORDER.indexOf(severity);
  return index === -1 ? SEVERITY_ORDER.length : index;
};

/** True when `file` is a usable dependabot.json payload. */
export function isDependabotPayload(file) {
  return (
    file?.schema_version === 1 &&
    Array.isArray(file.alerts) &&
    Array.isArray(file.repositories)
  );
}

/**
 * Filter alerts by state, severity, repository and client. "all" and ""
 * mean no restriction. Sorted by severity, then oldest first.
 */
export function filterAlerts(file, filters) {
  const {
    state = "open",
    severity = "",
    repository = "",
    client = "",
  } = filters;
  const clientOf = new Map(
    file.repositories.map((repo) => [repo.full_name, repo.client || ""]),
  );
  return file.alerts
    .filter((alert) => state === "all" || alert.state === state)
    .filter((alert) => !severity || alert.severity === severity)
    .filter((alert) => !repository || alert.repository === repository)
    .filter((alert) => !client || clientOf.get(alert.repository) === client)
    .sort(
      (a, b) =>
        severityRank(a.severity) - severityRank(b.severity) ||
        (b.age_days ?? -1) - (a.age_days ?? -1) ||
        a.repository.localeCompare(b.repository) ||
        a.number - b.number,
    );
}

/** Repositories whose alerts could not be fully read, for the coverage panel. */
export function coverageGaps(file) {
  return file.repositories.filter((repo) => repo.status !== "available");
}

const CSV_COLUMNS = [
  ["repository", "Repository"],
  ["number", "Alert"],
  ["state", "State"],
  ["severity", "Severity"],
  ["package", "Package"],
  ["ecosystem", "Ecosystem"],
  ["ghsa_id", "Advisory"],
  ["cve_id", "CVE"],
  ["vulnerable_range", "Vulnerable versions"],
  ["fixed_version", "Fixed in"],
  ["created_at", "Created"],
  ["dismissed_at", "Dismissed"],
  ["fixed_at", "Fixed"],
  ["age_days", "Age (days)"],
  ["html_url", "Link"],
];

const csvCell = (value) => {
  const text = value === null || value === undefined ? "" : String(value);
  // Prefix formula starters so a spreadsheet never evaluates advisory text.
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
};

/** The alert CSV columns in the shape ExportButton takes. */
export const ALERT_EXPORT_COLUMNS = CSV_COLUMNS.map(([key, label]) => ({
  key,
  label,
}));

export function alertsToCsv(alerts) {
  const header = CSV_COLUMNS.map(([, label]) => label).join(",");
  const rows = alerts.map((alert) =>
    CSV_COLUMNS.map(([key]) => csvCell(alert[key])).join(","),
  );
  return [header, ...rows].join("\n");
}
