import { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Card } from "@/components/Brand";
import CoverageState from "@/components/Common/CoverageState";
import DataTable from "@/components/Common/DataTable";
import ExportButton from "@/components/Common/ExportButton";
import FilterBar from "@/components/Common/FilterBar";
import {
  ALERT_EXPORT_COLUMNS,
  REASON_LABELS,
  SEVERITY_ORDER,
  STATE_FILTERS,
  coverageGaps,
  filterAlerts,
} from "@/utils/dependabot";
import { alertColumns, alertKey } from "./alertColumns";
import styles from "./SecurityView.module.css";

/**
 * Dependabot alerts for the repositories in scope: totals, a coverage panel
 * that says which repositories could not be read and why, and a filterable
 * alert list. A repository name opens that repository's details.
 */
function SecurityView({ file, onToast, onOpenRepository }) {
  const [filters, setFilters] = useState({
    state: "open",
    severity: "",
    repository: "",
  });
  const set = (key) => (value) =>
    setFilters((previous) => ({ ...previous, [key]: value }));

  const repositoryNames = useMemo(
    () => new Set(file.repositories.map((r) => r.full_name)),
    [file],
  );
  // A repository filter left over from a wider scope no longer applies.
  const repository = repositoryNames.has(filters.repository)
    ? filters.repository
    : "";
  const effective = { ...filters, repository };
  const alerts = useMemo(
    () =>
      filterAlerts(file, {
        state: filters.state,
        severity: filters.severity,
        repository,
      }),
    [file, filters.state, filters.severity, repository],
  );
  const gaps = useMemo(() => coverageGaps(file), [file]);

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
  const columns = useMemo(
    () => alertColumns({ onOpenRepository }),
    [onOpenRepository],
  );

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
                  <CoverageState
                    status={repo.status}
                    reason={REASON_LABELS[repo.reason] ?? repo.reason}
                  />
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
        <FilterBar
          label="Alert filters"
          fields={[
            {
              id: "sec-state",
              label: "State",
              value: effective.state,
              onChange: set("state"),
              allLabel: null,
              options: STATE_FILTERS,
            },
            {
              id: "sec-severity",
              label: "Severity",
              value: effective.severity,
              onChange: set("severity"),
              allLabel: "All severities",
              options: SEVERITY_ORDER.map((s) => ({ value: s, label: s })),
            },
            {
              id: "sec-repository",
              label: "Repository",
              value: effective.repository,
              onChange: set("repository"),
              allLabel: "All repositories",
              options: file.repositories.map((r) => ({
                value: r.full_name,
                label: r.full_name,
              })),
            },
          ]}
        >
          <ExportButton
            data={alerts}
            columns={ALERT_EXPORT_COLUMNS}
            filename="dependabot-alerts"
            noun="alerts"
            jsonDescription="Full alert records"
            disabled={alerts.length === 0}
            onToast={onToast}
          />
        </FilterBar>

        <DataTable
          labelledBy="alerts-heading"
          caption={`Showing ${alerts.length} alert${alerts.length === 1 ? "" : "s"}`}
          columns={columns}
          rows={alerts}
          rowKey={alertKey}
          emptyMessage="No alerts match these filters."
          minWidth={760}
        />
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
  onOpenRepository: PropTypes.func,
};

export default SecurityView;
