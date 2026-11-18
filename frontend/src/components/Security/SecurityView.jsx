import { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Card, Badge } from "@/components/Brand";
import {
  COVERAGE_LABELS,
  REASON_LABELS,
  SEVERITY_ORDER,
  STATE_FILTERS,
  alertsToCsv,
  coverageGaps,
  filterAlerts,
} from "@/utils/dependabot";
import styles from "./SecurityView.module.css";

const SEVERITY_TONE = {
  critical: "critical",
  high: "critical",
  medium: "caution",
  low: "neutral",
  unknown: "neutral",
};

const formatDate = (value) => (value ? value.slice(0, 10) : "—");

function downloadCsv(alerts) {
  const blob = new Blob([alertsToCsv(alerts)], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "dependabot-alerts.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function Select({ id, label, value, onChange, children }) {
  return (
    <label className={styles.field} htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {children}
      </select>
    </label>
  );
}

Select.propTypes = {
  id: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  children: PropTypes.node,
};

/**
 * Dependabot alerts across the portfolio: totals, a coverage panel that says
 * which repositories could not be read and why, and a filterable alert list.
 */
function SecurityView({ file, onToast }) {
  const [filters, setFilters] = useState({
    state: "open",
    severity: "",
    repository: "",
    client: "",
  });
  const set = (key) => (value) =>
    setFilters((previous) => ({ ...previous, [key]: value }));

  const alerts = useMemo(() => filterAlerts(file, filters), [file, filters]);
  const gaps = useMemo(() => coverageGaps(file), [file]);
  const clients = useMemo(
    () => [...new Set(file.repositories.map((r) => r.client).filter(Boolean))],
    [file],
  );

  const totals = useMemo(() => {
    const open = { total: 0, critical: 0, high: 0, medium: 0, low: 0 };
    for (const repo of file.repositories) {
      for (const key of Object.keys(open)) {
        open[key] += repo.counts.open[key] ?? 0;
      }
    }
    return open;
  }, [file]);

  const read = file.repositories.length - gaps.length;

  function handleExport() {
    try {
      downloadCsv(alerts);
      onToast?.(`Exported ${alerts.length} alerts`, "success");
    } catch {
      onToast?.("Export failed", "error");
    }
  }

  return (
    <div className={styles.layout}>
      <div className={styles.summaryGrid}>
        <Card padding="md" className={styles.tile}>
          <span className={styles.summaryLabel}>Open alerts</span>
          <strong className={styles.summaryValue}>{totals.total}</strong>
        </Card>
        {["critical", "high", "medium", "low"].map((severity) => (
          <Card key={severity} padding="md" className={styles.tile}>
            <span className={styles.summaryLabel}>{severity}</span>
            <strong className={styles.summaryValue}>{totals[severity]}</strong>
          </Card>
        ))}
        <Card padding="md" className={styles.tile}>
          <span className={styles.summaryLabel}>Repositories read</span>
          <strong className={styles.summaryValue}>
            {read}/{file.repositories.length}
          </strong>
        </Card>
      </div>

      <p className={styles.notice}>
        A Dependabot alert is not proof that a vulnerability can be exploited in
        your code, and no alerts is not proof that a repository is secure.
        Counts cover only the repositories read.
        {file.generated_at && ` Updated ${formatDate(file.generated_at)}.`}
      </p>

      {gaps.length > 0 && (
        <Card padding="none" className={styles.panel}>
          <section aria-labelledby="coverage-heading">
            <h3 id="coverage-heading">Coverage</h3>
            <p className={styles.notice}>
              {gaps.length}{" "}
              {gaps.length === 1 ? "repository has" : "repositories have"} no
              complete alert data. These are not the same as zero alerts.
            </p>
            <ul className={styles.gapList}>
              {gaps.map((repo) => (
                <li key={repo.full_name}>
                  <strong>{repo.full_name}</strong>{" "}
                  <Badge tone="caution">
                    {COVERAGE_LABELS[repo.status] || repo.status}
                  </Badge>{" "}
                  <span className={styles.muted}>
                    {REASON_LABELS[repo.reason] ?? repo.reason}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </Card>
      )}

      <Card padding="none">
        <div className={styles.tableHeader}>
          <h3 id="alerts-heading">Alerts</h3>
        </div>
        <form
          className={styles.filters}
          aria-label="Alert filters"
          onSubmit={(e) => e.preventDefault()}
        >
          <Select
            id="sec-state"
            label="State"
            value={filters.state}
            onChange={set("state")}
          >
            {STATE_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Select
            id="sec-severity"
            label="Severity"
            value={filters.severity}
            onChange={set("severity")}
          >
            <option value="">All severities</option>
            {SEVERITY_ORDER.map((severity) => (
              <option key={severity} value={severity}>
                {severity}
              </option>
            ))}
          </Select>
          <Select
            id="sec-repository"
            label="Repository"
            value={filters.repository}
            onChange={set("repository")}
          >
            <option value="">All repositories</option>
            {file.repositories.map((repo) => (
              <option key={repo.full_name} value={repo.full_name}>
                {repo.full_name}
              </option>
            ))}
          </Select>
          {clients.length > 0 && (
            <Select
              id="sec-client"
              label="Client"
              value={filters.client}
              onChange={set("client")}
            >
              <option value="">All clients</option>
              {clients.map((client) => (
                <option key={client} value={client}>
                  {client}
                </option>
              ))}
            </Select>
          )}
          <button
            type="button"
            className={styles.exportButton}
            onClick={handleExport}
            disabled={alerts.length === 0}
          >
            Export CSV
          </button>
        </form>

        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-labelledby="alerts-heading">
            <caption role="status" aria-live="polite">
              Showing {alerts.length} alert{alerts.length === 1 ? "" : "s"}
            </caption>
            <thead>
              <tr>
                <th scope="col">Severity</th>
                <th scope="col">Repository</th>
                <th scope="col">Package</th>
                <th scope="col">Advisory</th>
                <th scope="col">Vulnerable</th>
                <th scope="col">Fixed in</th>
                <th scope="col">State</th>
                <th scope="col">Age</th>
                <th scope="col">GitHub</th>
              </tr>
            </thead>
            <tbody>
              {alerts.length === 0 && (
                <tr>
                  <td colSpan={9} className={styles.muted}>
                    No alerts match these filters.
                  </td>
                </tr>
              )}
              {alerts.map((alert) => (
                <tr key={`${alert.repository}#${alert.number}`}>
                  <td>
                    <Badge tone={SEVERITY_TONE[alert.severity] || "neutral"}>
                      {alert.severity}
                    </Badge>
                  </td>
                  <td>{alert.repository}</td>
                  <td>
                    {alert.package || "—"}
                    {alert.ecosystem && (
                      <span className={styles.muted}> ({alert.ecosystem})</span>
                    )}
                  </td>
                  <td title={alert.summary || undefined}>
                    {alert.ghsa_id || alert.cve_id || "—"}
                  </td>
                  <td>{alert.vulnerable_range || "—"}</td>
                  <td>{alert.fixed_version || "No fix yet"}</td>
                  <td>
                    {alert.state}
                    {alert.state === "fixed" &&
                      ` ${formatDate(alert.fixed_at)}`}
                    {alert.state === "dismissed" &&
                      ` ${formatDate(alert.dismissed_at)}`}
                  </td>
                  <td>{alert.age_days == null ? "—" : `${alert.age_days}d`}</td>
                  <td>
                    {alert.html_url ? (
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
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

SecurityView.propTypes = {
  file: PropTypes.shape({
    generated_at: PropTypes.string,
    repositories: PropTypes.array.isRequired,
    alerts: PropTypes.array.isRequired,
  }).isRequired,
  onToast: PropTypes.func,
};

export default SecurityView;
