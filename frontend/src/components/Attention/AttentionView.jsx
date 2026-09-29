import { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Card, Badge, Eyebrow } from "@/components/Brand";
import ExportButton from "@/components/Common/ExportButton";
import { getTierTone, getTierLabel } from "@/utils/repositoryPresentation";
import styles from "./AttentionView.module.css";

const COMPONENT_ROWS = [
  { key: "pull_requests", label: "Pull requests" },
  { key: "security", label: "Security findings" },
  { key: "staleness", label: "Staleness" },
  { key: "dependencies", label: "Dependency health" },
];

function getComponents(repo) {
  return repo.attention_metrics?.components || {};
}

function getComponentScore(repo, key) {
  return getComponents(repo)[key]?.score;
}

function getSecurityAlerts(repo) {
  return getComponents(repo).security?.active_alert_counts?.total_open ?? 0;
}

function getOpenPullRequests(repo) {
  const prs = getComponents(repo).pull_requests;
  return prs?.total_open ?? null;
}

function scoreThresholdClass(score) {
  if (score >= 60) return styles.scoreCritical;
  if (score >= 30) return styles.scoreCaution;
  return styles.scorePositive;
}

function getSortValue(repo, key) {
  switch (key) {
    case "score":
      return repo.attention_score ?? 0;
    case "name":
      return repo.name.toLowerCase();
    case "tier": {
      const order = { critical: 4, elevated: 3, watch: 2, healthy: 1 };
      return order[repo.attention_metrics?.tier] ?? 0;
    }
    case "prs":
      return getOpenPullRequests(repo) ?? -1;
    case "alerts":
      return getSecurityAlerts(repo);
    case "stale":
      return repo.days_since_last_push ?? -1;
    case "readme":
      return repo.has_readme ? 1 : 0;
    default:
      return 0;
  }
}

function AttentionView({ repositories, onRepoClick, onToast }) {
  const rankedRepositories = useMemo(() => {
    return [...repositories].sort(
      (a, b) => (b.attention_score ?? 0) - (a.attention_score ?? 0),
    );
  }, [repositories]);

  const summary = useMemo(() => {
    const needsAttention = rankedRepositories.filter(
      (r) => r.attention_metrics?.needs_attention,
    );
    return {
      total: needsAttention.length,
      critical: rankedRepositories.filter(
        (r) => r.attention_metrics?.tier === "critical",
      ).length,
      securityBacklog: rankedRepositories.filter(
        (r) => getSecurityAlerts(r) > 0,
      ).length,
      stale: rankedRepositories.filter(
        (r) => (r.days_since_last_push ?? 0) >= 90,
      ).length,
    };
  }, [rankedRepositories]);

  const methodology = useMemo(() => {
    const n = rankedRepositories.length || 1;
    return COMPONENT_ROWS.map(({ key, label }) => {
      const scores = rankedRepositories
        .map((r) => getComponentScore(r, key))
        .filter((s) => typeof s === "number");
      const average = scores.length
        ? scores.reduce((sum, s) => sum + s, 0) / scores.length
        : 0;
      const hit = rankedRepositories.filter((r) =>
        r.attention_metrics?.reasons?.includes(key),
      ).length;
      return { key, label, hit, total: n, average };
    });
  }, [rankedRepositories]);

  const [sort, setSort] = useState({ key: "score", dir: "desc" });

  function handleSort(key) {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "desc" ? "asc" : "desc" }
        : { key, dir: "desc" },
    );
  }

  function handleKeyboardAction(event, action) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      action();
    }
  }

  const displayRows = useMemo(() => {
    return [...rankedRepositories].sort((a, b) => {
      const av = getSortValue(a, sort.key);
      const bv = getSortValue(b, sort.key);
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
  }, [rankedRepositories, sort]);

  function sortIcon(key) {
    if (sort.key !== key) return "↕";
    return sort.dir === "asc" ? "↑" : "↓";
  }

  const columns = [
    { key: "name", label: "Repository" },
    { key: "tier", label: "Tier" },
    { key: "score", label: "Score" },
    { key: "prs", label: "PRs" },
    { key: "alerts", label: "Alerts" },
    { key: "stale", label: "Stale (days)" },
    { key: "readme", label: "README" },
  ];

  return (
    <div className={styles.layout}>
      <div className={styles.summaryGrid}>
        <Card padding="md" className={styles.tileNeedsAttention}>
          <span className={styles.summaryLabel}>Need attention</span>
          <strong className={styles.summaryValue}>{summary.total}</strong>
        </Card>
        <Card padding="md" className={styles.tile}>
          <span className={styles.summaryLabel}>Critical</span>
          <strong
            className={`${styles.summaryValue} ${summary.critical > 0 ? styles.valueCritical : ""}`}
          >
            {summary.critical}
          </strong>
        </Card>
        <Card padding="md" className={styles.tile}>
          <span className={styles.summaryLabel}>Security backlog</span>
          <strong className={styles.summaryValue}>
            {summary.securityBacklog}
          </strong>
        </Card>
        <Card padding="md" className={styles.tile}>
          <span className={styles.summaryLabel}>Stale 90+ days</span>
          <strong className={styles.summaryValue}>{summary.stale}</strong>
        </Card>
      </div>

      <div className={styles.body}>
        <Card padding="none" className={styles.tableCard}>
          <div className={styles.tableHeader}>
            <div>
              <h3>Maintenance ranking</h3>
              <p>
                Higher scores indicate greater need for maintainer attention.
              </p>
            </div>
            <ExportButton
              data={displayRows}
              filename="health-ranking"
              label="Export"
              onToast={onToast}
            />
          </div>

          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>#</th>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      className={`${styles.sortable} ${sort.key === col.key ? styles.sortActive : ""}`}
                      aria-sort={
                        sort.key === col.key
                          ? sort.dir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      <button
                        type="button"
                        className={styles.sortButton}
                        onClick={() => handleSort(col.key)}
                        onKeyDown={(event) =>
                          handleKeyboardAction(event, () => handleSort(col.key))
                        }
                        aria-label={`Sort by ${col.label}`}
                      >
                        {col.label}
                        <span className={styles.sortIcon} aria-hidden="true">
                          {sortIcon(col.key)}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayRows.map((repo, index) => {
                  const tier = repo.attention_metrics?.tier;
                  const score = repo.attention_score ?? 0;
                  const openPrs = getOpenPullRequests(repo);
                  return (
                    <tr key={repo.name} className={styles.row}>
                      <td>{index + 1}</td>
                      <td>
                        <div className={styles.repoCell}>
                          <button
                            type="button"
                            className={styles.repoButton}
                            onClick={() => onRepoClick?.(repo, displayRows)}
                            onKeyDown={(event) =>
                              handleKeyboardAction(event, () =>
                                onRepoClick?.(repo, displayRows),
                              )
                            }
                            aria-label={`Open details for ${repo.name}`}
                          >
                            {repo.name}
                          </button>
                          <span>{repo.language || "Unknown"}</span>
                        </div>
                      </td>
                      <td>
                        <Badge tone={getTierTone(tier)}>
                          {getTierLabel(tier)}
                        </Badge>
                      </td>
                      <td>
                        <div className={styles.scoreCell}>
                          <span
                            className={`${styles.scoreBar} ${scoreThresholdClass(score)}`}
                          />
                          {score.toFixed(0)}
                        </div>
                      </td>
                      <td>{openPrs ?? "n/a"}</td>
                      <td>{getSecurityAlerts(repo)}</td>
                      <td>{repo.days_since_last_push ?? "n/a"}</td>
                      <td
                        className={!repo.has_readme ? styles.readmeMissing : ""}
                      >
                        {repo.has_readme ? "Yes" : "No"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <aside className={styles.explainerCard}>
          <Eyebrow color="onDark">Methodology</Eyebrow>
          <h3 className={styles.explainerTitle}>What drives the score</h3>
          <ul className={styles.explainerList}>
            {methodology.map(({ key, label, hit, total, average }) => (
              <li key={key} className={styles.methodologyRow}>
                <div className={styles.methodologyLabelRow}>
                  <span>{label}</span>
                  <span className={styles.methodologyCount}>
                    {hit} of {total} repos
                  </span>
                </div>
                <div className={styles.methodologyTrack}>
                  <div
                    className={styles.methodologyFill}
                    style={{ width: `${Math.min(average, 100)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
          <p className={styles.explainerFootnote}>
            Bars show average component score across the portfolio. Tiers:
            Healthy, Watch, Elevated, Critical.
          </p>
        </aside>
      </div>
    </div>
  );
}

AttentionView.propTypes = {
  repositories: PropTypes.array.isRequired,
  onRepoClick: PropTypes.func,
};

export default AttentionView;
