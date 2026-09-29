import { Suspense, lazy, useCallback, useMemo } from "react";
import PropTypes from "prop-types";
import StatCards from "./StatCards";
import LoadingState from "@/components/Common/LoadingState";
import { Card } from "@/components/Brand";
import { getLanguageColor } from "@/utils/repositoryPresentation";
import styles from "./DashboardView.module.css";

const BarChart = lazy(() => import("./BarChart"));
const PieChart = lazy(() => import("./PieChart"));
const ActivityTimeline = lazy(() => import("./ActivityTimeline"));
const QualityMatrix = lazy(() => import("./QualityMatrix"));

export default function DashboardView({ repositories, profile, onRepoClick }) {
  const commitData = useMemo(() => {
    return [...repositories]
      .sort((a, b) => (b.total_commits || 0) - (a.total_commits || 0))
      .map((r) => ({
        name: r.name,
        value: r.total_commits || 0,
        language: r.language || "Unknown",
        fullData: r,
      }));
  }, [repositories]);

  const languageData = useMemo(() => {
    const counts = {};
    repositories.forEach((r) => {
      const lang = r.language || "Unknown";
      counts[lang] = (counts[lang] || 0) + 1;
    });
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [repositories]);

  const recentActivityData = useMemo(() => {
    return [...repositories]
      .filter((r) => (r.recent_commits_90d ?? 0) > 0)
      .sort((a, b) => (b.recent_commits_90d || 0) - (a.recent_commits_90d || 0))
      .map((r) => ({
        name: r.name,
        value: r.recent_commits_90d || 0,
        language: r.language || "Unknown",
        fullData: r,
      }));
  }, [repositories]);

  const handleChartClick = useCallback(
    (data) => {
      if (data?.fullData && onRepoClick) {
        onRepoClick(data.fullData);
      }
    },
    [onRepoClick],
  );

  return (
    <div className={styles.panels}>
      <StatCards repositories={repositories} profile={profile} />

      <div className={styles.twoCol}>
        <Card padding="lg">
          <h3 className={styles.panelTitle}>Total commits</h3>
          <Suspense fallback={<LoadingState message="Loading chart..." />}>
            <BarChart
              data={commitData}
              metricLabel="Total Commits"
              onBarClick={handleChartClick}
              horizontal={true}
              maxBars={30}
            />
          </Suspense>
        </Card>

        <div className={styles.stack}>
          <Card padding="lg">
            <h3 className={styles.panelTitle}>Language distribution</h3>
            <Suspense fallback={<LoadingState message="Loading chart..." />}>
              <PieChart
                data={languageData}
                title="Language Distribution"
                doughnut={true}
                cutout={50}
              />
            </Suspense>
            <ul className={styles.legendList}>
              {languageData.map((lang) => (
                <li key={lang.name} className={styles.legendItem}>
                  <span
                    className={styles.legendSwatch}
                    style={{ background: getLanguageColor(lang.name) }}
                    aria-hidden="true"
                  />
                  {lang.name}
                  <span className={styles.legendCount}>{lang.value}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card padding="lg">
            <h3 className={styles.panelTitle}>Commits, last 90 days</h3>
            <Suspense fallback={<LoadingState message="Loading chart..." />}>
              <BarChart
                data={recentActivityData}
                metricLabel="Commits (Last 90 Days)"
                onBarClick={handleChartClick}
                horizontal={true}
                maxBars={20}
              />
            </Suspense>
          </Card>
        </div>
      </div>

      <Suspense fallback={<LoadingState message="Loading timeline..." />}>
        <ActivityTimeline weeklyActivity={profile?.weekly_activity} />
      </Suspense>

      <Suspense fallback={<LoadingState message="Loading quality matrix..." />}>
        <QualityMatrix repositories={repositories} onRepoClick={onRepoClick} />
      </Suspense>
    </div>
  );
}

DashboardView.propTypes = {
  repositories: PropTypes.array.isRequired,
  profile: PropTypes.object,
  onRepoClick: PropTypes.func,
};
