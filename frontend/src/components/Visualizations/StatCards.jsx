import PropTypes from "prop-types";
import { Card, Eyebrow } from "@/components/Brand";
import styles from "./StatCards.module.css";

function StatCard({ label, value, sublabel, tone }) {
  return (
    <Card padding="md" className={styles.card}>
      <Eyebrow as="span" color="muted" className={styles.label}>
        {label}
      </Eyebrow>
      <div className={`${styles.value} ${tone ? styles[tone] : ""}`}>
        {value}
      </div>
      {sublabel && <div className={styles.sublabel}>{sublabel}</div>}
    </Card>
  );
}

export default function StatCards({ repositories }) {
  const getTotalCommits = (repo) =>
    repo.commit_history?.total_commits || repo.total_commits || 0;

  const getOpenPullRequests = (repo) =>
    repo.pull_request_summary?.availability === "available"
      ? repo.pull_request_summary.total_open || 0
      : 0;

  const getOpenSecurityAlerts = (repo) =>
    repo.security_summary?.availability === "available"
      ? repo.security_summary.active_alert_counts?.total_open || 0
      : 0;

  const totalRepos = repositories.length;
  const activeRepos = repositories.filter(
    (r) => (r.days_since_last_push ?? 999) <= 30,
  ).length;

  const totalCommits = repositories.reduce(
    (sum, r) => sum + getTotalCommits(r),
    0,
  );

  const languages = [
    ...new Set(repositories.map((r) => r.language).filter(Boolean)),
  ];

  const readmeCoveragePct =
    totalRepos > 0
      ? Math.round(
          (repositories.filter((r) => r.has_readme).length / totalRepos) * 100,
        )
      : 0;

  const totalOpenPullRequests = repositories.reduce(
    (sum, r) => sum + getOpenPullRequests(r),
    0,
  );
  const reposWithOpenPullRequests = repositories.filter(
    (r) => getOpenPullRequests(r) > 0,
  ).length;

  const totalSecurityAlerts = repositories.reduce(
    (sum, r) => sum + getOpenSecurityAlerts(r),
    0,
  );
  const reposWithSecurityAlerts = repositories.filter(
    (r) => getOpenSecurityAlerts(r) > 0,
  ).length;

  return (
    <div className={styles.grid}>
      <StatCard
        label="Repositories"
        value={totalRepos}
        sublabel={`${activeRepos} active in 30 days`}
      />
      <StatCard
        label="Total commits"
        value={totalCommits.toLocaleString()}
        sublabel="All-time"
      />
      <StatCard
        label="Languages"
        value={languages.length}
        sublabel="Primary languages"
      />
      <StatCard
        label="README coverage"
        value={`${readmeCoveragePct}%`}
        sublabel="Repos with a README"
      />
      <StatCard
        label="Open pull requests"
        value={totalOpenPullRequests.toLocaleString()}
        sublabel={`${reposWithOpenPullRequests} repos with open PRs`}
        tone="brand"
      />
      <StatCard
        label="Security alerts"
        value={totalSecurityAlerts.toLocaleString()}
        sublabel={`${reposWithSecurityAlerts} repos with alerts`}
        tone={totalSecurityAlerts > 0 ? "critical" : "positive"}
      />
    </div>
  );
}

StatCards.propTypes = {
  repositories: PropTypes.array.isRequired,
};
