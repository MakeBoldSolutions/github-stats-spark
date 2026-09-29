import { useMemo } from "react";
import PropTypes from "prop-types";
import { Card } from "@/components/Brand";
import styles from "./ActivityTimeline.module.css";

/**
 * Branded weekly activity timeline: one bar per week (ember, rust for the
 * peak week, a thin stub for empty weeks), with a tick label every 8th week.
 *
 * @param {Object} props
 * @param {Array}  props.weeklyActivity - Array of {week, label, commits, active_repos}
 * @param {string} [props.className]   - Extra CSS class
 */
export default function ActivityTimeline({ weeklyActivity, className }) {
  const weeks = useMemo(
    () => (Array.isArray(weeklyActivity) ? weeklyActivity : []),
    [weeklyActivity],
  );

  if (weeks.length === 0) {
    return (
      <Card
        padding="lg"
        className={`${styles.timeline} ${className ?? ""}`.trim()}
      >
        <p className={styles.empty}>No weekly activity data available.</p>
      </Card>
    );
  }

  const maxCommits = Math.max(...weeks.map((w) => w.commits || 0), 1);
  const peakIndex = weeks.reduce(
    (best, w, i) => ((w.commits || 0) > (weeks[best].commits || 0) ? i : best),
    0,
  );
  const peakWeek = weeks[peakIndex];

  return (
    <Card
      padding="lg"
      className={`${styles.timeline} ${className ?? ""}`.trim()}
    >
      <p className={styles.header}>
        Peak week: {peakWeek.label ?? peakWeek.week} ·{" "}
        {(peakWeek.commits || 0).toLocaleString()} commits
      </p>
      <div className={styles.chart}>
        {weeks.map((w, i) => {
          const commits = w.commits || 0;
          const heightPct =
            commits > 0 ? Math.max((commits / maxCommits) * 100, 4) : 0.8;
          const isPeak = i === peakIndex && commits > 0;
          return (
            <div
              key={w.week ?? i}
              className={styles.barWrapper}
              title={`Week of ${w.label ?? w.week}: ${commits} commit${commits !== 1 ? "s" : ""}`}
            >
              <div
                className={`${styles.bar} ${commits === 0 ? styles.barEmpty : ""} ${isPeak ? styles.barPeak : ""}`}
                style={{ height: `${heightPct}%` }}
              />
              {i % 8 === 0 && (
                <span className={styles.tick}>{w.label ?? w.week}</span>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

ActivityTimeline.propTypes = {
  weeklyActivity: PropTypes.arrayOf(
    PropTypes.shape({
      week: PropTypes.string.isRequired,
      label: PropTypes.string,
      commits: PropTypes.number,
      active_repos: PropTypes.number,
    }),
  ),
  className: PropTypes.string,
};
