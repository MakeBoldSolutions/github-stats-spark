import { Badge } from "@/components/Brand";
import styles from "./SecurityView.module.css";

/** Shared by the Security view and the repository drawer's Security panel. */

export const SEVERITY_TONE = {
  critical: "critical",
  high: "critical",
  medium: "caution",
  low: "neutral",
  unknown: "neutral",
};

export const formatDate = (value) => (value ? value.slice(0, 10) : "—");

/** Table columns for alerts; the repository column only where several show. */
export function alertColumns({ showRepository = true, onOpenRepository } = {}) {
  const columns = [
    {
      key: "severity",
      header: "Severity",
      render: (alert) => (
        <Badge tone={SEVERITY_TONE[alert.severity] || "neutral"}>
          {alert.severity}
        </Badge>
      ),
    },
    showRepository && {
      key: "repository",
      header: "Repository",
      render: (alert) =>
        onOpenRepository ? (
          <button
            type="button"
            className={styles.repoLink}
            onClick={() => onOpenRepository(alert.repository)}
            aria-label={`Open ${alert.repository} details`}
          >
            {alert.repository}
          </button>
        ) : (
          alert.repository
        ),
    },
    {
      key: "package",
      header: "Package",
      render: (alert) => (
        <>
          {alert.package || "—"}
          {alert.ecosystem && (
            <span className={styles.muted}> ({alert.ecosystem})</span>
          )}
        </>
      ),
    },
    {
      key: "advisory",
      header: "Advisory",
      render: (alert) => (
        <span title={alert.summary || undefined}>
          {alert.ghsa_id || alert.cve_id || "—"}
        </span>
      ),
    },
    {
      key: "vulnerable_range",
      header: "Vulnerable",
      render: (alert) => alert.vulnerable_range || "—",
    },
    {
      key: "fixed_version",
      header: "Fixed in",
      render: (alert) => alert.fixed_version || "No fix yet",
    },
    {
      key: "state",
      header: "State",
      render: (alert) =>
        `${alert.state}${
          alert.state === "fixed" ? ` ${formatDate(alert.fixed_at)}` : ""
        }${
          alert.state === "dismissed"
            ? ` ${formatDate(alert.dismissed_at)}`
            : ""
        }`,
    },
    {
      key: "age",
      header: "Age",
      render: (alert) => (alert.age_days == null ? "—" : `${alert.age_days}d`),
    },
    {
      key: "github",
      header: "GitHub",
      render: (alert) =>
        alert.html_url ? (
          <a
            className={styles.link}
            href={alert.html_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Alert ${alert.number} on ${alert.repository} (opens GitHub)`}
          >
            #{alert.number}
          </a>
        ) : (
          `#${alert.number}`
        ),
    },
  ];
  return columns.filter(Boolean);
}

export const alertKey = (alert) => `${alert.repository}#${alert.number}`;
