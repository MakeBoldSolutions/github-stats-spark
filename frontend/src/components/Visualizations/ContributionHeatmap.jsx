import React, { useMemo, useState } from "react";
import PropTypes from "prop-types";
import { computeHeatmapData } from "../../services/metricsCalculator";
import styles from "./ContributionHeatmap.module.css";

const MONTH_LABELS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/**
 * ContributionHeatmap renders a GitHub-style trailing-365-day calendar heatmap
 * of daily commit counts. Each cell is coloured by intensity level 0–4.
 *
 * @param {Object} props
 * @param {Object} props.activityCalendar  - Map of "YYYY-MM-DD" → commit count
 * @param {string} [props.className]       - Extra CSS class
 */
export default function ContributionHeatmap({ activityCalendar, className }) {
  const [tooltip, setTooltip] = useState(null);

  const cells = useMemo(
    () => computeHeatmapData(activityCalendar),
    [activityCalendar],
  );

  if (!activityCalendar || Object.keys(activityCalendar).length === 0) {
    return (
      <div className={`${styles.heatmap} ${className ?? ""}`.trim()}>
        <p className={styles.empty}>No activity data available.</p>
      </div>
    );
  }

  // Group cells by ISO week (column) and day-of-week (row)
  const columns = [];
  let currentCol = null;
  let currentColKey = null;

  for (const cell of cells) {
    const date = new Date(cell.date + "T00:00:00");
    const dow = date.getDay(); // 0 = Sun

    // Determine ISO week column key (year-week)
    const colDate = new Date(date);
    colDate.setDate(colDate.getDate() - dow); // back to Sunday of this week
    const colKey = colDate.toISOString().slice(0, 10);

    if (colKey !== currentColKey) {
      currentCol = { key: colKey, month: date.getMonth(), cells: [] };
      columns.push(currentCol);
      currentColKey = colKey;
    }

    // Fill blanks at start of first column
    if (currentCol.cells.length === 0 && dow > 0 && columns.length === 1) {
      for (let i = 0; i < dow; i++) {
        currentCol.cells.push(null);
      }
    }

    currentCol.cells.push(cell);
  }

  // Build month label offsets
  const monthOffsets = [];
  let lastMonth = -1;
  columns.forEach((col, idx) => {
    if (col.month !== lastMonth) {
      monthOffsets.push({ month: col.month, colIdx: idx });
      lastMonth = col.month;
    }
  });

  return (
    <div className={`${styles.heatmap} ${className ?? ""}`.trim()}>
      <div className={styles.wrapper}>
        {/* Day-of-week labels */}
        <div className={styles.dayLabels}>
          {DAY_LABELS.map((d, i) => (
            <span
              key={d}
              className={styles.dayLabel}
              style={{ gridRow: i + 1 }}
            >
              {i % 2 === 1 ? d : ""}
            </span>
          ))}
        </div>

        {/* Grid container */}
        <div className={styles.scrollArea}>
          {/* Month labels row */}
          <div
            className={styles.monthRow}
            style={{
              gridTemplateColumns: `repeat(${columns.length}, var(--cell-size))`,
            }}
          >
            {columns.map((col, idx) => {
              const mo = monthOffsets.find((m) => m.colIdx === idx);
              return (
                <span key={col.key} className={styles.monthLabel}>
                  {mo ? MONTH_LABELS[mo.month] : ""}
                </span>
              );
            })}
          </div>

          {/* Cell columns */}
          <div className={styles.grid}>
            {columns.map((col) => (
              <div key={col.key} className={styles.column}>
                {Array.from({ length: 7 }).map((_, dow) => {
                  const cell = col.cells[dow] ?? null;
                  if (!cell) {
                    return <div key={dow} className={styles.cellEmpty} />;
                  }
                  return (
                    <div
                      key={cell.date}
                      className={`${styles.cell} ${styles[`intensity${cell.intensity}`]}`}
                      role="img"
                      aria-label={`${cell.date}: ${cell.count} commit${cell.count !== 1 ? "s" : ""}`}
                      onMouseEnter={(e) =>
                        setTooltip({
                          date: cell.date,
                          count: cell.count,
                          x: e.clientX,
                          y: e.clientY,
                        })
                      }
                      onMouseLeave={() => setTooltip(null)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        <span className={styles.legendLabel}>Less</span>
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`${styles.cell} ${styles[`intensity${i}`]} ${styles.legendCell}`}
            aria-hidden="true"
          />
        ))}
        <span className={styles.legendLabel}>More</span>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className={styles.tooltip}
          style={{ left: tooltip.x + 12, top: tooltip.y - 36 }}
          role="tooltip"
        >
          <strong>
            {tooltip.count} commit{tooltip.count !== 1 ? "s" : ""}
          </strong>
          {" on "}
          {tooltip.date}
        </div>
      )}
    </div>
  );
}

ContributionHeatmap.propTypes = {
  activityCalendar: PropTypes.objectOf(PropTypes.number),
  className: PropTypes.string,
};
